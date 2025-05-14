# backend/routers/uploads.py
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Dict
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends

from backend.models.api_models import UserAuthDetails
from backend.services.auth_service import get_current_active_user
from backend.utils.path_helpers import get_user_temp_uploads_path, secure_filename
from backend.config import MAX_IMAGE_SIZE_MB, MAX_IMAGE_UPLOADS_PER_MESSAGE, TEMP_UPLOADS_DIR_NAME

upload_router = APIRouter(prefix="/api/upload", tags=["Uploads"])

@upload_router.post("/chat_image", response_model=List[Dict[str, str]])
async def upload_chat_images(
    files: List[UploadFile] = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> List[Dict[str, str]]:
    if len(files) > MAX_IMAGE_UPLOADS_PER_MESSAGE:
        raise HTTPException(status_code=400, detail=f"Max {MAX_IMAGE_UPLOADS_PER_MESSAGE} images allowed per message.")

    username = current_user.username
    temp_uploads_path = get_user_temp_uploads_path(username)
    uploaded_file_infos = []

    for file_upload in files:
        if not file_upload.content_type or not file_upload.content_type.startswith("image/"):
            # Clean up already processed files if one fails? For now, let's not.
            raise HTTPException(status_code=400, detail=f"File '{file_upload.filename}' is not an image.")

        # Check file size
        file_upload.file.seek(0, os.SEEK_END)
        file_size = file_upload.file.tell()
        if file_size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"Image '{file_upload.filename}' exceeds {MAX_IMAGE_SIZE_MB}MB limit.")
        file_upload.file.seek(0) # Reset cursor for reading

        # Secure filename and create unique name
        s_fn_base = secure_filename(Path(file_upload.filename or "upload").stem)
        s_fn_ext = secure_filename(Path(file_upload.filename or ".png").suffix)
        if not s_fn_ext: # Default to .png if no extension
            s_fn_ext = ".png"
        
        final_filename = f"{s_fn_base}_{uuid.uuid4().hex[:8]}{s_fn_ext}"
        target_file_path = temp_uploads_path / final_filename

        try:
            with open(target_file_path, "wb") as buffer:
                shutil.copyfileobj(file_upload.file, buffer)
            
            # Path for client to use to refer to this temp image (relative to server root where temp uploads are served)
            # This needs to align with how temp images might be served or if they are moved immediately
            # The original code implies these are temporary and moved when used in a message.
            relative_server_path = f"{TEMP_UPLOADS_DIR_NAME}/{final_filename}" # This is a logical path, not directly served
            uploaded_file_infos.append({"filename": file_upload.filename, "server_path": relative_server_path})
        except Exception as e:
            # Log error
            print(f"ERROR: Could not save image '{file_upload.filename}': {str(e)}")
            # traceback.print_exc() # For more detail
            raise HTTPException(status_code=500, detail=f"Could not save image '{file_upload.filename}'.")
        finally:
            await file_upload.close()
            
    return uploaded_file_infos