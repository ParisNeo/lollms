# [UPDATE] backend/session.py
import json
import traceback
import datetime
import threading
from pathlib import Path
from typing import Dict, Optional, Any, cast

from fastapi import HTTPException, Depends, status
from sqlalchemy.orm import Session, joinedload, object_session
from werkzeug.utils import secure_filename
from ascii_colors import trace_exception, ASCIIColors

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.service import MCP as DBMCP, App as DBApp
from backend.db.models.datastore import DataStore as DBDataStore, SharedDataStoreLink as DBSharedDataStoreLink
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.config import LLMBinding as DBLLMBinding, TTIBinding as DBTTIBinding, TTSBinding as DBTTSBinding, STTBinding as DBSTTBinding
from lollms_client import LollmsClient
from backend.models.user import UserAuthDetails
from backend.models.auth import TokenData
from backend.security import oauth2_scheme, decode_main_access_token
from backend.config import (
    APP_DATA_DIR,
    SAFE_STORE_DEFAULTS,
    USERS_DIR_NAME,
    TEMP_UPLOADS_DIR_NAME,
    DISCUSSION_ASSETS_DIR_NAME,
    DM_ASSETS_DIR_NAME,
    DATASTORES_DIR_NAME,
    VOICES_DIR_NAME,
    IMAGES_DIR_NAME,
    NOTEBOOK_ASSETS_DIR_NAME
)
from backend.settings import settings
from backend.security import create_access_token

try:
    import safe_store
except ImportError:
    safe_store = None

# Global In-Memory Session Cache
user_sessions: Dict[str, Dict[str, Any]] = {}

# Locks to prevent race conditions during concurrent requests
_session_init_lock = threading.Lock()
_client_build_locks: Dict[str, threading.Lock] = {}
_client_build_locks_lock = threading.Lock()

# helper function
def ensure_bool(value, default=False):
    """
    Ensures a value is a boolean.  Attempts to parse strings as booleans.
    """
    if isinstance(value, bool):
        return value
    elif isinstance(value, str):
        try:
            return value.lower() in ("true", "yes", "1")
        except:
            return default
    else:
        return default

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
    
    now = datetime.datetime.now(datetime.timezone.utc)
    last_activity_aware = user.last_activity_at.replace(tzinfo=datetime.timezone.utc) if user.last_activity_at and user.last_activity_at.tzinfo is None else user.last_activity_at

    if not last_activity_aware or (now - last_activity_aware) > datetime.timedelta(seconds=60):
        user.last_activity_at = now
    
    return user

