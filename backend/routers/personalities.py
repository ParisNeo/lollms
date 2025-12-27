# backend/routers/personalities.py
import traceback
import json
from typing import List, Dict, Optional
import io
import base64
import zipfile
import yaml
from PIL import Image

# Third-Party Imports
from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File, Response
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, and_

# Local Application Imports
from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.db_task import DBTask
from backend.models import (
    UserAuthDetails, PersonalityPublic, PersonalityCreate,
    PersonalityUpdate, PersonalitySendRequest,
    GeneratePersonalityFromPromptRequest, TaskInfo,
    EnhancePromptRequest, GenerateIconRequest
)
from backend.session import (
    get_current_active_user,
    get_current_db_user_from_token,
    user_sessions,
    get_user_lollms_client,
    build_lollms_client_from_params
)
from backend.task_manager import task_manager, Task
from backend.settings import settings
from ascii_colors import trace_exception, ASCIIColors

personalities_router = APIRouter(prefix="/api/personalities", tags=["Personalities"])

def _to_task_info(db_task: DBTask) -> TaskInfo:
    """Converts a DBTask SQLAlchemy model to a TaskInfo Pydantic model."""
    if not db_task:
        return None
    return TaskInfo(
        id=db_task.id, name=db_task.name, description=db_task.description,
        status=db_task.status, progress=db_task.progress,
        logs=[log for log in (db_task.logs or [])], result=db_task.result, error=db_task.error,
        created_at=db_task.created_at, started_at=db_task.started_at, completed_at=db_task.completed_at,
        file_name=db_task.file_name, total_files=db_task.total_files,
        owner_username=db_task.owner.username if db_task.owner else "System"
    )
    
