import asyncio
import datetime
import hashlib
import inspect
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from contextlib import asynccontextmanager, contextmanager
from multiprocessing import set_start_method
from pathlib import Path
from typing import Optional

# Windows cp1252 consoles crash on the Unicode used by ascii_colors. Fix before it is imported.
if os.name == 'nt':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    for _stream in (sys.stdout, sys.stderr):
        if _stream and hasattr(_stream, 'reconfigure'):
            _stream.reconfigure(encoding='utf-8')

import pipmaster as pm
pm.ensure_packages(["ascii_colors>=0.11.13", "lollms_client>=1.12.4", "filelock"])

from ascii_colors import ASCIIColors, trace_exception
from filelock import FileLock, Timeout

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Depends, HTTPException, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, inspect as sa_inspect
from sqlalchemy.orm import Session

from lollms_client import LollmsDataManager

from backend.config import (
    APP_SETTINGS, APP_VERSION, APP_DB_URL,
    INITIAL_ADMIN_USER_CONFIG, SERVER_CONFIG,
    APPS_ZOO_ROOT_PATH, MCPS_ZOO_ROOT_PATH, PROMPTS_ZOO_ROOT_PATH,
    PERSONALITIES_ZOO_ROOT_PATH, SKILLS_ZOO_ROOT_PATH
)
from backend.db import init_database, get_db, session as db_session_module
from backend.db.base import Base, TaskStatus
from backend.db.migration import run_schema_migrations_and_bootstrap, check_and_update_db_version
from backend.db.models.user import User as DBUser
from backend.db.models.service import (
    AppZooRepository as DBAppZooRepository,
    MCPZooRepository as DBMCPZooRepository,
    PromptZooRepository as DBPromptZooRepository,
    PersonalityZooRepository as DBPersonalityZooRepository,
    SkillZooRepository as DBSkillZooRepository,
)
from backend.db.models.connections import WebSocketConnection
from backend.db.models.db_task import DBTask
from backend.security import get_password_hash as hash_password
from backend.migration_utils import LegacyDiscussion
from backend.session import (
    get_user_data_root, get_user_discussion_path, user_sessions,
    build_lollms_client_from_params, get_current_active_user
)
from backend.models.user import UserAuthDetails
from backend.settings import settings

from backend.routers.auth import auth_router
from backend.routers.admin import admin_router
from backend.routers.languages import languages_router
from backend.routers.personalities import personalities_router
from backend.routers.friends import friends_router
from backend.routers.groups import groups_router
from backend.routers.social.dm import dm_router
from backend.routers.stores import store_files_router, datastore_router
from backend.routers.extensions import apps_router, mcp_router, discussion_tools_router
from backend.routers.social import social_router
from backend.routers.users import users_router
from backend.routers.social.dm_ws import dm_ws_router
from backend.routers.api_keys import api_keys_router
from backend.routers.services.openai_v1 import openai_v1_router
from backend.routers.services.ollama_v1 import ollama_v1_router
from backend.routers.lollms_config import lollms_config_router
from backend.routers.files import upload_router, assets_router, files_router
from backend.routers.ui import add_ui_routes, ui_router
from backend.routers.sso import sso_router
from backend.routers.sso_client import sso_client_router
from backend.routers.scim import scim_router
from backend.routers.extensions.app_utils import cleanup_and_autostart_apps, synchronize_filesystem_and_db
from backend.routers.zoos.apps_zoo import apps_zoo_router
from backend.routers.zoos.mcps_zoo import mcps_zoo_router
from backend.routers.zoos.prompts_zoo import prompts_zoo_router
from backend.routers.zoos.personalities_zoo import personalities_zoo_router
from backend.routers.zoos.skills_zoo import skills_zoo_router
from backend.routers.discussion_groups import discussion_groups_router
from backend.routers.voices_studio import voices_studio_router
from backend.routers.image_studio import image_studio_router
from backend.routers.music_studio import music_studio_router
from backend.routers.notes import notes_router
from backend.routers.notebooks import router as notebooks_router
from backend.routers.public import public_router
from backend.routers.flow_studio import router as flow_studio_router
from backend.routers.services.lollms_v1 import lollms_v1_router
from backend.routers.tasks import tasks_router
from backend.routers.skills import skills_router
from backend.routers.help import help_router
from backend.routers.prompts import prompts_router
from backend.routers.memories import memories_router
from backend.routers.news import news_router
from backend.routers.discussion import build_discussions_router
from backend.routers.discussion.core import build_core_router
from backend.tasks.email_tasks import _generate_email_proposal_task
from backend.tasks.news_tasks import _scrape_rss_feeds_task, _cleanup_old_news_articles_task
from backend.tasks.social_tasks import _generate_feed_post_task
from backend.tasks.system_tasks import _prune_old_tasks_task
from backend.task_manager import task_manager
from backend.ws_manager import manager, listen_for_broadcasts
from backend.zoo_cache import load_cache


