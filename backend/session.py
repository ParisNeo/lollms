# --- Helpers ---
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
    status
)
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

from backend.database_setup import Personality as DBPersonality, MCP as DBMCP
from backend.config import *
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
from lollms_client import (
    LollmsClient,
    MSG_TYPE,
    LollmsDiscussion as LollmsClientDiscussion,
    ELF_COMPLETION_FORMAT, # For client params
)

# --- Pydantic Models for API ---
from backend.models import (
UserCreate,
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
DirectMessageCreate,
TokenData
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


from backend.message import AppLollmsMessage
from backend.discussion import AppLollmsDiscussion
from backend.security import oauth2_scheme, jwt, JWTError, get_password_hash

# --- Global User Session Management & Locks ---
user_sessions: Dict[str, Dict[str, Any]] = {}
message_grade_lock = threading.Lock()

def get_user_by_username(db: Session, username: str) -> Optional[DBUser]:
    return db.query(DBUser).filter(DBUser.username == username).first()

def get_user_by_email(db: Session, email: str) -> Optional[DBUser]:
    return db.query(DBUser).filter(DBUser.email == email).first()


async def get_current_db_user_from_token(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> DBUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


def get_current_active_user(db_user: DBUser = Depends(get_current_db_user_from_token)) -> UserAuthDetails:
    username = db_user.username
    if username not in user_sessions:
        print(f"INFO: Initializing session state for user: {username}")
        initial_lollms_model = db_user.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
        initial_vectorizer = db_user.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer")
        
        session_llm_params = {
            "ctx_size": db_user.llm_ctx_size if db_user.llm_ctx_size is not None else LOLLMS_CLIENT_DEFAULTS.get("ctx_size"),
            "temperature": db_user.llm_temperature if db_user.llm_temperature is not None else LOLLMS_CLIENT_DEFAULTS.get("temperature"),
            "top_k": db_user.llm_top_k if db_user.llm_top_k is not None else LOLLMS_CLIENT_DEFAULTS.get("top_k"),
            "top_p": db_user.llm_top_p if db_user.llm_top_p is not None else LOLLMS_CLIENT_DEFAULTS.get("top_p"),
            "repeat_penalty": db_user.llm_repeat_penalty if db_user.llm_repeat_penalty is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
            "repeat_last_n": db_user.llm_repeat_last_n if db_user.llm_repeat_last_n is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n"),
        }
        session_llm_params = {k: v for k, v in session_llm_params.items() if v is not None}

        user_sessions[username] = {
            "lollms_client": None, "safe_store_instances": {}, 
            "discussions": {}, "discussion_titles": {},
            "active_vectorizer": initial_vectorizer, 
            "lollms_model_name": initial_lollms_model,
            "llm_params": session_llm_params,
            "active_personality_id": db_user.active_personality_id, 
            "active_personality_prompt": None,
        }
        if db_user.active_personality_id:
            db_session_for_init = next(get_db())
            try:
                active_pers = db_session_for_init.query(DBPersonality.prompt_text).filter(DBPersonality.id == db_user.active_personality_id).scalar()
                if active_pers:
                    user_sessions[username]["active_personality_prompt"] = active_pers
            finally:
                db_session_for_init.close()


    lc = get_user_lollms_client(username) 
    ai_name_for_user = getattr(lc, "ai_name", LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant"))
    if not user_sessions[username].get("discussions"): _load_user_discussions(username)

    current_session_llm_params = user_sessions[username].get("llm_params", {})
    return UserAuthDetails(
        username=username, is_admin=db_user.is_admin,
        first_name=db_user.first_name,
        family_name=db_user.family_name,
        email=db_user.email,
        birth_date=db_user.birth_date,
        lollms_model_name=user_sessions[username]["lollms_model_name"],
        safe_store_vectorizer=user_sessions[username]["active_vectorizer"],
        active_personality_id=user_sessions[username]["active_personality_id"],
        lollms_client_ai_name=ai_name_for_user,
        
        llm_ctx_size=current_session_llm_params.get("ctx_size"),
        llm_temperature=current_session_llm_params.get("temperature"),
        llm_top_k=current_session_llm_params.get("top_k"),
        llm_top_p=current_session_llm_params.get("top_p"),
        llm_repeat_penalty=current_session_llm_params.get("repeat_penalty"),
        llm_repeat_last_n=current_session_llm_params.get("repeat_last_n"),
        put_thoughts_in_context=current_session_llm_params.get("put_thoughts_in_context"),
        rag_top_k=db_user.rag_top_k,
        max_rag_len=db_user.max_rag_len,
        rag_n_hops=db_user.rag_n_hops,
        rag_min_sim_percent=db_user.rag_min_sim_percent,
        rag_use_graph=db_user.rag_use_graph,
        rag_graph_response_type=db_user.rag_graph_response_type
    )

def get_current_admin_user(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator privileges required.")
    return current_user


def get_user_lollms_client(username: str) -> LollmsClient:
    session = user_sessions.get(username)
    if not session: raise HTTPException(status_code=500, detail="User session not found for LollmsClient.")
    
    force_reinit = session.get("lollms_client") is None
    
    current_model_name = session["lollms_model_name"]
    if not force_reinit and hasattr(session["lollms_client"], "model_name") and session["lollms_client"].model_name != current_model_name:
        force_reinit = True
    
    if force_reinit:
        model_name = session["lollms_model_name"]
        binding_name = LOLLMS_CLIENT_DEFAULTS.get("binding_name", "lollms")
        host_address = LOLLMS_CLIENT_DEFAULTS.get("host_address","")
        models_path = LOLLMS_CLIENT_DEFAULTS.get("models_path","")
        ctx_size = LOLLMS_CLIENT_DEFAULTS.get("ctx_size", 4096)
        service_key_env_name = LOLLMS_CLIENT_DEFAULTS.get("service_key_env_var")
        service_key = os.getenv(service_key_env_name) if service_key_env_name else None
        user_name_conf = LOLLMS_CLIENT_DEFAULTS.get("user_name", "user")
        ai_name_conf = LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant")
        
        servers_infos = {}

        # 1. Add default MCPs from config.toml
        for mcp_config in DEFAULT_MCPS:
            if "name" in mcp_config and "url" in mcp_config:
                servers_infos[mcp_config["name"]] = {
                    "server_url": mcp_config["url"],
                    "auth_config": {}
                }

        # 2. Add user-specific MCPs from the database (overwrites defaults if names conflict)
        db_session_for_mcp = next(get_db())
        try:
            user_db = db_session_for_mcp.query(DBUser).filter(DBUser.username == username).first()
            if user_db:
                personal_mcps = db_session_for_mcp.query(DBMCP).filter(DBMCP.owner_user_id == user_db.id).all()
                for mcp in personal_mcps:
                    servers_infos[mcp.name] = {
                        "server_url": mcp.url,
                        "auth_config": {}
                    }
        except Exception as e:
            print(f"Error fetching personal MCPs for user {username}: {e}")
        finally:
            db_session_for_mcp.close()

        client_init_params = session.get("llm_params", {}).copy() 

        client_init_params.update({
            "binding_name": binding_name, "model_name": model_name, "host_address": host_address, "models_path": models_path,
            "ctx_size": ctx_size, "service_key": service_key, 
            "user_name": user_name_conf, "ai_name": ai_name_conf,
        })

        if servers_infos:
            mcp_binding_config = { "servers_infos": servers_infos }
            client_init_params["mcp_binding_name"] = "remote_mcp"
            client_init_params["mcp_binding_config"] = mcp_binding_config
        
        completion_format_str = LOLLMS_CLIENT_DEFAULTS.get("completion_format")
        if completion_format_str:
            try: client_init_params["completion_format"] = ELF_COMPLETION_FORMAT.from_string(completion_format_str)
            except ValueError: print(f"WARN: Invalid completion_format '{completion_format_str}' in config.")
        
        try:
            final_client_init_params = {k: v for k, v in client_init_params.items() if v is not None}
            lc = LollmsClient(**final_client_init_params)
            session["lollms_client"] = lc
        except Exception as e:
            traceback.print_exc()
            session["lollms_client"] = None
            print(f"Could not initialize LLM Client: {str(e)}")
            
    return cast(LollmsClient, session["lollms_client"])


def get_safe_store_instance(requesting_user_username: str, datastore_id: str, db: Session) -> safe_store.SafeStore:
    if safe_store is None: raise HTTPException(status_code=501, detail="SafeStore library not installed. RAG is disabled.")
    
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record: raise HTTPException(status_code=404, detail=f"DataStore '{datastore_id}' not found.")

    owner_username = datastore_record.owner.username
    requesting_user_record = db.query(DBUser).filter(DBUser.username == requesting_user_username).first()
    if not requesting_user_record: raise HTTPException(status_code=404, detail="Requesting user not found.")

    is_owner = (owner_username == requesting_user_username)
    is_shared_with_requester = False
    if not is_owner:
        link = db.query(DBSharedDataStoreLink).filter_by(
            datastore_id=datastore_id, shared_with_user_id=requesting_user_record.id
        ).first()
        if link and link.permission_level == "read_query":
            is_shared_with_requester = True
    
    if not is_owner and not is_shared_with_requester:
        raise HTTPException(status_code=403, detail="Access denied to this DataStore.")

    session = user_sessions.get(requesting_user_username)
    if not session: raise HTTPException(status_code=500, detail="User session not found for SafeStore access.")
    
    if datastore_id not in session["safe_store_instances"]:
        ss_db_path = get_datastore_db_path(owner_username, datastore_id)
        encryption_key = SAFE_STORE_DEFAULTS.get("encryption_key")
        log_level_str = SAFE_STORE_DEFAULTS.get("log_level", "INFO").upper()
        ss_log_level = getattr(SafeStoreLogLevel, log_level_str, SafeStoreLogLevel.INFO) if SafeStoreLogLevel else None
        try:
            ss_params = {"db_path": ss_db_path, "encryption_key": encryption_key}
            if ss_log_level is not None: ss_params["log_level"] = ss_log_level
            ss_instance = safe_store.SafeStore(**ss_params)
            session["safe_store_instances"][datastore_id] = ss_instance
        except safe_store.ConfigurationError as e:
            raise HTTPException(status_code=500, detail=f"SafeStore configuration error for {datastore_id}: {str(e)}.")
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not initialize SafeStore for {datastore_id}: {str(e)}")
            
    return cast(safe_store.SafeStore, session["safe_store_instances"][datastore_id])

# --- Discussion Management Helper Functions ---
def _load_user_discussions(username: str) -> None:
    try: lc = get_user_lollms_client(username)
    except HTTPException as e:
        print(f"ERROR: Cannot load discussions for {username}; LollmsClient unavailable: {e.detail}")
        if username in user_sessions: user_sessions[username]["discussions"] = {}; user_sessions[username]["discussion_titles"] = {}
        return
    discussion_dir = get_user_discussion_path(username)
    session = user_sessions[username]
    session["discussions"] = {}; session["discussion_titles"] = {}
    loaded_count = 0
    for file_path in discussion_dir.glob("*.yaml"):
        if file_path.name.startswith('.'): continue
        discussion_id = file_path.stem
        discussion_obj = AppLollmsDiscussion.load_from_disk(lc, file_path)
        if discussion_obj:
            discussion_obj.discussion_id = discussion_id
            session["discussions"][discussion_id] = discussion_obj
            session["discussion_titles"][discussion_id] = discussion_obj.title
            loaded_count += 1
        else: print(f"WARNING: Failed to load discussion from {file_path} for user {username}.")
    print(f"INFO: Loaded {loaded_count} discussions for user {username}.")

def get_user_discussion(username: str, discussion_id: str, create_if_missing: bool = False) -> Optional[AppLollmsDiscussion]:
    session = user_sessions.get(username)
    if not session: raise HTTPException(status_code=500, detail="User session not found.")
    discussion_obj = session["discussions"].get(discussion_id)
    if discussion_obj: return discussion_obj
    try: uuid.UUID(discussion_id)
    except ValueError:
        if not create_if_missing: return None
        else: discussion_id = str(uuid.uuid4())
    safe_discussion_filename = secure_filename(f"{discussion_id}.yaml")
    if not safe_discussion_filename.endswith(".yaml") or safe_discussion_filename == ".yaml":
        raise HTTPException(status_code=400, detail="Invalid discussion ID format.")
    file_path = get_user_discussion_path(username) / safe_discussion_filename
    lc = get_user_lollms_client(username)
    if file_path.exists():
        disk_obj = AppLollmsDiscussion.load_from_disk(lc, file_path)
        if disk_obj:
            disk_obj.discussion_id = discussion_id
            session["discussions"][discussion_id] = disk_obj
            session["discussion_titles"][discussion_id] = disk_obj.title
            return disk_obj
    if create_if_missing:
        new_discussion = AppLollmsDiscussion(lollms_client_instance=lc, discussion_id=discussion_id)
        session["discussions"][discussion_id] = new_discussion
        session["discussion_titles"][discussion_id] = new_discussion.title
        save_user_discussion(username, discussion_id, new_discussion)
        return new_discussion
    return None

def save_user_discussion(username: str, discussion_id: str, discussion_obj: AppLollmsDiscussion) -> None:
    try: uuid.UUID(discussion_id)
    except ValueError: return
    safe_discussion_filename = secure_filename(f"{discussion_id}.yaml")
    if not safe_discussion_filename.endswith(".yaml") or safe_discussion_filename == ".yaml": return
    file_path = get_user_discussion_path(username) / safe_discussion_filename
    try:
        discussion_obj.save_to_disk(file_path)
        if username in user_sessions: user_sessions[username]["discussion_titles"][discussion_id] = discussion_obj.title
    except Exception as e: traceback.print_exc()


# --- User-specific Path Helpers ---
def get_user_data_root(username: str) -> Path:
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    if not all(c in allowed_chars for c in username):
        print(f"WARNING: Attempt to access user data root with invalid username: '{username}'")
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
    try: uuid.UUID(datastore_id)
    except ValueError: raise HTTPException(status_code=400, detail="Invalid datastore ID format.")
    return get_user_datastore_root_path(owner_username) / f"{datastore_id}.db"