import shutil
import datetime
from pathlib import Path
from typing import Optional
import os
import subprocess
import sys
from multiprocessing import cpu_count, Lock, set_start_method
from urllib.parse import urlparse
import pipmaster as pm
pm.ensure_packages(["ascii_colors>=0.11.13", "lollms_client>=1.12.4"])

from ascii_colors import ASCIIColors, trace_exception, Live, Panel, Console
import asyncio
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from multipart.multipart import FormParser
FormParser.max_size = 50 * 1024 * 1024  # 50 MB

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, inspect, desc

from backend.lollms_init_watcher import lollms_init_watcher
from backend.config import (
    APP_SETTINGS, APP_VERSION, APP_DB_URL,
    INITIAL_ADMIN_USER_CONFIG, SERVER_CONFIG,
    APPS_ZOO_ROOT_PATH, MCPS_ZOO_ROOT_PATH, PROMPTS_ZOO_ROOT_PATH, PERSONALITIES_ZOO_ROOT_PATH
)
from backend.db import init_database, get_db, session as db_session_module
from backend.db.base import Base, TaskStatus
from backend.db.migration import run_schema_migrations_and_bootstrap, check_and_update_db_version
from backend.db.models.user import User as DBUser
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.prompt import SavedPrompt as DBSavedPrompt
from backend.db.models.config import LLMBinding as DBLLMBinding
from backend.db.models.service import AppZooRepository as DBAppZooRepository, App as DBApp, MCP as DBMCP, MCPZooRepository as DBMCPZooRepository, PromptZooRepository as DBPromptZooRepository, PersonalityZooRepository as DBPersonalityZooRepository
from backend.db.models.connections import WebSocketConnection
from backend.db.models.db_task import DBTask
from backend.security import get_password_hash as hash_password
from backend.migration_utils import LegacyDiscussion
from backend.session import (
    get_user_data_root, get_user_discussion_path, user_sessions,
    build_lollms_client_from_params, get_user_lollms_client
)
from lollms_client import LollmsDataManager
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
from backend.routers.discussion_groups import discussion_groups_router
from backend.routers.voices_studio import voices_studio_router
from backend.routers.image_studio import image_studio_router
from backend.routers.notes import notes_router 
from backend.routers.notebooks import router as notebooks_router
from backend.routers.public import public_router
from backend.routers.flow_studio import router as flow_studio_router
from backend.routers.services.lollms_v1 import lollms_v1_router
from backend.tasks.email_tasks import _generate_email_proposal_task 
from backend.routers.tasks import tasks_router
from backend.routers.skills import skills_router
from backend.task_manager import task_manager
from backend.ws_manager import manager, listen_for_broadcasts
from backend.routers.help import help_router
from backend.routers.prompts import prompts_router
from backend.routers.memories import memories_router
from backend.routers.news import news_router
from backend.zoo_cache import load_cache
from backend.routers.discussion import build_discussions_router

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from backend.tasks.news_tasks import _scrape_rss_feeds_task, _cleanup_old_news_articles_task
from backend.tasks.social_tasks import _generate_feed_post_task 
from backend.tasks.system_tasks import _prune_old_tasks_task

broadcast_listener_task = None
rss_scheduler = None
startup_lock = Lock() 

def scheduled_rss_job():
    active_tasks = task_manager.get_all_tasks()
    if any(t.name == "Scheduled RSS Feed Scraping" and t.status in ['running', 'pending'] for t in active_tasks):
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
    db = db_session_module.SessionLocal()
    try:
        settings.load_from_db(db)
        if not settings.get("tasks_auto_cleanup", True):
            return
            
        task_manager.submit_task(
            name="Scheduled Task Pruning",
            target=_prune_old_tasks_task,
            description="Automatic background cleanup of old finished tasks.",
            owner_username=None
        )
    finally:
        db.close()

