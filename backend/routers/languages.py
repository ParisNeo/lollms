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

from backend.database_setup import Personality as DBPersonality # Add this import at the top of main.py

# Local Application Imports
from backend.database_setup import (
    User as DBUser,
    UserStarredDiscussion,
    UserMessageGrade,
    FriendshipStatus,Friendship, 
    DataStore as DBDataStore,
    SharedDataStoreLink as DBSharedDataStoreLink,
    init_database,
    get_db,
    hash_password,
    DATABASE_URL_CONFIG_KEY,
)
from lollms_client import (
    LollmsClient,
    MSG_TYPE,
    LollmsDiscussion as LollmsClientDiscussion,
    ELF_COMPLETION_FORMAT, # For client params
)

# safe_store is expected to be installed
try:
    import safe_store
    from safe_store import (
        LogLevel as SafeStoreLogLevel,
    )
except ImportError:
    print(
        "WARNING: safe_store library not found. RAG features will be disabled. Install with: pip install safe_store[all]"
    )
    safe_store = None
    SafeStoreLogLevel = None

# --- Pydantic Models for API ---
from backend.models import (
UserLLMParams,
UserAuthDetails,
UserCreateAdmin,
UserPasswordResetAdmin,UserPasswordChange,
UserPublic,
DiscussionInfo,
DiscussionTitleUpdate,
DiscussionRagDatastoreUpdate,MessageOutput,
MessageContentUpdate,
MessageGradeUpdate,
SafeStoreDocumentInfo,
DiscussionExportRequest,
ExportData,
DiscussionImportRequest,
DiscussionSendRequest,
DataStoreBase,
DataStoreCreate,
DataStorePublic,
DataStoreShareRequest,
PersonalityBase,
PersonalityCreate,
PersonalityUpdate,
PersonalityPublic,
UserUpdate,
FriendshipBase,
FriendRequestCreate,
FriendshipAction,
FriendPublic,
FriendshipRequestPublic,
PersonalitySendRequest,

DirectMessagePublic,
DirectMessageCreate
)
from backend.config import (
    TEMP_UPLOADS_DIR_NAME,
    LOCALS_DIR
)
from backend.session import (
    get_current_active_user,
    get_current_admin_user,
    get_current_db_user,
    get_datastore_db_path,
    get_db, get_safe_store_instance,
    get_user_data_root, get_user_datastore_root_path,
    get_user_discussion, get_user_discussion_assets_path,
    get_user_discussion_path,
    get_user_lollms_client,
    get_user_temp_uploads_path,
    _load_user_discussions,
    save_user_discussion,
    
    message_grade_lock,
    user_sessions,
    )
from backend.config import (LOLLMS_CLIENT_DEFAULTS, SAFE_STORE_DEFAULTS)
from backend.discussion import (AppLollmsDiscussion)

security = HTTPBasic()



languages_router = APIRouter(prefix="/api/languages", tags=["Languages router"])
@languages_router.get("/", response_class=JSONResponse)
async def get_languages():
    languages = {}
    if not LOCALS_DIR.is_dir():
        print(f"Warning: Locals directory not found at {LOCALS_DIR}")
        return {"en": "English", "fr": "Français"}

    try:
        for filepath in LOCALS_DIR.glob("*.json"):
            lang_code = filepath.stem  
            display_name = lang_code.upper()
            if lang_code == "en": display_name = "English"
            elif lang_code == "fr": display_name = "Français"
            elif lang_code == "es": display_name = "Español"
            elif lang_code == "de": display_name = "Deutsch"
            languages[lang_code] = display_name
    except Exception as e:
        print(f"Error scanning locals directory: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve language list.")

    if not languages: 
        print(f"Warning: No JSON language files found in {LOCALS_DIR}")
        return {"en": "English"} 

    return languages

@languages_router.get("/locals/{lang_code}.json")
async def get_locale_file(lang_code: str):
    if not LOCALS_DIR.is_dir():
        raise HTTPException(status_code=404, detail=f"Locals directory not found.")

    if not lang_code.replace('-', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid language code format.")

    file_path = LOCALS_DIR / f"{lang_code}.json"

    if not file_path.is_file():
        base_lang_code = lang_code.split('-')[0]
        if base_lang_code != lang_code:
            base_file_path = LOCALS_DIR / f"{base_lang_code}.json"
            if base_file_path.is_file():
                print(f"Serving base language file {base_file_path} for requested {file_path}")
                try:
                    with open(base_file_path, "r", encoding="utf-8") as f: content = json.load(f)
                    return JSONResponse(content=content)
                except Exception as e:
                    print(f"Error reading base locale file {base_file_path}: {e}")
                    raise HTTPException(status_code=500, detail="Error reading locale file.")
        raise HTTPException(status_code=404, detail=f"Locale file for '{lang_code}' not found.")

    try:
        with open(file_path, "r", encoding="utf-8") as f: content = json.load(f)
        return JSONResponse(content=content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Locale file '{lang_code}.json' is not valid JSON.")
    except Exception as e:
        print(f"Error reading locale file {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Error reading locale file.")
