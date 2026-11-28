# backend/routers/admin/system_management.py
import sys
import os
import asyncio
import statistics
import subprocess
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

import psutil
from fastapi import APIRouter, Depends, Request, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, desc, update
from lollms_client import LollmsDataManager
from packaging.requirements import Requirement
from importlib.metadata import version as get_installed_version, PackageNotFoundError
from packaging.version import parse as parse_version


from sqlalchemy.orm import Session, joinedload, defer
from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.service import App as DBApp
from backend.db.models.connections import WebSocketConnection
from backend.db.models.db_task import DBTask
from backend.models import UserAuthDetails, SystemUsageStats, GPUInfo, DiskInfo, TaskInfo
from backend.models.admin import GlobalGenerationStats, UserActivityStat, ForceGlobalConfigPayload, RequirementInfo, InstallReqPayload
from backend.config import PROJECT_ROOT, APP_DATA_DIR, SERVER_CONFIG, APP_VERSION, USERS_DIR_NAME, TEMP_UPLOADS_DIR_NAME
from backend.session import get_current_admin_user, get_user_data_root, user_sessions
from backend.ws_manager import manager
from backend.task_manager import task_manager, Task
from backend.utils import get_local_ip_addresses
from backend.tasks.system_tasks import _create_backup_task, _analyze_logs_task, _prune_old_tasks_task
from backend.settings import settings
from ascii_colors import trace_exception, ASCIIColors

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
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    energy_kwh: float = 0.0
    co2_g: float = 0.0
    percentage: float = 0.0

class LogEntry(BaseModel):
    task_id: str
    task_name: str
    timestamp: str
    level: str
    message: str


class ComposeEmailRequest(BaseModel):
    """Request payload for AI-driven email authoring from a natural-language brief.

    Unlike /enhance-email (which rewrites an already-written draft), /compose-email
    generates the ENTIRE message (subject + body) from a prompt, so an admin can
    say "invite users to try the new Flow Studio with a punchy headline" and get
    a complete, ready-to-send draft.
    """
    prompt: str
    tone: Optional[str] = "professional"
    language: Optional[str] = "en"
    background_color: Optional[str] = None
    include_subject: bool = True


class ComposeEmailResponse(BaseModel):
    subject: str = ""
    body: str = ""

@system_management_router.post("/system/force-all-users-config", response_model=Dict[str, str])
async def force_all_users_config(payload: ForceGlobalConfigPayload, db: Session = Depends(get_db)):
    """
    Instantly updates all users in the database to use specific models for various services.
    Also clears active server-side sessions to enforce the change immediately on the next request.
    """
    try:
        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No configuration provided to force.")
        
        # Batch update all users
        stmt = update(DBUser).values(**update_data)
        result = db.execute(stmt)
        db.commit()
        
        # Clear all in-memory user sessions to force client re-initialization
        user_sessions.clear()
        
        # Notify all connected clients that their configuration has changed
        await manager.broadcast({"type": "settings_updated", "data": {"reason": "global_force_update"}})
        
        return {"message": f"Successfully forced configuration on {result.rowcount} users."}
    except Exception as e:
        db.rollback()
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to apply global configuration: {str(e)}")

def _run_pip_install(task: Task, pkg_name: str, pkg_version: str, extra_flags: Optional[List[str]] = None) -> tuple[bool, List[str]]:
    """
    Runs a hardened pip install subprocess, streaming its output to the task log
    while capturing a bounded tail of the last lines for diagnostics.
    Returns (success, tail_lines).
    """
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--no-cache-dir", "--disable-pip-version-check", "--no-input"
    ]
    if pkg_version:
        cmd.append(f"{pkg_name}=={pkg_version}")
    else:
        cmd.append("--upgrade")
        cmd.append(pkg_name)
    if extra_flags:
        cmd.extend(extra_flags)

    tail: deque = deque(maxlen=15)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    task.process = process
    for line in process.stdout:
        stripped = line.strip()
        if stripped:
            task.log(stripped)
            tail.append(stripped)

    process.wait()
    return process.returncode == 0, list(tail)


def _install_with_pep668_retry(task: Task, pkg_name: str, pkg_version: str) -> tuple[bool, List[str]]:
    """
    Attempts a pip install; on failure caused by an externally-managed environment
    (PEP 668), retries once with --break-system-packages.
    Returns (success, tail_lines_of_final_attempt).
    """
    success, tail = _run_pip_install(task, pkg_name, pkg_version)
    if success:
        return True, tail

    if any("externally-managed-environment" in line for line in tail):
        task.log(
            "Externally managed environment detected, retrying with --break-system-packages",
            level="WARNING"
        )
        retry_success, retry_tail = _run_pip_install(
            task, pkg_name, pkg_version, extra_flags=["--break-system-packages"]
        )
        if retry_success:
            return True, retry_tail
        return False, tail + retry_tail

    return False, tail


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

            gpu_util = 0
            try:
                util = nvmlDeviceGetUtilizationRates(handle)
                gpu_util = util.gpu
            except Exception:
                pass

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
                    
                    mem_used = p.usedGpuMemory / (1024**2) if p.usedGpuMemory else 0 
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
    db_task = task_manager.submit_task(
        name="Analyze System Logs",
        target=_analyze_logs_task,
        args=(current_user.username,),
        description="Analyzing recent task logs and system events for issues.",
        owner_username=current_user.username
    )
    return db_task

class ConsoleLogEntry(BaseModel):
    """One row of the merged console log feed.

    ``source`` distinguishes task logs from captured stdout/stderr so the admin
    UI can filter visually. ``task_name`` is populated for task logs only.
    """
    id: str
    timestamp: str
    level: str
    source: str
    message: str
    task_name: Optional[str] = None


@system_management_router.get("/system/console-logs", response_model=List[ConsoleLogEntry])
async def get_console_logs(
    hours: int = Query(24, ge=1, le=168, description="Look-back window in hours (1..168)."),
    limit: int = Query(500, ge=1, le=2000, description="Maximum number of rows to return."),
    include_tasks: bool = Query(True, description="Merge background-task logs into the feed."),
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_admin_user),
):
    """Return the real server console output (stdout/stderr) for the last N hours.

    Unlike ``/system/logs`` (which only surfaces ``DBTask.logs``), this endpoint
    reads the process-level ring buffer populated by ``backend.log_buffer`` —
    the same buffer that powers ``/system/process-logs``. It captures everything
    printed to the console (``print``, ``ascii_colors`` panels, uvicorn
    access/error lines, ``logging`` records) so the feed is never empty just
    because no background task happened to run.

    ``include_tasks`` optionally merges task logs (with ``source='task'``) so the
    caller gets a single, chronologically sorted operations feed.
    """
    from backend.log_buffer import get_logs

    merged: List[Dict[str, Any]] = []

    # 1. Captured stdout/stderr (+ logging records) from the ring buffer.
    # ``get_logs`` already strips ANSI/ascii_colors markup at capture time, so
    # the message is plain text suitable for JSON/HTML rendering.
    try:
        for i, entry in enumerate(get_logs(hours=hours, limit=limit)):
            merged.append({
                "id": f"sb-{i}-{entry.get('timestamp', '')}",
                "timestamp": entry.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                "level": entry.get("level") or "INFO",
                "source": entry.get("source") or "stdout",
                "message": entry.get("message") or "",
                "task_name": None,
            })
    except Exception as e:
        trace_exception(e)

    # 2. Background-task logs, scoped to the same time window.
    if include_tasks:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            recent_tasks = db.query(DBTask)\
                .options(defer(DBTask.result), defer(DBTask.error))\
                .filter(DBTask.updated_at >= cutoff)\
                .order_by(desc(DBTask.updated_at))\
                .limit(50)\
                .all()
            for t in recent_tasks:
                if not t.logs:
                    continue
                for i, log in enumerate(t.logs):
                    ts = log.get("timestamp") or datetime.now(timezone.utc).isoformat()
                    merged.append({
                        "id": f"task-{t.id}-{i}",
                        "timestamp": ts,
                        "level": (log.get("level") or "INFO").upper(),
                        "source": "task",
                        "message": log.get("message") or "",
                        "task_name": t.name,
                    })
        except Exception as e:
            trace_exception(e)

    # Chronological sort (newest first) then apply the hard limit.
    def _sort_key(row: Dict[str, Any]):
        try:
            return datetime.fromisoformat(str(row.get("timestamp")))
        except (ValueError, TypeError):
            return datetime.now(timezone.utc)

    merged.sort(key=_sort_key, reverse=True)
    return merged[:limit]