def check_and_run_scheduled_posts():
    db = db_session_module.SessionLocal()
    try:
        settings.load_from_db(db)
        
        if not settings.get("ai_bot_auto_post", False):
            return

        schedule = settings.get("ai_bot_post_schedule", [])
        if not schedule:
            return

        last_posted_str = settings.get("ai_bot_last_posted_at")
        last_posted = None
        if last_posted_str:
            try:
                last_posted = datetime.datetime.fromisoformat(last_posted_str)
            except ValueError: pass

        now = datetime.datetime.now()
        current_time_str = now.strftime("%H:%M")
        
        should_post = False
        for time_slot in schedule:
            if current_time_str == time_slot:
                if last_posted:
                    time_diff = now - last_posted
                    if time_diff.total_seconds() < 3540: 
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
        print(f"Error in scheduler check: {e}")
    finally:
        db.close()

def scheduled_email_proposal_job():
    task_manager.submit_task(
        name="Generate Email Proposal",
        target=_generate_email_proposal_task,
        description="Lollms researching and drafting email content.",
        owner_username=None
    )

startup_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="lollms_startup")

def run_one_time_startup_tasks(lock: Lock):
    acquired = lock.acquire(blocking=False)
    if not acquired:
        return

    ASCIIColors.panel(f"ℹ️ Worker [bold]{os.getpid()}[/bold] acquired startup lock. Running one-time tasks... 🚀")

    steps = [
        ("Database tables check/creation", False),
        ("Schema migration & bootstrap", False),
        ("Legacy discussion migration", False),
        ("Default admin & DB entries", False),
        ("App Zoo repository setup", False),
        ("MCP Zoo repository setup", False),
        ("Prompt Zoo repository setup", False),
        ("Personality Zoo repository setup", False),
        ("Filesystem‑DB synchronization", False),
        ("Stale WebSocket & task cleanup", False),
        ("Autostart & cleanup", False)
    ]

    def render_steps_panel():
        lines = []
        for description, done in steps:
            checkbox = "[green]✔[/green]" if done else "[red]✘[/red]"
            lines.append(f"{checkbox} {description}")
        markdown = "\n".join(lines)
        return ASCIIColors.panel(markdown, title="🛠️ Startup Progress", border_style="cyan")

    try:
        engine = db_session_module.engine
        Base.metadata.create_all(bind=engine)
        steps[0] = (steps[0][0], True)
        render_steps_panel()
    except Exception as e:
        ASCIIColors.error(f"Database table creation failed: {e}")
        trace_exception(e)
        lock.release()
        raise

    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            run_schema_migrations_and_bootstrap(connection, inspector)
            ASCIIColors.green("INFO: Schema migration completed.")
        check_and_update_db_version(db_session_module.SessionLocal)
        steps[1] = (steps[1][0], True)
        render_steps_panel()
    except Exception as e:
        ASCIIColors.error(f"Schema migration failed: {e}")
        trace_exception(e)
        lock.release()
        raise

    try:
        if APP_SETTINGS.get("migrate"):
            db_session = None
            try:
                db_session = next(get_db())
                all_users = db_session.query(DBUser).all()
                for user in all_users:
                    username = user.username
                    old_discussion_path = get_user_discussion_path(username)
                    if not (old_discussion_path.exists() and old_discussion_path.is_dir()):
                        continue
                    if username not in user_sessions:
                        user_sessions[username] = {
                            "lollms_model_name": user.lollms_model_name,
                            "llm_params": {}
                        }
                    db_path = get_user_data_root(username) / "discussions.db"
                    dm = LollmsDataManager(db_path=f"sqlite:///{db_path.resolve()}")
                    migrated_count = 0
                    for file_path in old_discussion_path.glob("*.yaml"):
                        discussion_db_session = None
                        try:
                            old_disc = LegacyDiscussion.load_from_yaml(file_path)
                            if not old_disc:
                                continue
                            discussion_db_session = dm.get_session()
                            if discussion_db_session.query(dm.DiscussionModel).filter_by(id=old_disc.discussion_id).first():
                                discussion_db_session.close()
                                continue
                            new_db_disc_orm = dm.DiscussionModel(
                                id=old_disc.discussion_id,
                                discussion_metadata={"title": old_disc.title, "rag_datastore_ids": old_disc.rag_datastore_ids},
                                active_branch_id=old_disc.active_branch_id
                            )
                            discussion_db_session.add(new_db_disc_orm)
                            for msg in old_disc.messages:
                                msg_orm = dm.MessageModel(
                                    id=msg.id,
                                    discussion_id=new_db_disc_orm.id,
                                    parent_id=msg.parent_id,
                                    sender=msg.sender,
                                    sender_type=msg.sender_type,
                                    content=msg.content,
                                    created_at=msg.created_at,
                                    binding_name=msg.binding_name,
                                    model_name=msg.model_name,
                                    tokens=msg.token_count,
                                    message_metadata={"sources": msg.sources, "steps": msg.steps}
                                )
                                discussion_db_session.add(msg_orm)
                            discussion_db_session.commit()
                            migrated_count += 1
                        except Exception as e:
                            if discussion_db_session:
                                discussion_db_session.rollback()
                        finally:
                            if discussion_db_session:
                                discussion_db_session.close()
                    if migrated_count > 0:
                        backup_path = old_discussion_path.parent / f"{old_discussion_path.name}_migrated_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                        shutil.move(str(old_discussion_path), str(backup_path))
            finally:
                if db_session:
                    db_session.close()
        steps[2] = (steps[2][0], True)
        render_steps_panel()
    except Exception as e:
        trace_exception(e)

    try:
        db_for_defaults = next(get_db())
        admin_username = INITIAL_ADMIN_USER_CONFIG.get("username", "admin")
        admin_password = INITIAL_ADMIN_USER_CONFIG.get("password", "admin")
        admin_exists = db_for_defaults.query(DBUser).filter(DBUser.is_admin == True).first() is not None
        if not admin_exists:
            existing_user = db_for_defaults.query(DBUser).filter(DBUser.username == admin_username).first()
            if existing_user:
                existing_user.is_admin = True
                existing_user.is_active = True
                existing_user.status = "active"
                db_for_defaults.commit()
            else:
                new_admin = DBUser(
                    username=admin_username, 
                    hashed_password=hash_password(admin_password), 
                    is_admin=True,
                    is_active=True,
                    status="active"
                )
                db_for_defaults.add(new_admin)
                db_for_defaults.commit()
        steps[3] = (steps[3][0], True)
        render_steps_panel()
    except Exception as e:
        trace_exception(e)
    finally:
        if db_for_defaults:
            db_for_defaults.close()

    try:
        db_for_repos = next(get_db())
        app_zoo_name = "Official LoLLMs Apps Zoo"
        app_zoo_url = "https://github.com/ParisNeo/lollms_apps_zoo.git"
        app_zoo_repo_path = APPS_ZOO_ROOT_PATH / app_zoo_name

        if not db_for_repos.query(DBAppZooRepository).filter(
            or_(DBAppZooRepository.name == app_zoo_name, DBAppZooRepository.url == app_zoo_url)
        ).first():
            default_repo = DBAppZooRepository(name=app_zoo_name, url=app_zoo_url, is_deletable=False)
            db_for_repos.add(default_repo)
            db_for_repos.commit()
        if not app_zoo_repo_path.exists():
            subprocess.run(["git", "clone", app_zoo_url, str(app_zoo_repo_path)], check=True)
        steps[4] = (steps[4][0], True)
        render_steps_panel()
    except Exception as e:
        trace_exception(e)
    finally:
        if db_for_repos:
            db_for_repos.close()

    try:
        db_for_mcps = next(get_db())
        mcp_zoo_name = "lollms_mcps_zoo"
        mcp_zoo_url = "https://github.com/ParisNeo/lollms_mcps_zoo.git"
        mcp_zoo_repo_path = MCPS_ZOO_ROOT_PATH / mcp_zoo_name

        if not db_for_mcps.query(DBMCPZooRepository).filter(
            or_(DBMCPZooRepository.name == mcp_zoo_name, DBMCPZooRepository.url == mcp_zoo_url)
        ).first():
            default_mcp_repo = DBMCPZooRepository(name=mcp_zoo_name, url=mcp_zoo_url, is_deletable=False)
            db_for_mcps.add(default_mcp_repo)
            db_for_mcps.commit()
        if not mcp_zoo_repo_path.exists():
            subprocess.run(["git", "clone", mcp_zoo_url, str(mcp_zoo_repo_path)], check=True)
        steps[5] = (steps[5][0], True)
        render_steps_panel()
    except Exception as e:
        trace_exception(e)
    finally:
        if db_for_mcps:
            db_for_mcps.close()

    try:
        db_for_prompts = next(get_db())
        prompt_zoo_name = "lollms_prompts_zoo"
        prompt_zoo_url = "https://github.com/ParisNeo/lollms_prompts_zoo.git"
        prompt_zoo_repo_path = PROMPTS_ZOO_ROOT_PATH / prompt_zoo_name

        if not db_for_prompts.query(DBPromptZooRepository).filter(
            or_(DBPromptZooRepository.name == prompt_zoo_name, DBPromptZooRepository.url == prompt_zoo_url)
        ).first():
            default_prompt_repo = DBPromptZooRepository(name=prompt_zoo_name, url=prompt_zoo_url, is_deletable=False)
            db_for_prompts.add(default_prompt_repo)
            db_for_prompts.commit()
        if not prompt_zoo_repo_path.exists():
            subprocess.run(["git", "clone", prompt_zoo_url, str(prompt_zoo_repo_path)], check=True)
        steps[6] = (steps[6][0], True)
        render_steps_panel()
    except Exception as e:
        trace_exception(e)
    finally:
        if db_for_prompts:
            db_for_prompts.close()

    try:
        db_for_personalities = next(get_db())
        personality_zoo_name = "lollms_personalities_zoo"
        personality_zoo_url = "https://github.com/ParisNeo/lollms_personalities_zoo.git"
        personality_zoo_repo_path = PERSONALITIES_ZOO_ROOT_PATH / personality_zoo_name

        if not db_for_personalities.query(DBPersonalityZooRepository).filter(
            or_(DBPersonalityZooRepository.name == personality_zoo_name, DBPersonalityZooRepository.url == personality_zoo_url)
        ).first():
            default_personality_repo = DBPersonalityZooRepository(name=personality_zoo_name, url=personality_zoo_url, is_deletable=False)
            db_for_personalities.add(default_personality_repo)
            db_for_personalities.commit()
        if not personality_zoo_repo_path.exists():
            subprocess.run(["git", "clone", personality_zoo_url, str(personality_zoo_repo_path)], check=True)
        steps[7] = (steps[7][0], True)
        render_steps_panel()
    except Exception as e:
        trace_exception(e)
    finally:
        if db_for_personalities:
            db_for_personalities.close()

    try:
        db_for_sync = next(get_db())
        synchronize_filesystem_and_db(db_for_sync)
        steps[8] = (steps[8][0], True)
        render_steps_panel()
    except Exception as e:
        trace_exception(e)
    finally:
        if db_for_sync:
            db_for_sync.close()

    try:
        db_for_cleanup = next(get_db())
        db_for_cleanup.query(WebSocketConnection).delete()
        interrupted_tasks = db_for_cleanup.query(DBTask).filter(
            DBTask.status.in_([TaskStatus.RUNNING, TaskStatus.PENDING])
        ).all()
        if interrupted_tasks:
            for task in interrupted_tasks:
                task.status = TaskStatus.FAILED
                task.error = "Task interrupted by server restart."
                task.completed_at = datetime.datetime.now(datetime.timezone.utc)
                task.logs = [{"timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "message": "System Restart Recovery", "level": "ERROR"}]
            db_for_cleanup.commit()
        steps[9] = (steps[9][0], True)
        render_steps_panel()
    except Exception as e:
        trace_exception(e)
    finally:
        if db_for_cleanup:
            db_for_cleanup.close()

    try:
        load_cache()
        task_manager.init_app(db_session_module.SessionLocal)
        cleanup_and_autostart_apps()
        steps[10] = (steps[10][0], True)
        render_steps_panel()
    except Exception as e:
        trace_exception(e)

    try:
        db_warmup = next(get_db())
        active_llm_bindings = db_warmup.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()
        if active_llm_bindings:
            for binding in active_llm_bindings:
                startup_executor.submit(
                    build_lollms_client_from_params,
                    "lollms",
                    binding_alias=binding.alias,
                    load_llm=True,
                    callback=lollms_init_watcher
                )
        db_warmup.close()
        steps.append(("Pre-warm Active Bindings", True))
    except Exception as e:
        trace_exception(e)

    lock.release()

async def startup_event():
    global broadcast_listener_task, rss_scheduler, startup_lock

    init_database(APP_DB_URL)
    run_one_time_startup_tasks(startup_lock)

    db = db_session_module.SessionLocal()
    try:
        settings.load_from_db(db)

        active_bindings = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()
        if active_bindings:
            loop = asyncio.get_running_loop()
            for b in active_bindings:
                loop.run_in_executor(
                    startup_executor,
                    get_user_lollms_client,
                    "lollms",
                    b.alias
                )
    finally:
        db.close()

    manager.set_loop(asyncio.get_running_loop())
    task_manager.init_app(db_session_module.SessionLocal)

    if SERVER_CONFIG.get("workers", 1) > 1:
        broadcast_listener_task = asyncio.create_task(listen_for_broadcasts())

    if os.getpid() == os.getppid() or os.getenv("WORKER_ID") == "1":
        rss_scheduler = BackgroundScheduler(daemon=True)

        if settings.get("rss_feed_enabled"):
            interval = settings.get("rss_feed_check_interval_minutes", 60)
            next_run = datetime.datetime.now() + datetime.timedelta(seconds=20)
            rss_scheduler.add_job(scheduled_rss_job, 'interval', minutes=interval, next_run_time=next_run)

            retention_days = settings.get("rss_news_retention_days", 1)
            if retention_days > 0:
                rss_scheduler.add_job(scheduled_news_cleanup_job, 'cron', hour=3, minute=0)

        rss_scheduler.add_job(check_and_run_scheduled_posts, 'interval', minutes=1)
        rss_scheduler.add_job(scheduled_task_pruning_job, 'cron', hour=4, minute=0)

        if settings.get("email_marketing_enabled", False):
            rss_scheduler.add_job(
                scheduled_email_proposal_job, 
                'interval', 
                hours=24, 
                next_run_time=datetime.datetime.now() + datetime.timedelta(minutes=5)
            )

        if not rss_scheduler.running:
            rss_scheduler.start()

async def shutdown_event():
    ASCIIColors.info(f"--- Worker process (PID: {os.getpid()}) shutting down. ---")
    if broadcast_listener_task:
        broadcast_listener_task.cancel()
        try:
            await broadcast_listener_task
        except asyncio.CancelledError:
            pass
    if rss_scheduler and rss_scheduler.running:
        rss_scheduler.shutdown()

app = FastAPI(
    title="LoLLMs Platform", 
    description="API for a multi-user LoLLMs and SafeStore chat application.", 
    version=APP_VERSION,
    on_startup=[startup_event],
    on_shutdown=[shutdown_event]
)

# Robust, Top-Level CORS Middleware Setup (Universal for all workers and preflight OPTIONS requests)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex="https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(languages_router)
app.include_router(personalities_router)
app.include_router(friends_router)
app.include_router(groups_router)
app.include_router(dm_router)
app.include_router(store_files_router)
app.include_router(datastore_router)
app.include_router(apps_router)
app.include_router(mcp_router)
app.include_router(discussion_tools_router)
app.include_router(social_router)
app.include_router(users_router)
app.include_router(dm_ws_router)
app.include_router(api_keys_router)
app.include_router(openai_v1_router)
app.include_router(ollama_v1_router)
app.include_router(lollms_config_router)
app.include_router(files_router)
app.include_router(ui_router)
app.include_router(sso_router)
app.include_router(sso_client_router)
app.include_router(scim_router)
app.include_router(apps_zoo_router)
app.include_router(mcps_zoo_router)
app.include_router(prompts_zoo_router)
app.include_router(personalities_zoo_router)
app.include_router(tasks_router)
app.include_router(help_router)
app.include_router(prompts_router)
app.include_router(memories_router)
app.include_router(news_router)
app.include_router(upload_router)
app.include_router(assets_router)
app.include_router(build_discussions_router())
app.include_router(discussion_groups_router)
app.include_router(voices_studio_router)
app.include_router(image_studio_router)
app.include_router(notes_router)
app.include_router(notebooks_router) 
app.include_router(public_router)
app.include_router(lollms_v1_router) 
app.include_router(flow_studio_router)
app.include_router(skills_router)

add_ui_routes(app)

if __name__ == "__main__":
    if os.name == 'nt':
        try:
            set_start_method('spawn')
        except RuntimeError as e:
            if "context has already been set" not in str(e):
                raise
            else:
                pass

    init_database(APP_DB_URL)

    db_path_str = APP_DB_URL.replace("sqlite:///", "")
    db_path = Path(db_path_str)
    is_first_run = not db_path.exists()
    
    if is_first_run:
        wizard_script = Path(__file__).resolve().parent / "scripts" / "setup_wizard.py"
        if wizard_script.exists():
            python_executable = sys.executable
            env = os.environ.copy()
            project_root_path = str(Path(__file__).resolve().parent)
            current_python_path = env.get("PYTHONPATH", "")
            new_python_path = f"{project_root_path}{os.pathsep}{current_python_path}"
            env["PYTHONPATH"] = new_python_path
            
            result = subprocess.run([python_executable, str(wizard_script)], env=env)
            if result.returncode != 0:
                sys.exit(1)

    run_one_time_startup_tasks(startup_lock)
    
    db = db_session_module.SessionLocal()
    try:
        settings.load_from_db(db)

        from backend.com_hub import start_hub_server
        hub_port_val = settings.get("com_hub_port", SERVER_CONFIG.get("com_hub_port", 8042))
        threading.Thread(
            target=start_hub_server, 
            kwargs={"host": "127.0.0.1", "port": int(hub_port_val)}, 
            daemon=True
        ).start()

        host_setting = settings.get("host", SERVER_CONFIG.get("host", "0.0.0.0"))
        port_setting = settings.get("port", SERVER_CONFIG.get("port", 9642))
        https_enabled = settings.get("https_enabled", False)
    finally:
        db.close()
   
    data_dir = Path(settings.get("data_dir", "data"))
    (data_dir / "mcps").mkdir(parents=True, exist_ok=True)
    (data_dir / "apps").mkdir(parents=True, exist_ok=True)
    
    workers = int(os.getenv("LOLLMS_WORKERS", SERVER_CONFIG.get("workers", 1)))
    
    ssl_params = {}
    if settings.get("https_enabled"):
        certfile = settings.get("ssl_certfile")
        keyfile = settings.get("ssl_keyfile")
        try:
            if certfile and keyfile and Path(certfile).is_file() and Path(keyfile).is_file():
                ssl_params["ssl_certfile"] = certfile
                ssl_params["ssl_keyfile"] = keyfile
            else:
                raise FileNotFoundError("Certificate or key file is missing.")
        except Exception as e:
            print(f"WARNING: HTTPS config error: {e}. Server will start without HTTPS.")

    content = ""
    protocol = "https" if ssl_params else "http"

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

    from pydantic import BaseModel, Field
    from backend.session import get_current_active_user, UserAuthDetails

    class GenerateTextRequest(BaseModel):
        prompt: str
        max_new_tokens: Optional[int] = Field(default=1024, alias="max_new_tokens")
        temperature: Optional[float] = 0.2

    @app.post("/api/lollms/generate")
    async def lollms_generate(
        request: GenerateTextRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        try:
            user_model_full = current_user.lollms_model_name
            binding_alias = None
            model_name = None
            if user_model_full and '/' in user_model_full:
                binding_alias, model_name = user_model_full.split('/', 1)

            lc = build_lollms_client_from_params(
                username=current_user.username,
                binding_alias=binding_alias,
                model_name=model_name,
                load_llm=True
            )

            generated_text = await asyncio.to_thread(
                lc.generate_text,
                prompt=request.prompt,
                n_predict=request.max_new_tokens,
                temperature=request.temperature
            )
            return {"generated_text": generated_text}
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=str(e))

    uvicorn.run("main:app", host=host_setting, port=int(port_setting), reload=False, workers=workers, timeout_keep_alive=600, **ssl_params)