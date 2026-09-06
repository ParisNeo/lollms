# backend/routers/admin/bindings_management.py
import json
import io
import base64
import inspect
from typing import List, Dict, Any, Optional
from PIL import Image
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from lollms_client import LollmsClient, list_bindings, get_binding_desc
from backend.lollms_init_watcher import lollms_init_watcher
from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.config import (
    GlobalConfig,
    LLMBinding as DBLLMBinding, 
    TTIBinding as DBTTIBinding, 
    TTSBinding as DBTTSBinding, 
    STTBinding as DBSTTBinding,
    TTVBinding as DBTTVBinding,
    TTMBinding as DBTTMBinding,
    RAGBinding as DBRAGBinding
)
from backend.models import UserAuthDetails, ForceSettingsPayload, ModelInfo, TaskInfo
from backend.models.admin import (
    LLMBindingCreate, LLMBindingUpdate, LLMBindingPublicAdmin,
    TTIBindingCreate, TTIBindingUpdate, TTIBindingPublicAdmin,
    TTSBindingCreate, TTSBindingUpdate, TTSBindingPublicAdmin,
    STTBindingCreate, STTBindingUpdate, STTBindingPublicAdmin,
    TTVBindingCreate, TTVBindingUpdate, TTVBindingPublicAdmin,
    TTMBindingCreate, TTMBindingUpdate, TTMBindingPublicAdmin,
    ModelAliasUpdate, TtiModelAliasUpdate, TtsModelAliasUpdate, SttModelAliasUpdate,
    TtvModelAliasUpdate, TtmModelAliasUpdate,
    ModelAliasDelete, BindingModel, ModelNamePayload
)
from backend.models.personality_generation import GenerateIconRequest
from backend.session import (
    get_current_admin_user,
    user_sessions,
    get_user_lollms_client,
    build_lollms_client_from_params,
    invalidate_model_cache
)
from backend.settings import settings
from backend.ws_manager import manager
from backend.task_manager import task_manager, Task
from backend.utils import get_system_cache, set_system_cache
from ascii_colors import trace_exception, ASCIIColors

bindings_management_router = APIRouter()

class BindingCommandRequest(BaseModel):
    command_name: str
    parameters: Dict[str, Any] = {}

class ZooInstallRequest(BaseModel):
    index: int

class ForceProfilesPayload(BaseModel):
    mode: str = "force_always" # "force_always", "force_once", "set_default", "set_beginner"
    lollms_model_name: Optional[str] = None
    tti_binding_model_name: Optional[str] = None
    tts_binding_model_name: Optional[str] = None
    stt_binding_model_name: Optional[str] = None
    ttv_binding_model_name: Optional[str] = None
    ttm_binding_model_name: Optional[str] = None
    rag_vectorizer_name: Optional[str] = None
    context_size: Optional[int] = None
    vlm_model_profile: Optional[str] = None

def _format_model_alias_dict(alias_data: Any) -> Optional[Dict[str, Any]]:
    if not alias_data:
        return None
    if isinstance(alias_data, dict):
        return alias_data.get('alias', alias_data) if 'alias' in alias_data else alias_data
    return {"title": str(alias_data)}

def _normalize_binding_desc(name: str, desc: Dict[str, Any], binding_type: str = "llm") -> Dict[str, Any]:
    base_info = {
        "name": name,
        "binding_name": name,
        "title": name.replace('_', ' ').title(),
        "input_parameters": [],
        "model_parameters": [],
        "commands": [],
        "description": "",
        "is_degraded": False
    }

    if not desc or not isinstance(desc, dict):
        base_info["is_degraded"] = True
        base_info["description"] = "⚠️ Metadata extraction failed. Binding dependencies might be missing."
        return base_info

    if "error" in desc:
        base_info["is_degraded"] = True
        base_info["description"] = f"⚠️ **Binding Error**: {desc['error']}"
        base_info["name"] = desc.get("name", name)
        base_info["binding_name"] = desc.get("binding_name", name)
        return base_info

    desc['binding_name'] = desc.get('binding_name', name)
    desc['name'] = desc.get('name', name)
    desc['title'] = desc.get('title', desc.get('name', name).replace('_', ' ').title())
        
    if not desc.get('input_parameters'):
        if desc.get('global_input_parameters'):
            desc['input_parameters'] = desc['global_input_parameters']
        elif desc.get('parameters'):
            desc['input_parameters'] = desc['parameters']
        elif desc.get('config'): 
            desc['input_parameters'] = desc['config']
        else:
            desc['input_parameters'] = []
            
    if not desc.get('model_parameters'):
        if desc.get('model_input_parameters'):
            desc['model_parameters'] = desc['model_input_parameters']
        else:
            desc['model_parameters'] = []
        
    return desc

def _process_binding_config(binding_name: str, config: Dict[str, Any], binding_type: str = "llm") -> Dict[str, Any]:
    raw_desc = get_binding_desc(binding_name, binding_type)
    binding_desc = _normalize_binding_desc(binding_name, raw_desc, binding_type)
    
    if "error" in binding_desc:
        return config

    all_params = binding_desc.get("input_parameters", []) + binding_desc.get("model_parameters", [])
    param_types = {p["name"]: p["type"] for p in all_params}
    
    processed_config = {}
    for key, value in config.items():
        if value is None or value == '':
            processed_config[key] = value
            continue

        target_type = param_types.get(key)
        if not target_type:
            processed_config[key] = value
            continue

        try:
            if target_type == 'int':
                processed_config[key] = int(value)
            elif target_type == 'float':
                processed_config[key] = float(value)
            elif target_type == 'bool':
                processed_config[key] = str(value).lower() in ('true', '1', 'yes', 'on')
            else:
                processed_config[key] = value
        except (ValueError, TypeError):
            processed_config[key] = value

    return processed_config