# --------------------------------------------------------------------------- #
# Process-wide state
# --------------------------------------------------------------------------- #
broadcast_listener_task = None
rss_scheduler: Optional[BackgroundScheduler] = None

_startup_done = False
_task_manager_ready = False
_scheduler_lock: Optional[FileLock] = None

# Cross-process coordination files, namespaced per database so instances don't collide.
_INSTANCE_TAG = hashlib.sha1(str(APP_DB_URL).encode()).hexdigest()[:10]
_LOCK_DIR = Path(tempfile.gettempdir())
_STARTUP_LOCK_PATH = _LOCK_DIR / f"lollms_{_INSTANCE_TAG}_startup.lock"
_STARTUP_MARKER_PATH = _LOCK_DIR / f"lollms_{_INSTANCE_TAG}_startup.done"
_SCHEDULER_LOCK_PATH = _LOCK_DIR / f"lollms_{_INSTANCE_TAG}_scheduler.lock"


@contextmanager
def db_scope():
    """Session that is always closed, and never unbound in a finally block."""
    db = db_session_module.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _boot_id() -> str:
    """Identifies one server launch. Set by __main__; falls back to the parent pid for `uvicorn main:app`."""
    return os.getenv("LOLLMS_BOOT_ID") or f"ppid-{os.getppid()}"


# --------------------------------------------------------------------------- #
# Scheduled jobs
# --------------------------------------------------------------------------- #
def scheduled_rss_job():
    active = task_manager.get_all_tasks()
    if any(t.name == "Scheduled RSS Feed Scraping" and t.status in ['running', 'pending'] for t in active):
        return
    task_manager.submit_task(
        name="Scheduled RSS Feed Scraping",
        target=_scrape_rss_feeds_task,
        description="Periodically fetching and processing all active RSS feeds.",
        owner_username=None
    )


def scheduled_news_cleanup_job():
    task_manager.submit_task(
        name="Daily News Article Cleanup",
        target=_cleanup_old_news_articles_task,
        description="Deleting old news articles based on retention policy.",
        owner_username=None
    )


def scheduled_task_pruning_job():
    with db_scope() as db:
        settings.load_from_db(db)
    if not settings.get("tasks_auto_cleanup", True):
        return
    task_manager.submit_task(
        name="Scheduled Task Pruning",
        target=_prune_old_tasks_task,
        description="Automatic background cleanup of old finished tasks.",
        owner_username=None
    )


def check_and_run_scheduled_posts():
    try:
        with db_scope() as db:
            settings.load_from_db(db)

        if not settings.get("ai_bot_auto_post", False):
            return
        schedule = settings.get("ai_bot_post_schedule", [])
        if not schedule:
            return

        last_posted = None
        last_posted_str = settings.get("ai_bot_last_posted_at")
        if last_posted_str:
            try:
                last_posted = datetime.datetime.fromisoformat(last_posted_str)
            except ValueError:
                pass

        now = datetime.datetime.now()
        current_time_str = now.strftime("%H:%M")

        should_post = False
        for time_slot in schedule:
            if current_time_str != time_slot:
                continue
            if last_posted and (now - last_posted).total_seconds() < 3540:
                continue
            should_post = True
            break

        if should_post:
            task_manager.submit_task(
                name="AI Bot Scheduled Post",
                target=_generate_feed_post_task,
                args=(True,),
                description=f"Scheduled post for {current_time_str}",
                owner_username=None
            )
    except Exception as e:
        ASCIIColors.error(f"Error in scheduler check: {e}")
        trace_exception(e)


