# backend/routers/admin/system_management.py
import sys
import asyncio
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

import psutil
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, desc
from lollms_client import LollmsDataManager

from sqlalchemy.orm import Session, joinedload
from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.service import App as DBApp
from backend.db.models.connections import WebSocketConnection
from backend.db.models.db_task import DBTask
from backend.models import UserAuthDetails, SystemUsageStats, GPUInfo, DiskInfo, TaskInfo
from backend.models.admin import GlobalGenerationStats, UserActivityStat
from backend.config import PROJECT_ROOT, APP_DATA_DIR, SERVER_CONFIG, APP_VERSION, USERS_DIR_NAME, TEMP_UPLOADS_DIR_NAME
from backend.session import get_current_admin_user, get_user_data_root
from backend.ws_manager import manager
from backend.task_manager import task_manager, Task
from backend.utils import get_local_ip_addresses
from backend.tasks.system_tasks import _create_backup_task, _analyze_logs_task
from backend.settings import settings
from ascii_colors import trace_exception

system_management_router = APIRouter()

class AdminBroadcastRequest(BaseModel):
    message: str

class BackupRequest(BaseModel):
    password: str 

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
    url: str
    active_ports: List[AppPortInfo]
    cors_origins: List[str]
    local_ips: Optional[List[str]] = None

class GPUProcessInfo(BaseModel):
    pid: int
    name: str
    memory_used: float

class ExpandedGPUInfo(GPUInfo):
    gpu_utilization: int = 0
    processes: List[GPUProcessInfo] = []

class ExpandedSystemUsageStats(SystemUsageStats):
    gpus: List[ExpandedGPUInfo]

class KillProcessRequest(BaseModel):
    pid: int

class ModelUsageStat(BaseModel):
    model_name: str
    count: int

class LogEntry(BaseModel):
    task_id: str
    task_name: str
    timestamp: str
    level: str
    message: str

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
    return {"message": f"Purge complete. Scanned {total_scanned} files, deleted {deleted_count} files."}

@system_management_router.get("/system-status", response_model=ExpandedSystemUsageStats)
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
            nvmlDeviceGetMemoryInfo, nvmlDeviceGetName, nvmlDeviceGetComputeRunningProcesses,
            nvmlDeviceGetGraphicsRunningProcesses, nvmlDeviceGetUtilizationRates
        )
        nvmlInit()
        count = nvmlDeviceGetCount()
        for i in range(count):
            handle = nvmlDeviceGetHandleByIndex(i)
            name = nvmlDeviceGetName(handle)
            gpu_name = name.decode("utf-8") if isinstance(name, (bytes, bytearray)) else str(name)

            mem = nvmlDeviceGetMemoryInfo(handle)
            total_gb = mem.total / (1024 ** 3)
            used_gb  = mem.used  / (1024 ** 3)
            usage_pct = (mem.used / mem.total) * 100 if mem.total > 0 else 0.0

            # Get Compute Utilization
            gpu_util = 0
            try:
                util = nvmlDeviceGetUtilizationRates(handle)
                gpu_util = util.gpu
            except Exception:
                pass

            # Get processes
            procs = []
            try:
                compute_procs = nvmlDeviceGetComputeRunningProcesses(handle)
                graphics_procs = nvmlDeviceGetGraphicsRunningProcesses(handle)
                all_nvml_procs = compute_procs + graphics_procs
                
                for p in all_nvml_procs:
                    try:
                        sys_proc = psutil.Process(p.pid)
                        proc_name = sys_proc.name()
                    except psutil.NoSuchProcess:
                        proc_name = "Unknown/Terminated"
                    
                    mem_used = p.usedGpuMemory / (1024**2) if p.usedGpuMemory else 0 # MB
                    procs.append(GPUProcessInfo(pid=p.pid, name=proc_name, memory_used=mem_used))
            except Exception:
                pass

            gpus_info.append(ExpandedGPUInfo(
                id=i,
                name=gpu_name,
                vram_total_gb=total_gb,
                vram_used_gb=used_gb,
                vram_usage_percent=usage_pct,
                gpu_utilization=gpu_util,
                processes=procs
            ))
        nvmlShutdown()
    except (ImportError, Exception): pass

    return ExpandedSystemUsageStats(
        cpu_ram_total_gb=ram.total / (1024**3), cpu_ram_used_gb=ram.used / (1024**3),
        cpu_ram_available_gb=ram.available / (1024**3), cpu_ram_usage_percent=ram.percent,
        disks=disks_info, gpus=gpus_info,
    )

