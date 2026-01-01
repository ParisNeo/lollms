# backend/routers/image_studio.py
import base64
import uuid
import json
from pathlib import Path
from typing import List, Optional
from PIL import Image
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Request, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename
from ascii_colors import trace_exception

from backend.db import get_db
from backend.db.models.image import UserImage, ImageAlbum
from backend.models import UserAuthDetails, TaskInfo
from backend.models.image import (
    UserImagePublic, ImageGenerationRequest, MoveImageToDiscussionRequest, 
    ImageEditRequest, ImagePromptEnhancementRequest, ImagePromptEnhancementResponse,
    SaveCanvasRequest, TimelapseRequest,
    ImageAlbumCreate, ImageAlbumUpdate, ImageAlbumPublic, MoveImageToAlbumRequest
)
from backend.session import (
    get_current_active_user, get_user_data_root, 
    build_lollms_client_from_params, get_user_lollms_client,
    get_user_images_path
)
from backend.config import IMAGES_DIR_NAME
from backend.discussion import get_user_discussion
from backend.task_manager import task_manager
from backend.tasks.utils import _to_task_info
from backend.tasks.image_generation_tasks import (
    _image_studio_generate_task, 
    _image_studio_edit_task, 
    _image_studio_enhance_prompt_task,
    _generate_timelapse_task
)

image_studio_router = APIRouter(
    prefix="/api/image-studio",
    tags=["Image Studio"],
    dependencies=[Depends(get_current_active_user)]
)

# --- Album Management ---

