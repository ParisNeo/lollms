import base64
import datetime
import io
import os
import shutil
import tempfile
import zipfile
import re
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response, status
from pydantic import BaseModel, Field
from PIL import Image

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, desc
from sqlalchemy.exc import IntegrityError

from backend.db import get_db
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.user import User as DBUser
from backend.models import (
    UserAuthDetails, PersonalityCreate, PersonalityUpdate, 
    PersonalityPublic, PersonalitySendRequest, PersonalityPromptGenerateRequest
)
from backend.session import (
    get_current_active_user,
    get_current_db_user_from_token,
    build_lollms_client_from_params,
    get_user_lollms_client,
    user_sessions
)
from backend.ws_manager import manager
from backend.task_manager import task_manager, Task
from backend.tasks.utils import _to_task_info
from ascii_colors import trace_exception

personalities_router = APIRouter(prefix="/api/personalities", tags=["Personalities"])

class EnhancePromptRequest(BaseModel):
    prompt_text: str
    modification_prompt: str

class GenerateIconRequest(BaseModel):
    prompt: str

def _generate_personality_task(task: Task, username: str, prompt_text: str):
    task.log("Starting personality generation...")
    task.set_progress(10)
    try:
        lc = build_lollms_client_from_params(username=username)
        task.log("LLM Client initialized.")
        task.set_progress(30)
        
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "A creative, concise name for the personality."},
                "description": {"type": "string", "description": "A short summary of who the personality is and what they do."},
                "category": {"type": "string", "description": "A general category, e.g., 'Coding', 'Writing', 'Fun', 'Expert', 'Philosophy'."},
                "prompt_text": {"type": "string", "description": "A comprehensive system prompt that defines the persona's tone, knowledge, behavioral guidelines, constraints, and operational mode."},
                "icon_prompt": {"type": "string", "description": "A descriptive prompt for an image generator to create an avatar/icon for this personality. E.g., 'A wise old robotic wizard with glowing blue runes, digital art'."}
            },
            "required": ["name", "description", "category", "prompt_text", "icon_prompt"]
        }
        
        system_prompt = "You are a master AI Persona Architect. Your job is to create rich, vivid, deep, and highly effective AI personalities based on user concepts."
        user_prompt = f"Design a complete AI personality based on this concept:\n\"{prompt_text}\""
        
        task.log("Generating structured personality blueprint...")
        personality_data = lc.generate_structured_content(user_prompt, schema=schema, system_prompt=system_prompt)
        
        if not personality_data or not isinstance(personality_data, dict):
            raise Exception("AI failed to return valid personality structure.")
            
        task.set_progress(70)
        task.log(f"Generated blueprint for '{personality_data.get('name')}'. Generating icon...")
        
        icon_base64 = None
        icon_prompt = personality_data.get("icon_prompt")
        
        if icon_prompt:
            try:
                tti_client = build_lollms_client_from_params(username=username, load_llm=False, load_tti=True)
                if tti_client.tti:
                    img_bytes = tti_client.tti.generate_image(icon_prompt, width=512, height=512)
                    if img_bytes:
                        if isinstance(img_bytes, list):
                            img_bytes = img_bytes[0]
                        if isinstance(img_bytes, str) and img_bytes.startswith('data:'):
                            img_bytes = base64.b64decode(img_bytes.split(',', 1)[1])
                        elif isinstance(img_bytes, str):
                            img_bytes = base64.b64decode(img_bytes)

                        with Image.open(io.BytesIO(img_bytes)) as img:
                            if img.mode not in ("RGB", "RGBA"):
                                img = img.convert("RGBA")
                            img.thumbnail((128, 128))
                            buf = io.BytesIO()
                            img.save(buf, format="PNG")
                            icon_base64 = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
                            task.log("Icon generated successfully.")
            except Exception as tti_err:
                task.log(f"Icon generation skipped or failed: {tti_err}", "WARNING")
                
        task.set_progress(90)
        
        db = next(get_db())
        try:
            user = db.query(DBUser).filter(DBUser.username == username).first()
            if not user:
                raise Exception("User not found.")
            
            new_pers = DBPersonality(
                name=personality_data.get("name", "New Persona"),
                author=username,
                category=personality_data.get("category", "Custom"),
                description=personality_data.get("description", ""),
                prompt_text=personality_data.get("prompt_text", ""),
                icon_base64=icon_base64,
                owner_user_id=user.id,
                is_public=False
            )
            db.add(new_pers)
            db.commit()
            db.refresh(new_pers)
            
            task.set_progress(100)
            task.log("Personality saved to your library!")
            
            return {
                "id": new_pers.id,
                "name": new_pers.name,
                "category": new_pers.category,
                "description": new_pers.description,
                "prompt_text": new_pers.prompt_text,
                "icon_base64": new_pers.icon_base64
            }
        finally:
            db.close()
            
    except Exception as e:
        task.log(f"Generation failed: {e}", "ERROR")
        trace_exception(e)
        raise e