def scheduled_email_proposal_job():
    task_manager.submit_task(
        name="Generate Email Proposal",
        target=_generate_email_proposal_task,
        description="Lollms researching and drafting email content.",
        owner_username=None
    )


def _become_scheduler_leader() -> bool:
    """Exactly one process across all workers gets the scheduler. The OS drops the lock if it dies."""
    global _scheduler_lock
    if _scheduler_lock is not None:
        return True
    lock = FileLock(str(_SCHEDULER_LOCK_PATH))
    try:
        lock.acquire(timeout=0)
    except Timeout:
        return False
    _scheduler_lock = lock
    return True


AGENT_USERNAME = "lollms"


def _warm_agent_client():
    """
    Builds the moderation/organisation agent's client once, ~30s after startup, in the
    scheduler-leader process only. Runs after the server accepts connections, so MCP servers
    hosted by this app are reachable. A failure here never affects startup.
    """
    try:
        build_lollms_client_from_params(AGENT_USERNAME, load_llm=True)
        ASCIIColors.info(f"Agent client '{AGENT_USERNAME}' ready.")
    except Exception as e:
        ASCIIColors.warning(f"Agent client '{AGENT_USERNAME}' warmup failed: {e}")


# --------------------------------------------------------------------------- #
# One-time startup (runs once per server launch, across all processes)
# --------------------------------------------------------------------------- #
def _migrate_legacy_discussions():
    if not APP_SETTINGS.get("migrate"):
        return
    with db_scope() as db:
        for user in db.query(DBUser).all():
            username = user.username
            old_path = get_user_discussion_path(username)
            if not (old_path.exists() and old_path.is_dir()):
                continue
            if username not in user_sessions:
                user_sessions[username] = {
                    "lollms_model_name": user.lollms_model_name,
                    "llm_params": {}
                }
            db_path = get_user_data_root(username) / "discussions.db"
            dm = LollmsDataManager(db_path=f"sqlite:///{db_path.resolve()}")
            migrated = 0
            failed = 0
            for file_path in old_path.glob("*.yaml"):
                ddb = None
                try:
                    old_disc = LegacyDiscussion.load_from_yaml(file_path)
                    if not old_disc:
                        continue
                    ddb = dm.get_session()
                    if ddb.query(dm.DiscussionModel).filter_by(id=old_disc.discussion_id).first():
                        continue
                    new_disc = dm.DiscussionModel(
                        id=old_disc.discussion_id,
                        discussion_metadata={"title": old_disc.title, "rag_datastore_ids": old_disc.rag_datastore_ids},
                        active_branch_id=old_disc.active_branch_id
                    )
                    ddb.add(new_disc)
                    for msg in old_disc.messages:
                        ddb.add(dm.MessageModel(
                            id=msg.id,
                            discussion_id=new_disc.id,
                            parent_id=msg.parent_id,
                            sender=msg.sender,
                            sender_type=msg.sender_type,
                            content=msg.content,
                            created_at=msg.created_at,
                            binding_name=msg.binding_name,
                            model_name=msg.model_name,
                            tokens=msg.token_count,
                            message_metadata={"sources": msg.sources, "steps": msg.steps}
                        ))
                    ddb.commit()
                    migrated += 1
                except Exception as e:
                    failed += 1
                    if ddb:
                        ddb.rollback()
                    ASCIIColors.warning(f"Legacy discussion migration failed for {file_path.name} ({username}): {e}")
                finally:
                    if ddb:
                        ddb.close()
            # Only archive the old folder if nothing failed, otherwise data would be hidden from a retry.
            if migrated > 0 and failed == 0:
                stamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                backup = old_path.parent / f"{old_path.name}_migrated_{stamp}"
                shutil.move(str(old_path), str(backup))


def _ensure_default_admin():
    admin_username = INITIAL_ADMIN_USER_CONFIG.get("username", "admin")
    admin_password = INITIAL_ADMIN_USER_CONFIG.get("password", "admin")
    with db_scope() as db:
        if db.query(DBUser).filter(DBUser.is_admin.is_(True)).first():
            return
        existing = db.query(DBUser).filter(DBUser.username == admin_username).first()
        if existing:
            existing.is_admin = True
            existing.is_active = True
            existing.status = "active"
        else:
            db.add(DBUser(
                username=admin_username,
                hashed_password=hash_password(admin_password),
                is_admin=True,
                is_active=True,
                status="active"
            ))
        db.commit()