@system_management_router.get("/system/logs", response_model=List[LogEntry])
async def get_system_logs(limit: int = 200, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_admin_user)):
    recent_tasks = db.query(DBTask)\
        .options(defer(DBTask.result), defer(DBTask.error))\
        .order_by(desc(DBTask.updated_at))\
        .limit(30)\
        .all()
    
    all_logs = []
    count = 0
    
    for t in recent_tasks:
        if t.logs:
            for l in reversed(t.logs): 
                all_logs.append(LogEntry(
                    task_id=t.id,
                    task_name=t.name,
                    timestamp=l.get('timestamp') or datetime.now().isoformat(),
                    level=l.get('level', 'INFO'),
                    message=l.get('message', '')
                ))
                count += 1
                if count >= limit:
                    break
        if count >= limit:
            break
    
    all_logs.sort(key=lambda x: x.timestamp, reverse=True)
    return all_logs[:limit]


class ProcessLogEntry(BaseModel):
    timestamp: str
    level: str
    source: str
    message: str


class ProcessLogsResponse(BaseModel):
    entries: List[ProcessLogEntry]
    window_hours: float
    total_in_buffer: int
    count: int


@system_management_router.get("/system/process-logs", response_model=ProcessLogsResponse)
async def get_process_logs(
    hours: float = Query(24.0, ge=0, le=24 * 90, description="Time window in hours. 0 = everything retained."),
    limit: int = Query(500, ge=1, le=5000, description="Maximum number of (newest) lines to return."),
    level: Optional[str] = Query(None, description="Exact level filter (DEBUG/INFO/WARNING/ERROR/CRITICAL)."),
    source: Optional[str] = Query(None, description="Exact source filter (stdout/stderr/app)."),
    _admin: UserAuthDetails = Depends(get_current_admin_user),
):
    """Return this process's captured stdout/stderr/app output.

    Complements ``/system/logs`` (background task logs). The raw console output
    of the server — uvicorn lines, tracebacks, startup banners — is tee'd into
    an in-memory ring buffer by ``backend.log_buffer`` and served here so the
    admin "Live operations log" panel is never empty just because no background
    task ran recently.
    """
    from backend.log_buffer import get_logs, buffer_size

    try:
        entries = get_logs(hours=hours, limit=limit, level=level, source=source)
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to read process logs: {e}")

    # Defense-in-depth: strip any ANSI color codes / control characters that
    # survived capture (ascii_colors and uvicorn emit "\x1b[..m" SGR codes).
    # The buffer already sanitizes at write time, but re-cleaning here keeps the
    # API honest if a line ever arrives through another capture path.
    from backend.log_buffer import strip_ansi
    cleaned = []
    for e in entries:
        row = dict(e)
        row["message"] = strip_ansi(row.get("message") or "")
        cleaned.append(ProcessLogEntry(**row))

    return ProcessLogsResponse(
        entries=cleaned,
        window_hours=hours,
        total_in_buffer=buffer_size(),
        count=len(cleaned),
    )


@system_management_router.post("/system/process-logs/clear", response_model=Dict[str, int])
async def clear_process_logs(_admin: UserAuthDetails = Depends(get_current_admin_user)):
    """Empty the process-log ring buffer. Returns the number of dropped lines."""
    from backend.log_buffer import clear_logs
    return {"cleared": clear_logs()}


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

class TopUserStat(BaseModel):
    user_id: int
    username: str
    icon: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0


# ---------------------------------------------------------------------------
# Rich token consumption analytics
# ---------------------------------------------------------------------------
# The admin dashboard needs fine-grained, multi-dimensional views of token
# consumption. ``GenerationMetric`` is the single source of truth for all
# metered generations (WebUI chat tagged ``source='chat'``; every external API
# surface tagged ``source!='chat'``). All aggregation happens in SQL so the
# endpoint stays responsive as the table grows into the millions of rows.


class ConsumptionBucket(BaseModel):
    label: str
    bucket: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0
    webui_input_tokens: int = 0
    webui_output_tokens: int = 0
    webui_tokens: int = 0
    webui_calls: int = 0
    api_input_tokens: int = 0
    api_output_tokens: int = 0
    api_tokens: int = 0
    api_calls: int = 0




