import json
import traceback
import datetime
from pathlib import Path
from typing import Dict, Optional, Any, cast

from fastapi import HTTPException, Depends, status
from sqlalchemy.orm import Session, joinedload
from werkzeug.utils import secure_filename
from jose import jwt, JWTError

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.datastore import DataStore as DBDataStore, SharedDataStoreLink as DBSharedDataStoreLink
from backend.db.models.service import MCP as DBMCP
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.config import LLMBinding as DBLLMBinding
from lollms_client import LollmsClient
from backend.models import UserAuthDetails, TokenData
from backend.security import oauth2_scheme, SECRET_KEY, ALGORITHM, decode_main_access_token
from backend.config import (
    APP_DATA_DIR,
    SAFE_STORE_DEFAULTS,
    TEMP_UPLOADS_DIR_NAME,
    DISCUSSION_ASSETS_DIR_NAME,
    DATASTORES_DIR_NAME,
)
from backend.settings import settings
from backend.security import create_access_token

try:
    import safe_store
except ImportError:
    safe_store = None

user_sessions: Dict[str, Dict[str, Any]] = {}

def get_user_by_username(db: Session, username: str) -> Optional[DBUser]:
    return db.query(DBUser).filter(DBUser.username == username).first()

async def get_current_db_user_from_token(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> DBUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_main_access_token(token)
    if payload is None:
        raise credentials_exception
    
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    token_data = TokenData(username=username)
    
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
    if not db_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive.")

    username = db_user.username
    if username not in user_sessions:
        print(f"INFO: Re-initializing session for {username} on first request after server start.")
        session_llm_params = {
            "ctx_size": db_user.llm_ctx_size,
            "temperature": db_user.llm_temperature,
            "top_k": db_user.llm_top_k,
            "top_p": db_user.llm_top_p,
            "repeat_penalty": db_user.llm_repeat_penalty,
            "repeat_last_n": db_user.llm_repeat_last_n,
            "put_thoughts_in_context": db_user.put_thoughts_in_context
        }
        user_sessions[username] = {
            "lollms_clients": {},
            "safe_store_instances": {},
            "active_vectorizer": db_user.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
            "lollms_model_name": db_user.lollms_model_name,
            "llm_params": {k: v for k, v in session_llm_params.items() if v is not None},
            "active_personality_id": db_user.active_personality_id,
        }

    lc = get_user_lollms_client(username) 
    ai_name_for_user = getattr(lc, "ai_name", "assistant")
    current_session_llm_params = user_sessions[username].get("llm_params", {})

    is_api_service_enabled = settings.get("openai_api_service_enabled", False)

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
        receive_notification_emails=db_user.receive_notification_emails,
        is_searchable=db_user.is_searchable,
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
        fun_mode=db_user.fun_mode,
        show_token_counter=db_user.show_token_counter,
        openai_api_service_enabled=is_api_service_enabled
    )

