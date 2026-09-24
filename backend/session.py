# backend/session.py
import os
import json
import traceback
import datetime
import threading
from pathlib import Path
from typing import Dict, Optional, Any, cast, Callable, Tuple
from urllib.parse import urlparse

from fastapi import HTTPException, Depends, status
from sqlalchemy.orm import Session, joinedload, object_session
from werkzeug.utils import secure_filename
from ascii_colors import trace_exception, ASCIIColors

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.service import MCP as DBMCP, App as DBApp
from backend.db.models.datastore import DataStore as DBDataStore, SharedDataStoreLink as DBSharedDataStoreLink
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.config import (
    GlobalConfig, LLMBinding as DBLLMBinding, TTIBinding as DBTTIBinding,
    TTSBinding as DBTTSBinding, STTBinding as DBSTTBinding
)
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

# Authentication Cache to prevent DB bombardment during request bursts
_token_user_cache: Dict[str, tuple] = {}
_token_cache_lock = threading.Lock()
TOKEN_CACHE_TTL = 10 # seconds

# Global Client Registry to prevent file descriptor exhaustion
_global_client_registry: Dict[str, LollmsClient] = {}
_registry_lock = threading.Lock()

def reset_client_state(lc: Optional[LollmsClient]) -> None:
    """
    Arms a clean, uncancelled generation state on a LollmsClient and its underlying binding.
    Must be called before any generation and after successful completion.
    """
    if lc is None:
        return
    try:
        lc.cancel_generation = False
        if hasattr(lc, 'llm') and lc.llm is not None:
            llm = lc.llm
            if hasattr(llm, 'reset_cancel') and callable(llm.reset_cancel):
                try:
                    llm.reset_cancel()
                except Exception:
                    pass
            if hasattr(llm, '_cancel_event') and llm._cancel_event is not None:
                try:
                    llm._cancel_event.clear()
                except Exception:
                    pass
            if hasattr(llm, 'cancelled'):
                try:
                    llm.cancelled = False
                except Exception:
                    pass
    except Exception as e:
        ASCIIColors.warning(f"Error resetting client generation state: {e}")

def cancel_client_generation(lc: Optional[LollmsClient]) -> None:
    """
    Signals cooperative and socket-level cancellation to LollmsClient and its underlying binding.
    Closes active response streams to immediately free inference slots on the generation server.
    """
    if lc is None:
        return
    try:
        lc.cancel_generation = True
        if hasattr(lc, 'llm') and lc.llm is not None:
            llm = lc.llm
            if hasattr(llm, 'cancel') and callable(llm.cancel):
                try:
                    llm.cancel()
                except Exception as e:
                    ASCIIColors.warning(f"Error calling llm.cancel(): {e}")
            if hasattr(llm, '_cancel_event') and llm._cancel_event is not None:
                try:
                    llm._cancel_event.set()
                except Exception:
                    pass
            if hasattr(llm, 'cancelled'):
                try:
                    llm.cancelled = True
                except Exception:
                    pass
            if hasattr(llm, 'current_response') and llm.current_response is not None:
                try:
                    llm.current_response.close()
                except Exception:
                    pass
    except Exception as e:
        ASCIIColors.warning(f"Error cancelling client generation: {e}")

def evict_client_from_registry(client: Optional[LollmsClient] = None, username: Optional[str] = None) -> None:
    """
    Evicts a poisoned or disconnected LollmsClient instance from the global cache,
    forcing the next request to construct a fresh connection pool to the generation server.
    """
    with _registry_lock:
        if client is not None:
            keys_to_remove = [k for k, v in _global_client_registry.items() if v is client]
            for k in keys_to_remove:
                del _global_client_registry[k]
        else:
            _global_client_registry.clear()

    if username and username in user_sessions:
        user_sessions[username].pop("lollms_clients_cache", None)

# Locks to prevent race conditions during concurrent requests
_session_init_lock = threading.Lock()
_client_build_locks: Dict[str, threading.Lock] = {}
_client_build_locks_lock = threading.Lock()

def ensure_bool(value, default=False):
    if isinstance(value, bool):
        return value
    elif isinstance(value, str):
        try:
            return value.lower() in ("true", "yes", "1")
        except Exception:
            return default
    else:
        return default

def is_sentence_transformer_vectorizer(name: Optional[str], config: Optional[Dict[str, Any]] = None) -> bool:
    """Checks if a vectorizer name or config represents a Sentence-Transformers model."""
    if name:
        n = str(name).lower().strip()
        if n in ["st", "sentence_transformer", "sentence_transformers", "sentense_transformer", "sentense_transformers"]:
            return True
        if n.startswith("st:") or n.startswith("st_"):
            return True
        if "sentence_transformer" in n or "sentense_transformer" in n:
            return True
    if config and isinstance(config, dict):
        vec = config.get("vectorizer_name") or config.get("vectorizer")
        if vec and is_sentence_transformer_vectorizer(vec):
            return True
    return False

def get_user_by_username(db: Session, username: str) -> Optional[DBUser]:
    return db.query(DBUser).filter(DBUser.username == username).first()

