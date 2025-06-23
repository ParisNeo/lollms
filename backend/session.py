# backend/session.py

# --- Standard Library Imports ---
import os
import shutil
import uuid
import json
from pathlib import Path
from typing import Dict, Optional, Any, cast
import traceback

# --- Third-Party Imports ---
from fastapi import HTTPException, Depends, status
from sqlalchemy.orm import Session, joinedload
from werkzeug.utils import secure_filename

# --- Local Application Imports ---
from backend.database_setup import (
    User as DBUser,
    DataStore as DBDataStore,
    SharedDataStoreLink as DBSharedDataStoreLink,
    Personality as DBPersonality,
    MCP as DBMCP,
    get_db,
)
from lollms_client import (
    LollmsClient,
    ELF_COMPLETION_FORMAT,
)
from backend.models import UserAuthDetails, TokenData
from backend.security import oauth2_scheme, jwt, JWTError, SECRET_KEY, ALGORITHM
from backend.config import (
    APP_DATA_DIR,
    LOLLMS_CLIENT_DEFAULTS,
    SAFE_STORE_DEFAULTS,
    DEFAULT_MCPS,
    TEMP_UPLOADS_DIR_NAME,
    DISCUSSION_ASSETS_DIR_NAME,
    DATASTORES_DIR_NAME,
)

# --- safe_store is optional ---
try:
    import safe_store
    from safe_store import LogLevel as SafeStoreLogLevel
except ImportError:
    safe_store = None
    SafeStoreLogLevel = None


# --- Global User Session Management ---
user_sessions: Dict[str, Dict[str, Any]] = {}


# --- User & Authentication Helpers ---

def get_user_by_username(db: Session, username: str) -> Optional[DBUser]:
    return db.query(DBUser).filter(DBUser.username == username).first()

