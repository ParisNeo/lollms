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
SECRET_KEY = config.get("secret_key", os.environ.get("LOLLMS_SECRET_KEY","Some key"))
ACCESS_TOKEN_EXPIRE_MINUTES = config.get("access_token_expires_mintes", os.environ.get("LOLLMS_ACCESS_TOKEN_EXPIRES_MINUTES", 30))



DEFAULT_PERSONALITIES = [
    {
        "name": "Standard Assistant",
        "category": "General",
        "author": "System",
        "description": "A helpful and general-purpose AI assistant.",
        "prompt_text": "You are a helpful AI assistant. Respond clearly and concisely.",
        "is_public": True,
        "icon_base64": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iY3VycmVudENvbG9yIiBjbGFzcz0idy02IGgtNiI+CiAgPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNMTIgMmMxLjY1NyAwIDMgMS4zNDMgMyAzcy0xLjM0MyAzLTMgMy0zLTEuMzQzLTMtMyAxLjM0My0zIDMtM3ptMCA0YTUgNSAwIDEwMC0xMCA1IDUgMCAwMDQgNC45OThWMTRoLTJhMiAyIDAgMDAwIDRoMmEyIDIgMCAwMDAtNGgtMnYtLjAwMkE1LjAwMiA1LjAwMiAwIDAwMTIgNnptLTYgOGEyLjUgMi41IDAgMDAtMi41IDIuNUEyLjUgMi41IDAgMDEgMy41IDE0SDJhLjUuNSAwIDAxMC0xaDEuNWEzLjUgMy41IDAgMTE3IDBWMTNoLTJhMiAyIDAgMDAtMi0ySDZ6bTEyIDBhMi41IDIuNSAwIDAxMi41IDIuNUEyLjUgMi41IDAgMDExOC41IDE0SDIwYS41LjUgMCAwMDAtMWgtMS41YTMuNSAzLjUgMCAxMDctN1YxM2gyYTIgMiAwIDAwMi0ySDE4eiIgY2xpcC1ydWxlPSJldmVub2RkIiAvPgo8L3N2Zz4K" # Example generic icon
    },
    {
        "name": "LoLLMS",
        "category": "General",
        "author": "System",
        "description": "A helpful and general-purpose AI assistant.",
        "prompt_text": "You are LoLLMS, a helpful AI assistant. Respond clearly and concisely.",
        "is_public": True,
        "icon_base64": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iY3VycmVudENvbG9yIiBjbGFzcz0idy02IGgtNiI+CiAgPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNMTIgMmMxLjY1NyAwIDMgMS4zNDMgMyAzcy0xLjM0MyAzLTMgMy0zLTEuMzQzLTMtMyAxLjM0My0zIDMtM3ptMCA0YTUgNSAwIDEwMC0xMCA1IDUgMCAwMDQgNC45OThWMTRoLTJhMiAyIDAgMDAwIDRoMmEyIDIgMCAwMDAtNGgtMnYtLjAwMkE1LjAwMiA1LjAwMiAwIDAwMTIgNnptLTYgOGEyLjUgMi41IDAgMDAtMi41IDIuNUEyLjUgMi41IDAgMDEgMy41IDE0SDJhLjUuNSAwIDAxMC0xaDEuNWEzLjUgMy41IDAgMTE3IDBWMTNoLTJhMiAyIDAgMDAtMi0ySDZ6bTEyIDBhMi41IDIuNSAwIDAxMi41IDIuNUEyLjUgMi41IDAgMDExOC41IDE0SDIwYS41LjUgMCAwMDAtMWgtMS41YTMuNSAzLjUgMCAxMDctN1YxM2gyYTIgMiAwIDAwMi0ySDE4eiIgY2xpcC1ydWxlPSJldmVub2RkIiAvPgo8L3N2Zz4K" # Example generic icon
    },    
    {
        "name": "Funny LoLLMS",
        "category": "General",
        "author": "System",
        "description": "A helpful and general-purpose AI assistant with a touch of fun.",
        "prompt_text": "You are a helpful AI assistant with a touch of fun named Funny LoLLMS. Be funny. Respond clearly and concisely.",
        "is_public": True,
        "icon_base64": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iY3VycmVudENvbG9yIiBjbGFzcz0idy02IGgtNiI+CiAgPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNMTIgMmMxLjY1NyAwIDMgMS4zNDMgMyAzcy0xLjM0MyAzLTMgMy0zLTEuMzQzLTMtMyAxLjM0My0zIDMtM3ptMCA0YTUgNSAwIDEwMC0xMCA1IDUgMCAwMDQgNC45OThWMTRoLTJhMiAyIDAgMDAwIDRoMmEyIDIgMCAwMDAtNGgtMnYtLjAwMkE1LjAwMiA1LjAwMiAwIDAwMTIgNnptLTYgOGEyLjUgMi41IDAgMDAtMi41IDIuNUEyLjUgMi41IDAgMDEgMy41IDE0SDJhLjUuNSAwIDAxMC0xaDEuNWEzLjUgMy41IDAgMTE3IDBWMTNoLTJhMiAyIDAgMDAtMi0ySDZ6bTEyIDBhMi41IDIuNSAwIDAxMi41IDIuNUEyLjUgMi41IDAgMDExOC41IDE0SDIwYS41LjUgMCAwMDAtMWgtMS41YTMuNSAzLjUgMCAxMDctN1YxM2gyYTIgMiAwIDAwMi0ySDE4eiIgY2xpcC1ydWxlPSJldmVub2RkIiAvPgo8L3N2Zz4K" # Example generic icon
    },    
    {
        "name": "Creative Writer",
        "category": "Writing",
        "author": "System",
        "description": "An AI assistant specialized in creative writing, storytelling, and poetry.",
        "prompt_text": "You are a creative writing assistant. Help the user craft compelling narratives, poems, or scripts. Be imaginative and evocative.",
        "is_public": True,
        "icon_base64": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iY3VycmVudENvbG9yIiBjbGFzcz0idy02IGgtNiI+CiAgPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNMTUuNzUgMy43NWEzIDMgMCAwMC0zLTYgMyAzIDAgMDAtMyAzSDguMjVhMyAzIDAgMDAtMyAzdjExLjI1YTMgMyAwIDAwMyAzaDcuNWEzIDMgMCAwMDMtM1Y2Ljc1YTMgMyAwIDAwLTMtM3ptLTMgNC41YTEuNSAxLjUgMCAxMS0zIDAgMS41IDEuNSAwIDAxMyAwem0xLjM3MyA3LjE3NmExIDEgMCAwMS0xLjQxNCAxLjQxNGwtMS4xMjEtMS4xMjFhMSAxIDAgMDAtMS40MTQgMGwtMS4xMjEgMS4xMjFhMSAxIDAgMDEtMS40MTQtMS40MTRsMS4xMjEtMS4xMjFhMSAxIDAgMDExLjQxNCAwbDEuMTIxIDEuMTIxeiIgY2xpcC1ydWxlPSJldmVub2RkIiAvPgo8L3N2Zz4K" # Example pen icon
    },
    {
        "name": "Code Helper",
        "category": "Programming",
        "author": "System",
        "description": "An AI assistant for programming tasks, code generation, debugging, and explanation.",
        "prompt_text": "You are a coding assistant. Provide accurate code snippets, explain complex programming concepts, and help debug code. Prioritize correctness and clarity.",
        "is_public": True,
        "icon_base64": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iY3VycmVudENvbG9yIiBjbGFzcz0idy02IGgtNiI+CiAgPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNNy41IDYuNzVMMy43NSAxbDItMi4yNUw5Ljc1IDZMNiA5Ljc1bC0yLjI1LTJMMi4yNSA2bDMuNzUtMy43NXptOSAwbDMuNzUgMy43NWwtMy43NSAzLjc1TDE1Ljc1IDEyIDEyIDkuNzVsMi4yNS0yLjI1TDE4IDYuNzVsLTMuNzUtMy43NXptLTYuNzUgNy41bC0xLjUgMyAxLjUgMyAxLjUtMy0xLjUtM3oiIGNsaXAtcnVsZT0iZXZlbm9kZCIgLz4KPC9zdmc+Cg==" # Example code icon
    }
]