async def get_current_db_user_from_token(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> DBUser:
    now = datetime.datetime.now(datetime.timezone.utc)

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

    with _token_cache_lock:
        if token in _token_user_cache:
            cached_user, expiry = _token_user_cache[token]
            if now < expiry:
                merged_user = db.merge(cached_user, load=False)
                token_iat = payload.get("iat")
                pwd_changed = merged_user.password_changed_at
                if pwd_changed and token_iat is not None:
                    pwd_changed_ts = pwd_changed.replace(tzinfo=datetime.timezone.utc).timestamp() if pwd_changed.tzinfo is None else pwd_changed.timestamp()
                    if (token_iat + 1) < pwd_changed_ts:
                        del _token_user_cache[token]
                        raise credentials_exception
                return merged_user
            else:
                del _token_user_cache[token]

    try:
        user = db.query(DBUser).filter(DBUser.username == username).first()
        if user is None:
            raise credentials_exception

        token_iat = payload.get("iat")
        if user.password_changed_at is not None and token_iat is not None:
            pwd_changed = user.password_changed_at
            pwd_changed_ts = pwd_changed.replace(tzinfo=datetime.timezone.utc).timestamp() if pwd_changed.tzinfo is None else pwd_changed.timestamp()
            if (token_iat + 1) < pwd_changed_ts:
                raise credentials_exception

        try:
            last_act = user.last_activity_at
            if last_act is None:
                user.last_activity_at = now
                db.commit()
                db.refresh(user)
            elif isinstance(last_act, datetime.datetime):
                last_activity_aware = last_act.replace(tzinfo=datetime.timezone.utc) if last_act.tzinfo is None else last_act
                if (now - last_activity_aware) > datetime.timedelta(seconds=60):
                    user.last_activity_at = now
                    db.commit()
                    db.refresh(user)
        except Exception:
            db.rollback()

        with _token_cache_lock:
            _token_user_cache[token] = (user, now + datetime.timedelta(seconds=TOKEN_CACHE_TTL))
            if len(_token_user_cache) > 1000:
                _token_user_cache.clear()

        return user

    except HTTPException:
        raise
    except Exception as e:
        trace_exception(e)
        raise credentials_exception

def get_current_active_user(db_user: DBUser = Depends(get_current_db_user_from_token)) -> UserAuthDetails:
    if not db_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive.")

    is_maintenance = settings.get("maintenance_mode", False)
    if is_maintenance and not db_user.is_admin:
        msg = settings.get("maintenance_message", "System under maintenance.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=msg
        )

    username = db_user.username
    db = object_session(db_user)
    db_was_created = False
    if not db:
        db = next(get_db())
        db_user = db.merge(db_user)
        db_was_created = True

    try:
        session_ui_level = db_user.user_ui_level
        if db_user.is_admin and session_ui_level != 4:
            session_ui_level = 4

        if username not in user_sessions:
            with _session_init_lock:
                if username not in user_sessions:
                    session_llm_params = {
                        "temperature": db_user.llm_temperature,
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

        force_model_mode = settings.get("force_model_mode", "disabled")
        forced_model = settings.get("force_model_name")
        if force_model_mode == "force_always" and forced_model:
            user_model_full = forced_model

        session = user_sessions[username]
        if session.get("lollms_model_name") != user_model_full:
            session["lollms_model_name"] = user_model_full

        llm_settings_overridden = False
        effective_llm_params = {
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

        _, _, prof_info = get_universal_model_profile(db, user_model_full, modality="llm")
        if prof_info and not prof_info.get('allow_parameters_override', True):
            llm_settings_overridden = True
            param_map = {
                "temperature": "llm_temperature",
                "top_k": "llm_top_k",
                "top_p": "llm_top_p",
                "repeat_penalty": "llm_repeat_penalty",
                "repeat_last_n": "llm_repeat_last_n",
                "reasoning_activation": "reasoning_activation",
                "reasoning_effort": "reasoning_effort",
                "reasoning_summary": "reasoning_summary"
            }
            for alias_key, user_key in param_map.items():
                if alias_key in prof_info and prof_info[alias_key] is not None:
                    effective_llm_params[user_key] = prof_info[alias_key]

        lc = get_user_lollms_client(username)
        ai_name_for_user = getattr(lc, "ai_name", "assistant")
        
        is_api_service_enabled = ensure_bool(settings.get("openai_api_service_enabled", False), False)
        is_api_require_key = ensure_bool(settings.get("openai_api_require_key", True), True)
        is_ollama_service_enabled = ensure_bool(settings.get("ollama_service_enabled", False), False)
        is_ollama_require_key = ensure_bool(settings.get("ollama_require_key", True), True)
        latex_builder_enabled = ensure_bool(settings.get("latex_builder_enabled", False), False)
        allow_user_chunking_config = ensure_bool(settings.get("allow_user_chunking_config", True), True)
        default_chunk_size = settings.get("default_chunk_size", 2048)
        default_chunk_overlap = settings.get("default_chunk_overlap", 256)

        force_rag_mode = settings.get("force_rag_settings_mode", "disabled")
        rag_settings_forced = False

        effective_rag_top_k = db_user.rag_top_k
        effective_max_rag_len = db_user.max_rag_len
        effective_rag_n_hops = db_user.rag_n_hops
        effective_rag_min_sim_percent = db_user.rag_min_sim_percent
        effective_rag_use_graph = db_user.rag_use_graph
        effective_rag_graph_response_type = db_user.rag_graph_response_type
        effective_rag_retrieval_mode = db_user.rag_retrieval_mode or "hybrid"
        effective_rag_dense_weight = db_user.rag_dense_weight if db_user.rag_dense_weight is not None else 0.5
        effective_rag_bm25_weight = db_user.rag_bm25_weight if db_user.rag_bm25_weight is not None else 0.5
        effective_rag_graph_weight = db_user.rag_graph_weight if db_user.rag_graph_weight is not None else 0.3
        effective_rag_rrf_k = db_user.rag_rrf_k or 60
        effective_default_rag_chunk_size = db_user.default_rag_chunk_size
        effective_default_rag_chunk_overlap = db_user.default_rag_chunk_overlap
        effective_safe_store_vectorizer = user_sessions[username].get("active_vectorizer")

        if force_rag_mode == "force_always":
            rag_settings_forced = True
            allow_user_chunking_config = False

            forced_vec = settings.get("force_rag_vectorizer")
            if forced_vec:
                effective_safe_store_vectorizer = forced_vec

            effective_default_rag_chunk_size = settings.get("force_rag_chunk_size", 2048)
            effective_default_rag_chunk_overlap = settings.get("force_rag_chunk_overlap", 256)
            default_chunk_size = effective_default_rag_chunk_size
            default_chunk_overlap = effective_default_rag_chunk_overlap

            effective_rag_top_k = settings.get("force_rag_top_k", 10)
            effective_max_rag_len = settings.get("force_rag_max_rag_len", 80000)
            effective_rag_n_hops = settings.get("force_rag_n_hops", 0)
            effective_rag_min_sim_percent = float(settings.get("force_rag_min_sim_percent", 50.0))
            effective_rag_retrieval_mode = settings.get("force_rag_retrieval_mode", "hybrid")
            effective_rag_dense_weight = float(settings.get("force_rag_dense_weight", 0.5))
            effective_rag_bm25_weight = float(settings.get("force_rag_bm25_weight", 0.5))
            effective_rag_rrf_k = int(settings.get("force_rag_rrf_k", 60))
            effective_rag_use_graph = ensure_bool(settings.get("force_rag_use_graph", False), False)
            effective_rag_graph_response_type = settings.get("force_rag_graph_response_type", "chunks_summary")

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
            safe_store_vectorizer=effective_safe_store_vectorizer,
            active_personality_id=user_sessions[username].get("active_personality_id"),
            active_voice_id=db_user.active_voice_id,
            last_discussion_id=db_user.last_discussion_id,
            lollms_client_ai_name=ai_name_for_user,
            **effective_llm_params,
            rag_top_k=effective_rag_top_k, 
            max_rag_len=effective_max_rag_len, 
            rag_n_hops=effective_rag_n_hops,
            rag_min_sim_percent=effective_rag_min_sim_percent, 
            rag_use_graph=effective_rag_use_graph,
            rag_graph_response_type=effective_rag_graph_response_type, 
            rag_retrieval_mode=effective_rag_retrieval_mode,
            rag_dense_weight=effective_rag_dense_weight,
            rag_bm25_weight=effective_rag_bm25_weight,
            rag_graph_weight=effective_rag_graph_weight,
            rag_rrf_k=effective_rag_rrf_k,
            default_rag_chunk_size=effective_default_rag_chunk_size,
            default_rag_chunk_overlap=effective_default_rag_chunk_overlap,
            default_rag_metadata_mode=db_user.default_rag_metadata_mode,
            rag_settings_forced=rag_settings_forced,
            auto_title=db_user.auto_title,
            user_ui_level=session_ui_level if isinstance(session_ui_level, int) else int(session_ui_level) if isinstance(session_ui_level, str) else 0, chat_active=db_user.chat_active, first_page=db_user.first_page,
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
            image_studio_seed=db_user.image_studio_seed or -1,
            image_studio_generation_params=db_user.image_studio_generation_params,
            image_generation_enabled=db_user.image_generation_enabled,
            image_generation_system_prompt=db_user.image_generation_system_prompt,
            image_annotation_enabled=db_user.image_annotation_enabled,
            image_editing_enabled=db_user.image_editing_enabled,
            inline_widgets_enabled=db_user.inline_widgets_enabled,
            slide_maker_enabled=db_user.slide_maker_enabled,
            activate_generated_images=db_user.activate_generated_images,
            note_generation_enabled=db_user.note_generation_enabled,
            memory_enabled=db_user.memory_enabled,
            auto_memory_enabled=db_user.auto_memory_enabled,
            skills_library_enabled=db_user.skills_library_enabled,
            skills_building_enabled=db_user.skills_building_enabled,
            form_building_enabled=db_user.form_building_enabled,
            preferred_name=db_user.preferred_name,
            user_personal_info=db_user.user_personal_info,
            share_personal_info_with_llm=db_user.share_personal_info_with_llm,
            max_image_width=db_user.max_image_width,
            max_image_height=db_user.max_image_height,
            compress_images=db_user.compress_images,
            image_compression_quality=db_user.image_compression_quality,

            herd_mode_enabled=db_user.herd_mode_enabled,
            herd_participants=db_user.herd_participants or [],
            herd_precode_participants=db_user.herd_precode_participants or [],
            herd_postcode_participants=db_user.herd_postcode_participants or [],
            herd_rounds=db_user.herd_rounds,
            herd_dynamic_mode=db_user.herd_dynamic_mode,
            herd_model_pool=db_user.herd_model_pool or [],
            
            google_api_key=db_user.google_api_key,
            google_cse_id=db_user.google_cse_id,
            web_search_enabled=db_user.web_search_enabled,
            web_search_providers=db_user.web_search_providers or [],
            web_search_deep_analysis=db_user.web_search_deep_analysis,
            street_view_enabled=db_user.street_view_enabled,
            scheduler_enabled=db_user.scheduler_enabled,
            google_drive_enabled=db_user.google_drive_enabled,
            google_calendar_enabled=db_user.google_calendar_enabled,
            google_gmail_enabled=db_user.google_gmail_enabled
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
                if not mcp.url: continue
                
                mcp_base_url = mcp.url.rstrip('/')
                parsed = urlparse(mcp_base_url)
                
                if mcp_base_url.endswith('/mcp'):
                     mcp_full_url = mcp_base_url
                elif parsed.path and parsed.path != '/':
                     mcp_full_url = mcp_base_url
                else:
                     mcp_full_url = f"{mcp_base_url}/mcp"
                
                server_info = {"server_url": mcp_full_url}
                
                if mcp.authentication_type == "lollms_chat_auth" and access_token:
                    server_info["auth_config"] = { "type": "bearer", "token": access_token }
                elif mcp.authentication_type == "bearer":
                    server_info["auth_config"] = { "type": "bearer", "token": mcp.authentication_key }
                elif mcp.authentication_type == "api_key":
                    key = mcp.authentication_key
                    header = "X-API-Key"
                    
                    if key and key.strip().startswith('{'):
                        try:
                            data = json.loads(key)
                            if isinstance(data, dict):
                                key = data.get("key", "")
                                header = data.get("header_name", "X-API-Key")
                        except Exception as e:
                            print(f"Warning: Failed to parse API key JSON for {mcp.name}: {e}")
                    
                    server_info["auth_config"] = { 
                        "type": "api_key", 
                        "key": key,
                        "header_name": header
                    }

                servers_infos[mcp.name] = server_info
            except Exception as e:
                trace_exception(e)
    finally:
        db_for_mcp.close()
    return servers_infos

def invalidate_user_mcp_cache(username: str):
    if username in user_sessions:
        session = user_sessions[username]
        if 'tools_cache' in session:
            del session['tools_cache']
        if 'servers_infos' in session:
            del session['servers_infos']
        session.pop("lollms_clients_cache", None)
        print(f"INFO: Fully invalidated MCP caches for user: {username}")

def reload_lollms_client_mcp(username: str):
    invalidate_user_mcp_cache(username)

def get_user_lollms_client(
    username: str,
    binding_alias_override: Optional[str] = None,
    model_name_override: Optional[str] = None,
    load_mcp: bool = True,
    llm_params: Optional[Dict[str, Any]] = None
) -> LollmsClient:
    client = build_lollms_client_from_params(
        username=username,
        binding_alias=binding_alias_override,
        model_name=model_name_override,
        llm_params=llm_params,
        load_mcp=load_mcp
    )

    if username in user_sessions:
        clients_cache = user_sessions[username].setdefault("lollms_clients_cache", {})
        params_suffix = f"_{hash(json.dumps(llm_params, sort_keys=True, default=str))}" if llm_params else ""
        cache_key = f"{binding_alias_override or 'default'}_{model_name_override or 'default'}{params_suffix}"
        if not load_mcp:
            cache_key += "_no_mcp"
        clients_cache[cache_key] = client

    return client

def _build_universal_profiles_for_modality(
    db: Session,
    binding_model_cls: Any,
    active_binding_alias: Optional[str],
    active_model_name: Optional[str],
    user_overrides: Dict[str, Any],
    forced_ctx_size: Optional[int] = None
) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[str]]:
    all_bindings = db.query(binding_model_cls).filter(binding_model_cls.is_active == True).all()
    binding_profiles = {}
    model_profiles = {}
    default_model_profile_name = None

    def _matches_active(b_alias: str, p_key: str, p_cfg: dict) -> bool:
        if not active_model_name:
            return False
        m_raw = active_model_name.strip()
        m_low = m_raw.lower()
        if active_binding_alias and active_binding_alias != b_alias:
            if not m_low.startswith(f"{b_alias.lower()}/"):
                return False

        p_title = (p_cfg.get('title') or '').strip().lower()
        p_name = (p_cfg.get('name') or '').strip().lower()
        p_target = (p_cfg.get('model_name') or '').strip().lower()
        p_key_low = p_key.strip().lower()
        namespaced_key = f"{b_alias}/{p_key}".lower()
        namespaced_target = f"{b_alias}/{p_target}".lower() if p_target else ""

        return (
            m_low == p_key_low or
            m_low == namespaced_key or
            m_low == p_title or
            m_low == p_name or
            m_low == p_target or
            m_low == namespaced_target
        )

    # First pass: Build concrete binding profiles & universal model profiles
    for binding in all_bindings:
        b_config = binding.config.copy() if binding.config else {}
        is_binding_default = (binding.alias == active_binding_alias)

        binding_profiles[binding.alias] = {
            "binding_name": binding.name,
            "binding_config": b_config,
            "is_default": is_binding_default
        }

        aliases = binding.model_aliases or {}
        if isinstance(aliases, str):
            try: aliases = json.loads(aliases)
            except Exception: aliases = {}
        if not isinstance(aliases, dict):
            aliases = {}

        for orig_name, alias_data in aliases.items():
            if not isinstance(alias_data, dict):
                alias_data = {"title": str(alias_data)}

            cfg = alias_data.get('alias', {}) if 'alias' in alias_data else alias_data
            prof_name = f"{binding.alias}/{orig_name}"
            is_model_default = _matches_active(binding.alias, orig_name, cfg)

            if is_model_default:
                default_model_profile_name = prof_name

            raw_ctx = forced_ctx_size or cfg.get('forced_context_size') or cfg.get('ctx_size') or b_config.get('ctx_size')
            effective_ctx = None
            if raw_ctx is not None:
                try:
                    parsed_ctx = int(raw_ctx)
                    if parsed_ctx > 1:
                        effective_ctx = parsed_ctx
                except (ValueError, TypeError):
                    effective_ctx = None

            target_model = cfg.get('model_name') or orig_name

            profile_entry = {
                "name": orig_name,
                "binding_profile_name": binding.alias,
                "model_name": target_model,
                "title": cfg.get('title') or orig_name,
                "description": cfg.get('description', ''),
                "vision_enabled": cfg.get('vision_enabled', cfg.get('has_vision', False)),
                "has_vision": cfg.get('has_vision', cfg.get('vision_enabled', False)),
                "forced_context_size": effective_ctx,
                "ctx_size": effective_ctx,
                "temperature": cfg.get('temperature'),
                "top_k": cfg.get('top_k'),
                "top_p": cfg.get('top_p'),
                "repeat_penalty": cfg.get('repeat_penalty'),
                "repeat_last_n": cfg.get('repeat_last_n'),
                "reasoning_activation": cfg.get('reasoning_activation', False),
                "reasoning_effort": cfg.get('reasoning_effort'),
                "reasoning_summary": cfg.get('reasoning_summary', False),
                "allow_parameters_override": cfg.get('allow_parameters_override', True),
                "icon": cfg.get('icon'),
                "routing_config": cfg.get('routing_config', {
                    "description": cfg.get('description') or cfg.get('title') or orig_name,
                    "complexity_tier": 2,
                    "cost_per_1k_tokens": 0.0,
                    "avg_latency_ms": 200,
                    "priority": 1
                }),
                "vlm_model_profile": cfg.get('vlm_model_profile'),
                "selected_model_profiles": cfg.get('selected_model_profiles', []),
                "routing_strategy": cfg.get('routing_strategy', 'balanced'),
                "is_default": is_model_default
            }

            if profile_entry["allow_parameters_override"] and user_overrides:
                for k, v in user_overrides.items():
                    profile_entry[k] = v

            # Index under both full ID and short key for seamless lollms_client lookup
            model_profiles[prof_name] = profile_entry
            if orig_name not in model_profiles:
                model_profiles[orig_name] = profile_entry

    # Second pass: Dynamically assemble Smart Router groups using member profiles
    for binding in all_bindings:
        if (binding.name == 'smart_router' or binding.alias == 'smart_router'):
            aliases = binding.model_aliases or {}
            if isinstance(aliases, str):
                try: aliases = json.loads(aliases)
                except Exception: aliases = {}

            if not aliases:
                aliases = {"auto": {"title": "Auto Smart Router", "routing_strategy": "balanced"}}

            for group_key, group_data in aliases.items():
                if not isinstance(group_data, dict):
                    group_data = {"title": str(group_data)}

                cfg = group_data.get('alias', {}) if 'alias' in group_data else group_data
                selected_profs = cfg.get('selected_model_profiles', [])
                group_strategy = cfg.get('routing_strategy', 'balanced')

                assembled_pool = {}
                for p_id, p_info in model_profiles.items():
                    if p_info.get("binding_profile_name") == binding.alias:
                        continue
                    if not selected_profs or p_id in selected_profs:
                        parent_b = binding_profiles.get(p_info["binding_profile_name"], {})
                        assembled_pool[p_id] = {
                            "binding_name": parent_b.get("binding_name", "openai"),
                            "binding_config": {
                                **(parent_b.get("binding_config", {})),
                                "model_name": p_info["model_name"]
                            },
                            "vision_enabled": p_info.get("vision_enabled", False),
                            "routing_profile": p_info.get("routing_config", {
                                "description": p_info.get("description") or p_info.get("title"),
                                "complexity_tier": 2,
                                "cost_per_1k_tokens": 0.0,
                                "avg_latency_ms": 200,
                                "priority": 1
                            })
                        }

                smart_b_profile_name = f"{binding.alias}_group_{group_key}"
                binding_profiles[smart_b_profile_name] = {
                    "binding_name": "smart_router",
                    "binding_config": {
                        "routing_strategy": group_strategy,
                        "model_profiles": assembled_pool
                    },
                    "is_default": (binding.alias == active_binding_alias and group_key == active_model_name)
                }

                prof_full_name = f"{binding.alias}/{group_key}"
                is_group_default = (binding.alias == active_binding_alias and (group_key == active_model_name or active_model_name is None))
                if is_group_default:
                    default_model_profile_name = prof_full_name

                model_profiles[prof_full_name] = {
                    "binding_profile_name": smart_b_profile_name,
                    "model_name": group_key,
                    "title": cfg.get('title') or f"Smart Router ({group_key})",
                    "description": cfg.get('description', f"Auto-routing group with {len(assembled_pool)} models"),
                    "vision_enabled": True,
                    "has_vision": True,
                    "forced_context_size": forced_ctx_size or cfg.get('forced_context_size'),
                    "ctx_size": forced_ctx_size or cfg.get('forced_context_size'),
                    "selected_model_profiles": selected_profs,
                    "routing_strategy": group_strategy,
                    "is_default": is_group_default,
                    **user_overrides
                }

    return binding_profiles, model_profiles, default_model_profile_name

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
    load_stt: bool = False,
    load_mcp: bool = True,
    callback: Optional[Callable] = None
) -> LollmsClient:
    session = user_sessions.get(username)
    
    if not session:
        session = {
            "safe_store_instances": {},
            "discussions": {},
            "llm_params": {},
        }

    db = next(get_db())
    try:
        user_db = db.query(DBUser).filter(DBUser.username == username).first()
        if not user_db:
             raise HTTPException(status_code=404, detail=f"User '{username}' not found.")
        
        user_saved_params = {
            "temperature": user_db.llm_temperature,
            "top_k": user_db.llm_top_k, "top_p": user_db.llm_top_p,
            "repeat_penalty": user_db.llm_repeat_penalty, "repeat_last_n": user_db.llm_repeat_last_n,
            "put_thoughts_in_context": user_db.put_thoughts_in_context,
            "reasoning_activation": user_db.reasoning_activation,
            "reasoning_effort": user_db.reasoning_effort,
            "reasoning_summary": user_db.reasoning_summary
        }
        user_session_params = session.get("llm_params", {})
        final_user_params = {**{k: v for k, v in user_saved_params.items() if v is not None}, **user_session_params}
        if llm_params:
            final_user_params.update(llm_params)

        force_model_mode = settings.get("force_model_mode", "disabled")
        forced_ctx = None
        if force_model_mode == "force_always":
            forced_ctx = settings.get("force_context_size")
            forced_model = settings.get("force_model_name")
            if forced_model:
                if '/' in forced_model:
                    binding_alias, model_name = forced_model.split('/', 1)
                else:
                    binding_alias, model_name = None, forced_model

        user_model_full = user_db.lollms_model_name or session.get("lollms_model_name") or settings.get("default_lollms_model_name")
        target_binding_alias = binding_alias
        target_model_name = model_name

        if not target_binding_alias and user_model_full:
            if '/' in user_model_full:
                target_binding_alias, target_model_name = user_model_full.split('/', 1)
            else:
                try:
                    resolved_alias, resolved_model = resolve_model_name(db, user_model_full, fallback_to_default=True)
                    target_binding_alias = resolved_alias
                    if not target_model_name:
                        target_model_name = resolved_model
                except Exception:
                    pass

        if not target_binding_alias:
            default_binding = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).order_by(DBLLMBinding.id).first()
            if default_binding:
                target_binding_alias = default_binding.alias
                if not target_model_name:
                    target_model_name = default_binding.default_model_name

        llm_binding_profiles, llm_model_profiles, default_llm_prof = _build_universal_profiles_for_modality(
            db=db,
            binding_model_cls=DBLLMBinding,
            active_binding_alias=target_binding_alias,
            active_model_name=target_model_name,
            user_overrides=final_user_params,
            forced_ctx_size=forced_ctx
        )

        tti_binding_profiles, tti_model_profiles, _ = _build_universal_profiles_for_modality(
            db=db,
            binding_model_cls=DBTTIBinding,
            active_binding_alias=tti_binding_alias or (user_db.tti_binding_model_name.split('/')[0] if user_db.tti_binding_model_name and '/' in user_db.tti_binding_model_name else None),
            active_model_name=tti_model_name or (user_db.tti_binding_model_name.split('/', 1)[1] if user_db.tti_binding_model_name and '/' in user_db.tti_binding_model_name else None),
            user_overrides=tti_params or {}
        )

        tts_binding_profiles, tts_model_profiles, _ = _build_universal_profiles_for_modality(
            db=db,
            binding_model_cls=DBTTSBinding,
            active_binding_alias=tts_binding_alias or (user_db.tts_binding_model_name.split('/')[0] if user_db.tts_binding_model_name and '/' in user_db.tts_binding_model_name else None),
            active_model_name=tts_model_name or (user_db.tts_binding_model_name.split('/', 1)[1] if user_db.tts_binding_model_name and '/' in user_db.tts_binding_model_name else None),
            user_overrides=tts_params or {}
        )

        stt_binding_profiles, stt_model_profiles, _ = _build_universal_profiles_for_modality(
            db=db,
            binding_model_cls=DBSTTBinding,
            active_binding_alias=stt_binding_alias or (user_db.stt_binding_model_name.split('/')[0] if user_db.stt_binding_model_name and '/' in user_db.stt_binding_model_name else None),
            active_model_name=stt_model_name or (user_db.stt_binding_model_name.split('/', 1)[1] if user_db.stt_binding_model_name and '/' in user_db.stt_binding_model_name else None),
            user_overrides=stt_params or {}
        )

        # 1. Resolve Primary LLM Universal Profile and Config
        primary_binding = db.query(DBLLMBinding).filter(DBLLMBinding.alias == target_binding_alias, DBLLMBinding.is_active == True).first()
        primary_config = primary_binding.config.copy() if primary_binding and primary_binding.config else {}

        active_prof = None
        if default_llm_prof and default_llm_prof in llm_model_profiles:
            active_prof = llm_model_profiles[default_llm_prof]
        else:
            for p in llm_model_profiles.values():
                if p.get("is_default"):
                    active_prof = p
                    break

        actual_model = (active_prof.get("model_name") if active_prof else None) or target_model_name or (primary_binding.default_model_name if primary_binding else "")

        active_ctx = forced_ctx
        if not active_ctx and active_prof:
            active_ctx = active_prof.get("forced_context_size") or active_prof.get("ctx_size")
        if not active_ctx and primary_config.get("ctx_size"):
            try:
                parsed_c = int(primary_config["ctx_size"])
                if parsed_c > 1: active_ctx = parsed_c
            except (ValueError, TypeError):
                pass
        if not active_ctx or active_ctx <= 1:
            active_ctx = 32000

        primary_config["model_name"] = actual_model
        primary_config["ctx_size"] = active_ctx
        primary_config["forced_context_size"] = active_ctx

        # Apply parameters respecting allow_parameters_override
        if active_prof and not active_prof.get("allow_parameters_override", True):
            for param_k in ['temperature', 'top_k', 'top_p', 'repeat_penalty', 'repeat_last_n', 'reasoning_activation', 'reasoning_effort', 'reasoning_summary']:
                if active_prof.get(param_k) is not None:
                    primary_config[param_k] = active_prof[param_k]
        else:
            primary_config.update(final_user_params)
            primary_config["model_name"] = actual_model
            primary_config["ctx_size"] = active_ctx
            primary_config["forced_context_size"] = active_ctx

        # 2. Resolve Primary TTS Binding
        target_tts_alias = tts_binding_alias or (user_db.tts_binding_model_name.split('/')[0] if user_db.tts_binding_model_name and '/' in user_db.tts_binding_model_name else None)
        if not target_tts_alias:
            def_tts_name = settings.get("default_tts_binding_model")
            if def_tts_name and '/' in def_tts_name:
                target_tts_alias = def_tts_name.split('/')[0]
        if not target_tts_alias:
            def_tts_b = db.query(DBTTSBinding).filter(DBTTSBinding.is_active == True).order_by(DBTTSBinding.id).first()
            if def_tts_b:
                target_tts_alias = def_tts_b.alias

        primary_tts_binding = db.query(DBTTSBinding).filter(DBTTSBinding.alias == target_tts_alias, DBTTSBinding.is_active == True).first() if target_tts_alias else None
        primary_tts_config = primary_tts_binding.config.copy() if primary_tts_binding and primary_tts_binding.config else {}
        if tts_params:
            primary_tts_config.update(tts_params)

        # 3. Resolve Primary TTI Binding
        target_tti_alias = tti_binding_alias or (user_db.tti_binding_model_name.split('/')[0] if user_db.tti_binding_model_name and '/' in user_db.tti_binding_model_name else None)
        if not target_tti_alias:
            def_tti_name = settings.get("default_tti_binding_model")
            if def_tti_name and '/' in def_tti_name:
                target_tti_alias = def_tti_name.split('/')[0]
        if not target_tti_alias:
            def_tti_b = db.query(DBTTIBinding).filter(DBTTIBinding.is_active == True).order_by(DBTTIBinding.id).first()
            if def_tti_b:
                target_tti_alias = def_tti_b.alias

        primary_tti_binding = db.query(DBTTIBinding).filter(DBTTIBinding.alias == target_tti_alias, DBTTIBinding.is_active == True).first() if target_tti_alias else None
        primary_tti_config = primary_tti_binding.config.copy() if primary_tti_binding and primary_tti_binding.config else {}
        if tti_params:
            primary_tti_config.update(tti_params)

        # 4. Resolve Primary STT Binding
        target_stt_alias = stt_binding_alias or (user_db.stt_binding_model_name.split('/')[0] if user_db.stt_binding_model_name and '/' in user_db.stt_binding_model_name else None)
        if not target_stt_alias:
            def_stt_name = settings.get("default_stt_binding_model")
            if def_stt_name and '/' in def_stt_name:
                target_stt_alias = def_stt_name.split('/')[0]
        if not target_stt_alias:
            def_stt_b = db.query(DBSTTBinding).filter(DBSTTBinding.is_active == True).order_by(DBSTTBinding.id).first()
            if def_stt_b:
                target_stt_alias = def_stt_b.alias

        primary_stt_binding = db.query(DBSTTBinding).filter(DBSTTBinding.alias == target_stt_alias, DBSTTBinding.is_active == True).first() if target_stt_alias else None
        primary_stt_config = primary_stt_binding.config.copy() if primary_stt_binding and primary_stt_binding.config else {}
        if stt_params:
            primary_stt_config.update(stt_params)

        client_init_params = {
            "load_llm": load_llm,
            "load_tti": load_tti,
            "load_tts": load_tts,
            "load_stt": load_stt,
            "llm_binding_profiles": llm_binding_profiles,
            "llm_model_profiles": llm_model_profiles,
            "tti_binding_profiles": tti_binding_profiles,
            "tti_model_profiles": tti_model_profiles,
            "tts_binding_profiles": tts_binding_profiles,
            "tts_model_profiles": tts_model_profiles,
            "stt_binding_profiles": stt_binding_profiles,
            "stt_model_profiles": stt_model_profiles,
            "llm_binding_name": primary_binding.name if primary_binding else None,
            "llm_binding_config": primary_config,
            "tts_binding_name": primary_tts_binding.name if primary_tts_binding else None,
            "tts_binding_config": primary_tts_config,
            "tti_binding_name": primary_tti_binding.name if primary_tti_binding else None,
            "tti_binding_config": primary_tti_config,
            "stt_binding_name": primary_stt_binding.name if primary_stt_binding else None,
            "stt_binding_config": primary_stt_config
        }

        if load_llm and load_mcp:
            servers_infos = session.get('servers_infos')
            if servers_infos is not None:
                client_init_params["tools_binding_name"] = "remote_mcp"
                client_init_params["tools_binding_config"] = {"servers_infos": servers_infos}

        try:
            registry_payload = {k: v for k, v in client_init_params.items() if v is not None}
            registry_key = str(hash(json.dumps(registry_payload, sort_keys=True, default=str)))

            with _registry_lock:
                if registry_key in _global_client_registry:
                    if callback:
                        callback("⚡ Universal Engine cached - Instant access enabled.", 28, {})
                    return _global_client_registry[registry_key]

                try:
                    lc = LollmsClient(**registry_payload, callback=callback)
                    if hasattr(lc, 'llm') and lc.llm:
                        if hasattr(lc.llm, 'set_forced_ctx_size') and callable(lc.llm.set_forced_ctx_size):
                            try: lc.llm.set_forced_ctx_size(active_ctx)
                            except Exception: pass
                        if hasattr(lc.llm, 'forced_context_size'):
                            lc.llm.forced_context_size = active_ctx
                        if hasattr(lc.llm, 'ctx_size'):
                            lc.llm.ctx_size = active_ctx
                        if "reasoning_activation" in primary_config:
                            setattr(lc.llm, 'reasoning_activation', primary_config["reasoning_activation"])
                        if "reasoning_effort" in primary_config:
                            setattr(lc.llm, 'reasoning_effort', primary_config["reasoning_effort"])

                    if "reasoning_activation" in primary_config:
                        setattr(lc, 'reasoning_activation', primary_config["reasoning_activation"])
                    if "reasoning_effort" in primary_config:
                        setattr(lc, 'reasoning_effort', primary_config["reasoning_effort"])

                    _global_client_registry[registry_key] = lc
                    return lc
                except Exception as engine_err:
                    error_msg = str(engine_err)
                    binding_alias_to_show = target_binding_alias or 'N/A'
                    
                    ASCIIColors.warning(f"Engine Load Failed >> Binding: {binding_alias_to_show} | Error: {error_msg}")
                    
                    if callback:
                        callback(f"⚠️ Configuration Issue: {error_msg}", 24, {})
                    
                    degraded_payload = registry_payload.copy()
                    degraded_payload["load_llm"] = False
                    degraded_payload["load_tti"] = False
                    degraded_payload["load_tts"] = False
                    degraded_payload["load_stt"] = False
                    degraded_payload.pop("llm_binding_name", None)
                    degraded_payload.pop("llm_binding_config", None)
                    degraded_payload.pop("llm_binding_profiles", None)
                    degraded_payload.pop("llm_model_profiles", None)
                    
                    degraded_lc = LollmsClient(**degraded_payload)
                    return degraded_lc

        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"System error during engine registry: {str(e)}")
    finally:
        db.close()

