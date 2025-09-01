# backend/routers/admin.py
import json
import shutil
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any
import asyncio  # Import asyncio


import psutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import IntegrityError
from lollms_client import LollmsClient
from lollms_client.lollms_llm_binding import get_available_bindings
from lollms_client.lollms_tti_binding import get_available_bindings as get_available_tti_bindings
from backend.ws_manager import manager

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.config import GlobalConfig as DBGlobalConfig, LLMBinding as DBLLMBinding, TTIBinding as DBTTIBinding
from backend.db.models.prompt import SavedPrompt as DBSavedPrompt
from backend.security import get_password_hash as hash_password

from ascii_colors import trace_exception, ASCIIColors

from backend.db.models.db_task import DBTask
from backend.models import (
    UserAuthDetails,
    UserCreateAdmin,
    UserPasswordResetAdmin,
    UserPublic,
    GlobalConfigPublic,
    GlobalConfigUpdate,
    AdminUserUpdate,
    BatchUsersSettingsUpdate,
    ModelInfo,
    ForceSettingsPayload,
    EmailUsersRequest,
    AdminDashboardStats,
    EnhanceEmailRequest,
    EnhancedEmailResponse,
    LLMBindingCreate,
    LLMBindingUpdate,
    LLMBindingPublicAdmin,
    TTIBindingCreate,
    TTIBindingUpdate,
    TTIBindingPublicAdmin,
    TaskInfo,
    SystemUsageStats,
    GPUInfo,
    DiskInfo,
    PromptCreate,
    PromptPublic,
    PromptUpdate,
    ModelAliasUpdate,
    TtiModelAliasUpdate,
    ModelAliasDelete,
    BindingModel,
    ModelNamePayload
)
from backend.session import (
    get_user_data_root,
    get_current_admin_user,
    get_user_temp_uploads_path,
    user_sessions,
    get_user_lollms_client,
    build_lollms_client_from_params
)
from backend.security import create_reset_token, send_generic_email
from backend.settings import settings
from backend.config import INITIAL_ADMIN_USER_CONFIG, APP_DATA_DIR, TEMP_UPLOADS_DIR_NAME, PROJECT_ROOT
from backend.migration_utils import run_openwebui_migration
from backend.task_manager import task_manager, Task
from fastapi import status


admin_router = APIRouter(prefix="/api/admin", tags=["Administration"], dependencies=[Depends(get_current_admin_user)])

class AdminBroadcastRequest(BaseModel):
    message: str

def _process_binding_config(binding_name: str, config: Dict[str, Any], binding_type: str = "llm") -> Dict[str, Any]:
    """Casts config values to their correct types based on binding description."""
    if binding_type == "llm":
        available_bindings = get_available_bindings()
    else: # tti
        available_bindings = get_available_tti_bindings()
        
    binding_desc = next((b for b in available_bindings if b.get("binding_name") == binding_name), None)
    
    # Use model_parameters for TTI if they exist, otherwise fallback to input_parameters
    parameters_key = "input_parameters"
    if binding_type == "tti" and binding_desc and "model_parameters" in binding_desc:
        parameters_key = "model_parameters"

    if not binding_desc or parameters_key not in binding_desc:
        return config

    param_types = {p["name"]: p["type"] for p in binding_desc[parameters_key]}
    
    processed_config = {}
    for key, value in config.items():
        if value is None or value == '': # Don't process empty/null values, just keep them.
            processed_config[key] = value
            continue

        target_type = param_types.get(key)
        if not target_type:
            processed_config[key] = value # Keep as is if param not in description
            continue

        try:
            if target_type == 'int':
                processed_config[key] = int(value)
            elif target_type == 'float':
                processed_config[key] = float(value)
            elif target_type == 'bool':
                # Handle various string representations of booleans
                processed_config[key] = str(value).lower() in ('true', '1', 'yes', 'on')
            else: # str or any other type
                processed_config[key] = value
        except (ValueError, TypeError):
            ASCIIColors.warning(f"Could not cast config value '{value}' for key '{key}' to type '{target_type}'. Keeping original value.")
            processed_config[key] = value # Keep original on casting error

    return processed_config


@admin_router.post("/broadcast", status_code=202)
async def broadcast_message_to_all_users(
    payload: AdminBroadcastRequest,
    current_user: UserAuthDetails = Depends(get_current_admin_user)
):
    """
    Sends a persistent notification message to all currently connected users.
    """
    # Add a small delay to allow websocket connections to establish
    await asyncio.sleep(0.1)
    
    await manager.broadcast({
        "type": "admin_broadcast",
        "data": {
            "message": payload.message,
            "sender": current_user.username
        }
    })
    return {"message": "Broadcast sent to all connected users."}


