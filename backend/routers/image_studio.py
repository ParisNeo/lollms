# backend/routers/image_studio.py
import base64
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename

from backend.db import get_db
from backend.db.models.image import UserImage
from backend.models import UserAuthDetails
from backend.models.image import UserImagePublic, ImageGenerationRequest, MoveImageToDiscussionRequest, ImageEditRequest
from backend.session import get_current_active_user, get_user_data_root, build_lollms_client_from_params
from backend.config import IMAGES_DIR_NAME
from backend.discussion import get_user_discussion

image_studio_router = APIRouter(
    prefix="/api/image-studio",
    tags=["Image Studio"],
    dependencies=[Depends(get_current_active_user)]
)

def get_user_images_path(username: str) -> Path:
    path = get_user_data_root(username) / IMAGES_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

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


@image_studio_router.post("/generate", response_model=List[UserImagePublic])
async def generate_image(
    request: ImageGenerationRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    model_full_name = request.model or current_user.tti_binding_model_name
    if not model_full_name or '/' not in model_full_name:
        raise HTTPException(status_code=400, detail="A valid TTI model must be selected in your settings or provided in the request.")

    tti_binding_alias, tti_model_name = model_full_name.split('/', 1)
    
    lc = build_lollms_client_from_params(
        username=current_user.username,
        tti_binding_alias=tti_binding_alias,
        tti_model_name=tti_model_name
    )
    if not lc.tti:
        raise HTTPException(status_code=500, detail=f"TTI binding '{tti_binding_alias}' is not available.")

    user_images_path = get_user_images_path(current_user.username)
    generated_images = []

    for _ in range(request.n):
        image_bytes = lc.tti.generate_image(prompt=request.prompt, size=request.size)
        
        filename = f"{uuid.uuid4().hex}.png"
        file_path = user_images_path / filename
        with open(file_path, "wb") as f:
            f.write(image_bytes)
        
        new_image = UserImage(
            owner_user_id=current_user.id,
            filename=filename,
            prompt=request.prompt,
            model=model_full_name
        )
        db.add(new_image)
        generated_images.append(new_image)

    db.commit()
    for img in generated_images:
        db.refresh(img)
        
    return generated_images

@image_studio_router.post("/edit", response_model=UserImagePublic)
async def edit_image(
    request: ImageEditRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    model_full_name = request.model or current_user.tti_binding_model_name
    if not model_full_name or '/' not in model_full_name:
        raise HTTPException(status_code=400, detail="A valid TTI model must be selected.")

    tti_binding_alias, tti_model_name = model_full_name.split('/', 1)
    
    lc = build_lollms_client_from_params(
        username=current_user.username,
        tti_binding_alias=tti_binding_alias,
        tti_model_name=tti_model_name
    )
    if not lc.tti:
        raise HTTPException(status_code=500, detail=f"TTI binding '{tti_binding_alias}' is not available.")

    user_images_path = get_user_images_path(current_user.username)
    
    source_images_b64 = []
    for image_id in request.image_ids:
        image_record = db.query(UserImage).filter(UserImage.id == image_id, UserImage.owner_user_id == current_user.id).first()
        if not image_record:
            raise HTTPException(status_code=404, detail=f"Image with ID {image_id} not found.")
        file_path = user_images_path / image_record.filename
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail=f"Image file for {image_id} not found on disk.")
        
        with open(file_path, "rb") as f:
            source_images_b64.append(base64.b64encode(f.read()).decode('utf-8'))

    # Call the edit_image function, now with the optional mask
    edited_image_bytes = lc.tti.edit_image(
        images=source_images_b64, 
        prompt=request.prompt,
        mask=request.mask
    )

    if not edited_image_bytes:
        raise HTTPException(status_code=500, detail="Image generation failed.")

    # Save the new image
    new_filename = f"{uuid.uuid4().hex}.png"
    new_file_path = user_images_path / new_filename
    with open(new_file_path, "wb") as f:
        f.write(edited_image_bytes)
    
    new_image_record = UserImage(
        owner_user_id=current_user.id,
        filename=new_filename,
        prompt=f"Edited from {len(source_images_b64)} image(s): {request.prompt}",
        model=model_full_name
    )
    db.add(new_image_record)
    db.commit()
    db.refresh(new_image_record)
    
    return new_image_record

@image_studio_router.post("/upload", response_model=UserImagePublic)
async def upload_image(
    file: UploadFile = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    user_images_path = get_user_images_path(current_user.username)
    s_filename = secure_filename(file.filename)
    filename = f"{uuid.uuid4().hex}_{s_filename}"
    file_path = user_images_path / filename

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    new_image = UserImage(
        owner_user_id=current_user.id,
        filename=filename,
        prompt="Uploaded image"
    )
    db.add(new_image)
    db.commit()
    db.refresh(new_image)
    return new_image

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