def _migrate_datastore_sqlite_schema(db_path: Path):
    if not db_path.exists() or db_path.is_dir():
        return
    import sqlite3
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        if "documents" in tables:
            cursor.execute("PRAGMA table_info(documents)")
            doc_cols = {row[1] for row in cursor.fetchall()}
            if "full_text" not in doc_cols:
                cursor.execute("ALTER TABLE documents ADD COLUMN full_text TEXT")
            if "metadata" not in doc_cols:
                cursor.execute("ALTER TABLE documents ADD COLUMN metadata TEXT")
            if "created_at" not in doc_cols:
                cursor.execute("ALTER TABLE documents ADD COLUMN created_at DATETIME")
            if "updated_at" not in doc_cols:
                cursor.execute("ALTER TABLE documents ADD COLUMN updated_at DATETIME")
            conn.commit()

        if "chunks" in tables:
            cursor.execute("PRAGMA table_info(chunks)")
            chunk_cols = {row[1] for row in cursor.fetchall()}
            if "metadata" not in chunk_cols:
                cursor.execute("ALTER TABLE chunks ADD COLUMN metadata TEXT")
            if "chunk_index" not in chunk_cols:
                cursor.execute("ALTER TABLE chunks ADD COLUMN chunk_index INTEGER")
            conn.commit()

        conn.close()
    except Exception as e:
        print(f"Warning: Failed to auto-migrate SQLite schema for {db_path.name}: {e}")