# --- Task for Personality Generation ---
def _generate_personality_task(task: Task, username: str, prompt: str):
    task.log("Starting personality generation...")
    task.set_progress(10)
    
    with task.db_session_factory() as db_session:
        lc = get_user_lollms_client(username)
        current_user = db_session.query(DBUser).filter(DBUser.username == username).first()
        if not current_user:
            raise Exception("User not found for personality generation task.")

        personality_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Short, catchy name for the personality."},
                "category": {"type": "string", "description": "Category for the personality (e.g., 'Creative', 'Coding', 'Educational')."},
                "author": {"type": "string", "description": "The author or creator of the personality."},
                "description": {"type": "string", "description": "A brief overview of the personality's purpose and style, for display in the UI."},
                "prompt_text": {"type": "string", "description": "The core system prompt that defines the AI's role, rules, and initial instructions for character."},
                "disclaimer": {"type": "string", "description": "Any necessary warnings or disclaimers users should be aware of."},
                "script_code": {"type": "string", "description": "Optional Python code for advanced behaviors. Can be empty."},
                "active_mcps": {"type": "array", "items": {"type": "string"}, "description": "A list of default MCP tools to activate with this personality."},
                "required_context_options": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["image_generation", "image_editing", "slide_maker", "note_generation", "memory"]
                    },
                    "description": "List of mandatory context features required for this personality. Select 'image_generation' if the personality is visual/artist, 'memory' if it needs long-term memory, etc."
                }
            },
            "required": ["name", "prompt_text"],
            "description": "JSON object defining a LoLLMs personality."
        }

        system_prompt = f"""You are an expert personality designer for AI chatbots.
Your task is to create a new personality based on the user's prompt.
Analyze the requested personality and intelligently select 'required_context_options'.
For example:
- If the personality is an Artist or Designer, select 'image_generation'.
- If it's a Writer or Editor, 'image_generation' is likely unnecessary.
- If it needs to remember long-term details, select 'memory'."""

        task.log("Sending prompt to LLM for JSON generation...")
        task.set_progress(30)
        
        generated_data_dict = lc.generate_structured_content(prompt,
                                                             system_prompt=system_prompt,
                                                             schema=personality_schema,
                                                             #n_predict=settings.get("default_llm_ctx_size")
                                                            )

        if not generated_data_dict:
             raise Exception("Failed to generate personality structure from LLM.")

        # --- Auto-Icon Generation if TTI is active ---
        if current_user.tti_binding_model_name:
            task.log("TTI engine detected. Generating personality icon...")
            task.set_progress(60)
            try:
                # 1. Use LLM to generate a specific image prompt from the description
                image_prompt_request = f"""Create a detailed image generation prompt for a profile icon based on this personality:
Name: {generated_data_dict.get('name')}
Description: {generated_data_dict.get('description')}
Category: {generated_data_dict.get('category')}

The prompt should specify the subject, art style, lighting, and composition. Ensure it is suitable for a square icon. Return ONLY the prompt."""
                
                icon_gen_prompt = lc.generate_text(image_prompt_request, max_new_tokens=150).strip()
                task.log(f"LLM generated icon prompt: {icon_gen_prompt}")

                # 2. Initialize TTI client
                tti_client = build_lollms_client_from_params(username=username, load_llm=False, load_tti=True)
                
                if tti_client.tti:
                    img_bytes = None
                    try:
                        img_bytes = tti_client.tti.generate_image(
                            prompt=icon_gen_prompt, 
                            negative_prompt="bad quality, ugly, deformed, text, watermark, nsfw",
                            width=512, 
                            height=512
                        )
                    except Exception as e:
                        # Safety filter fallback
                        task.log(f"Initial icon generation failed ({e}). Trying safe fallback.", "WARNING")
                        img_bytes = tti_client.tti.generate_image(
                            prompt="Abstract digital avatar icon, geometric shapes, blue and white, minimalist, high quality",
                            negative_prompt="nsfw, blurry, text",
                            width=512, 
                            height=512
                        )
                    
                    if img_bytes:
                        if isinstance(img_bytes, list): 
                            img_bytes = img_bytes[0]
                        
                        # Handle pre-encoded data vs raw bytes
                        if isinstance(img_bytes, str) and img_bytes.startswith('data:'):
                             generated_data_dict['icon_base64'] = img_bytes
                        elif isinstance(img_bytes, (bytes, bytearray)):
                             image = Image.open(io.BytesIO(img_bytes))
                             image.thumbnail((128, 128))
                             buffered = io.BytesIO()
                             image.save(buffered, format="PNG")
                             img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                             generated_data_dict['icon_base64'] = f"data:image/png;base64,{img_b64}"
                    
                    task.log("Icon generated successfully.")
            except Exception as e:
                task.log(f"Failed to generate icon: {e}", "WARNING")
                trace_exception(e)

        task.log("Creating new personality in the database...")
        task.set_progress(90)

        # FIX: Clear active_mcps to prevent hallucinated tools, but keep required_context_options
        generated_data_dict['active_mcps'] = []
        
        existing_personality = db_session.query(DBPersonality).filter(
            DBPersonality.owner_user_id == current_user.id,
            DBPersonality.name == generated_data_dict.get("name")
        ).first()
        if existing_personality:
            task.log(f"Personality '{generated_data_dict.get('name')}' already exists. Appending UUID to make it unique.", "WARNING")
            generated_data_dict["name"] = f"{generated_data_dict.get('name')} {task.id.split('-')[0]}"

        new_personality = DBPersonality(
            owner_user_id=current_user.id,
            is_public=False,
            **generated_data_dict
        )
        db_session.add(new_personality)
        db_session.commit()
        db_session.refresh(new_personality, ["owner"])

        task.log("Personality created and saved successfully.")
        task.set_progress(100)
        
        return get_personality_public_from_db(new_personality, username).model_dump(mode='json')

