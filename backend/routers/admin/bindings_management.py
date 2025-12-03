# [UPDATE] backend/routers/admin/bindings_management.py
import json
import io
import base64
import inspect
from typing import List, Dict, Any, Optional
from PIL import Image
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import IntegrityError
from lollms_client import LollmsClient
from lollms_client.lollms_llm_binding import get_available_bindings
from lollms_client.lollms_tti_binding import get_available_bindings as get_available_tti_bindings
from lollms_client.lollms_tts_binding import get_available_bindings as get_available_tts_bindings
from lollms_client.lollms_stt_binding import get_available_bindings as get_available_stt_bindings

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.config import LLMBinding as DBLLMBinding, TTIBinding as DBTTIBinding, TTSBinding as DBTTSBinding, STTBinding as DBSTTBinding
from backend.models import UserAuthDetails, ForceSettingsPayload, ModelInfo, TaskInfo
from backend.models.admin import (
    LLMBindingCreate, LLMBindingUpdate, LLMBindingPublicAdmin,
    TTIBindingCreate, TTIBindingUpdate, TTIBindingPublicAdmin,
    TTSBindingCreate, TTSBindingUpdate, TTSBindingPublicAdmin,
    STTBindingCreate, STTBindingUpdate, STTBindingPublicAdmin,
    ModelAliasUpdate, TtiModelAliasUpdate, TtsModelAliasUpdate, SttModelAliasUpdate,
    ModelAliasDelete, BindingModel, ModelNamePayload
)
from backend.models.personality_generation import GenerateIconRequest
from backend.session import (
    get_current_admin_user,
    user_sessions,
    get_user_lollms_client,
    build_lollms_client_from_params
)
from backend.ws_manager import manager
from backend.task_manager import task_manager, Task
from ascii_colors import trace_exception, ASCIIColors

bindings_management_router = APIRouter()

class BindingCommandRequest(BaseModel):
    command_name: str
    parameters: Dict[str, Any] = {}

def _process_binding_config(binding_name: str, config: Dict[str, Any], binding_type: str = "llm") -> Dict[str, Any]:
    """Casts config values to their correct types based on binding description."""
    if binding_type == "llm":
        available_bindings = get_available_bindings()
    elif binding_type == "tti":
        available_bindings = get_available_tti_bindings()
    elif binding_type == "stt":
        available_bindings = get_available_stt_bindings()
    else: # tts
        available_bindings = get_available_tts_bindings()
        
    binding_desc = next((b for b in available_bindings if b.get("binding_name") == binding_name), None)
    
    parameters_key = "input_parameters"
    if binding_type in ["tti", "tts", "stt"] and binding_desc and "model_parameters" in binding_desc:
        parameters_key = "model_parameters"

    if not binding_desc or parameters_key not in binding_desc:
        return config

    param_types = {p["name"]: p["type"] for p in binding_desc[parameters_key]}
    
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
            ASCIIColors.warning(f"Could not cast config value '{value}' for key '{key}' to type '{target_type}'. Keeping original value.")
            processed_config[key] = value

    return processed_config