class ConsumptionTotals(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0
    webui_input_tokens: int = 0
    webui_output_tokens: int = 0
    webui_tokens: int = 0
    webui_calls: int = 0
    api_input_tokens: int = 0
    api_output_tokens: int = 0
    api_tokens: int = 0
    api_calls: int = 0
    energy_kwh: float = 0.0
    co2_g: float = 0.0




class ConsumptionBreakdownItem(BaseModel):
    """One row of the Top Models / Top Users breakdown tables.

    ``name`` is the generic identity field (model name or username). The
    frontend also reads the semantic aliases ``model_name`` / ``username`` and
    ``calls``, so they are all declared here — an undeclared field would be
    silently dropped by ``_only`` and the panel would render blanks.
    """
    name: str = ""
    model_name: Optional[str] = None
    username: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0
    percentage: float = 0.0


class ConsumptionAnalyticsResponse(BaseModel):
    granularity: str
    source: str
    days: int
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    totals: ConsumptionTotals = ConsumptionTotals()
    buckets: List[ConsumptionBucket] = []
    by_model: List[ConsumptionBreakdownItem] = []
    by_user: List[ConsumptionBreakdownItem] = []
    avg_tokens_per_call: float = 0
    avg_output_per_call: float = 0
    input_output_ratio: str = "—"
    peak_bucket: Optional[str] = None



_VALID_GRANULARITIES = {"hour", "day", "week", "month"}
_VALID_SOURCE_SCOPES = {"all", "webui", "api"}


def _bucket_sql_expr(granularity: str):
    """Return a SQLAlchemy expression producing a sortable bucket string.

    SQLite's ``strftime`` gives us deterministic ISO-like strings:
      * hour  -> ``YYYY-MM-DD HH:00``
      * day   -> ``YYYY-MM-DD``
      * week  -> ``YYYY-Www`` (ISO week)
      * month -> ``YYYY-MM``
    These sort lexicographically, so no extra ordering expression is needed.
    """
    from backend.db.models.generation_metric import GenerationMetric

    col = GenerationMetric.created_at
    if granularity == "hour":
        return func.strftime("%Y-%m-%d %H:00", col)
    if granularity == "day":
        return func.strftime("%Y-%m-%d", col)
    if granularity == "week":
        return func.strftime("%Y-W%W", col)
    return func.strftime("%Y-%m", col)


def _humanize_bucket_label(bucket: str, granularity: str) -> str:
    """Turn a raw bucket string into a human-friendly label."""
    if not bucket:
        return bucket
    try:
        if granularity == "hour":
            return bucket  # "2025-11-25 14:00"
        if granularity == "day":
            dt = datetime.strptime(bucket, "%Y-%m-%d")
            return dt.strftime("%a %d %b")
        if granularity == "month":
            dt = datetime.strptime(bucket, "%Y-%m")
            return dt.strftime("%b %Y")
        # week: "YYYY-Www"
        year, week = bucket.split("-W")
        return f"Wk {int(week):02d} {year}"
    except Exception:
        return bucket



def _source_values_for(scope: str):
    """Map a UI 'source' scope to the concrete ``GenerationMetric.source`` values.

    WebUI chat records ``source="chat"``; every external/API surface records a
    different token (e.g. ``"openai"``, ``"ollama"``, ``"lollms"``, ``"api"``).
    Keeping this mapping in one place ensures the on-screen report and the
    export never disagree about what counts as "API".
    """
    scope = (scope or "all").lower()
    if scope == "webui":
        return ("chat", "webui")
    if scope == "api":
        return ("openai", "ollama", "lollms", "api", "service", "openai_v1", "ollama_v1", "lollms_v1")
    return None



@system_management_router.get("/system/consumption-analytics", response_model=ConsumptionAnalyticsResponse)
def get_consumption_analytics(
    granularity: str = Query("day", description="hour|day|week|month"),
    source: str = Query("all", description="all|webui|api"),
    days: int = Query(30, ge=0, le=3650),
    top_n: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: UserAuthDetails = Depends(get_current_admin_user),
):
    """Fine-grained token consumption analytics.

    Aggregation is done in Python over the raw ``generation_metrics`` rows so the
    result is identical on SQLite and PostgreSQL and never depends on
    dialect-specific date functions. ``source`` filters via a value-set mapping
    (webui -> chat; api -> openai/ollama/lollms/...).
    """
    from datetime import datetime, timedelta
    from datetime import datetime, timedelta
    from backend.db.models.generation_metric import GenerationMetric
    from collections import defaultdict

    if granularity not in ("hour", "day", "week", "month"):
        granularity = "day"

    query = db.query(GenerationMetric)
    if days and days > 0:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(GenerationMetric.created_at >= cutoff)
    source_values = _source_values_for(source)
    if source_values is not None:
        query = query.filter(GenerationMetric.source.in_(source_values))

    rows = query.all()

    def _normalize_dt(dt):
        if dt is None:
            return datetime.utcnow()
        if isinstance(dt, str):
            try:
                return datetime.fromisoformat(dt)
            except ValueError:
                return datetime.utcnow()
        return dt

    def _bucket_key(dt):
        if granularity == "hour":
            return dt.strftime("%Y-%m-%d %H:00")
        if granularity == "week":
            iso = dt.isocalendar()
            return f"{iso[0]}-W{iso[1]:02d}"
        if granularity == "month":
            return dt.strftime("%Y-%m")
        return dt.strftime("%Y-%m-%d")

    def _is_api_source(src):
        return src in ("openai", "ollama", "lollms", "api", "openai_v1", "ollama_v1", "lollms_v1")

    buckets = defaultdict(lambda: {
        "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "calls": 0,
        "webui_input_tokens": 0, "webui_output_tokens": 0, "webui_tokens": 0, "webui_calls": 0,
        "api_input_tokens": 0, "api_output_tokens": 0, "api_tokens": 0, "api_calls": 0,
    })
    totals = {
        "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "calls": 0,
        "webui_input_tokens": 0, "webui_output_tokens": 0, "webui_tokens": 0, "webui_calls": 0,
        "api_input_tokens": 0, "api_output_tokens": 0, "api_tokens": 0, "api_calls": 0,
    }
    model_totals = defaultdict(lambda: {"model_name": "", "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "calls": 0})
    user_totals = defaultdict(lambda: {"username": "", "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "calls": 0})
    energy_kwh = 0.0
    co2_g = 0.0

    for row in rows:
        dt = _normalize_dt(row.created_at)
        key = _bucket_key(dt)
        b = buckets[key]
        pt = int(row.prompt_tokens or 0)
        ct = int(row.completion_tokens or 0)
        tt = int(row.total_tokens or (pt + ct))
        b["input_tokens"] += pt
        b["output_tokens"] += ct
        b["total_tokens"] += tt
        b["calls"] += 1
        totals["input_tokens"] += pt
        totals["output_tokens"] += ct
        totals["total_tokens"] += tt
        totals["calls"] += 1
        energy_kwh += float(row.energy_kwh or 0)
        co2_g += float(row.co2_g or 0)

        if _is_api_source(row.source):
            b["api_input_tokens"] += pt
            b["api_output_tokens"] += ct
            b["api_tokens"] += tt
            b["api_calls"] += 1
            totals["api_input_tokens"] += pt
            totals["api_output_tokens"] += ct
            totals["api_tokens"] += tt
            totals["api_calls"] += 1
        else:
            b["webui_input_tokens"] += pt
            b["webui_output_tokens"] += ct
            b["webui_tokens"] += tt
            b["webui_calls"] += 1
            totals["webui_input_tokens"] += pt
            totals["webui_output_tokens"] += ct
            totals["webui_tokens"] += tt
            totals["webui_calls"] += 1

        mname = row.model_name or "unknown"
        mt = model_totals[mname]
        mt["model_name"] = mname
        mt["input_tokens"] += pt
        mt["output_tokens"] += ct
        mt["total_tokens"] += tt
        mt["calls"] += 1

        uname = row.username or "anonymous"
        ut = user_totals[uname]
        ut["username"] = uname
        ut["input_tokens"] += pt
        ut["output_tokens"] += ct
        ut["total_tokens"] += tt
        ut["calls"] += 1

    order = sorted(buckets.keys(), reverse=(granularity == "hour"))
    if granularity in ("day", "week", "month"):
        order = sorted(buckets.keys())

    bucket_list = []
    for key in order:
        b = buckets[key]
        # ``bucket`` carries the raw sortable key (e.g. "2025-11-25", "2025-W48");
        # ``label`` carries the human-friendly rendering. Both are declared on
        # ConsumptionBucket, so both must be supplied or pydantic raises
        # "Field required".
        bucket_list.append({
            "label": _humanize_bucket_label(key, granularity),
            "bucket": key,
            **b,
        })

    model_share_base = totals["total_tokens"] or 1
    model_list = sorted(model_totals.values(), key=lambda x: x["total_tokens"], reverse=True)[:top_n]
    for m in model_list:
        m["percentage"] = round((m["total_tokens"] / model_share_base) * 100, 1)
        # Mirror ``model_name`` into the generic ``name`` field so the item
        # validates against ``ConsumptionBreakdownItem`` while still exposing
        # the semantic key the frontend template binds to.
        m["name"] = m.get("model_name") or "unknown"

    user_share_base = totals["total_tokens"] or 1
    user_list = sorted(user_totals.values(), key=lambda x: x["total_tokens"], reverse=True)[:top_n]
    for u in user_list:
        u["percentage"] = round((u["total_tokens"] / user_share_base) * 100, 1)
        u["name"] = u.get("username") or "anonymous"

    ratio = "—"
    if totals["output_tokens"] > 0:
        ratio = f"{round(totals['input_tokens'] / totals['output_tokens'], 2)}:1"
    avg_tokens_per_call = round(totals["total_tokens"] / totals["calls"], 1) if totals["calls"] else 0
    avg_output_per_call = round(totals["output_tokens"] / totals["calls"], 1) if totals["calls"] else 0

    peak_bucket_label = None
    if bucket_list:
        peak = max(bucket_list, key=lambda x: x["total_tokens"])
        peak_bucket_label = peak["label"]

    def _only(model_cls, data):
        # Pass only the fields the pydantic model actually declares, so the
        # endpoint can never 500 on an unexpected-attribute ValidationError if
        # the response schema evolves independently of the aggregation code.
        #
        # ``required`` fields that the aggregation forgot to populate are
        # backfilled with an empty-string default so a schema/aggregation drift
        # degrades gracefully instead of taking down the whole report.
        fields = getattr(model_cls, "model_fields", {}) or {}
        allowed = set(fields)
        filtered = {k: v for k, v in data.items() if k in allowed}
        for name, field in fields.items():
            if name in filtered:
                continue
            if not field.is_required():
                continue
            # Only strings are silently defaulted; a missing numeric/other
            # required field is a genuine bug that should still surface loudly.
            if field.annotation is str:
                filtered[name] = ""
            else:
                raise ValueError(
                    f"Missing required field '{name}' for {model_cls.__name__}"
                )
        return model_cls(**filtered)

    totals_payload = {"energy_kwh": round(energy_kwh, 4), "co2_g": round(co2_g, 4), **totals}

    # ConsumptionAnalyticsResponse declares ``granularity``, ``source`` AND
    # ``days`` as REQUIRED fields. ``days`` must be forwarded from the query
    # param or FastAPI's response validation fails with
    # ``Missing required field 'days'`` (propagated as HTTP 500 by the
    # ``_only`` helper). ``window_start`` / ``window_end`` are populated when a
    # finite window was requested; ``None`` is acceptable for "all time".
    window_start_iso = None
    window_end_iso = None
    if days and days > 0:
        _end = datetime.utcnow()
        _start = _end - timedelta(days=days)
        window_start_iso = _start.isoformat()
        window_end_iso = _end.isoformat()

    # ``ConsumptionAnalyticsResponse`` declares ``by_model`` and ``by_user`` as
    # ``List[dict]``. Building ``ConsumptionBreakdownItem`` instances here and
    # then handing them to the response validator triggers
    # ``Input should be a valid dictionary`` (a model instance is not a dict).
    # Pass the aggregated dicts straight through; ``_only`` is reserved for the
    # strictly-typed sub-objects (``buckets``, ``totals``) and the top-level
    # response whose inner typing we *do* want to enforce.
    response_payload = {
        "granularity": granularity,
        "source": source,
        "days": days,
        "window_start": window_start_iso,
        "window_end": window_end_iso,
        "buckets": [_only(ConsumptionBucket, b) for b in bucket_list],
        "totals": _only(ConsumptionTotals, totals_payload),
        "by_model": list(model_list),
        "by_user": list(user_list),
        "input_output_ratio": ratio,
        "avg_tokens_per_call": avg_tokens_per_call,
        "avg_output_per_call": avg_output_per_call,
        "peak_bucket": peak_bucket_label,
    }
    return _only(ConsumptionAnalyticsResponse, response_payload)



@system_management_router.get("/top-users", response_model=List[TopUserStat])
async def get_top_users(
    source: Optional[str] = Query(None, description="Filter by source: 'chat' (WebUI), 'api', or omit for all"),
    metric: str = Query("total_tokens", description="Ranking metric: 'input_tokens', 'output_tokens', 'total_tokens', or 'calls'"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of users to return"),
    days: int = Query(0, ge=0, le=3650, description="Restrict aggregation to the last N days. 0 = all time."),
    db: Session = Depends(get_db),
):
    """
    Return the top users by a chosen metric within an optional source scope.

    The four supported metrics map cleanly to a single sortable integer column:
      - 'input_tokens'   -> SUM(prompt_tokens)
      - 'output_tokens'  -> SUM(completion_tokens)
      - 'total_tokens'   -> SUM(total_tokens)
      - 'calls'          -> COUNT(GenerationMetric.id)

    ``source='chat'`` scopes to the WebUI chat surface, ``source='api'`` scopes
    to every external API surface. Omitting ``source`` aggregates both.

    Admin-authored dashboards frequently pivot between these four criteria and
    two scopes; doing the aggregation in SQL keeps the frontend honest even as
    the raw ``generation_metrics`` table grows into the millions of rows.
    """
    from backend.db.models.generation_metric import GenerationMetric

    metric_norm = (metric or "total_tokens").strip().lower()
    metric_expr_map = {
        "input_tokens": func.coalesce(func.sum(GenerationMetric.prompt_tokens), 0),
        "output_tokens": func.coalesce(func.sum(GenerationMetric.completion_tokens), 0),
        "total_tokens": func.coalesce(func.sum(GenerationMetric.total_tokens), 0),
        "calls": func.count(GenerationMetric.id),
    }
    if metric_norm not in metric_expr_map:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported metric '{metric}'. Valid values: "
                f"{', '.join(metric_expr_map.keys())}."
            ),
        )
    rank_expr = metric_expr_map[metric_norm]

    query = db.query(
        GenerationMetric.user_id,
        GenerationMetric.username,
        func.coalesce(func.sum(GenerationMetric.prompt_tokens), 0).label("prompt_tokens"),
        func.coalesce(func.sum(GenerationMetric.completion_tokens), 0).label("completion_tokens"),
        func.coalesce(func.sum(GenerationMetric.total_tokens), 0).label("total_tokens"),
        func.count(GenerationMetric.id).label("calls"),
    ).group_by(GenerationMetric.user_id, GenerationMetric.username)

    if source:
        source_norm = source.strip().lower()
        # 'webui' is accepted as an alias for the canonical 'chat' source tag.
        if source_norm in ("webui", "chat"):
            query = query.filter(GenerationMetric.source == "chat")
        elif source_norm == "api":
            query = query.filter(GenerationMetric.source != "chat")
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported source '{source}'. Valid values: 'webui', 'chat', 'api'.",
            )

    if days and days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.filter(GenerationMetric.created_at >= cutoff)

    rows = query.order_by(desc(rank_expr)).limit(limit).all()

    # Resolve icons in one shot to avoid N+1 queries.
    user_ids = [r[0] for r in rows if r[0] is not None]
    icons_by_id: Dict[int, Optional[str]] = {}
    if user_ids:
        icon_rows = db.query(DBUser.id, DBUser.icon).filter(DBUser.id.in_(user_ids)).all()
        icons_by_id = {uid: icon for uid, icon in icon_rows}

    return [
        TopUserStat(
            user_id=user_id if user_id is not None else 0,
            username=username or "unknown",
            icon=icons_by_id.get(user_id),
            prompt_tokens=int(prompt_tokens or 0),
            completion_tokens=int(completion_tokens or 0),
            total_tokens=int(total_tokens or 0),
            calls=int(calls or 0),
        )
        for user_id, username, prompt_tokens, completion_tokens, total_tokens, calls in rows
    ]


@system_management_router.get("/system/consumption-analytics/export")
def export_consumption_analytics(
    format: str = Query("html", pattern="^(html|pdf|docx|xlsx)$"),
    granularity: str = Query("day", pattern="^(hour|day|week|month)$"),
    source: str = Query("all"),
    days: int = Query(30, ge=0, le=3650),
    top_n: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: UserAuthDetails = Depends(get_current_admin_user),
):
    """Export the consumption report.

    Reuses ``get_consumption_analytics`` as the single source of truth so the
    exported document always matches the on-screen view (no duplicate SQL that
    could drift or fail). Supports html/pdf/docx/xlsx.
    """
    import io as _io
    from datetime import datetime as _dt

    # Defensive: generation_analytics returns a Pydantic model instance.
    report = get_consumption_analytics(
        granularity=granularity,
        source=source,
        days=days,
        top_n=top_n,
        db=db,
        _admin=_admin,
    )
    data = report.model_dump() if hasattr(report, "model_dump") else report
    data = report.dict() if not isinstance(data, dict) and hasattr(report, "dict") else data

    stamp = _dt.now().strftime("%Y-%m-%d %H:%M")
    title = "Token Consumption Report"
    subtitle = f"Granularity: {granularity} · Source: {source} · Window: {days or 'all'} day(s) · Generated: {stamp}"

    def _num(n):
        try:
            return f"{int(n):,}"
        except Exception:
            return str(n)

    totals = data.get("totals", {})
    buckets = data.get("buckets", [])
    by_model = data.get("by_model", [])
    by_user = data.get("by_user", [])

    if format == "html":
        rows = "".join(
            f"<tr><td>{b.get('label','')}</td><td>{_num(b.get('input_tokens',0))}</td>"
            f"<td>{_num(b.get('output_tokens',0))}</td><td>{_num(b.get('total_tokens',0))}</td>"
            f"<td>{_num(b.get('calls',0))}</td></tr>"
            for b in buckets
        )
        model_rows = "".join(
            f"<tr><td>{m.get('model_name','')}</td><td>{_num(m.get('input_tokens',0))}</td>"
            f"<td>{_num(m.get('output_tokens',0))}</td><td>{_num(m.get('total_tokens',0))}</td>"
            f"<td>{m.get('percentage',0)}%</td></tr>"
            for m in by_model
        )
        user_rows = "".join(
            f"<tr><td>{u.get('username','')}</td><td>{_num(u.get('input_tokens',0))}</td>"
            f"<td>{_num(u.get('output_tokens',0))}</td><td>{_num(u.get('total_tokens',0))}</td>"
            f"<td>{u.get('percentage',0)}%</td></tr>"
            for u in by_user
        )
        kpi = (
            f"<div class='kpi'><b>Total tokens:</b> {_num(totals.get('total_tokens',0))} "
            f"(<span style='color:#2563eb'>{_num(totals.get('input_tokens',0))} in</span> · "
            f"<span style='color:#059669'>{_num(totals.get('output_tokens',0))} out</span>)</div>"
            f"<div class='kpi'><b>Calls:</b> {_num(totals.get('calls',0))}</div>"
            f"<div class='kpi'><b>WebUI / API tokens:</b> {_num(totals.get('webui_tokens',0))} / {_num(totals.get('api_tokens',0))}</div>"
            f"<div class='kpi'><b>Energy:</b> {totals.get('energy_kwh',0)} kWh · {totals.get('co2_g',0)} g CO₂</div>"
        )
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:32px;color:#1f2937;}}
h1{{font-size:22px;margin:0 0 4px;}} .sub{{color:#6b7280;font-size:12px;margin-bottom:20px;}}
.kpi{{padding:6px 0;font-size:13px;border-bottom:1px solid #eee;}}
table{{border-collapse:collapse;width:100%;margin:12px 0 24px;font-size:12px;}}
th,td{{border:1px solid #e5e7eb;padding:6px 8px;text-align:left;}}
th{{background:#f3f4f6;font-weight:700;}}
h2{{font-size:15px;margin:24px 0 4px;}}
</style></head><body>
<h1>{title}</h1><div class="sub">{subtitle}</div>
<div>{kpi}</div>
<h2>Consumption over time ({granularity})</h2>
<table><thead><tr><th>Period</th><th>Input</th><th>Output</th><th>Total</th><th>Calls</th></tr></thead>
<tbody>{rows or '<tr><td colspan="5">No data</td></tr>'}</tbody></table>
<h2>Top models</h2>
<table><thead><tr><th>Model</th><th>Input</th><th>Output</th><th>Total</th><th>Share</th></tr></thead>
<tbody>{model_rows or '<tr><td colspan="5">No data</td></tr>'}</tbody></table>
<h2>Top users</h2>
<table><thead><tr><th>User</th><th>Input</th><th>Output</th><th>Total</th><th>Share</th></tr></thead>
<tbody>{user_rows or '<tr><td colspan="5">No data</td></tr>'}</tbody></table>
</body></html>"""
        from fastapi import Response as _Resp
        return _Resp(
            content=html.encode("utf-8"),
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename=\"token_consumption_{_dt.now().strftime("%Y%m%d_%H%M%S")}.html\"'},
        )

    if format == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.chart import BarChart, PieChart, Reference
        from fastapi import Response as _Resp

        HEADER_FILL = PatternFill("solid", fgColor="4F46E5")
        HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
        TITLE_FONT = Font(bold=True, size=16, color="1F2937")
        SUB_FONT = Font(italic=True, size=10, color="6B7280")
        SECTION_FONT = Font(bold=True, size=13, color="1F2937")
        _thin = Side(style="thin", color="E5E7EB")
        BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)
        CENTER = Alignment(horizontal="center", vertical="center")

        def style_header(sheet, row, ncols):
            for c in range(1, ncols + 1):
                cell = sheet.cell(row=row, column=c)
                cell.fill = HEADER_FILL
                cell.font = HEADER_FONT
                cell.alignment = CENTER
                cell.border = BORDER

        def style_body(sheet, first_row, last_row, ncols, right_cols=()):
            for rr in range(first_row, last_row + 1):
                for c in range(1, ncols + 1):
                    cell = sheet.cell(row=rr, column=c)
                    cell.border = BORDER
                    if c in right_cols:
                        cell.alignment = Alignment(horizontal="right")

        wb = Workbook()

        # --- Summary sheet: title + KPI table + WebUI/API pie chart ---
        ws = wb.active
        ws.title = "Summary"
        ws["A1"] = title
        ws["A1"].font = TITLE_FONT
        ws["A2"] = subtitle
        ws["A2"].font = SUB_FONT
        ws.merge_cells("A1:D1")
        ws.merge_cells("A2:D2")

        ws["A4"] = "Key Metrics"
        ws["A4"].font = SECTION_FONT
        ws["A5"] = "Metric"
        ws["B5"] = "Value"
        style_header(ws, 5, 2)
        summary_rows = [
            ("Total tokens", int(totals.get("total_tokens", 0))),
            ("Input tokens", int(totals.get("input_tokens", 0))),
            ("Output tokens", int(totals.get("output_tokens", 0))),
            ("Calls", int(totals.get("calls", 0))),
            ("WebUI tokens", int(totals.get("webui_tokens", 0))),
            ("API tokens", int(totals.get("api_tokens", 0))),
            ("Energy (kWh)", float(totals.get("energy_kwh", 0))),
            ("CO2 (g)", float(totals.get("co2_g", 0))),
        ]
        rr = 6
        for label, value in summary_rows:
            ws.cell(row=rr, column=1, value=label)
            ws.cell(row=rr, column=2, value=value)
            rr += 1
        style_body(ws, 6, rr - 1, 2, right_cols=(2,))
        ws.column_dimensions["A"].width = 22
        ws.column_dimensions["B"].width = 22

        # WebUI vs API pie chart data block (kept on Summary, chart anchored beside)
        split_header = rr + 1
        ws.cell(row=split_header, column=1, value="WebUI vs API").font = SECTION_FONT
        ws.cell(row=split_header + 1, column=1, value="Channel")
        ws.cell(row=split_header + 1, column=2, value="Tokens")
        style_header(ws, split_header + 1, 2)
        ws.cell(row=split_header + 2, column=1, value="WebUI")
        ws.cell(row=split_header + 2, column=2, value=int(totals.get("webui_tokens", 0)))
        ws.cell(row=split_header + 3, column=1, value="API")
        ws.cell(row=split_header + 3, column=2, value=int(totals.get("api_tokens", 0)))
        style_body(ws, split_header + 2, split_header + 3, 2, right_cols=(2,))
        if (int(totals.get("webui_tokens", 0)) + int(totals.get("api_tokens", 0))) > 0:
            pie = PieChart()
            pie.title = "WebUI vs API token share"
            pdata = Reference(ws, min_col=2, min_row=split_header + 1, max_row=split_header + 3)
            plabels = Reference(ws, min_col=1, min_row=split_header + 2, max_row=split_header + 3)
            pie.add_data(pdata, titles_from_data=True)
            pie.set_categories(plabels)
            pie.height = 7
            pie.width = 11
            ws.add_chart(pie, "D5")

        # --- Timeline sheet: styled table + stacked bar chart ---
        ws2 = wb.create_sheet("Timeline")
        ws2["A1"] = "Consumption over time"
        ws2["A1"].font = SECTION_FONT
        tl_headers = ["Period", "Input", "Output", "Total", "Calls", "WebUI", "API"]
        for i, h in enumerate(tl_headers, start=1):
            ws2.cell(row=3, column=i, value=h)
        style_header(ws2, 3, len(tl_headers))
        r2 = 4
        for b in buckets:
            ws2.cell(row=r2, column=1, value=b.get("label", ""))
            ws2.cell(row=r2, column=2, value=int(b.get("input_tokens", 0)))
            ws2.cell(row=r2, column=3, value=int(b.get("output_tokens", 0)))
            ws2.cell(row=r2, column=4, value=int(b.get("total_tokens", 0)))
            ws2.cell(row=r2, column=5, value=int(b.get("calls", 0)))
            ws2.cell(row=r2, column=6, value=int(b.get("webui_tokens", 0)))
            ws2.cell(row=r2, column=7, value=int(b.get("api_tokens", 0)))
            r2 += 1
        tl_last = r2 - 1
        if tl_last >= 4:
            style_body(ws2, 4, tl_last, len(tl_headers), right_cols=(2, 3, 4, 5, 6, 7))
            chart = BarChart()
            chart.type = "col"
            chart.grouping = "stacked"
            chart.title = "Input vs Output tokens over time"
            chart.y_axis.title = "Tokens"
            chart.x_axis.title = "Period"
            data = Reference(ws2, min_col=2, max_col=3, min_row=3, max_row=tl_last)
            cats = Reference(ws2, min_col=1, min_row=4, max_row=tl_last)
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(cats)
            chart.height = 9
            chart.width = 24
            ws2.add_chart(chart, "I3")
        for col, w in zip("ABCDEFG", (16, 12, 12, 12, 10, 12, 12)):
            ws2.column_dimensions[col].width = w

        # --- By Model sheet: styled table + bar chart ---
        ws3 = wb.create_sheet("By Model")
        ws3["A1"] = "Top models"
        ws3["A1"].font = SECTION_FONT
        m_headers = ["Model", "Input", "Output", "Total", "Share %"]
        for i, h in enumerate(m_headers, start=1):
            ws3.cell(row=3, column=i, value=h)
        style_header(ws3, 3, len(m_headers))
        r3 = 4
        for m in by_model:
            ws3.cell(row=r3, column=1, value=m.get("model_name", ""))
            ws3.cell(row=r3, column=2, value=int(m.get("input_tokens", 0)))
            ws3.cell(row=r3, column=3, value=int(m.get("output_tokens", 0)))
            ws3.cell(row=r3, column=4, value=int(m.get("total_tokens", 0)))
            ws3.cell(row=r3, column=5, value=float(m.get("percentage", 0)))
            r3 += 1
        m_last = r3 - 1
        if m_last >= 4:
            style_body(ws3, 4, m_last, len(m_headers), right_cols=(2, 3, 4, 5))
            mchart = BarChart()
            mchart.type = "bar"
            mchart.title = "Tokens by model"
            mchart.y_axis.title = "Model"
            mchart.x_axis.title = "Tokens"
            mdata = Reference(ws3, min_col=4, min_row=3, max_row=m_last)
            mcats = Reference(ws3, min_col=1, min_row=4, max_row=m_last)
            mchart.add_data(mdata, titles_from_data=True)
            mchart.set_categories(mcats)
            mchart.height = 8
            mchart.width = 22
            ws3.add_chart(mchart, "G3")
        for col, w in zip("ABCDE", (30, 12, 12, 14, 10)):
            ws3.column_dimensions[col].width = w

        # --- By User sheet: styled table + bar chart ---
        ws4 = wb.create_sheet("By User")
        ws4["A1"] = "Top users"
        ws4["A1"].font = SECTION_FONT
        u_headers = ["User", "Input", "Output", "Total", "Share %"]
        for i, h in enumerate(u_headers, start=1):
            ws4.cell(row=3, column=i, value=h)
        style_header(ws4, 3, len(u_headers))
        r4 = 4
        for u in by_user:
            ws4.cell(row=r4, column=1, value=u.get("username", ""))
            ws4.cell(row=r4, column=2, value=int(u.get("input_tokens", 0)))
            ws4.cell(row=r4, column=3, value=int(u.get("output_tokens", 0)))
            ws4.cell(row=r4, column=4, value=int(u.get("total_tokens", 0)))
            ws4.cell(row=r4, column=5, value=float(u.get("percentage", 0)))
            r4 += 1
        u_last = r4 - 1
        if u_last >= 4:
            style_body(ws4, 4, u_last, len(u_headers), right_cols=(2, 3, 4, 5))
            uchart = BarChart()
            uchart.type = "bar"
            uchart.title = "Tokens by user"
            uchart.y_axis.title = "User"
            uchart.x_axis.title = "Tokens"
            udata = Reference(ws4, min_col=4, min_row=3, max_row=u_last)
            ucats = Reference(ws4, min_col=1, min_row=4, max_row=u_last)
            uchart.add_data(udata, titles_from_data=True)
            uchart.set_categories(ucats)
            uchart.height = 8
            uchart.width = 22
            ws4.add_chart(uchart, "G3")
        for col, w in zip("ABCDE", (26, 12, 12, 14, 10)):
            ws4.column_dimensions[col].width = w

        bio = _io.BytesIO()
        wb.save(bio)
        return _Resp(
            content=bio.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="token_consumption_{_dt.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'},
        )

    # ---- DOCX / PDF: build markdown-ish HTML then convert with shared helpers ----
    from fastapi import Response as _Resp
    md_lines = [f"# {title}", "", subtitle, "", "## Summary", ""]
    md_lines += [
        f"- **Total tokens:** {_num(totals.get('total_tokens',0))} "
        f"({_num(totals.get('input_tokens',0))} in · {_num(totals.get('output_tokens',0))} out)",
        f"- **Calls:** {_num(totals.get('calls',0))}",
        f"- **WebUI / API tokens:** {_num(totals.get('webui_tokens',0))} / {_num(totals.get('api_tokens',0))}",
        f"- **Energy:** {totals.get('energy_kwh',0)} kWh · {totals.get('co2_g',0)} g CO₂",
        "",
    ]
    md_lines += ["## Consumption over time", "", f"| Period | Input | Output | Total | Calls |", "|---|---|---|---|---|"]
    for b in buckets:
        md_lines.append(f"| {b.get('label','')} | {_num(b.get('input_tokens',0))} | {_num(b.get('output_tokens',0))} | {_num(b.get('total_tokens',0))} | {_num(b.get('calls',0))} |")
    md_lines += ["", "## Top models", "", "| Model | Input | Output | Total | Share |", "|---|---|---|---|---|"]
    for m in by_model:
        md_lines.append(f"| {m.get('model_name','')} | {_num(m.get('input_tokens',0))} | {_num(m.get('output_tokens',0))} | {_num(m.get('total_tokens',0))} | {m.get('percentage',0)}% |")
    md_lines += ["", "## Top users", "", "| User | Input | Output | Total | Share |", "|---|---|---|---|---|"]
    for u in by_user:
        md_lines.append(f"| {u.get('username','')} | {_num(u.get('input_tokens',0))} | {_num(u.get('output_tokens',0))} | {_num(u.get('total_tokens',0))} | {u.get('percentage',0)}% |")
    md_text = "\n".join(md_lines)

    filename_base = f"token_consumption_{_dt.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        from backend.routers.files import md2_to_html, html_to_docx_bytes, md_to_pdf_bytes, html_to_pdf_bytes
    except Exception:
        md2_to_html = html_to_docx_bytes = md_to_pdf_bytes = html_to_pdf_bytes = None

    if format == "docx":
        if html_to_docx_bytes is None:
            from fastapi import HTTPException as _HE
            raise _HE(status_code=501, detail="DOCX export requires python-docx (not available).")
        html = md2_to_html(md_text) if md2_to_html else f"<pre>{md_text}</pre>"
        content = html_to_docx_bytes(html)
        return _Resp(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.docx"'},
        )

    if format == "pdf":
        if md_to_pdf_bytes is None and html_to_pdf_bytes is None:
            from fastapi import HTTPException as _HE
            raise _HE(status_code=501, detail="PDF export requires a PDF engine (not available).")
        try:
            content = md_to_pdf_bytes(md_text) if md_to_pdf_bytes else html_to_pdf_bytes(md2_to_html(md_text))
        except Exception:
            content = html_to_pdf_bytes(md2_to_html(md_text))
        return _Resp(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.pdf"'},
        )

    from fastapi import HTTPException as _HE
    raise _HE(status_code=400, detail=f"Unsupported export format: {format}")


@system_management_router.get("/model-usage-stats", response_model=List[ModelUsageStat])
async def get_model_usage_stats(db: Session = Depends(get_db)):
    from backend.db.models.generation_metric import GenerationMetric, KWH_PER_TOKEN, CO2_G_PER_KWH

    metric_rows = db.query(
        GenerationMetric.model_name,
        func.count(GenerationMetric.id).label('req_count'),
        func.sum(GenerationMetric.total_tokens).label('total_tok'),
        func.sum(GenerationMetric.prompt_tokens).label('prompt_tok'),
        func.sum(GenerationMetric.completion_tokens).label('comp_tok')
    ).group_by(GenerationMetric.model_name).all()

    overall_tokens = sum((row[2] or 0) for row in metric_rows)

    stats = []
    if metric_rows:
        for model_name, req_count, total_tok, prompt_tok, comp_tok in metric_rows:
            tot = total_tok or 0
            p_tok = prompt_tok or 0
            c_tok = comp_tok or 0
            kwh = tot * KWH_PER_TOKEN
            co2 = kwh * CO2_G_PER_KWH
            pct = round((tot / overall_tokens * 100.0), 1) if overall_tokens > 0 else 0.0

            stats.append(ModelUsageStat(
                model_name=model_name or "unknown",
                count=req_count or 0,
                total_tokens=tot,
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                energy_kwh=round(kwh, 4),
                co2_g=round(co2, 2),
                percentage=pct
            ))
    else:
        user_rows = db.query(DBUser.lollms_model_name, func.count(DBUser.id)).group_by(DBUser.lollms_model_name).all()
        for model_name, count in user_rows:
            stats.append(ModelUsageStat(model_name=model_name or "Default", count=count))

    return sorted(stats, key=lambda x: x.total_tokens if x.total_tokens > 0 else x.count, reverse=True)

@system_management_router.get("/server-info", response_model=ServerInfo)
async def get_server_info(request: Request, db: Session = Depends(get_db)):
    running_apps = db.query(DBApp).filter(DBApp.status == 'running', DBApp.port != None).all()
    active_ports = [AppPortInfo(port=app.port, app_name=app.name, app_id=app.id) for app in running_apps]

    allowed_origins = next((m.options.get('allow_origins', []) for m in request.app.user_middleware if "CORSMiddleware" in str(m)), [])
    
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

@system_management_router.post("/compose-email", response_model=ComposeEmailResponse)
async def compose_email_with_ai(
    payload: ComposeEmailRequest,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_admin_user),
):
    """
    Generate a complete email (subject + body) from a natural-language prompt.

    Uses the primary admin's configured LLM binding — the same one that powers
    the existing /enhance-email flow — so admins do not need to configure a
    second model for outreach. The output is stripped of markdown fences and
    returned as plain {subject, body} JSON so the compose UI can drop it
    directly into the form.
    """
    import re as _re
    import json as _json

    prompt_text = (payload.prompt or "").strip()
    if not prompt_text:
        raise HTTPException(status_code=400, detail="`prompt` must be a non-empty string.")

    tone = (payload.tone or "professional").strip()
    language = (payload.language or "en").strip()
    want_subject = bool(payload.include_subject)

    # Compose the system prompt. Keeping this deterministic makes the AI output
    # stable for a given brief, and the explicit format contract eliminates the
    # most common failure mode (the model prepending commentary like "Here's
    # your email:" which would leak into the subject/body fields).
    system_prompt = (
        "You are an experienced email marketing copywriter writing an outreach "
        "email that will be sent by an administrator of a self-hosted AI platform "
        "(LoLLMs). Compose the very best email for the brief below.\n\n"
        "RULES:\n"
        f"- Tone: {tone}.\n"
        f"- Language: {language}.\n"
        "- The body must be plain text (no markdown fences, no HTML tags, no headings).\n"
        "- Use short, readable paragraphs. 90-180 words is ideal.\n"
        "- Never invent concrete statistics, prices, or URLs that were not in the brief.\n"
        "- End with a warm, single-sentence sign-off from 'The LoLLMs team'.\n"
    )
    if want_subject:
        system_prompt += (
            "\nReturn ONLY a single JSON object with exactly two keys: "
            "\"subject\" (a short, concrete subject line, under 90 characters) and "
            "\"body\" (the full plain-text email body). Do not add any other text, "
            "code fences, or explanation."
        )
    else:
        system_prompt += (
            "\nReturn ONLY a single JSON object with exactly two keys: "
            "\"subject\" (empty string) and \"body\" (the full plain-text email body). "
            "Do not add any other text, code fences, or explanation."
        )

    # Build the LLM client from the current admin's stored preferences — this
    # matches the pattern used by /enhance-email so no extra configuration step
    # is introduced for the operator.
    try:
        from backend.session import (
            user_sessions,
            build_lollms_client_from_params,
            resolve_model_name,
        )
        from backend.db.models.user import User as DBUser

        admin = db.query(DBUser).filter(DBUser.id == current_user.id).first()
        if not admin:
            raise HTTPException(status_code=404, detail="Admin user not found.")

        # Ensure an in-memory session exists so the client factory can read
        # model/preferences without re-running the whole session-init routine.
        if admin.username not in user_sessions:
            user_sessions[admin.username] = {
                "safe_store_instances": {},
                "discussions": {},
                "active_vectorizer": getattr(admin, "safe_store_vectorizer", None),
                "lollms_model_name": getattr(admin, "lollms_model_name", None),
                "llm_params": {},
                "active_personality_id": getattr(admin, "active_personality_id", None),
            }

        model_ref = getattr(admin, "lollms_model_name", None)
        if not model_ref:
            raise HTTPException(
                status_code=503,
                detail="No LLM model is configured for the administrator account.",
            )

        binding_alias, model_name = resolve_model_name(db, model_ref)
        lc = build_lollms_client_from_params(
            username=admin.username,
            binding_alias=binding_alias,
            model_name=model_name,
            load_llm=True,
            load_mcp=False,
        )
        if lc is None or not getattr(lc, "llm", None):
            raise HTTPException(
                status_code=503,
                detail="The LLM client could not be initialised. Check bindings and model availability.",
            )

        raw = lc.generate_from_messages(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_text},
            ],
            temperature=0.7,
            n_predict=1200,
        )
    except HTTPException:
        raise
    except Exception as e:
        trace_exception(e)
        raise HTTPException(
            status_code=500,
            detail=f"Email composition failed: {echo_safe(e)}",
        )

    text = raw if isinstance(raw, str) else str(raw)
    text = _strip_fences(text)

    parsed_subject = ""
    parsed_body = ""
    try:
        obj = _json.loads(text)
        if isinstance(obj, dict):
            parsed_subject = str(obj.get("subject") or "").strip()
            parsed_body = str(obj.get("body") or "").strip()
    except Exception:
        # Fallback: if the model ignores the JSON contract, treat the whole
        # output as the body and leave the subject blank. Better to hand the
        # admin a usable draft than to raise and lose the generation.
        parsed_body = text.strip()

    if not parsed_body and not parsed_subject:
        raise HTTPException(
            status_code=502,
            detail="The model returned an empty email. Try rephrasing the prompt.",
        )

    return ComposeEmailResponse(subject=parsed_subject, body=parsed_body)


def _strip_fences(text: str) -> str:
    """Remove triple-backtick fences a model sometimes wraps JSON in."""
    text = text.strip()
    if text.startswith("```"):
        # Drop leading fence (with optional language tag) and trailing fence.
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def echo_safe(err: Exception) -> str:
    """Return a non-leaking short description of an exception for HTTP details."""
    msg = str(err) or err.__class__.__name__
    return msg[:300]


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
    from backend.db.models.generation_metric import GenerationMetric, calculate_co2_equivalents, KWH_PER_TOKEN, CO2_G_PER_KWH

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    # 1. Query real telemetry records partitioned by date and source
    metrics_query = db.query(
        func.date(GenerationMetric.created_at).label('metric_date'),
        GenerationMetric.source,
        func.count(GenerationMetric.id).label('gen_count'),
        func.sum(GenerationMetric.total_tokens).label('tok_count'),
        func.sum(GenerationMetric.prompt_tokens).label('p_tok'),
        func.sum(GenerationMetric.completion_tokens).label('c_tok')
    ).filter(
        GenerationMetric.created_at >= thirty_days_ago
    ).group_by(func.date(GenerationMetric.created_at), GenerationMetric.source).all()

    all_dates = set()
    daily_totals = defaultdict(int)
    daily_webui_gens = defaultdict(int)
    daily_api_gens = defaultdict(int)

    tokens_per_day_dict = defaultdict(int)
    prompt_tokens_per_day_dict = defaultdict(int)
    completion_tokens_per_day_dict = defaultdict(int)
    webui_tokens_per_day_dict = defaultdict(int)
    api_tokens_per_day_dict = defaultdict(int)

    total_tokens = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    webui_tokens_total = 0
    api_tokens_total = 0
    webui_reqs_total = 0
    api_reqs_total = 0

    for date_str, src, count, tokens, p_tok, c_tok in metrics_query:
        if date_str:
            d_str = str(date_str)
            all_dates.add(d_str)
            cnt = count or 0
            tok = tokens or 0
            p = p_tok or 0
            c = c_tok or 0

            daily_totals[d_str] += cnt
            tokens_per_day_dict[d_str] += tok
            prompt_tokens_per_day_dict[d_str] += p
            completion_tokens_per_day_dict[d_str] += c
            total_tokens += tok
            total_prompt_tokens += p
            total_completion_tokens += c

            if src == "chat":
                daily_webui_gens[d_str] += cnt
                webui_tokens_per_day_dict[d_str] += tok
                webui_tokens_total += tok
                webui_reqs_total += cnt
            else:
                daily_api_gens[d_str] += cnt
                api_tokens_per_day_dict[d_str] += tok
                api_tokens_total += tok
                api_reqs_total += cnt

    # Ensure zero values exist for aligned dates across all datasets
    sorted_date_strings = sorted(list(all_dates))

    generations_per_day_list = [
        UserActivityStat(date=datetime.strptime(d_str, '%Y-%m-%d').date(), count=daily_totals[d_str])
        for d_str in sorted_date_strings
    ]
    tokens_per_day_list = [
        UserActivityStat(date=datetime.strptime(d_str, '%Y-%m-%d').date(), count=tokens_per_day_dict[d_str])
        for d_str in sorted_date_strings
    ]
    prompt_tokens_per_day_list = [
        UserActivityStat(date=datetime.strptime(d_str, '%Y-%m-%d').date(), count=prompt_tokens_per_day_dict[d_str])
        for d_str in sorted_date_strings
    ]
    completion_tokens_per_day_list = [
        UserActivityStat(date=datetime.strptime(d_str, '%Y-%m-%d').date(), count=completion_tokens_per_day_dict[d_str])
        for d_str in sorted_date_strings
    ]
    webui_tokens_per_day_list = [
        UserActivityStat(date=datetime.strptime(d_str, '%Y-%m-%d').date(), count=webui_tokens_per_day_dict[d_str])
        for d_str in sorted_date_strings
    ]
    api_tokens_per_day_list = [
        UserActivityStat(date=datetime.strptime(d_str, '%Y-%m-%d').date(), count=api_tokens_per_day_dict[d_str])
        for d_str in sorted_date_strings
    ]
    webui_generations_per_day_list = [
        UserActivityStat(date=datetime.strptime(d_str, '%Y-%m-%d').date(), count=daily_webui_gens[d_str])
        for d_str in sorted_date_strings
    ]
    api_generations_per_day_list = [
        UserActivityStat(date=datetime.strptime(d_str, '%Y-%m-%d').date(), count=daily_api_gens[d_str])
        for d_str in sorted_date_strings
    ]

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

    sum_tokens = webui_tokens_total + api_tokens_total if (webui_tokens_total + api_tokens_total) > 0 else total_tokens
    total_reqs = webui_reqs_total + api_reqs_total

    webui_ratio = round((webui_tokens_total / sum_tokens * 100.0), 1) if sum_tokens > 0 else 0.0
    api_ratio = round((api_tokens_total / sum_tokens * 100.0), 1) if sum_tokens > 0 else 0.0

    webui_energy = webui_tokens_total * KWH_PER_TOKEN
    api_energy = api_tokens_total * KWH_PER_TOKEN
    webui_co2 = webui_energy * CO2_G_PER_KWH
    api_co2 = api_energy * CO2_G_PER_KWH

    from backend.models.admin import SourceConsumptionBreakdown

    source_breakdown = SourceConsumptionBreakdown(
        webui_tokens=webui_tokens_total,
        api_tokens=api_tokens_total,
        total_tokens=sum_tokens,
        webui_requests=webui_reqs_total,
        api_requests=api_reqs_total,
        total_requests=total_reqs,
        webui_ratio=webui_ratio,
        api_ratio=api_ratio,
        webui_energy_kwh=round(webui_energy, 4),
        api_energy_kwh=round(api_energy, 4),
        webui_co2_g=round(webui_co2, 2),
        api_co2_g=round(api_co2, 2)
    )

    total_energy_kwh = sum_tokens * KWH_PER_TOKEN
    total_co2_g = total_energy_kwh * CO2_G_PER_KWH
    co2_equivalents = calculate_co2_equivalents(total_co2_g)

    return GlobalGenerationStats(
        generations_per_day=generations_per_day_list,
        tokens_per_day=tokens_per_day_list,
        prompt_tokens_per_day=prompt_tokens_per_day_list,
        completion_tokens_per_day=completion_tokens_per_day_list,
        webui_tokens_per_day=webui_tokens_per_day_list,
        api_tokens_per_day=api_tokens_per_day_list,
        webui_generations_per_day=webui_generations_per_day_list,
        api_generations_per_day=api_generations_per_day_list,
        mean_per_weekday=mean_per_weekday,
        variance_per_weekday=variance_per_weekday,
        total_tokens=sum_tokens,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        total_energy_kwh=round(total_energy_kwh, 4),
        total_co2_g=round(total_co2_g, 2),
        co2_equivalents=co2_equivalents,
        source_breakdown=source_breakdown
    )

@system_management_router.post("/backup/create", response_model=TaskInfo, status_code=202)
async def create_backup(
    request: BackupRequest,
    current_admin: UserAuthDetails = Depends(get_current_admin_user)
):
    db_task = task_manager.submit_task(
        name="Create Application Backup",
        target=_create_backup_task,
        args=(request.password,),
        description="Creating a secure password-protected zip archive of the entire application.",
        owner_username=current_admin.username
    )
    return db_task

@system_management_router.post("/tasks/prune", response_model=TaskInfo, status_code=202)
async def trigger_manual_task_pruning(current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    """Manually triggers the background task to delete finished tasks older than configured retention."""
    db_task = task_manager.submit_task(
        name="Manual Task Pruning",
        target=_prune_old_tasks_task,
        description="Cleaning up old finished background tasks.",
        owner_username=current_admin.username
    )
    return db_task

@system_management_router.get("/system/requirements", response_model=List[RequirementInfo])
async def get_system_requirements(current_user: UserAuthDetails = Depends(get_current_admin_user)):
    requirements_path = PROJECT_ROOT / "requirements.txt"
    if not requirements_path.exists():
        raise HTTPException(status_code=404, detail="requirements.txt not found")
    
    results = []
    
    with open(requirements_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            try:
                req = Requirement(line)
                name = req.name
                
                # Extract required version from specs if == is present
                required_version = None
                for spec in req.specifier:
                    if spec.operator == '==':
                        required_version = spec.version
                        break
                
                installed_version = None
                try:
                    installed_version = get_installed_version(name)
                except PackageNotFoundError:
                    pass
                
                status = 'missing'
                if installed_version:
                    if not required_version:
                        status = 'ok' # No specific version required
                    else:
                        inst_v = parse_version(installed_version)
                        req_v = parse_version(required_version)
                        
                        if inst_v == req_v:
                            status = 'ok'
                        elif inst_v > req_v:
                            status = 'newer'
                        else:
                            status = 'older'
                
                results.append(RequirementInfo(
                    name=name,
                    required_version=required_version or "Any",
                    installed_version=installed_version or "Not Installed",
                    status=status
                ))
            except Exception as e:
                print(f"Error parsing requirement line '{line}': {e}")
                continue
                
    return results

@system_management_router.post("/system/requirements/install", response_model=TaskInfo, status_code=202)
async def install_requirement(payload: InstallReqPayload, current_user: UserAuthDetails = Depends(get_current_admin_user)):
    def _install_task(task: Task, pkg_name: str, pkg_version: str):
        task.log(f"Installing {pkg_name}...")
        success, tail = _install_with_pep668_retry(task, pkg_name, pkg_version)
        if success:
            task.log(f"Successfully installed {pkg_name}")
            return {"message": "Installation successful"}
        raise Exception(
            f"Installation of {pkg_name} failed. pip output:\n" + "\n".join(tail)
        )

    target_version = payload.version
    description = f"Installing {payload.name}"
    if target_version:
        description += f" version {target_version}"
    else:
        description += " (Latest)"

    return task_manager.submit_task(
        name=f"Install Requirement: {payload.name}",
        target=_install_task,
        args=(payload.name, target_version),
        description=description,
        owner_username=current_user.username
    )

# --- Update and Reboot Endpoints (Service Compatible) ---

@system_management_router.post("/system/reboot")
async def reboot_server(current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    """
    Signals the wrapper script (run.sh or run_windows.bat) to restart the application.
    This works by creating a 'restart' flag if needed, or simply exiting the process.
    The wrapper script loop will detect the exit and restart the process.
    """
    try:
        ASCIIColors.yellow("Initiating Server Reboot (Service/Loop Mode)...")
        
        # We don't strictly need a file for a simple restart if the loop is infinite,
        # but the flag is good practice to distinguish intentional restarts from crashes.
        # However, to keep it compatible with simple loops, just exiting 0 is often enough.
        
        def delayed_exit():
            import time
            time.sleep(1)
            ASCIIColors.red("Exiting process for reboot.")
            # Exit with code 0 to indicate clean shutdown to wrapper
            os._exit(0)
            
        import threading
        threading.Thread(target=delayed_exit, daemon=True).start()

        return {"message": "Server is rebooting..."}

    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to initiate reboot: {str(e)}")


@system_management_router.post("/system/update")
async def update_server(current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    """
    Signals the wrapper script to perform an update before restarting.
    Creates an 'update_request.flag' file in the root directory.
    The run.sh/run_windows.bat script checks for this file on loop iteration.
    """
    try:
        ASCIIColors.yellow("Initiating Server Update (Service/Loop Mode)...")
        
        # Create flag file
        flag_path = PROJECT_ROOT / "update_request.flag"
        with open(flag_path, 'w') as f:
            f.write("update_requested")
            
        def delayed_exit():
            import time
            time.sleep(1)
            ASCIIColors.red("Exiting process for update sequence.")
            os._exit(0) # Exit to let wrapper handle the update
            
        import threading
        threading.Thread(target=delayed_exit, daemon=True).start()

        return {"message": "Server is restarting to apply updates."}

    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to initiate update: {str(e)}")

@system_management_router.post("/system/requirements/fix-all", response_model=TaskInfo, status_code=202)
async def fix_all_requirements(current_user: UserAuthDetails = Depends(get_current_admin_user)):
    """
    Installs the correct version for all requirements that are not 'ok'.
    Returns a task that can be monitored for progress.
    """
    def _fix_all_task(task: Task):
        task.log("Starting to fix all requirements...")

        # Get requirements directly from the requirements.txt file
        requirements_path = PROJECT_ROOT / "requirements.txt"
        if not requirements_path.exists():
            task.log("requirements.txt not found", level="ERROR")
            raise Exception("requirements.txt not found")

        # Parse requirements
        requirements_to_fix = []
        with open(requirements_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if line.startswith("-e") or "://" in line:
                    continue

                try:
                    req = Requirement(line)
                    name = req.name

                    # Extract required version from specs if == is present
                    required_version = None
                    for spec in req.specifier:
                        if spec.operator == '==':
                            required_version = spec.version
                            break

                    installed_version = None
                    try:
                        installed_version = get_installed_version(name)
                    except PackageNotFoundError:
                        pass

                    status = 'missing'
                    if installed_version:
                        if not required_version:
                            status = 'ok'  # No specific version required
                        else:
                            inst_v = parse_version(installed_version)
                            req_v = parse_version(required_version)

                            if inst_v == req_v:
                                status = 'ok'
                            elif inst_v > req_v:
                                status = 'newer'
                            else:
                                status = 'older'

                    if status != 'ok':
                        requirements_to_fix.append({
                            "name": name,
                            "required_version": required_version
                        })
                except Exception as e:
                    task.log(f"Error parsing requirement line '{line}': {e}", level="ERROR")
                    continue

        if not requirements_to_fix:
            task.log("All requirements are already satisfied.")
            task.set_progress(100)
            return {"message": "All requirements are already satisfied."}

        total_reqs = len(requirements_to_fix)
        fixed_count = 0

        for i, req in enumerate(requirements_to_fix):
            if task.cancellation_event.is_set():
                task.log("Fix all requirements task cancelled.", level="WARNING")
                break

            task.log(f"Fixing {req['name']} (required: {req['required_version'] or 'latest'})...")
            try:
                success, tail = _install_with_pep668_retry(task, req['name'], req['required_version'])
                if success:
                    task.log(f"Successfully installed {req['name']}")
                    fixed_count += 1
                else:
                    task.log(
                        f"Installation failed for {req['name']}. pip output:\n" + "\n".join(tail),
                        level="ERROR"
                    )
            except Exception as e:
                task.log(f"Failed to install {req['name']}: {str(e)}", level="ERROR")

            task.set_progress(int(90 * (i + 1) / total_reqs))

        task.set_progress(100)
        return {"message": f"Fixed {fixed_count} out of {total_reqs} requirements."}

    db_task = task_manager.submit_task(
        name="Fix All Requirements",
        target=_fix_all_task,
        description="Installing correct versions for all requirements that are not satisfied.",
        owner_username=current_user.username
    )
    return db_task