# --- Task for Prompt Enhancement ---
def _enhance_prompt_task(task: Task, username: str, prompt_text: str, custom_instruction: Optional[str]):
    task.log("Starting prompt enhancement...")
    task.set_progress(10)

    lc = get_user_lollms_client(username)

    enhance_instruction = custom_instruction.strip() if custom_instruction else "Enhance the prompt:"
    enhance_instruction +=f"\nOriginal system prompt:\n{prompt_text}\n"
    # Define the schema for personality generation
    output_schema = {
        "type": "object",
        "properties": {
            "enhanced_system_prompt": {"type": "string", "description": "The core system prompt that defines the AI's role, rules, and initial instructions for character enhanced from the original one using the instructions provided by the user."},
        },
        "required": ["name", "enhanced_system_prompt"],
        "description": "JSON object defining a LoLLMs personality system prompt."
    }

    system_prompt = f"""You are an expert personality designer for AI chatbots.
Your task is to enhance the current system prompt of the personality.
You return the JSON without any comments or placeholders."""

    task.log("Sending prompt to LLM for JSON generation...")
    task.set_progress(30)
    
    generated_data_dict = lc.generate_structured_content(enhance_instruction,
                                                            system_prompt=system_prompt,
                                                            schema=output_schema,
                                                            #n_predict=settings.get("default_llm_ctx_size")
                                                        )
    
    task.log("Prompt enhanced successfully.")
    task.set_progress(100)
    return generated_data_dict

# --- Task for Icon Generation ---
def _generate_icon_task(task: Task, username: str, prompt: str):
    task.log("Starting icon generation...")
    task.set_progress(10)
    
    try:
        # Load BOTH LLM (for prompt refinement) and TTI (for generation)
        lc = build_lollms_client_from_params(username=username, load_llm=True, load_tti=True)
        
        if not lc.tti:
            raise Exception("Text-to-Image service is not configured for this user.")

        # 1. Refine Prompt using LLM
        task.log("Refining image prompt with LLM...")
        refinement_sys_prompt = "You are an expert prompt engineer for AI art. Convert the user's description into a high-quality, detailed stable diffusion prompt for a profile icon. Focus on style, lighting, and subject. Output ONLY the prompt."
        
        refined_prompt = lc.generate_text(prompt, system_prompt=refinement_sys_prompt, max_new_tokens=200).strip()
        task.log(f"Refined Prompt: {refined_prompt}")

        task.log(f"Generating image using TTI engine: {lc.tti.config.get('model_name', 'default')}")
        
        img_data = None
        
        # Helper to process result
        def process_img_bytes(img_bytes):
            if not img_bytes: return None
            if isinstance(img_bytes, list): img_bytes = img_bytes[0]
            
            if isinstance(img_bytes, str):
                if img_bytes.startswith("data:"):
                    return img_bytes
                # Try base64 decode if it's a raw b64 string
                try:
                    base64.b64decode(img_bytes)
                    return f"data:image/png;base64,{img_bytes}"
                except:
                    pass

            if isinstance(img_bytes, (bytes, bytearray)):
                image = Image.open(io.BytesIO(img_bytes))
                image.thumbnail((128, 128))
                buf = io.BytesIO()
                image.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                return f"data:image/png;base64,{b64}"
            return None

        # 2. Try Primary Prompt (Refined)
        try:
            # Add safety modifiers to the user prompt to try and guide it
            safe_prompt = f"{refined_prompt}, safe content, pg-13, no nudity, no violence"
            img_data = lc.tti.generate_image(
                prompt=safe_prompt, 
                negative_prompt="bad quality, ugly, deformed, text, watermark, nsfw, nudity, violence, explicit",
                width=512, 
                height=512
            )
        except Exception as e:
            error_msg = str(e).lower()
            task.log(f"Primary generation failed: {str(e)}", "WARNING")
            
            # Check for common content filter errors
            safety_keywords = ["prohibited", "content", "filter", "safety", "blocked", "policy", "nsfw"]
            is_safety_error = any(k in error_msg for k in safety_keywords)
            
            if is_safety_error:
                task.log("Safety filter detected. Switching to abstract fallback.", "INFO")
                # 3. Try Safe Fallback
                try:
                    fallback_prompt = "Abstract digital avatar icon, colorful geometric shapes, high quality, minimalist, safe content"
                    img_data = lc.tti.generate_image(
                        prompt=fallback_prompt, 
                        negative_prompt="nsfw, blurry, text, realistic, face, body",
                        width=512, 
                        height=512
                    )
                except Exception as fallback_error:
                    task.log(f"Fallback generation also failed: {fallback_error}", "ERROR")
                    raise e # Raise original error if fallback fails
            else:
                raise e # Raise non-safety errors (network, auth, etc)

        icon_b64 = process_img_bytes(img_data)
        
        if not icon_b64:
             raise Exception("Image generation failed: TTI engine returned no data.")

        task.set_progress(100)
        task.log("Icon generated successfully.")
        return {"icon_base64": icon_b64}

    except Exception as e:
        task.log(f"Icon generation failed: {e}", "ERROR")
        trace_exception(e)
        raise e