def get_current_admin_user(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator privileges required.")
    return current_user

def load_mcps(username):
    session = user_sessions[username]
    servers_infos = {}
    db_for_mcp = next(get_db())
    try:
        system_mcps = db_for_mcp.query(DBMCP).filter(DBMCP.type == 'system').all()
        user_db = db_for_mcp.query(DBUser).filter(DBUser.username == username).first()
        if user_db:
            session["access_token"] = create_access_token(data={"sub": user_db.username})
            for mcp in system_mcps:
                if mcp.active:
                    if mcp.authentication_type=="lollms_chat_auth":
                        servers_infos[mcp.name] = {
                            "server_url": mcp.url,
                            "auth_config": {
                                "type": "bearer",
                                "token": session.get("access_token") 
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
                
            for mcp in user_db.personal_mcps:
                if mcp.active:
                    if mcp.authentication_type=="lollms_chat_auth":
                        servers_infos[mcp.name] = {
                            "server_url": mcp.url,
                            "auth_config": {
                                "type": "bearer",
                                "token": session.get("access_token") 
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


def invalidate_user_mcp_cache(username: str):
    if username in user_sessions and 'tools_cache' in user_sessions[username]:
        del user_sessions[username]['tools_cache']
        print(f"INFO: Invalidated tools cache for user: {username}")

def reload_lollms_client_mcp(username: str):
    invalidate_user_mcp_cache(username)
    lc = get_user_lollms_client(username)
    if hasattr(lc, 'mcp') and lc.mcp:
        lc.mcp = None
    
    servers_infos = load_mcps(username)
    
    if hasattr(lc, 'mcp_binding_manager'):
        lc.mcp = lc.mcp_binding_manager.create_binding(
            "remote_mcp",
            servers_infos=servers_infos
        )
    print(f"INFO: Completed MCP reload for user: {username}")

def get_user_lollms_client(username: str, binding_alias_override: Optional[str] = None) -> LollmsClient:
    session = user_sessions.get(username)
    if not session:
        raise HTTPException(status_code=500, detail="User session not found for LollmsClient.")
    
    if "lollms_clients" not in session:
        session["lollms_clients"] = {}

    db = next(get_db())
    try:
        binding_to_use = None
        
        target_binding_alias = binding_alias_override
        if not target_binding_alias:
            user_model_full = session.get("lollms_model_name")
            if user_model_full and '/' in user_model_full:
                target_binding_alias = user_model_full.split('/', 1)[0]

        if target_binding_alias:
            binding_to_use = db.query(DBLLMBinding).filter(DBLLMBinding.alias == target_binding_alias, DBLLMBinding.is_active == True).first()

        if not binding_to_use:
            binding_to_use = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).order_by(DBLLMBinding.id).first()
            if not binding_to_use:
                raise HTTPException(status_code=404, detail="No active LLM bindings are configured.")

        final_alias = binding_to_use.alias
        if final_alias in session["lollms_clients"]:
            return cast(LollmsClient, session["lollms_clients"][final_alias])
        
        user_model_full = session.get("lollms_model_name")
        selected_binding_alias, selected_model_name = (user_model_full.split('/', 1) + [None])[:2] if user_model_full else (None, None)

        if selected_binding_alias == final_alias:
            model_name_for_binding = selected_model_name
        else:
            model_name_for_binding = binding_to_use.default_model_name

        client_init_params = session.get("llm_params", {}).copy()
        
        force_mode = settings.get("force_model_mode", "disabled")
        if force_mode == "force_always":
            forced_model_full = settings.get("force_model_name")
            forced_binding_alias, forced_model_name = (forced_model_full.split('/', 1) + [None])[:2] if forced_model_full else (None, None)
            if forced_binding_alias == final_alias:
                model_name_for_binding = forced_model_name
            ctx_size_override = settings.get("force_context_size")
            if ctx_size_override is not None:
                client_init_params["ctx_size"] = ctx_size_override

        client_init_params.update({
            "binding_name": binding_to_use.name,
            "model_name": model_name_for_binding,
            "host_address": binding_to_use.host_address,
            "models_path": binding_to_use.models_path,
            "verify_ssl_certificate": binding_to_use.verify_ssl_certificate,
            "service_key": binding_to_use.service_key,
            "user_name": "user",
            "ai_name": "assistant",
        })

        servers_infos = load_mcps(username)
        if servers_infos:
            client_init_params["mcp_binding_name"] = "remote_mcp"
            client_init_params["mcp_binding_config"] = {"servers_infos": servers_infos}

        try:
            lc = LollmsClient(**{k: v for k, v in client_init_params.items() if v is not None})
            session["lollms_clients"][final_alias] = lc
            return lc
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not initialize LLM Client for binding '{final_alias}': {str(e)}")
    finally:
        db.close()

def build_lollms_client_from_params(
    username: str, 
    binding_alias: str, 
    model_name: str,
    llm_params: Optional[Dict[str, Any]] = None
) -> LollmsClient:
    session = user_sessions.get(username)
    if not session:
        raise HTTPException(status_code=500, detail="User session not found, cannot build LollmsClient.")

    db = next(get_db())
    try:
        binding_to_use = db.query(DBLLMBinding).filter(DBLLMBinding.alias == binding_alias, DBLLMBinding.is_active == True).first()
        if not binding_to_use:
            raise HTTPException(status_code=404, detail=f"Active binding with alias '{binding_alias}' not found.")

        client_init_params = session.get("llm_params", {}).copy()
        if llm_params:
            client_init_params.update(llm_params)
        
        client_init_params.update({
            "binding_name": binding_to_use.name,
            "model_name": model_name,
            "host_address": binding_to_use.host_address,
            "models_path": binding_to_use.models_path,
            "verify_ssl_certificate": binding_to_use.verify_ssl_certificate,
            "service_key": binding_to_use.service_key,
            "user_name": "user",
            "ai_name": "assistant",
        })

        servers_infos = load_mcps(username)
        if servers_infos:
            client_init_params["mcp_binding_name"] = "remote_mcp"
            client_init_params["mcp_binding_config"] = {"servers_infos": servers_infos}

        try:
            lc = LollmsClient(**{k: v for k, v in client_init_params.items() if v is not None})
            return lc
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not initialize ad-hoc LLM Client for binding '{binding_alias}': {str(e)}")
    finally:
        db.close()


def get_safe_store_instance(
    requesting_user_username: str,
    datastore_id: str,
    db: Session,
    permission_level: str = "read_query"
) -> safe_store.SafeStore:
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
    
    if not is_owner:
        link = db.query(DBSharedDataStoreLink).filter_by(
            datastore_id=datastore_id,
            shared_with_user_id=requesting_user_record.id
        ).first()

        if not link:
            raise HTTPException(status_code=403, detail="Access denied to this DataStore.")
        
        user_permission = link.permission_level
        
        permission_hierarchy = {
            "read_query": ["read_query", "read_write", "revectorize"],
            "read_write": ["read_write", "revectorize"],
            "revectorize": ["revectorize"]
        }

        if user_permission not in permission_hierarchy.get(permission_level, []):
            raise HTTPException(
                status_code=403,
                detail=f"You do not have the required '{permission_level}' permission for this DataStore."
            )

    session = user_sessions.get(requesting_user_username)
    if not session:
        raise HTTPException(status_code=500, detail="User session not found for SafeStore access.")
    
    if datastore_id not in session.get("safe_store_instances", {}):
        ss_db_path = get_datastore_db_path(owner_username, datastore_id)
        try:
            ss_instance = safe_store.SafeStore(
                                                db_path=ss_db_path, 
                                                name=datastore_record.name, 
                                                description=datastore_record.description, 
                                                encryption_key=SAFE_STORE_DEFAULTS["encryption_key"],
                                                cache_folder=SAFE_STORE_DEFAULTS.get("cache_folder","data/cache/safestore")
                                            )
            session["safe_store_instances"][datastore_id] = ss_instance
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not initialize SafeStore for {datastore_id}: {str(e)}")
            
    return cast(safe_store.SafeStore, session["safe_store_instances"][datastore_id])


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
