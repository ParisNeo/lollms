# backend/routers/personalities.py
import traceback
import json
from typing import List, Dict, Optional
import io
import base64
from PIL import Image

# Third-Party Imports
from fastapi import (
    APIRouter, Depends, HTTPException
)
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
    get_user_lollms_client
)
from backend.task_manager import task_manager, Task
from backend.settings import settings
from ascii_colors import trace_exception

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
                "active_mcps": {"type": "array", "items": {"type": "string"}, "description": "A list of default MCP tools to activate with this personality."}
            },
            "required": ["name", "prompt_text"],
            "description": "JSON object defining a LoLLMs personality."
        }

        system_prompt = f"""You are an expert personality designer for AI chatbots.
Your task is to create a new personality based on the user's prompt."""

        task.log("Sending prompt to LLM for JSON generation...")
        task.set_progress(30)
        
        generated_data_dict = lc.generate_structured_content(prompt,
                                                             system_prompt=system_prompt,
                                                             schema=personality_schema,
                                                             #n_predict=settings.get("default_llm_ctx_size")
                                                            )

        task.log("Creating new personality in the database...")
        task.set_progress(90)

        # FIX: Ensure newly generated personalities do not have pre-selected MCPs
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
        lc = get_user_lollms_client(username)
        if not lc.tti:
            raise Exception("Text-to-Image service is not configured for this user.")

        task.log("Generating image using TTI engine...")
        # Generate image as raw bytes (not base64)
        img_data = lc.tti.generate_image(prompt, width=512, height=512)
        
        # If API returns a list, pick the first
        if isinstance(img_data, (list, tuple)):
            if not img_data:
                raise Exception("Image generation returned empty list.")
            img_data = img_data[0]

        # If the provider sometimes returns a data URI or base64 str, normalize:
        if isinstance(img_data, str):
            # Remove any data URI prefix if present
            if img_data.startswith("data:"):
                img_data = img_data.split(",", 1)[1]
            # Base64 string -> raw bytes
            img_data = base64.b64decode(img_data)

        if not isinstance(img_data, (bytes, bytearray)):
            raise Exception(f"Unsupported image payload type from generator: {type(img_data)}")

        task.set_progress(80)
        task.log("Processing image...")

        with Image.open(io.BytesIO(img_data)) as img:
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            img.thumbnail((128, 128))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            icon_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        task.log("Icon generated successfully.")
        task.set_progress(100)
        return {"icon_base64": f"data:image/png;base64,{icon_b64}"}

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