def get_current_active_user(db_user: DBUser = Depends(get_current_db_user_from_token)) -> UserAuthDetails:
    if not db_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive.")

    username = db_user.username
    db = object_session(db_user)
    db_was_created = False
    if not db:
        # print(f"WARNING: db_user object for '{username}' was detached. Getting a new session.")
        db = next(get_db())
        db_user = db.merge(db_user)
        db_was_created = True

    try:
        # Enforce Expert UI for admins
        if db_user.is_admin and db_user.user_ui_level != 4:
            # print(f"INFO: Correcting UI level for admin user '{db_user.username}' to Expert (4).")
            db_user.user_ui_level = 4
            try:
                db.commit()
                db.refresh(db_user)
            except Exception as e:
                print(f"ERROR: Could not persist corrected UI level for admin '{db_user.username}'. Error: {e}")
                db.rollback()

        # Initialize session if needed (THREAD-SAFE)
        if username not in user_sessions:
            with _session_init_lock:
                if username not in user_sessions: # Double check inside lock
                    print(f"INFO: Re-initializing session for {username} on first request after server start.")
                    session_llm_params = {
                        "ctx_size": db_user.llm_ctx_size, "temperature": db_user.llm_temperature,
                        "top_k": db_user.llm_top_k, "top_p": db_user.llm_top_p,
                        "repeat_penalty": db_user.llm_repeat_penalty, "repeat_last_n": db_user.llm_repeat_last_n,
                        "put_thoughts_in_context": db_user.put_thoughts_in_context
                    }
                    user_sessions[username] = {
                        "safe_store_instances": {}, "discussions": {},
                        "active_vectorizer": db_user.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
                        "lollms_model_name": db_user.lollms_model_name,
                        "llm_params": {k: v for k, v in session_llm_params.items() if v is not None},
                        "active_personality_id": db_user.active_personality_id,
                    }

        user_model_full = db_user.lollms_model_name
        session = user_sessions[username]
        
        # Sync model name if changed in DB
        if session.get("lollms_model_name") != user_model_full:
            session["lollms_model_name"] = user_model_full
            # print(f"INFO: Synced session model name for '{username}' to '{user_model_full}'.")

        llm_settings_overridden = False
        effective_llm_params = {
            "llm_ctx_size": db_user.llm_ctx_size,
            "llm_temperature": db_user.llm_temperature,
            "llm_top_k": db_user.llm_top_k,
            "llm_top_p": db_user.llm_top_p,
            "llm_repeat_penalty": db_user.llm_repeat_penalty,
            "llm_repeat_last_n": db_user.llm_repeat_last_n,
            "put_thoughts_in_context": db_user.put_thoughts_in_context,
            "reasoning_activation": db_user.reasoning_activation,
            "reasoning_effort": db_user.reasoning_effort,
            "reasoning_summary": db_user.reasoning_summary
        }

        # --- Enforce Context Size Lock and other alias overrides ---
        ctx_size_to_enforce = None
        if user_model_full and '/' in user_model_full:
            binding_alias, model_name = user_model_full.split('/', 1)
            binding = db.query(DBLLMBinding).filter(DBLLMBinding.alias == binding_alias).first()
            if binding and binding.model_aliases:
                if isinstance(binding.model_aliases, str):
                    try:
                        binding.model_aliases = json.loads(binding.model_aliases)
                    except Exception as e:
                        trace_exception(e)
                        binding.model_aliases = {}
                
                alias_info = binding.model_aliases.get(model_name)
                
                if alias_info and alias_info.get('ctx_size_locked', False) and 'ctx_size' in alias_info:
                    ctx_size_to_enforce = alias_info['ctx_size']
                
                if alias_info and not alias_info.get('allow_parameters_override', True):
                    llm_settings_overridden = True
                    param_map = {"ctx_size": "llm_ctx_size", "temperature": "llm_temperature", "top_k": "llm_top_k", "top_p": "llm_top_p", "repeat_penalty": "llm_repeat_penalty", "repeat_last_n": "llm_repeat_last_n", "reasoning_activation": "reasoning_activation", "reasoning_effort": "reasoning_effort", "reasoning_summary": "reasoning_summary"}
                    for alias_key, user_key in param_map.items():
                        if alias_key in alias_info and alias_info[alias_key] is not None:
                            effective_llm_params[user_key] = alias_info[alias_key]
                            if alias_key == 'ctx_size':
                                ctx_size_to_enforce = alias_info['ctx_size']

        if ctx_size_to_enforce is not None:
            effective_llm_params["llm_ctx_size"] = ctx_size_to_enforce
            if db_user.llm_ctx_size != ctx_size_to_enforce:
                db_user.llm_ctx_size = ctx_size_to_enforce
                try:
                    db.commit()
                    db.refresh(db_user)
                except Exception as e:
                    db.rollback()
            
            session_params = user_sessions[username].get("llm_params", {})
            if session_params.get("ctx_size") != ctx_size_to_enforce:
                session_params["ctx_size"] = ctx_size_to_enforce
                user_sessions[username]["llm_params"] = session_params
                user_sessions[username]["lollms_clients_cache"] = {}

        lc = get_user_lollms_client(username)
        ai_name_for_user = getattr(lc, "ai_name", "assistant")
        
        # Helper bools
        is_api_service_enabled = ensure_bool(settings.get("openai_api_service_enabled", False), False)
        is_api_require_key = ensure_bool(settings.get("openai_api_require_key", True), True)
        is_ollama_service_enabled = ensure_bool(settings.get("ollama_service_enabled", False), False)
        is_ollama_require_key = ensure_bool(settings.get("ollama_require_key", True), True)
        latex_builder_enabled = ensure_bool(settings.get("latex_builder_enabled", False), False)
        allow_user_chunking_config = ensure_bool(settings.get("allow_user_chunking_config", True), True)
        default_chunk_size = settings.get("default_chunk_size", 2048)
        default_chunk_overlap = settings.get("default_chunk_overlap", 256)

        return UserAuthDetails(
            id=db_user.id, username=username, is_admin=db_user.is_admin, is_moderator=(db_user.is_admin or db_user.is_moderator), is_active=db_user.is_active,
            icon=db_user.icon, first_name=db_user.first_name, family_name=db_user.family_name, email=db_user.email,
            birth_date=db_user.birth_date, receive_notification_emails=db_user.receive_notification_emails,
            is_searchable=db_user.is_searchable, first_login_done=db_user.first_login_done,
            data_zone=db_user.data_zone,
            lollms_model_name=db_user.lollms_model_name,
            tti_binding_model_name=db_user.tti_binding_model_name,
            iti_binding_model_name=db_user.iti_binding_model_name,
            tti_models_config=db_user.tti_models_config,
            tts_binding_model_name=db_user.tts_binding_model_name,
            tts_models_config=db_user.tts_models_config,
            stt_binding_model_name=db_user.stt_binding_model_name,
            stt_models_config=db_user.stt_models_config,
            safe_store_vectorizer=user_sessions[username].get("active_vectorizer"),
            active_personality_id=user_sessions[username].get("active_personality_id"),
            active_voice_id=db_user.active_voice_id,
            last_discussion_id=db_user.last_discussion_id,
            lollms_client_ai_name=ai_name_for_user,
            **effective_llm_params,
            rag_top_k=db_user.rag_top_k, 
            max_rag_len=db_user.max_rag_len, 
            rag_n_hops=db_user.rag_n_hops,
            rag_min_sim_percent=db_user.rag_min_sim_percent, 
            rag_use_graph=db_user.rag_use_graph,
            rag_graph_response_type=db_user.rag_graph_response_type, 
            default_rag_chunk_size=db_user.default_rag_chunk_size,
            default_rag_chunk_overlap=db_user.default_rag_chunk_overlap,
            default_rag_metadata_mode=db_user.default_rag_metadata_mode,
            auto_title=db_user.auto_title,
            user_ui_level=db_user.user_ui_level, chat_active=db_user.chat_active, first_page=db_user.first_page,
            ai_response_language=db_user.ai_response_language,
            force_ai_response_language=db_user.force_ai_response_language,
            fun_mode=db_user.fun_mode,
            show_token_counter=db_user.show_token_counter, 
            openai_api_service_enabled=is_api_service_enabled,
            openai_api_require_key=is_api_require_key,
            ollama_service_enabled=is_ollama_service_enabled,
            ollama_require_key=is_ollama_require_key,
            include_memory_date_in_context=db_user.include_memory_date_in_context,
            llm_settings_overridden=llm_settings_overridden,
            tti_model_forced=False,
            iti_model_forced=False,
            latex_builder_enabled=latex_builder_enabled,
            coding_style_constraints=db_user.coding_style_constraints,
            programming_language_preferences=db_user.programming_language_preferences,
            tell_llm_os=db_user.tell_llm_os,
            share_dynamic_info_with_llm=db_user.share_dynamic_info_with_llm,
            message_font_size=db_user.message_font_size,
            allow_user_chunking_config=allow_user_chunking_config,
            default_chunk_size=default_chunk_size,
            default_chunk_overlap=default_chunk_overlap,
            image_studio_prompt=db_user.image_studio_prompt,
            image_studio_negative_prompt=db_user.image_studio_negative_prompt,
            image_studio_image_size=db_user.image_studio_image_size,
            image_studio_n_images=db_user.image_studio_n_images,
            image_studio_seed=db_user.image_studio_seed,
            image_studio_generation_params=db_user.image_studio_generation_params,
            image_generation_enabled=db_user.image_generation_enabled,
            image_annotation_enabled=db_user.image_annotation_enabled,
            note_generation_enabled=db_user.note_generation_enabled,
            preferred_name=db_user.preferred_name,
            user_personal_info=db_user.user_personal_info,
            share_personal_info_with_llm=db_user.share_personal_info_with_llm
        )
    finally:
        if db_was_created:
            db.close()
         