def _execute_binding_command_task(task: Task, binding_type: str, binding_data: Dict, command_name: str, parameters: Dict[str, Any], username: str):
    task.log(f"Starting execution of command '{command_name}' for {binding_type.upper()} binding '{binding_data['alias']}'...")
    task.set_progress(10)
    
    try:
        service = None
        if binding_type == "llm":
            # For LLM, we leverage the user's existing client context to ensure loaded models are reused if possible
            lc = get_user_lollms_client(username, binding_data['alias'])
            service = lc.llm
        elif binding_type == "tti":
            client_params = { "tti_binding_name": binding_data['name'], "tti_binding_config": { **binding_data['config'], "model_name": binding_data['default_model_name'] } }
            lc = LollmsClient(**client_params)
            service = lc.tti
        elif binding_type == "tts":
            client_params = { "tts_binding_name": binding_data['name'], "tts_binding_config": { **binding_data['config'], "model_name": binding_data['default_model_name'] } }
            lc = LollmsClient(**client_params)
            service = lc.tts
        elif binding_type == "stt":
            client_params = { "stt_binding_name": binding_data['name'], "stt_binding_config": { **binding_data['config'], "model_name": binding_data['default_model_name'] } }
            lc = LollmsClient(**client_params)
            service = lc.stt
        else:
            raise ValueError(f"Unknown binding type: {binding_type}")

        if not service:
             raise Exception(f"{binding_type.upper()} engine could not be initialized. Please check configuration.")

        if hasattr(service, command_name):
             method = getattr(service, command_name)
             if callable(method):
                 task.log(f"Executing method: {command_name}")
                 
                 # Check signature for callback
                 sig = inspect.signature(method)
                 if 'callback' in sig.parameters:
                     def progress_callback(data: dict):
                         # Expected format: {'status': str, 'completed': int, 'total': int}
                         status = data.get('status', 'Processing...')
                         task.log(status)
                         
                         total = data.get('total', 100)
                         completed = data.get('completed', 0)
                         if total > 0:
                             percent = (completed / total) * 100
                             task.set_progress(percent)
                             
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

def _generate_model_icon_task(task: Task, username: str, prompt: str):
    task.log("Starting model icon generation...")
    task.set_progress(10)
    
    try:
        lc = get_user_lollms_client(username)
        if not lc.tti:
            raise Exception("Text-to-Image service is not configured for this user.")

        task.log("Generating image using TTI engine...")
        # Generate image as raw bytes (not base64)
        img_data = lc.tti.generate_image(prompt, width=512, height=512)
        
        # If API returns a list, pick the first
        if isinstance(img_data, (list, tuple)):
            if not img_data:
                raise Exception("Image generation returned empty list.")
            img_data = img_data[0]

        # If the provider sometimes returns a data URI or base64 str, normalize:
        if isinstance(img_data, str):
            # Remove any data URI prefix if present
            if img_data.startswith("data:"):
                img_data = img_data.split(",", 1)[1]
            # Base64 string -> raw bytes
            img_data = base64.b64decode(img_data)

        if not isinstance(img_data, (bytes, bytearray)):
            raise Exception(f"Unsupported image payload type from generator: {type(img_data)}")

        task.set_progress(80)
        task.log("Processing image...")

        with Image.open(io.BytesIO(img_data)) as img:
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
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

