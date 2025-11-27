# This script is a failsafe script if you loose admin password
import getpass
import shutil
import datetime

from multipart.multipart import FormParser
FormParser.max_size = 50 * 1024 * 1024  # 50 MB


from backend.config import (
    APP_DB_URL, APP_DATA_DIR
)
from backend.db import init_database, get_db, session as db_session_module
from backend.db.models.user import User as DBUser
from backend.db.models.social import Post
from backend.security import get_password_hash as hash_password
from backend.settings import settings
from backend.db import init_database, get_db, session as db_session_module
from backend.db.base import Base
from backend.db.migration import run_schema_migrations_and_bootstrap, check_and_update_db_version
from backend.db.models.user import User as DBUser
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.prompt import SavedPrompt as DBSavedPrompt
from backend.db.models.config import LLMBinding as DBLLMBinding
from backend.db.models.service import AppZooRepository as DBAppZooRepository, App as DBApp, MCP as DBMCP, MCPZooRepository as DBMCPZooRepository, PromptZooRepository as DBPromptZooRepository, PersonalityZooRepository as DBPersonalityZooRepository
from backend.db.models.connections import WebSocketConnection
from backend.security import get_password_hash as hash_password
from backend.migration_utils import LegacyDiscussion
from backend.db.models.api_key import OpenAIAPIKey as DBAPIKey
from backend.db.models.datastore import DataStore as DBDataStore, SharedDataStoreLink as DBSharedDataStoreLink

from backend.db.models.personality import Personality as DBPersonality
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


