# -*- coding: utf-8 -*-
# Project name: simplified_lollms
# File path: main.py
# Author: ParisNeo
# Creation date: 2025-05-08
# Description: Main FastAPI application for a multi-user LoLLMs and SafeStore
# chat service. Provides API endpoints for user authentication, discussion
# management (including starring and message grading), LLM interaction
# (via lollms-client) with enriched message metadata and multimodal support,
# RAG (via safe_store with multiple datastores), file management for RAG,
# data import/export, discussion sharing, and administrative user management.

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
    BackgroundTasks,
)
from fastapi.middleware.cors import CORSMiddleware
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
    DirectMessage,
    FriendshipStatus,
    Friendship, 
    DataStore as DBDataStore,
    SharedDataStoreLink as DBSharedDataStoreLink,
    init_database,
    get_db,
    hash_password,
    DATABASE_URL_CONFIG_KEY,
    get_friendship_record
)
from lollms_client import (
    LollmsClient,
    MSG_TYPE,
    LollmsDiscussion,
    LollmsDataManager,
    ELF_COMPLETION_FORMAT, # For client params
)

# --- Pydantic Models for API ---
from backend.discussion import LegacyDiscussion # Import the safe legacy class
from backend.session import get_user_discussion_path, get_user_lollms_client
from backend.models import (
UserLLMParams,
UserAuthDetails,
DataStoreBase,
DataStoreCreate,
DataStoreEdit,
DataStorePublic,
DataStoreShareRequest,
)
# safe_store is expected to be installed
try:
    import safe_store
    from safe_store import (
        LogLevel as SafeStoreLogLevel,
    )
except ImportError:
    print(
        "WARNING: safe_store library not found. RAG features will be disabled. Install with: pip install safe_store[all]"
    )
    safe_store = None
    SafeStoreLogLevel = None

#routers
from backend.routers.auth import auth_router
from backend.routers.discussion import discussion_router
from backend.routers.admin import admin_router
from backend.routers.languages import languages_router
from backend.routers.personalities import personalities_router
from backend.routers.friends import friends_router
from backend.routers.dm import dm_router
from backend.routers.stores import store_files_router
from backend.routers.mcp import mcp_router, discussion_tools_router


# --- Application Version ---
from backend.config import(
    APP_VERSION,
    APP_DATA_DIR,
    APP_DB_URL,
    LOLLMS_CLIENT_DEFAULTS,
    INITIAL_ADMIN_USER_CONFIG,
    SERVER_CONFIG,
    TEMP_UPLOADS_DIR_NAME,
    DEFAULT_PERSONALITIES
)

from backend.session import (
    get_user_data_root,
    get_user_discussion_path,
    get_current_active_user,
    get_current_admin_user,
    get_datastore_db_path,
    get_db, get_safe_store_instance,
    get_user_data_root,
    get_user_discussion_assets_path,
    get_user_discussion_path,
    get_user_lollms_client,
    get_user_temp_uploads_path,
    user_sessions
    )
# --- Enriched Application Data Models ---



# --- FastAPI Application Setup ---
app = FastAPI(
    title="Simplified LoLLMs Chat API",
    description="API for a multi-user LoLLMs and SafeStore chat application with RAG, file management, starring, message grading, and data import/export.",
    version=APP_VERSION,
)
security = HTTPBasic()


@app.on_event("startup")
async def on_startup() -> None:
    # 1. Initialize DB
    init_database(APP_DB_URL)
    print("Database initialized.")

    # 2. PERMANENT MIGRATION SCRIPT
    print("\n--- Running Automated Discussion Migration ---")
    db_session = None
    try:
        db_session = next(get_db())
        all_users = db_session.query(DBUser).all()
        for user in all_users:
            username = user.username
            old_discussion_path = get_user_discussion_path(username)
            
            if not (old_discussion_path.exists() and old_discussion_path.is_dir()):
                continue

            print(f"Found legacy discussion folder for '{username}'. Starting migration...")

            if username not in user_sessions:
                user_sessions[username] = {
                    "lollms_client": None,
                    "lollms_model_name": user.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name"),
                    "llm_params": {}
                }
            
            user_data_path = get_user_data_root(username)
            db_path = user_data_path / "discussions.db"
            db_url = f"sqlite:///{db_path.resolve()}"
            # --- FIX: Initialize LollmsDataManager without the invalid argument ---
            dm = LollmsDataManager(db_path=db_url)
            lc = get_user_lollms_client(username)

            migrated_count = 0
            for file_path in old_discussion_path.glob("*.yaml"):
                discussion_db_session = None
                try:
                    old_disc = LegacyDiscussion.load_from_yaml(file_path)
                    if not old_disc:
                        continue

                    # Manually manage the session to ensure it's closed
                    discussion_db_session = dm.get_session()
                    
                    exists = discussion_db_session.query(dm.DiscussionModel).filter_by(id=old_disc.discussion_id).first()
                    if exists:
                        discussion_db_session.close() # Close session even if skipping
                        continue
                    
                    new_db_disc_orm = dm.DiscussionModel(
                        id=old_disc.discussion_id,
                        discussion_metadata={"title": old_disc.title, "rag_datastore_ids": old_disc.rag_datastore_ids},
                        active_branch_id=old_disc.active_branch_id
                    )
                    discussion_db_session.add(new_db_disc_orm)

                    for msg in old_disc.messages:
                        msg_orm = dm.MessageModel(
                            id=msg.id, discussion_id=new_db_disc_orm.id, parent_id=msg.parent_id, 
                            sender=msg.sender, sender_type=msg.sender_type, content=msg.content, 
                            created_at=msg.created_at, binding_name=msg.binding_name, 
                            model_name=msg.model_name, tokens=msg.token_count, 
                            message_metadata={"sources": msg.sources, "steps": msg.steps}
                        )
                        discussion_db_session.add(msg_orm)
                    
                    discussion_db_session.commit()
                    migrated_count += 1
                except Exception as e:
                    if discussion_db_session:
                        discussion_db_session.rollback()
                    print(f"    - FAILED to migrate {file_path.name}: {e}")
                    traceback.print_exc()
                finally:
                    if discussion_db_session:
                        discussion_db_session.close()

            if migrated_count > 0:
                print(f"Successfully migrated {migrated_count} discussions for '{username}'.")
            
            backup_path = old_discussion_path.parent / f"{old_discussion_path.name}_migrated_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            shutil.move(str(old_discussion_path), str(backup_path))
            print(f"Backed up legacy folder to: {backup_path.name}")
            
            if username in user_sessions:
                user_sessions[username]['lollms_client'] = None

    except Exception as e:
        print(f"CRITICAL ERROR during migration: {e}")
        traceback.print_exc()
    finally:
        if db_session:
            db_session.close()
    print("--- Migration Finished ---\n")

    # --- 3. Create Initial Admin User (if needed) ---
    db_for_admin: Optional[Session] = None
    try:
        db_for_admin = next(get_db())
        admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
        admin_password = INITIAL_ADMIN_USER_CONFIG.get("password")
        if not admin_username or not admin_password:
            print("WARNING: Initial admin user 'username' or 'password' not configured. Skipping creation.")
        else:
            existing_admin = db_for_admin.query(DBUser).filter(DBUser.username == admin_username).first()
            if not existing_admin:
                hashed_admin_pass = hash_password(admin_password)
                new_admin = DBUser(
                    username=admin_username, 
                    hashed_password=hashed_admin_pass, 
                    is_admin=True,
                    # ... other admin fields ...
                )
                db_for_admin.add(new_admin)
                db_for_admin.commit()
                print(f"INFO: Initial admin user '{admin_username}' created successfully.")
            else:
                print(f"INFO: Initial admin user '{admin_username}' already exists.")
    except Exception as e:
        print(f"ERROR: Failed during initial admin user setup: {e}")
        traceback.print_exc()
    finally:
        if db_for_admin: db_for_admin.close()

    # --- 4. Populate Default Public Personalities (if needed) ---
    db_for_defaults: Optional[Session] = None
    try:
        db_for_defaults = next(get_db())
        for default_pers_data in DEFAULT_PERSONALITIES:
            exists = db_for_defaults.query(DBPersonality).filter(
                DBPersonality.name == default_pers_data["name"],
                DBPersonality.is_public == True,
                DBPersonality.owner_user_id == None
            ).first()
            if not exists:
                new_pers = DBPersonality(
                    name=default_pers_data["name"], category=default_pers_data.get("category"),
                    author=default_pers_data.get("author", "System"), description=default_pers_data.get("description"),
                    prompt_text=default_pers_data["prompt_text"], disclaimer=default_pers_data.get("disclaimer"),
                    is_public=True, owner_user_id=None
                )
                db_for_defaults.add(new_pers)
                print(f"INFO: Added default public personality: '{new_pers.name}'")
        db_for_defaults.commit()
    except Exception as e:
        if db_for_defaults: db_for_defaults.rollback()
        print(f"ERROR: Failed during default personalities setup: {e}")
        traceback.print_exc()
    finally:
        if db_for_defaults: db_for_defaults.close()