@bindings_management_router.get("/bindings/available_types", response_model=List[Dict])
async def get_available_binding_types():
    try:
        return get_available_bindings()
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
        manager.broadcast_sync({"type": "bindings_updated"})
        return {"message": "Binding deleted successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.post("/bindings/{binding_id}/execute_command", response_model=TaskInfo, status_code=202)
async def execute_llm_binding_command(binding_id: int, payload: BindingCommandRequest, current_user: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    binding = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="Binding not found.")
    
    binding_data = {
        "id": binding.id,
        "name": binding.name,
        "alias": binding.alias,
        "config": binding.config,
        "default_model_name": binding.default_model_name
    }
    
    task = task_manager.submit_task(
        name=f"Exec LLM Cmd: {payload.command_name}",
        target=_execute_binding_command_task,
        args=("llm", binding_data, payload.command_name, payload.parameters, current_user.username),
        description=f"Executing command {payload.command_name} on binding {binding.alias}",
        owner_username=current_user.username
    )
    return task

@bindings_management_router.get("/tti-bindings/available_types", response_model=List[Dict])
async def get_available_tti_binding_types():
    try:
        return get_available_tti_bindings()
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to get available TTI binding types: {e}")

@bindings_management_router.get("/tti-bindings", response_model=List[TTIBindingPublicAdmin])
async def get_all_tti_bindings(db: Session = Depends(get_db)):
    return db.query(DBTTIBinding).all()

@bindings_management_router.post("/tti-bindings", response_model=TTIBindingPublicAdmin, status_code=201)
async def create_tti_binding(binding_data: TTIBindingCreate, db: Session = Depends(get_db)):
    if db.query(DBTTIBinding).filter(DBTTIBinding.alias == binding_data.alias).first():
        raise HTTPException(status_code=400, detail="A TTI binding with this alias already exists.")
    
    if binding_data.config:
        binding_data.config = _process_binding_config(binding_data.name, binding_data.config, "tti")

    new_binding = DBTTIBinding(**binding_data.model_dump())
    try:
        db.add(new_binding)
        db.commit()
        db.refresh(new_binding)
        manager.broadcast_sync({"type": "bindings_updated"})
        return new_binding
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="A TTI binding with this alias already exists.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.put("/tti-bindings/{binding_id}", response_model=TTIBindingPublicAdmin)
async def update_tti_binding(binding_id: int, update_data: TTIBindingUpdate, db: Session = Depends(get_db)):
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
        manager.broadcast_sync({"type": "bindings_updated"})
        return binding_to_update
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.delete("/tti-bindings/{binding_id}", response_model=Dict[str, str])
async def delete_tti_binding(binding_id: int, db: Session = Depends(get_db)):
    binding_to_delete = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding_to_delete:
        raise HTTPException(status_code=404, detail="TTI Binding not found.")
    
    try:
        db.delete(binding_to_delete)
        db.commit()
        manager.broadcast_sync({"type": "bindings_updated"})
        return {"message": "TTI Binding deleted successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.post("/tti-bindings/{binding_id}/execute_command", response_model=TaskInfo, status_code=202)
async def execute_tti_binding_command(binding_id: int, payload: BindingCommandRequest, current_user: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    binding = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="TTI Binding not found.")
    
    binding_data = {
        "id": binding.id,
        "name": binding.name,
        "alias": binding.alias,
        "config": binding.config,
        "default_model_name": binding.default_model_name
    }
    
    task = task_manager.submit_task(
        name=f"Exec TTI Cmd: {payload.command_name}",
        target=_execute_binding_command_task,
        args=("tti", binding_data, payload.command_name, payload.parameters, current_user.username),
        description=f"Executing command {payload.command_name} on binding {binding.alias}",
        owner_username=current_user.username
    )
    return task

@bindings_management_router.get("/tti-bindings/{binding_id}/models", response_model=List[BindingModel])
async def get_tti_binding_models(binding_id: int, db: Session = Depends(get_db)):
    binding = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="TTI Binding not found.")
    
    try:
        client_params = { "tti_binding_name": binding.name, "tti_binding_config": { **binding.config, "model_name": binding.default_model_name } }
        lc = LollmsClient(**client_params)
        if not lc.tti:
            raise Exception("Could not build a tti instance from the configuration. make sure you have set all configuration parameters correctly")
        raw_models = lc.tti.list_models()
        
        models_list = [item if isinstance(item, str) else item.get("model_name") for item in raw_models if (isinstance(item, str) or item.get("model_name"))]
        model_aliases = binding.model_aliases or {}
        if isinstance(model_aliases, str):
            try: model_aliases = json.loads(model_aliases)
            except (json.JSONDecodeError, TypeError): model_aliases = {}
        
        return [BindingModel(original_model_name=model_name, alias=model_aliases.get(model_name)) for model_name in sorted(models_list)]
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Could not fetch models from TTI binding '{binding.alias}': {e}")

@bindings_management_router.put("/tti-bindings/{binding_id}/alias", response_model=TTIBindingPublicAdmin)
async def update_tti_model_alias(binding_id: int, payload: TtiModelAliasUpdate, db: Session = Depends(get_db)):
    binding = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="TTI Binding not found.")
    
    if binding.model_aliases is None:
        binding.model_aliases = {}
    
    binding.model_aliases[payload.original_model_name] = payload.alias
    flag_modified(binding, "model_aliases")
    
    db.commit()
    db.refresh(binding)
    return binding

@bindings_management_router.delete("/tti-bindings/{binding_id}/alias", response_model=TTIBindingPublicAdmin)
async def delete_tti_model_alias(binding_id: int, payload: ModelAliasDelete, db: Session = Depends(get_db)):
    binding = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="TTI Binding not found.")
        
    if binding.model_aliases and payload.original_model_name in binding.model_aliases:
        del binding.model_aliases[payload.original_model_name]
        flag_modified(binding, "model_aliases")
    
    db.commit()
    db.refresh(binding)
    return binding