def _get_effective_config(binding_data: Any) -> Dict[str, Any]:
    if isinstance(binding_data, dict):
        config = binding_data.get('config', {}).copy() if binding_data.get('config') else {}
        default_model = binding_data.get('default_model_name')
        model_aliases = binding_data.get('model_aliases')
    else:
        config = binding_data.config.copy() if binding_data.config else {}
        default_model = binding_data.default_model_name
        model_aliases = binding_data.model_aliases

    if default_model and model_aliases:
        try:
            if isinstance(model_aliases, str):
                model_aliases = json.loads(model_aliases)
            
            if isinstance(model_aliases, dict) and default_model in model_aliases:
                alias_wrapper = model_aliases[default_model]
                alias_config = alias_wrapper.get('alias', {}) if isinstance(alias_wrapper, dict) and 'alias' in alias_wrapper else alias_wrapper
                metadata_keys = ['title', 'description', 'icon', 'original_model_name', 'name', 'ctx_size', 'forced_context_size', 'temperature', 'top_k', 'top_p', 'repeat_penalty', 'repeat_last_n', 'reasoning_effort', 'reasoning_activation', 'reasoning_summary', 'has_vision', 'vision_enabled', 'ctx_size_locked', 'allow_parameters_override', 'routing_config', 'vlm_model_profile']
                for k, v in alias_config.items():
                    if k not in metadata_keys and v is not None:
                        config[k] = v
        except Exception as e:
            ASCIIColors.warning(f"Error merging alias config for {default_model}: {e}")
            
    return config

def _get_binding_instance(binding_type: str, binding_name: str, config: Dict[str, Any]):
    safe_config = config.copy() if config else {}
    safe_config['model_name'] = None
    
    if binding_type == "llm":
        return LollmsClient(llm_binding_name=binding_name, llm_binding_config=safe_config, load_llm=True).llm
    elif binding_type == "tti":
        return LollmsClient(tti_binding_name=binding_name, tti_binding_config=safe_config, load_tti=True, load_llm=False).tti
    elif binding_type == "tts":
        return LollmsClient(tts_binding_name=binding_name, tts_binding_config=safe_config, load_tts=True, load_llm=False).tts
    elif binding_type == "stt":
        return LollmsClient(stt_binding_name=binding_name, stt_binding_config=safe_config, load_stt=True, load_llm=False).stt
    elif binding_type == "ttv":
        return LollmsClient(ttv_binding_name=binding_name, ttv_binding_config=safe_config, load_ttv=True, load_llm=False).ttv
    elif binding_type == "ttm":
        return LollmsClient(ttm_binding_name=binding_name, ttm_binding_config=safe_config, load_ttm=True, load_llm=False).ttm
    return None

def _execute_binding_command_task(task: Task, binding_type: str, binding_data: Dict, command_name: str, parameters: Dict[str, Any], username: str):
    task.log(f"Starting execution of command '{command_name}' for {binding_type.upper()} binding '{binding_data['alias']}'...")
    task.set_progress(10)
    try:
        service = None
        if binding_type == "llm":
            lc = build_lollms_client_from_params(username=username, binding_alias=binding_data['alias'], llm_params=None, load_mcp=False, callback=lollms_init_watcher)
            service = lc.llm
        else:
            effective_config = _get_effective_config(binding_data)
            service = _get_binding_instance(binding_type, binding_data['name'], effective_config)
        
        if not service:
             raise Exception(f"{binding_type.upper()} engine could not be initialized.")

        if hasattr(service, command_name):
             method = getattr(service, command_name)
             if callable(method):
                 sig = inspect.signature(method)
                 if 'callback' in sig.parameters:
                     def progress_callback(data: dict):
                         status = data.get('status', 'Processing...')
                         task.log(status)
                         total = data.get('total', 100)
                         completed = data.get('completed', 0)
                         if total > 0:
                             task.set_progress((completed / total) * 100)
                     parameters['callback'] = progress_callback
                 
                 result = method(**parameters)
                 task.log(f"Command '{command_name}' completed successfully.")
                 task.set_progress(100)
                 return result
        
        raise Exception(f"Command '{command_name}' not supported by binding '{binding_data['name']}'.")
    except Exception as e:
        task.log(f"Command execution failed: {e}", "ERROR")
        trace_exception(e)
        raise e

def _get_binding_zoo(binding_record, binding_type: str) -> List[Dict[str, Any]]:
    try:
        config = _get_effective_config(binding_record)
        service = _get_binding_instance(binding_type, binding_record.name, config)
        if not service:
            return []
        if hasattr(service, 'list_models_zoo') and callable(service.list_models_zoo):
            return service.list_models_zoo() or []
        if hasattr(service, 'get_models_zoo') and callable(service.get_models_zoo):
            return service.get_models_zoo() or []
        if hasattr(service, 'models_zoo'):
            zoo = service.models_zoo
            return zoo() if callable(zoo) else (zoo or [])
        return []
    except Exception as e:
        trace_exception(e)
        return []

def _install_from_zoo_task(task: Task, binding_type: str, binding_data: Dict, index: int):
    task.log(f"Installing model index {index} from zoo for {binding_type.upper()} binding '{binding_data['alias']}'...")
    task.set_progress(10)
    try:
        effective_config = _get_effective_config(binding_data)
        service = _get_binding_instance(binding_type, binding_data['name'], effective_config)
        if not service:
            raise Exception(f"{binding_type.upper()} engine could not be initialized.")

        if hasattr(service, 'install_model'):
            method = getattr(service, 'install_model')
            sig = inspect.signature(method)
            kwargs = {}
            if 'callback' in sig.parameters:
                def progress_callback(data: dict):
                    status = data.get('status', 'Downloading/Installing...')
                    task.log(status)
                    total = data.get('total', 100)
                    completed = data.get('completed', 0)
                    if total > 0:
                        task.set_progress((completed / total) * 100)
                kwargs['callback'] = progress_callback

            if 'index' in sig.parameters:
                method(index=index, **kwargs)
            else:
                method(index, **kwargs)
            task.log("Model installed successfully.")
            task.set_progress(100)
            return {"status": "success"}
        raise Exception(f"install_model not supported by {binding_data['name']}")
    except Exception as e:
        task.log(f"Zoo installation failed: {e}", "ERROR")
        trace_exception(e)
        raise e

