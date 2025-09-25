import shutil
import datetime
from pathlib import Path
from typing import Optional
import os
import subprocess
import sys
from multiprocessing import cpu_count, Lock
from urllib.parse import urlparse
from ascii_colors import ASCIIColors, trace_exception
import asyncio
import time


from multipart.multipart import FormParser
FormParser.max_size = 50 * 1024 * 1024  # 50 MB

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, inspect

from backend.config import (
    APP_SETTINGS, APP_VERSION, APP_DB_URL,
    INITIAL_ADMIN_USER_CONFIG, SERVER_CONFIG,
    APPS_ZOO_ROOT_PATH, MCPS_ZOO_ROOT_PATH, PROMPTS_ZOO_ROOT_PATH, PERSONALITIES_ZOO_ROOT_PATH,
    LOLLMS_CLIENT_DEFAULTS, APP_DATA_DIR
)
from backend.db import init_database, get_db, session as db_session_module
from backend.db.base import Base
from backend.db.migration import run_schema_migrations_and_bootstrap, check_and_update_db_version
from backend.db.models.user import User as DBUser
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.prompt import SavedPrompt as DBSavedPrompt
from backend.db.models.config import LLMBinding as DBLLMBinding
from backend.db.models.service import AppZooRepository as DBAppZooRepository, App as DBApp, MCP as DBMCP, MCPZooRepository as DBMCPZooRepository, PromptZooRepository as DBPromptZooRepository, PersonalityZooRepository as DBPersonalityZooRepository
from backend.security import get_password_hash as hash_password
from backend.migration_utils import LegacyDiscussion
from backend.session import (
    get_user_data_root, get_user_discussion_path, user_sessions
)
from lollms_client import LollmsDataManager
from backend.settings import settings

from backend.routers.auth import auth_router
from backend.routers.discussion import build_discussions_router
from backend.routers.admin import admin_router
from backend.routers.languages import languages_router
from backend.routers.personalities import personalities_router
from backend.routers.friends import friends_router
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
from backend.routers.extensions.app_utils import cleanup_and_autostart_apps, synchronize_filesystem_and_db
from backend.routers.zoos.apps_zoo import apps_zoo_router
from backend.routers.zoos.mcps_zoo import mcps_zoo_router
from backend.routers.zoos.prompts_zoo import prompts_zoo_router
from backend.routers.zoos.personalities_zoo import personalities_zoo_router
from backend.routers.discussion_groups import discussion_groups_router

from backend.routers.tasks import tasks_router
from backend.task_manager import task_manager
from backend.ws_manager import manager, listen_for_broadcasts
from backend.routers.help import help_router
from backend.routers.prompts import prompts_router
from backend.routers.memories import memories_router
from backend.zoo_cache import load_cache

import uvicorn
from backend.settings import settings

broadcast_listener_task = None