@system_management_router.post("/system/analyze-logs", response_model=TaskInfo, status_code=202)
async def analyze_logs(current_user: UserAuthDetails = Depends(get_current_admin_user)):
    """
    Triggers a task to analyze recent system logs using the LLM.
    """
    db_task = task_manager.submit_task(
        name="Analyze System Logs",
        target=_analyze_logs_task,
        args=(current_user.username,),
        description="Analyzing recent task logs and system events for issues.",
        owner_username=current_user.username
    )
    return db_task

@system_management_router.get("/system/logs", response_model=List[LogEntry])
async def get_system_logs(limit: int = 200, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_admin_user)):
    """
    Retrieves aggregated logs from recent tasks.
    """
    recent_tasks = db.query(DBTask).order_by(desc(DBTask.updated_at)).limit(50).all()
    
    all_logs = []
    for t in recent_tasks:
        if t.logs:
            for l in t.logs:
                all_logs.append(LogEntry(
                    task_id=t.id,
                    task_name=t.name,
                    timestamp=l.get('timestamp') or datetime.now().isoformat(),
                    level=l.get('level', 'INFO'),
                    message=l.get('message', '')
                ))
    
    # Sort by timestamp descending
    all_logs.sort(key=lambda x: x.timestamp, reverse=True)
    return all_logs[:limit]

@system_management_router.post("/system/kill-process")
async def kill_process(payload: KillProcessRequest, current_user: UserAuthDetails = Depends(get_current_admin_user)):
    try:
        proc = psutil.Process(payload.pid)
        proc.kill()
        return {"message": f"Process {payload.pid} killed."}
    except psutil.NoSuchProcess:
        raise HTTPException(status_code=404, detail="Process not found.")
    except psutil.AccessDenied:
        raise HTTPException(status_code=403, detail="Permission denied to kill process.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@system_management_router.get("/model-usage-stats", response_model=List[ModelUsageStat])
async def get_model_usage_stats(db: Session = Depends(get_db)):
    results = db.query(DBUser.lollms_model_name, func.count(DBUser.id)).group_by(DBUser.lollms_model_name).all()
    stats = []
    for model_name, count in results:
        stats.append(ModelUsageStat(model_name=model_name or "Not Set", count=count))
    
    return sorted(stats, key=lambda x: x.count, reverse=True)

@system_management_router.get("/server-info", response_model=ServerInfo)
async def get_server_info(request: Request, db: Session = Depends(get_db)):
    running_apps = db.query(DBApp).filter(DBApp.status == 'running', DBApp.port != None).all()
    active_ports = [AppPortInfo(port=app.port, app_name=app.name, app_id=app.id) for app in running_apps]

    allowed_origins = next((m.options.get('allow_origins', []) for m in request.app.user_middleware if "CORSMiddleware" in str(m)), [])
    
    # Use 'settings' to get the live value from DB if available, fallback to env/default
    host = settings.get("host", SERVER_CONFIG.get("host", "localhost"))
    port = settings.get("port", SERVER_CONFIG.get("port", 9642))
    https = settings.get("https_enabled", SERVER_CONFIG.get("https_enabled", False))
    protocol = "https" if https else "http"
    
    local_ips = None
    if host == "0.0.0.0":
        local_ips = get_local_ip_addresses()
        display_host = local_ips[0] if local_ips else "localhost"
    else:
        display_host = host

    url = f"{protocol}://{display_host}:{port}"

    return ServerInfo(
        lollms_version=APP_VERSION, python_version=sys.version,
        host=host, port=port,
        https_enabled=https,
        url=url,
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
        description="Creating a secure password-protected zip archive of the entire application.",
        owner_username=current_admin.username
    )
    return db_task