def _ensure_zoo(repo_model, name: str, url: str, root_path: Path):
    """Register a zoo repository in the DB and clone it if missing."""
    with db_scope() as db:
        exists = db.query(repo_model).filter(
            or_(repo_model.name == name, repo_model.url == url)
        ).first()
        if not exists:
            db.add(repo_model(name=name, url=url, is_deletable=False))
            db.commit()
    repo_path = Path(root_path) / name
    if not repo_path.exists():
        try:
            subprocess.run(["git", "clone", url, str(repo_path)], check=True, timeout=600)
        except Exception:
            # Don't leave a half-cloned directory that would pass the exists() check next time.
            shutil.rmtree(repo_path, ignore_errors=True)
            raise


def _cleanup_stale_state():
    with db_scope() as db:
        db.query(WebSocketConnection).delete()
        interrupted = db.query(DBTask).filter(
            DBTask.status.in_([TaskStatus.RUNNING, TaskStatus.PENDING])
        ).all()
        now = datetime.datetime.now(datetime.timezone.utc)
        for task in interrupted:
            task.status = TaskStatus.FAILED
            task.error = "Task interrupted by server restart."
            task.completed_at = now
            task.logs = list(task.logs or []) + [{
                "timestamp": now.isoformat(),
                "message": "System Restart Recovery",
                "level": "ERROR"
            }]
        db.commit()


def _schema_migration():
    engine = db_session_module.engine
    with engine.connect() as connection:
        inspector = sa_inspect(connection)
        run_schema_migrations_and_bootstrap(connection, inspector)
    ASCIIColors.green("INFO: Schema migration completed.")
    check_and_update_db_version(db_session_module.SessionLocal)


def _ensure_task_manager():
    """task_manager lives in process memory, so init it once per process."""
    global _task_manager_ready
    if not _task_manager_ready:
        task_manager.init_app(db_session_module.SessionLocal)
        _task_manager_ready = True


def _autostart():
    _ensure_task_manager()
    cleanup_and_autostart_apps()


def _do_startup_tasks():
    ASCIIColors.panel(f"ℹ️ Process [bold]{os.getpid()}[/bold] running one-time startup tasks... 🚀")

    # (label, function, fatal)
    plan = [
        ("Database tables check/creation", lambda: Base.metadata.create_all(bind=db_session_module.engine), True),
        ("Schema migration & bootstrap", _schema_migration, True),
        ("Legacy discussion migration", _migrate_legacy_discussions, False),
        ("Default admin & DB entries", _ensure_default_admin, False),
        ("App Zoo repository setup",
         lambda: _ensure_zoo(DBAppZooRepository, "Official LoLLMs Apps Zoo",
                             "https://github.com/ParisNeo/lollms_apps_zoo.git", APPS_ZOO_ROOT_PATH), False),
        ("MCP Zoo repository setup",
         lambda: _ensure_zoo(DBMCPZooRepository, "lollms_mcps_zoo",
                             "https://github.com/ParisNeo/lollms_mcps_zoo.git", MCPS_ZOO_ROOT_PATH), False),
        ("Prompt Zoo repository setup",
         lambda: _ensure_zoo(DBPromptZooRepository, "lollms_prompts_zoo",
                             "https://github.com/ParisNeo/lollms_prompts_zoo.git", PROMPTS_ZOO_ROOT_PATH), False),
        ("Personality Zoo repository setup",
         lambda: _ensure_zoo(DBPersonalityZooRepository, "lollms_personalities_zoo",
                             "https://github.com/ParisNeo/lollms_personalities_zoo.git", PERSONALITIES_ZOO_ROOT_PATH), False),
        ("Skill Zoo repository setup",
         lambda: _ensure_zoo(DBSkillZooRepository, "lollms_skills_zoo",
                             "https://github.com/ParisNeo/lollms_skills_zoo.git", SKILLS_ZOO_ROOT_PATH), False),
        ("Filesystem-DB synchronization", lambda: _sync_fs_db(), False),
        ("Stale WebSocket & task cleanup", _cleanup_stale_state, False),
        ("Autostart & cleanup", _autostart, False),
    ]

    results = []
    for label, fn, fatal in plan:
        try:
            fn()
            results.append((label, True))
        except Exception as e:
            ASCIIColors.error(f"Startup step failed: {label}: {e}")
            trace_exception(e)
            results.append((label, False))
            if fatal:
                raise

    lines = [f"{'[green]✔[/green]' if ok else '[red]✘[/red]'} {label}" for label, ok in results]
    ASCIIColors.panel("\n".join(lines), title="🛠️ Startup Progress", border_style="cyan")


