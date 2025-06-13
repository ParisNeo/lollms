# Standard Library Imports
import os
import shutil
import uuid
import json
from pathlib import Path
from typing import List, Dict, Optional, Any, cast, Union, Tuple, AsyncGenerator
import datetime
import asyncio
import threading
import traceback
import io

# Third-Party Imports
import toml
import yaml
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
    File,
    UploadFile,
    Form,
    APIRouter,
    Response,
    Query,
    BackgroundTasks
)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import (
    HTMLResponse,
    StreamingResponse,
    JSONResponse,
    FileResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, constr, field_validator, validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import (
    or_, and_ # Add this line
)
from dataclasses import dataclass, field as dataclass_field
from werkzeug.utils import secure_filename
from pydantic import BaseModel, Field, constr, field_validator, validator # Ensure these are imported
import datetime # Ensure datetime is imported


# --- Application Version ---
APP_VERSION = "1.6.0"  # Updated version for LLM param name fix
PROJECT_ROOT = Path(__file__).resolve().parent.parent 
LOCALS_DIR = PROJECT_ROOT / "locals"

# --- Configuration Loading ---
CONFIG_PATH = Path("config.toml")
if not CONFIG_PATH.exists():
    EXAMPLE_CONFIG_PATH = Path("config_example.toml")
    if EXAMPLE_CONFIG_PATH.exists():
        shutil.copy(EXAMPLE_CONFIG_PATH, CONFIG_PATH)
        print(f"INFO: config.toml not found. Copied from {EXAMPLE_CONFIG_PATH}.")
    else:
        print(
            "CRITICAL: config.toml not found and config_example.toml also missing. "
            "Please create config.toml from the example or documentation."
        )
        config = {}
else:
    try:
        config = toml.load(CONFIG_PATH)
    except toml.TomlDecodeError as e:
        print(
            f"CRITICAL: Error parsing config.toml: {e}. Please check the file for syntax errors."
        )
        config = {}
DATABASE_URL_CONFIG_KEY = "database_url"

APP_SETTINGS = config.get("app_settings", {})
APP_DATA_DIR = Path(APP_SETTINGS.get("data_dir", "data")).resolve()
APP_DB_URL = APP_SETTINGS.get(DATABASE_URL_CONFIG_KEY, "sqlite:///./data/app_main.db")

LOLLMS_CLIENT_DEFAULTS = config.get("lollms_client_defaults", {})
SAFE_STORE_DEFAULTS = config.get("safe_store_defaults", {})
INITIAL_ADMIN_USER_CONFIG = config.get("initial_admin_user", {})
SERVER_CONFIG = config.get("server", {})

# --- Constants for directory names ---
TEMP_UPLOADS_DIR_NAME = "temp_uploads"
DISCUSSION_ASSETS_DIR_NAME = "discussion_assets"
DATASTORES_DIR_NAME = "safestores"
ALGORITHM = "HS256"
SECRET_KEY = APP_SETTINGS.get("secret_key", os.environ.get("LOLLMS_SECRET_KEY","Some key"))
ACCESS_TOKEN_EXPIRE_MINUTES = APP_SETTINGS.get("access_token_expires_mintes", os.environ.get("LOLLMS_ACCESS_TOKEN_EXPIRES_MINUTES", 30))



DEFAULT_PERSONALITIES = config.get("default_personas", {})
