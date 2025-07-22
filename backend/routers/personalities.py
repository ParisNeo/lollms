# backend/routers/personalities.py

# Standard Library Imports
import traceback
import json
from typing import List, Dict, Optional

# Third-Party Imports
from fastapi import (
    APIRouter, Depends, HTTPException, BackgroundTasks
)
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, and_

# Local Application Imports
from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.personality import Personality as DBPersonality
from backend.models import (
    UserAuthDetails, PersonalityPublic, PersonalityCreate,
    PersonalityUpdate, PersonalitySendRequest,
    GeneratePersonalityFromPromptRequest
)
from backend.session import (
    get_current_active_user,
    get_current_db_user_from_token,
    user_sessions,
    get_user_lollms_client
)
from backend.task_manager import task_manager, Task
from backend.settings import settings

personalities_router = APIRouter(prefix="/api/personalities", tags=["Personalities"])

# --- Task for Personality Generation ---
def _generate_personality_task(task: Task, username: str, prompt: str):
    task.log("Starting personality generation...")
    task.set_progress(10)
    db_session = next(get_db())
    raw_response = "" # Initialize raw_response
    try:
        lc = get_user_lollms_client(username)
        current_user = db_session.query(DBUser).filter(DBUser.username == username).first()
        if not current_user:
            raise Exception("User not found for personality generation task.")

        # Define the schema for personality generation
        personality_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Short, catchy name for the personality."},
                "category": {"type": "string", "description": "Category for the personality (e.g., 'Creative', 'Coding', 'Educational')."},
                "author": {"type": "string", "description": "The author or creator of the personality."},
                "description": {"type": "string", "description": "A brief overview of the personality's purpose and style, for display in the UI."},
                "prompt_text": {"type": "string", "description": "The core system prompt that defines the AI's role, rules, and initial instructions for character."},
                "disclaimer": {"type": "string", "description": "Any necessary warnings or disclaimers users should be aware of."},
                "script_code": {"type": "string", "description": "Optional Python code for advanced behaviors. Can be empty."}
            },
            "required": ["name", "prompt_text"],
            "description": "JSON object defining a LoLLMs personality."
        }

        generation_prompt = f"""You are an expert personality designer for AI chatbots.
Your task is to create a new personality based on the user's prompt.
You MUST output ONLY a single valid JSON object strictly conforming to the following JSON schema.
Do NOT include any other text, comments, or explanations outside the JSON object.

JSON Schema:
{json.dumps(personality_schema, indent=2)}

User's prompt: "{prompt}"

Please generate the personality now."""

        task.log("Sending prompt to LLM for JSON generation...")
        task.set_progress(30)
        
        raw_response = lc.generate_text(generation_prompt, stream=False, n_predict=settings.get("default_llm_ctx_size"))
        
        task.log("LLM response received. Parsing JSON...")
        task.set_progress(70)

        json_start = raw_response.find('{')
        json_end = raw_response.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            raise ValueError("LLM did not return a valid JSON object.")
            
        json_string = raw_response[json_start:json_end]
        generated_data_dict = json.loads(json_string)

        task.log("Creating new personality in the database...")
        task.set_progress(90)

        # Check if a personality with the same name already exists for this user
        existing_personality = db_session.query(DBPersonality).filter(
            DBPersonality.owner_user_id == current_user.id,
            DBPersonality.name == generated_data_dict.get("name")
        ).first()
        if existing_personality:
            task.log(f"Personality '{generated_data_dict.get('name')}' already exists. Appending UUID to make it unique.", "WARNING")
            generated_data_dict["name"] = f"{generated_data_dict.get('name')} {task.id.split('-')[0]}"


        # Create the new personality record
        new_personality = DBPersonality(
            owner_user_id=current_user.id,
            is_public=False,
            **generated_data_dict
        )
        db_session.add(new_personality)
        db_session.commit()
        db_session.refresh(new_personality, ["owner"])

        # Use model_dump_json() to ensure the result is a JSON string.
        task.result = get_personality_public_from_db(new_personality, username).model_dump_json()

        task.log("Personality created and saved successfully.")
        task.set_progress(100)

    except ValueError as ve:
        db_session.rollback()
        task.log(f"JSON Parsing Error: {ve}. Response was:\n{raw_response}", level="ERROR")
        task.error = f"Failed to parse LLM response as JSON: {ve}. Check LLM output for formatting issues."
        raise ValueError(f"LLM output was not valid JSON: {ve}") from ve
    except json.JSONDecodeError as jde:
        db_session.rollback()
        task.log(f"JSON Decode Error: {jde}. Response was:\n{raw_response}", level="ERROR")
        task.error = f"LLM output could not be decoded as JSON: {jde}. Ensure the LLM outputs a valid JSON object."
        raise json.JSONDecodeError(f"LLM output could not be decoded as JSON: {jde}", json_string or raw_response, 0) from jde
    except Exception as e:
        db_session.rollback()
        task.log(f"An unexpected error occurred during personality generation: {e}", level="CRITICAL")
        task.error = str(e)
        raise e
    finally:
        db_session.close()

