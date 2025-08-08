import shutil
import datetime
from pathlib import Path
from typing import Optional
import os
import subprocess
from multiprocessing import cpu_count
from urllib.parse import urlparse
from ascii_colors import ASCIIColors
from contextlib import asynccontextmanager

from multipart.multipart import FormParser
FormParser.max_size = 50 * 1024 * 1024  # 50 MB

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.config import (
    APP_SETTINGS, APP_VERSION, APP_DB_URL,
    INITIAL_ADMIN_USER_CONFIG, SERVER_CONFIG, DEFAULT_PERSONALITIES,
    APPS_ZOO_ROOT_PATH, MCPS_ZOO_ROOT_PATH, PROMPTS_ZOO_ROOT_PATH
)
from backend.db import init_database, get_db, session as db_session_module
from backend.db.models.user import User as DBUser
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.prompt import SavedPrompt as DBSavedPrompt
from backend.db.models.service import AppZooRepository as DBAppZooRepository, App as DBApp, MCP as DBMCP, MCPZooRepository as DBMCPZooRepository, PromptZooRepository as DBPromptZooRepository
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
from backend.routers.app_utils import cleanup_and_autostart_apps
from backend.routers.apps_zoo import apps_zoo_router
from backend.routers.mcps_zoo import mcps_zoo_router
from backend.routers.prompts_zoo import prompts_zoo_router
from backend.routers.tasks import tasks_router
from backend.task_manager import task_manager # Import the singleton instance

from backend.routers.help import help_router
from backend.routers.prompts import prompts_router
from backend.zoo_cache import build_full_cache

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Code to be executed on startup ---
    ASCIIColors.info("Application startup...")
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

    # --- Setup Defaults (Admin, Personalities, Repositories) ---
    ASCIIColors.yellow("--- Verifying Default Database Entries & Repositories ---")
    db_for_defaults: Optional[Session] = None
    try:
        db_for_defaults = next(get_db())
        
        # 1. Initial Admin User
        admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
        admin_password = INITIAL_ADMIN_USER_CONFIG.get("password")
        if admin_username and admin_password and not db_for_defaults.query(DBUser).filter(DBUser.username == admin_username).first():
            new_admin = DBUser(username=admin_username, hashed_password=hash_password(admin_password), is_admin=True)
            db_for_defaults.add(new_admin)
            db_for_defaults.commit()
            ASCIIColors.green(f"INFO: Initial admin user '{admin_username}' created successfully.")
        
        # 2. Default Personalities (Kept for backward compatibility)
        for default_pers_data in DEFAULT_PERSONALITIES:
            if not db_for_defaults.query(DBPersonality).filter(DBPersonality.name == default_pers_data["name"], DBPersonality.is_public == True, DBPersonality.owner_user_id == None).first():
                new_pers_data = default_pers_data.copy()
                new_pers_data['owner_user_id'] = None
                new_pers = DBPersonality(**new_pers_data)
                db_for_defaults.add(new_pers)
                db_for_defaults.commit()
                ASCIIColors.green(f"INFO: Added default public personality: '{new_pers.name}'")
        
        # 3. NEW: Hardcoded Default System Prompts
        DEFAULT_PROMPTS = [
            # Writing & Communication
            {
                "name": "Enhance Email",
                "content": """@<style>@
title: Email Style
type: str
options: Formal, Friendly & Casual, Persuasive, Direct & Concise
help: The desired tone for the email.
@</style>@
Enhance the following email draft to be more @<style>@. Refine the language, structure, and tone accordingly."""
            },
            {
                "name": "Improve Text",
                "content": """@<style>@
title: Writing Style
type: str
options: Professional, Academic, Creative, Simple & Clear
@</style>@
@<goal>@
title: Main Goal
type: text
help: e.g., 'convince the reader', 'explain a complex topic simply', 'inspire action'
@</goal>@
Revise the following text to make it more @<style>@. The main goal is to @<goal>@. Improve clarity, flow, and impact."""
            },
            {
                "name": "Translate",
                "content": """@<language>@
title: Target Language
type: str
options: English, French, Spanish, German, Italian, Chinese, Japanese, Arabic, Russian
help: The language to translate the text into.
@</language>@
Translate the text to @<language>@. Make sure your translation is accurate and natural.
If you add any comments in the translated text, please also write them in @<language>@."""
            },
            # Coding & Development
            {
                "name": "Code Syntax Check",
                "content": """@<language>@
title: Programming Language
type: str
options: Python, JavaScript, C++, Java, TypeScript, HTML, CSS, SQL
help: The programming language of the code to be checked.
@</language>@
You are a code syntax and style checker. Review the following @<language>@ code. Identify any syntax errors, potential bugs, style guide violations (like PEP 8 for Python), or areas for improvement. Provide your feedback as a list of suggestions."""
            },
            {
                "name": "Translate Code",
                "content": """@<source_language>@
title: Source Language
type: str
options: Python, JavaScript, C++, Java, C#, Go, Rust
@</source_language>@
@<target_language>@
title: Target Language
type: str
options: Python, JavaScript, C++, Java, C#, Go, Rust
@</target_language>@
@<constraints>@
title: Constraints
type: text
help: e.g., 'must be object-oriented', 'avoid external libraries', 'prioritize performance'
@</constraints>@
Translate the following code from @<source_language>@ to @<target_language>@. Adhere to the following constraints: @<constraints>@."""
            },
            # Creative & Fun
            {
                "name": "Creative Writer",
                "content": """@<genre>@
title: Genre
type: str
options: Fantasy, Science Fiction, Mystery, Horror, Romance, Comedy
@</genre>@
@<topic>@
title: Topic
type: text
help: What should the story be about? (e.g., a lost dragon, a space detective)
@</topic>@
Write a short @<genre>@ story about @<topic>@."""
            },
            {
                "name": "Poem Generator",
                "content": """@<style>@
title: Poem Style
type: str
options: Haiku, Sonnet, Free Verse, Limerick, Ballad
@</style>@
@<topic>@
title: Topic
type: text
help: What should the poem be about?
@</topic>@
Write a `@<style>@` poem about `@<topic>@`."""
            },
            # Education & Learning
            {
                "name": "Math Problem Solver",
                "content": """@<problem>@
title: Math Problem
type: text
help: Enter the math problem you want to solve.
@</problem>@
Solve the following math problem step-by-step, explaining your reasoning for each step:
@<problem>@"""
            },
            {
                "name": "Quiz Generator",
                "content": """@<num_questions>@
title: Number of Questions
type: int
help: How many questions to generate.
@</num_questions>@
@<question_type>@
title: Question Type
type: str
options: Multiple Choice, True/False, Short Answer
@</question_type>@
@<source_material>@
title: Source Material
type: text
help: Paste the text to base the quiz on.
@</source_material>@
Generate a quiz with @<num_questions>@ `@<question_type>@` questions based on the provided source material. Include a separate answer key at the end.
Source Material:
@<source_material>@"""
            }
        ]

        for default_prompt_data in DEFAULT_PROMPTS:
            if not db_for_defaults.query(DBSavedPrompt).filter(DBSavedPrompt.name == default_prompt_data["name"], DBSavedPrompt.owner_user_id.is_(None)).first():
                new_prompt = DBSavedPrompt(
                    name=default_prompt_data["name"],
                    content=default_prompt_data["content"],
                    owner_user_id=None
                )
                db_for_defaults.add(new_prompt)
                db_for_defaults.commit()
                ASCIIColors.green(f"INFO: Added default system prompt: '{new_prompt.name}'")

    except Exception as e:
        ASCIIColors.error(f"ERROR during admin/personality/prompt setup: {e}")
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
        if db_for_prompts: db_for_prompts.rollback()
    finally:
        if db_for_prompts: db_for_prompts.close()


    ASCIIColors.yellow("--- Verifying Default Database Entries Verified ---")

    build_full_cache()
    cleanup_and_autostart_apps()
    
    ASCIIColors.info("--- Startup complete. Application is ready. ---")
    yield
    # --- Code to be executed on shutdown ---
    ASCIIColors.info("--- Application shutting down. ---")