def _sync_fs_db():
    with db_scope() as db:
        synchronize_filesystem_and_db(db)


def run_one_time_startup_tasks():
    """
    Runs the heavy startup exactly once per server launch, no matter how many processes
    import this module. A file lock serialises processes; a marker keyed on the launch id
    tells latecomers it is already done.
    """
    global _startup_done
    if _startup_done:
        return
    boot_id = _boot_id()
    with FileLock(str(_STARTUP_LOCK_PATH), timeout=900):
        try:
            already = _STARTUP_MARKER_PATH.read_text().strip() == boot_id
        except OSError:
            already = False
        if not already:
            _do_startup_tasks()
            _STARTUP_MARKER_PATH.write_text(boot_id)
    _startup_done = True


# --------------------------------------------------------------------------- #
# Lifespan
# --------------------------------------------------------------------------- #
async def startup_event():
    global broadcast_listener_task, rss_scheduler

    init_database(APP_DB_URL)
    await asyncio.to_thread(run_one_time_startup_tasks)

    # Per-process state: these live in each worker's memory.
    await asyncio.to_thread(load_cache)

    with db_scope() as db:
        settings.load_from_db(db)

    manager.set_loop(asyncio.get_running_loop())
    _ensure_task_manager()

    if SERVER_CONFIG.get("workers", 1) > 1:
        broadcast_listener_task = asyncio.create_task(listen_for_broadcasts())

    # No client is built at startup. User clients are built lazily on first request.

    if _become_scheduler_leader():
        rss_scheduler = BackgroundScheduler(daemon=True)
        job_opts = {"max_instances": 1, "coalesce": True}

        if settings.get("rss_feed_enabled"):
            interval = settings.get("rss_feed_check_interval_minutes", 60)
            rss_scheduler.add_job(
                scheduled_rss_job, 'interval', minutes=interval,
                next_run_time=datetime.datetime.now() + datetime.timedelta(seconds=20), **job_opts
            )
            if settings.get("rss_news_retention_days", 1) > 0:
                rss_scheduler.add_job(scheduled_news_cleanup_job, 'cron', hour=3, minute=0, **job_opts)

        rss_scheduler.add_job(check_and_run_scheduled_posts, 'interval', minutes=1, **job_opts)
        rss_scheduler.add_job(scheduled_task_pruning_job, 'cron', hour=4, minute=0, **job_opts)

        if settings.get("email_marketing_enabled", False):
            rss_scheduler.add_job(
                scheduled_email_proposal_job, 'interval', hours=24,
                next_run_time=datetime.datetime.now() + datetime.timedelta(minutes=5), **job_opts
            )

        if settings.get("prewarm_agent", True):
            rss_scheduler.add_job(
                _warm_agent_client, 'date',
                run_date=datetime.datetime.now() + datetime.timedelta(seconds=30),
                id="warm_agent_client"
            )

        rss_scheduler.start()
        ASCIIColors.info(f"Scheduler started in process {os.getpid()}.")


async def shutdown_event():
    global _scheduler_lock
    ASCIIColors.info(f"--- Worker process (PID: {os.getpid()}) shutting down. ---")
    if broadcast_listener_task:
        broadcast_listener_task.cancel()
        try:
            await broadcast_listener_task
        except asyncio.CancelledError:
            pass
    if rss_scheduler and rss_scheduler.running:
        rss_scheduler.shutdown(wait=False)
    if _scheduler_lock is not None:
        _scheduler_lock.release()
        _scheduler_lock = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    await startup_event()
    try:
        yield
    finally:
        await shutdown_event()


app = FastAPI(
    title="LoLLMs Platform",
    description="API for a multi-user LoLLMs and SafeStore chat application.",
    version=APP_VERSION,
    lifespan=lifespan
)


# --------------------------------------------------------------------------- #
# CORS
# --------------------------------------------------------------------------- #
_DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:9642",
    "http://127.0.0.1:9642",
]


