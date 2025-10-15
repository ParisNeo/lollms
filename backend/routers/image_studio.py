# [UPDATE] lollms/backend/routers/image_studio.py
import base64
import uuid
import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename
from ascii_colors import trace_exception

from backend.db import get_db
from backend.db.models.image import UserImage
from backend.models import UserAuthDetails, TaskInfo
from backend.models.image import (
    UserImagePublic, ImageGenerationRequest, MoveImageToDiscussionRequest, 
    ImageEditRequest, ImagePromptEnhancementRequest, ImagePromptEnhancementResponse
)
from backend.session import (
    get_current_active_user, get_user_data_root, 
    build_lollms_client_from_params, get_user_lollms_client,
    get_user_images_path
)
from backend.config import IMAGES_DIR_NAME
from backend.discussion import get_user_discussion
from backend.task_manager import task_manager
from backend.tasks.discussion_tasks import _to_task_info, _image_studio_generate_task, _image_studio_edit_task

image_studio_router = APIRouter(
    prefix="/api/image-studio",
    tags=["Image Studio"],
    dependencies=[Depends(get_current_active_user)]
)

@image_studio_router.get("", response_model=List[UserImagePublic])
async def get_user_images(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return db.query(UserImage).filter(UserImage.owner_user_id == current_user.id).order_by(UserImage.created_at.desc()).all()

@image_studio_router.get("/{image_id}/file")
async def get_image_file(
    image_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    image_record = db.query(UserImage).filter(UserImage.id == image_id, UserImage.owner_user_id == current_user.id).first()
    if not image_record:
        raise HTTPException(status_code=404, detail="Image not found.")
    
    file_path = get_user_images_path(current_user.username) / image_record.filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image file not found on disk.")
        
    return FileResponse(str(file_path))

@image_studio_router.post("/generate", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def generate_image(
    request: ImageGenerationRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    model_full_name = request.model or current_user.tti_binding_model_name
    if not model_full_name or '/' not in model_full_name:
        raise HTTPException(status_code=400, detail="A valid TTI model must be selected in your settings or provided in the request.")

    db_task = task_manager.submit_task(
        name=f"Generating {request.n} image(s): {request.prompt[:30]}...",
        target=_image_studio_generate_task,
        args=(current_user.username, request.model_dump()),
        description=f"Generating {request.n} image(s) with prompt: '{request.prompt[:50]}...'",
        owner_username=current_user.username
    )
    return _to_task_info(db_task)


@image_studio_router.post("/edit", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def edit_image(
    request: ImageEditRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    model_full_name = request.model or current_user.tti_binding_model_name
    if not model_full_name or '/' not in model_full_name:
        raise HTTPException(status_code=400, detail="A valid TTI model must be selected.")

    db_task = task_manager.submit_task(
        name=f"Editing image: {request.prompt[:30]}...",
        target=_image_studio_edit_task,
        args=(current_user.username, request.model_dump()),
        description=f"Editing image(s) with prompt: '{request.prompt[:50]}...'",
        owner_username=current_user.username
    )
    return _to_task_info(db_task)

@image_studio_router.post("/upload", response_model=List[UserImagePublic])
async def upload_images(
    files: List[UploadFile] = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    user_images_path = get_user_images_path(current_user.username)
    new_images_db = []
    for file in files:
        s_filename = secure_filename(file.filename)
        filename = f"{uuid.uuid4().hex}_{s_filename}"
        file_path = user_images_path / filename

        content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)

        new_image = UserImage(
            id=str(uuid.uuid4()),
            owner_user_id=current_user.id,
            filename=filename,
            prompt="Uploaded image"
        )
        db.add(new_image)
        new_images_db.append(new_image)

    db.commit()
    for img in new_images_db:
        db.refresh(img)
    return new_images_db

@image_studio_router.delete("/{image_id}", status_code=204)
async def delete_image(
    image_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    image_record = db.query(UserImage).filter(UserImage.id == image_id, UserImage.owner_user_id == current_user.id).first()
    if not image_record:
        raise HTTPException(status_code=404, detail="Image not found.")
    
    file_path = get_user_images_path(current_user.username) / image_record.filename
    file_path.unlink(missing_ok=True)
    
    db.delete(image_record)
    db.commit()

@image_studio_router.post("/{image_id}/move-to-discussion")
async def move_image_to_discussion(
    image_id: str,
    request: MoveImageToDiscussionRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    image_record = db.query(UserImage).filter(UserImage.id == image_id, UserImage.owner_user_id == current_user.id).first()
    if not image_record:
        raise HTTPException(status_code=404, detail="Image not found.")
        
    discussion = get_user_discussion(current_user.username, request.discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found.")
        
    file_path = get_user_images_path(current_user.username) / image_record.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk.")
        
    with open(file_path, "rb") as f:
        image_bytes = f.read()
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    
    discussion.add_discussion_image(image_b64, source=f"ImageStudio: {image_record.filename}")
    discussion.commit()
    
    image_record.discussion_id = request.discussion_id
    db.commit()
    
    return {"message": "Image successfully added to the discussion's data zone."}

@image_studio_router.post("/enhance-prompt", response_model=ImagePromptEnhancementResponse)
async def enhance_image_prompt(
    request: ImagePromptEnhancementRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    try:
        model_full_name = request.model or current_user.lollms_model_name
        if not model_full_name or '/' not in model_full_name:
            lc = get_user_lollms_client(current_user.username)
        else:
            binding_alias, model_name = model_full_name.split('/', 1)
            lc = build_lollms_client_from_params(
                username=current_user.username,
                binding_alias=binding_alias,
                model_name=model_name
            )

        system_prompt = "You are an expert image generation prompt engineer.\n"
        user_prompt_parts = []

        if request.target in ['prompt', 'both']:
            system_prompt += "- Enhance the positive prompt by adding descriptive details, cinematic keywords, and stylistic elements.\n"
            user_prompt_parts.append(f'Positive: "{request.prompt}"')

        if request.target in ['negative_prompt', 'both']:
            system_prompt += "- Enhance the negative prompt by adding common keywords to prevent artifacts and low quality.\n"
            user_prompt_parts.append(f'Negative: "{request.negative_prompt}"')
        
        system_prompt += '- Respond ONLY with a single valid JSON object containing the key(s) for the prompt(s) you enhanced ("prompt", "negative_prompt"). Do not add any extra text or explanations.'
        user_prompt = "Enhance the following prompts:\n" + "\n".join(user_prompt_parts)

        raw_response = lc.generate_text(user_prompt, system_prompt=system_prompt, stream=False)
        
        json_match = raw_response[raw_response.find('{'):raw_response.rfind('}') + 1]
        if not json_match:
            raise HTTPException(status_code=500, detail="AI did not return a valid JSON object.")
            
        enhanced_data = json.loads(json_match)
        
        response_data = {}
        if 'prompt' in enhanced_data:
            response_data['prompt'] = enhanced_data.get('prompt')
        if 'negative_prompt' in enhanced_data:
            response_data['negative_prompt'] = enhanced_data.get('negative_prompt')

        return ImagePromptEnhancementResponse(**response_data)
        
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"AI enhancement failed: {e}")