def _to_task_info(db_task: DBTask) -> TaskInfo:
    """Converts a DBTask SQLAlchemy model to a TaskInfo Pydantic model."""
    if not db_task:
        return None
    return TaskInfo(
        id=db_task.id, name=db_task.name, description=db_task.description,
        status=db_task.status, progress=db_task.progress,
        logs=[log for log in (db_task.logs or [])], result=db_task.result, error=db_task.error,
        created_at=db_task.created_at, started_at=db_task.started_at, updated_at=db_task.updated_at, completed_at=db_task.completed_at,
        file_name=db_task.file_name, total_files=db_task.total_files,
        owner_username=db_task.owner.username if db_task.owner else "System"
    )

# --- Task Functions ---
def _email_users_task(task: Task, user_ids: List[int], subject: str, body: str, background_color: Optional[str], send_as_text: bool):
    db_session_local = next(get_db())
    try:
        users_to_email = db_session_local.query(DBUser).filter(DBUser.id.in_(user_ids)).all()
        total_users = len(users_to_email)
        sent_count = 0
        task.set_progress(5)
        for i, user in enumerate(users_to_email):
            if task.cancellation_event.is_set():
                task.log(f"Cancellation requested. Stopping email process.", level="WARNING")
                break
            if user.email and user.receive_notification_emails:
                try:
                    send_generic_email(
                        user.email,
                        subject,
                        body,
                        background_color,
                        send_as_text
                    )
                    sent_count += 1
                    task.log(f"Email sent to {user.username} ({user.email}).")
                except Exception as e:
                    task.log(f"Failed to send email to {user.username}: {e}", level="ERROR")
            
            progress = 5 + int(90 * (i + 1) / total_users)
            task.set_progress(progress)
        
        task.set_progress(100)
        return {"message": f"Email sending task completed. Emails sent to {sent_count} of {total_users} targeted users."}
    except Exception as e:
        trace_exception(e)
        raise e
    finally:
        db_session_local.close()

def _purge_unused_temp_files_task(task: Task):
    task.log("Starting purge of unused temporary files older than 24 hours.")
    deleted_count = 0
    total_scanned = 0
    retention_period = timedelta(hours=24)
    now = datetime.now(timezone.utc)
    
    all_user_dirs = [d for d in APP_DATA_DIR.iterdir() if d.is_dir()]
    task.set_progress(5)

    if not all_user_dirs:
        task.log("No user data directories found to scan.")
        task.set_progress(100)
        return {"message": "Purge complete. No user directories found."}

    for i, user_dir in enumerate(all_user_dirs):
        if task.cancellation_event.is_set():
            task.log("Purge task cancelled.", level="WARNING")
            break
            
        temp_uploads_path = user_dir / TEMP_UPLOADS_DIR_NAME
        if temp_uploads_path.exists():
            task.log(f"Scanning directory: {temp_uploads_path}")
            for file_path in temp_uploads_path.iterdir():
                if file_path.is_file():
                    total_scanned += 1
                    try:
                        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, timezone.utc)
                        if (now - file_mtime) > retention_period:
                            file_path.unlink()
                            deleted_count += 1
                            task.log(f"Deleted old temporary file: {file_path.name}")
                    except Exception as e:
                        task.log(f"Error processing file {file_path.name}: {e}", level="ERROR")
        
        progress = 5 + int(90 * (i + 1) / len(all_user_dirs))
        task.set_progress(progress)

    task.set_progress(100)
    return {"message": f"Purge complete. Scanned {total_scanned} files and deleted {deleted_count}."}