def _allowed_origins() -> list:
    """Explicit allow-list. Extend via SERVER_CONFIG['allowed_origins'] or LOLLMS_CORS_ORIGINS (comma-separated)."""
    origins = list(_DEFAULT_ORIGINS)
    origins += list(SERVER_CONFIG.get("allowed_origins", []) or [])
    env = os.getenv("LOLLMS_CORS_ORIGINS", "")
    origins += [o.strip() for o in env.split(",") if o.strip()]
    return list(dict.fromkeys(origins))


ALLOWED_ORIGINS = _allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # Any port on loopback only. Never `.*` together with credentials.
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)


@app.exception_handler(Exception)
async def global_unhandled_exception_handler(request: Request, exc: Exception):
    """Unhandled 500s still carry CORS headers (for allowed origins only) so the browser shows the real status."""
    error_id = uuid.uuid4().hex[:12]
    ASCIIColors.error(f"Unhandled exception [{error_id}] on {request.method} {request.url.path}")
    trace_exception(exc)

    headers = {}
    origin = request.headers.get("origin")
    if origin and origin in ALLOWED_ORIGINS:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error_id": error_id},
        headers=headers
    )


# --------------------------------------------------------------------------- #
# Routers
# --------------------------------------------------------------------------- #
for _router in (
    auth_router, admin_router, languages_router, personalities_router, friends_router,
    groups_router, dm_router, store_files_router, datastore_router, apps_router, mcp_router,
    discussion_tools_router, social_router, users_router, dm_ws_router, api_keys_router,
    openai_v1_router, ollama_v1_router, lollms_config_router, files_router, ui_router,
    sso_router, sso_client_router, scim_router, apps_zoo_router, mcps_zoo_router,
    prompts_zoo_router, personalities_zoo_router, skills_zoo_router, tasks_router,
    help_router, prompts_router, memories_router, news_router, upload_router, assets_router,
    build_discussions_router(),
):
    app.include_router(_router)

core_router = APIRouter()
build_core_router(core_router)
app.include_router(core_router, prefix="/api/discussions", tags=["Discussions"])

for _router in (
    discussion_groups_router, voices_studio_router, image_studio_router, music_studio_router,
    notes_router, notebooks_router, public_router, lollms_v1_router, flow_studio_router,
    skills_router,
):
    app.include_router(_router)


# --------------------------------------------------------------------------- #
# Direct generation endpoint
# --------------------------------------------------------------------------- #
class GenerateTextRequest(BaseModel):
    prompt: str
    max_new_tokens: Optional[int] = Field(default=1024, ge=1)
    temperature: Optional[float] = 0.2


