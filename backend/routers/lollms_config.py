# [UPDATE] backend/routers/lollms_config.py
# backend/routers/lollms_config.py
import json
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from lollms_client import LollmsClient
from ascii_colors import trace_exception
from lollms_client.lollms_tti_binding import get_available_bindings as get_available_tti_bindings
from lollms_client.lollms_tts_binding import get_available_bindings as get_available_tts_bindings
from lollms_client.lollms_stt_binding import get_available_bindings as get_available_stt_bindings
from lollms_client.lollms_llm_binding import list_binding_models as list_llm_binding_models
from lollms_client.lollms_tti_binding import list_binding_models as list_tti_binding_models
from lollms_client.lollms_tts_binding import list_binding_models as list_tts_binding_models
from lollms_client.lollms_stt_binding import list_binding_models as list_stt_binding_models


from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.config import LLMBinding as DBLLMBinding, TTIBinding as DBTTIBinding, TTSBinding as DBTTSBinding, STTBinding as DBSTTBinding
from backend.session import get_current_active_user, get_user_lollms_client, user_sessions, build_lollms_client_from_params
from backend.models import UserLLMParams, UserAuthDetails
from backend.models.shared import ModelInfo
from backend.settings import settings

lollms_config_router = APIRouter(prefix="/api/config", tags=["LoLLMs Configuration"])

class ModelInfo(BaseModel):
    id: str
    name: str
    alias: Optional[Dict[str, Any]] = None
    binding_params: Optional[Dict[str, List[Dict[str, Any]]]] = None

@lollms_config_router.get("/lollms-models", response_model=List[ModelInfo])
async def get_lollms_models(
    db: Session = Depends(get_db)
):
    all_models = []
    active_bindings = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()
    model_display_mode = settings.get("model_display_mode", "mixed")

    for binding in active_bindings:
        try:
            models_from_binding = list_llm_binding_models(llm_binding_name=binding.name, llm_binding_config=binding.config)
            
            raw_model_names = []
            if isinstance(models_from_binding, list):
                for item in models_from_binding:
                    model_id = None
                    if isinstance(item, str): model_id = item
                    elif isinstance(item, dict): model_id = item.get("name") or item.get("id") or item.get("model_name")
                    if model_id: raw_model_names.append(model_id)

            model_aliases = binding.model_aliases or {}
            if isinstance(model_aliases, str):
                try:
                    model_aliases = json.loads(model_aliases)
                except Exception:
                    model_aliases = {}

            for model_name in raw_model_names:
                alias_data = model_aliases.get(model_name)
                
                if model_display_mode == 'aliased' and not alias_data:
                    continue
                
                display_name = f"{binding.alias}/{model_name}"

                if alias_data and (model_display_mode == 'mixed' or model_display_mode == 'aliased'):
                    display_name = alias_data.get('title', model_name)

                model_info = {
                    "id": f"{binding.alias}/{model_name}",
                    "name": display_name,
                    "alias": alias_data
                }

                all_models.append(model_info)

        except Exception as e:
            print(f"WARNING: Could not fetch models from binding '{binding.alias}': {e}")
            continue

    return sorted(all_models, key=lambda x: x['name'])

@lollms_config_router.get("/tti-models", response_model=List[ModelInfo])
async def get_lollms_tti_models(
    db: Session = Depends(get_db)
):
    """
    Lists all available Text-to-Image models from all active TTI bindings.
    """
    all_models = []
    active_tti_bindings = db.query(DBTTIBinding).filter(DBTTIBinding.is_active == True).all()
    model_display_mode = settings.get("tti_model_display_mode", "mixed")

    try:
        available_binding_descs = {b['binding_name']: b for b in get_available_tti_bindings()}
    except Exception as e:
        trace_exception(e)
        available_binding_descs = {}

    for binding in active_tti_bindings:
        try:
            models_from_binding = list_tti_binding_models(tti_binding_name=binding.name, tti_binding_config=binding.config)
            
            raw_model_names = []
            if isinstance(models_from_binding, list):
                for item in models_from_binding:
                    model_id = item if isinstance(item, str) else item.get("model_name")
                    if model_id: raw_model_names.append(model_id)
            
            model_aliases = binding.model_aliases or {}
            if isinstance(model_aliases, str):
                try:
                    model_aliases = json.loads(model_aliases)
                except Exception:
                    model_aliases = {}
            
            binding_desc = available_binding_descs.get(binding.name)

            for model_name in raw_model_names:
                alias_data = model_aliases.get(model_name)
                
                if model_display_mode == 'aliased' and not alias_data:
                    continue

                display_name = f"{binding.alias}/{model_name}"
                if alias_data and (model_display_mode == 'mixed' or model_display_mode == 'aliased'):
                    display_name = alias_data.get('title', model_name)

                binding_params = {}
                if binding_desc:
                    binding_params['class_parameters'] = binding_desc.get('input_parameters', [])
                    binding_params['generation_parameters'] = binding_desc.get('generate_image_parameters', [])
                    binding_params['edit_parameters'] = binding_desc.get('edit_image_parameters', [])

                model_info = {
                    "id": f"{binding.alias}/{model_name}",
                    "name": display_name,
                    "alias": alias_data,
                    "binding_params": binding_params,
                }

                all_models.append(model_info)

        except Exception as e:
            print(f"WARNING: Could not fetch TTI models from binding '{binding.alias}': {e}")
            trace_exception(e)
            continue

    return sorted(all_models, key=lambda x: x['name'])


