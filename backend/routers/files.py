import os
import shutil
import uuid
from pathlib import Path
from typing import List, Dict

from fastapi import (
    APIRouter, Depends, File, UploadFile, HTTPException
)
from fastapi.responses import FileResponse
from werkzeug.utils import secure_filename

from backend.session import (
    get_current_active_user, get_user_temp_uploads_path, get_user_discussion_assets_path
)
from backend.models import UserAuthDetails
from backend.config import TEMP_UPLOADS_DIR_NAME

upload_router = APIRouter(prefix="/api/upload", tags=["Uploads"])
assets_router = APIRouter()

MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_UPLOADS_PER_MESSAGE = 5

@upload_router.post("/chat_image", response_model=List[Dict[str,str]])
async def upload_chat_images(files: List[UploadFile] = File(...), current_user: UserAuthDetails = Depends(get_current_active_user)):
    if len(files) > MAX_IMAGE_UPLOADS_PER_MESSAGE:
        raise HTTPException(status_code=400, detail=f"Cannot upload more than {MAX_IMAGE_UPLOADS_PER_MESSAGE} images at once.")
    
    username = current_user.username
    temp_uploads_path = get_user_temp_uploads_path(username)
    temp_uploads_path.mkdir(parents=True, exist_ok=True)
    
    uploaded_file_infos = []
    for file_upload in files:
        if not file_upload.content_type or not file_upload.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"File '{file_upload.filename}' is not a valid image type.")
        
        file_upload.file.seek(0, os.SEEK_END)
        if file_upload.file.tell() > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"Image '{file_upload.filename}' exceeds max size of {MAX_IMAGE_SIZE_MB}MB.")
        file_upload.file.seek(0)
        
        s_filename_base, s_filename_ext = os.path.splitext(secure_filename(file_upload.filename or "image"))
        if not s_filename_ext:
            s_filename_ext = ".png"
            
        final_filename = f"{s_filename_base}_{uuid.uuid4().hex[:8]}{s_filename_ext}"
        target_file_path = temp_uploads_path / final_filename
        
        try:
            with open(target_file_path, "wb") as buffer:
                shutil.copyfileobj(file_upload.file, buffer)
            uploaded_file_infos.append({"filename": file_upload.filename, "server_path": f"{TEMP_UPLOADS_DIR_NAME}/{final_filename}"})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not save uploaded image '{file_upload.filename}': {str(e)}")
        finally:
            await file_upload.close()
            
    return uploaded_file_infos

@assets_router.get("/user_assets/{username}/{discussion_id}/{filename}", include_in_schema=False)
async def get_discussion_asset(
    username: str, discussion_id: str, filename: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> FileResponse:
    if current_user.username != username:
        raise HTTPException(status_code=403, detail="Forbidden to access assets of another user.")

    asset_path = get_user_discussion_assets_path(username) / discussion_id / secure_filename(filename)
    if not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found.")
    return FileResponse(asset_path)