def _token_limit_kwarg(fn) -> str:
    """Pick the parameter name the installed lollms_client uses, by inspection instead of try/except TypeError
    (which could re-run a full generation after a TypeError raised inside the model)."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return "max_new_tokens"
    if "max_new_tokens" in params:
        return "max_new_tokens"
    if "n_predict" in params:
        return "n_predict"
    return "max_new_tokens"


@app.post("/api/lollms/generate")
async def lollms_generate(
    request: GenerateTextRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    try:
        binding_alias = None
        model_name = None
        user_model_full = current_user.lollms_model_name
        if user_model_full and '/' in user_model_full:
            binding_alias, model_name = user_model_full.split('/', 1)

        lc = build_lollms_client_from_params(
            username=current_user.username,
            binding_alias=binding_alias,
            model_name=model_name,
            load_llm=True
        )

        limit_kwarg = _token_limit_kwarg(lc.generate_text)

        def _run_gen():
            return lc.generate_text(
                prompt=request.prompt,
                temperature=request.temperature,
                **{limit_kwarg: request.max_new_tokens}
            )

        generated_text = await asyncio.to_thread(_run_gen)

        from backend.db.models.generation_metric import record_generation_metric
        record_generation_metric(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            model_name=model_name or "unknown",
            binding_name=binding_alias,
            prompt_tokens=len(request.prompt) // 4,
            completion_tokens=len(generated_text) // 4,
            source="api"
        )
        return {"generated_text": generated_text}
    except HTTPException:
        raise
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail="Generation failed. See server logs.")


add_ui_routes(app)


# --------------------------------------------------------------------------- #
# Windows: silence benign WinError 10054 tracebacks from the Proactor event loop
# --------------------------------------------------------------------------- #
if os.name == 'nt':
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
        _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost

        def _silenced_call_connection_lost(self, exc):
            try:
                _orig_call_connection_lost(self, exc)
            except ConnectionResetError:
                pass
            except OSError as e:
                if getattr(e, 'winerror', None) != 10054:
                    raise

        _ProactorBasePipeTransport._call_connection_lost = _silenced_call_connection_lost
    except ImportError:
        pass


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def _detect_first_run() -> bool:
    """Must run BEFORE init_database(), which may create the SQLite file."""
    url = str(APP_DB_URL)
    if not url.startswith("sqlite:///"):
        return False
    return not Path(url.replace("sqlite:///", "", 1)).exists()


def _run_setup_wizard():
    wizard_script = Path(__file__).resolve().parent / "scripts" / "setup_wizard.py"
    if not wizard_script.exists():
        return
    env = os.environ.copy()
    project_root = str(Path(__file__).resolve().parent)
    env["PYTHONPATH"] = f"{project_root}{os.pathsep}{env.get('PYTHONPATH', '')}"
    result = subprocess.run([sys.executable, str(wizard_script)], env=env)
    if result.returncode != 0:
        sys.exit(1)


if __name__ == "__main__":
    if os.name == 'nt':
        try:
            set_start_method('spawn')
        except RuntimeError as e:
            if "context has already been set" not in str(e):
                raise

    # One id per launch, inherited by uvicorn workers. Lets them skip work done here.
    os.environ["LOLLMS_BOOT_ID"] = uuid.uuid4().hex

    is_first_run = _detect_first_run()
    if is_first_run:
        _run_setup_wizard()

    init_database(APP_DB_URL)
    run_one_time_startup_tasks()

    with db_scope() as db:
        settings.load_from_db(db)
        host_setting = settings.get("host", SERVER_CONFIG.get("host", "0.0.0.0"))
        port_setting = int(settings.get("port", SERVER_CONFIG.get("port", 9642)))
        hub_port = int(settings.get("com_hub_port", SERVER_CONFIG.get("com_hub_port", 8042)))
        https_enabled = settings.get("https_enabled", False)
        certfile = settings.get("ssl_certfile")
        keyfile = settings.get("ssl_keyfile")
        data_dir = Path(settings.get("data_dir", "data"))

    from backend.com_hub import start_hub_server
    threading.Thread(
        target=start_hub_server,
        kwargs={"host": "127.0.0.1", "port": hub_port},
        daemon=True
    ).start()

    (data_dir / "mcps").mkdir(parents=True, exist_ok=True)
    (data_dir / "apps").mkdir(parents=True, exist_ok=True)

    workers = int(os.getenv("LOLLMS_WORKERS", SERVER_CONFIG.get("workers", 1)))

    ssl_params = {}
    if https_enabled:
        try:
            if certfile and keyfile and Path(certfile).is_file() and Path(keyfile).is_file():
                ssl_params["ssl_certfile"] = certfile
                ssl_params["ssl_keyfile"] = keyfile
            else:
                raise FileNotFoundError("Certificate or key file is missing.")
        except Exception as e:
            ASCIIColors.warning(f"HTTPS config error: {e}. Server will start without HTTPS.")

    protocol = "https" if ssl_params else "http"
    content = ""
    if host_setting == "0.0.0.0":
        from backend.utils import get_accessible_host
        accessible_host = get_accessible_host()
        if accessible_host != 'localhost':
            content += f"[magenta]Recommended public access URL:[/magenta] {protocol}://{accessible_host}:{port_setting}/\n"
        content += f"[magenta]Or access locally at:[/magenta] {protocol}://localhost:{port_setting}/\n"
    else:
        content += f"[magenta]Access UI at:[/magenta] {protocol}://{host_setting}:{port_setting}/\n"
    content += f"[green]Using {workers} Workers[/green]"
    ASCIIColors.panel(content, f"LoLLMs Platform (v{APP_VERSION})")

    uvicorn.run(
        f"{Path(__file__).stem}:app",
        host=host_setting,
        port=port_setting,
        reload=False,
        workers=workers,
        timeout_keep_alive=600,
        **ssl_params
    )