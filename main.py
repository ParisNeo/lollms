import shutil
import datetime
from pathlib import Path
from typing import Optional
import os
from multiprocessing import cpu_count


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.config import (
    APP_SETTINGS, APP_VERSION, APP_DB_URL,
    INITIAL_ADMIN_USER_CONFIG, SERVER_CONFIG, DEFAULT_PERSONALITIES
)
from backend.db import init_database, get_db, session as db_session_module
from backend.db.models.user import User as DBUser
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.service import AppZooRepository as DBAppZooRepository
from backend.security import get_password_hash as hash_password
from backend.discussion import LegacyDiscussion
from backend.session import (
    get_user_data_root, get_user_discussion_path, user_sessions
)
from lollms_client import LollmsDataManager

from backend.routers.auth import auth_router
from backend.routers.discussion import discussion_router
from backend.routers.admin import admin_router
from backend.routers.languages import languages_router
from backend.routers.personalities import personalities_router
from backend.routers.friends import friends_router
from backend.routers.dm import dm_router
from backend.routers.stores import store_files_router, datastore_router
from backend.routers.services import apps_router, mcp_router, discussion_tools_router
from backend.routers.social import social_router
from backend.routers.users import users_router
from backend.routers.dm_ws import dm_ws_router
from backend.routers.api_keys import api_keys_router
from backend.routers.openai_v1 import openai_v1_router
from backend.routers.lollms_config import lollms_config_router
from backend.routers.files import upload_router, assets_router, files_router
from backend.routers.ui import add_ui_routes, ui_router
from backend.routers.sso import sso_router
from backend.routers.apps_management import apps_management_router
from backend.routers.tasks import tasks_router
from backend.routers.help import help_router
from backend.task_manager import task_manager # Import the singleton instance


app = FastAPI(
    title="LoLLMs Platform",
    description="API for a multi-user LoLLMs and SafeStore chat application with social features and AI hub.",
    version=APP_VERSION,
)

@app.on_event("startup")
async def on_startup() -> None:
    init_database(APP_DB_URL)
    task_manager.init_app(db_session_module.SessionLocal)
    print("Database initialized.")
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

    db_for_defaults: Optional[Session] = None
    try:
        db_for_defaults = next(get_db())
        admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
        admin_password = INITIAL_ADMIN_USER_CONFIG.get("password")
        if admin_username and admin_password and not db_for_defaults.query(DBUser).filter(DBUser.username == admin_username).first():
            new_admin = DBUser(username=admin_username, hashed_password=hash_password(admin_password), is_admin=True)
            db_for_defaults.add(new_admin)
            print(f"INFO: Initial admin user '{admin_username}' created successfully.")
        
        for default_pers_data in DEFAULT_PERSONALITIES:
            if not db_for_defaults.query(DBPersonality).filter(DBPersonality.name == default_pers_data["name"], DBPersonality.is_public == True, DBPersonality.owner_user_id == None).first():
                new_pers = DBPersonality(name=default_pers_data["name"], author=default_pers_data.get("author", "System"), description=default_pers_data.get("description"), prompt_text=default_pers_data["prompt_text"], is_public=True, owner_user_id=None, **{k:v for k,v in default_pers_data.items() if k not in ["name", "author", "description", "prompt_text"]})
                db_for_defaults.add(new_pers)
                print(f"INFO: Added default public personality: '{new_pers.name}'")
        
        repo_count = db_for_defaults.query(func.count(DBAppZooRepository.id)).scalar()
        if repo_count == 0:
            default_repo = DBAppZooRepository(
                name="Official LoLLMs Apps Zoo",
                url="https://github.com/ParisNeo/lollms_apps_zoo.git"
            )
            db_for_defaults.add(default_repo)
            print("INFO: Added default LoLLMs App Zoo repository.")

        db_for_defaults.commit()
    except Exception as e:
        if db_for_defaults: db_for_defaults.rollback()
    finally:
        if db_for_defaults: db_for_defaults.close()

# --- CORS Configuration ---
host = SERVER_CONFIG.get("host", "0.0.0.0")
port = SERVER_CONFIG.get("port", 9642)
https_enabled = SERVER_CONFIG.get("https_enabled", False)

allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

if host == "0.0.0.0":
    allowed_origins.append(f"http://localhost:{port}")
    allowed_origins.append(f"http://127.0.0.1:{port}")
    if https_enabled:
        allowed_origins.append(f"https://localhost:{port}")
        allowed_origins.append(f"https://127.0.0.1:{port}")
else:
    allowed_origins.append(f"http://{host}:{port}")
    if https_enabled:
        allowed_origins.append(f"https://{host}:{port}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(discussion_router)
app.include_router(admin_router)
app.include_router(languages_router)
app.include_router(personalities_router)
app.include_router(apps_router)
app.include_router(mcp_router)
app.include_router(discussion_tools_router)
app.include_router(store_files_router)
app.include_router(datastore_router)
app.include_router(social_router)
app.include_router(friends_router)
app.include_router(dm_router)
app.include_router(users_router)
app.include_router(dm_ws_router)
app.include_router(api_keys_router)
app.include_router(openai_v1_router)
app.include_router(lollms_config_router)
app.include_router(upload_router)
app.include_router(assets_router)
app.include_router(files_router)
app.include_router(ui_router)
app.include_router(sso_router)
app.include_router(apps_management_router)
app.include_router(tasks_router)
app.include_router(help_router)


add_ui_routes(app)

if __name__ == "__main__":
    import uvicorn
    from backend.settings import settings
    import socket
    import psutil  # Requires `pip install psutil`

    init_database(APP_DB_URL)
    
    settings.refresh()
    
    host_setting = settings.get("host", host)
    port_setting = int(settings.get("port", port))
    # Decide how many workers to run
    # Priority: env var LOLLMS_WORKERS > settings["workers"] > cpu_count()
    workers = int(os.getenv("LOLLMS_WORKERS", settings.get("workers", cpu_count())))
    ssl_params = {}
    if settings.get("https_enabled"):
        certfile = settings.get("ssl_certfile")
        keyfile = settings.get("ssl_keyfile")
        
        if certfile and keyfile and Path(certfile).is_file() and Path(keyfile).is_file():
            ssl_params["ssl_certfile"] = certfile
            ssl_params["ssl_keyfile"] = keyfile
        else:
            print("WARNING: HTTPS is enabled in settings, but the certificate or key file is missing, not found, or invalid.")
            print(f"         Certfile path: '{certfile}' (Exists: {Path(certfile).is_file()})")
            print(f"         Keyfile path: '{keyfile}' (Exists: {Path(keyfile).is_file()})")
            print("         Server will start without HTTPS to avoid crashing.")

    print(f"--- LoLLMs Plateform (v{APP_VERSION}) ---")
    protocol = "https" if ssl_params else "http"
    
    if host_setting == "0.0.0.0":
        # Always include localhost
        print(f"Access UI at: {protocol}://localhost:{port_setting}/")

        # Get all network interfaces and IPs
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    print(f"Access UI at: {protocol}://{addr.address}:{port_setting}/")
        # Optionally print hostnames
        hostname = socket.gethostname()
        fqdn = socket.getfqdn()
        print(f"Access UI via hostname: {protocol}://{hostname}:{port_setting}/")
        if fqdn != hostname:
            print(f"Access UI via FQDN: {protocol}://{fqdn}:{port_setting}/")
    else:
        print(f"Access UI at: {protocol}://{host_setting}:{port_setting}/")
            
    uvicorn.run("main:app", host=host_setting, port=port_setting, reload=False, workers=workers, **ssl_params)
