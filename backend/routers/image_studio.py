# [UPDATE] backend/routers/image_studio.py
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from backend.db import get_db
from backend.db.models.config import TTIBinding as DBTTIBinding
from backend.models import UserAuthDetails, TaskInfo
from backend.models.image_studio import ImageStudioGenerateRequest, ImageFilePublic # UPDATED IMPORT
from backend.session import get_current_active_user, build_lollms_client_from_params, get_user_data_root
from backend.task_manager import task_manager, Task
from backend.tasks.discussion_tasks import _to_task_info
from backend.db.models.user import User as DBUser
from ascii_colors import trace_exception
import datetime
import os

image_studio_router = APIRouter(
    prefix="/api/image-studio",
    tags=["Image Studio"],
    dependencies=[Depends(get_current_active_user)]
)

def _image_studio_generation_task(task: Task, username: str, payload: Dict):
    """
    Background task to generate an image outside of a specific discussion context.
    The task will save the generated image to the user's generated_images folder.
    """
    task.log("Starting Image Studio generation task...")
    task.set_progress(5)

    with task.db_session_factory() as db:
        user = db.query(DBUser).filter(DBUser.username == username).first()
        if not user:
            raise Exception(f"User '{username}' not found.")
        
        # 1. Determine binding and model from payload
        tti_model_full = payload.get("model_name")
        if not tti_model_full or '/' not in tti_model_full:
            raise Exception("Invalid TTI model format. Must be 'binding_alias/model_name'.")

        binding_alias, model_name = tti_model_full.split('/', 1)

        # 2. Build LollmsClient with TTI binding
        lc = build_lollms_client_from_params(
            username=username,
            tti_binding_alias=binding_alias,
            tti_model_name=model_name
        )
        
        if not hasattr(lc, 'tti') or not lc.tti:
            raise Exception(f"TTI functionality is not available for binding '{binding_alias}'.")
        
        task.log(f"Using TTI model: {tti_model_full}")
        task.set_progress(20)

        # 3. Prepare generation parameters
        prompt = payload.get("prompt")
        
        # Apply payload parameters, falling back to TTI config if necessary
        gen_params = {
            "size": payload.get("size", "1024x1024"),
            "quality": payload.get("quality", "standard"),
            "style": payload.get("style", "vivid"),
            "steps": payload.get("steps"),
            "sampler_name": payload.get("sampler_name"),
            "cfg_scale": payload.get("cfg_scale"),
            "seed": payload.get("seed"),
        }
        
        # Filter out None values
        gen_params = {k: v for k, v in gen_params.items() if v is not None}
        
        # 4. Generate the image
        task.log(f"Generating image with prompt: '{prompt[:50]}...'")
        image_bytes = lc.tti.generate_image(prompt=prompt, **gen_params)
        task.log("Image data received from binding.")
        task.set_progress(80)

        if not image_bytes:
            raise Exception("TTI binding returned empty image data.")

        # 5. Save the image to the user's generated_images folder
        user_generated_path = get_user_data_root(username) / "generated_images"
        user_generated_path.mkdir(parents=True, exist_ok=True)
        
        filename = f"studio_img_{task.id}.png"
        file_path = user_generated_path / filename
        
        with open(file_path, "wb") as f:
            f.write(image_bytes)
        
        task.log(f"Image saved to: {file_path}")
        task.set_progress(100)
        
        # 6. Return path relative to the user's generated_images folder
        return {
            "message": "Image generated successfully.",
            "file_name": filename,
            "image_url": f"/api/files/generated/{filename}"
        }



@image_studio_router.post("/generate", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
def generate_image_in_studio(
    payload: ImageStudioGenerateRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    if not payload.model_name or '/' not in payload.model_name:
        raise HTTPException(status_code=400, detail="Invalid model name. Must be in 'binding_alias/model_name' format.")
    
    if not payload.prompt or not payload.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required for image generation.")

    db_task = task_manager.submit_task(
        name=f"Image Studio Gen: {payload.model_name}",
        target=_image_studio_generation_task,
        args=(current_user.username, payload.model_dump()),
        description=f"Generating: '{payload.prompt[:50]}...'",
        owner_username=current_user.username
    )
    return _to_task_info(db_task)


@image_studio_router.get("/generated-images", response_model=List[ImageFilePublic])
def list_user_generated_images(
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    user_generated_path = get_user_data_root(current_user.username) / "generated_images"
    user_generated_path.mkdir(parents=True, exist_ok=True)
    
    images = []
    # Sort files by modified time, newest first
    for file_path in sorted(user_generated_path.iterdir(), key=os.path.getmtime, reverse=True):
        if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
            images.append({
                "file_name": file_path.name,
                "image_url": f"/api/files/generated/{file_path.name}",
                "timestamp": datetime.datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            })
    
    return [ImageFilePublic.model_validate(img) for img in images]


@image_studio_router.delete("/generated-images/{file_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_generated_image(
    file_name: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    user_generated_path = get_user_data_root(current_user.username) / "generated_images"
    file_path = user_generated_path / file_name
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image file not found.")

    try:
        file_path.unlink()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")