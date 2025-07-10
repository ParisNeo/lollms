# backend/session.py

# --- Standard Library Imports ---
import json
import traceback
import datetime
from pathlib import Path
from typing import Dict, Optional, Any, cast

# --- Third-Party Imports ---
from fastapi import HTTPException, Depends, status
from sqlalchemy.orm import Session, joinedload
from werkzeug.utils import secure_filename
from jose import jwt, JWTError

# --- Local Application Imports ---
from backend.database_setup import (
    User as DBUser,
    DataStore as DBDataStore,
    SharedDataStoreLink as DBSharedDataStoreLink,
    Personality as DBPersonality,
    MCP as DBMCP,
    get_db,
)
from lollms_client import LollmsClient
from backend.models import UserAuthDetails, TokenData
from backend.security import oauth2_scheme, SECRET_KEY, ALGORITHM
from backend.config import (
    APP_DATA_DIR,
    LOLLMS_CLIENT_DEFAULTS,
    SAFE_STORE_DEFAULTS,
    DEFAULT_MCPS,
    TEMP_UPLOADS_DIR_NAME,
    DISCUSSION_ASSETS_DIR_NAME,
    DATASTORES_DIR_NAME,
)
from backend.settings import settings
from backend.security import create_access_token
# --- safe_store is optional ---
try:
    import safe_store
except ImportError:
    safe_store = None

# --- Global User Session Management ---
user_sessions: Dict[str, Dict[str, Any]] = {}


# --- User & Authentication Helpers ---

def get_user_by_username(db: Session, username: str) -> Optional[DBUser]:
    """Fetches a user from the database by their username."""
    return db.query(DBUser).filter(DBUser.username == username).first()

async def get_current_db_user_from_token(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> DBUser:
    """
    Decodes the JWT token to get the username, fetches the user from the database,
    and updates their last activity timestamp.
    """
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
    
    now = datetime.datetime.now(datetime.timezone.utc)
    last_activity_aware = None
    
    if user.last_activity_at:
        if user.last_activity_at.tzinfo is None:
            last_activity_aware = user.last_activity_at.replace(tzinfo=datetime.timezone.utc)
        else:
            last_activity_aware = user.last_activity_at

    if last_activity_aware is None or (now - last_activity_aware) > datetime.timedelta(seconds=60):
        user.last_activity_at = now
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Warning: Could not update last_activity_at for user {user.username}: {e}")

    return user

def get_current_active_user(db_user: DBUser = Depends(get_current_db_user_from_token)) -> UserAuthDetails:
    """
    Takes a DB user record, ensures they are active, and constructs the detailed
    UserAuthDetails model with data from both the DB and the active session.
    """
    if not db_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive.")

    username = db_user.username
    if username not in user_sessions:
        print(f"INFO: Re-initializing session for {username} on first request after server start.")
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
            "lollms_client": None, "safe_store_instances": {},
            "active_vectorizer": db_user.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
            "lollms_model_name": db_user.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name"),
            "llm_params": {k: v for k, v in session_llm_params.items() if v is not None},
            "active_personality_id": db_user.active_personality_id,
        }

    lc = get_user_lollms_client(username)
    ai_name_for_user = getattr(lc, "ai_name", LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant"))
    current_session_llm_params = user_sessions[username].get("llm_params", {})

    # --- THIS IS THE FIX ---
    # The UserAuthDetails model is now populated with all required fields directly from the db_user object.
    return UserAuthDetails(
        id=db_user.id,
        username=username,
        is_admin=db_user.is_admin,
        is_active=db_user.is_active,
        icon=db_user.icon,
        first_name=db_user.first_name,
        family_name=db_user.family_name,
        email=db_user.email,
        birth_date=db_user.birth_date,
        receive_notification_emails=db_user.receive_notification_emails, # This was the missing field
        lollms_model_name=user_sessions[username].get("lollms_model_name"),
        safe_store_vectorizer=user_sessions[username].get("active_vectorizer"),
        active_personality_id=user_sessions[username].get("active_personality_id"),
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
        rag_graph_response_type=db_user.rag_graph_response_type,
        auto_title=db_user.auto_title,
        user_ui_level=db_user.user_ui_level,
        chat_active=db_user.chat_active,
        first_page=db_user.first_page,
        ai_response_language=db_user.ai_response_language,
        fun_mode=db_user.fun_mode
    )

def get_current_admin_user(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails:
    """Checks if the current active user has administrator privileges."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator privileges required.")
    return current_user


# --- Service Instance Helpers ---
def load_mcps(username):
    session = user_sessions[username]
    servers_infos = {}
    db_for_mcp = next(get_db())
    try:
        user_db = db_for_mcp.query(DBUser).filter(DBUser.username == username).first()
        if user_db:
            session["access_token"] = create_access_token(data={"sub": user_db.username})
            for mcp in user_db.personal_mcps:
                if mcp.active:
                    if mcp.authentication_type=="lollms_chat_auth":
                        servers_infos[mcp.name] = {
                            "server_url": mcp.url,
                            "auth_config": {
                                "type": "bearer",
                                "token": session.get("access_token") # ou None
                            }
                        }
                    elif mcp.authentication_type=="bearer":
                        servers_infos[mcp.name] = {
                            "server_url": mcp.url,
                            "auth_config": {
                                "type": "bearer",
                                "token": mcp.authentication_key
                            }
                        }
                    else:
                        servers_infos[mcp.name] = {
                            "server_url": mcp.url
                        }
                
    finally:
        db_for_mcp.close()
    return servers_infos

def get_user_lollms_client(username: str) -> LollmsClient:
    session = user_sessions.get(username)
    if not session:
        raise HTTPException(status_code=500, detail="User session not found for LollmsClient.")
    
    if session.get("lollms_client") is None:
        # Check for admin-forced model settings
        force_mode = settings.get("force_model_mode", "disabled")
        if force_mode == "force_always":
            model_name = settings.get("force_model_name")
            ctx_size_override = settings.get("force_context_size")
            if not model_name:
                print("WARNING: Admin model forcing is enabled, but no model name is set. Falling back to user/default.")
                model_name = session.get("lollms_model_name", settings.get("default_lollms_model_name"))
            
            # Update session params for this session only
            session_params = session.get("llm_params", {}).copy()
            if ctx_size_override is not None:
                session_params["ctx_size"] = ctx_size_override
            session["llm_params"] = session_params
        else:
            model_name = session.get("lollms_model_name", settings.get("default_lollms_model_name"))

        client_init_params = session.get("llm_params", {}).copy()
        
        client_init_params.update({
            "binding_name": LOLLMS_CLIENT_DEFAULTS.get("binding_name", "lollms"),
            "model_name": model_name,
            "host_address": LOLLMS_CLIENT_DEFAULTS.get("host_address", ""),
            "user_name": LOLLMS_CLIENT_DEFAULTS.get("user_name", "user"),
            "ai_name": LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant"),
            "service_key": LOLLMS_CLIENT_DEFAULTS.get("service_key"),
            "verify_ssl_certificate": LOLLMS_CLIENT_DEFAULTS.get("verify_ssl_certificate", True)
        })

        servers_infos=load_mcps(username)
        
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