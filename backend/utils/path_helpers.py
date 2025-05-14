# backend/utils/path_helpers.py
import uuid
from pathlib import Path
from fastapi import HTTPException
from werkzeug.utils import secure_filename # Keep this if you don't want to reimplement secure_filename

from backend.config import (
    APP_DATA_DIR,
    TEMP_UPLOADS_DIR_NAME,
    DISCUSSION_ASSETS_DIR_NAME,
    DATASTORES_DIR_NAME,
)

def get_user_data_root(username: str) -> Path:
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    if not all(c in allowed_chars for c in username):
        raise HTTPException(status_code=400, detail="Invalid username format for path.")
    path = APP_DATA_DIR / username
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_user_discussion_path(username: str) -> Path:
    path = get_user_data_root(username) / "discussions"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_user_discussion_assets_path(username: str) -> Path:
    path = get_user_data_root(username) / DISCUSSION_ASSETS_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_user_temp_uploads_path(username: str) -> Path:
    path = get_user_data_root(username) / TEMP_UPLOADS_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_user_datastore_root_path(username: str) -> Path:
    path = get_user_data_root(username) / DATASTORES_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_datastore_db_path(owner_username: str, datastore_id: str) -> Path:
    try:
        uuid.UUID(datastore_id) # Validate it's a UUID
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datastore ID format.")
    return get_user_datastore_root_path(owner_username) / f"{datastore_id}.db"

# If you want to avoid werkzeug for secure_filename:
# You can implement a simplified version or use a different library.
# For now, keeping werkzeug.utils.secure_filename is fine.
# from werkzeug.utils import secure_filename