@lollms_config_router.post("/lollms-model")
async def set_user_lollms_model(model_name: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    db_user_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user_record:
        raise HTTPException(status_code=404, detail="User not found.")
    user_sessions[current_user.username]["lollms_model_name"] = model_name
    user_sessions[current_user.username]["lollms_clients_cache"] = {}
    db_user_record.lollms_model_name = model_name
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    return {"message": f"Default LoLLMs model set to '{model_name}'. Client will re-initialize."}

@lollms_config_router.post("/llm-params")
async def set_user_llm_params(params: UserLLMParams, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    db_user_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user_record:
        raise HTTPException(status_code=404, detail="User not found.")
    session_llm_params = user_sessions[current_user.username].get("llm_params", {})
    db_updated = session_updated = False
    for key, value in params.model_dump(exclude_unset=True).items():
        db_key = key
        session_key = key.replace('llm_', '')
        if getattr(db_user_record, db_key) != value:
            setattr(db_user_record, db_key, value)
            db_updated = True
        if session_llm_params.get(session_key) != value:
            session_llm_params[session_key] = value
            session_updated = True
    if db_updated:
        try:
            db.commit()
        except:
            db.rollback()
            raise
    if session_updated:
        user_sessions[current_user.username]["llm_params"] = {k: v for k, v in session_llm_params.items() if v is not None}
        user_sessions[current_user.username]["lollms_clients_cache"] = {}
        return {"message": "LLM parameters updated. Client will re-initialize."}
    return {"message": "No changes to LLM parameters."}


@lollms_config_router.get("/tts-models", response_model=List[ModelInfo])
async def get_tts_models(
    db: Session = Depends(get_db)
):
    all_models = []
    active_bindings = db.query(DBTTSBinding).filter(DBTTSBinding.is_active == True).all()
    model_display_mode = settings.get("tts_model_display_mode", "mixed")
    
    try:
        available_binding_descs = {b['binding_name']: b for b in get_available_tts_bindings()}
    except Exception as e:
        trace_exception(e)
        available_binding_descs = {}

    for binding in active_bindings:
        model_aliases = binding.model_aliases or {}
        if isinstance(model_aliases, str):
            try:
                model_aliases = json.loads(model_aliases)
            except Exception:
                model_aliases = {}
        try:
            models = list_tts_binding_models(tts_binding_name=binding.name, tts_binding_config=binding.config)
            
            if isinstance(models, list):
                for item in models:
                    model_id = item if isinstance(item, str) else (item.get("id") or item.get("model_name"))
                    if model_id:
                        alias_data = model_aliases.get(model_id)
                        
                        if model_display_mode == 'aliased' and not alias_data:
                            continue

                        display_name = f"{binding.alias}/{model_id}"
                        if alias_data and (model_display_mode == 'mixed' or model_display_mode == 'aliased'):
                            display_name = alias_data.get('title', model_id)

                        binding_desc = available_binding_descs.get(binding.name)
                        binding_params = {}
                        if binding_desc:
                            binding_params['class_parameters'] = binding_desc.get('input_parameters', [])
                            binding_params['generation_parameters'] = binding_desc.get('synthesize_audio_parameters', [])

                        model_info = {
                            "id": f"{binding.alias}/{model_id}",
                            "name": display_name,
                            "alias": alias_data,
                            "binding_params": binding_params,
                        }

                        all_models.append(model_info)
        except Exception as e:
            print(f"WARNING: Could not fetch TTS models from binding '{binding.alias}': {e}")
            trace_exception(e)
            continue
            
    unique_models = {m["id"]: m for m in all_models}
    return sorted(list(unique_models.values()), key=lambda x: x['name'])

@lollms_config_router.get("/stt-models", response_model=List[ModelInfo])
async def get_stt_models(
    db: Session = Depends(get_db)
):
    all_models = []
    active_bindings = db.query(DBSTTBinding).filter(DBSTTBinding.is_active == True).all()
    model_display_mode = settings.get("stt_model_display_mode", "mixed")
    
    try:
        available_binding_descs = {b['binding_name']: b for b in get_available_stt_bindings()}
    except Exception as e:
        trace_exception(e)
        available_binding_descs = {}

    for binding in active_bindings:
        model_aliases = binding.model_aliases or {}
        if isinstance(model_aliases, str):
            try:
                model_aliases = json.loads(model_aliases)
            except Exception:
                model_aliases = {}
        try:
            models = list_stt_binding_models(stt_binding_name=binding.name, stt_binding_config=binding.config)
            
            if isinstance(models, list):
                for item in models:
                    model_id = item if isinstance(item, str) else (item.get("id") or item.get("model_name"))
                    if model_id:
                        alias_data = model_aliases.get(model_id)
                        
                        if model_display_mode == 'aliased' and not alias_data:
                            continue

                        display_name = f"{binding.alias}/{model_id}"
                        if alias_data and (model_display_mode == 'mixed' or model_display_mode == 'aliased'):
                            display_name = alias_data.get('title', model_id)

                        binding_desc = available_binding_descs.get(binding.name)
                        binding_params = {}
                        if binding_desc:
                            binding_params['class_parameters'] = binding_desc.get('input_parameters', [])
                            binding_params['generation_parameters'] = binding_desc.get('transcribe_audio_parameters', [])

                        model_info = {
                            "id": f"{binding.alias}/{model_id}",
                            "name": display_name,
                            "alias": alias_data,
                            "binding_params": binding_params,
                        }

                        all_models.append(model_info)
        except Exception as e:
            print(f"WARNING: Could not fetch STT models from binding '{binding.alias}': {e}")
            trace_exception(e)
            continue
            
    unique_models = {m["id"]: m for m in all_models}
    return sorted(list(unique_models.values()), key=lambda x: x['name'])