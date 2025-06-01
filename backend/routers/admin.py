
# --- Authentication API ---
# Standard Library Imports
import os
import shutil
import uuid
import json
from pathlib import Path
from typing import List, Dict, Optional, Any, cast, Union, Tuple, AsyncGenerator
import datetime
import asyncio
import threading
import traceback
import io

# Third-Party Imports
import toml
import yaml
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
    File,
    UploadFile,
    Form,
    APIRouter,
    Response,
    Query,
    BackgroundTasks
)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import (
    HTMLResponse,
    StreamingResponse,
    JSONResponse,
    FileResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, constr, field_validator, validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import (
    or_, and_ # Add this line
)
from dataclasses import dataclass, field as dataclass_field
from werkzeug.utils import secure_filename
from pydantic import BaseModel, Field, constr, field_validator, validator # Ensure these are imported
import datetime # Ensure datetime is imported

from backend.database_setup import Personality as DBPersonality # Add this import at the top of main.py

# Local Application Imports
from backend.database_setup import (
    User as DBUser,
    UserStarredDiscussion,
    UserMessageGrade,
    FriendshipStatus,Friendship, 
    DataStore as DBDataStore,
    SharedDataStoreLink as DBSharedDataStoreLink,
    init_database,
    get_db,
    hash_password,
    DATABASE_URL_CONFIG_KEY,
)

# --- Pydantic Models for API ---
from backend.models import (
UserLLMParams,
UserAuthDetails,
UserCreateAdmin,
UserPasswordResetAdmin,UserPasswordChange,
UserPublic,
DiscussionInfo,
DiscussionTitleUpdate,
DiscussionRagDatastoreUpdate,MessageOutput,
MessageContentUpdate,
MessageGradeUpdate,
SafeStoreDocumentInfo,
DiscussionExportRequest,
ExportData,
DiscussionImportRequest,
DiscussionSendRequest,
DataStoreBase,
DataStoreCreate,
DataStorePublic,
DataStoreShareRequest,
PersonalityBase,
PersonalityCreate,
PersonalityUpdate,
PersonalityPublic,
UserUpdate,
FriendshipBase,
FriendRequestCreate,
FriendshipAction,
FriendPublic,
FriendshipRequestPublic,
PersonalitySendRequest,

DirectMessagePublic,
DirectMessageCreate
)

from backend.session import (
    get_user_data_root,
    get_current_admin_user,
    get_current_active_user,
    get_current_db_user,
    get_user_lollms_client,
    get_user_temp_uploads_path,
    user_sessions)
from backend.config import (
    LOLLMS_CLIENT_DEFAULTS,
    INITIAL_ADMIN_USER_CONFIG,
    SAFE_STORE_DEFAULTS)

auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])
security = HTTPBasic()


# --- Admin API ---
admin_router = APIRouter(prefix="/api/admin", tags=["Administration"], dependencies=[Depends(get_current_admin_user)])
@admin_router.get("/users", response_model=List[UserPublic])
async def admin_get_all_users(db: Session = Depends(get_db)) -> List[DBUser]: return db.query(DBUser).all()

@admin_router.post("/users", response_model=UserPublic, status_code=201)
async def admin_add_new_user(user_data: UserCreateAdmin, db: Session = Depends(get_db)) -> DBUser:
    if db.query(DBUser).filter(DBUser.username == user_data.username).first(): raise HTTPException(status_code=400, detail="Username already registered.")
    
    # user_data has llm_prefixed params. DBUser also expects llm_prefixed params.
    # Default values from LOLLMS_CLIENT_DEFAULTS are non-prefixed.
    new_db_user = DBUser(
        username=user_data.username, hashed_password=hash_password(user_data.password), 
        is_admin=user_data.is_admin, 
        lollms_model_name=user_data.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name"),
        safe_store_vectorizer=user_data.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
        llm_temperature=user_data.llm_temperature if user_data.llm_temperature is not None else LOLLMS_CLIENT_DEFAULTS.get("temperature"),
        llm_top_k=user_data.llm_top_k if user_data.llm_top_k is not None else LOLLMS_CLIENT_DEFAULTS.get("top_k"),
        llm_top_p=user_data.llm_top_p if user_data.llm_top_p is not None else LOLLMS_CLIENT_DEFAULTS.get("top_p"),
        llm_repeat_penalty=user_data.llm_repeat_penalty if user_data.llm_repeat_penalty is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
        llm_repeat_last_n=user_data.llm_repeat_last_n if user_data.llm_repeat_last_n is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n"),
        put_thoughts_in_context=user_data.put_thoughts_in_context if user_data.put_thoughts_in_context is not None else LOLLMS_CLIENT_DEFAULTS.get("put_thoughts_in_context", False)
    )
    try: db.add(new_db_user); db.commit(); db.refresh(new_db_user); return new_db_user
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")

@admin_router.post("/users/{user_id}/reset-password")
async def admin_reset_user_password(user_id: int, payload: UserPasswordResetAdmin, db: Session = Depends(get_db)) -> Dict[str, str]:
    user_to_update = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_update: raise HTTPException(status_code=404, detail="User not found.")
    user_to_update.hashed_password = hash_password(payload.new_password)
    try: db.commit(); return {"message": f"Password for user '{user_to_update.username}' reset."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")

@admin_router.delete("/users/{user_id}")
async def admin_remove_user(user_id: int, db: Session = Depends(get_db), current_admin: UserAuthDetails = Depends(get_current_admin_user), background_tasks: BackgroundTasks = BackgroundTasks()) -> Dict[str, str]:
    user_to_delete = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_delete: raise HTTPException(status_code=404, detail="User not found.")
    initial_admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
    if initial_admin_username and user_to_delete.username == initial_admin_username and user_to_delete.is_admin: raise HTTPException(status_code=403, detail="Initial superadmin cannot be deleted.")
    if user_to_delete.username == current_admin.username: raise HTTPException(status_code=403, detail="Administrators cannot delete themselves.")
    
    user_data_dir_to_delete = get_user_data_root(user_to_delete.username) 

    try:
        if user_to_delete.username in user_sessions:
            del user_sessions[user_to_delete.username]

        db.delete(user_to_delete) 
        db.commit()
        
        if user_data_dir_to_delete.exists():
            background_tasks.add_task(shutil.rmtree, user_data_dir_to_delete, ignore_errors=True)
            
        return {"message": f"User '{user_to_delete.username}' and their data deleted."}
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error or file system error during user deletion: {e}")