def get_safe_store_instance(
    requesting_user_username: str,
    datastore_id: str,
    db: Session,
    permission_level: str = "read_query"
) -> Any:
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
        _migrate_datastore_sqlite_schema(ss_db_path)
        try:
            vectorizer_config = datastore_record.vectorizer_config or {}
            if isinstance(vectorizer_config, str):
                try:
                    vectorizer_config = json.loads(vectorizer_config)
                except Exception:
                    vectorizer_config = {}
            
            v_config = vectorizer_config.copy()
            if 'model_name' in v_config and 'model' not in v_config:
                v_config['model'] = v_config['model_name']

            # Enforce use_shared_server for sentence-transformer vectorizers
            if is_sentence_transformer_vectorizer(datastore_record.vectorizer_name, v_config):
                v_config["use_shared_server"] = True

            strategy = getattr(datastore_record, "chunking_strategy", "recursive") or "recursive"
            strategy_kwargs = getattr(datastore_record, "chunking_kwargs", {}) or {}

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
                chunking_strategy=strategy,
                chunking_kwargs=strategy_kwargs if isinstance(strategy_kwargs, dict) else {}
            )
            ss_instance.name = datastore_record.name
            ss_instance.description = datastore_record.description
            session.setdefault("safe_store_instances", {})[datastore_id] = ss_instance
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Could not initialize SafeStore for {datastore_id}: {str(e)}")

    return session["safe_store_instances"][datastore_id]

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

