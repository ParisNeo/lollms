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

languages_router = APIRouter(prefix="/api/languages", tags=["Languages router"])
@languages_router.get("/", response_class=JSONResponse)
async def get_languages():
    languages = {}
    if not LOCALS_DIR.is_dir():
        print(f"Warning: Locals directory not found at {LOCALS_DIR}")
        return {"en": "English", "fr": "Français"}

    try:
        for filepath in LOCALS_DIR.glob("*.json"):
            lang_code = filepath.stem  
            display_name = lang_code.upper()
            if lang_code == "en": display_name = "English"
            elif lang_code == "fr": display_name = "Français"
            elif lang_code == "es": display_name = "Español"
            elif lang_code == "de": display_name = "Deutsch"
            languages[lang_code] = display_name
    except Exception as e:
        print(f"Error scanning locals directory: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve language list.")

    if not languages: 
        print(f"Warning: No JSON language files found in {LOCALS_DIR}")
        return {"en": "English"} 

    return languages

@languages_router.get("/locals/{lang_code}.json")
async def get_locale_file(lang_code: str):
    if not LOCALS_DIR.is_dir():
        raise HTTPException(status_code=404, detail=f"Locals directory not found.")

    if not lang_code.replace('-', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid language code format.")

    file_path = LOCALS_DIR / f"{lang_code}.json"

    if not file_path.is_file():
        base_lang_code = lang_code.split('-')[0]
        if base_lang_code != lang_code:
            base_file_path = LOCALS_DIR / f"{base_lang_code}.json"
            if base_file_path.is_file():
                print(f"Serving base language file {base_file_path} for requested {file_path}")
                try:
                    with open(base_file_path, "r", encoding="utf-8") as f: content = json.load(f)
                    return JSONResponse(content=content)
                except Exception as e:
                    print(f"Error reading base locale file {base_file_path}: {e}")
                    raise HTTPException(status_code=500, detail="Error reading locale file.")
        raise HTTPException(status_code=404, detail=f"Locale file for '{lang_code}' not found.")

    try:
        with open(file_path, "r", encoding="utf-8") as f: content = json.load(f)
        return JSONResponse(content=content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Locale file '{lang_code}.json' is not valid JSON.")
    except Exception as e:
        print(f"Error reading locale file {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Error reading locale file.")

app.include_router(languages_router)


# --- Personality Pydantic Models (ensure these are defined) ---
class PersonalityBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    author: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    prompt_text: str 
    disclaimer: Optional[str] = Field(None, max_length=1000)
    script_code: Optional[str] = None
    icon_base64: Optional[str] = None

class PersonalityCreate(PersonalityBase):
    is_public: Optional[bool] = False 

class PersonalityUpdate(PersonalityBase):
    name: Optional[constr(min_length=1, max_length=100)] = None
    prompt_text: Optional[str] = None
    is_public: Optional[bool] = None # Only admin should be able to make an existing one public

class PersonalityPublic(PersonalityBase):
    id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_public: bool
    owner_username: Optional[str] = None 
    model_config = {"from_attributes": True}

# --- FastAPI Router for Personalities ---
personalities_router = APIRouter(prefix="/api/personalities", tags=["Personalities"])

def get_personality_public_from_db(db_personality: DBPersonality, owner_username: Optional[str] = None) -> PersonalityPublic:
    """Helper to convert DBPersonality to PersonalityPublic, fetching owner username if needed."""
    if owner_username is None and db_personality.owner_user_id and db_personality.owner:
        owner_username = db_personality.owner.username
    elif owner_username is None and db_personality.owner_user_id and not db_personality.owner:
        # This case should be rare if relationships are loaded, but as a fallback:
        # db = next(get_db()) # Avoid creating new session if possible
        # owner = db.query(DBUser.username).filter(DBUser.id == db_personality.owner_user_id).scalar()
        # owner_username = owner if owner else "Unknown"
        # db.close()
        # For simplicity, if owner not loaded, it will be None. Caller should ensure owner is loaded.
        pass


    return PersonalityPublic(
        id=db_personality.id,
        name=db_personality.name,
        category=db_personality.category,
        author=db_personality.author,
        description=db_personality.description,
        prompt_text=db_personality.prompt_text,
        disclaimer=db_personality.disclaimer,
        script_code=db_personality.script_code,
        icon_base64=db_personality.icon_base64,
        created_at=db_personality.created_at,
        updated_at=db_personality.updated_at,
        is_public=db_personality.is_public,
        owner_username=owner_username
    )

@personalities_router.post("", response_model=PersonalityPublic, status_code=201)
async def create_personality(
    personality_data: PersonalityCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> PersonalityPublic:
    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Check for name conflict for this user
    existing_personality = db.query(DBPersonality).filter(
        DBPersonality.owner_user_id == db_user.id,
        DBPersonality.name == personality_data.name
    ).first()
    if existing_personality:
        raise HTTPException(status_code=400, detail=f"You already have a personality named '{personality_data.name}'.")

    # If admin tries to create a public personality
    owner_id_for_new_pers = db_user.id
    if personality_data.is_public and current_user.is_admin:
        # Admin can create a truly public (system) personality with no owner,
        # or a public personality owned by themselves.
        # For simplicity, let's assume admin-created public personalities are system-level (owner_user_id = None)
        # Or, if you want admin to "own" public ones they create:
        # owner_id_for_new_pers = db_user.id
        # For truly public/system, set owner_id_for_new_pers = None
        # Let's make admin-created public personalities owned by them for now, simpler.
        pass # is_public will be set from personality_data
    elif personality_data.is_public and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only administrators can create public personalities.")
    
    db_personality = DBPersonality(
        **personality_data.model_dump(exclude={"is_public"}), # Exclude is_public if handled separately
        owner_user_id=owner_id_for_new_pers, # User owns their created personalities
        is_public=personality_data.is_public if current_user.is_admin else False # User-created are private
    )

    try:
        db.add(db_personality)
        db.commit()
        db.refresh(db_personality)
        return get_personality_public_from_db(db_personality, current_user.username)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Personality name conflict (race condition).")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@personalities_router.get("/my", response_model=List[PersonalityPublic])
async def get_my_personalities(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[PersonalityPublic]:
    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    owned_personalities_db = db.query(DBPersonality).filter(DBPersonality.owner_user_id == db_user.id).order_by(DBPersonality.name).all()
    return [get_personality_public_from_db(p, current_user.username) for p in owned_personalities_db]

@personalities_router.get("/public", response_model=List[PersonalityPublic])
async def get_public_personalities(
    db: Session = Depends(get_db)
    # No auth needed to view public personalities, but could be added if desired
) -> List[PersonalityPublic]:
    # Load owner relationship to get owner_username
    public_personalities_db = db.query(DBPersonality).options(joinedload(DBPersonality.owner)).filter(DBPersonality.is_public == True).order_by(DBPersonality.category, DBPersonality.name).all()
    return [get_personality_public_from_db(p) for p in public_personalities_db]


@personalities_router.get("/{personality_id}", response_model=PersonalityPublic)
async def get_personality(
    personality_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user), # Auth to check ownership for non-public
    db: Session = Depends(get_db)
) -> PersonalityPublic:
    db_personality = db.query(DBPersonality).options(joinedload(DBPersonality.owner)).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user: # Should not happen if current_user is valid
        raise HTTPException(status_code=404, detail="Requesting user not found.")

    is_owner = (db_personality.owner_user_id == db_user.id)

    if not db_personality.is_public and not is_owner:
        raise HTTPException(status_code=403, detail="You do not have permission to view this personality.")
    
    return get_personality_public_from_db(db_personality)


@personalities_router.put("/{personality_id}", response_model=PersonalityPublic)
async def update_personality(
    personality_id: str,
    personality_data: PersonalityUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> PersonalityPublic:
    db_personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    is_owner = (db_personality.owner_user_id == db_user.id)

    if not is_owner and not current_user.is_admin: # Only owner or admin can update
        raise HTTPException(status_code=403, detail="You do not have permission to update this personality.")
    
    # If admin is updating a personality not owned by them, they can change its public status.
    # If user is updating their own, they cannot make it public unless they are also admin.
    if personality_data.is_public is not None:
        if not current_user.is_admin:
            # Non-admin trying to change public status of their own personality
            if is_owner and personality_data.is_public != db_personality.is_public:
                 raise HTTPException(status_code=403, detail="Only administrators can change the public status of a personality.")
        # If admin, they can change is_public for any personality
        # If it's an admin updating their own, they can change it.
        # If it's an admin updating someone else's, they can change it.
        # If it's an admin updating a system (owner_user_id=None) personality, they can change it.
        if current_user.is_admin:
            db_personality.is_public = personality_data.is_public
    
    update_data = personality_data.model_dump(exclude_unset=True, exclude={"is_public"}) # is_public handled above

    if "name" in update_data and update_data["name"] != db_personality.name:
        # Check for name conflict for this user if it's their personality
        # Or global conflict if it's a public personality being renamed by admin
        owner_id_for_check = db_personality.owner_user_id
        if db_personality.is_public and owner_id_for_check is None: # System personality
             existing_conflict = db.query(DBPersonality).filter(
                DBPersonality.owner_user_id == None, # Check among system personalities
                DBPersonality.name == update_data["name"],
                DBPersonality.id != personality_id
            ).first()
        else: # User-owned or admin-owned public
            existing_conflict = db.query(DBPersonality).filter(
                DBPersonality.owner_user_id == owner_id_for_check,
                DBPersonality.name == update_data["name"],
                DBPersonality.id != personality_id
            ).first()
        if existing_conflict:
            raise HTTPException(status_code=400, detail=f"A personality named '{update_data['name']}' already exists.")

    for field, value in update_data.items():
        if hasattr(db_personality, field):
            setattr(db_personality, field, value)
    
    try:
        db.commit()
        db.refresh(db_personality)
        # Reload owner for username if it was an admin editing someone else's
        db.refresh(db_personality, attribute_names=['owner']) 
        return get_personality_public_from_db(db_personality)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Personality name conflict (race condition).")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@personalities_router.delete("/{personality_id}", status_code=200)
async def delete_personality(
    personality_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    db_personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    is_owner = (db_personality.owner_user_id == db_user.id)

    if not is_owner and not (current_user.is_admin and db_personality.is_public):
        # User can delete their own.
        # Admin can delete any public personality (even if owned by another user, or system-owned).
        raise HTTPException(status_code=403, detail="You do not have permission to delete this personality.")

    # If this personality is active for any user, set their active_personality_id to None
    users_with_this_active_personality = db.query(DBUser).filter(DBUser.active_personality_id == personality_id).all()
    for user_to_update in users_with_this_active_personality:
        user_to_update.active_personality_id = None
        # Clear from session if user is active
        if user_to_update.username in user_sessions:
            user_sessions[user_to_update.username]["active_personality_id"] = None
            user_sessions[user_to_update.username]["active_personality_prompt"] = None
            # If this affects the current_user, their session will be updated.
            # If it affects other users, their session will update on their next /me or relevant action.

    try:
        db.delete(db_personality)
        db.commit()
        return {"message": f"Personality '{db_personality.name}' deleted successfully."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@personalities_router.post("/{personality_id}/send", response_model=PersonalityPublic)
async def send_personality_to_user(
    personality_id: str,
    send_request: PersonalitySendRequest,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> PersonalityPublic:
    original_personality = db.query(DBPersonality).filter(
        DBPersonality.id == personality_id,
        # User can send their own, or an admin can send any public one
        or_(
            DBPersonality.owner_user_id == current_db_user.id,
            and_(DBPersonality.is_public == True, current_db_user.is_admin == True)
        )
    ).first()

    if not original_personality:
        raise HTTPException(status_code=404, detail="Personality not found or you don't have permission to send it.")

    target_user = db.query(DBUser).filter(DBUser.username == send_request.target_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Target user '{send_request.target_username}' not found.")
    
    if target_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="Cannot send a personality to yourself.")

    # Check if target user already has a personality with the same name
    existing_target_pers = db.query(DBPersonality).filter(
        DBPersonality.owner_user_id == target_user.id,
        DBPersonality.name == original_personality.name
    ).first()
    if existing_target_pers:
        raise HTTPException(status_code=400, detail=f"User '{target_user.username}' already has a personality named '{original_personality.name}'.")

    copied_personality = DBPersonality(
        name=original_personality.name, # Or prompt for a new name if desired
        category=original_personality.category,
        author=original_personality.author, # Or set to sender: current_db_user.username
        description=original_personality.description,
        prompt_text=original_personality.prompt_text,
        disclaimer=original_personality.disclaimer,
        script_code=original_personality.script_code,
        icon_base64=original_personality.icon_base64,
        owner_user_id=target_user.id, # New owner is the target user
        is_public=False # Copies are private to the recipient
    )
    db.add(copied_personality)
    try:
        db.commit()
        db.refresh(copied_personality)
        return get_personality_public_from_db(copied_personality, target_user.username)
    except IntegrityError: # Should be caught by name check above
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to send personality due to a name conflict for the target user.")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error sending personality: {str(e)}")

# Add the router to the main app
app.include_router(personalities_router)

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

# --- FastAPI Router for Friendships ---
friends_router = APIRouter(prefix="/api/friends", tags=["Friends Management"])

def get_friend_public_from_friendship(friendship: Friendship, current_user_id: int) -> FriendPublic:
    """
    Helper to determine who the 'friend' is in a friendship record
    relative to the current_user_id and format it as FriendPublic.
    """
    friend_user_obj = None
    if friendship.user1_id == current_user_id:
        friend_user_obj = friendship.user2 # The other user is user2
    elif friendship.user2_id == current_user_id:
        friend_user_obj = friendship.user1 # The other user is user1
    
    if not friend_user_obj:
        # This should not happen if the friendship involves the current_user_id
        raise ValueError("Friendship record does not involve the current user.")

    return FriendPublic(
        id=friend_user_obj.id,
        username=friend_user_obj.username,
        friendship_id=friendship.id,
        status_with_current_user=friendship.status # The status of the friendship itself
    )

@friends_router.post("/request", response_model=FriendshipRequestPublic, status_code=201)
async def send_friend_request(
    request_data: FriendRequestCreate,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> FriendshipRequestPublic:
    if current_db_user.username == request_data.target_username:
        raise HTTPException(status_code=400, detail="You cannot send a friend request to yourself.")

    target_user = db.query(DBUser).filter(DBUser.username == request_data.target_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User '{request_data.target_username}' not found.")

    # Ensure canonical order for user1_id and user2_id to prevent duplicate entries
    # (user1_id < user2_id)
    user1_id, user2_id = sorted((current_db_user.id, target_user.id))

    existing_friendship = db.query(Friendship).filter(
        Friendship.user1_id == user1_id,
        Friendship.user2_id == user2_id
    ).first()

    if existing_friendship:
        if existing_friendship.status == FriendshipStatus.ACCEPTED:
            raise HTTPException(status_code=400, detail="You are already friends with this user.")
        elif existing_friendship.status == FriendshipStatus.PENDING and existing_friendship.action_user_id == current_db_user.id:
            raise HTTPException(status_code=400, detail="You have already sent a friend request to this user.")
        elif existing_friendship.status == FriendshipStatus.PENDING and existing_friendship.action_user_id == target_user.id:
            raise HTTPException(status_code=400, detail="This user has already sent you a friend request. Please respond to it.")
        elif existing_friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and user1_id == current_db_user.id: # You blocked them
            raise HTTPException(status_code=403, detail="You have blocked this user. Unblock them to send a request.")
        elif existing_friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and user2_id == current_db_user.id: # You blocked them
             raise HTTPException(status_code=403, detail="You have blocked this user. Unblock them to send a request.")
        elif (existing_friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and user1_id == target_user.id) or \
             (existing_friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and user2_id == target_user.id): # They blocked you
            raise HTTPException(status_code=403, detail="You cannot send a friend request to this user as they have blocked you.")
        # If other statuses, potentially allow re-request or overwrite (e.g., after a decline)
        # For now, if any record exists and isn't one of the above, it's an edge case or needs specific handling.
        # Let's assume we can overwrite a previously declined/removed one by setting status to PENDING.
        existing_friendship.status = FriendshipStatus.PENDING
        existing_friendship.action_user_id = current_db_user.id # Current user is sending the request
        db_friendship_to_return = existing_friendship
    else:
        new_friendship = Friendship(
            user1_id=user1_id,
            user2_id=user2_id,
            status=FriendshipStatus.PENDING,
            action_user_id=current_db_user.id # Current user is sending the request
        )
        db.add(new_friendship)
        db_friendship_to_return = new_friendship
    
    try:
        db.commit()
        db.refresh(db_friendship_to_return)
        return FriendshipRequestPublic(
            friendship_id=db_friendship_to_return.id,
            requesting_user_id=current_db_user.id, # The one who sent the request
            requesting_username=current_db_user.username,
            requested_at=db_friendship_to_return.created_at, # Or updated_at if overwriting
            status=db_friendship_to_return.status
        )
    except IntegrityError: # Should be caught by existing_friendship check mostly
        db.rollback()
        raise HTTPException(status_code=400, detail="Friendship request conflict.")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@friends_router.get("/requests/pending", response_model=List[FriendshipRequestPublic])
async def get_pending_friend_requests(
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> List[FriendshipRequestPublic]:
    """Gets friend requests sent TO the current user that are pending."""
    pending_requests_db = db.query(Friendship).options(
        joinedload(Friendship.user1), # Eager load user1 (potential requester)
        joinedload(Friendship.user2)  # Eager load user2 (potential requester)
    ).filter(
        or_(
            and_(Friendship.user1_id == current_db_user.id, Friendship.action_user_id != current_db_user.id), # Request sent by user2 to user1
            and_(Friendship.user2_id == current_db_user.id, Friendship.action_user_id != current_db_user.id)  # Request sent by user1 to user2
        ),
        Friendship.status == FriendshipStatus.PENDING
    ).all()

    response_list = []
    for req in pending_requests_db:
        requester = req.user1 if req.user2_id == current_db_user.id else req.user2
        if requester: # Ensure requester object is loaded
            response_list.append(FriendshipRequestPublic(
                friendship_id=req.id,
                requesting_user_id=requester.id,
                requesting_username=requester.username,
                requested_at=req.updated_at, # Use updated_at as it reflects when request was made/last actioned
                status=req.status
            ))
    return response_list

@friends_router.put("/requests/{friendship_id}", response_model=FriendPublic)
async def respond_to_friend_request(
    friendship_id: int,
    response_data: FriendshipAction, # e.g., {"action": "accept"} or {"action": "reject"}
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> FriendPublic:
    friendship = db.query(Friendship).filter(Friendship.id == friendship_id).first()

    if not friendship:
        raise HTTPException(status_code=404, detail="Friend request not found.")

    # Ensure the current user is the recipient of this pending request
    is_recipient = (friendship.user1_id == current_db_user.id and friendship.action_user_id != current_db_user.id) or \
                   (friendship.user2_id == current_db_user.id and friendship.action_user_id != current_db_user.id)

    if not is_recipient or friendship.status != FriendshipStatus.PENDING:
        raise HTTPException(status_code=403, detail="Not a valid pending request for you to respond to.")

    action = response_data.action.lower()
    if action == "accept":
        friendship.status = FriendshipStatus.ACCEPTED
        friendship.action_user_id = current_db_user.id # Current user accepted
    elif action == "reject":
        # Option 1: Delete the request
        db.delete(friendship)
        db.commit()
        # Return a specific response or raise an exception that the frontend can interpret as "rejected and removed"
        # For simplicity, let's just say it's gone. The frontend won't see it in pending list.
        # Or, if you want to keep a "declined" state:
        # friendship.status = FriendshipStatus.DECLINED 
        # friendship.action_user_id = current_db_user.id
        # For now, deleting is simpler.
        raise HTTPException(status_code=200, detail="Friend request rejected and removed.") # 200 or 204
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'accept' or 'reject'.")

    try:
        db.commit()
        db.refresh(friendship)
        # Eager load related users for get_friend_public_from_friendship
        db.refresh(friendship, attribute_names=['user1', 'user2'])
        return get_friend_public_from_friendship(friendship, current_db_user.id)
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@friends_router.get("", response_model=List[FriendPublic]) # Get list of accepted friends
async def get_my_friends(
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> List[FriendPublic]:
    # Friendships where current user is user1 OR user2, and status is ACCEPTED
    friendships_db = db.query(Friendship).options(
        joinedload(Friendship.user1), joinedload(Friendship.user2)
    ).filter(
        or_(Friendship.user1_id == current_db_user.id, Friendship.user2_id == current_db_user.id),
        Friendship.status == FriendshipStatus.ACCEPTED
    ).order_by(Friendship.updated_at.desc()).all() # Or order by friend's username

    friends_list = []
    for fs in friendships_db:
        try:
            friends_list.append(get_friend_public_from_friendship(fs, current_db_user.id))
        except ValueError: # Should not happen with the query filter
            pass 
    
    # Sort by username for consistent display
    friends_list.sort(key=lambda f: f.username.lower())
    return friends_list


@friends_router.delete("/{friend_user_id_or_username}", status_code=200) # Unfriend or cancel sent request
async def remove_friend_or_cancel_request(
    friend_user_id_or_username: str,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    other_user = None
    try:
        other_user_id = int(friend_user_id_or_username)
        other_user = db.query(DBUser).filter(DBUser.id == other_user_id).first()
    except ValueError:
        other_user = db.query(DBUser).filter(DBUser.username == friend_user_id_or_username).first()

    if not other_user:
        raise HTTPException(status_code=404, detail="Target user not found.")
    if other_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="Cannot perform this action on yourself.")

    user1_id, user2_id = sorted((current_db_user.id, other_user.id))

    friendship = db.query(Friendship).filter(
        Friendship.user1_id == user1_id,
        Friendship.user2_id == user2_id
    ).first()

    if not friendship:
        raise HTTPException(status_code=404, detail="No friendship or request found with this user.")

    action_taken = ""
    if friendship.status == FriendshipStatus.ACCEPTED:
        # Unfriend: Delete the record
        db.delete(friendship)
        action_taken = "unfriended"
    elif friendship.status == FriendshipStatus.PENDING and friendship.action_user_id == current_db_user.id:
        # Cancel sent request: Delete the record
        db.delete(friendship)
        action_taken = "friend request cancelled"
    elif friendship.status == FriendshipStatus.PENDING and friendship.action_user_id == other_user.id:
        # Reject incoming request: Delete the record (same as /requests/{id} with "reject")
        db.delete(friendship)
        action_taken = "friend request rejected"
    else:
        # E.g., trying to unfriend someone you blocked, or a non-pending/non-accepted state
        raise HTTPException(status_code=400, detail=f"Cannot perform this action on current friendship status: {friendship.status.value}")

    try:
        db.commit()
        return {"message": f"Successfully {action_taken} user '{other_user.username}'."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# --- New Block/Unblock Endpoints ---
@friends_router.put("/block/{user_id_or_username}", response_model=FriendPublic)
async def block_user(
    user_id_or_username: str,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> FriendPublic:
    other_user = None
    try:
        other_user_id_val = int(user_id_or_username)
        other_user = db.query(DBUser).filter(DBUser.id == other_user_id_val).first()
    except ValueError:
        other_user = db.query(DBUser).filter(DBUser.username == user_id_or_username).first()

    if not other_user:
        raise HTTPException(status_code=404, detail="Target user not found.")
    if other_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="You cannot block yourself.")

    friendship = get_friendship_record(db, current_db_user.id, other_user.id)
    
    user1_id_ordered, user2_id_ordered = sorted((current_db_user.id, other_user.id))

    if not friendship:
        friendship = Friendship(
            user1_id=user1_id_ordered,
            user2_id=user2_id_ordered,
            action_user_id=current_db_user.id
        )
        db.add(friendship)
    else:
        # Check if already blocked by the other user
        if (friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and friendship.user1_id == other_user.id) or \
           (friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and friendship.user2_id == other_user.id):
            raise HTTPException(status_code=403, detail="Cannot block a user who has blocked you.")
        friendship.action_user_id = current_db_user.id


    if user1_id_ordered == current_db_user.id: # Current user is user1 in the canonical pair
        friendship.status = FriendshipStatus.BLOCKED_BY_USER1
    else: # Current user is user2 in the canonical pair
        friendship.status = FriendshipStatus.BLOCKED_BY_USER2
    
    try:
        db.commit()
        db.refresh(friendship)
        db.refresh(friendship, attribute_names=['user1', 'user2'])
        return get_friend_public_from_friendship(friendship, current_db_user.id)
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@friends_router.put("/unblock/{user_id_or_username}", response_model=FriendPublic)
async def unblock_user(
    user_id_or_username: str,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> FriendPublic:
    other_user = None
    try:
        other_user_id_val = int(user_id_or_username)
        other_user = db.query(DBUser).filter(DBUser.id == other_user_id_val).first()
    except ValueError:
        other_user = db.query(DBUser).filter(DBUser.username == user_id_or_username).first()

    if not other_user:
        raise HTTPException(status_code=404, detail="Target user not found.")
    if other_user.id == current_db_user.id: # Should not happen if UI prevents
        raise HTTPException(status_code=400, detail="Invalid action.")

    friendship = get_friendship_record(db, current_db_user.id, other_user.id)

    if not friendship:
        raise HTTPException(status_code=404, detail="No relationship record found with this user to unblock.")

    # Check if the current user actually initiated the block
    is_blocker = (friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and friendship.user1_id == current_db_user.id) or \
                 (friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and friendship.user2_id == current_db_user.id)

    if not is_blocker:
        raise HTTPException(status_code=400, detail="You have not blocked this user, or they blocked you.")

    # Unblocking sets the status back to PENDING (or you could delete the record if no prior friendship)
    # If you want to restore previous friendship status, that's more complex (need to store pre-block status)
    # For simplicity, unblocking could mean the relationship is removed, or goes to a neutral state.
    # Let's assume unblocking removes the record, allowing for a fresh start.
    # Or, set to PENDING, with action_user being the one unblocking, effectively "offering" a re-connection.
    # For now, let's just delete the record to signify the end of the block.
    # A more nuanced approach might set it to a neutral state or revert to pre-block status.
    # Let's change this: unblocking will remove the friendship record entirely.
    # This means if they were friends before, they are no longer. They'd have to re-request.
    # This is simpler than trying to restore a previous state.
    
    # Alternative: Set to a neutral state, e.g., if they were friends, they remain friends.
    # If it was PENDING before block, it's gone.
    # This is complex. Let's make unblock simply remove the record for now.
    # If you want to "unblock and revert to previous state", you'd need to store that state.

    # Simpler: Unblocking removes the friendship record. User can re-initiate.
    # db.delete(friendship)

    # More user-friendly: Unblocking sets status to what it might have been before, or neutral.
    # If they were friends, they become friends again. If nothing, then nothing.
    # For now, let's set status to PENDING, with current user as action_user,
    # effectively making them "open" to re-friending. The other user would see nothing changed
    # until a new request is made or accepted.
    # This is still not ideal. The simplest "unblock" is to remove the block status.
    # What was the status before the block? If it was ACCEPTED, should it go back?
    # Let's assume unblocking means the relationship is now "neutral" (no record or a new PENDING if one wants to re-initiate).
    # For this implementation, let's just remove the record.
    
    # Revised: Unblocking sets the status to what it would be if no block existed.
    # If they were friends, they are friends. If it was pending, it's pending from other user.
    # This is too complex without storing pre-block state.
    # Simplest: Unblock removes the record.
    
    # Let's try this: unblocking sets the status to PENDING, with the action_user_id being the one who unblocked.
    # This means the relationship is now open for the other person to accept if they wish, or for the unblocker to send a new request.
    # This is still not perfect.
    # The most straightforward "unblock" is to simply remove the block status.
    # If they were friends before, they are friends again.
    # If the request was pending from the other user, it remains pending from them.
    # If the request was pending from the current user (blocker), it's now unblocked and still pending from them.

    # Let's assume the previous state was "nothing" or "pending from other".
    # Unblocking will effectively delete the friendship record, requiring a new request.
    # This is the cleanest break.
    
    # Final Decision for this iteration: Unblocking removes the friendship record.
    # This forces a re-evaluation of the relationship.
    db.delete(friendship)
    action_message = f"User '{other_user.username}' unblocked. Any previous friendship status is cleared."


    try:
        db.commit()
        # Since the record is deleted, we can't return FriendPublic of the old record.
        # We return a message. The frontend should update its state.
        return JSONResponse(status_code=200, content={"message": action_message})
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")



# Add the router to the main app
app.include_router(friends_router)

dm_router = APIRouter(prefix="/api/dm", tags=["Direct Messaging"])

@dm_router.post("/send", response_model=DirectMessagePublic, status_code=201)
async def send_direct_message(
    dm_data: DirectMessageCreate,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> DirectMessagePublic:
    if current_db_user.id == dm_data.receiver_user_id:
        raise HTTPException(status_code=400, detail="You cannot send a message to yourself.")

    receiver_user = db.query(DBUser).filter(DBUser.id == dm_data.receiver_user_id).first()
    if not receiver_user:
        raise HTTPException(status_code=404, detail="Receiver user not found.")

    # Check friendship status and blocks
    friendship = get_friendship_record(db, current_db_user.id, receiver_user.id) # Uses helper from friends_router

    if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
        # Check for blocks even if not "ACCEPTED" friends, as a block overrides everything
        if friendship: # A record exists, check its status
            if (friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and friendship.user1_id == current_db_user.id) or \
               (friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and friendship.user2_id == current_db_user.id):
                raise HTTPException(status_code=403, detail="You have blocked this user. Unblock them to send messages.")
            if (friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and friendship.user1_id == receiver_user.id) or \
               (friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and friendship.user2_id == receiver_user.id):
                raise HTTPException(status_code=403, detail="You cannot send a message to this user as they have blocked you.")
        # If no record or not accepted (and not blocked by receiver)
        raise HTTPException(status_code=403, detail="You can only send messages to accepted friends who have not blocked you.")


    new_dm = DirectMessage(
        sender_id=current_db_user.id,
        receiver_id=receiver_user.id,
        content=dm_data.content
        # image_references_json=dm_data.image_references_json # If supporting images
    )
    db.add(new_dm)
    try:
        db.commit()
        db.refresh(new_dm)
        # Eager load sender and receiver for username in response
        db.refresh(new_dm, attribute_names=['sender', 'receiver'])
        
        return DirectMessagePublic(
            id=new_dm.id,
            sender_id=new_dm.sender_id,
            sender_username=new_dm.sender.username,
            receiver_id=new_dm.receiver_id,
            receiver_username=new_dm.receiver.username,
            content=new_dm.content,
            sent_at=new_dm.sent_at,
            read_at=new_dm.read_at
            # image_references_json=new_dm.image_references_json
        )
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error sending message: {str(e)}")


@dm_router.get("/conversation/{other_user_id_or_username}", response_model=List[DirectMessagePublic])
async def get_dm_conversation(
    other_user_id_or_username: str,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db),
    before_message_id: Optional[int] = None, # For pagination: load messages before this ID
    limit: int = Query(50, ge=1, le=100) # Pagination limit
) -> List[DirectMessagePublic]:
    other_user = None
    try:
        other_user_id_val = int(other_user_id_or_username)
        other_user = db.query(DBUser).filter(DBUser.id == other_user_id_val).first()
    except ValueError:
        other_user = db.query(DBUser).filter(DBUser.username == other_user_id_or_username).first()

    if not other_user:
        raise HTTPException(status_code=404, detail="Other user not found.")
    if other_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="Cannot fetch conversation with yourself.")

    # Optional: Check friendship status before allowing to view conversation
    # friendship = get_friendship_record(db, current_db_user.id, other_user.id)
    # if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
    #     raise HTTPException(status_code=403, detail="You can only view conversations with accepted friends.")
    # For now, allow viewing even if unfriended, but sending is restricted.

    query = db.query(DirectMessage).options(
        joinedload(DirectMessage.sender), joinedload(DirectMessage.receiver)
    ).filter(
        or_(
            and_(DirectMessage.sender_id == current_db_user.id, DirectMessage.receiver_id == other_user.id),
            and_(DirectMessage.sender_id == other_user.id, DirectMessage.receiver_id == current_db_user.id)
        )
    ).order_by(DirectMessage.sent_at.desc()) # Get newest first for pagination

    if before_message_id:
        before_message = db.query(DirectMessage).filter(DirectMessage.id == before_message_id).first()
        if before_message:
            query = query.filter(DirectMessage.sent_at < before_message.sent_at)
        else: # Invalid before_message_id, return empty or error
            return [] 
            
    messages_db = query.limit(limit).all()
    
    # Mark messages sent by the other user to current_user as read (if not already)
    # This should ideally be a separate endpoint hit when user opens a conversation
    unread_message_ids = [
        msg.id for msg in messages_db 
        if msg.receiver_id == current_db_user.id and msg.read_at is None
    ]
    if unread_message_ids:
        db.query(DirectMessage).filter(
            DirectMessage.id.in_(unread_message_ids)
        ).update({"read_at": datetime.datetime.now(datetime.timezone.utc)}, synchronize_session=False)
        db.commit()
        # Re-fetch to get updated read_at times for the response (or update in-memory)
        for msg in messages_db:
            if msg.id in unread_message_ids:
                msg.read_at = datetime.datetime.now(datetime.timezone.utc) # Approximate

    response_list = [
        DirectMessagePublic(
            id=msg.id,
            sender_id=msg.sender_id,
            sender_username=msg.sender.username,
            receiver_id=msg.receiver_id,
            receiver_username=msg.receiver.username,
            content=msg.content,
            sent_at=msg.sent_at,
            read_at=msg.read_at
            # image_references_json=msg.image_references_json
        ) for msg in reversed(messages_db) # Reverse to show oldest first in the fetched page
    ]
    return response_list

# Endpoint to explicitly mark messages as read (better than doing it in GET)
@dm_router.post("/conversation/{other_user_id}/mark_read", status_code=200)
async def mark_dm_conversation_as_read(
    other_user_id: int,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
):
    # Mark all unread messages received by current_db_user from other_user_id as read
    updated_count = db.query(DirectMessage).filter(
        DirectMessage.sender_id == other_user_id,
        DirectMessage.receiver_id == current_db_user.id,
        DirectMessage.read_at == None
    ).update({"read_at": datetime.datetime.now(datetime.timezone.utc)}, synchronize_session=False)
    
    db.commit()
    return {"message": f"{updated_count} messages marked as read."}


# Placeholder for listing DM conversations (threads)
# This would typically involve getting the latest message from each unique correspondent.
@dm_router.get("/conversations", response_model=List[Dict[str, Any]]) # Response model needs to be defined
async def list_dm_conversations(
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
):
    # This is a complex query to get distinct conversation partners and last message.
    # Using a subquery to get the latest message_id for each conversation pair.
    # SQL might look like:
    # SELECT dm.*, u.username as partner_username FROM direct_messages dm
    # JOIN (
    #   SELECT
    #     CASE WHEN sender_id = :current_user_id THEN receiver_id ELSE sender_id END as partner_id,
    #     MAX(id) as max_id
    #   FROM direct_messages
    #   WHERE sender_id = :current_user_id OR receiver_id = :current_user_id
    #   GROUP BY partner_id
    # ) latest_msg ON dm.id = latest_msg.max_id
    # JOIN users u ON u.id = latest_msg.partner_id
    # ORDER BY dm.sent_at DESC;

    # SQLAlchemy equivalent is more involved. For now, a simplified version:
    # Get all friends, then for each friend, get the last message. This is N+1.
    # A more optimized query is needed for production.

    # Simplified approach: Get all friends, then fetch last message for each.
    friends_response = await get_my_friends(current_db_user, db) # Re-use existing friends list endpoint logic
    
    conversations = []
    for friend in friends_response:
        last_message = db.query(DirectMessage).filter(
            or_(
                and_(DirectMessage.sender_id == current_db_user.id, DirectMessage.receiver_id == friend.id),
                and_(DirectMessage.sender_id == friend.id, DirectMessage.receiver_id == current_db_user.id)
            )
        ).order_by(DirectMessage.sent_at.desc()).first()

        unread_count = db.query(DirectMessage).filter(
            DirectMessage.sender_id == friend.id, # Messages from friend
            DirectMessage.receiver_id == current_db_user.id, # To me
            DirectMessage.read_at == None
        ).scalar() or 0

        if last_message:
            conversations.append({
                "partner_user_id": friend.id,
                "partner_username": friend.username,
                "last_message_content": last_message.content[:50] + "..." if last_message.content and len(last_message.content) > 50 else last_message.content,
                "last_message_sent_at": last_message.sent_at,
                "last_message_sender_id": last_message.sender_id,
                "unread_count": unread_count
            })
        # else: # Friend with no messages yet, could still be listed
        #    conversations.append({ "partner_user_id": friend.id, "partner_username": friend.username, "unread_count": 0})


    # Sort conversations by last message time, descending
    conversations.sort(key=lambda x: x.get("last_message_sent_at", datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)), reverse=True)
    return conversations


app.include_router(dm_router)
