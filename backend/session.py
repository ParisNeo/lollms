# backend/session.py
import json
import traceback
import datetime
from pathlib import Path
from typing import Dict, Optional, Any, cast

from fastapi import HTTPException, Depends, status
from sqlalchemy.orm import Session, joinedload
from werkzeug.utils import secure_filename
from jose import jwt, JWTError
from ascii_colors import trace_exception, ASCIIColors

from backend.db import get_db
from backend.db.models.service import MCP as DBMCP, App as DBApp
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
    DM_ASSETS_DIR_NAME,
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
    
    user = db.query(DBUser).filter(DBUser.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    
    # --- CORRECTED LOGIC START ---
    # Update last activity timestamp. The commit will be handled by the endpoint's session.
    now = datetime.datetime.now(datetime.timezone.utc)
    last_activity_aware = user.last_activity_at.replace(tzinfo=datetime.timezone.utc) if user.last_activity_at and user.last_activity_at.tzinfo is None else user.last_activity_at

    if not last_activity_aware or (now - last_activity_aware) > datetime.timedelta(seconds=60):
        user.last_activity_at = now
        # DO NOT COMMIT HERE. The main endpoint will handle the commit.
    
    # The complex logic for 'first_login_done' has been moved to the login endpoint,
    # which is a safer place for write operations.
    # --- CORRECTED LOGIC END ---

    return user

def get_current_active_user(db_user: DBUser = Depends(get_current_db_user_from_token)) -> UserAuthDetails:
    if not db_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive.")

    username = db_user.username
    db = next(get_db())
    try:
        if username not in user_sessions:
            print(f"INFO: Re-initializing session for {username} on first request after server start.")
            session_llm_params = {
                "ctx_size": db_user.llm_ctx_size, "temperature": db_user.llm_temperature,
                "top_k": db_user.llm_top_k, "top_p": db_user.llm_top_p,
                "repeat_penalty": db_user.llm_repeat_penalty, "repeat_last_n": db_user.llm_repeat_last_n,
                "put_thoughts_in_context": db_user.put_thoughts_in_context
            }
            user_sessions[username] = {
                "lollms_clients": {}, "safe_store_instances": {}, "discussions": {},
                "active_vectorizer": db_user.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
                "lollms_model_name": db_user.lollms_model_name,
                "llm_params": {k: v for k, v in session_llm_params.items() if v is not None},
                "active_personality_id": db_user.active_personality_id,
            }

        # --- NEW: Logic to determine if settings are overridden ---
        user_model_full = user_sessions[username].get("lollms_model_name")
        llm_settings_overridden = False
        effective_llm_params = {
            "llm_ctx_size": user_sessions[username].get("llm_params", {}).get("ctx_size", db_user.llm_ctx_size),
            "llm_temperature": user_sessions[username].get("llm_params", {}).get("temperature", db_user.llm_temperature),
            "llm_top_k": user_sessions[username].get("llm_params", {}).get("top_k", db_user.llm_top_k),
            "llm_top_p": user_sessions[username].get("llm_params", {}).get("top_p", db_user.llm_top_p),
            "llm_repeat_penalty": user_sessions[username].get("llm_params", {}).get("repeat_penalty", db_user.llm_repeat_penalty),
            "llm_repeat_last_n": user_sessions[username].get("llm_params", {}).get("repeat_last_n", db_user.llm_repeat_last_n),
            "put_thoughts_in_context": user_sessions[username].get("llm_params", {}).get("put_thoughts_in_context", db_user.put_thoughts_in_context)
        }

        if user_model_full and '/' in user_model_full:
            binding_alias, model_name = user_model_full.split('/', 1)
            binding = db.query(DBLLMBinding).filter(DBLLMBinding.alias == binding_alias).first()
            if binding and binding.model_aliases:
                if isinstance(binding.model_aliases,str):
                    try:
                        binding.model_aliases = json.loads(binding.model_aliases)
                    except Exception as e:
                        trace_exception(e)
                        binding.model_aliases= {}
                alias_info = binding.model_aliases.get(model_name)
                if alias_info and not alias_info.get('allow_parameters_override', True):
                    llm_settings_overridden = True
                    # Override the effective params with values from the alias
                    param_map = {"ctx_size": "llm_ctx_size", "temperature": "llm_temperature", "top_k": "llm_top_k", "top_p": "llm_top_p", "repeat_penalty": "llm_repeat_penalty", "repeat_last_n": "llm_repeat_last_n"}
                    for alias_key, user_key in param_map.items():
                        if alias_key in alias_info and alias_info[alias_key] is not None:
                            effective_llm_params[user_key] = alias_info[alias_key]
        # --- END NEW ---
        
        lc = get_user_lollms_client(username)
        ai_name_for_user = getattr(lc, "ai_name", "assistant")
        is_api_service_enabled = settings.get("openai_api_service_enabled", False)
        is_api_require_key = settings.get("openai_api_require_key", True)
        is_ollama_service_enabled = settings.get("ollama_service_enabled", False)
        is_ollama_require_key = settings.get("ollama_require_key", True)

        return UserAuthDetails(
            id=db_user.id, username=username, is_admin=db_user.is_admin, is_moderator=(db_user.is_admin or db_user.is_moderator), is_active=db_user.is_active,
            icon=db_user.icon, first_name=db_user.first_name, family_name=db_user.family_name, email=db_user.email,
            birth_date=db_user.birth_date, receive_notification_emails=db_user.receive_notification_emails,
            is_searchable=db_user.is_searchable, first_login_done=db_user.first_login_done,
            data_zone=db_user.data_zone, memory=db_user.memory,
            lollms_model_name=user_model_full,
            safe_store_vectorizer=user_sessions[username].get("active_vectorizer"),
            active_personality_id=user_sessions[username].get("active_personality_id"),
            lollms_client_ai_name=ai_name_for_user,
            **effective_llm_params,
            rag_top_k=db_user.rag_top_k, max_rag_len=db_user.max_rag_len, rag_n_hops=db_user.rag_n_hops,
            rag_min_sim_percent=db_user.rag_min_sim_percent, rag_use_graph=db_user.rag_use_graph,
            rag_graph_response_type=db_user.rag_graph_response_type, auto_title=db_user.auto_title,
            user_ui_level=db_user.user_ui_level, chat_active=db_user.chat_active, first_page=db_user.first_page,
            ai_response_language=db_user.ai_response_language, fun_mode=db_user.fun_mode,
            show_token_counter=db_user.show_token_counter, 
            openai_api_service_enabled=is_api_service_enabled,
            openai_api_require_key=is_api_require_key,
            ollama_service_enabled=is_ollama_service_enabled,
            ollama_require_key=is_ollama_require_key,
            llm_settings_overridden=llm_settings_overridden
        )
    finally:
        db.close()

def get_current_admin_user(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator privileges required.")
    return current_user

def load_mcps(username):
    session = user_sessions[username]
    servers_infos = {}
    db_for_mcp = next(get_db())
    try:
        
        app_mcps = db_for_mcp.query(DBApp).options(joinedload(DBApp.owner)).filter(DBApp.app_metadata['item_type'].as_string() == 'mcp').all()
        system_mcps = db_for_mcp.query(DBMCP).filter(DBMCP.type == 'system', DBMCP.active == True).all()
        user_db = db_for_mcp.query(DBUser).filter(DBUser.username == username).first()
        
        personal_mcps = []
        if user_db:
            session["access_token"] = create_access_token(data={"sub": user_db.username})
            personal_mcps = [mcp for mcp in user_db.personal_mcps if mcp.active]

        all_active_mcps = app_mcps + system_mcps + personal_mcps

        for mcp in all_active_mcps:
            try:
                mcp_base_url = mcp.url.rstrip('/')
                if not mcp_base_url.endswith('/mcp'):
                    mcp_full_url = f"{mcp_base_url}/mcp"
                else:
                    mcp_full_url = mcp_base_url
                
                server_info = {"server_url": mcp_full_url}
                
                if mcp.authentication_type == "lollms_chat_auth":
                    server_info["auth_config"] = { "type": "bearer", "token": session.get("access_token") }
                elif mcp.authentication_type == "bearer":
                    server_info["auth_config"] = { "type": "bearer", "token": mcp.authentication_key }

                servers_infos[mcp.name] = server_info
            except Exception as e:
                trace_exception(e)
    finally:
        db_for_mcp.close()
    return servers_infos


def invalidate_user_mcp_cache(username: str):
    if username in user_sessions and 'tools_cache' in user_sessions[username]:
        del user_sessions[username]['tools_cache']
        print(f"INFO: Invalidated tools cache for user: {username}")

def reload_lollms_client_mcp(username: str):
    """
    Invalidates the MCP tools cache and the lollms_client instance for a user,
    forcing a full reload and tool re-discovery on the next request.
    """
    if username in user_sessions:
        session = user_sessions[username]
        # Clear the cached list of discovered tools
        if 'tools_cache' in session:
            del session['tools_cache']
            print(f"INFO: Invalidated tools cache for user: {username}")
        
        # Clear any cached lollms_client instances that might hold old MCP connections.
        # This forces a full reconnection on the next get_user_lollms_client call.
        if "lollms_clients" in session:
            session["lollms_clients"] = {}
            print(f"INFO: Invalidated all lollms_client instances for user: {username}")

Loaded_registry={

}

def get_user_lollms_client(username: str, binding_alias_override: Optional[str] = None) -> LollmsClient:
    if not (username, binding_alias_override) in Loaded_registry:
        Loaded_registry[(username, binding_alias_override)] = build_lollms_client_from_params(username, binding_alias_override)
    return Loaded_registry[(username, binding_alias_override)]


def build_lollms_client_from_params(
    username: str, 
    binding_alias: Optional[str] = None, 
    model_name: Optional[str] = None,
    llm_params: Optional[Dict[str, Any]] = None
) -> LollmsClient:
    session = user_sessions.get(username)
    if not session:
        raise HTTPException(status_code=500, detail="User session not found, cannot build LollmsClient.")

    db = next(get_db())
    try:
        user_db = db.query(DBUser).filter(DBUser.username == username).first()
        binding_to_use = None
        
        target_binding_alias = binding_alias
        user_model_full = session.get("lollms_model_name")
        if not target_binding_alias and user_model_full and '/' in user_model_full:
            target_binding_alias = user_model_full.split('/', 1)[0]

        if target_binding_alias:
            binding_to_use = db.query(DBLLMBinding).filter(DBLLMBinding.alias == target_binding_alias, DBLLMBinding.is_active == True).first()

        if not binding_to_use:
            binding_to_use = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).order_by(DBLLMBinding.id).first()
            if not binding_to_use:
                raise HTTPException(status_code=404, detail="No active LLM bindings are configured.")

        final_alias = binding_to_use.alias
        if not model_name and final_alias in session.get("lollms_clients", {}):
            return cast(LollmsClient, session["lollms_clients"][final_alias])
        
        model_name_for_binding = model_name
        if not model_name_for_binding:
            selected_binding_alias, selected_model_name = (user_model_full.split('/', 1) + [None])[:2] if user_model_full else (None, None)
            model_name_for_binding = selected_model_name if selected_binding_alias == final_alias else binding_to_use.default_model_name

        # Start with parameters from binding's config field
        llm_init_params = { **binding_to_use.config }
        
        user_saved_params = {
            "ctx_size": user_db.llm_ctx_size, "temperature": user_db.llm_temperature,
            "top_k": user_db.llm_top_k, "top_p": user_db.llm_top_p,
            "repeat_penalty": user_db.llm_repeat_penalty, "repeat_last_n": user_db.llm_repeat_last_n,
            "put_thoughts_in_context": user_db.put_thoughts_in_context
        }
        user_session_params = session.get("llm_params", {})
        
        final_user_params = {**{k:v for k,v in user_saved_params.items() if v is not None}, **user_session_params}
        if llm_params:
            final_user_params.update(llm_params)

        model_aliases = binding_to_use.model_aliases or {}
        if isinstance(model_aliases,str):
            try:
                model_aliases = json.loads(model_aliases)
            except Exception as e:
                trace_exception(e)
                model_aliases= {}
        alias_info = model_aliases.get(model_name_for_binding)

        if alias_info:
            override_allowed = alias_info.get('allow_parameters_override', True)
            alias_params = {k: v for k, v in alias_info.items() if v is not None}

            if override_allowed:
                # User/session parameters can override alias defaults
                llm_init_params.update({**alias_params, **final_user_params})
            else:
                # Alias parameters override user/session
                llm_init_params.update(final_user_params) # Apply user defaults first
                llm_init_params.update(alias_params) # Then override with alias parameters
            
            if alias_info.get('ctx_size_locked', False) and 'ctx_size' in alias_info:
                llm_init_params["ctx_size"] = alias_info['ctx_size']
        else:
            llm_init_params.update(final_user_params)

        llm_init_params["model_name"] = model_name_for_binding
        client_init_params = {"llm_binding_name": binding_to_use.name, "llm_binding_config": llm_init_params}    
        
        servers_infos = load_mcps(username)
        if servers_infos:
            client_init_params["mcp_binding_name"] = "remote_mcp"
            client_init_params["mcp_binding_config"] = {"servers_infos": servers_infos}

        try:
            lc = LollmsClient(**{k: v for k, v in client_init_params.items() if v is not None})
            if not model_name: # Only cache the user's default client
                session.setdefault("lollms_clients", {})[final_alias] = lc
            return lc
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not initialize LLM Client for binding '{final_alias}': {str(e)}")
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

def get_user_dm_assets_path(username: str) -> Path:
    path = get_user_data_root(username) / DM_ASSETS_DIR_NAME
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