def get_current_admin_user(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator privileges required.")
    return current_user

def load_mcps(username):
    session = user_sessions.get(username)
    is_temp_session = not session
    
    servers_infos = {}
    db_for_mcp = next(get_db())
    try:
        app_mcps = db_for_mcp.query(DBApp).options(joinedload(DBApp.owner)).filter(DBApp.app_metadata['item_type'].as_string() == 'mcp').all()
        system_mcps = db_for_mcp.query(DBMCP).filter(DBMCP.type == 'system', DBMCP.active == True).all()
        user_db = db_for_mcp.query(DBUser).filter(DBUser.username == username).first()
        
        personal_mcps = []
        access_token = None
        
        if user_db:
            if session and not is_temp_session:
                session["access_token"] = create_access_token(data={"sub": user_db.username})
                access_token = session.get("access_token")
            else:
                access_token = create_access_token(data={"sub": user_db.username})
            
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
                
                if mcp.authentication_type == "lollms_chat_auth" and access_token:
                    server_info["auth_config"] = { "type": "bearer", "token": access_token }
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
    if username in user_sessions:
        session = user_sessions[username]
        if 'tools_cache' in session:
            del session['tools_cache']
            print(f"INFO: Invalidated tools cache for user: {username}")
        
        if 'servers_infos' in session:
            del session['servers_infos']
            print(f"INFO: Invalidated MCP servers cache for user: {username}")


def get_user_lollms_client(username: str, binding_alias_override: Optional[str] = None) -> LollmsClient:
    session = user_sessions.get(username)
    if not session:
        # print(f"INFO: No active session for '{username}' in get_user_lollms_client. Building temporary client.")
        return build_lollms_client_from_params(username, binding_alias_override)

    clients_cache = session.setdefault("lollms_clients_cache", {})
    
    # Determine cache key: 'default' for user's main model, or the specific override alias
    cache_key = binding_alias_override or "default"

    # Fast path check before locking
    if cache_key in clients_cache:
        # print(f"DEBUG: Returning cached client for user '{username}' with key '{cache_key}'.")
        return clients_cache[cache_key]
    
    # --- THREAD LOCKING START ---
    # Ensure a lock exists for this specific user+key combination
    lock_key = f"{username}_{cache_key}"
    
    with _client_build_locks_lock:
        if lock_key not in _client_build_locks:
            _client_build_locks[lock_key] = threading.Lock()
        lock = _client_build_locks[lock_key]

    with lock:
        # Double-check inside lock in case another thread finished building while we waited
        if cache_key in clients_cache:
            return clients_cache[cache_key]

        print(f"INFO: LollmsClient not in cache for user '{username}' with key '{cache_key}'. Building new client.")
        client = build_lollms_client_from_params(username, binding_alias_override)
        clients_cache[cache_key] = client
        return client
    # --- THREAD LOCKING END ---


def build_lollms_client_from_params(
    username: str, 
    binding_alias: Optional[str] = None, 
    model_name: Optional[str] = None,
    llm_params: Optional[Dict[str, Any]] = None,
    tti_binding_alias: Optional[str] = None,
    tti_model_name: Optional[str] = None,
    tti_params: Optional[Dict[str, Any]] = None,
    tts_binding_alias: Optional[str] = None,
    tts_model_name: Optional[str] = None,
    tts_params: Optional[Dict[str, Any]] = None,
    stt_binding_alias: Optional[str] = None,
    stt_model_name: Optional[str] = None,
    stt_params: Optional[Dict[str, Any]] = None,
    load_llm: bool = True,
    load_tti: bool = False,
    load_tts: bool = False,
    load_stt: bool = False
) -> LollmsClient:
    session = user_sessions.get(username)
    
    is_temp_session = False
    if not session:
        is_temp_session = True
        session = {
            "safe_store_instances": {},
            "discussions": {},
            "llm_params": {},
        }
        # print(f"INFO: No active session for '{username}'. Creating temporary client context.")

    db = next(get_db())
    try:
        user_db = db.query(DBUser).filter(DBUser.username == username).first()
        if not user_db:
             raise HTTPException(status_code=404, detail=f"User '{username}' not found.")

        # Validate selected models against active bindings before building client
        if load_llm and user_db.lollms_model_name and '/' in user_db.lollms_model_name:
            binding_alias_check, _ = user_db.lollms_model_name.split('/', 1)
            is_active = db.query(DBLLMBinding.id).filter(DBLLMBinding.alias == binding_alias_check, DBLLMBinding.is_active == True).first()
            if not is_active:
                user_db.lollms_model_name = None

        if load_tti and user_db.tti_binding_model_name and '/' in user_db.tti_binding_model_name:
            binding_alias_check, _ = user_db.tti_binding_model_name.split('/', 1)
            is_active = db.query(DBTTIBinding.id).filter(DBTTIBinding.alias == binding_alias_check, DBTTIBinding.is_active == True).first()
            if not is_active:
                user_db.tti_binding_model_name = None

        if load_tti and user_db.iti_binding_model_name and '/' in user_db.iti_binding_model_name:
            binding_alias_check, _ = user_db.iti_binding_model_name.split('/', 1)
            is_active = db.query(DBTTIBinding.id).filter(DBTTIBinding.alias == binding_alias_check, DBTTIBinding.is_active == True).first()
            if not is_active:
                user_db.iti_binding_model_name = None

        if load_tts and user_db.tts_binding_model_name and '/' in user_db.tts_binding_model_name:
            binding_alias_check, _ = user_db.tts_binding_model_name.split('/', 1)
            is_active = db.query(DBTTSBinding.id).filter(DBTTSBinding.alias == binding_alias_check, DBTTSBinding.is_active == True).first()
            if not is_active:
                user_db.tts_binding_model_name = None
                
        if load_stt and user_db.stt_binding_model_name and '/' in user_db.stt_binding_model_name:
            binding_alias_check, _ = user_db.stt_binding_model_name.split('/', 1)
            is_active = db.query(DBSTTBinding.id).filter(DBSTTBinding.alias == binding_alias_check, DBSTTBinding.is_active == True).first()
            if not is_active:
                user_db.stt_binding_model_name = None
        
        client_init_params = {
            "load_llm": load_llm,
            "load_tti": load_tti,
            "load_tts": load_tts,
            "load_stt": load_stt,
        }
        
        binding_to_use = None
        
        # Determine the model name from session or DB
        user_model_full = session.get("lollms_model_name") or user_db.lollms_model_name

        if load_llm:
            if user_model_full:
                target_binding_alias = binding_alias
                if not target_binding_alias and '/' in user_model_full:
                    target_binding_alias = user_model_full.split('/', 1)[0]

                if target_binding_alias:
                    binding_to_use = db.query(DBLLMBinding).filter(DBLLMBinding.alias == target_binding_alias, DBLLMBinding.is_active == True).first()

            if not binding_to_use:
                binding_to_use = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).order_by(DBLLMBinding.id).first()
            
            if binding_to_use:            
                final_alias = binding_to_use.alias
                model_name_for_binding = model_name
                if not model_name_for_binding:
                    selected_binding_alias, selected_model_name = (user_model_full.split('/', 1) + [None])[:2] if user_model_full else (None, None)
                    model_name_for_binding = selected_model_name if selected_binding_alias == final_alias else binding_to_use.default_model_name

                llm_init_params = { **binding_to_use.config }
                
                user_saved_params = {
                    "ctx_size": user_db.llm_ctx_size, "temperature": user_db.llm_temperature,
                    "top_k": user_db.llm_top_k, "top_p": user_db.llm_top_p,
                    "repeat_penalty": user_db.llm_repeat_penalty, "repeat_last_n": user_db.llm_repeat_last_n,
                    "put_thoughts_in_context": user_db.put_thoughts_in_context,
                    "reasoning_activation": user_db.reasoning_activation,
                    "reasoning_effort": user_db.reasoning_effort,
                    "reasoning_summary": user_db.reasoning_summary
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
                        llm_init_params.update({**alias_params, **final_user_params})
                    else:
                        llm_init_params.update(final_user_params)
                        llm_init_params.update(alias_params)
                    
                    if alias_info.get('ctx_size_locked', False) and 'ctx_size' in alias_info:
                        llm_init_params["ctx_size"] = alias_info['ctx_size']
                else:
                    llm_init_params.update(final_user_params)

                llm_init_params["model_name"] = model_name_for_binding
                client_init_params["llm_binding_name"] = binding_to_use.name
                client_init_params["llm_binding_config"] = llm_init_params    
        
        # --- TTI Binding Integration ---
        if load_tti:
            force_tti_mode = settings.get("force_tti_model_mode", "disabled")
            force_tti_name = settings.get("force_tti_model_name")
            effective_tti_model_full = None

            if force_tti_mode == "force_always" and force_tti_name:
                effective_tti_model_full = force_tti_name
            elif tti_binding_alias:
                effective_tti_model_full = f"{tti_binding_alias}/{tti_model_name or ''}"
            elif user_db.tti_binding_model_name:
                effective_tti_model_full = user_db.tti_binding_model_name
            
            selected_tti_binding = None
            selected_tti_model_name = None

            if effective_tti_model_full:
                if '/' in effective_tti_model_full:
                    effective_tti_binding_alias, effective_tti_model_name_part = effective_tti_model_full.split('/', 1)
                    selected_tti_binding = db.query(DBTTIBinding).filter(DBTTIBinding.alias == effective_tti_binding_alias, DBTTIBinding.is_active == True).first()
                    if selected_tti_binding:
                        selected_tti_model_name = effective_tti_model_name_part

                if not selected_tti_binding:
                    selected_tti_binding = db.query(DBTTIBinding).filter(DBTTIBinding.is_active == True).order_by(DBTTIBinding.id).first()
                    if selected_tti_binding:
                        selected_tti_model_name = selected_tti_binding.default_model_name
            
            if selected_tti_binding:
                tti_binding_config = selected_tti_binding.config.copy() if selected_tti_binding.config else {}
                
                tti_model_aliases = selected_tti_binding.model_aliases or {}
                tti_alias_info = tti_model_aliases.get(selected_tti_model_name)
                
                if tti_alias_info:
                    for key, value in tti_alias_info.items():
                        if key not in ['title', 'description', 'icon'] and value is not None:
                            tti_binding_config[key] = value
                            
                allow_tti_override = (tti_alias_info or {}).get('allow_parameters_override', True)
                if allow_tti_override:
                    user_tti_configs = user_db.tti_models_config or {}
                    model_user_config = user_tti_configs.get(user_db.tti_binding_model_name)
                    if model_user_config:
                        for key, value in model_user_config.items():
                            if value is not None:
                                tti_binding_config[key] = value

                if tti_params:
                    tti_binding_config.update(tti_params)
                                
                if selected_tti_model_name:
                    tti_binding_config['model_name'] = selected_tti_model_name                
                    tti_binding_config["models_path"]= str(Path(settings.get("data_dir","data"))/"tti_models"/selected_tti_binding.name)
                client_init_params["tti_binding_name"] = selected_tti_binding.name
                client_init_params["tti_binding_config"] = tti_binding_config
        
        # --- TTS Binding Integration ---
        if load_tts:
            selected_tts_binding = None
            selected_tts_model_name = tts_model_name
            
            user_tts_model_full = user_db.tts_binding_model_name
            if tts_binding_alias:
                user_tts_model_full = f"{tts_binding_alias}/{tts_model_name or ''}"
            
            if user_tts_model_full:
                if '/' in user_tts_model_full:
                    tts_binding_alias_local, tts_model_name_local = user_tts_model_full.split('/', 1)
                    selected_tts_binding = db.query(DBTTSBinding).filter(DBTTSBinding.alias == tts_binding_alias_local, DBTTSBinding.is_active == True).first()
                    if not selected_tts_model_name:
                        selected_tts_model_name = tts_model_name_local

                if not selected_tts_binding:
                    selected_tts_binding = db.query(DBTTSBinding).filter(DBTTSBinding.is_active == True).order_by(DBTTSBinding.id).first()
                    if selected_tts_binding and not selected_tts_model_name:
                        selected_tts_model_name = selected_tts_binding.default_model_name

            if selected_tts_binding:
                tts_binding_config = selected_tts_binding.config.copy() if selected_tts_binding.config else {}
                
                tts_model_aliases = selected_tts_binding.model_aliases or {}
                tts_alias_info = tts_model_aliases.get(selected_tts_model_name)
                
                if tts_alias_info:
                    for key, value in tts_alias_info.items():
                        if key not in ['title', 'description', 'icon'] and value is not None:
                            tts_binding_config[key] = value
                            
                allow_tts_override = (tts_alias_info or {}).get('allow_parameters_override', True)
                if allow_tts_override:
                    user_tts_configs = user_db.tts_models_config or {}
                    model_user_config = user_tts_configs.get(user_db.tts_binding_model_name)
                    if model_user_config:
                        for key, value in model_user_config.items():
                            if value is not None:
                                tts_binding_config[key] = value

                if tts_params:
                    tts_binding_config.update(tts_params)
                                
                if selected_tts_model_name:
                    tts_binding_config['model_name'] = selected_tts_model_name
                    
                client_init_params["tts_binding_name"] = selected_tts_binding.name
                client_init_params["tts_binding_config"] = tts_binding_config
            
        # --- STT Binding Integration ---
        if load_stt:
            selected_stt_binding = None
            selected_stt_model_name = stt_model_name
            
            user_stt_model_full = user_db.stt_binding_model_name
            if stt_binding_alias:
                user_stt_model_full = f"{stt_binding_alias}/{stt_model_name or ''}"

            if user_stt_model_full:
                if '/' in user_stt_model_full:
                    stt_binding_alias_local, stt_model_name_local = user_stt_model_full.split('/', 1)
                    selected_stt_binding = db.query(DBSTTBinding).filter(DBSTTBinding.alias == stt_binding_alias_local, DBSTTBinding.is_active == True).first()
                    if not selected_stt_model_name:
                        selected_stt_model_name = stt_model_name_local

                if not selected_stt_binding:
                    selected_stt_binding = db.query(DBSTTBinding).filter(DBSTTBinding.is_active == True).order_by(DBSTTBinding.id).first()
                    if selected_stt_binding and not selected_stt_model_name:
                        selected_stt_model_name = selected_stt_binding.default_model_name

            if selected_stt_binding:
                stt_binding_config = selected_stt_binding.config.copy() if selected_stt_binding.config else {}
                
                stt_model_aliases = selected_stt_binding.model_aliases or {}
                stt_alias_info = stt_model_aliases.get(selected_stt_model_name)
                
                if stt_alias_info:
                    for key, value in stt_alias_info.items():
                        if key not in ['title', 'description', 'icon'] and value is not None:
                            stt_binding_config[key] = value
                            
                allow_stt_override = (stt_alias_info or {}).get('allow_parameters_override', True)
                if allow_stt_override:
                    user_stt_configs = user_db.stt_models_config or {}
                    model_user_config = user_stt_configs.get(user_db.stt_binding_model_name)
                    if model_user_config:
                        for key, value in model_user_config.items():
                            if value is not None:
                                stt_binding_config[key] = value

                if stt_params:
                    stt_binding_config.update(stt_params)
                                
                if selected_stt_model_name:
                    stt_binding_config['model_name'] = selected_stt_model_name
                    
                client_init_params["stt_binding_name"] = selected_stt_binding.name
                client_init_params["stt_binding_config"] = stt_binding_config
        # --- END STT Binding Integration ---
        
        if 'servers_infos' not in session:
            session['servers_infos'] = load_mcps(username)
        servers_infos = session['servers_infos']
        
        if load_llm and servers_infos:
            client_init_params["mcp_binding_name"] = "remote_mcp"
            client_init_params["mcp_binding_config"] = {"servers_infos": servers_infos}

        try:
            ASCIIColors.magenta(f"INFO: Initializing LollmsClient for user '{username}'.")
            lc = LollmsClient(**{k: v for k, v in client_init_params.items() if v is not None})
            
            return lc
        except Exception as e:
            traceback.print_exc()
            binding_alias_to_show = binding_to_use.alias if binding_to_use else 'N/A'
            raise HTTPException(status_code=500, detail=f"Could not initialize LLM Client for binding '{binding_alias_to_show}': {str(e)}")
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
        # ASCIIColors.info(f"Recovering vectorizer:{datastore_record.vectorizer_name}")
        try:
            # FIX: Ensure 'model' key exists if 'model_name' is present, required for some vectorizers like ollama
            vectorizer_config = datastore_record.vectorizer_config or {}
            if isinstance(vectorizer_config, str):
                try:
                    vectorizer_config = json.loads(vectorizer_config)
                except Exception:
                    vectorizer_config = {}
            
            # Make a copy to avoid mutating the DB object if it's attached, though here it's likely fine.
            # safe_store modifies config passed to it sometimes? better be safe.
            v_config = vectorizer_config.copy()
            if 'model_name' in v_config and 'model' not in v_config:
                v_config['model'] = v_config['model_name']

            ss_instance = safe_store.SafeStore(
                name=datastore_record.name,
                description=datastore_record.description,
                db_path=ss_db_path,
                vectorizer_name=datastore_record.vectorizer_name,
                vectorizer_config=v_config,
                chunk_size=datastore_record.chunk_size,
                chunk_overlap=datastore_record.chunk_overlap,
                expand_before=10,
                expand_after=10,
                chunking_strategy="token"
            )
            ss_instance.name = datastore_record.name
            ss_instance.description = datastore_record.description
            session.setdefault("safe_store_instances", {})[datastore_id] = ss_instance
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Could not initialize SafeStore for {datastore_id}: {str(e)}")
            
    return cast(safe_store.SafeStore, session["safe_store_instances"][datastore_id])


def get_user_data_root(username: str) -> Path:
    safe_username = secure_filename(username)
    path = APP_DATA_DIR / USERS_DIR_NAME / safe_username
    path.mkdir(parents=True, exist_ok=True)
    (path / VOICES_DIR_NAME).mkdir(exist_ok=True)
    return path

def get_user_images_path(username: str) -> Path:
    path = get_user_data_root(username) / IMAGES_DIR_NAME
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

def get_user_notebook_assets_path(username: str, notebook_id: str) -> Path:
    path = get_user_data_root(username) / NOTEBOOK_ASSETS_DIR_NAME / secure_filename(notebook_id)
    path.mkdir(parents=True, exist_ok=True)
    return path