# --- System Status Endpoint ---
@admin_router.get("/system-status", response_model=SystemUsageStats)
async def get_system_status():
    # CPU RAM
    ram = psutil.virtual_memory()
    cpu_ram_total_gb = ram.total / (1024**3)
    cpu_ram_used_gb = ram.used / (1024**3)
    cpu_ram_available_gb = ram.available / (1024**3)
    cpu_ram_usage_percent = ram.percent

    # Disk Usage
    disks_info = []
    app_disk_mount = None
    data_disk_mount = None

    try:
        partitions = psutil.disk_partitions(all=False)
        
        def find_mount_point(path, partitions_list):
            path_abs = Path(path).resolve()
            best_match = ''
            for p in partitions_list:
                if str(path_abs).startswith(p.mountpoint) and len(p.mountpoint) > len(best_match):
                    best_match = p.mountpoint
            return best_match if best_match else None

        app_disk_mount = find_mount_point(PROJECT_ROOT, partitions)
        data_disk_mount = find_mount_point(APP_DATA_DIR, partitions)
        
        for part in partitions:
            if 'loop' in part.device or not part.fstype or not Path(part.mountpoint).exists():
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks_info.append(DiskInfo(
                    mount_point=part.mountpoint,
                    total_gb=usage.total / (1024**3),
                    used_gb=usage.used / (1024**3),
                    available_gb=usage.free / (1024**3),
                    usage_percent=usage.percent,
                    is_app_disk=(part.mountpoint == app_disk_mount),
                    is_data_disk=(part.mountpoint == data_disk_mount)
                ))
            except OSError as e:
                print(f"Could not get usage for partition {part.mountpoint}: {e}")
    except Exception as e:
        print(f"Error collecting disk information: {e}")

    # GPU VRAM
    gpus_info = []
    try:
        import pynvml
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpu_name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(gpu_name, bytes):
                gpu_name = gpu_name.decode('utf-8')
            
            gpus_info.append(GPUInfo(
                id=i,
                name=gpu_name,
                vram_total_gb=info.total / (1024**3),
                vram_used_gb=info.used / (1024**3),
                vram_usage_percent=(info.used / info.total) * 100 if info.total > 0 else 0
            ))
        pynvml.nvmlShutdown()
    except ImportError:
        pass
    except Exception as e:
        print(f"Could not get GPU info: {e}")

    return SystemUsageStats(
        cpu_ram_total_gb=cpu_ram_total_gb,
        cpu_ram_used_gb=cpu_ram_used_gb,
        cpu_ram_available_gb=cpu_ram_available_gb,
        cpu_ram_usage_percent=cpu_ram_usage_percent,
        disks=disks_info,
        gpus=gpus_info,
    )

# --- Bindings Management Endpoints ---

@admin_router.get("/bindings/available_types", response_model=List[Dict])
async def get_available_binding_types():
    try:
        return get_available_bindings()
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to get available binding types: {e}")

@admin_router.get("/bindings")#, response_model=List[LLMBindingPublicAdmin])
async def get_all_bindings(db: Session = Depends(get_db)):
    bindings = db.query(DBLLMBinding).all()
    if isinstance(bindings, str):
        ASCIIColors.info("Fixing the bindings content")
        bindings = json.loads(bindings)

    return bindings