app = FastAPI(
    title="LoLLMs Platform", 
    description="API for a multi-user LoLLMs and SafeStore chat application.", 
    version=APP_VERSION,
    lifespan=lifespan
)
    
# CORS Configuration... (remains the same)
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

# Add authenticated app origins
init_database(APP_DB_URL)
db = db_session_module.SessionLocal()
try:
    sso_apps = db.query(DBApp).filter(DBApp.active == True, DBApp.authentication_type == 'lollms_sso').all()
    sso_mcps = db.query(DBMCP).filter(DBMCP.active == True, DBMCP.authentication_type == 'lollms_sso').all()
    
    sso_services = sso_apps + sso_mcps
    
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
finally:
    db.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
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
app.include_router(files_router)
app.include_router(ui_router)
app.include_router(sso_router)
app.include_router(apps_zoo_router)
app.include_router(mcps_zoo_router)
app.include_router(prompts_zoo_router)
app.include_router(tasks_router)
app.include_router(help_router)
app.include_router(prompts_router)

# UI and Assets routers
app.include_router(upload_router)
app.include_router(assets_router)
add_ui_routes(app)

if __name__ == "__main__":
    import uvicorn
    from backend.settings import settings
    init_database(APP_DB_URL)
    settings.refresh()
    host_setting = settings.get("host", host)
    port_setting = int(settings.get("port", port))
    workers = int(os.getenv("LOLLMS_WORKERS", settings.get("workers", SERVER_CONFIG.get("workers", cpu_count()))))
    
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

    print("")
    ASCIIColors.cyan(f"--- LoLLMs Plateform (v{APP_VERSION}) ---")
    protocol = "https" if ssl_params else "http"
    
    if host_setting == "0.0.0.0":
        import psutil
        import socket
        # Always include localhost
        ASCIIColors.magenta(f"Access UI at: {protocol}://localhost:{port_setting}/")

        # Get all network interfaces and IPs
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    ASCIIColors.magenta(f"Access UI at: {protocol}://{addr.address}:{port_setting}/")
        # Optionally print hostnames
        hostname = socket.gethostname()
        fqdn = socket.getfqdn()
        ASCIIColors.magenta(f"Access UI via hostname: {protocol}://{hostname}:{port_setting}/")
        if fqdn != hostname:
            ASCIIColors.magenta(f"Access UI via FQDN: {protocol}://{fqdn}:{port_setting}/")
    else:
        ASCIIColors.magenta(f"Access UI at: {protocol}://{host_setting}:{port_setting}/")
    ASCIIColors.green(f"Using {workers} Workers")
    print("----------------------")
            
    uvicorn.run("main:app", host=host_setting, port=port_setting, reload=False, workers=workers, **ssl_params)