def get_user_social_assets_path(username: str) -> Path:
    path = get_user_data_root(username) / "social_assets"
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

def get_universal_model_profile(
    db: Session,
    requested_model: Optional[str],
    modality: str = "llm"
) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    """
    Authoritative Universal Model Profile resolver.
    Matches incoming requested model by:
    1. Full profile ID ('binding_alias/profile_key')
    2. Profile key ('profile_key')
    3. Profile title or name
    4. Underlying physical model name
    Returns (binding_alias, profile_key, profile_dict).
    """
    binding_classes = {
        "llm": DBLLMBinding,
        "tti": DBTTIBinding,
        "tts": DBTTSBinding,
        "stt": DBSTTBinding
    }
    binding_cls = binding_classes.get(modality, DBLLMBinding)
    all_bindings = db.query(binding_cls).filter(binding_cls.is_active == True).all()

    if not requested_model or not requested_model.strip():
        if all_bindings:
            first_b = all_bindings[0]
            aliases = first_b.model_aliases or {}
            if isinstance(aliases, str):
                try: aliases = json.loads(aliases)
                except Exception: aliases = {}
            if isinstance(aliases, dict) and aliases:
                p_key = next(iter(aliases))
                p_val = aliases[p_key]
                cfg = p_val.get('alias', p_val) if isinstance(p_val, dict) else {"title": str(p_val)}
                return first_b.alias, p_key, cfg
            return first_b.alias, first_b.default_model_name, None
        return None, None, None

    req_str = requested_model.strip()
    req_lower = req_str.lower()
    has_slash = '/' in req_str
    prefix_alias = req_str.split('/', 1)[0] if has_slash else None
    suffix_model = req_str.split('/', 1)[1] if has_slash else req_str
    suffix_lower = suffix_model.lower()

    # Pass 1: Direct matches against bindings and profiles
    for binding in all_bindings:
        if prefix_alias and binding.alias != prefix_alias:
            continue

        aliases = binding.model_aliases or {}
        if isinstance(aliases, str):
            try: aliases = json.loads(aliases)
            except Exception: aliases = {}
        if not isinstance(aliases, dict):
            aliases = {}

        # 1. Exact profile key match
        if suffix_model in aliases:
            p_val = aliases[suffix_model]
            cfg = p_val.get('alias', p_val) if isinstance(p_val, dict) else {"title": str(p_val)}
            return binding.alias, suffix_model, cfg

        # 2. Case-insensitive key, title, name, or model_name match
        for p_key, p_val in aliases.items():
            if not isinstance(p_val, dict):
                p_val = {"title": str(p_val)}
            cfg = p_val.get('alias', p_val) if isinstance(p_val, dict) else p_val
            p_title = (cfg.get('title') or '').strip().lower()
            p_name = (cfg.get('name') or '').strip().lower()
            p_model = (cfg.get('model_name') or '').strip().lower()
            p_key_lower = p_key.strip().lower()

            if (
                suffix_lower == p_key_lower or
                suffix_lower == p_title or
                suffix_lower == p_name or
                suffix_lower == p_model or
                req_lower == f"{binding.alias}/{p_key}".lower() or
                req_lower == f"{binding.alias}/{p_title}".lower()
            ):
                return binding.alias, p_key, cfg

    # Pass 2: Fallback for raw physical models running on a binding
    if prefix_alias:
        target_b = next((b for b in all_bindings if b.alias == prefix_alias), None)
        if target_b:
            return target_b.alias, suffix_model, None

    # Pass 3: Global search without slash fallback
    for binding in all_bindings:
        if binding.default_model_name and suffix_lower == binding.default_model_name.lower():
            return binding.alias, binding.default_model_name, None

    return None, None, None