# --- Task for Prompt Enhancement ---
def _enhance_prompt_task(task: Task, username: str, prompt_text: str, custom_instruction: Optional[str]):
    task.log("Starting prompt enhancement...")
    task.set_progress(10)
    try:
        lc = get_user_lollms_client(username)

        enhance_instruction = custom_instruction.strip() if custom_instruction else ""

        if enhance_instruction:
            generation_prompt = f"""{enhance_instruction}

Here is the text to enhance:
---
{prompt_text}
---
"""
        else:
            generation_prompt = f"""You are an expert copywriter. Your task is to enhance the following text. Make it more engaging, descriptive, and clear. You must return ONLY the enhanced text, nothing else.

Text to enhance:
---
{prompt_text}
---
"""
        
        task.log("Sending text to LLM for enhancement...")
        task.set_progress(50)
        
        enhanced_text = lc.generate_text(generation_prompt, stream=False, n_predict=settings.get("default_llm_ctx_size"))
        
        # Ensure the result is a JSON string.
        task.result = json.dumps({"enhanced_prompt_text": enhanced_text})
        task.log("Prompt enhanced successfully.")
        task.set_progress(100)

    except Exception as e:
        task.log(f"Failed to enhance prompt: {e}", level="CRITICAL")
        task.error = str(e)
        raise e

# --- Personality Generation from Prompt Endpoint ---
@personalities_router.post("/generate_from_prompt", response_model=Dict[str, str], status_code=202)
async def generate_personality_from_prompt(
    payload: GeneratePersonalityFromPromptRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Triggers a background task to generate a personality from a natural language prompt using an LLM.
    """
    task = task_manager.submit_task(
        name="Generate Personality from Prompt",
        target=_generate_personality_task,
        args=(current_user.username, payload.prompt),
        description=f"Generating personality from prompt: '{payload.prompt[:50]}...'",
        owner_username=current_user.username  # CORRECTED
    )
    background_tasks.add_task(task.run)
    return {"task_id": task.id, "message": "Personality generation started in the background. Check tasks for progress."}

# --- Prompt Enhancement Endpoint ---
@personalities_router.post("/enhance_prompt", response_model=Dict[str, str], status_code=202)
async def enhance_personality_prompt(
    payload: Dict[str, str], # Use dict for flexible input, Pydantic model can be added later
    current_user: UserAuthDetails = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Triggers a background task to enhance a personality's system prompt using an LLM.
    """
    prompt_text = payload.get("prompt_text")
    custom_instruction = payload.get("custom_instruction")

    if not prompt_text:
        raise HTTPException(status_code=400, detail="Prompt text is required for enhancement.")

    task = task_manager.submit_task(
        name="Enhance Personality Prompt",
        target=_enhance_prompt_task,
        args=(current_user.username, prompt_text, custom_instruction),
        description="Enhancing personality system prompt.",
        owner_username=current_user.username  # CORRECTED
    )
    background_tasks.add_task(task.run)
    return {"task_id": task.id, "message": "Prompt enhancement started in the background. Check tasks for progress."}


def get_personality_public_from_db(db_personality: DBPersonality, owner_username: Optional[str] = None) -> PersonalityPublic:
    if owner_username is None and db_personality.owner:
        owner_username = db_personality.owner.username
    
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
        owner_username=owner_username
    )

@personalities_router.post("", response_model=PersonalityPublic, status_code=201)
async def create_personality(personality_data: PersonalityCreate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> PersonalityPublic:
    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
    
    existing_personality = db.query(DBPersonality).filter(
        DBPersonality.owner_user_id == db_user.id,
        DBPersonality.name == personality_data.name
    ).first()
    if existing_personality:
        raise HTTPException(status_code=400, detail=f"You already have a personality named '{personality_data.name}'.")

    if personality_data.is_public and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only administrators can create public personalities.")
    
    db_personality = DBPersonality(
        **personality_data.model_dump(exclude={"is_public"}),
        owner_user_id=db_user.id,
        is_public=personality_data.is_public if current_user.is_admin else False
    )

    try:
        db.add(db_personality)
        db.commit()
        db.refresh(db_personality)
        return get_personality_public_from_db(db_personality, current_user.username)
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
    public_personalities_db = db.query(DBPersonality).options(joinedload(DBPersonality.owner)).filter(DBPersonality.is_public == True).order_by(DBPersonality.category, DBPersonality.name).all()
    return [get_personality_public_from_db(p) for p in public_personalities_db]

@personalities_router.get("/{personality_id}", response_model=PersonalityPublic)
async def get_personality(personality_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> PersonalityPublic:
    db_personality = db.query(DBPersonality).options(joinedload(DBPersonality.owner)).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
    is_owner = (db_personality.owner_user_id == db_user.id)

    if not db_personality.is_public and not is_owner:
        raise HTTPException(status_code=403, detail="You do not have permission to view this personality.")
    
    return get_personality_public_from_db(db_personality)

@personalities_router.put("/{personality_id}", response_model=PersonalityPublic)
async def update_personality(personality_id: str, personality_data: PersonalityUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> PersonalityPublic:
    db_personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
    is_owner = (db_personality.owner_user_id == db_user.id)

    if not is_owner and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="You do not have permission to update this personality.")
    
    if personality_data.is_public is not None:
        if not current_user.is_admin:
            if is_owner and personality_data.is_public != db_personality.is_public:
                 raise HTTPException(status_code=403, detail="Only administrators can change the public status of a personality.")
        elif current_user.is_admin:
            db_personality.is_public = personality_data.is_public
    
    update_data = personality_data.model_dump(exclude_unset=True, exclude={"is_public"})

    if "name" in update_data and update_data["name"] != db_personality.name:
        owner_id_for_check = db_personality.owner_user_id
        q = db.query(DBPersonality).filter(
            DBPersonality.owner_user_id == owner_id_for_check,
            DBPersonality.name == update_data["name"],
            DBPersonality.id != personality_id
        )
        if q.first():
            raise HTTPException(status_code=400, detail=f"A personality named '{update_data['name']}' already exists.")

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

    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
    is_owner = (db_personality.owner_user_id == db_user.id)

    if not is_owner and not (current_user.is_admin and (db_personality.is_public or db_personality.owner_user_id is None)):
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