def _generate_model_icon_task(task: Task, username: str, prompt: str):
    task.log("Starting model icon generation...")
    task.set_progress(10)
    try:
        lc = build_lollms_client_from_params(username=username, load_llm=False, load_tti=True)
        if not lc.tti:
            raise Exception("Text-to-Image service is not configured for this user.")

        task.log("Generating image using TTI engine...")
        img_data = lc.tti.generate_image(prompt, width=512, height=512)
        
        if isinstance(img_data, (list, tuple)):
            img_data = img_data[0]

        if isinstance(img_data, str):
            if img_data.startswith("data:"): img_data = img_data.split(",", 1)[1]
            img_data = base64.b64decode(img_data)

        task.set_progress(80)
        with Image.open(io.BytesIO(img_data)) as img:
            if img.mode not in ("RGB", "RGBA"): img = img.convert("RGBA")
            img.thumbnail((128, 128))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            icon_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        task.log("Icon generated successfully.")
        task.set_progress(100)
        return {"icon_base64": f"data:image/png;base64,{icon_b64}"}
    except Exception as e:
        task.log(f"Icon generation failed: {e}", "ERROR")
        trace_exception(e)
        raise e

# --- Admin API Routes ---

@bindings_management_router.get("/universal-profiles", response_model=Dict[str, Any])
async def get_all_universal_profiles(db: Session = Depends(get_db)):
    """
    Returns all configured universal model profiles across all active bindings.
    Used by the Smart Router composition matrix, policy modals, and dashboard.
    """
    profiles = {}
    active_bindings = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()

    for binding in active_bindings:
        aliases = binding.model_aliases or {}
        if isinstance(aliases, str):
            try: aliases = json.loads(aliases)
            except Exception: aliases = {}

        for orig_name, alias_data in aliases.items():
            if not isinstance(alias_data, dict):
                alias_data = {"title": str(alias_data)}
            cfg = alias_data.get("alias", {}) if "alias" in alias_data else alias_data

            prof_id = f"{binding.alias}/{orig_name}"
            profiles[prof_id] = {
                "id": prof_id,
                "binding_alias": binding.alias,
                "binding_name": binding.name,
                "model_name": cfg.get("model_name") or orig_name,
                "title": cfg.get("title") or cfg.get("name") or orig_name,
                "description": cfg.get("description", ""),
                "vision_enabled": bool(cfg.get("vision_enabled", cfg.get("has_vision", False))),
                "forced_context_size": cfg.get("forced_context_size", cfg.get("ctx_size")),
                "routing_config": cfg.get("routing_config", {
                    "description": cfg.get("description") or cfg.get("title") or orig_name,
                    "complexity_tier": 2,
                    "cost_per_1k_tokens": 0.0,
                    "avg_latency_ms": 200,
                    "priority": 1
                }),
                "vlm_model_profile": cfg.get("vlm_model_profile")
            }

        # Include default model as profile if not aliased
        if binding.default_model_name and f"{binding.alias}/{binding.default_model_name}" not in profiles:
            def_id = f"{binding.alias}/{binding.default_model_name}"
            profiles[def_id] = {
                "id": def_id,
                "binding_alias": binding.alias,
                "binding_name": binding.name,
                "model_name": binding.default_model_name,
                "title": binding.default_model_name,
                "description": f"Default model for {binding.alias}",
                "vision_enabled": False,
                "forced_context_size": None,
                "routing_config": {
                    "description": f"Default engine model {binding.default_model_name}",
                    "complexity_tier": 2,
                    "cost_per_1k_tokens": 0.0,
                    "avg_latency_ms": 200,
                    "priority": 1
                }
            }

    return {"profiles": profiles, "count": len(profiles)}

@bindings_management_router.post("/bindings/migrate-and-heal", response_model=Dict[str, Any])
async def trigger_migration_and_healing(
    db: Session = Depends(get_db),
    current_admin: UserAuthDetails = Depends(get_current_admin_user)
):
    """
    On-demand administrative trigger to upgrade all legacy aliases and heal orphaned user model selections.
    """
    from backend.db.migration import _migrate_model_aliases_to_universal_profiles
    try:
        connection = db.connection()
        _migrate_model_aliases_to_universal_profiles(connection)
        invalidate_model_cache(db)
        manager.broadcast_sync({"type": "bindings_updated"})
        return {"message": "Universal model profile migration and user healing completed successfully."}
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Migration failed: {e}")

@bindings_management_router.get("/bindings/available_types", response_model=List[Dict])
async def get_available_binding_types():
    try:
        names = list_bindings("llm")
        desc_list = []
        for name in names:
            try:
                raw = get_binding_desc(name, "llm")
                desc_list.append(_normalize_binding_desc(name, raw, "llm"))
            except Exception:
                desc_list.append(_normalize_binding_desc(name, None, "llm"))
        return desc_list
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to get available binding types: {e}")

@bindings_management_router.get("/bindings", response_model=List[LLMBindingPublicAdmin])
async def get_all_bindings(db: Session = Depends(get_db)):
    return db.query(DBLLMBinding).all()