async def get_current_db_user_from_token(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> DBUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise credentials_exception
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
        # Initialize the session for a user the first time they make a request
        print(f"INFO: Initializing session state for user: {username}")
        initial_lollms_model = db_user.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
        
        session_llm_params = {
            "ctx_size": db_user.llm_ctx_size if db_user.llm_ctx_size is not None else LOLLMS_CLIENT_DEFAULTS.get("ctx_size"),
            "temperature": db_user.llm_temperature if db_user.llm_temperature is not None else LOLLMS_CLIENT_DEFAULTS.get("temperature"),
            "top_k": db_user.llm_top_k if db_user.llm_top_k is not None else LOLLMS_CLIENT_DEFAULTS.get("top_k"),
            "top_p": db_user.llm_top_p if db_user.llm_top_p is not None else LOLLMS_CLIENT_DEFAULTS.get("top_p"),
            "repeat_penalty": db_user.llm_repeat_penalty if db_user.llm_repeat_penalty is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
            "repeat_last_n": db_user.llm_repeat_last_n if db_user.llm_repeat_last_n is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n"),
            "put_thoughts_in_context": db_user.put_thoughts_in_context
        }
        
        user_sessions[username] = {
            "lollms_client": None,
            "discussion_manager": None, # Will be created on first use by get_user_discussion_manager
            "safe_store_instances": {},
            "active_vectorizer": db_user.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
            "lollms_model_name": initial_lollms_model,
            "llm_params": {k: v for k, v in session_llm_params.items() if v is not None},
            "active_personality_id": db_user.active_personality_id,
        }

    lc = get_user_lollms_client(username)
    ai_name_for_user = getattr(lc, "ai_name", LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant"))

    current_session_llm_params = user_sessions[username].get("llm_params", {})
    return UserAuthDetails(
        username=username, is_admin=db_user.is_admin, first_name=db_user.first_name,
        family_name=db_user.family_name, email=db_user.email, birth_date=db_user.birth_date,
        lollms_model_name=user_sessions[username]["lollms_model_name"],
        safe_store_vectorizer=user_sessions[username].get("active_vectorizer","st:all-MiniLM-L6-v2"),
        active_personality_id=user_sessions[username]["active_personality_id"],
        lollms_client_ai_name=ai_name_for_user,
        llm_ctx_size=current_session_llm_params.get("ctx_size"),
        llm_temperature=current_session_llm_params.get("temperature"),
        llm_top_k=current_session_llm_params.get("top_k"),
        llm_top_p=current_session_llm_params.get("top_p"),
        llm_repeat_penalty=current_session_llm_params.get("repeat_penalty"),
        llm_repeat_last_n=current_session_llm_params.get("repeat_last_n"),
        put_thoughts_in_context=current_session_llm_params.get("put_thoughts_in_context"),
        rag_top_k=db_user.rag_top_k, max_rag_len=db_user.max_rag_len,
        rag_n_hops=db_user.rag_n_hops, rag_min_sim_percent=db_user.rag_min_sim_percent,
        rag_use_graph=db_user.rag_use_graph, rag_graph_response_type=db_user.rag_graph_response_type
    )

def get_current_admin_user(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator privileges required.")
    return current_user

# --- Service Instance Helpers ---

def get_user_lollms_client(username: str) -> LollmsClient:
    session = user_sessions.get(username)
    if not session:
        raise HTTPException(status_code=500, detail="User session not found for LollmsClient.")
    
    if session.get("lollms_client") is None:
        model_name = session["lollms_model_name"]
        client_init_params = session.get("llm_params", {}).copy()
        
        # Add connection/default params from config
        client_init_params.update({
            "binding_name": LOLLMS_CLIENT_DEFAULTS.get("binding_name", "lollms"),
            "model_name": model_name,
            "host_address": LOLLMS_CLIENT_DEFAULTS.get("host_address", ""),
            "user_name": LOLLMS_CLIENT_DEFAULTS.get("user_name", "user"),
            "ai_name": LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant"),
        })

        # Add MCP tool servers
        servers_infos = {mcp["name"]: {"server_url": mcp["url"]} for mcp in DEFAULT_MCPS}
        db_for_mcp = next(get_db())
        try:
            user_db = db_for_mcp.query(DBUser).filter(DBUser.username == username).first()
            if user_db:
                for mcp in user_db.personal_mcps:
                    servers_infos[mcp.name] = {"server_url": mcp.url}
        finally:
            db_for_mcp.close()

        if servers_infos:
            client_init_params["mcp_binding_name"] = "remote_mcp"
            client_init_params["mcp_binding_config"] = {"servers_infos": servers_infos}
        
        try:
            lc = LollmsClient(**{k: v for k, v in client_init_params.items() if v is not None})
            session["lollms_client"] = lc
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not initialize LLM Client: {str(e)}")
            
    return cast(LollmsClient, session["lollms_client"])

def get_safe_store_instance(requesting_user_username: str, datastore_id: str, db: Session) -> safe_store.SafeStore:
    if safe_store is None:
        raise HTTPException(status_code=501, detail="SafeStore library not installed. RAG is disabled.")
    
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record:
        raise HTTPException(status_code=404, detail=f"DataStore '{datastore_id}' not found.")

    owner_username = datastore_record.owner.username
    requesting_user_record = db.query(DBUser).filter(DBUser.username == requesting_user_username).first()
    if not requesting_user_record:
        raise HTTPException(status_code=404, detail="Requesting user not found.")

    is_owner = (owner_username == requesting_user_username)
    link = db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id, shared_with_user_id=requesting_user_record.id).first()
    has_access = is_owner or (link and link.permission_level in ["read_query", "read_write"])
    
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied to this DataStore.")

    session = user_sessions.get(requesting_user_username)
    if not session:
        raise HTTPException(status_code=500, detail="User session not found for SafeStore access.")
    
    if datastore_id not in session.get("safe_store_instances", {}):
        ss_db_path = get_datastore_db_path(owner_username, datastore_id)
        try:
            ss_instance = safe_store.SafeStore(db_path=ss_db_path, name =datastore_record.name, description=datastore_record.description, encryption_key=SAFE_STORE_DEFAULTS["encryption_key"])
            session["safe_store_instances"][datastore_id] = ss_instance
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not initialize SafeStore for {datastore_id}: {str(e)}")
            
    return cast(safe_store.SafeStore, session["safe_store_instances"][datastore_id])


# --- User-specific Path Helpers ---

def get_user_data_root(username: str) -> Path:
    safe_username = secure_filename(username)
    path = APP_DATA_DIR / safe_username
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_user_discussion_path(username: str) -> Path:
    # This now points to the location of the OLD YAML files, for migration purposes.
    path = get_user_data_root(username) / "discussions"
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
    safe_datastore_id = secure_filename(datastore_id)
    return get_user_datastore_root_path(owner_username) / f"{safe_datastore_id}.db"