def find_model_by_alias(db: Session, alias_title: str) -> Tuple[Optional[str], Optional[str]]:
    binding_alias, profile_key, _ = get_universal_model_profile(db, alias_title, modality="llm")
    return binding_alias, profile_key

def invalidate_model_cache(db: Session):
    db.query(GlobalConfig).filter(GlobalConfig.key == "cache_available_models").delete()
    db.commit()
    with _registry_lock:
        _global_client_registry.clear()

    from backend.ws_manager import manager
    manager.broadcast_internal_event_sync("global_model_cache_invalidate", {})

def resolve_model_name(db: Session, requested_model: str, fallback_to_default: bool = True) -> Tuple[str, str]:
    binding_alias, profile_key, _ = get_universal_model_profile(db, requested_model, modality="llm")
    if binding_alias and profile_key:
        return binding_alias, profile_key

    if fallback_to_default:
        default_binding = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).order_by(DBLLMBinding.id).first()
        if default_binding:
            def_alias, def_prof, _ = get_universal_model_profile(db, None, modality="llm")
            target_model = def_prof or default_binding.default_model_name or "default"
            ASCIIColors.warning(f"Universal profile '{requested_model}' not found. Falling back to default: {default_binding.alias}/{target_model}")
            return default_binding.alias, target_model

    raise HTTPException(status_code=400, detail=f"Model profile '{requested_model}' not found. Please use an active universal profile name or 'binding/profile' format.")