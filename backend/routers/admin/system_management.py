# backend/routers/admin/system_management.py
import sys
import asyncio
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict

import psutil
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func
from lollms_client import LollmsDataManager

from sqlalchemy.orm import Session, joinedload
from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.service import App as DBApp
from backend.db.models.connections import WebSocketConnection
from backend.models import UserAuthDetails, SystemUsageStats, GPUInfo, DiskInfo, TaskInfo
from backend.models.admin import GlobalGenerationStats, UserActivityStat
from backend.config import PROJECT_ROOT, APP_DATA_DIR, SERVER_CONFIG, APP_VERSION, USERS_DIR_NAME, TEMP_UPLOADS_DIR_NAME
from backend.session import get_current_admin_user, get_user_data_root
from backend.ws_manager import manager
from backend.task_manager import task_manager, Task
from backend.utils import get_local_ip_addresses
from backend.tasks.system_tasks import _create_backup_task # NEW IMPORT
from ascii_colors import trace_exception

system_management_router = APIRouter()

class AdminBroadcastRequest(BaseModel):
    message: str

class BackupRequest(BaseModel):
    password: Optional[str] = None

class ConnectedUser(BaseModel):
    id: int
    username: str
    icon: Optional[str] = None
    class Config:
        from_attributes = True

class AppPortInfo(BaseModel):
    port: int
    app_name: str
    app_id: str

class ServerInfo(BaseModel):
    lollms_version: str
    python_version: str
    host: str
    port: int
    https_enabled: bool
    active_ports: List[AppPortInfo]
    cors_origins: List[str]
    local_ips: Optional[List[str]] = None

def _to_task_info(db_task) -> TaskInfo:
    return TaskInfo(
        id=db_task.id, name=db_task.name, description=db_task.description,
        status=db_task.status, progress=db_task.progress,
        logs=[log for log in (db_task.logs or [])], result=db_task.result, error=db_task.error,
        created_at=db_task.created_at, started_at=db_task.started_at, updated_at=db_task.updated_at, completed_at=db_task.completed_at,
        file_name=db_task.file_name, total_files=db_task.total_files,
        owner_username=db_task.owner.username if db_task.owner else "System"
    )

def _purge_unused_temp_files_task(task: Task):
    task.log("Starting purge of unused temporary files older than 24 hours.")
    deleted_count, total_scanned = 0, 0
    retention_period = timedelta(hours=24)
    now = datetime.now(timezone.utc)
    
    users_root_path = APP_DATA_DIR / USERS_DIR_NAME
    if not users_root_path.exists():
        task.set_progress(100)
        return {"message": "Users directory not found."}
    
    all_user_dirs = [d for d in users_root_path.iterdir() if d.is_dir()]
    if not all_user_dirs:
        task.set_progress(100)
        return {"message": "No user directories found."}

    for i, user_dir in enumerate(all_user_dirs):
        if task.cancellation_event.is_set():
            task.log("Purge task cancelled.", level="WARNING")
            break
            
        temp_uploads_path = user_dir / TEMP_UPLOADS_DIR_NAME
        if temp_uploads_path.exists():
            for file_path in temp_uploads_path.iterdir():
                if file_path.is_file():
                    total_scanned += 1
                    try:
                        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, timezone.utc)
                        if (now - file_mtime) > retention_period:
                            file_path.unlink()
                            deleted_count += 1
                            task.log(f"Deleted old file: {file_path.name}")
                    except Exception as e:
                        task.log(f"Error with file {file_path.name}: {e}", level="ERROR")
        
        task.set_progress(5 + int(90 * (i + 1) / len(all_user_dirs)))

    task.set_progress(100)
    return {"message": f"Purge complete. Scanned {total_scanned} files, deleted {deleted_count}."}

@system_management_router.get("/system-status", response_model=SystemUsageStats)
async def get_system_status():
    ram = psutil.virtual_memory()
    
    disks_info = []
    try:
        partitions = psutil.disk_partitions(all=False)
        def find_mount(path, parts):
            abs_path = Path(path).resolve()
            return next((p.mountpoint for p in sorted(parts, key=lambda p: len(p.mountpoint), reverse=True) if str(abs_path).startswith(p.mountpoint)), None)

        app_mount = find_mount(PROJECT_ROOT, partitions)
        data_mount = find_mount(APP_DATA_DIR, partitions)
        
        for part in partitions:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks_info.append(DiskInfo(
                    mount_point=part.mountpoint, total_gb=usage.total / (1024**3),
                    used_gb=usage.used / (1024**3), available_gb=usage.free / (1024**3),
                    usage_percent=usage.percent, is_app_disk=(part.mountpoint == app_mount),
                    is_data_disk=(part.mountpoint == data_mount)
                ))
            except OSError: continue
    except Exception: pass

    gpus_info = []
    try:
        from pynvml import (
            nvmlInit, nvmlShutdown, nvmlDeviceGetCount, nvmlDeviceGetHandleByIndex,
            nvmlDeviceGetMemoryInfo, nvmlDeviceGetName, NVMLError
        )
        nvmlInit()
        count = nvmlDeviceGetCount()
        for i in range(count):
            handle = nvmlDeviceGetHandleByIndex(i)
            name = nvmlDeviceGetName(handle)
            # nvmlDeviceGetName may return bytes on some platforms
            gpu_name = name.decode("utf-8") if isinstance(name, (bytes, bytearray)) else str(name)

            mem = nvmlDeviceGetMemoryInfo(handle)
            total_gb = mem.total / (1024 ** 3)
            used_gb  = mem.used  / (1024 ** 3)
            usage_pct = (mem.used / mem.total) * 100 if mem.total > 0 else 0.0

            gpus_info.append(GPUInfo(
                id=i,
                name=gpu_name,
                vram_total_gb=total_gb,
                vram_used_gb=used_gb,
                vram_usage_percent=usage_pct
            ))
        nvmlShutdown()
    except (ImportError, Exception): pass

    return SystemUsageStats(
        cpu_ram_total_gb=ram.total / (1024**3), cpu_ram_used_gb=ram.used / (1024**3),
        cpu_ram_available_gb=ram.available / (1024**3), cpu_ram_usage_percent=ram.percent,
        disks=disks_info, gpus=gpus_info,
    )