@admin_router.post("/bindings", response_model=LLMBindingPublicAdmin, status_code=201)
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
        await manager.broadcast({"type": "bindings_updated"})
        return new_binding
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="A binding with this alias already exists.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@admin_router.put("/bindings/{binding_id}", response_model=LLMBindingPublicAdmin)
async def update_binding(binding_id: int, update_data: LLMBindingUpdate, db: Session = Depends(get_db)):
    binding_to_update = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding_to_update:
        raise HTTPException(status_code=404, detail="Binding not found.")
    
    if update_data.alias and update_data.alias != binding_to_update.alias:
        if db.query(DBLLMBinding).filter(DBLLMBinding.alias == update_data.alias).first():
            raise HTTPException(status_code=400, detail="A binding with the new alias already exists.")

    update_dict = update_data.model_dump(exclude_unset=True)
    if 'service_key' in update_dict and not update_dict['service_key']:
        del update_dict['service_key']

    if 'config' in update_dict and update_dict['config'] is not None:
        binding_name = update_dict.get('name', binding_to_update.name)
        update_dict['config'] = _process_binding_config(binding_name, update_dict['config'], "llm")

    for key, value in update_dict.items():
        setattr(binding_to_update, key, value)
    
    try:
        db.commit()
        db.refresh(binding_to_update)
        # Invalidate cached clients
        for session in user_sessions.values():
            if "lollms_clients" in session and binding_to_update.alias in session["lollms_clients"]:
                del session["lollms_clients"][binding_to_update.alias]
        await manager.broadcast({"type": "bindings_updated"})
        return binding_to_update
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@admin_router.delete("/bindings/{binding_id}", response_model=Dict[str, str])
async def delete_binding(binding_id: int, db: Session = Depends(get_db)):
    binding_to_delete = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding_to_delete:
        raise HTTPException(status_code=404, detail="Binding not found.")
    
    try:
        db.delete(binding_to_delete)
        db.commit()
        await manager.broadcast({"type": "bindings_updated"})
        return {"message": "Binding deleted successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# --- TTI Bindings Management Endpoints ---

@admin_router.get("/tti-bindings/available_types", response_model=List[Dict])
async def get_available_tti_binding_types():
    try:
        return get_available_tti_bindings()
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to get available TTI binding types: {e}")

@admin_router.get("/tti-bindings", response_model=List[TTIBindingPublicAdmin])
async def get_all_tti_bindings(db: Session = Depends(get_db)):
    return db.query(DBTTIBinding).all()

@admin_router.post("/tti-bindings", response_model=TTIBindingPublicAdmin, status_code=201)
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
        return new_binding
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="A TTI binding with this alias already exists.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@admin_router.put("/tti-bindings/{binding_id}", response_model=TTIBindingPublicAdmin)
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
        return binding_to_update
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@admin_router.delete("/tti-bindings/{binding_id}", response_model=Dict[str, str])
async def delete_tti_binding(binding_id: int, db: Session = Depends(get_db)):
    binding_to_delete = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding_to_delete:
        raise HTTPException(status_code=404, detail="TTI Binding not found.")
    
    try:
        db.delete(binding_to_delete)
        db.commit()
        return {"message": "TTI Binding deleted successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@admin_router.get("/tti-bindings/{binding_id}/models", response_model=List[BindingModel])
async def get_tti_binding_models(binding_id: int, db: Session = Depends(get_db)):
    binding = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="TTI Binding not found.")
    
    try:
        # Build client parameters for TTI. 
        # LollmsClient requires an LLM binding to be set, so we use a dummy one.
        client_params = {
            "tti_binding_name": binding.name,
            "tti_binding_config": {
                **binding.config,
                "model_name": binding.default_model_name
            }
        }

        lc = LollmsClient(**client_params)
        if not lc.tti:
            ASCIIColors.error("Could not build a tti instance from the configuration. make sure you have set all configuration parameters correctly")
            raise Exception("Could not build a tti instance from the configuration. make sure you have set all configuration parameters correctly")
        raw_models = lc.tti.listModels()
        
        models_list = []
        if isinstance(raw_models, list):
            for item in raw_models:
                model_id = item if isinstance(item, str) else item.get("model_name")
                if model_id:
                    models_list.append(model_id)
        
        model_aliases = binding.model_aliases or {}
        
        result = []
        for model_name in sorted(models_list):
            result.append(BindingModel(
                original_model_name=model_name,
                alias=model_aliases.get(model_name)
            ))
        return result
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Could not fetch models from TTI binding '{binding.alias}': {e}")

@admin_router.put("/tti-bindings/{binding_id}/alias", response_model=TTIBindingPublicAdmin)
async def update_tti_model_alias(binding_id: int, payload: TtiModelAliasUpdate, db: Session = Depends(get_db)):
    binding = db.query(DBTTIBinding).filter(DBTTIBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="TTI Binding not found.")
    
    if binding.model_aliases is None:
        binding.model_aliases = {}
    
    # Directly assign the dictionary from the payload.
    binding.model_aliases[payload.original_model_name] = payload.alias
    flag_modified(binding, "model_aliases")
    
    db.commit()
    db.refresh(binding)
    return binding

@admin_router.delete("/tti-bindings/{binding_id}/alias", response_model=TTIBindingPublicAdmin)
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

# --- NEW: Model Alias Endpoints ---

@admin_router.get("/bindings/{binding_id}/models", response_model=List[BindingModel])
async def get_binding_models(binding_id: int, current_admin: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    binding = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found.")
    
    try:
        lc = get_user_lollms_client(current_admin.username, binding.alias)
        raw_models = lc.listModels()
        
        models_list = []
        if isinstance(raw_models, list):
            for item in raw_models:
                model_id = None
                if isinstance(item, str): model_id = item
                elif isinstance(item, dict): model_id = item.get("name") or item.get("id") or item.get("model_name")
                if model_id: models_list.append(model_id)
        
        model_aliases = binding.model_aliases or {}
        
        result = []
        for model_name in sorted(models_list):
            result.append(BindingModel(
                original_model_name=model_name,
                alias=model_aliases.get(model_name)
            ))
        return result
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Could not fetch models from binding '{binding.alias}': {e}")

@admin_router.post("/bindings/{binding_id}/context-size", response_model=Dict[str, Optional[int]])
async def get_model_context_size(binding_id: int, payload: ModelNamePayload, current_admin: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    binding = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found.")
    
    try:
        # Use a temporary client to avoid affecting user session state
        lc = build_lollms_client_from_params(
            username=current_admin.username,
            binding_alias=binding.alias,
            model_name=payload.model_name
        )
        ctx_size = lc.get_ctx_size()
        return {"ctx_size": ctx_size}
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Could not fetch context size from binding '{binding.alias}': {e}")

@admin_router.put("/bindings/{binding_id}/alias", response_model=LLMBindingPublicAdmin)
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
    await manager.broadcast({"type": "bindings_updated"})
    return binding

@admin_router.delete("/bindings/{binding_id}/alias", response_model=LLMBindingPublicAdmin)
async def delete_model_alias(binding_id: int, payload: ModelAliasDelete, db: Session = Depends(get_db)):
    binding = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found.")
        
    if binding.model_aliases and payload.original_model_name in binding.model_aliases:
        del binding.model_aliases[payload.original_model_name]
        flag_modified(binding, "model_aliases")
    
    db.commit()
    db.refresh(binding)
    await manager.broadcast({"type": "bindings_updated"})
    return binding


# --- Existing Admin Endpoints ---

@admin_router.get("/stats", response_model=AdminDashboardStats)
async def get_dashboard_stats(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    
    total_users = db.query(DBUser).count()
    
    active_24h_threshold = now - timedelta(hours=24)
    active_users_24h = db.query(DBUser).filter(DBUser.last_activity_at > active_24h_threshold).count()

    new_7d_threshold = now - timedelta(days=7)
    new_users_7d = db.query(DBUser).filter(DBUser.created_at > new_7d_threshold).count()
    
    registration_mode = settings.get("registration_mode", "admin_approval")
    pending_approval = 0
    if registration_mode == "admin_approval":
        pending_approval = db.query(DBUser).filter(DBUser.is_active == False, DBUser.activation_token.isnot(None)).count()
    
    pending_password_resets = db.query(DBUser).filter(
        DBUser.password_reset_token.isnot(None), 
        DBUser.reset_token_expiry > now
    ).count()

    return AdminDashboardStats(
        total_users=total_users,
        active_users_24h=active_users_24h,
        new_users_7d=new_users_7d,
        pending_approval=pending_approval,
        pending_password_resets=pending_password_resets
    )

@admin_router.post("/email-users", response_model=TaskInfo, status_code=202)
async def email_users(
    payload: EmailUsersRequest,
    current_admin: UserAuthDetails = Depends(get_current_admin_user)
):
    email_mode = settings.get("password_recovery_mode")
    if email_mode not in ["automatic", "system_mail", "outlook"]:
        raise HTTPException(status_code=412, detail=f"Email sending is not enabled or is set to manual. Current mode: '{email_mode}'.")

    if not payload.user_ids:
        raise HTTPException(status_code=400, detail="No users selected to email.")

    db_task = task_manager.submit_task(
        name=f"Emailing {len(payload.user_ids)} users",
        target=_email_users_task,
        args=(payload.user_ids, payload.subject, payload.body, payload.background_color, payload.send_as_text),
        description=f"Sending email with subject: '{payload.subject}'",
        owner_username=current_admin.username
    )
    return _to_task_info(db_task)

@admin_router.post("/purge-unused-uploads", response_model=TaskInfo, status_code=202)
async def purge_temp_files(current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    """
    Triggers a background task to delete temporary uploaded files older than 24 hours.
    """
    db_task = task_manager.submit_task(
        name="Purge unused temporary files",
        target=_purge_unused_temp_files_task,
        description="Scans all user temporary upload folders and deletes files older than 24 hours.",
        owner_username=current_admin.username
    )
    return _to_task_info(db_task)


@admin_router.post("/enhance-email", response_model=EnhancedEmailResponse)
async def enhance_email_with_ai(
    payload: EnhanceEmailRequest,
    current_admin: UserAuthDetails = Depends(get_current_admin_user)
):
    try:
        # This will use the admin's default model for now.
        lc = get_user_lollms_client(current_admin.username)
        
        if payload.prompt and payload.prompt.strip():
            prompt = f"""{payload.prompt.strip()}

You must return ONLY a single valid JSON object with three keys: "subject", "body", and "background_color".
Do not add any text or explanation before or after the JSON object.

Here is the email content to work on:
---
Original Subject:
{payload.subject}

Original Body:
{payload.body}

Current Background Color:
{payload.background_color or "#FFFFFF"}
---
"""
        else:
            prompt = f"""You are an expert copywriter and designer. Your task is to enhance the following email draft to make it more engaging, professional, and clear.
You must also suggest a suitable HTML background color for the email's theme.
Return ONLY a single valid JSON object with three keys: "subject", "body", and "background_color". The background_color should be a valid hex code (e.g., "#f0f4f8").
Do not add any text or explanation before or after the JSON object.

Original Subject:
{payload.subject}

Original Body:
{payload.body}

Current Background Color:
{payload.background_color or "#FFFFFF"}
"""
        
        raw_response = lc.generate_text(prompt, stream=False)

        json_start = raw_response.find('{')
        json_end = raw_response.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            raise HTTPException(status_code=500, detail="AI did not return a valid JSON object.")
            
        json_string = raw_response[json_start:json_end]

        try:
            enhanced_data = json.loads(json_string)
            if "subject" not in enhanced_data or "body" not in enhanced_data:
                 raise ValueError("The JSON response from the AI is missing 'subject' or 'body' keys.")
            return EnhancedEmailResponse(
                subject=enhanced_data.get("subject", payload.subject),
                body=enhanced_data.get("body", payload.body),
                background_color=enhanced_data.get("background_color", payload.background_color)
            )
        except (json.JSONDecodeError, ValueError) as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {e}")

    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"An error occurred while enhancing the email: {e}")

@admin_router.get("/available-models", response_model=List[ModelInfo])
async def get_available_models(current_admin: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    all_models = []
    active_bindings = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()

    for binding in active_bindings:
        try:
            # We get a client instance specifically for this binding to list its models
            lc = get_user_lollms_client(current_admin.username, binding.alias)
            models = lc.listModels()
            
            if isinstance(models, list):
                for item in models:
                    model_id = None
                    if isinstance(item, str):
                        model_id = item
                    elif isinstance(item, dict):
                        model_id = item.get("name") or item.get("id") or item.get("model_name")
                    
                    if model_id:
                        all_models.append({
                            "id": f"{binding.alias}/{model_id}",
                            "name": f"{binding.alias}/{model_id}"
                        })
        except Exception as e:
            print(f"WARNING: Could not fetch models from binding '{binding.alias}': {e}")
            continue

    unique_models = {m["id"]: m for m in all_models}
    sorted_models = sorted(list(unique_models.values()), key=lambda x: x['name'])

    if not sorted_models:
        raise HTTPException(status_code=404, detail="No models found from any active bindings.")
    
    return sorted_models

@admin_router.post("/force-settings-once", response_model=Dict[str, str])
async def force_settings_once(payload: ForceSettingsPayload, db: Session = Depends(get_db)):
    forced_model = payload.model_name
    forced_ctx = payload.context_size

    if not forced_model:
        raise HTTPException(status_code=400, detail="A model name must be provided in the payload.")

    try:
        users = db.query(DBUser).all()
        for user in users:
            user.lollms_model_name = forced_model
            if forced_ctx is not None:
                user.llm_ctx_size = forced_ctx
        
        db.commit()
        
        user_sessions.clear()
        
        return {"message": f"Successfully applied model '{forced_model}' and context size '{forced_ctx or 'N/A'}' to {len(users)} users."}
    except Exception as e:
        db.rollback()
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Database error while forcing settings: {e}")

@admin_router.post("/import-openwebui", response_model=Dict[str, str])
async def import_openwebui_data(
    file: UploadFile = File(...),
    current_admin: UserAuthDetails = Depends(get_current_admin_user)
):
    if not file:
        raise HTTPException(status_code=400, detail="No file was uploaded.")
    
    if file.filename != "webui.db":
        raise HTTPException(status_code=400, detail="Invalid file uploaded. Please upload the 'webui.db' file from OpenWebUI.")

    temp_import_dir = get_user_temp_uploads_path(current_admin.username) / f"owui_import_{uuid.uuid4()}"
    temp_import_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"INFO: Staging OpenWebUI import file in: {temp_import_dir}")
    
    try:
        file_path = temp_import_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    task_manager.submit_task(
        name="Import OpenWebUI Data",
        target=run_openwebui_migration,
        args=(str(temp_import_dir),),
        description=f"Migrating data from {file.filename}",
        owner_username=current_admin.username
    )

    return {"message": "Migration process started in the background. Check the Task Manager for progress."}

@admin_router.get("/settings", response_model=List[GlobalConfigPublic])
async def admin_get_global_settings(db: Session = Depends(get_db)):
    db_configs = db.query(DBGlobalConfig).order_by(DBGlobalConfig.category, DBGlobalConfig.key).all()
    response_models = []
    for config in db_configs:
        try:
            stored_data = json.loads(config.value)
            if isinstance(stored_data,str):
                stored_data = json.loads(stored_data)
            response_models.append(GlobalConfigPublic(
                key=config.key,
                value=stored_data.get('value'),
                type=stored_data.get('type', 'unknown'),
                description=config.description,
                category=config.category,
            ))
        except (json.JSONDecodeError, TypeError):
            response_models.append(GlobalConfigPublic(
                key=config.key, value=None, type='error',
                description=f"Error parsing value: {config.value}",
                category=config.category,
            ))
    return response_models

@admin_router.put("/settings", response_model=Dict[str, str])
async def admin_update_global_settings(
    update_data: GlobalConfigUpdate,
    db: Session = Depends(get_db)
):
    updated_keys = []
    try:
        for key, new_value in update_data.configs.items():
            db_config = db.query(DBGlobalConfig).filter(DBGlobalConfig.key == key).first()
            if db_config:
                if key == 'smtp_password' and not new_value:
                    continue
                
                stored_data = {}
                try:
                    # Attempt to parse what's in the DB. It should be a JSON string of a dict.
                    parsed_value = json.loads(db_config.value)
                    if isinstance(parsed_value, dict) and 'type' in parsed_value:
                        stored_data = parsed_value
                    else:
                        # Fallback for corrupted/old format data
                        stored_data['value'] = parsed_value
                        stored_data['type'] = 'string' # Assume string if type is missing
                except (json.JSONDecodeError, TypeError):
                    # Value is not JSON, e.g., just "mixed". Treat it as the value.
                    stored_data['value'] = db_config.value
                    stored_data['type'] = 'string' # Assume string
                
                # Update the value and serialize back to string for DB storage.
                stored_data['value'] = new_value
                db_config.value = json.dumps(stored_data)
                updated_keys.append(key)
            else:
                print(f"WARNING: Admin tried to update non-existent setting key: {key}")

        if updated_keys:
            db.commit()
            settings.refresh()
            await manager.broadcast({"type": "settings_updated"})
            print(f"INFO: Admin updated global settings: {', '.join(updated_keys)}")
        
        return {"message": f"Successfully updated {len(updated_keys)} settings."}
    except Exception as e:
        db.rollback()
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Database error while updating settings: {e}")

@admin_router.get("/users", response_model=List[UserPublic])
async def admin_get_all_users(db: Session = Depends(get_db)) -> List[DBUser]:
    return db.query(DBUser).all()

@admin_router.get("/active-sessions", response_model=List[str])
async def get_active_sessions():
    return list(user_sessions.keys())

@admin_router.post("/users", response_model=UserPublic, status_code=201)
async def admin_add_new_user(user_data: UserCreateAdmin, db: Session = Depends(get_db)) -> DBUser:
    if db.query(DBUser).filter(DBUser.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username is already registered.")
    if user_data.email and db.query(DBUser).filter(DBUser.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email is already in use by another account.")

    new_db_user = DBUser(
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        is_admin=user_data.is_admin,
        is_moderator=(user_data.is_admin or user_data.is_moderator),
        email=user_data.email,
        lollms_model_name=user_data.lollms_model_name,
        safe_store_vectorizer=user_data.safe_store_vectorizer or settings.get("default_safe_store_vectorizer"),
        llm_ctx_size=user_data.llm_ctx_size if user_data.llm_ctx_size is not None else settings.get("default_llm_ctx_size"),
        llm_temperature=user_data.llm_temperature if user_data.llm_temperature is not None else settings.get("default_llm_temperature"),
        is_active=True
    )
    try:
        db.add(new_db_user)
        db.commit()
        db.refresh(new_db_user)
        return new_db_user
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"A user with that username or email already exists. Original error: {e.orig}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"A database error occurred: {e}")

@admin_router.put("/users/{user_id}", response_model=UserPublic)
async def admin_update_user(user_id: int, update_data: AdminUserUpdate, db: Session = Depends(get_db), current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    user_to_update = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found.")
    
    if user_to_update.id == current_admin.id and update_data.is_admin is False:
        raise HTTPException(status_code=403, detail="Administrators cannot revoke their own admin status.")
    
    initial_admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
    if initial_admin_username and user_to_update.username == initial_admin_username and update_data.is_admin is False:
        raise HTTPException(status_code=403, detail="The initial superadmin account cannot have its admin status revoked.")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    
    # If user is being made an admin, also make them a moderator
    if 'is_admin' in update_dict and update_dict['is_admin']:
        update_dict['is_moderator'] = True

    for key, value in update_dict.items():
        setattr(user_to_update, key, value)
    
    try:
        db.commit()
        db.refresh(user_to_update)
        
        if user_to_update.username in user_sessions:
            user_sessions[user_to_update.username]["lollms_clients"] = {}
        
        return user_to_update
    except Exception as e:
        db.rollback()
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"A database error occurred: {e}")

@admin_router.post("/users/batch-update-settings", response_model=Dict[str, str])
async def admin_batch_update_user_settings(
    update_data: BatchUsersSettingsUpdate,
    db: Session = Depends(get_db),
    current_admin: UserAuthDetails = Depends(get_current_admin_user)
):
    if not update_data.user_ids:
        raise HTTPException(status_code=400, detail="No user IDs provided for the update.")

    users_to_update = db.query(DBUser).filter(DBUser.id.in_(update_data.user_ids)).all()
    if not users_to_update:
        raise HTTPException(status_code=404, detail="No valid users found for the provided IDs.")

    update_fields = update_data.model_dump(exclude={"user_ids"}, exclude_unset=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="No settings provided to update.")

    updated_usernames = []
    for user in users_to_update:
        for key, value in update_fields.items():
            setattr(user, key, value)
        updated_usernames.append(user.username)

    try:
        db.commit()

        for username in updated_usernames:
            if username in user_sessions:
                user_sessions[username]["lollms_clients"] = {}
                print(f"INFO: Invalidated LLM client cache for user '{username}' due to batch settings update.")

        return {"message": f"Successfully updated settings for {len(users_to_update)} users."}
    except Exception as e:
        db.rollback()
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"A database error occurred during batch update: {e}")

@admin_router.post("/users/{user_id}/activate", response_model=UserPublic)
async def admin_activate_user(user_id: int, db: Session = Depends(get_db)):
    user_to_activate = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_activate:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user_to_activate.is_active = True
    user_to_activate.activation_token = None
    user_to_activate.password_reset_token = None
    user_to_activate.reset_token_expiry = None

    try:
        db.commit()
        db.refresh(user_to_activate)
        return user_to_activate
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"A database error occurred: {e}")

@admin_router.post("/users/{user_id}/deactivate", response_model=UserPublic)
async def admin_deactivate_user(user_id: int, db: Session = Depends(get_db), current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    user_to_deactivate = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_deactivate:
        raise HTTPException(status_code=404, detail="User not found.")
    
    if user_to_deactivate.id == current_admin.id:
        raise HTTPException(status_code=403, detail="Administrators cannot deactivate their own accounts.")
    
    user_to_deactivate.is_active = False
    
    try:
        db.commit()
        db.refresh(user_to_deactivate)
        if user_to_deactivate.username in user_sessions:
            del user_sessions[user_to_deactivate.username]
        return user_to_deactivate
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"A database error occurred: {e}")

@admin_router.post("/users/{user_id}/reset-password", response_model=Dict[str, str])
async def admin_reset_user_password(user_id: int, payload: UserPasswordResetAdmin, db: Session = Depends(get_db)):
    user_to_update = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user_to_update.hashed_password = hash_password(payload.new_password)
    user_to_update.password_reset_token = None
    user_to_update.reset_token_expiry = None

    try:
        db.commit()
        return {"message": f"Password for user '{user_to_update.username}' has been successfully reset."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"A database error occurred: {e}")

@admin_router.post("/users/{user_id}/generate-reset-link", response_model=Dict[str, str])
async def admin_generate_password_reset_link(user_id: int, request: Request, db: Session = Depends(get_db)):
    user_to_update = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found.")

    token = create_reset_token()
    user_to_update.password_reset_token = token
    user_to_update.reset_token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    
    try:
        db.commit()
        base_url = str(request.base_url).strip('/')
        reset_link = f"{base_url}/reset-password?token={token}"
        return {"reset_link": reset_link}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"A database error occurred: {e}")

@admin_router.delete("/users/{user_id}", response_model=Dict[str, str])
async def admin_remove_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: UserAuthDetails = Depends(get_current_admin_user)
):
    user_to_delete = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User not found.")
    
    initial_admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
    if initial_admin_username and user_to_delete.username == initial_admin_username:
        raise HTTPException(status_code=403, detail="The initial superadmin account cannot be deleted.")
    if user_to_delete.id == current_admin.id:
        raise HTTPException(status_code=403, detail="Administrators cannot delete their own accounts.")
    
    user_data_dir_to_delete = get_user_data_root(user_to_delete.username)

    try:
        if user_to_delete.username in user_sessions:
            del user_sessions[user_to_delete.username]

        db.delete(user_to_delete)
        db.commit()
        
        if user_data_dir_to_delete.exists():
            task_manager.submit_task(
                name=f"Delete user data for {user_to_delete.username}",
                target=shutil.rmtree,
                args=(user_data_dir_to_delete,),
                kwargs={'ignore_errors': True},
                description=f"Cleaning up data directory: {user_data_dir_to_delete}"
            )
            
        return {"message": f"User '{user_to_delete.username}' deleted. Data cleanup initiated."}
    except Exception as e:
        db.rollback()
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"A database or file system error occurred during user deletion: {e}")
    

@admin_router.get("/ws-status", response_model=Dict[str, bool])
async def get_my_websocket_status(
    current_user: UserAuthDetails = Depends(get_current_admin_user)
):
    """
    Checks if the current admin user has an active WebSocket connection.
    """
    is_connected = current_user.id in manager.active_connections
    is_registered_admin = current_user.id in manager.admin_user_ids
    return {
        "is_connected": is_connected,
        "is_registered_as_admin": is_registered_admin
    }