@personalities_router.post("/generate_icon", response_model=TaskInfo, status_code=202)
async def generate_personality_icon(
    payload: GenerateIconRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    task = task_manager.submit_task(
        name="Generate Icon",
        target=_generate_icon_task,
        args=(current_user.username, payload.prompt),
        description="Generating icon from prompt.",
        owner_username=current_user.username
    )
    return task

# --- Personality Generation from Prompt Endpoint ---
@personalities_router.post("/generate_from_prompt", response_model=TaskInfo, status_code=202)
async def generate_personality_from_prompt(
    payload: GeneratePersonalityFromPromptRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    prompt = payload.prompt
    
    db_task = task_manager.submit_task(
        name="Generate Personality from Prompt",
        target=_generate_personality_task,
        args=(current_user.username, prompt),
        description=f"Generating personality from prompt: '{prompt[:50]}...'",
        owner_username=current_user.username
    )
    return db_task

# --- Prompt Enhancement Endpoint ---
@personalities_router.post("/enhance_prompt", response_model=TaskInfo, status_code=202)
async def enhance_personality_prompt(
    payload: EnhancePromptRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    prompt_text = payload.prompt_text
    custom_instruction = payload.modification_prompt

    if not prompt_text:
        raise HTTPException(status_code=400, detail="Prompt text is required for enhancement.")

    db_task = task_manager.submit_task(
        name="Enhance Personality Prompt",
        target=_enhance_prompt_task,
        args=(current_user.username, prompt_text, custom_instruction),
        description="Enhancing personality system prompt.",
        owner_username=current_user.username
    )
    return db_task


def get_personality_public_from_db(db_personality: DBPersonality, owner_username: Optional[str] = None) -> PersonalityPublic:
    if owner_username is None:
        owner_username = db_personality.owner.username if db_personality.owner else "System"
    
    return PersonalityPublic(
        id=db_personality.id,
        name=db_personality.name,
        category=db_personality.category,
        author=db_personality.author,
        description=db_personality.description,
        prompt_text=db_personality.prompt_text,
        disclaimer=db_personality.disclaimer,
        script_code=db_personality.script_code,
        icon_base64=db_personality.icon_base64,
        created_at=db_personality.created_at,
        updated_at=db_personality.updated_at,
        is_public=db_personality.is_public,
        active_mcps=db_personality.active_mcps or [],
        required_context_options=db_personality.required_context_options or [],
        owner_username=owner_username,
        data_source_type=db_personality.data_source_type,
        data_source=db_personality.data_source
    )

@personalities_router.post("", response_model=PersonalityPublic, status_code=201)
async def create_personality(personality_data: PersonalityCreate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> PersonalityPublic:
    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
    
    # --- NEW, more robust authorization checks ---
    if not current_user.is_admin:
        # For non-admins, always force ownership and privacy, ignoring any passed-in values.
        owner_id = db_user.id
        is_public = False
    else: # User is an admin
        if personality_data.owner_type == 'system':
            owner_id = None  # System personalities have no owner
        else:
            owner_id = db_user.id
        is_public = personality_data.is_public
    
    # --- Check for name collision ---
    q = db.query(DBPersonality).filter(DBPersonality.name == personality_data.name)
    if owner_id:
        q = q.filter(DBPersonality.owner_user_id == owner_id)
    else: # System personality check
        q = q.filter(DBPersonality.owner_user_id.is_(None))

    if q.first():
        scope = "system-wide" if owner_id is None else "your account"
        raise HTTPException(status_code=400, detail=f"A personality named '{personality_data.name}' already exists for {scope}.")

    # --- Create personality in DB ---
    db_personality = DBPersonality(
        **personality_data.model_dump(exclude={"is_public", "owner_type"}),
        owner_user_id=owner_id,
        is_public=is_public
    )

    try:
        db.add(db_personality)
        db.commit()
        db.refresh(db_personality)
        return get_personality_public_from_db(db_personality, current_user.username if owner_id else "System")
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Personality name conflict (race condition).")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@personalities_router.get("/my", response_model=List[PersonalityPublic])
async def get_my_personalities(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[PersonalityPublic]:
    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
    
    owned_personalities_db = db.query(DBPersonality).filter(DBPersonality.owner_user_id == db_user.id).order_by(DBPersonality.name).all()
    return [get_personality_public_from_db(p, current_user.username) for p in owned_personalities_db]

@personalities_router.get("/public", response_model=List[PersonalityPublic])
async def get_public_personalities(db: Session = Depends(get_db)) -> List[PersonalityPublic]:
    public_personalities_db = db.query(DBPersonality).options(joinedload(DBPersonality.owner)).filter(or_(DBPersonality.is_public == True, DBPersonality.owner_user_id.is_(None))).order_by(DBPersonality.category, DBPersonality.name).all()
    return [get_personality_public_from_db(p) for p in public_personalities_db]

@personalities_router.get("/{personality_id}", response_model=PersonalityPublic)
async def get_personality(personality_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> PersonalityPublic:
    db_personality = db.query(DBPersonality).options(joinedload(DBPersonality.owner)).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    is_owner = (db_personality.owner_user_id == current_user.id)
    is_system = db_personality.owner_user_id is None
    is_public = db_personality.is_public

    if not is_public and not is_system and not is_owner:
        raise HTTPException(status_code=403, detail="You do not have permission to view this personality.")
    
    return get_personality_public_from_db(db_personality)

@personalities_router.put("/{personality_id}", response_model=PersonalityPublic)
async def update_personality(personality_id: str, personality_data: PersonalityUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> PersonalityPublic:
    db_personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    is_owner = (db_personality.owner_user_id == current_user.id)

    if not is_owner and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="You do not have permission to update this personality.")
    
    update_data = personality_data.model_dump(exclude_unset=True)

    # Securely handle changes to the 'is_public' flag
    if 'is_public' in update_data:
        # Check if the user is attempting to CHANGE the public status
        if update_data['is_public'] != db_personality.is_public:
            if not current_user.is_admin:
                raise HTTPException(status_code=403, detail="Only administrators can change the public status of a personality.")
            # If admin, allow the change
            db_personality.is_public = update_data['is_public']
        # If the status is not being changed, we don't need to do anything.
        # This allows a non-admin to save their private personality without error.
        del update_data['is_public'] # Remove from dict to avoid reprocessing

    if "name" in update_data and update_data["name"] != db_personality.name:
        owner_id_for_check = db_personality.owner_user_id
        q = db.query(DBPersonality).filter(
            DBPersonality.name == update_data["name"],
            DBPersonality.id != personality_id
        )
        if owner_id_for_check:
            q = q.filter(DBPersonality.owner_user_id == owner_id_for_check)
        else:
            q = q.filter(DBPersonality.owner_user_id.is_(None))
        
        if q.first():
            scope = "system-wide" if owner_id_for_check is None else "your account"
            raise HTTPException(status_code=400, detail=f"A personality named '{update_data['name']}' already exists for {scope}.")

    for field, value in update_data.items():
        if hasattr(db_personality, field):
            setattr(db_personality, field, value)
    
    try:
        db.commit()
        db.refresh(db_personality, attribute_names=['owner']) 
        return get_personality_public_from_db(db_personality)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Personality name conflict (race condition).")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@personalities_router.delete("/{personality_id}", status_code=200)
async def delete_personality(personality_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    db_personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    is_owner = (db_personality.owner_user_id == current_user.id)

    if not is_owner and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this personality.")

    users_with_this_active = db.query(DBUser).filter(DBUser.active_personality_id == personality_id).all()
    for user in users_with_this_active:
        user.active_personality_id = None
        if user.username in user_sessions:
            user_sessions[user.username]["active_personality_id"] = None
            user_sessions[user.username]["active_personality_prompt"] = None

    try:
        db.delete(db_personality)
        db.commit()
        return {"message": f"Personality '{db_personality.name}' deleted successfully."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@personalities_router.post("/{personality_id}/send", response_model=PersonalityPublic)
async def send_personality_to_user(personality_id: str, send_request: PersonalitySendRequest, current_db_user: DBUser = Depends(get_current_db_user_from_token), db: Session = Depends(get_db)) -> PersonalityPublic:
    q = db.query(DBPersonality).filter(
        DBPersonality.id == personality_id,
        or_(
            DBPersonality.owner_user_id == current_db_user.id,
            and_(DBPersonality.is_public == True, current_db_user.is_admin == True)
        )
    )
    original_personality = q.first()
    if not original_personality:
        raise HTTPException(status_code=404, detail="Personality not found or you don't have permission to send it.")

    target_user = db.query(DBUser).filter(DBUser.username == send_request.target_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Target user '{send_request.target_username}' not found.")
    
    if target_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="Cannot send a personality to yourself.")

    existing_target_pers = db.query(DBPersonality).filter(
        DBPersonality.owner_user_id == target_user.id,
        DBPersonality.name == original_personality.name
    ).first()
    if existing_target_pers:
        raise HTTPException(status_code=400, detail=f"User '{target_user.username}' already has a personality named '{original_personality.name}'.")

    copied_personality = DBPersonality(
        name=original_personality.name,
        category=original_personality.category,
        author=f"Sent by {current_db_user.username}",
        description=original_personality.description,
        prompt_text=original_personality.prompt_text,
        disclaimer=original_personality.disclaimer,
        script_code=original_personality.script_code,
        icon_base64=original_personality.icon_base64,
        owner_user_id=target_user.id,
        active_mcps=original_personality.active_mcps,
        required_context_options=original_personality.required_context_options,
        is_public=False
    )
    db.add(copied_personality)
    try:
        db.commit()
        db.refresh(copied_personality)
        return get_personality_public_from_db(copied_personality, target_user.username)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to send personality due to a name conflict for the target user.")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error sending personality: {str(e)}")

@personalities_router.get("/{personality_id}/export")
async def export_personality(personality_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    Exports a personality as a zip file containing description.yaml, optional icon.png, and optional data.txt.
    """
    db_personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    is_owner = (db_personality.owner_user_id == current_user.id)
    is_system = db_personality.owner_user_id is None
    is_public = db_personality.is_public

    if not is_public and not is_system and not is_owner:
        raise HTTPException(status_code=403, detail="You do not have permission to export this personality.")

    try:
        # Prepare description.yaml content
        desc_data = {
            'name': db_personality.name,
            'category': db_personality.category,
            'author': db_personality.author,
            'description': db_personality.description,
            'prompt_text': db_personality.prompt_text,
            'disclaimer': db_personality.disclaimer,
            'version': db_personality.version or '1.0.0',
            'active_mcps': db_personality.active_mcps or [],
            'required_context_options': db_personality.required_context_options or []
        }
        
        # Prepare zip buffer
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add description.yaml
            zf.writestr('description.yaml', yaml.dump(desc_data, default_flow_style=False))
            
            # Add icon.png if available
            if db_personality.icon_base64:
                try:
                    # Remove header if present
                    b64_data = db_personality.icon_base64
                    if "base64," in b64_data:
                        b64_data = b64_data.split("base64,")[1]
                    
                    img_bytes = base64.b64decode(b64_data)
                    zf.writestr('icon.png', img_bytes)
                except Exception as e:
                    print(f"Warning: Failed to export icon for personality {personality_id}: {e}")

            # Add data.txt if static text
            if db_personality.data_source_type == 'static_text' and db_personality.data_source:
                zf.writestr('data.txt', db_personality.data_source)

        zip_buffer.seek(0)
        
        filename = f"{db_personality.name.replace(' ', '_')}_export.zip"
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
        
        return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)

    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to export personality: {e}")

@personalities_router.post("/import", response_model=PersonalityPublic)
async def import_personality(
    file: UploadFile = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Imports a personality from a zip file.
    Expects description.yaml. Optional: icon.png/jpg, data.txt.
    """
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload a .zip file.")

    try:
        content = await file.read()
        
        with zipfile.ZipFile(io.BytesIO(content), 'r') as zf:
            # 1. Parse description.yaml
            if 'description.yaml' not in zf.namelist():
                # Try config.yaml for legacy support
                if 'config.yaml' in zf.namelist():
                    desc_content = zf.read('config.yaml')
                else:
                    raise HTTPException(status_code=400, detail="Missing description.yaml in zip.")
            else:
                desc_content = zf.read('description.yaml')
            
            try:
                desc_data = yaml.safe_load(desc_content)
            except yaml.YAMLError:
                raise HTTPException(status_code=400, detail="Invalid YAML format in description.yaml.")

            # Validate mandatory fields
            if not desc_data.get('name') or not desc_data.get('prompt_text', desc_data.get('personality_conditioning')):
                raise HTTPException(status_code=400, detail="Personality must have a name and prompt text (personality_conditioning).")

            # 2. Handle Icon
            icon_base64 = None
            icon_files = [f for f in zf.namelist() if f.lower() in ['icon.png', 'icon.jpg', 'icon.jpeg', 'logo.png']]
            if icon_files:
                try:
                    icon_bytes = zf.read(icon_files[0])
                    # Detect mime
                    mime = "image/png"
                    if icon_files[0].lower().endswith('.jpg') or icon_files[0].lower().endswith('.jpeg'):
                        mime = "image/jpeg"
                    
                    b64_str = base64.b64encode(icon_bytes).decode('utf-8')
                    icon_base64 = f"data:{mime};base64,{b64_str}"
                except Exception as e:
                    print(f"Warning: Failed to process icon from import: {e}")

            # 3. Handle Data Source
            data_source_type = 'none'
            data_source = None
            if 'data.txt' in zf.namelist():
                try:
                    data_source = zf.read('data.txt').decode('utf-8')
                    data_source_type = 'static_text'
                except Exception:
                    print("Warning: Failed to read data.txt.")

            # Construct Personality Object
            # Check for name collision
            base_name = desc_data.get('name')
            
            # Map legacy fields if needed
            prompt_text = desc_data.get('prompt_text') or desc_data.get('personality_conditioning')
            description = desc_data.get('description') or desc_data.get('personality_description')
            active_mcps = desc_data.get('active_mcps') or desc_data.get('dependencies', [])
            required_context = desc_data.get('required_context_options') or []

            # Handle Owner
            db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
            owner_id = db_user.id
            is_public = False
            
            # Name collision check
            if db.query(DBPersonality).filter(DBPersonality.owner_user_id == owner_id, DBPersonality.name == base_name).first():
                 base_name = f"{base_name} (Imported)"

            new_personality = DBPersonality(
                name=base_name,
                category=desc_data.get('category', 'Imported'),
                author=desc_data.get('author', current_user.username),
                description=description,
                prompt_text=prompt_text,
                disclaimer=desc_data.get('disclaimer'),
                version=str(desc_data.get('version', '1.0')),
                icon_base64=icon_base64,
                active_mcps=active_mcps,
                required_context_options=required_context,
                data_source_type=data_source_type,
                data_source=data_source,
                owner_user_id=owner_id,
                is_public=is_public
            )
            
            db.add(new_personality)
            db.commit()
            db.refresh(new_personality)
            
            return get_personality_public_from_db(new_personality, current_user.username)

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip file.")
    except Exception as e:
        trace_exception(e)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