def run_one_time_startup_tasks(lock: Lock):
    """
    This function runs all tasks that should only be executed once across all worker processes.
    It uses a multiprocessing lock to ensure single execution.
    """
    acquired = lock.acquire(block=False)
    if not acquired:
        return
    
    ASCIIColors.green(f"Worker {os.getpid()} acquired startup lock. Running one-time tasks...")
    try:
        print("--- Running One-Time Startup Tasks ---")
        
        # --- Database Migration and Bootstrapping (run by one worker) ---
        engine = db_session_module.engine
        Base.metadata.create_all(bind=engine)
        print(f"INFO: Database tables checked/created using metadata at URL: {APP_DB_URL}")
        with engine.connect() as connection:
            inspector = inspect(connection)
            try:
                run_schema_migrations_and_bootstrap(connection, inspector)
                print("INFO: Database schema migration/check completed successfully.")
            except Exception as e_migrate:
                print(f"CRITICAL: Database migration failed: {e_migrate}.")
                trace_exception(e_migrate)
                raise
        check_and_update_db_version(db_session_module.SessionLocal)
        # --- End Database Migration ---
        
        print("\n--- Running Automated Discussion Migration ---")
        db_session = None
        if APP_SETTINGS.get("migrate"):
            try:
                db_session = next(get_db())
                all_users = db_session.query(DBUser).all()
                for user in all_users:
                    username = user.username
                    old_discussion_path = get_user_discussion_path(username)
                    if not (old_discussion_path.exists() and old_discussion_path.is_dir()):
                        continue
                    print(f"Found legacy discussion folder for '{username}'. Starting migration...")
                    if username not in user_sessions:
                        user_sessions[username] = {
                                                    "lollms_clients": {}, 
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
                            if not old_disc: continue
                            discussion_db_session = dm.get_session()
                            if discussion_db_session.query(dm.DiscussionModel).filter_by(id=old_disc.discussion_id).first():
                                discussion_db_session.close()
                                continue
                            new_db_disc_orm = dm.DiscussionModel(id=old_disc.discussion_id, discussion_metadata={"title": old_disc.title, "rag_datastore_ids": old_disc.rag_datastore_ids}, active_branch_id=old_disc.active_branch_id)
                            discussion_db_session.add(new_db_disc_orm)
                            for msg in old_disc.messages:
                                msg_orm = dm.MessageModel(id=msg.id, discussion_id=new_db_disc_orm.id, parent_id=msg.parent_id, sender=msg.sender, sender_type=msg.sender_type, content=msg.content, created_at=msg.created_at, binding_name=msg.binding_name, model_name=msg.model_name, tokens=msg.token_count, message_metadata={"sources": msg.sources, "steps": msg.steps})
                                discussion_db_session.add(msg_orm)
                            discussion_db_session.commit()
                            migrated_count += 1
                        except Exception as e:
                            if discussion_db_session: discussion_db_session.rollback()
                            print(f"    - FAILED to migrate {file_path.name}: {e}")
                        finally:
                            if discussion_db_session: discussion_db_session.close()
                    if migrated_count > 0:
                        backup_path = old_discussion_path.parent / f"{old_discussion_path.name}_migrated_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                        shutil.move(str(old_discussion_path), str(backup_path))
                        print(f"Successfully migrated {migrated_count} discussions and backed up legacy folder.")
                    if username in user_sessions: user_sessions[username]['lollms_clients'] = {}
                
            except Exception as e:
                print(f"CRITICAL ERROR during migration: {e}")
            finally:
                if db_session: db_session.close()
            print("--- Migration Finished ---\n")

        ASCIIColors.yellow("--- Verifying Default Database Entries & Repositories ---")
        db_for_defaults: Optional[Session] = None
        try:
            db_for_defaults = next(get_db())
            
            admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
            admin_password = INITIAL_ADMIN_USER_CONFIG.get("password")
            if admin_username and admin_password and not db_for_defaults.query(DBUser).filter(DBUser.username == admin_username).first():
                new_admin = DBUser(username=admin_username, hashed_password=hash_password(admin_password), is_admin=True)
                db_for_defaults.add(new_admin)
                db_for_defaults.commit()
                ASCIIColors.green(f"INFO: Initial admin user '{admin_username}' created successfully.")

            if not db_for_defaults.query(DBLLMBinding).first():
                ASCIIColors.yellow("No LLM bindings found in the database. Creating one from config.toml.")
                if LOLLMS_CLIENT_DEFAULTS:
                    binding_name = LOLLMS_CLIENT_DEFAULTS.get("binding_name")
                    if binding_name:
                        try:
                            config_data = LOLLMS_CLIENT_DEFAULTS.copy()
                            name = config_data.pop("binding_name", None)
                            default_model_name = config_data.pop("default_model_name", None)
                            alias = name
                            counter = 1
                            while db_for_defaults.query(DBLLMBinding).filter(DBLLMBinding.alias == alias).first():
                                alias = f"{name}_{counter}"
                                counter += 1
                            new_binding = DBLLMBinding(
                                alias=alias, name=name, config=config_data,
                                default_model_name=default_model_name, is_active=True
                            )
                            db_for_defaults.add(new_binding)
                            db_for_defaults.commit()
                            ASCIIColors.green(f"INFO: Successfully created initial LLM binding '{alias}' from config.toml.")
                        except Exception as e:
                            ASCIIColors.error(f"Failed to create initial binding: {e}")
                            db_for_defaults.rollback()
                            trace_exception(e) 
                    else:
                        ASCIIColors.warning("`binding_name` not found in [lollms_client_defaults] in config.toml. Cannot create initial binding.")
                else:
                    ASCIIColors.warning("[lollms_client_defaults] section is empty in config.toml. No initial binding created.")

        except Exception as e:
            ASCIIColors.error(f"ERROR during admin/personality/prompt setup: {e}")
            trace_exception(e)
            if db_for_defaults: db_for_defaults.rollback()
        finally:
            if db_for_defaults: db_for_defaults.close()

        db_for_repos: Optional[Session] = None
        try:
            db_for_repos = next(get_db())
            app_zoo_name = "Official LoLLMs Apps Zoo"
            app_zoo_url = "https://github.com/ParisNeo/lollms_apps_zoo.git"
            app_zoo_repo_path = APPS_ZOO_ROOT_PATH / app_zoo_name
            
            if not db_for_repos.query(DBAppZooRepository).filter(or_(DBAppZooRepository.name == app_zoo_name, DBAppZooRepository.url == app_zoo_url)).first():
                default_repo = DBAppZooRepository(name=app_zoo_name, url=app_zoo_url, is_deletable=False)
                db_for_repos.add(default_repo)
                db_for_repos.commit()
                ASCIIColors.green(f"INFO: Default App Zoo repo '{app_zoo_name}' added to DB.")

            if not app_zoo_repo_path.exists():
                ASCIIColors.yellow(f"First setup: Cloning '{app_zoo_name}'. This may take a moment...")
                subprocess.run(["git", "clone", app_zoo_url, str(app_zoo_repo_path)], check=True)
                ASCIIColors.green("Cloning complete.")

        except Exception as e:
            ASCIIColors.error(f"ERROR during App Zoo repository setup: {e}")
            trace_exception(e)
            if db_for_repos: db_for_repos.rollback()
        finally:
            if db_for_repos: db_for_repos.close()
            
        db_for_mcps: Optional[Session] = None
        try:
            db_for_mcps = next(get_db())
            mcp_zoo_name = "lollms_mcps_zoo"
            mcp_zoo_url = "https://github.com/ParisNeo/lollms_mcps_zoo.git"
            mcp_zoo_repo_path = MCPS_ZOO_ROOT_PATH / mcp_zoo_name

            if not db_for_mcps.query(DBMCPZooRepository).filter(or_(DBMCPZooRepository.name == mcp_zoo_name, DBMCPZooRepository.url == mcp_zoo_url)).first():
                default_mcp_repo = DBMCPZooRepository(name=mcp_zoo_name, url=mcp_zoo_url, is_deletable=False)
                db_for_mcps.add(default_mcp_repo)
                db_for_mcps.commit()
                ASCIIColors.green(f"INFO: Default MCP Zoo repo '{mcp_zoo_name}' added to DB.")

            if not mcp_zoo_repo_path.exists():
                ASCIIColors.yellow(f"First setup: Cloning '{mcp_zoo_name}'. This may take a moment...")
                subprocess.run(["git", "clone", mcp_zoo_url, str(mcp_zoo_repo_path)], check=True)
                ASCIIColors.green("Cloning complete.")
        except Exception as e:
            ASCIIColors.error(f"ERROR during MCP Zoo repository setup: {e}")
            trace_exception(e)
            if db_for_mcps: db_for_mcps.rollback()
        finally:
            if db_for_mcps: db_for_mcps.close()
        
        db_for_prompts: Optional[Session] = None
        try:
            db_for_prompts = next(get_db())
            prompt_zoo_name = "lollms_prompts_zoo"
            prompt_zoo_url = "https://github.com/ParisNeo/lollms_prompts_zoo.git"
            prompt_zoo_repo_path = PROMPTS_ZOO_ROOT_PATH / prompt_zoo_name

            if not db_for_prompts.query(DBPromptZooRepository).filter(or_(DBPromptZooRepository.name == prompt_zoo_name, DBPromptZooRepository.url == prompt_zoo_url)).first():
                default_prompt_repo = DBPromptZooRepository(name=prompt_zoo_name, url=prompt_zoo_url, is_deletable=False)
                db_for_prompts.add(default_prompt_repo)
                db_for_prompts.commit()
                ASCIIColors.green(f"INFO: Default Prompt Zoo repo '{prompt_zoo_name}' added to DB.")

            if not prompt_zoo_repo_path.exists():
                ASCIIColors.yellow(f"First setup: Cloning '{prompt_zoo_name}'. This may take a moment...")
                subprocess.run(["git", "clone", prompt_zoo_url, str(prompt_zoo_repo_path)], check=True)
                ASCIIColors.green("Cloning complete.")
        except Exception as e:
            ASCIIColors.error(f"ERROR during Prompt Zoo repository setup: {e}")
            trace_exception(e)
            if db_for_prompts: db_for_prompts.rollback()
        finally:
            if db_for_prompts: db_for_prompts.close()

        db_for_personalities: Optional[Session] = None
        try:
            db_for_personalities = next(get_db())
            personality_zoo_name = "lollms_personalities_zoo"
            personality_zoo_url = "https://github.com/ParisNeo/lollms_personalities_zoo.git"
            personality_zoo_repo_path = PERSONALITIES_ZOO_ROOT_PATH / personality_zoo_name

            if not db_for_personalities.query(DBPersonalityZooRepository).filter(or_(DBPersonalityZooRepository.name == personality_zoo_name, DBPersonalityZooRepository.url == personality_zoo_url)).first():
                default_personality_repo = DBPersonalityZooRepository(name=personality_zoo_name, url=personality_zoo_url, is_deletable=False)
                db_for_personalities.add(default_personality_repo)
                db_for_personalities.commit()
                ASCIIColors.green(f"INFO: Default Personality Zoo repo '{personality_zoo_name}' added to DB.")

            if not personality_zoo_repo_path.exists():
                ASCIIColors.yellow(f"First setup: Cloning '{personality_zoo_name}'. This may take a moment...")
                subprocess.run(["git", "clone", personality_zoo_url, str(personality_zoo_repo_path)], check=True)
                ASCIIColors.green("Cloning complete.")
        except Exception as e:
            ASCIIColors.error(f"ERROR during Personality Zoo repository setup: {e}")
            trace_exception(e)
            if db_for_personalities: db_for_personalities.rollback()
        finally:
            if db_for_personalities: db_for_personalities.close()


        ASCIIColors.yellow("--- Verifying Default Database Entries Verified ---")

        ASCIIColors.yellow("--- Synchronizing Filesystem Installations with Database ---")
        db_for_sync: Optional[Session] = None
        try:
            db_for_sync = next(get_db())
            synchronize_filesystem_and_db(db_for_sync)
            ASCIIColors.green("--- Synchronization Complete ---")
        except Exception as e:
            ASCIIColors.error(f"ERROR during startup synchronization: {e}")
            trace_exception(e)
            if db_for_sync: db_for_sync.rollback()
        finally:
            if db_for_sync: db_for_sync.close()

        load_cache()
        
        # Initialize the task manager AFTER DB is stable
        task_manager.init_app(db_session_module.SessionLocal)

        try:
            ASCIIColors.yellow("--- Running App Cleanup and Autostart (once) ---")
            cleanup_and_autostart_apps()
            ASCIIColors.green("--- Autostart Complete ---")
        except Exception as e:
            ASCIIColors.error(f"--- Autostart Failed: {e} ---")
            trace_exception(e)
            
    finally:
        lock.release()
        ASCIIColors.green(f"Worker {os.getpid()} released startup lock.")

async def startup_event():
    """
    This event runs for EACH worker process created by Uvicorn.
    """
    global broadcast_listener_task
    
    # Each worker must initialize its own database connection pool.
    init_database(APP_DB_URL)
    
    # Each worker needs to load settings into its own memory.
    # The _is_loaded flag in settings will prevent redundant logging.
    db = db_session_module.SessionLocal()
    try:
        settings.load_from_db(db)
    finally:
        db.close()
    
    manager.set_loop(asyncio.get_running_loop())
    task_manager.init_app(db_session_module.SessionLocal)
    
    broadcast_listener_task = asyncio.create_task(listen_for_broadcasts())
    
    print(f"INFO: Worker process (PID: {os.getpid()}) started and initialized.")

async def shutdown_event():
    ASCIIColors.info(f"--- Worker process (PID: {os.getpid()}) shutting down. ---")
    if broadcast_listener_task:
        broadcast_listener_task.cancel()
        try:
            await broadcast_listener_task
        except asyncio.CancelledError:
            ASCIIColors.info(f"Broadcast listener task in worker {os.getpid()} cancelled successfully.")

app = FastAPI(
    title="LoLLMs Platform", 
    description="API for a multi-user LoLLMs and SafeStore chat application.", 
    version=APP_VERSION,
    on_startup=[startup_event],
    on_shutdown=[shutdown_event]
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(languages_router)
app.include_router(personalities_router)
app.include_router(friends_router)
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
app.include_router(apps_zoo_router)
app.include_router(mcps_zoo_router)
app.include_router(prompts_zoo_router)
app.include_router(personalities_zoo_router)
app.include_router(tasks_router)
app.include_router(help_router)
app.include_router(prompts_router)
app.include_router(memories_router)
app.include_router(upload_router)
app.include_router(assets_router)
app.include_router(build_discussions_router())
app.include_router(discussion_groups_router)

add_ui_routes(app)

if __name__ == "__main__":
    # This block is executed only by the main process, before Uvicorn starts workers.
    init_database(APP_DB_URL)
    db = db_session_module.SessionLocal()
    try:
        # Load settings once for the main process to use for CORS, etc.
        settings.load_from_db(db)
        
        # --- CORS Setup ---
        host = SERVER_CONFIG.get("host")
        port = SERVER_CONFIG.get("port")
        https_enabled = SERVER_CONFIG.get("https_enabled")

        allowed_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

        if host == "0.0.0.0":
            allowed_origins.extend([f"http://localhost:{port}", f"http://127.0.0.1:{port}"])
            if https_enabled:
                allowed_origins.extend([f"https://localhost:{port}", f"https://127.0.0.1:{port}"])
        else:
            allowed_origins.append(f"http://{host}:{port}")
            if https_enabled:
                allowed_origins.append(f"https://{host}:{port}")

        sso_apps = db.query(DBApp).filter(DBApp.active == True, DBApp.authentication_type == 'lollms_sso').all()
        sso_mcps = db.query(DBMCP).filter(DBMCP.active == True, DBMCP.authentication_type == 'lollms_sso').all()
        openai_apps = db.query(DBApp).filter(DBApp.is_installed == True, DBApp.allow_openai_api_access == True).all()
        
        sso_services = sso_apps + sso_mcps + openai_apps
        for service in sso_services:
            if service.url:
                try:
                    parsed_url = urlparse(service.url)
                    origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
                    if origin not in allowed_origins:
                        allowed_origins.append(origin)
                        ASCIIColors.green(f"CORS: Allowing authenticated app origin: {origin}")
                except Exception as e:
                    ASCIIColors.warning(f"CORS: Could not parse URL for service '{service.name}': {service.url}. Error: {e}")

        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    finally:
        db.close()
   
    data_dir = Path(settings.get("data_dir","data"))
    mcp_dir = data_dir / "mcps"
    apps_dir = data_dir / "apps"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    apps_dir.mkdir(parents=True, exist_ok=True)
    host_setting = settings.get("host", "0.0.0.0")
    port_setting = int(settings.get("port", SERVER_CONFIG.get("port", 9642)))
    workers = int(os.getenv("LOLLMS_WORKERS", settings.get("workers", SERVER_CONFIG.get("workers", cpu_count()))))

    # --- MAIN PROCESS ONLY SETUP ---
    startup_lock = Lock()

    run_one_time_startup_tasks(startup_lock)
    
    # --- END MAIN PROCESS ONLY SETUP ---

    ssl_params = {}
    if settings.get("https_enabled"):
        ASCIIColors.green("Https enabled")
        certfile = settings.get("ssl_certfile")
        keyfile = settings.get("ssl_keyfile")
        ASCIIColors.green(f"certfile:{certfile}")
        ASCIIColors.green(f"keyfile:{keyfile}")

        try:
            if certfile and keyfile and Path(certfile).is_file() and Path(keyfile).is_file():
                ssl_params["ssl_certfile"] = certfile
                ssl_params["ssl_keyfile"] = keyfile
            else:
                raise FileNotFoundError("Certificate or key file is missing, not found, or invalid.")
        except Exception as e:
            print(f"WARNING: HTTPS is enabled in settings, but the certificate or key file is missing, not found, or invalid. Error: {e}")
            print(f"         Certfile path: '{certfile}'")
            print(f"         Keyfile path: '{keyfile}'")
            print("         Server will start without HTTPS to avoid crashing.")

    # This banner is now printed only once by the main process
    print("")
    ASCIIColors.cyan(f"--- LoLLMs Plateform (v{APP_VERSION}) ---")
    protocol = "https" if ssl_params else "http"

    if host_setting == "0.0.0.0":
        if sys.platform == "win32":
            ASCIIColors.yellow("\n--- IMPORTANT WINDOWS FIREWALL NOTICE ---")
            ASCIIColors.yellow(f"You are running on Windows with host '0.0.0.0', making the app accessible on your network.")
            ASCIIColors.yellow("However, Windows Defender Firewall will likely block incoming connections by default.")
            ASCIIColors.yellow(f"If you cannot access the UI from another device, you may need to create an")
            ASCIIColors.yellow(f"inbound firewall rule to allow connections on TCP port {port_setting}.")
            ASCIIColors.yellow("The 'install.bat' and 'install.ps1' scripts now attempt to do this automatically for new installations.")
            ASCIIColors.yellow("-------------------------------------------\n")
            
        import psutil
        import socket
        from backend.utils import get_accessible_host

        accessible_host = get_accessible_host()
        if accessible_host != 'localhost':
            ASCIIColors.magenta(f"Recommended public access URL: {protocol}://{accessible_host}:{port_setting}/")

        ASCIIColors.magenta(f"Or access locally at: {protocol}://localhost:{port_setting}/")

        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    if addr.address != accessible_host and addr.address != '127.0.0.1':
                        ASCIIColors.magenta(f"Also available at: {protocol}://{addr.address}:{port_setting}/")

    else:
        ASCIIColors.magenta(f"Access UI at: {protocol}://{host_setting}:{port_setting}/")
    ASCIIColors.green(f"Using {workers} Workers")
    print("----------------------")

    uvicorn.run("main:app", host=host_setting, port=port_setting, reload=False, workers=workers, timeout_keep_alive=600, **ssl_params)