@bindings_management_router.post("/bindings", response_model=LLMBindingPublicAdmin, status_code=201)
async def create_binding(binding_data: LLMBindingCreate, db: Session = Depends(get_db)):
    if db.query(DBLLMBinding).filter(DBLLMBinding.alias == binding_data.alias).first():
        raise HTTPException(status_code=400, detail="A binding with this alias already exists.")

    if binding_data.config:
        binding_data.config = _process_binding_config(binding_data.name, binding_data.config, "llm")

    new_binding = DBLLMBinding(**binding_data.model_dump())
    try:
        db.add(new_binding)
        db.commit()
        db.refresh(new_binding)
        invalidate_model_cache(db)
        manager.broadcast_sync({"type": "bindings_updated"})
        return new_binding
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="A binding with this alias already exists.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.put("/bindings/{binding_id}", response_model=LLMBindingPublicAdmin)
async def update_binding(binding_id: int, update_data: LLMBindingUpdate, db: Session = Depends(get_db)):
    binding_to_update = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding_to_update:
        raise HTTPException(status_code=404, detail="Binding not found.")

    if update_data.alias and update_data.alias != binding_to_update.alias:
        if db.query(DBLLMBinding).filter(DBLLMBinding.alias == update_data.alias).first():
            raise HTTPException(status_code=400, detail="A binding with the new alias already exists.")

    update_dict = update_data.model_dump(exclude_unset=True)

    if 'config' in update_dict and update_dict['config'] is not None:
        binding_name = update_dict.get('name', binding_to_update.name)
        update_dict['config'] = _process_binding_config(binding_name, update_dict['config'], "llm")

    for key, value in update_dict.items():
        setattr(binding_to_update, key, value)

    try:
        db.commit()
        db.refresh(binding_to_update)
        invalidate_model_cache(db)
        manager.broadcast_sync({"type": "bindings_updated"})
        return binding_to_update
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.delete("/bindings/{binding_id}", response_model=Dict[str, str])
async def delete_binding(binding_id: int, db: Session = Depends(get_db)):
    binding_to_delete = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding_to_delete:
        raise HTTPException(status_code=404, detail="Binding not found.")

    try:
        db.delete(binding_to_delete)
        db.commit()
        invalidate_model_cache(db)
        manager.broadcast_sync({"type": "bindings_updated"})
        return {"message": "Binding deleted successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.post("/bindings/{binding_id}/execute_command", response_model=TaskInfo, status_code=202)
async def execute_llm_binding_command(
    binding_id: int,
    payload: BindingCommandRequest,
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    binding = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found.")

    binding_data = {
        "id": binding.id,
        "name": binding.name,
        "alias": binding.alias,
        "config": binding.config,
        "default_model_name": binding.default_model_name,
        "model_aliases": binding.model_aliases
    }
    task = task_manager.submit_task(
        name=f"Execute {payload.command_name} on {binding.alias}",
        target=_execute_binding_command_task,
        args=("llm", binding_data, payload.command_name, payload.parameters, current_admin.username),
        description=f"Executing {payload.command_name} on LLM binding {binding.alias}",
        owner_username=current_admin.username
    )
    return task

@bindings_management_router.get("/bindings/{binding_id}/zoo", response_model=List[Dict[str, Any]])
async def get_llm_binding_zoo(binding_id: int, db: Session = Depends(get_db)):
    binding = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found.")
    return _get_binding_zoo(binding, "llm")

@bindings_management_router.post("/bindings/{binding_id}/zoo/install", response_model=TaskInfo, status_code=202)
async def install_llm_binding_zoo(
    binding_id: int,
    payload: ZooInstallRequest,
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    binding = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found.")

    binding_data = {
        "id": binding.id,
        "name": binding.name,
        "alias": binding.alias,
        "config": binding.config,
        "default_model_name": binding.default_model_name,
        "model_aliases": binding.model_aliases
    }
    task = task_manager.submit_task(
        name=f"Install model from zoo on {binding.alias}",
        target=_install_from_zoo_task,
        args=("llm", binding_data, payload.index),
        description=f"Installing zoo model index {payload.index} for LLM binding {binding.alias}",
        owner_username=current_admin.username
    )
    return task

@bindings_management_router.get("/available-models", response_model=List[ModelInfo])
async def get_available_models(
    force_refresh: bool = Query(False, description="Force refresh of the model cache"),
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    if not force_refresh:
        cached_models = get_system_cache(db, "cache_available_models")
        if cached_models:
            return cached_models

    all_models = []
    active_bindings = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()

    for binding in active_bindings:
        try:
            config = _get_effective_config(binding)
            service = _get_binding_instance("llm", binding.name, config)
            raw_models = service.list_models() if (service and hasattr(service, 'list_models')) else []

            aliases = binding.model_aliases or {}
            if isinstance(aliases, str):
                try: aliases = json.loads(aliases)
                except Exception: aliases = {}
            if not isinstance(aliases, dict):
                aliases = {}

            if isinstance(raw_models, list):
                for item in raw_models:
                    model_id = item if isinstance(item, str) else (item.get("name") or item.get("id") or item.get("model_name"))
                    if model_id:
                        alias_data = aliases.get(model_id, {})
                        alias_dict = alias_data.get('alias', alias_data) if isinstance(alias_data, dict) else {"title": str(alias_data)}
                        display_name = alias_dict.get('title') or alias_dict.get('name') or model_id
                        all_models.append({"id": f"{binding.alias}/{model_id}", "name": f"{binding.alias}/{display_name}", "alias": alias_dict if alias_dict else None})

            for orig_name, alias_data in aliases.items():
                alias_dict = alias_data.get('alias', alias_data) if isinstance(alias_data, dict) else {"title": str(alias_data)}
                full_id = f"{binding.alias}/{orig_name}"
                if not any(m["id"] == full_id for m in all_models):
                    display_name = alias_dict.get('title') or alias_dict.get('name') or orig_name
                    all_models.append({"id": full_id, "name": f"{binding.alias}/{display_name}", "alias": alias_dict})
        except Exception:
            continue

    unique_models = {m["id"]: m for m in all_models}
    sorted_models = sorted(list(unique_models.values()), key=lambda x: x['name'])
    set_system_cache(db, "cache_available_models", sorted_models)
    return sorted_models

@bindings_management_router.get("/bindings/{binding_id}/models", response_model=List[BindingModel])
async def get_binding_models(binding_id: int, current_admin: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    binding = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found.")

    return _get_modality_models_list(binding, "llm")

@bindings_management_router.put("/bindings/{binding_id}/alias", response_model=LLMBindingPublicAdmin)
async def update_model_alias(binding_id: int, payload: ModelAliasUpdate, db: Session = Depends(get_db)):
    binding = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found.")

    if binding.model_aliases is None:
        binding.model_aliases = {}
    elif isinstance(binding.model_aliases, str):
        try:
            binding.model_aliases = json.loads(binding.model_aliases)
        except Exception:
            binding.model_aliases = {}

    alias_dict = payload.alias.model_dump()
    alias_dict["binding_profile_name"] = binding.alias
    target_key = payload.original_model_name

    if payload.alias.model_name:
        alias_dict["model_name"] = payload.alias.model_name
    elif payload.new_model_name and payload.new_model_name != payload.original_model_name:
        alias_dict["model_name"] = payload.new_model_name
    else:
        alias_dict["model_name"] = alias_dict.get("model_name") or target_key

    binding.model_aliases[target_key] = alias_dict
    flag_modified(binding, "model_aliases")

    db.commit()
    db.refresh(binding)
    invalidate_model_cache(db)
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding

@bindings_management_router.delete("/bindings/{binding_id}/alias", response_model=LLMBindingPublicAdmin)
async def delete_model_alias(binding_id: int, payload: ModelAliasDelete, db: Session = Depends(get_db)):
    binding = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found.")

    if binding.model_aliases and payload.original_model_name in binding.model_aliases:
        del binding.model_aliases[payload.original_model_name]
        flag_modified(binding, "model_aliases")

    db.commit()
    db.refresh(binding)
    invalidate_model_cache(db)
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding

@bindings_management_router.post("/bindings/{binding_id}/context-size", response_model=Dict[str, Optional[int]])
async def get_model_context_size(binding_id: int, payload: ModelNamePayload, current_admin: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    binding = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found.")

    try:
        config = _get_effective_config(binding)
        safe_config = config.copy() if config else {}
        safe_config['model_name'] = payload.model_name
        service = _get_binding_instance("llm", binding.name, safe_config)
        ctx_size = None
        if service:
            if hasattr(service, 'get_ctx_size') and callable(service.get_ctx_size):
                ctx_size = service.get_ctx_size()
            elif hasattr(service, 'ctx_size'):
                ctx_size = service.ctx_size
            elif hasattr(service, 'config') and isinstance(service.config, dict):
                ctx_size = service.config.get('ctx_size')
        return {"ctx_size": ctx_size}
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Could not probe context size: {e}")

@bindings_management_router.post("/force-profiles", response_model=Dict[str, str])
async def force_model_profiles_action(
    payload: ForceProfilesPayload,
    db: Session = Depends(get_db),
    current_admin: UserAuthDetails = Depends(get_current_admin_user)
):
    target_model = payload.lollms_model_name
    msg_parts = []

    try:
        if target_model:
            if payload.mode == "force_always":
                await admin_update_setting(db, "force_model_mode", "force_always", "string")
                await admin_update_setting(db, "force_model_name", target_model, "string")
                if payload.context_size:
                    await admin_update_setting(db, "force_context_size", payload.context_size, "integer")
                msg_parts.append(f"God Mode LLM: '{target_model}'")

            elif payload.mode == "force_once":
                users = db.query(DBUser).all()
                for u in users:
                    u.lollms_model_name = target_model
                    if payload.context_size:
                        u.llm_ctx_size = payload.context_size
                db.commit()
                msg_parts.append(f"Batch updated {len(users)} users to '{target_model}'")

            elif payload.mode == "set_default":
                await admin_update_setting(db, "default_lollms_model_name", target_model, "string")
                if payload.context_size:
                    await admin_update_setting(db, "default_llm_ctx_size", payload.context_size, "integer")
                msg_parts.append(f"Default LLM: '{target_model}'")

            elif payload.mode == "set_beginner":
                await admin_update_setting(db, "default_lollms_model_name_beginner", target_model, "string")
                beginners = db.query(DBUser).filter(DBUser.user_ui_level == 0).all()
                for u in beginners:
                    u.lollms_model_name = target_model
                db.commit()
                msg_parts.append(f"Beginner default LLM: '{target_model}'")

        if payload.rag_vectorizer_name:
            if payload.mode == "force_always":
                await admin_update_setting(db, "force_rag_settings_mode", "force_always", "string")
                await admin_update_setting(db, "force_rag_vectorizer", payload.rag_vectorizer_name, "string")
                msg_parts.append(f"God Mode RAG: '{payload.rag_vectorizer_name}'")
            elif payload.mode == "force_once":
                users = db.query(DBUser).all()
                for u in users:
                    u.safe_store_vectorizer = payload.rag_vectorizer_name
                db.commit()
                msg_parts.append(f"Batch updated {len(users)} users vectorizer to '{payload.rag_vectorizer_name}'")
            else:
                await admin_update_setting(db, "default_safe_store_vectorizer", payload.rag_vectorizer_name, "string")
                msg_parts.append(f"Default RAG vectorizer: '{payload.rag_vectorizer_name}'")

        if payload.tti_binding_model_name:
            await admin_update_setting(db, "default_tti_binding_model", payload.tti_binding_model_name, "string")
            msg_parts.append(f"Default TTI: '{payload.tti_binding_model_name}'")
        if payload.tts_binding_model_name:
            await admin_update_setting(db, "default_tts_binding_model", payload.tts_binding_model_name, "string")
            msg_parts.append(f"Default TTS: '{payload.tts_binding_model_name}'")
        if payload.stt_binding_model_name:
            await admin_update_setting(db, "default_stt_binding_model", payload.stt_binding_model_name, "string")
            msg_parts.append(f"Default STT: '{payload.stt_binding_model_name}'")
        if payload.ttv_binding_model_name:
            await admin_update_setting(db, "default_ttv_binding_model", payload.ttv_binding_model_name, "string")
            msg_parts.append(f"Default TTV: '{payload.ttv_binding_model_name}'")
        if payload.ttm_binding_model_name:
            await admin_update_setting(db, "default_ttm_binding_model", payload.ttm_binding_model_name, "string")
            msg_parts.append(f"Default TTM: '{payload.ttm_binding_model_name}'")

        user_sessions.clear()
        from backend.settings import settings
        settings.refresh(db)
        manager.broadcast_sync({"type": "settings_updated"})
        return {"message": "Policy Applied: " + (", ".join(msg_parts) if msg_parts else "Settings updated.")}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to apply profile setting: {e}")

async def admin_update_setting(db: Session, key: str, value: Any, val_type: str):
    rec = db.query(GlobalConfig).filter(GlobalConfig.key == key).first()
    json_val = json.dumps({"value": value, "type": val_type})
    if rec:
        rec.value = json_val
    else:
        rec = GlobalConfig(key=key, value=json_val, category="Models", description="Model configuration")
        db.add(rec)
    db.commit()

@bindings_management_router.post("/force-settings-once", response_model=Dict[str, str])
async def force_settings_once(payload: ForceSettingsPayload, db: Session = Depends(get_db)):
    return await force_model_profiles_action(
        ForceProfilesPayload(mode="force_once", lollms_model_name=payload.model_name, context_size=payload.context_size),
        db=db,
        current_admin=None
    )

@bindings_management_router.post("/force-settings-beginners", response_model=Dict[str, str])
async def force_settings_beginners(payload: ForceSettingsPayload, db: Session = Depends(get_db)):
    return await force_model_profiles_action(
        ForceProfilesPayload(mode="set_beginner", lollms_model_name=payload.model_name, context_size=payload.context_size),
        db=db,
        current_admin=None
    )

@bindings_management_router.post("/bindings/generate_icon", response_model=TaskInfo, status_code=202)
async def generate_model_icon(
    payload: GenerateIconRequest,
    current_user: UserAuthDetails = Depends(get_current_admin_user),
):
    task = task_manager.submit_task(
        name="Generate Model Icon",
        target=_generate_model_icon_task,
        args=(current_user.username, payload.prompt),
        description="Generating icon from prompt for model alias.",
        owner_username=current_user.username
    )
    return task

# --- Modality Specific Model Listing & Alias Management ---

def _get_modality_models(
    db: Session,
    binding_model_cls: Any,
    modality_type: str,
    username: str,
    display_mode_setting: str
) -> List[ModelInfo]:
    mode_setting = settings.get(display_mode_setting, "mixed")
    active_bindings = db.query(binding_model_cls).filter(binding_model_cls.is_active == True).all()
    models_list = []

    for binding in active_bindings:
        try:
            config = _get_effective_config(binding)
            service = _get_binding_instance(modality_type, binding.name, config)
            raw_models = service.list_models() if (service and hasattr(service, 'list_models')) else []

            aliases = binding.model_aliases or {}
            if isinstance(aliases, str):
                try: aliases = json.loads(aliases)
                except Exception: aliases = {}
            if not isinstance(aliases, dict):
                aliases = {}

            # Populate models list according to display mode
            for raw_model in (raw_models or []):
                model_name = raw_model if isinstance(raw_model, str) else (raw_model.get("name") or raw_model.get("id") or raw_model.get("model_name"))
                if not model_name: continue

                alias_dict = _format_model_alias_dict(aliases.get(model_name))
                model_id = f"{binding.alias}/{model_name}"

                if mode_setting == 'aliased':
                    if alias_dict and (alias_dict.get('title') or alias_dict.get('name')):
                        models_list.append(ModelInfo(id=model_id, name=alias_dict.get('title') or alias_dict.get('name'), alias=alias_dict))
                elif mode_setting == 'original':
                    models_list.append(ModelInfo(id=model_id, name=model_name, alias=None))
                else: # mixed
                    display_name = alias_dict.get('title') or alias_dict.get('name') or model_name
                    models_list.append(ModelInfo(id=model_id, name=display_name, alias=alias_dict if alias_dict else None))

            # Ensure aliased entries are always present even if raw engine list fails
            for orig_name, alias_data in aliases.items():
                alias_dict = _format_model_alias_dict(alias_data)
                model_id = f"{binding.alias}/{orig_name}"
                if not any(m.id == model_id for m in models_list):
                    display_name = alias_dict.get('title') or alias_dict.get('name') or orig_name
                    models_list.append(ModelInfo(id=model_id, name=display_name, alias=alias_dict))

        except Exception as e:
            trace_exception(e)
            continue

    seen_ids = set()
    deduped_models = []
    for m in models_list:
        if m.id not in seen_ids:
            seen_ids.add(m.id)
            deduped_models.append(m)

    return sorted(deduped_models, key=lambda x: x.name)
def _get_modality_models_list(binding_record, binding_type: str) -> List[BindingModel]:
    try:
        config = _get_effective_config(binding_record)
        service = _get_binding_instance(binding_type, binding_record.name, config)
        raw_models = service.list_models() if hasattr(service, 'list_models') else []

        models_list = []
        if isinstance(raw_models, list):
            for item in raw_models:
                m_id = item if isinstance(item, str) else (item.get("name") or item.get("id") or item.get("model_name"))
                if m_id:
                    models_list.append(m_id)

        model_aliases = binding_record.model_aliases or {}
        if isinstance(model_aliases, str):
            try:
                model_aliases = json.loads(model_aliases)
            except Exception:
                model_aliases = {}

        return [BindingModel(original_model_name=model_name, alias=model_aliases.get(model_name)) for model_name in sorted(models_list)]
    except Exception as e:
        trace_exception(e)
        return []

# TTI
@bindings_management_router.get("/tti-bindings/available_types", response_model=List[Dict])
async def get_available_tti_binding_types():
    try:
        names = list_bindings("tti")
        desc_list = []
        for name in names:
            try:
                raw = get_binding_desc(name, "tti")
                desc_list.append(_normalize_binding_desc(name, raw, "tti"))
            except Exception:
                desc_list.append(_normalize_binding_desc(name, None, "tti"))
        return desc_list
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to get available TTI binding types: {e}")

@bindings_management_router.get("/tti-bindings", response_model=List[TTIBindingPublicAdmin])
async def get_all_tti_bindings(db: Session = Depends(get_db)):
    return db.query(DBTTIBinding).all()

@bindings_management_router.post("/tti-bindings", response_model=TTIBindingPublicAdmin, status_code=201)
async def create_tti_binding(
    binding_data: TTIBindingCreate,
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    if db.query(DBTTIBinding).filter(DBTTIBinding.alias == binding_data.alias).first():
        raise HTTPException(status_code=400, detail="A TTI binding with this alias already exists.")

    if binding_data.config:
        binding_data.config = _process_binding_config(binding_data.name, binding_data.config, "tti")

    new_binding = DBTTIBinding(**binding_data.model_dump())
    try:
        db.add(new_binding)
        db.commit()
        db.refresh(new_binding)
        invalidate_model_cache(db)
        manager.broadcast_sync({"type": "bindings_updated"})
        return new_binding
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="A TTI binding with this alias already exists.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.put("/tti-bindings/{binding_id}", response_model=TTIBindingPublicAdmin)
async def update_tti_binding(
    binding_id: int,
    update_data: TTIBindingUpdate,
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    binding_to_update = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding_to_update:
        raise HTTPException(status_code=404, detail="TTI Binding not found.")

    if update_data.alias and update_data.alias != binding_to_update.alias:
        if db.query(DBTTIBinding).filter(DBTTIBinding.alias == update_data.alias).first():
            raise HTTPException(status_code=400, detail="A TTI binding with the new alias already exists.")

    update_dict = update_data.model_dump(exclude_unset=True)

    if 'config' in update_dict and update_dict['config'] is not None:
        binding_name = update_dict.get('name', binding_to_update.name)
        update_dict['config'] = _process_binding_config(binding_name, update_dict['config'], "tti")

    for key, value in update_dict.items():
        setattr(binding_to_update, key, value)

    try:
        db.commit()
        db.refresh(binding_to_update)
        invalidate_model_cache(db)
        manager.broadcast_sync({"type": "bindings_updated"})
        return binding_to_update
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.delete("/tti-bindings/{binding_id}", response_model=Dict[str, str])
async def delete_tti_binding(
    binding_id: int,
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    binding_to_delete = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding_to_delete:
        raise HTTPException(status_code=404, detail="TTI Binding not found.")

    try:
        db.delete(binding_to_delete)
        db.commit()
        invalidate_model_cache(db)
        manager.broadcast_sync({"type": "bindings_updated"})
        return {"message": "TTI Binding deleted successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.get("/tti-bindings/{binding_id}/models", response_model=List[BindingModel])
async def get_tti_binding_models(binding_id: int, db: Session = Depends(get_db)):
    binding = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="TTI Binding not found.")
    return _get_modality_models_list(binding, "tti")

@bindings_management_router.put("/tti-bindings/{binding_id}/alias", response_model=TTIBindingPublicAdmin)
async def update_tti_model_alias(
    binding_id: int,
    payload: TtiModelAliasUpdate,
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    binding = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="TTI Binding not found.")
    if binding.model_aliases is None:
        binding.model_aliases = {}
    elif isinstance(binding.model_aliases, str):
        try:
            binding.model_aliases = json.loads(binding.model_aliases)
        except Exception:
            binding.model_aliases = {}

    alias_dict = payload.alias.model_dump()
    alias_dict["binding_profile_name"] = binding.alias
    target_key = payload.new_model_name or payload.original_model_name
    alias_dict["model_name"] = target_key

    if payload.new_model_name and payload.new_model_name != payload.original_model_name:
        if payload.original_model_name in binding.model_aliases:
            del binding.model_aliases[payload.original_model_name]

    binding.model_aliases[target_key] = alias_dict
    flag_modified(binding, "model_aliases")
    db.commit()
    db.refresh(binding)
    invalidate_model_cache(db)
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding

@bindings_management_router.delete("/tti-bindings/{binding_id}/alias", response_model=TTIBindingPublicAdmin)
async def delete_tti_model_alias(
    binding_id: int,
    payload: ModelAliasDelete,
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    binding = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="TTI Binding not found.")
    if binding.model_aliases is None:
        binding.model_aliases = {}
    elif isinstance(binding.model_aliases, str):
        try:
            binding.model_aliases = json.loads(binding.model_aliases)
        except Exception:
            binding.model_aliases = {}

    if binding.model_aliases and payload.original_model_name in binding.model_aliases:
        del binding.model_aliases[payload.original_model_name]
        flag_modified(binding, "model_aliases")
    db.commit()
    db.refresh(binding)
    invalidate_model_cache(db)
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding

@bindings_management_router.post("/tti-bindings/{binding_id}/execute_command", response_model=TaskInfo, status_code=202)
async def execute_tti_binding_command(
    binding_id: int,
    payload: BindingCommandRequest,
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    binding = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="TTI Binding not found.")

    binding_data = {
        "id": binding.id,
        "name": binding.name,
        "alias": binding.alias,
        "config": binding.config,
        "default_model_name": binding.default_model_name,
        "model_aliases": binding.model_aliases
    }
    task = task_manager.submit_task(
        name=f"Execute {payload.command_name} on {binding.alias}",
        target=_execute_binding_command_task,
        args=("tti", binding_data, payload.command_name, payload.parameters, current_admin.username),
        description=f"Executing {payload.command_name} on TTI binding {binding.alias}",
        owner_username=current_admin.username
    )
    return task

@bindings_management_router.get("/tti-bindings/{binding_id}/zoo", response_model=List[Dict[str, Any]])
async def get_tti_binding_zoo(binding_id: int, db: Session = Depends(get_db)):
    binding = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="TTI Binding not found.")
    return _get_binding_zoo(binding, "tti")

@bindings_management_router.post("/tti-bindings/{binding_id}/zoo/install", response_model=TaskInfo, status_code=202)
async def install_tti_binding_zoo(
    binding_id: int,
    payload: ZooInstallRequest,
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    binding = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="TTI Binding not found.")

    binding_data = {
        "id": binding.id,
        "name": binding.name,
        "alias": binding.alias,
        "config": binding.config,
        "default_model_name": binding.default_model_name,
        "model_aliases": binding.model_aliases
    }
    task = task_manager.submit_task(
        name=f"Install model from zoo on {binding.alias}",
        target=_install_from_zoo_task,
        args=("tti", binding_data, payload.index),
        description=f"Installing zoo model index {payload.index} for TTI binding {binding.alias}",
        owner_username=current_admin.username
    )
    return task

# TTS
@bindings_management_router.get("/tts-bindings", response_model=List[TTSBindingPublicAdmin])
async def get_all_tts_bindings(db: Session = Depends(get_db)): return db.query(DBTTSBinding).all()

@bindings_management_router.get("/tts-bindings/{binding_id}/models", response_model=List[BindingModel])
async def get_tts_binding_models(binding_id: int, db: Session = Depends(get_db)):
    binding = db.query(DBTTSBinding).filter(DBTTSBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="TTS Binding not found.")
    return _get_modality_models_list(binding, "tts")

@bindings_management_router.put("/tts-bindings/{binding_id}/alias", response_model=TTSBindingPublicAdmin)
async def update_tts_model_alias(binding_id: int, payload: TtsModelAliasUpdate, db: Session = Depends(get_db)):
    binding = db.query(DBTTSBinding).filter(DBTTSBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="TTS Binding not found.")
    if binding.model_aliases is None: binding.model_aliases = {}
    binding.model_aliases[payload.original_model_name] = payload.alias.model_dump()
    flag_modified(binding, "model_aliases")
    db.commit(); db.refresh(binding)
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding

@bindings_management_router.delete("/tts-bindings/{binding_id}/alias", response_model=TTSBindingPublicAdmin)
async def delete_tts_model_alias(binding_id: int, payload: ModelAliasDelete, db: Session = Depends(get_db)):
    binding = db.query(DBTTSBinding).filter(DBTTSBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="TTS Binding not found.")
    if binding.model_aliases and payload.original_model_name in binding.model_aliases:
        del binding.model_aliases[payload.original_model_name]
        flag_modified(binding, "model_aliases")
    db.commit(); db.refresh(binding)
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding

# STT
@bindings_management_router.get("/stt-bindings", response_model=List[STTBindingPublicAdmin])
async def get_all_stt_bindings(db: Session = Depends(get_db)): return db.query(DBSTTBinding).all()

@bindings_management_router.get("/stt-bindings/{binding_id}/models", response_model=List[BindingModel])
async def get_stt_binding_models(binding_id: int, db: Session = Depends(get_db)):
    binding = db.query(DBSTTBinding).filter(DBSTTBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="STT Binding not found.")
    return _get_modality_models_list(binding, "stt")

@bindings_management_router.put("/stt-bindings/{binding_id}/alias", response_model=STTBindingPublicAdmin)
async def update_stt_model_alias(binding_id: int, payload: SttModelAliasUpdate, db: Session = Depends(get_db)):
    binding = db.query(DBSTTBinding).filter(DBSTTBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="STT Binding not found.")
    if binding.model_aliases is None: binding.model_aliases = {}
    binding.model_aliases[payload.original_model_name] = payload.alias.model_dump()
    flag_modified(binding, "model_aliases")
    db.commit(); db.refresh(binding)
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding

@bindings_management_router.delete("/stt-bindings/{binding_id}/alias", response_model=STTBindingPublicAdmin)
async def delete_stt_model_alias(binding_id: int, payload: ModelAliasDelete, db: Session = Depends(get_db)):
    binding = db.query(DBSTTBinding).filter(DBSTTBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="STT Binding not found.")
    if binding.model_aliases and payload.original_model_name in binding.model_aliases:
        del binding.model_aliases[payload.original_model_name]
        flag_modified(binding, "model_aliases")
    db.commit(); db.refresh(binding)
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding

# TTV
@bindings_management_router.get("/ttv-bindings", response_model=List[TTVBindingPublicAdmin])
async def get_all_ttv_bindings(db: Session = Depends(get_db)): return db.query(DBTTVBinding).all()

@bindings_management_router.get("/ttv-bindings/{binding_id}/models", response_model=List[BindingModel])
async def get_ttv_binding_models(binding_id: int, db: Session = Depends(get_db)):
    binding = db.query(DBTTVBinding).filter(DBTTVBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="TTV Binding not found.")
    return _get_modality_models_list(binding, "ttv")

@bindings_management_router.put("/ttv-bindings/{binding_id}/alias", response_model=TTVBindingPublicAdmin)
async def update_ttv_model_alias(binding_id: int, payload: TtvModelAliasUpdate, db: Session = Depends(get_db)):
    binding = db.query(DBTTVBinding).filter(DBTTVBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="TTV Binding not found.")
    if binding.model_aliases is None: binding.model_aliases = {}
    binding.model_aliases[payload.original_model_name] = payload.alias.model_dump()
    flag_modified(binding, "model_aliases")
    db.commit(); db.refresh(binding)
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding

@bindings_management_router.delete("/ttv-bindings/{binding_id}/alias", response_model=TTVBindingPublicAdmin)
async def delete_ttv_model_alias(binding_id: int, payload: ModelAliasDelete, db: Session = Depends(get_db)):
    binding = db.query(DBTTVBinding).filter(DBTTVBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="TTV Binding not found.")
    if binding.model_aliases and payload.original_model_name in binding.model_aliases:
        del binding.model_aliases[payload.original_model_name]
        flag_modified(binding, "model_aliases")
    db.commit(); db.refresh(binding)
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding

# TTM
@bindings_management_router.get("/ttm-bindings", response_model=List[TTMBindingPublicAdmin])
async def get_all_ttm_bindings(db: Session = Depends(get_db)): return db.query(DBTTMBinding).all()

@bindings_management_router.get("/ttm-bindings/{binding_id}/models", response_model=List[BindingModel])
async def get_ttm_binding_models(binding_id: int, db: Session = Depends(get_db)):
    binding = db.query(DBTTMBinding).filter(DBTTMBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="TTM Binding not found.")
    return _get_modality_models_list(binding, "ttm")

@bindings_management_router.put("/ttm-bindings/{binding_id}/alias", response_model=TTMBindingPublicAdmin)
async def update_ttm_model_alias(binding_id: int, payload: TtmModelAliasUpdate, db: Session = Depends(get_db)):
    binding = db.query(DBTTMBinding).filter(DBTTMBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="TTM Binding not found.")
    if binding.model_aliases is None: binding.model_aliases = {}
    binding.model_aliases[payload.original_model_name] = payload.alias.model_dump()
    flag_modified(binding, "model_aliases")
    db.commit(); db.refresh(binding)
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding

@bindings_management_router.delete("/ttm-bindings/{binding_id}/alias", response_model=TTMBindingPublicAdmin)
async def delete_ttm_model_alias(binding_id: int, payload: ModelAliasDelete, db: Session = Depends(get_db)):
    binding = db.query(DBTTMBinding).filter(DBTTMBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="TTM Binding not found.")
    if binding.model_aliases and payload.original_model_name in binding.model_aliases:
        del binding.model_aliases[payload.original_model_name]
        flag_modified(binding, "model_aliases")
    db.commit(); db.refresh(binding)
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding