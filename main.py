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
    LollmsDiscussion as LollmsClientDiscussion,
    ELF_COMPLETION_FORMAT, # For client params
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
DataStoreEdit,
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


# --- Application Version ---
from backend.config import(
    APP_VERSION,
    PROJECT_ROOT,
    LOCALS_DIR,
    CONFIG_PATH,
    APP_SETTINGS,
    APP_DATA_DIR,
    APP_DB_URL,
    LOLLMS_CLIENT_DEFAULTS,
    SAFE_STORE_DEFAULTS,
    INITIAL_ADMIN_USER_CONFIG,
    SERVER_CONFIG,
    TEMP_UPLOADS_DIR_NAME,
    DISCUSSION_ASSETS_DIR_NAME,
    DATASTORES_DIR_NAME,
    DEFAULT_PERSONALITIES
)

from backend.message import AppLollmsMessage
from backend.discussion import AppLollmsDiscussion
from backend.session import (
    get_current_active_user,
    get_current_admin_user,
    get_current_db_user,
    get_datastore_db_path,
    get_db, get_safe_store_instance,
    get_user_data_root, get_user_datastore_root_path,
    get_user_discussion, get_user_discussion_assets_path,
    get_user_discussion_path,
    get_user_lollms_client,
    get_user_temp_uploads_path,
    user_sessions,
    _load_user_discussions,
    save_user_discussion
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
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"INFO: Data directory ensured at: {APP_DATA_DIR}")
        init_database(APP_DB_URL)
        print(f"INFO: Database initialized at: {APP_DB_URL}")
    except Exception as e:
        print(f"CRITICAL: Failed to initialize data directory or database: {e}")
        return
    db: Optional[Session] = None
    try:
        db = next(get_db())
        admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
        admin_password = INITIAL_ADMIN_USER_CONFIG.get("password")
        if not admin_username or not admin_password:
            print("WARNING: Initial admin user 'username' or 'password' not configured. Skipping creation.")
            return
        existing_admin = db.query(DBUser).filter(DBUser.username == admin_username).first()
        if not existing_admin:
            hashed_admin_pass = hash_password(admin_password)
            def_model = LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
            def_vec = SAFE_STORE_DEFAULTS.get("global_default_vectorizer")
            
            # LLM params from config
            def_temp = LOLLMS_CLIENT_DEFAULTS.get("temperature")
            def_top_k = LOLLMS_CLIENT_DEFAULTS.get("top_k")
            def_top_p = LOLLMS_CLIENT_DEFAULTS.get("top_p")
            def_rep_pen = LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty")
            def_rep_last_n = LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n")

            # RAG params from config (assuming they might be in SAFE_STORE_DEFAULTS or APP_SETTINGS)
            # Using APP_SETTINGS as an example, adjust if they are elsewhere
            def_rag_top_k = APP_SETTINGS.get("default_rag_top_k") 
            def_rag_min_sim_percent = APP_SETTINGS.get("rag_min_sim_percent") 
            def_rag_use_graph = APP_SETTINGS.get("default_rag_use_graph", False)
            def_rag_graph_response_type = APP_SETTINGS.get("default_rag_graph_response_type", "chunks_summary")

            new_admin = DBUser(
                username=admin_username, hashed_password=hashed_admin_pass, is_admin=True,
                # Optional personal info - can be left None or taken from config if available
                first_name=INITIAL_ADMIN_USER_CONFIG.get("first_name"),
                family_name=INITIAL_ADMIN_USER_CONFIG.get("family_name"),
                email=INITIAL_ADMIN_USER_CONFIG.get("email"),
                # birth_date: # Typically not set for initial admin

                lollms_model_name=def_model, 
                safe_store_vectorizer=def_vec,
                # active_personality_id: None, # Default, no active personality initially

                llm_temperature=def_temp, 
                llm_top_k=def_top_k, 
                llm_top_p=def_top_p,
                llm_repeat_penalty=def_rep_pen, 
                llm_repeat_last_n=def_rep_last_n,
                put_thoughts_in_context=LOLLMS_CLIENT_DEFAULTS.get("put_thoughts_in_context", False),

                rag_top_k=def_rag_top_k,
                rag_min_sim_percent=def_rag_min_sim_percent,
                rag_use_graph=def_rag_use_graph,
                rag_graph_response_type=def_rag_graph_response_type
            )
            db.add(new_admin); db.commit()
            print(f"INFO: Initial admin user '{admin_username}' created successfully with default RAG/LLM params.")

        else:
            print(f"INFO: Initial admin user '{admin_username}' already exists.")
    except Exception as e:
        print(f"ERROR: Failed during initial admin user setup: {e}")
        traceback.print_exc()
    finally:
        if db: db.close()

    db_for_defaults: Optional[Session] = None
    try:
        db_for_defaults = next(get_db())
        for default_pers_data in DEFAULT_PERSONALITIES:
            exists = db_for_defaults.query(DBPersonality).filter(
                DBPersonality.name == default_pers_data["name"],
                DBPersonality.is_public == True,
                DBPersonality.owner_user_id == None # System personalities have no owner
            ).first()
            if not exists:
                new_pers = DBPersonality(
                    name=default_pers_data["name"],
                    category=default_pers_data.get("category"),
                    author=default_pers_data.get("author", "System"),
                    description=default_pers_data.get("description"),
                    prompt_text=default_pers_data["prompt_text"],
                    disclaimer=default_pers_data.get("disclaimer"),
                    script_code=default_pers_data.get("script_code"),
                    icon_base64=default_pers_data.get("icon_base64"),
                    is_public=True,
                    owner_user_id=None # System-owned
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
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index_html(request: Request) -> FileResponse:
    index_path = Path("index.html").resolve()
    if not index_path.is_file(): raise HTTPException(status_code=404, detail="index.html not found.")
    return FileResponse(index_path)

@app.get("/main.js", include_in_schema=False)
async def serve_main_js(request: Request) -> FileResponse:
    main_js_path = Path("main.js").resolve()
    if not main_js_path.is_file(): raise HTTPException(status_code=404, detail="main.js not found.")
    return FileResponse(main_js_path, media_type="application/javascript")
@app.get("/style.css", include_in_schema=False)
async def serve_style_css(request: Request) -> FileResponse:
    style_css_path = Path("style.css").resolve()
    if not style_css_path.is_file(): raise HTTPException(status_code=404, detail="style.css not found.")
    return FileResponse(style_css_path, media_type="text/css")

@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def serve_admin_panel_page(admin_user: UserAuthDetails = Depends(get_current_admin_user)) -> FileResponse:
    admin_html_path = Path("admin.html").resolve()
    if not admin_html_path.is_file(): raise HTTPException(status_code=404, detail="admin.html not found.")
    return FileResponse(admin_html_path)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    favicon_path = Path("favicon.ico").resolve()
    return FileResponse(favicon_path, media_type="image/x-icon") if favicon_path.is_file() else Response(status_code=204)

@app.get("/logo.png", include_in_schema=False)
async def logo() -> Response:
    logo_path = Path("logo.png").resolve()
    return FileResponse(logo_path, media_type="image/png") if logo_path.is_file() else Response(status_code=404)

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


try:
    locales_path = Path("locals").resolve()
    if locales_path.is_dir(): app.mount("/locals", StaticFiles(directory=locales_path, html=False), name="locals")
    else: print("WARNING: 'locals' directory not found. Localization files will not be served.")
except Exception as e: print(f"ERROR: Failed to mount locals directory: {e}")

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


# --- SafeStore File Management API (now per-datastore) ---
store_files_router = APIRouter(prefix="/api/store/{datastore_id}", tags=["SafeStore RAG & File Management"])

@store_files_router.get("/vectorizers", response_model=List[Dict[str,str]])
async def list_datastore_vectorizers(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[Dict[str,str]]:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    ss = get_safe_store_instance(current_user.username, datastore_id, db) 
    try:
        with ss: methods_in_db = ss.list_vectorization_methods(); possible_names = ss.list_possible_vectorizer_names()
        formatted = []; existing_names = set()
        for method_info in methods_in_db:
            name = method_info.get("method_name")
            if name: formatted.append({"name": name, "method_name": f"{name} (dim: {method_info.get('vector_dim', 'N/A')})"}); existing_names.add(name)
        for possible_name in possible_names:
            if possible_name not in existing_names:
                display_text = possible_name
                if possible_name.startswith("tfidf:"): display_text = f"{possible_name} (TF-IDF)"
                elif possible_name.startswith("st:"): display_text = f"{possible_name} (Sentence Transformer)"
                formatted.append({"name": possible_name, "method_name": display_text})
        final_list = []; seen_names = set()
        for fv in formatted:
            if fv["name"] not in seen_names: final_list.append(fv); seen_names.add(fv["name"])
        final_list.sort(key=lambda x: x["name"]); return final_list
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error listing vectorizers for datastore {datastore_id}: {e}")


@store_files_router.post("/upload-files") 
async def upload_rag_documents_to_datastore(
    datastore_id: str, files: List[UploadFile] = File(...), vectorizer_name: str = Form(...),
    current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)
) -> JSONResponse:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    ds_record = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not ds_record or not user_db_record or ds_record.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner can upload files to this DataStore.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db) 
    
    datastore_docs_path = get_user_datastore_root_path(current_user.username) / "safestore_docs" / datastore_id
    datastore_docs_path.mkdir(parents=True, exist_ok=True)

    processed, errors_list = [], []
    try:
        with ss: all_vectorizers = {m['method_name'] for m in ss.list_vectorization_methods()} | set(ss.list_possible_vectorizer_names())
        if not (vectorizer_name in all_vectorizers or vectorizer_name.startswith("st:") or vectorizer_name.startswith("tfidf:")):
             raise HTTPException(status_code=400, detail=f"Vectorizer '{vectorizer_name}' not found or invalid format for datastore {datastore_id}.")
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error checking vectorizer for datastore {datastore_id}: {e}")

    for file_upload in files:
        s_filename = secure_filename(file_upload.filename or f"upload_{uuid.uuid4().hex[:8]}")
        target_file_path = datastore_docs_path / s_filename
        try:
            with open(target_file_path, "wb") as buffer: shutil.copyfileobj(file_upload.file, buffer)
            with ss: ss.add_document(str(target_file_path), vectorizer_name=vectorizer_name)
            processed.append(s_filename)
        except Exception as e:
            errors_list.append({"filename": s_filename, "error": str(e)}); target_file_path.unlink(missing_ok=True); traceback.print_exc()
        finally: await file_upload.close()
    status_code, msg = (207, "Some files processed with errors.") if errors_list and processed else \
                       (400, "Failed to process uploaded files.") if errors_list else \
                       (200, "All files uploaded and processed successfully.")
    return JSONResponse(status_code=status_code, content={"message": msg, "processed_files": processed, "errors": errors_list})

@store_files_router.get("/files", response_model=List[SafeStoreDocumentInfo])
async def list_rag_documents_in_datastore(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[SafeStoreDocumentInfo]:
    if not safe_store: return []
    ss = get_safe_store_instance(current_user.username, datastore_id, db) 
    managed_docs = []
    try:
        with ss: stored_meta = ss.list_documents()
        ds_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
        if not ds_record: raise HTTPException(status_code=404, detail="Datastore metadata not found in main DB.")
        
        expected_docs_root = get_user_datastore_root_path(ds_record.owner.username) / "safestore_docs" / datastore_id
        expected_docs_root_resolved = expected_docs_root.resolve()

        for doc_meta in stored_meta:
            original_path_str = doc_meta.get("file_path")
            if original_path_str:
                try:
                    if Path(original_path_str).resolve().parent == expected_docs_root_resolved:
                        managed_docs.append(SafeStoreDocumentInfo(filename=Path(original_path_str).name))
                except Exception: pass 
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error listing RAG docs for datastore {datastore_id}: {e}")
    managed_docs.sort(key=lambda x: x.filename); return managed_docs


@store_files_router.delete("/files/{filename}") 
async def delete_rag_document_from_datastore(datastore_id: str, filename: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    ds_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not ds_record or not user_db_record or ds_record.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete files from this DataStore.")

    s_filename = secure_filename(filename)
    if not s_filename or s_filename != filename: raise HTTPException(status_code=400, detail="Invalid filename.")
    
    datastore_docs_path = get_user_datastore_root_path(current_user.username) / "safestore_docs" / datastore_id
    file_to_delete_path = datastore_docs_path / s_filename
    if not file_to_delete_path.is_file(): raise HTTPException(status_code=404, detail=f"Document '{s_filename}' not found in datastore {datastore_id}.")
    
    ss = get_safe_store_instance(current_user.username, datastore_id, db)
    try:
        with ss: ss.delete_document_by_path(str(file_to_delete_path))
        file_to_delete_path.unlink()
        return {"message": f"Document '{s_filename}' deleted successfully from datastore {datastore_id}."}
    except Exception as e:
        if file_to_delete_path.exists(): raise HTTPException(status_code=500, detail=f"Could not delete '{s_filename}' from datastore {datastore_id}: {e}")
        else: return {"message": f"Document '{s_filename}' file deleted, potential DB cleanup issue in datastore {datastore_id}."}

app.include_router(store_files_router)
app.include_router(admin_router)

app.include_router(languages_router)

# Add the router to the main app
app.include_router(personalities_router)

# Add the router to the main app
app.include_router(friends_router)

app.include_router(dm_router)


# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    host = SERVER_CONFIG.get("host", "127.0.0.1"); port = int(SERVER_CONFIG.get("port", 9642))
    try: APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e: print(f"CRITICAL: Could not create main data directory {APP_DATA_DIR}: {e}")
    print(f"--- Simplified LoLLMs Chat API Server (v{APP_VERSION}) ---")
    print(f"Access UI at: http://{host}:{port}/")
    print(f"Access Admin Panel at: http://{host}:{port}/admin (requires admin login)")
    print("--------------------------------------------------------------------")
    uvicorn.run("main:app", host=host, port=port, reload=False) 