@image_studio_router.get("/albums", response_model=List[ImageAlbumPublic])
async def get_albums(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return db.query(ImageAlbum).filter(ImageAlbum.owner_user_id == current_user.id).order_by(ImageAlbum.created_at.desc()).all()

@image_studio_router.post("/albums", response_model=ImageAlbumPublic)
async def create_album(
    album: ImageAlbumCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    new_album = ImageAlbum(name=album.name, owner_user_id=current_user.id)
    db.add(new_album)
    db.commit()
    db.refresh(new_album)
    return new_album

@image_studio_router.put("/albums/{album_id}", response_model=ImageAlbumPublic)
async def update_album(
    album_id: str,
    album: ImageAlbumUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_album = db.query(ImageAlbum).filter(ImageAlbum.id == album_id, ImageAlbum.owner_user_id == current_user.id).first()
    if not db_album:
        raise HTTPException(status_code=404, detail="Album not found")
    db_album.name = album.name
    db.commit()
    db.refresh(db_album)
    return db_album

@image_studio_router.delete("/albums/{album_id}", status_code=204)
async def delete_album(
    album_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_album = db.query(ImageAlbum).filter(ImageAlbum.id == album_id, ImageAlbum.owner_user_id == current_user.id).first()
    if not db_album:
        raise HTTPException(status_code=404, detail="Album not found")
    db.delete(db_album)
    db.commit()

@image_studio_router.put("/images/{image_id}/album")
async def move_image_to_album(
    image_id: str,
    payload: MoveImageToAlbumRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    image = db.query(UserImage).filter(UserImage.id == image_id, UserImage.owner_user_id == current_user.id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    if payload.album_id:
        album = db.query(ImageAlbum).filter(ImageAlbum.id == payload.album_id, ImageAlbum.owner_user_id == current_user.id).first()
        if not album:
            raise HTTPException(status_code=404, detail="Album not found")
        image.album_id = payload.album_id
    else:
        image.album_id = None
        
    db.commit()
    return {"message": "Image moved successfully"}

# --- Image Management ---

@image_studio_router.get("", response_model=List[UserImagePublic])
async def get_user_images(
    album_id: Optional[str] = None,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(UserImage).filter(UserImage.owner_user_id == current_user.id)
    if album_id:
        query = query.filter(UserImage.album_id == album_id)
    else:
        # Optional: Decide if default view shows ALL images or only ungrouped. 
        # Usually "All Photos" shows everything. 
        # If we pass explicit 'none' string, filter for null.
        if album_id == 'none':
            query = query.filter(UserImage.album_id == None)
            
    return query.order_by(UserImage.created_at.desc()).all()

@image_studio_router.get("/{image_id}/file")
async def get_image_file(
    image_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    image_record = db.query(UserImage).filter(UserImage.id == image_id, UserImage.owner_user_id == current_user.id).first()
    filename = image_record.filename if image_record else image_id
    filename = secure_filename(filename)
    file_path = get_user_images_path(current_user.username) / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk.")
    return FileResponse(str(file_path))

@image_studio_router.post("/save-canvas", response_model=UserImagePublic)
async def save_canvas_as_new_image(
    payload: SaveCanvasRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    try:
        if payload.base_image_b64:
            base_image_bytes = base64.b64decode(payload.base_image_b64)
            base_img = Image.open(io.BytesIO(base_image_bytes)).convert("RGBA")
        else:
            base_img = Image.new("RGBA", (payload.width, payload.height), payload.bg_color)

        if payload.drawing_b64:
            drawing_bytes = base64.b64decode(payload.drawing_b64)
            drawing_img = Image.open(io.BytesIO(drawing_bytes)).convert("RGBA")
            if drawing_img.size != base_img.size:
                drawing_img = drawing_img.resize(base_img.size, Image.Resampling.LANCZOS)
            final_img = Image.alpha_composite(base_img, drawing_img)
        else:
            final_img = base_img

        user_images_path = get_user_images_path(current_user.username)
        filename = f"{uuid.uuid4().hex}.png"
        file_path = user_images_path / filename

        final_img.save(file_path, "PNG")

        new_image = UserImage(
            id=str(uuid.uuid4()),
            owner_user_id=current_user.id,
            filename=filename,
            prompt=payload.prompt,
            model=payload.model
        )
        db.add(new_image)
        db.commit()
        db.refresh(new_image)
        return new_image

    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to save canvas: {e}")

@image_studio_router.post("/generate", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def generate_image(
    request: Request,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    request_data = await request.json()
    model_full_name = request_data.get("model") or current_user.tti_binding_model_name
    if not model_full_name or '/' not in model_full_name:
        raise HTTPException(status_code=400, detail="A valid TTI model must be selected.")

    db_task = task_manager.submit_task(
        name=f"Generating {request_data.get('n', 1)} image(s): {request_data.get('prompt', '')[:30]}...",
        target=_image_studio_generate_task,
        args=(current_user.username, request_data),
        description=f"Generating {request_data.get('n', 1)} image(s) with prompt: '{request_data.get('prompt', '')[:50]}...'",
        owner_username=current_user.username
    )
    return db_task

@image_studio_router.post("/edit", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def edit_image(
    request: Request,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    request_data = await request.json()
    model_full_name = request_data.get("model") or current_user.tti_binding_model_name
    if not model_full_name or '/' not in model_full_name:
        raise HTTPException(status_code=400, detail="A valid TTI model must be selected.")

    db_task = task_manager.submit_task(
        name=f"Editing image: {request_data.get('prompt', '')[:30]}...",
        target=_image_studio_edit_task,
        args=(current_user.username, request_data),
        description=f"Editing image(s) with prompt: '{request_data.get('prompt', '')[:50]}...'",
        owner_username=current_user.username
    )
    return db_task

@image_studio_router.post("/upload", response_model=List[UserImagePublic])
async def upload_images(
    files: List[UploadFile] = File(...),
    album_id: Optional[str] = Form(None), # Allow upload directly to album
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    user_images_path = get_user_images_path(current_user.username)
    new_images_db = []
    
    target_album_id = None
    if album_id and album_id != 'null' and album_id != 'undefined':
        # Verify ownership
        album = db.query(ImageAlbum).filter(ImageAlbum.id == album_id, ImageAlbum.owner_user_id == current_user.id).first()
        if album: target_album_id = album.id

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
            prompt="Uploaded image",
            album_id=target_album_id
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

@image_studio_router.post("/enhance-prompt", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def enhance_image_prompt(
    request: ImagePromptEnhancementRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    db_task = task_manager.submit_task(
        name=f"Enhancing prompt: {request.prompt[:30]}...",
        target=_image_studio_enhance_prompt_task,
        args=(current_user.username, request.model_dump()),
        description="AI is enhancing your prompt...",
        owner_username=current_user.username
    )
    return db_task

@image_studio_router.post("/timelapse", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def generate_timelapse(
    request: TimelapseRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    model_full_name = request.model or current_user.tti_binding_model_name
    if not model_full_name or '/' not in model_full_name:
        raise HTTPException(status_code=400, detail="A valid TTI model must be selected for timelapse generation.")

    db_task = task_manager.submit_task(
        name=f"Generating Timelapse ({len(request.keyframes)} frames)",
        target=_generate_timelapse_task,
        args=(current_user.username, request.model_dump()),
        description="Generating storyboard images and compiling video...",
        owner_username=current_user.username
    )
    return db_task