# --- Helper Functions for User-Specific Services ---


# --- Root and Static File Endpoints ---

# Serve discussion assets (uploaded images)
user_assets_path_base = APP_DATA_DIR # Used to construct full path for StaticFiles
# Mount dynamically if needed, or ensure user_assets_path_base/<username>/discussion_assets exists
# For simplicity, assuming /user_assets/<username>/<discussion_id>/<filename> structure client-side
# This requires a more dynamic way to serve files or a wildcard path.
# For now, let client fetch from a dedicated endpoint if needed, or keep images as base64 in YAML (not ideal).
# Let's make a dedicated endpoint.

@app.get("/user_assets/{username}/{discussion_id}/{filename}", include_in_schema=False)
async def get_discussion_asset(
    username: str, discussion_id: str, filename: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> FileResponse:
    # Security: Ensure the currently logged-in user is requesting their own asset
    # or an asset from a discussion they have access to (if sharing discussions is implemented broadly)
    if current_user.username != username:
        # Basic check: If a more complex sharing model for discussions is added, this needs adjustment
        raise HTTPException(status_code=403, detail="Forbidden to access assets of another user.")

    asset_path = get_user_discussion_assets_path(username) / discussion_id / secure_filename(filename)
    if not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found.")
    return FileResponse(asset_path)



app.include_router(auth_router)

# --- Image Upload API ---
upload_router = APIRouter(prefix="/api/upload", tags=["Uploads"])
MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_UPLOADS_PER_MESSAGE = 5

@upload_router.post("/chat_image", response_model=List[Dict[str,str]])
async def upload_chat_images(
    files: List[UploadFile] = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> List[Dict[str,str]]:
    if len(files) > MAX_IMAGE_UPLOADS_PER_MESSAGE:
        raise HTTPException(status_code=400, detail=f"Cannot upload more than {MAX_IMAGE_UPLOADS_PER_MESSAGE} images at once.")

    username = current_user.username
    temp_uploads_path = get_user_temp_uploads_path(username)
    temp_uploads_path.mkdir(parents=True, exist_ok=True)
    
    uploaded_file_infos = []

    for file_upload in files:
        if not file_upload.content_type or not file_upload.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"File '{file_upload.filename}' is not a valid image type.")
        
        # Check file size
        file_upload.file.seek(0, os.SEEK_END)
        file_size = file_upload.file.tell()
        if file_size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"Image '{file_upload.filename}' exceeds max size of {MAX_IMAGE_SIZE_MB}MB.")
        file_upload.file.seek(0) # Reset file pointer

        s_filename_base = secure_filename(Path(file_upload.filename or "uploaded_image").stem)
        s_filename_ext = secure_filename(Path(file_upload.filename or ".png").suffix)
        if not s_filename_ext: s_filename_ext = ".png" # default extension
        
        unique_id = uuid.uuid4().hex[:8]
        final_filename = f"{s_filename_base}_{unique_id}{s_filename_ext}"
        target_file_path = temp_uploads_path / final_filename
        
        try:
            with open(target_file_path, "wb") as buffer:
                shutil.copyfileobj(file_upload.file, buffer)
            
            # Relative path for client to send back, server will resolve later
            relative_server_path = f"{TEMP_UPLOADS_DIR_NAME}/{final_filename}"
            uploaded_file_infos.append({"filename": file_upload.filename, "server_path": relative_server_path})
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not save uploaded image '{file_upload.filename}': {str(e)}")
        finally:
            await file_upload.close()
            
    return uploaded_file_infos
app.include_router(upload_router)



app.include_router(discussion_router)

