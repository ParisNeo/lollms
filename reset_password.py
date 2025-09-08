# This script is a failsafe script if you loose admin password
import shutil
import datetime
import getpass
import shutil
import datetime
from pathlib import Path
from typing import Optional
import os
import subprocess
import sys
from multiprocessing import cpu_count
from urllib.parse import urlparse
from ascii_colors import ASCIIColors, trace_exception
import asyncio
import time
from filelock import FileLock, Timeout

from multipart.multipart import FormParser
FormParser.max_size = 50 * 1024 * 1024  # 50 MB

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.config import (
    APP_SETTINGS, APP_VERSION, APP_DB_URL,
    INITIAL_ADMIN_USER_CONFIG, SERVER_CONFIG,
    APPS_ZOO_ROOT_PATH, MCPS_ZOO_ROOT_PATH, PROMPTS_ZOO_ROOT_PATH, PERSONALITIES_ZOO_ROOT_PATH,
    LOLLMS_CLIENT_DEFAULTS, APP_DATA_DIR
)
from backend.db import init_database, get_db, session as db_session_module
from backend.db.models.user import User as DBUser
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.prompt import SavedPrompt as DBSavedPrompt
from backend.db.models.config import LLMBinding as DBLLMBinding
from backend.db.models.service import AppZooRepository as DBAppZooRepository, App as DBApp, MCP as DBMCP, MCPZooRepository as DBMCPZooRepository, PromptZooRepository as DBPromptZooRepository, PersonalityZooRepository as DBPersonalityZooRepository
from backend.db.models.broadcast import BroadcastMessage
from backend.db.models.fun_fact import FunFact, FunFactCategory
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
from backend.routers.tasks import tasks_router
from backend.task_manager import task_manager
from backend.ws_manager import manager
from backend.routers.help import help_router
from backend.routers.prompts import prompts_router
from backend.routers.memories import memories_router
from backend.zoo_cache import build_full_cache

import uvicorn
from backend.settings import settings
init_database(APP_DB_URL)
db = db_session_module.SessionLocal()
try:
    settings.load_from_db(db)
finally:
    db.close()

POLLING_INTERVAL = 0.1
CLEANUP_INTERVAL = 3600
MAX_MESSAGE_AGE = 24 * 3600
CLEANUP_LOCK_PATH = APP_DATA_DIR / "broadcast_cleanup.lock"

polling_task = None

init_database(APP_DB_URL)
db = db_session_module.SessionLocal()

def reset_password():
    try:
        username = input("Enter the username to update password: ").strip()
        if not username:
            print("Username cannot be empty.")
            return
        user = db.query(DBUser).filter(DBUser.username == username).first()
        if not user:
            print(f"User '{username}' not found.")
            return

        new_password = getpass.getpass("Enter the new password: ")
        confirm_password = getpass.getpass("Confirm the new password: ")

        if new_password != confirm_password:
            print("Passwords do not match.")
            return


        user.hashed_password = hash_password(new_password)
        db.commit()
        print(f"Password for user '{username}' updated successfully.")

    except Exception as e:
        db.rollback()
        print(f"Error updating password: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_password()