@bindings_management_router.get("/tts-bindings/available_types", response_model=List[Dict])
async def get_available_tts_binding_types():
    try:
        return get_available_tts_bindings()
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to get available TTS binding types: {e}")

@bindings_management_router.get("/tts-bindings", response_model=List[TTSBindingPublicAdmin])
async def get_all_tts_bindings(db: Session = Depends(get_db)):
    return db.query(DBTTSBinding).all()

@bindings_management_router.post("/tts-bindings", response_model=TTSBindingPublicAdmin, status_code=201)
async def create_tts_binding(binding_data: TTSBindingCreate, db: Session = Depends(get_db)):
    if db.query(DBTTSBinding).filter(DBTTSBinding.alias == binding_data.alias).first():
        raise HTTPException(status_code=400, detail="A TTS binding with this alias already exists.")
    
    if binding_data.config:
        binding_data.config = _process_binding_config(binding_data.name, binding_data.config, "tts")

    new_binding = DBTTSBinding(**binding_data.model_dump())
    try:
        db.add(new_binding)
        db.commit()
        db.refresh(new_binding)
        manager.broadcast_sync({"type": "bindings_updated"})
        return new_binding
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="A TTS binding with this alias already exists.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.put("/tts-bindings/{binding_id}", response_model=TTSBindingPublicAdmin)
async def update_tts_binding(binding_id: int, update_data: TTSBindingUpdate, db: Session = Depends(get_db)):
    binding_to_update = db.query(DBTTSBinding).filter(DBTTSBinding.id == binding_id).first()
    if not binding_to_update:
        raise HTTPException(status_code=404, detail="TTS Binding not found.")
    
    if update_data.alias and update_data.alias != binding_to_update.alias:
        if db.query(DBTTSBinding).filter(DBTTSBinding.alias == update_data.alias).first():
            raise HTTPException(status_code=400, detail="A TTS binding with the new alias already exists.")

    update_dict = update_data.model_dump(exclude_unset=True)

    if 'config' in update_dict and update_dict['config'] is not None:
        binding_name = update_dict.get('name', binding_to_update.name)
        update_dict['config'] = _process_binding_config(binding_name, update_dict['config'], "tts")

    for key, value in update_dict.items():
        setattr(binding_to_update, key, value)
    
    try:
        db.commit()
        db.refresh(binding_to_update)
        manager.broadcast_sync({"type": "bindings_updated"})
        return binding_to_update
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.delete("/tts-bindings/{binding_id}", response_model=Dict[str, str])
async def delete_tts_binding(binding_id: int, db: Session = Depends(get_db)):
    binding_to_delete = db.query(DBTTSBinding).filter(DBTTSBinding.id == binding_id).first()
    if not binding_to_delete:
        raise HTTPException(status_code=404, detail="TTS Binding not found.")
    
    try:
        db.delete(binding_to_delete)
        db.commit()
        manager.broadcast_sync({"type": "bindings_updated"})
        return {"message": "TTS Binding deleted successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.post("/tts-bindings/{binding_id}/execute_command", response_model=TaskInfo, status_code=202)
async def execute_tts_binding_command(binding_id: int, payload: BindingCommandRequest, current_user: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    binding = db.query(DBTTSBinding).filter(DBTTSBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="TTS Binding not found.")
    
    binding_data = {
        "id": binding.id,
        "name": binding.name,
        "alias": binding.alias,
        "config": binding.config,
        "default_model_name": binding.default_model_name
    }
    
    task = task_manager.submit_task(
        name=f"Exec TTS Cmd: {payload.command_name}",
        target=_execute_binding_command_task,
        args=("tts", binding_data, payload.command_name, payload.parameters, current_user.username),
        description=f"Executing command {payload.command_name} on binding {binding.alias}",
        owner_username=current_user.username
    )
    return task

@bindings_management_router.get("/tts-bindings/{binding_id}/models", response_model=List[BindingModel])
async def get_tts_binding_models(binding_id: int, db: Session = Depends(get_db)):
    binding = db.query(DBTTSBinding).filter(DBTTSBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="TTS Binding not found.")
    
    try:
        client_params = { "tts_binding_name": binding.name, "tts_binding_config": { **binding.config, "model_name": binding.default_model_name } }
        lc = LollmsClient(**client_params)
        if not lc.tts:
            raise Exception("Could not build a tts instance from the configuration.")
        raw_models = lc.tts.list_models()
        
        models_list = [item if isinstance(item, str) else item.get("model_name") for item in raw_models if (isinstance(item, str) or item.get("model_name"))]
        
        model_aliases = binding.model_aliases or {}
        if isinstance(model_aliases, str):
            try: model_aliases = json.loads(model_aliases)
            except (json.JSONDecodeError, TypeError): model_aliases = {}
        
        return [BindingModel(original_model_name=model_name, alias=model_aliases.get(model_name)) for model_name in sorted(models_list)]
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Could not fetch models from TTS binding '{binding.alias}': {e}")

@bindings_management_router.put("/tts-bindings/{binding_id}/alias", response_model=TTSBindingPublicAdmin)
async def update_tts_model_alias(binding_id: int, payload: TtsModelAliasUpdate, db: Session = Depends(get_db)):
    binding = db.query(DBTTSBinding).filter(DBTTSBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="TTS Binding not found.")
    
    if binding.model_aliases is None:
        binding.model_aliases = {}
    
    binding.model_aliases[payload.original_model_name] = payload.alias
    flag_modified(binding, "model_aliases")
    
    db.commit()
    db.refresh(binding)
    return binding

@bindings_management_router.delete("/tts-bindings/{binding_id}/alias", response_model=TTSBindingPublicAdmin)
async def delete_tts_model_alias(binding_id: int, payload: ModelAliasDelete, db: Session = Depends(get_db)):
    binding = db.query(DBTTSBinding).filter(DBTTSBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="TTS Binding not found.")
        
    if binding.model_aliases and payload.original_model_name in binding.model_aliases:
        del binding.model_aliases[payload.original_model_name]
        flag_modified(binding, "model_aliases")
    
    db.commit()
    db.refresh(binding)
    return binding

# --------------------- STT Endpoints ---------------------
@bindings_management_router.get("/stt-bindings/available_types", response_model=List[Dict])
async def get_available_stt_binding_types():
    try:
        return get_available_stt_bindings()
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to get available STT binding types: {e}")

@bindings_management_router.get("/stt-bindings", response_model=List[STTBindingPublicAdmin])
async def get_all_stt_bindings(db: Session = Depends(get_db)):
    return db.query(DBSTTBinding).all()

@bindings_management_router.post("/stt-bindings", response_model=STTBindingPublicAdmin, status_code=201)
async def create_stt_binding(binding_data: STTBindingCreate, db: Session = Depends(get_db)):
    if db.query(DBSTTBinding).filter(DBSTTBinding.alias == binding_data.alias).first():
        raise HTTPException(status_code=400, detail="An STT binding with this alias already exists.")
    
    if binding_data.config:
        binding_data.config = _process_binding_config(binding_data.name, binding_data.config, "stt")

    new_binding = DBSTTBinding(**binding_data.model_dump())
    try:
        db.add(new_binding)
        db.commit()
        db.refresh(new_binding)
        manager.broadcast_sync({"type": "bindings_updated"})
        return new_binding
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="An STT binding with this alias already exists.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.put("/stt-bindings/{binding_id}", response_model=STTBindingPublicAdmin)
async def update_stt_binding(binding_id: int, update_data: STTBindingUpdate, db: Session = Depends(get_db)):
    binding_to_update = db.query(DBSTTBinding).filter(DBSTTBinding.id == binding_id).first()
    if not binding_to_update:
        raise HTTPException(status_code=404, detail="STT Binding not found.")
    
    if update_data.alias and update_data.alias != binding_to_update.alias:
        if db.query(DBSTTBinding).filter(DBSTTBinding.alias == update_data.alias).first():
            raise HTTPException(status_code=400, detail="An STT binding with the new alias already exists.")

    update_dict = update_data.model_dump(exclude_unset=True)

    if 'config' in update_dict and update_dict['config'] is not None:
        binding_name = update_dict.get('name', binding_to_update.name)
        update_dict['config'] = _process_binding_config(binding_name, update_dict['config'], "stt")

    for key, value in update_dict.items():
        setattr(binding_to_update, key, value)
    
    try:
        db.commit()
        db.refresh(binding_to_update)
        manager.broadcast_sync({"type": "bindings_updated"})
        return binding_to_update
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.delete("/stt-bindings/{binding_id}", response_model=Dict[str, str])
async def delete_stt_binding(binding_id: int, db: Session = Depends(get_db)):
    binding_to_delete = db.query(DBSTTBinding).filter(DBSTTBinding.id == binding_id).first()
    if not binding_to_delete:
        raise HTTPException(status_code=404, detail="STT Binding not found.")
    
    try:
        db.delete(binding_to_delete)
        db.commit()
        manager.broadcast_sync({"type": "bindings_updated"})
        return {"message": "STT Binding deleted successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@bindings_management_router.post("/stt-bindings/{binding_id}/execute_command", response_model=TaskInfo, status_code=202)
async def execute_stt_binding_command(binding_id: int, payload: BindingCommandRequest, current_user: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    binding = db.query(DBSTTBinding).filter(DBSTTBinding.id == binding_id).first()
    if not binding: raise HTTPException(status_code=404, detail="STT Binding not found.")
    
    binding_data = {
        "id": binding.id,
        "name": binding.name,
        "alias": binding.alias,
        "config": binding.config,
        "default_model_name": binding.default_model_name
    }
    
    task = task_manager.submit_task(
        name=f"Exec STT Cmd: {payload.command_name}",
        target=_execute_binding_command_task,
        args=("stt", binding_data, payload.command_name, payload.parameters, current_user.username),
        description=f"Executing command {payload.command_name} on binding {binding.alias}",
        owner_username=current_user.username
    )
    return task

@bindings_management_router.get("/stt-bindings/{binding_id}/models", response_model=List[BindingModel])
async def get_stt_binding_models(binding_id: int, db: Session = Depends(get_db)):
    binding = db.query(DBSTTBinding).filter(DBSTTBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="STT Binding not found.")
    
    try:
        client_params = { "stt_binding_name": binding.name, "stt_binding_config": { **binding.config, "model_name": binding.default_model_name } }
        lc = LollmsClient(**client_params)
        if not lc.stt:
            raise Exception("Could not build an STT instance from the configuration.")
        raw_models = lc.stt.list_models()
        
        models_list = [item if isinstance(item, str) else item.get("model_name") for item in raw_models if (isinstance(item, str) or item.get("model_name"))]
        
        model_aliases = binding.model_aliases or {}
        if isinstance(model_aliases, str):
            try: model_aliases = json.loads(model_aliases)
            except (json.JSONDecodeError, TypeError): model_aliases = {}
        
        return [BindingModel(original_model_name=model_name, alias=model_aliases.get(model_name)) for model_name in sorted(models_list)]
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Could not fetch models from STT binding '{binding.alias}': {e}")

@bindings_management_router.put("/stt-bindings/{binding_id}/alias", response_model=STTBindingPublicAdmin)
async def update_stt_model_alias(binding_id: int, payload: SttModelAliasUpdate, db: Session = Depends(get_db)):
    binding = db.query(DBSTTBinding).filter(DBSTTBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="STT Binding not found.")
    
    if binding.model_aliases is None:
        binding.model_aliases = {}
    
    binding.model_aliases[payload.original_model_name] = payload.alias
    flag_modified(binding, "model_aliases")
    
    db.commit()
    db.refresh(binding)
    return binding

@bindings_management_router.delete("/stt-bindings/{binding_id}/alias", response_model=STTBindingPublicAdmin)
async def delete_stt_model_alias(binding_id: int, payload: ModelAliasDelete, db: Session = Depends(get_db)):
    binding = db.query(DBSTTBinding).filter(DBSTTBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="STT Binding not found.")
        
    if binding.model_aliases and payload.original_model_name in binding.model_aliases:
        del binding.model_aliases[payload.original_model_name]
        flag_modified(binding, "model_aliases")
    
    db.commit()
    db.refresh(binding)
    return binding

# --------------------------------------------------------

@bindings_management_router.put("/bindings/{binding_id}/alias", response_model=LLMBindingPublicAdmin)
async def update_model_alias(binding_id: int, payload: ModelAliasUpdate, db: Session = Depends(get_db)):
    binding = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found.")
    
    if binding.model_aliases is None:
        binding.model_aliases = {}
    
    binding.model_aliases[payload.original_model_name] = payload.alias.model_dump()
    flag_modified(binding, "model_aliases")
    
    db.commit()
    db.refresh(binding)
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding

@bindings_management_router.get("/bindings/{binding_id}/models", response_model=List[BindingModel])
async def get_binding_models(binding_id: int, current_admin: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    binding = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found.")
    
    try:
        lc = get_user_lollms_client(current_admin.username, binding.alias)
        raw_models = lc.list_models()
        
        models_list = []
        if isinstance(raw_models, list):
            for item in raw_models:
                model_id = item if isinstance(item, str) else (item.get("name") or item.get("id") or item.get("model_name"))
                if model_id: models_list.append(model_id)
        
        model_aliases = binding.model_aliases or {}
        if isinstance(model_aliases, str):
            try: model_aliases = json.loads(model_aliases)
            except (json.JSONDecodeError, TypeError): model_aliases = {}
        
        return [BindingModel(original_model_name=model_name, alias=model_aliases.get(model_name)) for model_name in sorted(models_list)]
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Could not fetch models from binding '{binding.alias}': {e}")

@bindings_management_router.post("/bindings/{binding_id}/context-size", response_model=Dict[str, Optional[int]])
async def get_model_context_size(binding_id: int, payload: ModelNamePayload, current_admin: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    binding = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found.")
    
    try:
        lc = build_lollms_client_from_params(username=current_admin.username, binding_alias=binding.alias, model_name=payload.model_name)
        ctx_size = lc.get_ctx_size()
        return {"ctx_size": ctx_size}
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Could not fetch context size from binding '{binding.alias}': {e}")

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
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding

@bindings_management_router.get("/available-models", response_model=List[ModelInfo])
async def get_available_models(current_admin: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    all_models = []
    active_bindings = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()

    for binding in active_bindings:
        try:
            lc = get_user_lollms_client(current_admin.username, binding.alias)
            models = lc.list_models()
            
            if isinstance(models, list):
                for item in models:
                    model_id = item if isinstance(item, str) else (item.get("name") or item.get("id") or item.get("model_name"))
                    if model_id: all_models.append({"id": f"{binding.alias}/{model_id}", "name": f"{binding.alias}/{model_id}"})
        except Exception as e:
            print(f"WARNING: Could not fetch models from binding '{binding.alias}': {e}")
            continue

    unique_models = {m["id"]: m for m in all_models}
    sorted_models = sorted(list(unique_models.values()), key=lambda x: x['name'])

    if not sorted_models:
        raise HTTPException(status_code=404, detail="No models found from any active bindings.")
    
    return sorted_models

@bindings_management_router.post("/force-settings-once", response_model=Dict[str, str])
async def force_settings_once(payload: ForceSettingsPayload, db: Session = Depends(get_db)):
    if not payload.model_name:
        raise HTTPException(status_code=400, detail="A model name must be provided in the payload.")
    try:
        users = db.query(DBUser).all()
        for user in users:
            user.lollms_model_name = payload.model_name
            if payload.context_size is not None:
                user.llm_ctx_size = payload.context_size
        db.commit()
        user_sessions.clear()
        return {"message": f"Successfully applied settings to {len(users)} users."}
    except Exception as e:
        db.rollback()
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Database error while forcing settings: {e}")

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