def _enhance_prompt_task(task: Task, username: str, prompt_text: str, custom_instruction: Optional[str]):
    task.log("Starting prompt enhancement...")
    task.set_progress(10)
    try:
        lc = get_user_lollms_client(username)
        enhance_instruction = custom_instruction.strip() if custom_instruction else "Enhance the system prompt:"
        enhance_instruction += f"\nOriginal system prompt:\n{prompt_text}\n"
        
        output_schema = {
            "type": "object",
            "properties": {
                "enhanced_system_prompt": {"type": "string", "description": "The enhanced core system prompt."}
            },
            "required": ["enhanced_system_prompt"],
            "description": "JSON object defining the enhanced system prompt."
        }

        system_prompt = "You are an expert personality designer for AI assistants. Improve the prompt based on user instructions."
        task.set_progress(30)
        
        generated_data_dict = lc.generate_structured_content(
            enhance_instruction,
            system_prompt=system_prompt,
            schema=output_schema
        )
        
        task.log("Prompt enhanced successfully.")
        task.set_progress(100)
        return generated_data_dict
    except Exception as e:
        task.log(f"Prompt enhancement failed: {e}", "ERROR")
        trace_exception(e)
        raise e

def _generate_icon_task(task: Task, username: str, prompt: str):
    task.log("Starting icon generation...")
    task.set_progress(10)
    try:
        lc = build_lollms_client_from_params(username=username, load_llm=True, load_tti=True)
        if not lc.tti:
            raise Exception("Text-to-Image service is not configured for this user.")

        task.log("Refining prompt with LLM...")
        refinement_sys = "You are an expert prompt engineer. Convert the user's description into a detailed stable diffusion icon prompt. Output ONLY the prompt."
        refined_prompt = lc.generate_text(prompt, system_prompt=refinement_sys, max_new_tokens=200).strip()
        
        task.log("Rendering icon with TTI...")
        img_data = lc.tti.generate_image(refined_prompt, width=512, height=512)
        if not img_data:
            raise Exception("Image generation returned empty data.")
            
        if isinstance(img_data, list):
            img_data = img_data[0]
            
        if isinstance(img_data, str):
            if img_data.startswith("data:"):
                img_data = img_data.split(",", 1)[1]
            img_data = base64.b64decode(img_data)

        with Image.open(io.BytesIO(img_data)) as img:
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            img.thumbnail((128, 128))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            icon_b64 = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"

        task.log("Icon generated successfully.")
        task.set_progress(100)
        return {"icon_base64": icon_b64}
    except Exception as e:
        task.log(f"Icon generation failed: {e}", "ERROR")
        trace_exception(e)
        raise e