@system_management_router.get("/server-info", response_model=ServerInfo)
async def get_server_info(request: Request, db: Session = Depends(get_db)):
    running_apps = db.query(DBApp).filter(DBApp.status == 'running', DBApp.port != None).all()
    active_ports = [AppPortInfo(port=app.port, app_name=app.name, app_id=app.id) for app in running_apps]

    allowed_origins = next((m.options.get('allow_origins', []) for m in request.app.user_middleware if "CORSMiddleware" in str(m)), [])
    
    host = SERVER_CONFIG.get("host", "localhost")
    local_ips = None
    if host == "0.0.0.0":
        local_ips = get_local_ip_addresses()

    return ServerInfo(
        lollms_version=APP_VERSION, python_version=sys.version,
        host=host, port=SERVER_CONFIG.get("port", 9642),
        https_enabled=SERVER_CONFIG.get("https_enabled", False),
        active_ports=active_ports, cors_origins=allowed_origins,
        local_ips=local_ips
    )

@system_management_router.post("/broadcast", status_code=202)
async def broadcast_message_to_all_users(payload: AdminBroadcastRequest, current_user: UserAuthDetails = Depends(get_current_admin_user)):
    await asyncio.sleep(0.1)
    await manager.broadcast({"type": "admin_broadcast", "data": {"message": payload.message, "sender": current_user.username}})
    return {"message": "Broadcast sent."}

@system_management_router.get("/ws-connections", response_model=List[ConnectedUser])
async def get_websocket_connections(db: Session = Depends(get_db)):
    user_ids = [uid for uid, in db.query(WebSocketConnection.user_id).distinct().all()]
    return db.query(DBUser).filter(DBUser.id.in_(user_ids)).all() if user_ids else []

@system_management_router.get("/ws-status", response_model=Dict[str, bool])
async def get_my_websocket_status(current_user: UserAuthDetails = Depends(get_current_admin_user)):
    return {
        "is_connected": current_user.id in manager.active_connections,
        "is_registered_as_admin": current_user.id in manager.admin_user_ids
    }

@system_management_router.post("/purge-unused-uploads", response_model=TaskInfo, status_code=202)
async def purge_temp_files(current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    db_task = task_manager.submit_task(
        name="Purge unused temporary files",
        target=_purge_unused_temp_files_task,
        description="Scans user temp folders and deletes files older than 24 hours.",
        owner_username=current_admin.username
    )
    return db_task

@system_management_router.get("/global-generation-stats", response_model=GlobalGenerationStats)
def get_global_generation_stats(db: Session = Depends(get_db)):
    all_users = db.query(DBUser).all()
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    daily_totals = defaultdict(int)

    for user in all_users:
        discussions_db_path = get_user_data_root(user.username) / "discussions.db"
        if discussions_db_path.exists():
            try:
                dm = LollmsDataManager(db_path=f"sqlite:///{discussions_db_path.resolve()}")
                with dm.get_session() as session:
                    results = session.query(
                        func.date(dm.MessageModel.created_at),
                        func.count(dm.MessageModel.id)
                    ).filter(
                        dm.MessageModel.sender_type == 'assistant',
                        dm.MessageModel.created_at >= thirty_days_ago
                    ).group_by(func.date(dm.MessageModel.created_at)).all()

                    for date_str, count in results:
                        daily_totals[date_str] += count
            except Exception as e:
                trace_exception(e)
                print(f"Warning: Could not process discussions DB for user {user.username}: {e}")

    # Prepare generations_per_day
    generations_per_day_list = [
        UserActivityStat(date=datetime.strptime(date_str, '%Y-%m-%d').date(), count=count)
        for date_str, count in daily_totals.items()
    ]
    generations_per_day_list.sort(key=lambda x: x.date)

    # Prepare weekday stats
    weekday_data = defaultdict(list)
    for stat in generations_per_day_list:
        weekday_data[stat.date.weekday()].append(stat.count)

    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    mean_per_weekday = {}
    variance_per_weekday = {}

    for i, day_name in enumerate(weekday_names):
        counts = weekday_data.get(i, [])
        if len(counts) > 0:
            mean_per_weekday[day_name] = statistics.mean(counts)
            variance_per_weekday[day_name] = statistics.variance(counts) if len(counts) > 1 else 0.0
        else:
            mean_per_weekday[day_name] = 0.0
            variance_per_weekday[day_name] = 0.0
            
    return GlobalGenerationStats(
        generations_per_day=generations_per_day_list,
        mean_per_weekday=mean_per_weekday,
        variance_per_weekday=variance_per_weekday
    )

@system_management_router.post("/backup/create", response_model=TaskInfo, status_code=202)
async def create_backup(
    request: BackupRequest,
    current_admin: UserAuthDetails = Depends(get_current_admin_user)
):
    """
    Initiates a background task to create a full application backup.
    """
    db_task = task_manager.submit_task(
        name="Create Application Backup",
        target=_create_backup_task,
        args=(request.password,),
        description="Creating a password-protected zip archive of the entire application.",
        owner_username=current_admin.username
    )
    return db_task