# --- LoLLMs Configuration API ---
lollms_config_router = APIRouter(prefix="/api/config", tags=["LoLLMs Configuration"])
@lollms_config_router.get("/lollms-models", response_model=List[Dict[str, str]])
async def get_available_lollms_models(current_user: UserAuthDetails = Depends(get_current_active_user)) -> List[Dict[str, str]]:
    lc = get_user_lollms_client(current_user.username); models_set: set[str] = set()
    try:
        binding_models = lc.listModels()
        if isinstance(binding_models, list):
            for item in binding_models:
                if isinstance(item, str): models_set.add(item)
                elif isinstance(item, dict): name = item.get("name", item.get("id", item.get("model_name"))); models_set.add(name)
    except Exception as e: print(f"WARNING: Could not list models from LollmsClient: {e}")
    user_model = user_sessions[current_user.username].get("lollms_model_name"); global_default_model = LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
    if user_model: models_set.add(user_model)
    if global_default_model: models_set.add(global_default_model)
    models_set.discard(""); models_set.discard(None)
    if not models_set and lc.binding is not None and "openai" in lc.binding.binding_name.lower(): models_set.update(["gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"])
    return [{"name": name} for name in sorted(list(models_set))] if models_set else [{"name": "No models found"}]

@lollms_config_router.post("/lollms-model") # This sets the user's default model
async def set_user_lollms_model(model_name: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username
    user_sessions[username]["lollms_model_name"] = model_name
    user_sessions[username]["lollms_client"] = None # Force re-init on next use
    db_user_record = db.query(DBUser).filter(DBUser.username == username).first()
    if db_user_record:
        db_user_record.lollms_model_name = model_name
        try: db.commit()
        except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
    else: raise HTTPException(status_code=404, detail="User not found for model update.")
    return {"message": f"Default LoLLMs model set to '{model_name}'. Client will re-initialize."}

@lollms_config_router.get("/llm-params", response_model=UserLLMParams)
async def get_user_llm_params(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserLLMParams:
    # UserAuthDetails already contains llm_prefixed params, sourced from session's non-prefixed params
    return UserLLMParams(
        llm_ctx_size=current_user.llm_ctx_size,
        llm_temperature=current_user.llm_temperature,
        llm_top_k=current_user.llm_top_k,
        llm_top_p=current_user.llm_top_p,
        llm_repeat_penalty=current_user.llm_repeat_penalty,
        llm_repeat_last_n=current_user.llm_repeat_last_n,
    )

@lollms_config_router.post("/llm-params")
async def set_user_llm_params(params: UserLLMParams, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username
    db_user_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not db_user_record: raise HTTPException(status_code=404, detail="User not found.")

    updated_params_in_db = False
    # Update DBUser record with llm_prefixed fields
    if params.llm_ctx_size is not None and db_user_record.llm_ctx_size != params.llm_ctx_size:
        db_user_record.llm_ctx_size = params.llm_ctx_size; updated_params_in_db = True
    if params.llm_temperature is not None and db_user_record.llm_temperature != params.llm_temperature:
        db_user_record.llm_temperature = params.llm_temperature; updated_params_in_db = True
    if params.llm_top_k is not None and db_user_record.llm_top_k != params.llm_top_k:
        db_user_record.llm_top_k = params.llm_top_k; updated_params_in_db = True
    if params.llm_top_p is not None and db_user_record.llm_top_p != params.llm_top_p:
        db_user_record.llm_top_p = params.llm_top_p; updated_params_in_db = True
    if params.llm_repeat_penalty is not None and db_user_record.llm_repeat_penalty != params.llm_repeat_penalty:
        db_user_record.llm_repeat_penalty = params.llm_repeat_penalty; updated_params_in_db = True
    if params.llm_repeat_last_n is not None and db_user_record.llm_repeat_last_n != params.llm_repeat_last_n:
        db_user_record.llm_repeat_last_n = params.llm_repeat_last_n; updated_params_in_db = True

    if updated_params_in_db:
        try: db.commit()
        except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
    
    # Update session llm_params with non-prefixed keys
    session_llm_params = user_sessions[username].get("llm_params", {})
    updated_params_in_session = False

    if params.llm_ctx_size is not None and session_llm_params.get("ctx_size") != params.llm_ctx_size:
        session_llm_params["ctx_size"] = params.llm_ctx_size; updated_params_in_session = True
    if params.llm_temperature is not None and session_llm_params.get("temperature") != params.llm_temperature:
        session_llm_params["temperature"] = params.llm_temperature; updated_params_in_session = True
    if params.llm_top_k is not None and session_llm_params.get("top_k") != params.llm_top_k:
        session_llm_params["top_k"] = params.llm_top_k; updated_params_in_session = True
    if params.llm_top_p is not None and session_llm_params.get("top_p") != params.llm_top_p:
        session_llm_params["top_p"] = params.llm_top_p; updated_params_in_session = True
    if params.llm_repeat_penalty is not None and session_llm_params.get("repeat_penalty") != params.llm_repeat_penalty:
        session_llm_params["repeat_penalty"] = params.llm_repeat_penalty; updated_params_in_session = True
    if params.llm_repeat_last_n is not None and session_llm_params.get("repeat_last_n") != params.llm_repeat_last_n:
        session_llm_params["repeat_last_n"] = params.llm_repeat_last_n; updated_params_in_session = True
    
    # Filter out None values from session_llm_params after update
    user_sessions[username]["llm_params"] = {k: v for k, v in session_llm_params.items() if v is not None}

    if updated_params_in_session or updated_params_in_db: # If any change happened
        user_sessions[username]["lollms_client"] = None # Force LollmsClient re-init
        return {"message": "LLM parameters updated. Client will re-initialize."}
        
    return {"message": "No changes to LLM parameters."}

app.include_router(lollms_config_router)


# --- DataStore (RAG) API ---
datastore_router = APIRouter(prefix="/api/datastores", tags=["RAG DataStores"])

@datastore_router.post("", response_model=DataStorePublic, status_code=201)
async def create_datastore(ds_create: DataStoreCreate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DBDataStore:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    
    existing_ds = db.query(DBDataStore).filter_by(owner_user_id=user_db_record.id, name=ds_create.name).first()
    if existing_ds: raise HTTPException(status_code=400, detail=f"DataStore with name '{ds_create.name}' already exists for this user.")

    new_ds_db_obj = DBDataStore(
        owner_user_id=user_db_record.id,
        name=ds_create.name,
        description=ds_create.description
    )
    try:
        db.add(new_ds_db_obj); db.commit(); db.refresh(new_ds_db_obj)
        get_safe_store_instance(current_user.username, new_ds_db_obj.id, db)
        
        return DataStorePublic(
            id=new_ds_db_obj.id, name=new_ds_db_obj.name, description=new_ds_db_obj.description,
            owner_username=current_user.username, created_at=new_ds_db_obj.created_at, updated_at=new_ds_db_obj.updated_at
        )
    except IntegrityError: 
        db.rollback(); raise HTTPException(status_code=400, detail="DataStore name conflict (race condition).")
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error creating datastore: {e}")

@datastore_router.post("/edit", response_model=DataStorePublic, status_code=201)
async def create_datastore(ds_edit: DataStoreEdit, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DBDataStore:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    
    existing_ds = db.query(DBDataStore).filter_by(owner_user_id=user_db_record.id, name=ds_edit.name).first()
    existing_ds.name = ds_edit.new_name
    existing_ds.description = ds_edit.description
    try:
        db.commit(); db.refresh(existing_ds)
        get_safe_store_instance(current_user.username, existing_ds.id, db)
        
        return DataStorePublic(
            id=existing_ds.id, name=existing_ds.name, description=existing_ds.description,
            owner_username=current_user.username, created_at=existing_ds.created_at, updated_at=existing_ds.updated_at
        )
    except IntegrityError: 
        db.rollback(); raise HTTPException(status_code=400, detail="DataStore name conflict (race condition).")
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error creating datastore: {e}")


@datastore_router.get("", response_model=List[DataStorePublic])
async def list_my_datastores(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[DataStorePublic]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first() 
    if not user_db_record: 
        raise HTTPException(status_code=404, detail="User database record not found for authenticated user.") 

    owned_datastores_db = db.query(DBDataStore).filter(DBDataStore.owner_user_id == user_db_record.id).order_by(DBDataStore.name).all()
    
    shared_links_query = db.query(
        DBSharedDataStoreLink, DBDataStore
    ).join(
        DBDataStore, DBSharedDataStoreLink.datastore_id == DBDataStore.id
    ).filter(
        DBSharedDataStoreLink.shared_with_user_id == user_db_record.id 
    ).order_by(
        DBDataStore.name
    )
    shared_links_query = shared_links_query.options(
        joinedload(DBSharedDataStoreLink.datastore).joinedload(DBDataStore.owner)
    )
    
    shared_links_and_datastores_db = shared_links_query.all() 

    response_list = []
    for ds_db in owned_datastores_db:
        response_list.append(DataStorePublic(
            id=ds_db.id, name=ds_db.name, description=ds_db.description,
            owner_username=current_user.username, 
            created_at=ds_db.created_at, updated_at=ds_db.updated_at
        ))
    for link, ds_db in shared_links_and_datastores_db: 
        if not any(r.id == ds_db.id for r in response_list):
             response_list.append(DataStorePublic(
                id=ds_db.id, name=ds_db.name, description=ds_db.description,
                owner_username=ds_db.owner.username, 
                created_at=ds_db.created_at, updated_at=ds_db.updated_at
            ))
    return response_list


@datastore_router.put("/{datastore_id}", response_model=DataStorePublic)
async def update_datastore(datastore_id: str, ds_update: DataStoreBase, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DBDataStore:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    
    ds_db_obj = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    if not ds_db_obj: raise HTTPException(status_code=404, detail="DataStore not found.")
    if ds_db_obj.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner can update a DataStore.")

    if ds_update.name != ds_db_obj.name:
        existing_ds = db.query(DBDataStore).filter(DBDataStore.owner_user_id == user_db_record.id, DBDataStore.name == ds_update.name, DBDataStore.id != datastore_id).first()
        if existing_ds: raise HTTPException(status_code=400, detail=f"DataStore with name '{ds_update.name}' already exists.")

    ds_db_obj.name = ds_update.name
    ds_db_obj.description = ds_update.description
    try:
        db.commit(); db.refresh(ds_db_obj)
        return DataStorePublic(
             id=ds_db_obj.id, name=ds_db_obj.name, description=ds_db_obj.description,
             owner_username=current_user.username, created_at=ds_db_obj.created_at, updated_at=ds_db_obj.updated_at
        )
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error updating datastore: {e}")


@datastore_router.delete("/{datastore_id}", status_code=200)
async def delete_datastore(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()) -> Dict[str, str]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    
    ds_db_obj = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    if not ds_db_obj: raise HTTPException(status_code=404, detail="DataStore not found.")
    if ds_db_obj.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete a DataStore.")
    
    ds_file_path = get_datastore_db_path(current_user.username, datastore_id)
    ds_lock_file_path = Path(f"{ds_file_path}.lock")

    try:
        db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id).delete(synchronize_session=False)
        db.delete(ds_db_obj)
        db.commit()
        
        if current_user.username in user_sessions and datastore_id in user_sessions[current_user.username]["safe_store_instances"]:
            del user_sessions[current_user.username]["safe_store_instances"][datastore_id]

        if ds_file_path.exists(): background_tasks.add_task(ds_file_path.unlink, missing_ok=True)
        if ds_lock_file_path.exists(): background_tasks.add_task(ds_lock_file_path.unlink, missing_ok=True)
            
        return {"message": f"DataStore '{ds_db_obj.name}' deleted successfully."}
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error deleting datastore: {e}")

@datastore_router.post("/{datastore_id}/share", status_code=201)
async def share_datastore(datastore_id: str, share_request: DataStoreShareRequest, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db: raise HTTPException(status_code=404, detail="Owner user not found.")

    ds_to_share = db.query(DBDataStore).filter(DBDataStore.id == datastore_id, DBDataStore.owner_user_id == owner_user_db.id).first()
    if not ds_to_share: raise HTTPException(status_code=404, detail="DataStore not found or you are not the owner.")

    target_user_db = db.query(DBUser).filter(DBUser.username == share_request.target_username).first()
    if not target_user_db: raise HTTPException(status_code=404, detail=f"Target user '{share_request.target_username}' not found.")
    
    if owner_user_db.id == target_user_db.id:
        raise HTTPException(status_code=400, detail="Cannot share a datastore with yourself.")

    existing_link = db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id, shared_with_user_id=target_user_db.id).first()
    if existing_link:
        if existing_link.permission_level != share_request.permission_level:
            existing_link.permission_level = share_request.permission_level
            db.commit()
            return {"message": f"DataStore '{ds_to_share.name}' sharing permission updated for user '{target_user_db.username}'."}
        return {"message": f"DataStore '{ds_to_share.name}' already shared with user '{target_user_db.username}' with this permission."}

    new_link = DBSharedDataStoreLink(
        datastore_id=datastore_id,
        shared_with_user_id=target_user_db.id,
        permission_level=share_request.permission_level
    )
    try:
        db.add(new_link); db.commit()
        return {"message": f"DataStore '{ds_to_share.name}' shared successfully with user '{target_user_db.username}'."}
    except IntegrityError: 
        db.rollback(); raise HTTPException(status_code=400, detail="Sharing conflict (race condition).")
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error sharing datastore: {e}")

@datastore_router.delete("/{datastore_id}/share/{target_user_id_or_username}", status_code=200)
async def unshare_datastore(datastore_id: str, target_user_id_or_username: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db: raise HTTPException(status_code=404, detail="Owner user not found.")

    ds_to_unshare = db.query(DBDataStore).filter(DBDataStore.id == datastore_id, DBDataStore.owner_user_id == owner_user_db.id).first()
    if not ds_to_unshare: raise HTTPException(status_code=404, detail="DataStore not found or you are not the owner.")

    target_user_db = None
    try:
        target_user_id = int(target_user_id_or_username)
        target_user_db = db.query(DBUser).filter(DBUser.id == target_user_id).first()
    except ValueError: 
        target_user_db = db.query(DBUser).filter(DBUser.username == target_user_id_or_username).first()
        
    if not target_user_db: raise HTTPException(status_code=404, detail=f"Target user '{target_user_id_or_username}' not found.")

    link_to_delete = db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id, shared_with_user_id=target_user_db.id).first()
    if not link_to_delete:
        raise HTTPException(status_code=404, detail=f"DataStore was not shared with user '{target_user_db.username}'.")

    try:
        db.delete(link_to_delete); db.commit()
        return {"message": f"DataStore '{ds_to_unshare.name}' unshared from user '{target_user_db.username}'."}
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error unsharing datastore: {e}")

app.include_router(datastore_router)


app.include_router(store_files_router)
app.include_router(admin_router)
app.include_router(languages_router)
# Add the router to the main app
app.include_router(personalities_router)
# Add the router to the main app
app.include_router(friends_router)
app.include_router(dm_router)
app.include_router(mcp_router)
app.include_router(discussion_tools_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], # Add your Vue dev server URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
try:
    locales_path = (Path("frontend")/"legacy_webui"/"locals").resolve()
    if locales_path.is_dir(): app.mount("/locals", StaticFiles(directory=locales_path, html=False), name="locals")
    else: print("WARNING: 'locals' directory not found. Localization files will not be served.")
except Exception as e: print(f"ERROR: Failed to mount locals directory: {e}")

# Serve the new Vue.js frontend from the 'dist' directory
print("INFO: Serving new Vue.js frontend.")
VUE_APP_DIR = Path(__file__).resolve().parent / "frontend" / "dist"

# Mount the static assets directory from the Vue build.
# The path must be absolute or relative to where the script is run.
app.mount("/assets", StaticFiles(directory=VUE_APP_DIR / "assets"), name="vue-assets")

# This catch-all route MUST be last.
@app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
async def serve_vue_app(request: Request, full_path: str):
    index_path = VUE_APP_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="Vue app index.html not found. Did you run 'npm run build'?")
    return FileResponse(index_path)

# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    host = SERVER_CONFIG.get("host", "127.0.0.1"); port = int(SERVER_CONFIG.get("port", 9642))
    try: APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e: print(f"CRITICAL: Could not create main data directory {APP_DATA_DIR}: {e}")
    print(f"--- LoLLMs Chat API Server (v{APP_VERSION}) ---")
    print(f"Access UI at: http://{host}:{port}/")
    print(f"Access Admin Panel at: http://{host}:{port}/admin (requires admin login)")
    print("--------------------------------------------------------------------")
    uvicorn.run("main:app", host=host, port=port, reload=False)