@personalities_router.post("/generate_from_prompt", status_code=status.HTTP_202_ACCEPTED)
async def generate_personality(
    payload: PersonalityPromptGenerateRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    task = task_manager.submit_task(
        name=f"Generate Persona: {payload.prompt[:30]}...",
        target=_generate_personality_task,
        args=(current_user.username, payload.prompt),
        description=f"Creating rich personality from prompt: '{payload.prompt[:40]}...'",
        owner_username=current_user.username
    )
    return task

@personalities_router.post("/enhance_prompt", status_code=status.HTTP_200_OK)
async def enhance_prompt(
    payload: EnhancePromptRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    try:
        lc = build_lollms_client_from_params(username=current_user.username)
        prompt = f"""You are an expert Prompt Engineer for AI personas.
Improve and expand the following system prompt based on the user's enhancement instructions.

[CURRENT SYSTEM PROMPT]:
{payload.prompt_text}

[INSTRUCTIONS FOR ENHANCEMENT]:
{payload.modification_prompt}

[OUTPUT INSTRUCTION]:
Return ONLY the newly revised, high-fidelity system prompt text. Do not wrap in markdown or add conversational intro."""
        
        enhanced_text = lc.generate_text(prompt, max_new_tokens=2048)
        return {"enhanced_prompt": enhanced_text.strip()}
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=str(e))

@personalities_router.post("/generate_icon", status_code=status.HTTP_200_OK)
async def generate_icon(
    payload: GenerateIconRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    try:
        lc = build_lollms_client_from_params(username=current_user.username, load_llm=False, load_tti=True)
        if not lc.tti:
            raise HTTPException(status_code=400, detail="TTI binding is not configured.")
            
        img_bytes = lc.tti.generate_image(payload.prompt, width=512, height=512)
        if not img_bytes:
            raise HTTPException(status_code=500, detail="Image generation returned empty data.")
            
        if isinstance(img_bytes, list):
            img_bytes = img_bytes[0]
            
        if isinstance(img_bytes, str):
            if img_bytes.startswith("data:"):
                img_bytes = img_bytes.split(",", 1)[1]
            img_bytes = base64.b64decode(img_bytes)

        with Image.open(io.BytesIO(img_bytes)) as img:
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            img.thumbnail((128, 128))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            icon_base64 = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
            return {"icon_base64": icon_base64}
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=str(e))

@personalities_router.get("/my", response_model=List[PersonalityPublic])
def get_my_personalities(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return db.query(DBPersonality).filter(DBPersonality.owner_user_id == current_user.id).order_by(DBPersonality.name).all()

@personalities_router.get("/public", response_model=List[PersonalityPublic])
def get_public_personalities(
    db: Session = Depends(get_db)
):
    return db.query(DBPersonality).filter(DBPersonality.is_public == True).order_by(DBPersonality.category, DBPersonality.name).all()

@personalities_router.get("/{personality_id}", response_model=PersonalityPublic)
def get_personality(
    personality_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not personality:
        raise HTTPException(status_code=404, detail="Personality not found")
        
    if not personality.is_public and personality.owner_user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to view this personality")
        
    return personality

@personalities_router.post("", response_model=PersonalityPublic, status_code=status.HTTP_201_CREATED)
def create_personality(
    personality_data: PersonalityCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    new_personality = DBPersonality(
        **personality_data.model_dump(),
        owner_user_id=current_user.id
    )
    db.add(new_personality)
    try:
        db.commit()
        db.refresh(new_personality)
        return new_personality
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error creating personality.")

@personalities_router.put("/{personality_id}", response_model=PersonalityPublic)
def update_personality(
    personality_id: str,
    personality_data: PersonalityUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not personality:
        raise HTTPException(status_code=404, detail="Personality not found")
    
    if personality.owner_user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to edit this personality")

    update_dict = personality_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(personality, key, value)

    try:
        db.commit()
        db.refresh(personality)
        return personality
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error updating personality.")

@personalities_router.delete("/{personality_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_personality(
    personality_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not personality:
        raise HTTPException(status_code=404, detail="Personality not found")

    if personality.owner_user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this personality")

    db.delete(personality)
    db.commit()

@personalities_router.post("/{personality_id}/send", status_code=status.HTTP_200_OK)
async def send_personality(
    personality_id: str,
    payload: PersonalitySendRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not personality:
        raise HTTPException(status_code=404, detail="Personality not found")

    target_user = db.query(DBUser).filter(DBUser.username == payload.target_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Target user '{payload.target_username}' not found")

    new_pers = DBPersonality(
        name=personality.name,
        author=f"Shared by {current_user.username}",
        category=personality.category,
        description=personality.description,
        prompt_text=personality.prompt_text,
        icon_base64=personality.icon_base64,
        owner_user_id=target_user.id,
        is_public=False
    )
    db.add(new_pers)
    try:
        db.commit()
        db.refresh(new_pers)
        
        manager.send_personal_message_sync({
            "type": "personality_shared",
            "data": {
                "message": f"🎁 {current_user.username} shared AI persona: {personality.name}",
                "sender_username": current_user.username,
                "sender_icon": current_user.icon,
                "personality_id": new_pers.id,
                "name": new_pers.name,
                "type": "success",
                "duration": 6000
            }
        }, target_user.id)
        
        return {"message": f"Personality successfully sent to {payload.target_username}."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@personalities_router.get("/{personality_id}/export")
def export_personality(
    personality_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not personality:
        raise HTTPException(status_code=404, detail="Personality not found")
        
    export_dict = {
        "name": personality.name,
        "author": personality.author or current_user.username,
        "category": personality.category or "Custom",
        "description": personality.description or "",
        "prompt_text": personality.prompt_text or "",
        "icon_base64": personality.icon_base64,
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("personality.json", json.dumps(export_dict, indent=2))
        
    zip_buffer.seek(0)
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', personality.name)
    filename = f"personality_{safe_name}.zip"
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@personalities_router.post("/import", response_model=PersonalityPublic)
async def import_personality(
    file: UploadFile = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    content_bytes = await file.read()
    try:
        with zipfile.ZipFile(io.BytesIO(content_bytes)) as zip_file:
            json_file = next((f for f in zip_file.namelist() if f.endswith(".json")), None)
            if not json_file:
                raise ValueError("No personality.json found in ZIP archive.")
            data = json.loads(zip_file.read(json_file).decode("utf-8"))
    except zipfile.BadZipFile:
        try:
            data = json.loads(content_bytes.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid personality ZIP or JSON file.")

    new_pers = DBPersonality(
        name=data.get("name", "Imported Persona"),
        author=data.get("author", current_user.username),
        category=data.get("category", "Imported"),
        description=data.get("description", ""),
        prompt_text=data.get("prompt_text", ""),
        icon_base64=data.get("icon_base64"),
        owner_user_id=current_user.id,
        is_public=False
    )
    db.add(new_pers)
    db.commit()
    db.refresh(new_pers)
    return new_pers