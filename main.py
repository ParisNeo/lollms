# -*- coding: utf-8 -*-
# Project name: simplified_lollms
# File path: main.py
# Author: ParisNeo
# Creation date: 2025-05-08
# Description: Main FastAPI application for a multi-user LoLLMs and SafeStore
# chat service. Provides API endpoints for user authentication, discussion
# management (including starring and message grading), LLM interaction
# (via lollms-client) with enriched message metadata and multimodal support,
# RAG (via safe_store with multiple datastores), file management for RAG,
# data import/export, discussion sharing, administrative user management,
# user preferences (theme, RAG top_k), prompt management and store,
# and a friendship system for direct sharing.

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
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError
from dataclasses import dataclass, field as dataclass_field
from werkzeug.utils import secure_filename

# Local Application Imports
from database_setup import (
    User as DBUser,
    UserStarredDiscussion,
    UserMessageGrade,
    DataStore as DBDataStore,
    SharedDataStoreLink as DBSharedDataStoreLink,
    Prompt as DBPrompt, # New
    Friendship as DBFriendship, # New
    init_database,
    get_db,
    hash_password,
    DATABASE_URL_CONFIG_KEY,
)
from lollms_client import (
    LollmsClient,
    MSG_TYPE,
    LollmsDiscussion as LollmsClientDiscussion,
    ELF_COMPLETION_FORMAT, 
)

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

# --- Application Version ---
APP_VERSION = "1.6.0"  # Version update for prompts, friends, store

# --- Configuration Loading ---
CONFIG_PATH = Path("config.toml")
if not CONFIG_PATH.exists():
    EXAMPLE_CONFIG_PATH = Path("config_example.toml")
    if EXAMPLE_CONFIG_PATH.exists():
        shutil.copy(EXAMPLE_CONFIG_PATH, CONFIG_PATH)
        print(f"INFO: config.toml not found. Copied from {EXAMPLE_CONFIG_PATH}.")
    else:
        print("CRITICAL: config.toml not found and config_example.toml also missing.")
        config = {}
else:
    try: config = toml.load(CONFIG_PATH)
    except toml.TomlDecodeError as e: print(f"CRITICAL: Error parsing config.toml: {e}."); config = {}

APP_SETTINGS = config.get("app_settings", {})
APP_DATA_DIR = Path(APP_SETTINGS.get("data_dir", "data")).resolve()
APP_DB_URL = APP_SETTINGS.get(DATABASE_URL_CONFIG_KEY, "sqlite:///./data/app_main.db")
LOLLMS_CLIENT_DEFAULTS = config.get("lollms_client_defaults", {})
SAFE_STORE_DEFAULTS = config.get("safe_store_defaults", {})
INITIAL_ADMIN_USER_CONFIG = config.get("initial_admin_user", {})
SERVER_CONFIG = config.get("server", {})
DEFAULT_RAG_TOP_K = SAFE_STORE_DEFAULTS.get("default_top_k", 3) # New default from config

# --- Constants ---
TEMP_UPLOADS_DIR_NAME = "temp_uploads"
DISCUSSION_ASSETS_DIR_NAME = "discussion_assets"
DATASTORES_DIR_NAME = "safestores"
PROMPT_CATEGORIES_DEFAULT = ["General", "Coding", "Writing", "Analysis", "Creative", "Roleplay", "Education", "Custom"]

# --- Enriched Application Data Models (AppLollmsMessage, AppLollmsDiscussion) ---
# (These remain largely the same as previously provided, no structural changes needed for this update)
@dataclass
class AppLollmsMessage:
    sender: str; content: str
    id: str = dataclass_field(default_factory=lambda: str(uuid.uuid4()))
    parent_message_id: Optional[str] = None; binding_name: Optional[str] = None
    model_name: Optional[str] = None; token_count: Optional[int] = None
    image_references: Optional[List[str]] = dataclass_field(default_factory=list)
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None and k != "image_references"} | {"image_references": self.image_references or []}
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppLollmsMessage":
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})

class AppLollmsDiscussion:
    def __init__(self, lollms_client_instance: LollmsClient, discussion_id: Optional[str] = None, title: Optional[str] = None):
        self.messages: List[AppLollmsMessage] = []
        self.lollms_client: LollmsClient = lollms_client_instance
        self.discussion_id: str = discussion_id or str(uuid.uuid4())
        raw_title = title or f"New Discussion {self.discussion_id[:8]}"
        self.title: str = (raw_title[:250] + "...") if len(raw_title) > 253 else raw_title
        self.rag_datastore_id: Optional[str] = None
    def add_message(self, sender: str, content: str, parent_message_id: Optional[str] = None, binding_name: Optional[str] = None, model_name: Optional[str] = None, token_count: Optional[int] = None, image_references: Optional[List[str]] = None) -> AppLollmsMessage:
        message = AppLollmsMessage(sender=sender, content=content, parent_message_id=parent_message_id, binding_name=binding_name, model_name=model_name, token_count=token_count, image_references=image_references or [])
        self.messages.append(message); return message
    def edit_message(self, message_id: str, new_content: str) -> bool:
        for msg in self.messages:
            if msg.id == message_id:
                msg.content = new_content
                if msg.sender.lower() != self.lollms_client.user_name.lower():
                    try: msg.token_count = self.lollms_client.binding.count_tokens(new_content)
                    except Exception: msg.token_count = len(new_content) // 3
                return True
        return False
    def delete_message(self, message_id: str) -> bool:
        original_len = len(self.messages); self.messages = [msg for msg in self.messages if msg.id != message_id]; return len(self.messages) < original_len
    def _generate_title_from_messages_if_needed(self) -> None:
        is_generic_title = (self.title.startswith("New Discussion") or self.title.startswith("Imported") or self.title.startswith("Discussion ") or self.title.startswith("Sent: ") or not self.title.strip())
        if is_generic_title and self.messages:
            first_user_message = next((m for m in self.messages if m.sender.lower() == self.lollms_client.user_name.lower()), None)
            if first_user_message:
                content_to_use = first_user_message.content
                if not content_to_use and first_user_message.image_references: content_to_use = f"Image: {Path(first_user_message.image_references[0]).name}"
                if content_to_use:
                    new_title_base = content_to_use.strip().split("\n")[0]
                    max_title_len = 50
                    new_title = (new_title_base[: max_title_len - 3] + "...") if len(new_title_base) > max_title_len else new_title_base
                    if new_title: self.title = new_title
    def to_dict(self) -> Dict[str, Any]: self._generate_title_from_messages_if_needed(); return {"discussion_id": self.discussion_id, "title": self.title, "messages": [message.to_dict() for message in self.messages], "rag_datastore_id": self.rag_datastore_id}
    def save_to_disk(self, file_path: Union[str, Path]) -> None:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as file: yaml.dump(self.to_dict(), file, sort_keys=False, allow_unicode=True, Dumper=yaml.SafeDumper)
    @classmethod
    def load_from_disk(cls, lollms_client_instance: LollmsClient, file_path: Union[str, Path]) -> Optional["AppLollmsDiscussion"]:
        actual_path = Path(file_path)
        if not actual_path.exists(): print(f"WARNING: Discussion file not found: {actual_path}"); return None
        try:
            with open(actual_path, "r", encoding="utf-8") as file: data = yaml.safe_load(file)
        except Exception as e: print(f"ERROR: Could not load/parse discussion from {actual_path}: {e}"); return None
        if not isinstance(data, dict):
            disc_id_from_path = actual_path.stem
            discussion = cls(lollms_client_instance, discussion_id=disc_id_from_path, title=f"Imported {disc_id_from_path[:8]}")
            if isinstance(data, list):
                for msg_data in data:
                    if isinstance(msg_data, dict) and "sender" in msg_data and "content" in msg_data:
                        discussion.messages.append(AppLollmsMessage.from_dict(msg_data))
            discussion._generate_title_from_messages_if_needed(); return discussion
        discussion_id = data.get("discussion_id", actual_path.stem); title = data.get("title", f"Imported {discussion_id[:8]}")
        discussion = cls(lollms_client_instance, discussion_id=discussion_id, title=title); discussion.rag_datastore_id = data.get("rag_datastore_id")
        loaded_messages_data = data.get("messages", [])
        if isinstance(loaded_messages_data, list):
            for msg_data in loaded_messages_data:
                if isinstance(msg_data, dict) and "sender" in msg_data and "content" in msg_data: discussion.messages.append(AppLollmsMessage.from_dict(msg_data))
                else: print(f"WARNING: Skipping malformed message data in {actual_path}: {msg_data}")
        if (not discussion.title or discussion.title.startswith("Imported ") or discussion.title.startswith("New Discussion ") or discussion.title.startswith("Sent: ")): discussion._generate_title_from_messages_if_needed()
        return discussion
    def prepare_query_for_llm(self, current_prompt_text: str, image_paths_for_llm: Optional[List[str]], max_total_tokens: Optional[int] = None) -> str:
        lc = self.lollms_client
        if max_total_tokens is None: max_total_tokens = getattr(lc, "ctx_size", LOLLMS_CLIENT_DEFAULTS.get("ctx_size", 4096))
        client_discussion = LollmsClientDiscussion(lc)
        for app_msg in self.messages: client_discussion.add_message(sender=app_msg.sender, content=app_msg.content)
        user_prefix = f"{lc.separator_template}{lc.user_name}"; ai_prefix = f"\n{lc.separator_template}{lc.ai_name}\n"
        current_turn_formatted_text_only = f"{user_prefix}\n{current_prompt_text}{ai_prefix}"
        try: current_turn_tokens = self.lollms_client.binding.count_tokens(current_turn_formatted_text_only)
        except Exception: current_turn_tokens = len(current_turn_formatted_text_only) // 3
        tokens_for_history = max_total_tokens - current_turn_tokens; tokens_for_history = max(0, tokens_for_history)
        history_text = client_discussion.format_discussion(max_allowed_tokens=tokens_for_history)
        return f"{history_text}{user_prefix}\n{current_prompt_text}{ai_prefix}"


# --- Pydantic Models for API ---
class UserLLMParams(BaseModel):
    llm_temperature: Optional[float] = Field(None, ge=0.0, le=2.0); llm_top_k: Optional[int] = Field(None, ge=1)
    llm_top_p: Optional[float] = Field(None, ge=0.0, le=1.0); llm_repeat_penalty: Optional[float] = Field(None, ge=0.0)
    llm_repeat_last_n: Optional[int] = Field(None, ge=0)

class UserPreferences(BaseModel): # New for user settings
    theme_preference: Optional[str] = Field(None, pattern=r"^(light|dark|system)$")
    rag_top_k: Optional[int] = Field(None, ge=1, le=20) # Example range

class UserAuthDetails(UserLLMParams, UserPreferences): # Inherits from both
    username: str; is_admin: bool
    lollms_model_name: Optional[str] = None; safe_store_vectorizer: Optional[str] = None
    lollms_client_ai_name: Optional[str] = None

class UserCreateAdmin(UserLLMParams, UserPreferences): # Inherits for new user creation defaults
    username: constr(min_length=3, max_length=50); password: constr(min_length=8)
    is_admin: bool = False; lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None

class UserPasswordResetAdmin(BaseModel): new_password: constr(min_length=8)
class UserPasswordChange(BaseModel): # For user changing their own password
    current_password: str; new_password: constr(min_length=8)

class UserPublic(UserLLMParams, UserPreferences): # Inherits
    id: int; username: str; is_admin: bool
    lollms_model_name: Optional[str] = None; safe_store_vectorizer: Optional[str] = None
    model_config = {"from_attributes": True}

class DiscussionInfo(BaseModel): id: str; title: str; is_starred: bool; rag_datastore_id: Optional[str] = None
class DiscussionTitleUpdate(BaseModel): title: constr(min_length=1, max_length=255)
class DiscussionRagDatastoreUpdate(BaseModel): rag_datastore_id: Optional[str] = None
class MessageOutput(BaseModel):
    id: str; sender: str; content: str; parent_message_id: Optional[str] = None
    binding_name: Optional[str] = None; model_name: Optional[str] = None
    token_count: Optional[int] = None; image_references: List[str] = []; user_grade: int = 0
    @field_validator('user_grade', mode='before')
    def provide_default_grade(cls, value): return value if value is not None else 0
class MessageContentUpdate(BaseModel): content: str
class MessageGradeUpdate(BaseModel):
    change: int
    @field_validator('change')
    def change_must_be_one_or_minus_one(cls, value):
        if value not in [1, -1]: raise ValueError('Grade change must be 1 or -1')
        return value
class SafeStoreDocumentInfo(BaseModel): filename: str
class DiscussionExportRequest(BaseModel): discussion_ids: Optional[List[str]] = None
class ExportedMessageData(AppLollmsMessage): pass
class ExportData(BaseModel): # Updated to include prompts
    exported_by_user: str; export_timestamp: str; application_version: str
    user_settings_at_export: Dict[str, Optional[Any]]
    datastores_info: Dict[str, Any] = Field(default_factory=dict)
    discussions: List[Dict[str, Any]]
    prompts: List[Dict[str, Any]] = Field(default_factory=list) # Export owned prompts

class DiscussionImportRequest(BaseModel): discussion_ids_to_import: List[str]
class DiscussionSendRequest(BaseModel): target_username: constr(min_length=3, max_length=50)
class DataStoreBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_public_in_store: bool = False # New field
class DataStoreCreate(DataStoreBase): pass
class DataStorePublic(DataStoreBase):
    id: str; owner_username: str; created_at: datetime.datetime; updated_at: datetime.datetime
    model_config = {"from_attributes": True}
class DataStoreShareRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)
    permission_level: str = "read_query"
    @validator('permission_level')
    def permission_level_must_be_valid(cls, value):
        if value not in ["read_query"]: raise ValueError("Invalid permission level"); return value
# Prompt Models
class PromptBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    content: str
    is_public: bool = False
class PromptCreate(PromptBase): pass
class PromptUpdate(PromptBase): pass # All fields can be updated
class PromptPublic(PromptBase):
    id: int; owner_username: str
    created_at: datetime.datetime; updated_at: datetime.datetime
    model_config = {"from_attributes": True}
# Friendship Models
class FriendshipRequestCreate(BaseModel): target_username: constr(min_length=3, max_length=50)
class FriendshipPublic(BaseModel):
    id: int; friend_username: str; status: str; initiated_by_me: bool # True if current user is requester
    created_at: datetime.datetime; updated_at: datetime.datetime
    model_config = {"from_attributes": True}


# --- Global User Session Management & Locks ---
user_sessions: Dict[str, Dict[str, Any]] = {}
message_grade_lock = threading.Lock()

# --- FastAPI Application Setup ---
app = FastAPI(title="Simplified LoLLMs Chat API", description="API for multi-user LoLLMs chat with RAG, prompts, friends, and more.", version=APP_VERSION)
security = HTTPBasic()

@app.on_event("startup")
async def on_startup() -> None:
    try: APP_DATA_DIR.mkdir(parents=True, exist_ok=True); print(f"INFO: Data directory ensured at: {APP_DATA_DIR}")
    except Exception as e: print(f"CRITICAL: Failed to initialize data directory: {e}"); return
    try: init_database(APP_DB_URL); print(f"INFO: Database initialized at: {APP_DB_URL}")
    except Exception as e: print(f"CRITICAL: Failed to initialize database: {e}"); return
    db: Optional[Session] = None
    try:
        db = next(get_db())
        admin_username = INITIAL_ADMIN_USER_CONFIG.get("username"); admin_password = INITIAL_ADMIN_USER_CONFIG.get("password")
        if not admin_username or not admin_password: print("WARNING: Initial admin user not configured."); return
        existing_admin = db.query(DBUser).filter(DBUser.username == admin_username).first()
        if not existing_admin:
            new_admin = DBUser(
                username=admin_username, hashed_password=hash_password(admin_password), is_admin=True,
                lollms_model_name=LOLLMS_CLIENT_DEFAULTS.get("default_model_name"),
                safe_store_vectorizer=SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
                llm_temperature=LOLLMS_CLIENT_DEFAULTS.get("temperature"), llm_top_k=LOLLMS_CLIENT_DEFAULTS.get("top_k"),
                llm_top_p=LOLLMS_CLIENT_DEFAULTS.get("top_p"), llm_repeat_penalty=LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
                llm_repeat_last_n=LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n"),
                theme_preference='system', rag_top_k=DEFAULT_RAG_TOP_K # New defaults
            )
            db.add(new_admin); db.commit(); print(f"INFO: Initial admin user '{admin_username}' created.")
        else: print(f"INFO: Initial admin user '{admin_username}' already exists.")
    except Exception as e: print(f"ERROR: Initial admin setup failed: {e}"); traceback.print_exc()
    finally:
        if db: db.close()

# --- Path Helpers (Unchanged from previous structure) ---
def get_user_data_root(username: str) -> Path:
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    if not all(c in allowed_chars for c in username): raise HTTPException(status_code=400, detail="Invalid username format for path.")
    path = APP_DATA_DIR / username; path.mkdir(parents=True, exist_ok=True); return path
def get_user_discussion_path(username: str) -> Path: path = get_user_data_root(username) / "discussions"; path.mkdir(parents=True, exist_ok=True); return path
def get_user_discussion_assets_path(username: str) -> Path: path = get_user_data_root(username) / DISCUSSION_ASSETS_DIR_NAME; path.mkdir(parents=True, exist_ok=True); return path
def get_user_temp_uploads_path(username: str) -> Path: path = get_user_data_root(username) / TEMP_UPLOADS_DIR_NAME; path.mkdir(parents=True, exist_ok=True); return path
def get_user_datastore_root_path(username: str) -> Path: path = get_user_data_root(username) / DATASTORES_DIR_NAME; path.mkdir(parents=True, exist_ok=True); return path
def get_datastore_db_path(owner_username: str, datastore_id: str) -> Path:
    try: uuid.UUID(datastore_id)
    except ValueError: raise HTTPException(status_code=400, detail="Invalid datastore ID format.")
    return get_user_datastore_root_path(owner_username) / f"{datastore_id}.db"

# --- Authentication Dependencies ---
def get_current_db_user(credentials: HTTPBasicCredentials = Depends(security), db: Session = Depends(get_db)) -> DBUser:
    user = db.query(DBUser).filter(DBUser.username == credentials.username).first()
    if not user or not user.verify_password(credentials.password):
        raise HTTPException(status_code=401, detail="Incorrect username or password", headers={"WWW-Authenticate": "Basic"})
    return user

def get_current_active_user(db_user: DBUser = Depends(get_current_db_user)) -> UserAuthDetails:
    username = db_user.username
    if username not in user_sessions:
        print(f"INFO: Initializing session state for user: {username}")
        llm_params = {
            "temperature": db_user.llm_temperature if db_user.llm_temperature is not None else LOLLMS_CLIENT_DEFAULTS.get("temperature"),
            "top_k": db_user.llm_top_k if db_user.llm_top_k is not None else LOLLMS_CLIENT_DEFAULTS.get("top_k"),
            "top_p": db_user.llm_top_p if db_user.llm_top_p is not None else LOLLMS_CLIENT_DEFAULTS.get("top_p"),
            "repeat_penalty": db_user.llm_repeat_penalty if db_user.llm_repeat_penalty is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
            "repeat_last_n": db_user.llm_repeat_last_n if db_user.llm_repeat_last_n is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n"),
        }
        llm_params = {k: v for k, v in llm_params.items() if v is not None}
        user_sessions[username] = {
            "lollms_client": None, "safe_store_instances": {}, "discussions": {}, "discussion_titles": {},
            "active_vectorizer": db_user.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
            "lollms_model_name": db_user.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name"),
            "llm_params": llm_params,
            "theme_preference": db_user.theme_preference or 'system', # New
            "rag_top_k": db_user.rag_top_k or DEFAULT_RAG_TOP_K, # New
        }
    lc = get_user_lollms_client(username)
    ai_name = getattr(lc, "ai_name", LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant"))
    if not user_sessions[username].get("discussions"): _load_user_discussions(username)
    
    session_data = user_sessions[username]
    return UserAuthDetails(
        username=username, is_admin=db_user.is_admin,
        lollms_model_name=session_data["lollms_model_name"],
        safe_store_vectorizer=session_data["active_vectorizer"],
        lollms_client_ai_name=ai_name,
        llm_temperature=session_data["llm_params"].get("temperature"),
        llm_top_k=session_data["llm_params"].get("top_k"),
        llm_top_p=session_data["llm_params"].get("top_p"),
        llm_repeat_penalty=session_data["llm_params"].get("repeat_penalty"),
        llm_repeat_last_n=session_data["llm_params"].get("repeat_last_n"),
        theme_preference=session_data.get("theme_preference", 'system'), # New
        rag_top_k=session_data.get("rag_top_k", DEFAULT_RAG_TOP_K) # New
    )

def get_current_admin_user(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails:
    if not current_user.is_admin: raise HTTPException(status_code=403, detail="Administrator privileges required.")
    return current_user

# --- Helper Functions for User-Specific Services (LollmsClient, SafeStore, Discussions) ---
# (get_user_lollms_client, get_safe_store_instance, _load_user_discussions, get_user_discussion, save_user_discussion remain largely the same structurally)
def get_user_lollms_client(username: str) -> LollmsClient: # No major changes, uses session data
    session = user_sessions.get(username);
    if not session: raise HTTPException(status_code=500, detail="User session not found for LollmsClient.")
    force_reinit = session.get("lollms_client") is None
    current_model_name = session["lollms_model_name"]
    if not force_reinit and hasattr(session["lollms_client"], "model_name") and session["lollms_client"].model_name != current_model_name: force_reinit = True
    # Additional check for LLM params might be needed if LollmsClient takes them directly at re-init
    if force_reinit:
        client_init_params = session.get("llm_params", {}).copy()
        client_init_params.update({
            "binding_name": LOLLMS_CLIENT_DEFAULTS.get("binding_name", "lollms"), "model_name": current_model_name,
            "host_address": LOLLMS_CLIENT_DEFAULTS.get("host_address"), "ctx_size": LOLLMS_CLIENT_DEFAULTS.get("ctx_size", 4096),
            "service_key": os.getenv(LOLLMS_CLIENT_DEFAULTS.get("service_key_env_var")) if LOLLMS_CLIENT_DEFAULTS.get("service_key_env_var") else None,
            "user_name": LOLLMS_CLIENT_DEFAULTS.get("user_name", "user"), "ai_name": LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant"),
        })
        completion_format_str = LOLLMS_CLIENT_DEFAULTS.get("completion_format")
        if completion_format_str:
            try: client_init_params["completion_format"] = ELF_COMPLETION_FORMAT.from_string(completion_format_str)
            except ValueError: print(f"WARN: Invalid completion_format '{completion_format_str}' in config.")
        try: session["lollms_client"] = LollmsClient(**client_init_params)
        except Exception as e: traceback.print_exc(); raise HTTPException(status_code=500, detail=f"Could not initialize LLM Client: {str(e)}")
    return cast(LollmsClient, session["lollms_client"])

def get_safe_store_instance(requesting_user_username: str, datastore_id: str, db: Session) -> safe_store.SafeStore: # No structural changes
    if safe_store is None: raise HTTPException(status_code=501, detail="SafeStore library not installed.")
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record: raise HTTPException(status_code=404, detail=f"DataStore '{datastore_id}' not found.")
    owner_username = datastore_record.owner.username
    requesting_user_record = db.query(DBUser).filter(DBUser.username == requesting_user_username).first()
    if not requesting_user_record: raise HTTPException(status_code=404, detail="Requesting user not found.")
    is_owner = (owner_username == requesting_user_username)
    is_shared_with_requester = False
    if not is_owner:
        link = db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id, shared_with_user_id=requesting_user_record.id).first()
        if link and link.permission_level == "read_query": is_shared_with_requester = True
    if not is_owner and not is_shared_with_requester: raise HTTPException(status_code=403, detail="Access denied to this DataStore.")
    session = user_sessions.get(requesting_user_username)
    if not session: raise HTTPException(status_code=500, detail="User session not found for SafeStore access.")
    if datastore_id not in session["safe_store_instances"]:
        ss_db_path = get_datastore_db_path(owner_username, datastore_id)
        encryption_key = SAFE_STORE_DEFAULTS.get("encryption_key")
        log_level_str = SAFE_STORE_DEFAULTS.get("log_level", "INFO").upper()
        ss_log_level = getattr(SafeStoreLogLevel, log_level_str, SafeStoreLogLevel.INFO) if SafeStoreLogLevel else None
        try:
            ss_params = {"db_path": ss_db_path, "encryption_key": encryption_key}
            if ss_log_level is not None: ss_params["log_level"] = ss_log_level
            session["safe_store_instances"][datastore_id] = safe_store.SafeStore(**ss_params)
        except safe_store.ConfigurationError as e: raise HTTPException(status_code=500, detail=f"SafeStore config error for {datastore_id}: {str(e)}.")
        except Exception as e: traceback.print_exc(); raise HTTPException(status_code=500, detail=f"Could not init SafeStore for {datastore_id}: {str(e)}")
    return cast(safe_store.SafeStore, session["safe_store_instances"][datastore_id])

def _load_user_discussions(username: str) -> None: # No structural changes
    try: lc = get_user_lollms_client(username)
    except HTTPException as e: print(f"ERROR: Cannot load discussions for {username}; LollmsClient unavailable: {e.detail}"); return
    discussion_dir = get_user_discussion_path(username); session = user_sessions[username]
    session["discussions"] = {}; session["discussion_titles"] = {}; loaded_count = 0
    for file_path in discussion_dir.glob("*.yaml"):
        if file_path.name.startswith('.'): continue
        discussion_id = file_path.stem
        discussion_obj = AppLollmsDiscussion.load_from_disk(lc, file_path)
        if discussion_obj:
            discussion_obj.discussion_id = discussion_id
            session["discussions"][discussion_id] = discussion_obj; session["discussion_titles"][discussion_id] = discussion_obj.title; loaded_count += 1
        else: print(f"WARNING: Failed to load discussion from {file_path} for user {username}.")
    print(f"INFO: Loaded {loaded_count} discussions for user {username}.")

def get_user_discussion(username: str, discussion_id: str, create_if_missing: bool = False) -> Optional[AppLollmsDiscussion]: # No structural changes
    session = user_sessions.get(username);
    if not session: raise HTTPException(status_code=500, detail="User session not found.")
    if discussion_obj := session["discussions"].get(discussion_id): return discussion_obj
    try: uuid.UUID(discussion_id)
    except ValueError:
        if not create_if_missing: return None
        else: discussion_id = str(uuid.uuid4())
    safe_filename = secure_filename(f"{discussion_id}.yaml")
    if not safe_filename.endswith(".yaml") or safe_filename == ".yaml": raise HTTPException(status_code=400, detail="Invalid discussion ID format.")
    file_path = get_user_discussion_path(username) / safe_filename
    lc = get_user_lollms_client(username)
    if file_path.exists():
        if disk_obj := AppLollmsDiscussion.load_from_disk(lc, file_path):
            disk_obj.discussion_id = discussion_id; session["discussions"][discussion_id] = disk_obj; session["discussion_titles"][discussion_id] = disk_obj.title; return disk_obj
    if create_if_missing:
        new_discussion = AppLollmsDiscussion(lollms_client_instance=lc, discussion_id=discussion_id)
        session["discussions"][discussion_id] = new_discussion; session["discussion_titles"][discussion_id] = new_discussion.title
        save_user_discussion(username, discussion_id, new_discussion); return new_discussion
    return None

def save_user_discussion(username: str, discussion_id: str, discussion_obj: AppLollmsDiscussion) -> None: # No structural changes
    try: uuid.UUID(discussion_id)
    except ValueError: return
    safe_filename = secure_filename(f"{discussion_id}.yaml")
    if not safe_filename.endswith(".yaml") or safe_filename == ".yaml": return
    file_path = get_user_discussion_path(username) / safe_filename
    try:
        discussion_obj.save_to_disk(file_path)
        if username in user_sessions: user_sessions[username]["discussion_titles"][discussion_id] = discussion_obj.title
    except Exception as e: traceback.print_exc()


# --- Root and Static File Endpoints (Unchanged) ---
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index_html(request: Request) -> FileResponse:
    index_path = Path("index.html").resolve()
    if not index_path.is_file(): raise HTTPException(status_code=404, detail="index.html not found.")
    return FileResponse(index_path)
@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def serve_admin_panel_page(admin_user: UserAuthDetails = Depends(get_current_admin_user)) -> FileResponse:
    admin_html_path = Path("admin.html").resolve()
    if not admin_html_path.is_file(): raise HTTPException(status_code=404, detail="admin.html not found.")
    return FileResponse(admin_html_path)
@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    favicon_path = Path("favicon.ico").resolve()
    return FileResponse(favicon_path, media_type="image/x-icon") if favicon_path.is_file() else Response(status_code=204)
@app.get("/logo.png", include_in_schema=False)
async def logo() -> Response:
    logo_path = Path("logo.png").resolve()
    return FileResponse(logo_path, media_type="image/png") if logo_path.is_file() else Response(status_code=404)
@app.get("/user_assets/{username}/{discussion_id}/{filename}", include_in_schema=False)
async def get_discussion_asset(username: str, discussion_id: str, filename: str, current_user: UserAuthDetails = Depends(get_current_active_user)) -> FileResponse:
    if current_user.username != username: raise HTTPException(status_code=403, detail="Forbidden to access assets of another user.")
    asset_path = get_user_discussion_assets_path(username) / discussion_id / secure_filename(filename)
    if not asset_path.is_file(): raise HTTPException(status_code=404, detail="Asset not found.")
    return FileResponse(asset_path)
try:
    locales_path = Path("locales").resolve()
    if locales_path.is_dir(): app.mount("/locales", StaticFiles(directory=locales_path, html=False), name="locales")
    else: print("WARNING: 'locales' directory not found.")
except Exception as e: print(f"ERROR: Failed to mount locales directory: {e}")

# --- Authentication and User Preferences API ---
user_self_router = APIRouter(prefix="/api/users/me", tags=["User Self Management"])
auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"]) # Kept separate for /logout

@auth_router.get("/me", response_model=UserAuthDetails) # Moved here to keep /me consistent
async def get_my_details(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails: return current_user

@auth_router.post("/logout")
async def logout(response: Response, current_user: UserAuthDetails = Depends(get_current_active_user), background_tasks: BackgroundTasks = BackgroundTasks()) -> Dict[str, str]:
    username = current_user.username
    if username in user_sessions:
        temp_dir = get_user_temp_uploads_path(username)
        if temp_dir.exists(): background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)
        if "safe_store_instances" in user_sessions[username]:
            for ds_id, ss_instance in user_sessions[username]["safe_store_instances"].items():
                if hasattr(ss_instance, 'close') and callable(ss_instance.close):
                    try: background_tasks.add_task(ss_instance.close)
                    except Exception as e_ss_close: print(f"Error closing SafeStore {ds_id} for {username} on logout: {e_ss_close}")
        del user_sessions[username]
        print(f"INFO: User '{username}' session cleared. Temp files scheduled for cleanup.")
    return {"message": "Logout successful. Session cleared."}

@user_self_router.put("/password")
async def user_change_password(payload: UserPasswordChange, current_user_db: DBUser = Depends(get_current_db_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    if not current_user_db.verify_password(payload.current_password):
        raise HTTPException(status_code=400, detail="Incorrect current password.")
    current_user_db.hashed_password = hash_password(payload.new_password)
    try: db.commit(); return {"message": "Password changed successfully."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")

@user_self_router.get("/preferences", response_model=UserPreferences)
async def get_user_preferences(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserPreferences:
    return UserPreferences(theme_preference=current_user.theme_preference, rag_top_k=current_user.rag_top_k)

@user_self_router.put("/preferences")
async def update_user_preferences(preferences: UserPreferences, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username
    db_user_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not db_user_record: raise HTTPException(status_code=404, detail="User not found.")
    
    updated = False
    if preferences.theme_preference is not None and db_user_record.theme_preference != preferences.theme_preference:
        db_user_record.theme_preference = preferences.theme_preference
        user_sessions[username]["theme_preference"] = preferences.theme_preference; updated = True
    if preferences.rag_top_k is not None and db_user_record.rag_top_k != preferences.rag_top_k:
        db_user_record.rag_top_k = preferences.rag_top_k
        user_sessions[username]["rag_top_k"] = preferences.rag_top_k; updated = True
    
    if updated:
        try: db.commit(); return {"message": "Preferences updated successfully."}
        except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
    return {"message": "No changes to preferences."}

app.include_router(auth_router)
app.include_router(user_self_router)


# --- Image Upload API (Unchanged) ---
upload_router = APIRouter(prefix="/api/upload", tags=["Uploads"])
MAX_IMAGE_SIZE_MB = 10; MAX_IMAGE_UPLOADS_PER_MESSAGE = 5
@upload_router.post("/chat_image", response_model=List[Dict[str,str]])
async def upload_chat_images(files: List[UploadFile] = File(...), current_user: UserAuthDetails = Depends(get_current_active_user))) -> List[Dict[str,str]]:
    if len(files) > MAX_IMAGE_UPLOADS_PER_MESSAGE: raise HTTPException(status_code=400, detail=f"Max {MAX_IMAGE_UPLOADS_PER_MESSAGE} images.")
    username = current_user.username; temp_uploads_path = get_user_temp_uploads_path(username)
    uploaded_file_infos = []
    for file_upload in files:
        if not file_upload.content_type or not file_upload.content_type.startswith("image/"): raise HTTPException(status_code=400, detail=f"File '{file_upload.filename}' not image.")
        file_upload.file.seek(0, os.SEEK_END); file_size = file_upload.file.tell()
        if file_size > MAX_IMAGE_SIZE_MB * 1024 * 1024: raise HTTPException(status_code=413, detail=f"Image '{file_upload.filename}' > {MAX_IMAGE_SIZE_MB}MB.")
        file_upload.file.seek(0)
        s_fn_base = secure_filename(Path(file_upload.filename or "upload").stem); s_fn_ext = secure_filename(Path(file_upload.filename or ".png").suffix)
        if not s_fn_ext: s_fn_ext = ".png"
        final_filename = f"{s_fn_base}_{uuid.uuid4().hex[:8]}{s_fn_ext}"; target_file_path = temp_uploads_path / final_filename
        try:
            with open(target_file_path, "wb") as buffer: shutil.copyfileobj(file_upload.file, buffer)
            relative_server_path = f"{TEMP_UPLOADS_DIR_NAME}/{final_filename}"
            uploaded_file_infos.append({"filename": file_upload.filename, "server_path": relative_server_path})
        except Exception as e: traceback.print_exc(); raise HTTPException(status_code=500, detail=f"Could not save image '{file_upload.filename}': {str(e)}")
        finally: await file_upload.close()
    return uploaded_file_infos
app.include_router(upload_router)

# --- Discussion API (Updates for RAG top_k and friend-only send) ---
discussion_router = APIRouter(prefix="/api/discussions", tags=["Discussions"])
# (list_all_discussions, create_new_discussion, get_messages_for_discussion, update_discussion_title, update_discussion_rag_datastore, delete_specific_discussion, star_discussion, unstar_discussion, grade_discussion_message, update_discussion_message, delete_discussion_message - mostly unchanged except where noted)
@discussion_router.get("", response_model=List[DiscussionInfo])
async def list_all_discussions(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[DiscussionInfo]: # Unchanged
    username = current_user.username; user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    session_discussions = user_sessions[username].get("discussions", {})
    starred_ids = {star.discussion_id for star in db.query(UserStarredDiscussion.discussion_id).filter(UserStarredDiscussion.user_id == user_id).all()}
    return [DiscussionInfo(id=disc_id, title=disc_obj.title, is_starred=(disc_id in starred_ids), rag_datastore_id=disc_obj.rag_datastore_id) for disc_id, disc_obj in session_discussions.items()]
@discussion_router.post("", response_model=DiscussionInfo, status_code=201)
async def create_new_discussion(current_user: UserAuthDetails = Depends(get_current_active_user)) -> DiscussionInfo: # Unchanged
    username = current_user.username; discussion_id = str(uuid.uuid4())
    discussion_obj = get_user_discussion(username, discussion_id, create_if_missing=True)
    if not discussion_obj: raise HTTPException(status_code=500, detail="Failed to create new discussion.")
    return DiscussionInfo(id=discussion_id, title=discussion_obj.title, is_starred=False, rag_datastore_id=None)
@discussion_router.get("/{discussion_id}", response_model=List[MessageOutput])
async def get_messages_for_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[MessageOutput]: # Unchanged
    username = current_user.username; user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    user_grades = {g.message_id: g.grade for g in db.query(UserMessageGrade.message_id, UserMessageGrade.grade).filter(UserMessageGrade.user_id == user_id, UserMessageGrade.discussion_id == discussion_id).all()}
    messages_output = []
    for msg in discussion_obj.messages:
        full_image_refs = [f"/user_assets/{username}/{discussion_obj.discussion_id}/{Path(ref).name}" for ref in msg.image_references or []]
        messages_output.append(MessageOutput(id=msg.id, sender=msg.sender, content=msg.content, parent_message_id=msg.parent_message_id, binding_name=msg.binding_name, model_name=msg.model_name, token_count=msg.token_count, image_references=full_image_refs, user_grade=user_grades.get(msg.id, 0)))
    return messages_output
@discussion_router.put("/{discussion_id}/title", response_model=DiscussionInfo)
async def update_discussion_title(discussion_id: str, title_update: DiscussionTitleUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DiscussionInfo: # Unchanged
    username=current_user.username; user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    discussion_obj.title = title_update.title; save_user_discussion(username, discussion_id, discussion_obj)
    is_starred = db.query(UserStarredDiscussion).filter_by(user_id=user_id, discussion_id=discussion_id).first() is not None
    return DiscussionInfo(id=discussion_id, title=discussion_obj.title, is_starred=is_starred, rag_datastore_id=discussion_obj.rag_datastore_id)
@discussion_router.put("/{discussion_id}/rag_datastore", response_model=DiscussionInfo)
async def update_discussion_rag_datastore(discussion_id: str, update_payload: DiscussionRagDatastoreUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DiscussionInfo: # Unchanged
    username = current_user.username; discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    if update_payload.rag_datastore_id:
        try: get_safe_store_instance(username, update_payload.rag_datastore_id, db)
        except HTTPException as e:
            if e.status_code in [404, 403]: raise HTTPException(status_code=400, detail=f"Invalid/inaccessible RAG datastore: {update_payload.rag_datastore_id}")
            raise e
        except Exception as e_val: raise HTTPException(status_code=500, detail=f"Error validating RAG datastore: {str(e_val)}")
    discussion_obj.rag_datastore_id = update_payload.rag_datastore_id; save_user_discussion(username, discussion_id, discussion_obj)
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar();
    if not user_id: raise HTTPException(status_code=404, detail="User not found for star check.")
    is_starred = db.query(UserStarredDiscussion).filter_by(user_id=user_id, discussion_id=discussion_id).first() is not None
    return DiscussionInfo(id=discussion_id, title=discussion_obj.title, is_starred=is_starred, rag_datastore_id=discussion_obj.rag_datastore_id)
@discussion_router.delete("/{discussion_id}", status_code=200)
async def delete_specific_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()) -> Dict[str, str]: # Unchanged
    username = current_user.username;
    try: uuid.UUID(discussion_id)
    except ValueError: raise HTTPException(status_code=400, detail="Invalid discussion ID format.")
    session = user_sessions[username]
    disc_exists_session = discussion_id in session.get("discussions", {}); safe_filename = secure_filename(f"{discussion_id}.yaml")
    file_path = get_user_discussion_path(username) / safe_filename; disc_exists_disk = file_path.exists()
    if not disc_exists_session and not disc_exists_disk: raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    session.get("discussions", {}).pop(discussion_id, None); session.get("discussion_titles", {}).pop(discussion_id, None)
    if disc_exists_disk:
        try: file_path.unlink()
        except OSError as e:
            if file_path.exists(): print(f"ERROR: Failed to delete discussion file {file_path}: {e}")
    assets_path = get_user_discussion_assets_path(username) / discussion_id
    if assets_path.exists() and assets_path.is_dir(): background_tasks.add_task(shutil.rmtree, assets_path, ignore_errors=True)
    try:
        db.query(UserStarredDiscussion).filter_by(discussion_id=discussion_id).delete()
        db.query(UserMessageGrade).filter_by(discussion_id=discussion_id).delete(); db.commit()
    except Exception as e_db: db.rollback(); print(f"ERROR: Failed to delete DB entries for discussion {discussion_id}: {e_db}")
    return {"message": f"Discussion '{discussion_id}' deleted."}
@discussion_router.post("/{discussion_id}/star", status_code=201)
async def star_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]: # Unchanged
    username = current_user.username; user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    if not get_user_discussion(username, discussion_id): raise HTTPException(status_code=404, detail="Discussion not found.")
    if db.query(UserStarredDiscussion).filter_by(user_id=user_id, discussion_id=discussion_id).first(): return {"message": "Discussion already starred."}
    new_star = UserStarredDiscussion(user_id=user_id, discussion_id=discussion_id)
    try: db.add(new_star); db.commit(); return {"message": "Discussion starred."}
    except IntegrityError: db.rollback(); return {"message": "Discussion already starred (race condition)."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@discussion_router.delete("/{discussion_id}/star", status_code=200)
async def unstar_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]: # Unchanged
    username = current_user.username; user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    star_to_delete = db.query(UserStarredDiscussion).filter_by(user_id=user_id, discussion_id=discussion_id).first()
    if not star_to_delete: return {"message": "Discussion not starred."}
    try: db.delete(star_to_delete); db.commit(); return {"message": "Discussion unstarred."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@discussion_router.put("/{discussion_id}/messages/{message_id}/grade", response_model=MessageOutput)
async def grade_discussion_message(discussion_id: str, message_id: str, grade_update: MessageGradeUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> MessageOutput: # Unchanged
    username = current_user.username; user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail="Discussion not found.")
    target_message = next((msg for msg in discussion_obj.messages if msg.id == message_id), None)
    if not target_message: raise HTTPException(status_code=404, detail="Message not found.")
    lc = get_user_lollms_client(username)
    if target_message.sender == lc.user_name: raise HTTPException(status_code=400, detail="User messages cannot be graded.")
    with message_grade_lock:
        grade_record = db.query(UserMessageGrade).filter_by(user_id=user_id, discussion_id=discussion_id, message_id=message_id).first()
        if grade_record: grade_record.grade += grade_update.change
        else: grade_record = UserMessageGrade(user_id=user_id, discussion_id=discussion_id, message_id=message_id, grade=grade_update.change); db.add(grade_record)
        try: db.commit(); db.refresh(grade_record); current_user_grade = grade_record.grade
        except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error updating grade: {e}")
    full_image_refs = [f"/user_assets/{username}/{discussion_obj.discussion_id}/{Path(ref).name}" for ref in target_message.image_references or []]
    return MessageOutput(id=target_message.id, sender=target_message.sender, content=target_message.content, parent_message_id=target_message.parent_message_id, binding_name=target_message.binding_name, model_name=target_message.model_name, token_count=target_message.token_count, image_references=full_image_refs, user_grade=current_user_grade)
@discussion_router.put("/{discussion_id}/messages/{message_id}", response_model=MessageOutput)
async def update_discussion_message(discussion_id: str, message_id: str, payload: MessageContentUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> MessageOutput: # Unchanged
    username = current_user.username; user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj or not discussion_obj.edit_message(message_id, payload.content): raise HTTPException(status_code=404, detail="Message or discussion not found.")
    save_user_discussion(username, discussion_id, discussion_obj)
    updated_msg = next((m for m in discussion_obj.messages if m.id == message_id), None)
    if not updated_msg: raise HTTPException(status_code=500, detail="Error retrieving updated message.")
    user_grade = db.query(UserMessageGrade.grade).filter_by(user_id=user_id, discussion_id=discussion_id, message_id=message_id).scalar() or 0
    full_image_refs = [f"/user_assets/{username}/{discussion_obj.discussion_id}/{Path(ref).name}" for ref in updated_msg.image_references or []]
    return MessageOutput(id=updated_msg.id, sender=updated_msg.sender, content=updated_msg.content, parent_message_id=updated_msg.parent_message_id, binding_name=updated_msg.binding_name, model_name=updated_msg.model_name, token_count=updated_msg.token_count, image_references=full_image_refs, user_grade=user_grade)
@discussion_router.delete("/{discussion_id}/messages/{message_id}", status_code=200)
async def delete_discussion_message(discussion_id: str, message_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]: # Unchanged
    username = current_user.username; discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail="Discussion not found.")
    message_to_delete = next((msg for msg in discussion_obj.messages if msg.id == message_id), None)
    if not message_to_delete: raise HTTPException(status_code=404, detail="Message not found.")
    image_assets_to_delete = []
    if message_to_delete.image_references:
        disc_assets_path = get_user_discussion_assets_path(username) / discussion_id
        for ref in message_to_delete.image_references:
            asset_path = disc_assets_path / Path(ref).name
            if asset_path.is_file(): image_assets_to_delete.append(asset_path)
    if not discussion_obj.delete_message(message_id): raise HTTPException(status_code=404, detail="Message deletion failed.")
    save_user_discussion(username, discussion_id, discussion_obj)
    for asset_path in image_assets_to_delete:
        try: asset_path.unlink()
        except OSError as e: print(f"WARN: Could not delete asset {asset_path}: {e}")
    try: db.query(UserMessageGrade).filter_by(discussion_id=discussion_id, message_id=message_id).delete(); db.commit()
    except Exception as e: db.rollback(); print(f"WARN: Could not delete grades for msg {message_id}: {e}")
    return {"message": "Message deleted."}

@discussion_router.post("/{discussion_id}/chat") # Updated for RAG top_k
async def chat_in_existing_discussion(discussion_id: str, prompt: str = Form(...), image_server_paths_json: str = Form("[]"), use_rag: bool = Form(False), rag_datastore_id: Optional[str] = Form(None), parent_message_id: Optional[str] = Form(None), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()) -> StreamingResponse:
    username = current_user.username; discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    lc = get_user_lollms_client(username)
    final_image_references_for_message: List[str] = []; llm_image_paths: List[str] = []
    try: image_server_paths = json.loads(image_server_paths_json)
    except json.JSONDecodeError: raise HTTPException(status_code=400, detail="Invalid image_server_paths_json.")
    if image_server_paths:
        user_temp_uploads_path = get_user_temp_uploads_path(username)
        discussion_assets_path = get_user_discussion_assets_path(username) / discussion_id
        discussion_assets_path.mkdir(parents=True, exist_ok=True)
        for temp_rel_path in image_server_paths:
            if not temp_rel_path.startswith(TEMP_UPLOADS_DIR_NAME + "/"): print(f"WARN: Invalid temp image path: {temp_rel_path}"); continue
            image_filename = Path(temp_rel_path).name; temp_abs_path = user_temp_uploads_path / image_filename
            if temp_abs_path.is_file():
                persistent_filename = f"{uuid.uuid4().hex[:8]}_{image_filename}"; persistent_abs_path = discussion_assets_path / persistent_filename
                try:
                    shutil.move(str(temp_abs_path), str(persistent_abs_path))
                    final_image_references_for_message.append(persistent_filename); llm_image_paths.append(str(persistent_abs_path))
                except Exception as e_move: print(f"ERROR moving image {temp_abs_path} to {persistent_abs_path}: {e_move}")
            else: print(f"WARNING: Temp image file not found: {temp_abs_path}")
    user_token_count = lc.binding.count_tokens(prompt) if prompt else 0
    discussion_obj.add_message(sender=lc.user_name, content=prompt, parent_message_id=parent_message_id, token_count=user_token_count, image_references=final_image_references_for_message)
    final_prompt_for_llm = prompt
    if use_rag and safe_store:
        effective_rag_datastore_id = rag_datastore_id or discussion_obj.rag_datastore_id
        if not effective_rag_datastore_id: print(f"WARNING: RAG requested by {username} but no datastore ID provided for discussion or selected globally for user.") # Needs fix if user has a global default store preference
        if effective_rag_datastore_id:
            try:
                ss = get_safe_store_instance(username, effective_rag_datastore_id, db)
                active_vectorizer_for_store = user_sessions[username].get("active_vectorizer") # User's global default vectorizer
                # Use user's RAG top_k preference, or global default
                rag_k = current_user.rag_top_k or DEFAULT_RAG_TOP_K
                with ss: rag_results = ss.query(prompt, vectorizer_name=active_vectorizer_for_store, top_k=rag_k)
                if rag_results:
                    context_str = "\n\nRelevant context from documents:\n"; max_rag_len, current_rag_len, sources = 2000, 0, set()
                    for i, res in enumerate(rag_results):
                        chunk_text = res.get('chunk_text',''); file_name = Path(res.get('file_path','?')).name
                        if current_rag_len + len(chunk_text) > max_rag_len and i > 0: context_str += f"... (truncated {len(rag_results) - i} more results)\n"; break
                        context_str += f"{i+1}. From '{file_name}': {chunk_text}\n"; current_rag_len += len(chunk_text); sources.add(file_name)
                    final_prompt_for_llm = (f"User question: {prompt}\n\nUse the following context from ({', '.join(sorted(list(sources)))}) to answer if relevant:\n{context_str.strip()}")
            except HTTPException as e_rag_access: print(f"INFO: RAG query skipped for {username} on datastore {effective_rag_datastore_id}: {e_rag_access.detail}")
            except Exception as e: print(f"ERROR: RAG query failed for {username} on datastore {effective_rag_datastore_id}: {e}")
        else: print(f"WARNING: RAG requested by {username} but no RAG datastore selected.")
    elif use_rag and not safe_store: print(f"WARNING: RAG requested by {username} but safe_store not available.")
    
    main_loop = asyncio.get_event_loop(); stream_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
    shared_state = {"accumulated_ai_response": "", "generation_error": None, "final_message_id": None, "binding_name": None, "model_name": None}
    async def stream_generator() -> AsyncGenerator[str, None]:
        def llm_callback(chunk: str, msg_type: MSG_TYPE, params: Optional[Dict[str, Any]] = None) -> bool:
            if msg_type == MSG_TYPE.MSG_TYPE_CHUNK:
                shared_state["accumulated_ai_response"] += chunk; main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "chunk", "content": chunk}) + "\n")
            elif msg_type in (MSG_TYPE.MSG_TYPE_EXCEPTION, MSG_TYPE.MSG_TYPE_ERROR):
                err_content = f"LLM Error: {str(chunk)}"; shared_state["generation_error"] = err_content
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_content}) + "\n"); return False
            elif msg_type == MSG_TYPE.MSG_TYPE_FULL_INVISIBLE_TO_USER and params and "final_message_id" in params: shared_state["final_message_id"] = params["final_message_id"]
            elif msg_type == MSG_TYPE.MSG_TYPE_FINISHED_MESSAGE: return False
            return True
        generation_thread: Optional[threading.Thread] = None
        try:
            full_prompt_to_llm = discussion_obj.prepare_query_for_llm(final_prompt_for_llm, llm_image_paths)
            def blocking_call():
                try:
                    shared_state["binding_name"] = lc.binding.binding_name if lc.binding else "unknown"
                    shared_state["model_name"] = lc.binding.model_name if lc.binding and hasattr(lc.binding, "model_name") else session.get("lollms_model_name", "unknown")
                    lc.generate_text(prompt=full_prompt_to_llm, images=llm_image_paths, stream=True, streaming_callback=llm_callback)
                except Exception as e_gen:
                    err_msg = f"LLM generation failed: {str(e_gen)}"; shared_state["generation_error"] = err_msg
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_msg}) + "\n")
                finally: main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)
            generation_thread = threading.Thread(target=blocking_call, daemon=True); generation_thread.start()
            while True:
                item = await stream_queue.get()
                if item is None: stream_queue.task_done(); break
                yield item; stream_queue.task_done()
            if generation_thread: generation_thread.join(timeout=10)
            ai_response_content = shared_state["accumulated_ai_response"]
            ai_token_count = lc.binding.count_tokens(ai_response_content) if ai_response_content else 0
            ai_parent_id = discussion_obj.messages[-1].id if discussion_obj.messages and discussion_obj.messages[-1].sender == lc.user_name else None
            if ai_response_content and not shared_state["generation_error"]:
                ai_message = discussion_obj.add_message(sender=lc.ai_name, content=ai_response_content, parent_message_id=ai_parent_id, binding_name=shared_state.get("binding_name"), model_name=shared_state.get("model_name"), token_count=ai_token_count)
                if shared_state.get("final_message_id"): ai_message.id = shared_state["final_message_id"]
            elif shared_state["generation_error"]: discussion_obj.add_message(sender="system", content=shared_state["generation_error"], parent_message_id=ai_parent_id)
            save_user_discussion(username, discussion_id, discussion_obj)
        except Exception as e_outer:
            error_msg = f"Chat stream error: {str(e_outer)}"; traceback.print_exc()
            try: discussion_obj.add_message(sender="system", content=error_msg); save_user_discussion(username, discussion_id, discussion_obj)
            except Exception as save_err: print(f"ERROR: Failed to save discussion after outer stream error: {save_err}")
            yield json.dumps({"type": "error", "content": error_msg}) + "\n"
        finally:
            if generation_thread and generation_thread.is_alive(): print(f"WARN: LLM gen thread for {username} still alive after timeout.")
            if image_server_paths:
                user_temp_uploads_path = get_user_temp_uploads_path(username)
                for temp_rel_path in image_server_paths:
                    image_filename = Path(temp_rel_path).name; temp_abs_path = user_temp_uploads_path / image_filename
                    if temp_abs_path.exists(): background_tasks.add_task(temp_abs_path.unlink, missing_ok=True)
    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")

@discussion_router.post("/{discussion_id}/send", status_code=200) # Updated for friend-only send
async def send_discussion_to_user(discussion_id: str, send_request: DiscussionSendRequest, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    sender_username = current_user.username; target_username = send_request.target_username
    if sender_username == target_username: raise HTTPException(status_code=400, detail="Cannot send a discussion to yourself.")
    
    sender_user_db = db.query(DBUser).filter(DBUser.username == sender_username).first()
    target_user_db = db.query(DBUser).filter(DBUser.username == target_username).first()
    if not target_user_db: raise HTTPException(status_code=404, detail=f"Target user '{target_username}' not found.")
    if not sender_user_db: raise HTTPException(status_code=404, detail="Sender user not found.") # Should not happen

    # Check friendship
    friendship = db.query(DBFriendship).filter(
        ((DBFriendship.requester_id == sender_user_db.id) & (DBFriendship.addressee_id == target_user_db.id)) |
        ((DBFriendship.requester_id == target_user_db.id) & (DBFriendship.addressee_id == sender_user_db.id)),
        DBFriendship.status == 'accepted'
    ).first()
    if not friendship: raise HTTPException(status_code=403, detail=f"You are not friends with '{target_username}'. Discussion cannot be sent.")

    original_discussion_obj = get_user_discussion(sender_username, discussion_id)
    if not original_discussion_obj: raise HTTPException(status_code=404, detail=f"Original discussion '{discussion_id}' not found for sender.")
    
    if target_username not in user_sessions: # Prime target session if not active
        llm_params_target = {k: v for k, v in LOLLMS_CLIENT_DEFAULTS.items() if k in ['temperature', 'top_k', 'top_p', 'repeat_penalty', 'repeat_last_n']}
        llm_params_target = {k: v for k,v in llm_params_target.items() if v is not None}
        user_sessions[target_username] = {
            "lollms_client": None, "safe_store_instances": {}, "discussions": {}, "discussion_titles": {},
            "lollms_model_name": target_user_db.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name"),
            "llm_params": llm_params_target, "active_vectorizer": target_user_db.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
            "theme_preference": target_user_db.theme_preference or 'system', "rag_top_k": target_user_db.rag_top_k or DEFAULT_RAG_TOP_K,
        }
        _load_user_discussions(target_username)

    target_lc = get_user_lollms_client(target_username); new_discussion_id_for_target = str(uuid.uuid4())
    copied_discussion_obj = AppLollmsDiscussion(lollms_client_instance=target_lc, discussion_id=new_discussion_id_for_target, title=f"Sent by {sender_username}: {original_discussion_obj.title}")
    copied_discussion_obj.rag_datastore_id = None # RAG datastore selection is per-user/per-discussion

    sender_assets_path = get_user_discussion_assets_path(sender_username) / discussion_id
    target_assets_path = get_user_discussion_assets_path(target_username) / new_discussion_id_for_target
    if original_discussion_obj.messages and sender_assets_path.exists() and any(msg.image_references for msg in original_discussion_obj.messages):
        target_assets_path.mkdir(parents=True, exist_ok=True)

    for msg in original_discussion_obj.messages:
        new_image_refs = []
        if msg.image_references:
            for img_ref_filename in msg.image_references:
                original_asset_file = sender_assets_path / img_ref_filename
                if original_asset_file.exists():
                    new_asset_filename = f"{uuid.uuid4().hex[:8]}_{img_ref_filename}"
                    target_asset_file = target_assets_path / new_asset_filename
                    try: shutil.copy2(str(original_asset_file), str(target_asset_file)); new_image_refs.append(new_asset_filename)
                    except Exception as e_copy_asset: print(f"ERROR copying asset {original_asset_file}: {e_copy_asset}")
                else: print(f"WARN: Asset {original_asset_file} not found, skipping.")
        copied_discussion_obj.add_message(sender=msg.sender, content=msg.content, parent_message_id=msg.parent_message_id, binding_name=msg.binding_name, model_name=msg.model_name, token_count=msg.token_count, image_references=new_image_refs)
    save_user_discussion(target_username, new_discussion_id_for_target, copied_discussion_obj)
    if target_username in user_sessions: # Update target's session if active
         user_sessions[target_username]["discussions"][new_discussion_id_for_target] = copied_discussion_obj
         user_sessions[target_username]["discussion_titles"][new_discussion_id_for_target] = copied_discussion_obj.title
    return {"message": f"Discussion '{original_discussion_obj.title}' sent to friend '{target_username}'."}

@discussion_router.post("/export", response_model=ExportData) # Updated for prompts
async def export_user_data(export_request: DiscussionExportRequest, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> ExportData:
    username = current_user.username; user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    user_settings = {
        "lollms_model_name": user_db_record.lollms_model_name, "safe_store_vectorizer": user_db_record.safe_store_vectorizer,
        "llm_temperature": user_db_record.llm_temperature, "llm_top_k": user_db_record.llm_top_k, "llm_top_p": user_db_record.llm_top_p,
        "llm_repeat_penalty": user_db_record.llm_repeat_penalty, "llm_repeat_last_n": user_db_record.llm_repeat_last_n,
        "theme_preference": user_db_record.theme_preference, "rag_top_k": user_db_record.rag_top_k
    }
    owned_datastores_db = db.query(DBDataStore).filter(DBDataStore.owner_user_id == user_db_record.id).all()
    owned_ds_info = [{"id": ds.id, "name": ds.name, "description": ds.description, "is_public_in_store": ds.is_public_in_store} for ds in owned_datastores_db]
    shared_links = db.query(DBSharedDataStoreLink).options(joinedload(DBSharedDataStoreLink.datastore).joinedload(DBDataStore.owner)).filter(DBSharedDataStoreLink.shared_with_user_id == user_db_record.id).all()
    shared_ds_info = [{"id": link.datastore.id, "name": link.datastore.name, "description": link.datastore.description, "owner_username": link.datastore.owner.username, "is_public_in_store": link.datastore.is_public_in_store} for link in shared_links]
    datastores_export_info = {"owned": owned_ds_info, "shared_with_me": shared_ds_info, "safestore_library_error": None if safe_store else "SafeStore library not available on server."}
    
    if not user_sessions[username].get("discussions"): _load_user_discussions(username)
    all_user_discussions_map = user_sessions[username].get("discussions", {})
    discussions_to_export_ids = set(all_user_discussions_map.keys())
    if export_request.discussion_ids is not None: discussions_to_export_ids &= set(export_request.discussion_ids)
    user_grades_for_export = {}
    if discussions_to_export_ids:
        grades_query = db.query(UserMessageGrade.discussion_id, UserMessageGrade.message_id, UserMessageGrade.grade).filter(UserMessageGrade.user_id == user_db_record.id, UserMessageGrade.discussion_id.in_(discussions_to_export_ids)).all()
        for disc_id_db, msg_id_db, grade_db in grades_query:
            if disc_id_db not in user_grades_for_export: user_grades_for_export[disc_id_db] = {}
            user_grades_for_export[disc_id_db][msg_id_db] = grade_db
    discussions_data_list = []
    for disc_id in discussions_to_export_ids:
        disc_obj = all_user_discussions_map.get(disc_id);
        if not disc_obj: continue
        disc_dict = disc_obj.to_dict(); grades_for_this_disc = user_grades_for_export.get(disc_id, {})
        augmented_messages = []
        for msg_data in disc_dict.get("messages", []):
            msg_id_yaml = msg_data.get("id")
            if msg_id_yaml and msg_id_yaml in grades_for_this_disc: msg_data["user_grade"] = grades_for_this_disc[msg_id_yaml]
            augmented_messages.append(msg_data)
        disc_dict["messages"] = augmented_messages
        is_starred = db.query(UserStarredDiscussion).filter_by(user_id=user_db_record.id, discussion_id=disc_id).first() is not None
        disc_dict["is_starred"] = is_starred; discussions_data_list.append(disc_dict)
    
    # Export owned prompts
    owned_prompts_db = db.query(DBPrompt).filter(DBPrompt.owner_user_id == user_db_record.id).all()
    prompts_export_data = [{"id": p.id, "name": p.name, "category": p.category, "description": p.description, "content": p.content, "is_public": p.is_public} for p in owned_prompts_db]

    return ExportData(exported_by_user=username, export_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(), application_version=APP_VERSION, user_settings_at_export=user_settings, datastores_info=datastores_export_info, discussions=discussions_data_list, prompts=prompts_export_data)

@discussion_router.post("/import", status_code=200) # Updated for prompts
async def import_user_data(import_file: UploadFile = File(...), import_request_json: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    username = current_user.username; user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    try: import_request = DiscussionImportRequest.model_validate_json(import_request_json)
    except Exception as e: raise HTTPException(status_code=400, detail=f"Invalid import request format: {e}")
    if import_file.content_type != "application/json": raise HTTPException(status_code=400, detail="Invalid file type.")
    try: content = await import_file.read(); import_data = json.loads(content.decode('utf-8'))
    except Exception as e: await import_file.close(); raise HTTPException(status_code=500, detail=f"Failed to read/parse upload: {e}")
    finally: await import_file.close()
    if not isinstance(import_data, dict) or "discussions" not in import_data: raise HTTPException(status_code=400, detail="Invalid export file format (missing discussions).")
    
    imported_discussions_data = import_data.get("discussions", []); imported_prompts_data = import_data.get("prompts", [])
    if not isinstance(imported_discussions_data, list) or not isinstance(imported_prompts_data, list): raise HTTPException(status_code=400, detail="Format error: discussions or prompts not a list.")

    lc = get_user_lollms_client(username); session = user_sessions[username]
    imported_disc_count, skipped_disc_count, disc_errors = 0, 0, []
    imported_prompt_count, skipped_prompt_count, prompt_errors = 0, 0, []
    if not session.get("discussions"): _load_user_discussions(username)

    for disc_data in imported_discussions_data:
        if not isinstance(disc_data, dict) or "discussion_id" not in disc_data: skipped_disc_count += 1; disc_errors.append({"id": "Unknown", "error": "Missing ID"}); continue
        original_id = disc_data["discussion_id"]
        if original_id not in import_request.discussion_ids_to_import: continue
        try:
            new_id = str(uuid.uuid4())
            imported_obj = AppLollmsDiscussion(lc, new_id, disc_data.get("title", f"Imported {original_id[:8]}"))
            imported_obj.rag_datastore_id = disc_data.get("rag_datastore_id") # Preserve if valid for user
            messages_from_file = disc_data.get("messages", [])
            if isinstance(messages_from_file, list):
                for msg_data in messages_from_file:
                    if isinstance(msg_data, dict) and "sender" in msg_data and "content" in msg_data:
                        imported_msg = AppLollmsMessage.from_dict(msg_data); imported_msg.image_references = [] # Clear image refs
                        imported_obj.messages.append(imported_msg)
                        if (grade_val := msg_data.get("user_grade")) is not None:
                             db.add(UserMessageGrade(user_id=user_id, discussion_id=new_id, message_id=imported_msg.id, grade=grade_val))
            save_user_discussion(username, new_id, imported_obj)
            session["discussions"][new_id] = imported_obj; session["discussion_titles"][new_id] = imported_obj.title
            imported_disc_count += 1
            if disc_data.get("is_starred", False): db.add(UserStarredDiscussion(user_id=user_id, discussion_id=new_id))
        except Exception as e: skipped_disc_count += 1; disc_errors.append({"id": original_id, "error": str(e)}); traceback.print_exc()

    # Import prompts
    for prompt_data in imported_prompts_data:
        if not isinstance(prompt_data, dict) or "name" not in prompt_data or "content" not in prompt_data:
            skipped_prompt_count += 1; prompt_errors.append({"name": prompt_data.get("name", "Unknown"), "error": "Missing name or content"}); continue
        try:
            # Check for name conflict
            existing_prompt = db.query(DBPrompt).filter_by(owner_user_id=user_id, name=prompt_data["name"]).first()
            new_prompt_name = prompt_data["name"]
            if existing_prompt: new_prompt_name = f"{prompt_data['name']} (Imported {uuid.uuid4().hex[:4]})" # Make unique
            
            new_db_prompt = DBPrompt(
                owner_user_id=user_id, name=new_prompt_name,
                category=prompt_data.get("category"), description=prompt_data.get("description"),
                content=prompt_data["content"], is_public=False # Imported prompts are private by default
            )
            db.add(new_db_prompt); imported_prompt_count += 1
        except Exception as e: skipped_prompt_count += 1; prompt_errors.append({"name": prompt_data.get("name"), "error": str(e)}); traceback.print_exc()

    try: db.commit()
    except Exception as e_db: db.rollback(); disc_errors.append({"DB_COMMIT_ERROR": str(e_db)}); prompt_errors.append({"DB_COMMIT_ERROR": str(e_db)})
    return {"message": "Import finished.", "discussions": {"imported": imported_disc_count, "skipped": skipped_disc_count, "errors": disc_errors}, "prompts": {"imported": imported_prompt_count, "skipped": skipped_prompt_count, "errors": prompt_errors}}

app.include_router(discussion_router)

# --- LoLLMs Configuration API (Unchanged) ---
lollms_config_router = APIRouter(prefix="/api/config", tags=["LoLLMs Configuration"])
@lollms_config_router.get("/lollms-models", response_model=List[Dict[str, str]])
async def get_available_lollms_models(current_user: UserAuthDetails = Depends(get_current_active_user)) -> List[Dict[str, str]]:
    lc = get_user_lollms_client(current_user.username); models_set: set[str] = set()
    try:
        binding_models = lc.listModels()
        if isinstance(binding_models, list):
            for item in binding_models:
                if isinstance(item, str): models_set.add(item)
                elif isinstance(item, dict): name = item.get("name", item.get("id", item.get("model_name"))); models_set.add(name)
    except Exception as e: print(f"WARNING: Could not list models from LollmsClient: {e}")
    user_model = user_sessions[current_user.username].get("lollms_model_name"); global_default_model = LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
    if user_model: models_set.add(user_model);
    if global_default_model: models_set.add(global_default_model)
    models_set.discard(""); models_set.discard(None)
    if not models_set and lc.binding is not None and "openai" in lc.binding.binding_name.lower(): models_set.update(["gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"])
    return [{"name": name} for name in sorted(list(models_set))] if models_set else [{"name": "No models found"}]
@lollms_config_router.post("/lollms-model")
async def set_user_lollms_model(model_name: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username; user_sessions[username]["lollms_model_name"] = model_name; user_sessions[username]["lollms_client"] = None
    db_user_record = db.query(DBUser).filter(DBUser.username == username).first()
    if db_user_record:
        db_user_record.lollms_model_name = model_name
        try: db.commit()
        except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
    else: raise HTTPException(status_code=404, detail="User not found.")
    return {"message": f"Default LoLLMs model set to '{model_name}'. Client will re-initialize."}
@lollms_config_router.get("/llm-params", response_model=UserLLMParams)
async def get_user_llm_params(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserLLMParams:
    return UserLLMParams(llm_temperature=current_user.llm_temperature, llm_top_k=current_user.llm_top_k, llm_top_p=current_user.llm_top_p, llm_repeat_penalty=current_user.llm_repeat_penalty, llm_repeat_last_n=current_user.llm_repeat_last_n)
@lollms_config_router.post("/llm-params")
async def set_user_llm_params(params: UserLLMParams, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username; db_user_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not db_user_record: raise HTTPException(status_code=404, detail="User not found.")
    updated = False
    if params.llm_temperature is not None and db_user_record.llm_temperature != params.llm_temperature: db_user_record.llm_temperature = params.llm_temperature; updated = True
    if params.llm_top_k is not None and db_user_record.llm_top_k != params.llm_top_k: db_user_record.llm_top_k = params.llm_top_k; updated = True
    if params.llm_top_p is not None and db_user_record.llm_top_p != params.llm_top_p: db_user_record.llm_top_p = params.llm_top_p; updated = True
    if params.llm_repeat_penalty is not None and db_user_record.llm_repeat_penalty != params.llm_repeat_penalty: db_user_record.llm_repeat_penalty = params.llm_repeat_penalty; updated = True
    if params.llm_repeat_last_n is not None and db_user_record.llm_repeat_last_n != params.llm_repeat_last_n: db_user_record.llm_repeat_last_n = params.llm_repeat_last_n; updated = True
    if updated:
        try: db.commit()
        except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
        session_llm_params = user_sessions[username].get("llm_params", {}); session_llm_params.update(params.model_dump(exclude_unset=True))
        user_sessions[username]["llm_params"] = session_llm_params; user_sessions[username]["lollms_client"] = None 
        return {"message": "LLM parameters updated."}
    return {"message": "No changes to LLM parameters."}
app.include_router(lollms_config_router)

# --- DataStore (RAG) API (Updates for public store visibility and friend sharing) ---
datastore_router = APIRouter(prefix="/api/datastores", tags=["RAG DataStores"])
@datastore_router.post("", response_model=DataStorePublic, status_code=201) # Updated to include is_public_in_store
async def create_datastore(ds_create: DataStoreCreate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DataStorePublic:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    if db.query(DBDataStore).filter_by(owner_user_id=user_db_record.id, name=ds_create.name).first(): raise HTTPException(status_code=400, detail=f"DataStore '{ds_create.name}' already exists.")
    new_ds_db_obj = DBDataStore(owner_user_id=user_db_record.id, name=ds_create.name, description=ds_create.description, is_public_in_store=ds_create.is_public_in_store)
    try:
        db.add(new_ds_db_obj); db.commit(); db.refresh(new_ds_db_obj)
        get_safe_store_instance(current_user.username, new_ds_db_obj.id, db) # Init file
        return DataStorePublic(id=new_ds_db_obj.id, name=new_ds_db_obj.name, description=new_ds_db_obj.description, is_public_in_store=new_ds_db_obj.is_public_in_store, owner_username=current_user.username, created_at=new_ds_db_obj.created_at, updated_at=new_ds_db_obj.updated_at)
    except IntegrityError: db.rollback(); raise HTTPException(status_code=400, detail="DataStore name conflict.")
    except Exception as e: db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@datastore_router.get("", response_model=List[DataStorePublic]) # Unchanged structurally, but DBDataStore has new field
async def list_my_datastores(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[DataStorePublic]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User DB record not found.")
    owned_ds_db = db.query(DBDataStore).filter(DBDataStore.owner_user_id == user_db_record.id).order_by(DBDataStore.name).all()
    shared_links_query = db.query(DBSharedDataStoreLink, DBDataStore).join(DBDataStore, DBSharedDataStoreLink.datastore_id == DBDataStore.id).filter(DBSharedDataStoreLink.shared_with_user_id == user_db_record.id).order_by(DBDataStore.name).options(joinedload(DBSharedDataStoreLink.datastore).joinedload(DBDataStore.owner))
    shared_links_and_ds_db = shared_links_query.all()
    response_list = [DataStorePublic.model_validate(ds_db, context={"owner_username": current_user.username}) for ds_db in owned_ds_db]
    for link, ds_db in shared_links_and_ds_db:
        if not any(r.id == ds_db.id for r in response_list):
             response_list.append(DataStorePublic.model_validate(ds_db, context={"owner_username": ds_db.owner.username}))
    return response_list
@datastore_router.get("/store", response_model=List[DataStorePublic]) # New: List public datastores
async def list_public_datastores(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[DataStorePublic]:
    public_ds_db = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.is_public_in_store == True).order_by(DBDataStore.name).all()
    return [DataStorePublic.model_validate(ds_db, context={"owner_username": ds_db.owner.username}) for ds_db in public_ds_db]
@datastore_router.put("/{datastore_id}", response_model=DataStorePublic) # Updated for is_public_in_store
async def update_datastore(datastore_id: str, ds_update: DataStoreCreate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DataStorePublic: # ds_update is now DataStoreCreate
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    ds_db_obj = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    if not ds_db_obj: raise HTTPException(status_code=404, detail="DataStore not found.")
    if ds_db_obj.owner_user_id != user_db_record.id: raise HTTPException(status_code=403, detail="Only owner can update.")
    if ds_update.name != ds_db_obj.name and db.query(DBDataStore).filter(DBDataStore.owner_user_id == user_db_record.id, DBDataStore.name == ds_update.name, DBDataStore.id != datastore_id).first():
        raise HTTPException(status_code=400, detail=f"DataStore name '{ds_update.name}' already exists.")
    ds_db_obj.name = ds_update.name; ds_db_obj.description = ds_update.description; ds_db_obj.is_public_in_store = ds_update.is_public_in_store
    try:
        db.commit(); db.refresh(ds_db_obj)
        return DataStorePublic.model_validate(ds_db_obj, context={"owner_username": current_user.username})
    except Exception as e: db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@datastore_router.delete("/{datastore_id}", status_code=200) # Unchanged
async def delete_datastore(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()) -> Dict[str, str]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    ds_db_obj = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    if not ds_db_obj: raise HTTPException(status_code=404, detail="DataStore not found.")
    if ds_db_obj.owner_user_id != user_db_record.id: raise HTTPException(status_code=403, detail="Only owner can delete.")
    ds_file_path = get_datastore_db_path(current_user.username, datastore_id); ds_lock_file_path = Path(f"{ds_file_path}.lock")
    try:
        db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id).delete(synchronize_session=False)
        db.delete(ds_db_obj); db.commit()
        if current_user.username in user_sessions and datastore_id in user_sessions[current_user.username]["safe_store_instances"]:
            del user_sessions[current_user.username]["safe_store_instances"][datastore_id]
        if ds_file_path.exists(): background_tasks.add_task(ds_file_path.unlink, missing_ok=True)
        if ds_lock_file_path.exists(): background_tasks.add_task(ds_lock_file_path.unlink, missing_ok=True)
        return {"message": f"DataStore '{ds_db_obj.name}' deleted."}
    except Exception as e: db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@datastore_router.post("/{datastore_id}/add_to_my_interface", status_code=201) # New
async def add_public_datastore_to_interface(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    
    public_ds = db.query(DBDataStore).filter(DBDataStore.id == datastore_id, DBDataStore.is_public_in_store == True).first()
    if not public_ds: raise HTTPException(status_code=404, detail="Public DataStore not found or not public.")
    if public_ds.owner_user_id == user_db_record.id: raise HTTPException(status_code=400, detail="Cannot add your own datastore to interface this way.")

    existing_link = db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id, shared_with_user_id=user_db_record.id).first()
    if existing_link: return {"message": "DataStore already added to your interface."}
    
    new_link = DBSharedDataStoreLink(datastore_id=datastore_id, shared_with_user_id=user_db_record.id, permission_level="read_query")
    try: db.add(new_link); db.commit(); return {"message": f"DataStore '{public_ds.name}' added to your interface."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@datastore_router.post("/{datastore_id}/share_with_friend", status_code=201) # Renamed from /share for clarity
async def share_datastore_with_friend(datastore_id: str, share_request: DataStoreShareRequest, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db: raise HTTPException(status_code=404, detail="Owner user not found.")
    ds_to_share = db.query(DBDataStore).filter(DBDataStore.id == datastore_id, DBDataStore.owner_user_id == owner_user_db.id).first()
    if not ds_to_share: raise HTTPException(status_code=404, detail="DataStore not found or not owner.")
    target_user_db = db.query(DBUser).filter(DBUser.username == share_request.target_username).first()
    if not target_user_db: raise HTTPException(status_code=404, detail=f"Target user '{share_request.target_username}' not found.")
    if owner_user_db.id == target_user_db.id: raise HTTPException(status_code=400, detail="Cannot share with yourself.")
    
    # Check friendship
    friendship = db.query(DBFriendship).filter(
        ((DBFriendship.requester_id == owner_user_db.id) & (DBFriendship.addressee_id == target_user_db.id)) |
        ((DBFriendship.requester_id == target_user_db.id) & (DBFriendship.addressee_id == owner_user_db.id)),
        DBFriendship.status == 'accepted'
    ).first()
    if not friendship: raise HTTPException(status_code=403, detail=f"You are not friends with '{target_user_db.username}'. Cannot share datastore.")
    
    existing_link = db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id, shared_with_user_id=target_user_db.id).first()
    if existing_link:
        if existing_link.permission_level != share_request.permission_level:
            existing_link.permission_level = share_request.permission_level; db.commit()
            return {"message": f"Permission updated for user '{target_user_db.username}'."}
        return {"message": f"Already shared with '{target_user_db.username}' with this permission."}
    new_link = DBSharedDataStoreLink(datastore_id=datastore_id, shared_with_user_id=target_user_db.id, permission_level=share_request.permission_level)
    try: db.add(new_link); db.commit(); return {"message": f"DataStore '{ds_to_share.name}' shared with friend '{target_user_db.username}'."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@datastore_router.delete("/{datastore_id}/unshare_from_friend/{friend_username}", status_code=200) # Clarified endpoint
async def unshare_datastore_from_friend(datastore_id: str, friend_username: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db: raise HTTPException(status_code=404, detail="Owner user not found.")
    ds_to_unshare = db.query(DBDataStore).filter(DBDataStore.id == datastore_id, DBDataStore.owner_user_id == owner_user_db.id).first()
    if not ds_to_unshare: raise HTTPException(status_code=404, detail="DataStore not found or not owner.")
    friend_user_db = db.query(DBUser).filter(DBUser.username == friend_username).first()
    if not friend_user_db: raise HTTPException(status_code=404, detail=f"Friend user '{friend_username}' not found.")
    link_to_delete = db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id, shared_with_user_id=friend_user_db.id).first()
    if not link_to_delete: raise HTTPException(status_code=404, detail=f"DataStore not shared with '{friend_username}'.")
    try: db.delete(link_to_delete); db.commit(); return {"message": f"Unshared from '{friend_username}'."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@datastore_router.get("/{datastore_id}/shared_with", response_model=List[UserPublic]) # New
async def get_datastore_shared_with_users(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[UserPublic]:
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db: raise HTTPException(status_code=404, detail="Owner user not found.")
    ds_record = db.query(DBDataStore).filter(DBDataStore.id == datastore_id, DBDataStore.owner_user_id == owner_user_db.id).first()
    if not ds_record: raise HTTPException(status_code=404, detail="DataStore not found or you are not the owner.")
    
    links = db.query(DBSharedDataStoreLink).options(joinedload(DBSharedDataStoreLink.shared_with_user)).filter(DBSharedDataStoreLink.datastore_id == datastore_id).all()
    return [UserPublic.model_validate(link.shared_with_user) for link in links]

app.include_router(datastore_router)

# --- SafeStore File Management API (Now Per-Datastore, unchanged structurally) ---
store_files_router = APIRouter(prefix="/api/store/{datastore_id}", tags=["SafeStore RAG & File Management"])
@store_files_router.get("/vectorizers", response_model=List[Dict[str,str]])
async def list_datastore_vectorizers(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[Dict[str,str]]:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    ss = get_safe_store_instance(current_user.username, datastore_id, db)
    try:
        with ss: methods_in_db = ss.list_vectorization_methods(); possible_names = ss.list_possible_vectorizer_names()
        formatted = []; existing_names = set()
        for method_info in methods_in_db:
            name = method_info.get("method_name")
            if name: formatted.append({"name": name, "method_name": f"{name} (dim: {method_info.get('vector_dim', 'N/A')})"}); existing_names.add(name)
        for possible_name in possible_names:
            if possible_name not in existing_names:
                display_text = possible_name
                if possible_name.startswith("tfidf:"): display_text = f"{possible_name} (TF-IDF)"
                elif possible_name.startswith("st:"): display_text = f"{possible_name} (Sentence Transformer)"
                formatted.append({"name": possible_name, "method_name": display_text})
        final_list = sorted([fv for i, fv in enumerate(formatted) if fv["name"] not in {f["name"] for f in formatted[:i]}], key=lambda x: x["name"])
        return final_list
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error listing vectorizers for {datastore_id}: {e}")
@store_files_router.post("/upload-files")
async def upload_rag_documents_to_datastore(datastore_id: str, files: List[UploadFile] = File(...), vectorizer_name: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> JSONResponse:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    ds_record = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not ds_record or not user_db_record or ds_record.owner_user_id != user_db_record.id: raise HTTPException(status_code=403, detail="Only owner can upload.")
    ss = get_safe_store_instance(current_user.username, datastore_id, db)
    datastore_docs_path = get_user_datastore_root_path(current_user.username) / "safestore_docs" / datastore_id
    datastore_docs_path.mkdir(parents=True, exist_ok=True)
    processed, errors_list = [], []
    try:
        with ss: all_vectorizers = {m['method_name'] for m in ss.list_vectorization_methods()} | set(ss.list_possible_vectorizer_names())
        if not (vectorizer_name in all_vectorizers or vectorizer_name.startswith("st:") or vectorizer_name.startswith("tfidf:")): raise HTTPException(status_code=400, detail=f"Vectorizer '{vectorizer_name}' invalid.")
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error checking vectorizer: {e}")
    for file_upload in files:
        s_filename = secure_filename(file_upload.filename or f"upload_{uuid.uuid4().hex[:8]}"); target_file_path = datastore_docs_path / s_filename
        try:
            with open(target_file_path, "wb") as buffer: shutil.copyfileobj(file_upload.file, buffer)
            with ss: ss.add_document(str(target_file_path), vectorizer_name=vectorizer_name)
            processed.append(s_filename)
        except Exception as e: errors_list.append({"filename": s_filename, "error": str(e)}); target_file_path.unlink(missing_ok=True); traceback.print_exc()
        finally: await file_upload.close()
    status_code, msg = (207, "Some files processed with errors.") if errors_list and processed else (400, "Failed to process files.") if errors_list else (200, "All files processed.")
    return JSONResponse(status_code=status_code, content={"message": msg, "processed_files": processed, "errors": errors_list})
@store_files_router.get("/files", response_model=List[SafeStoreDocumentInfo])
async def list_rag_documents_in_datastore(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[SafeStoreDocumentInfo]:
    if not safe_store: return []
    ss = get_safe_store_instance(current_user.username, datastore_id, db)
    managed_docs = []
    try:
        with ss: stored_meta = ss.list_documents()
        ds_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
        if not ds_record: raise HTTPException(status_code=404, detail="Datastore metadata not found.")
        expected_docs_root_resolved = (get_user_datastore_root_path(ds_record.owner.username) / "safestore_docs" / datastore_id).resolve()
        for doc_meta in stored_meta:
            if (original_path_str := doc_meta.get("file_path")):
                try:
                    if Path(original_path_str).resolve().parent == expected_docs_root_resolved:
                        managed_docs.append(SafeStoreDocumentInfo(filename=Path(original_path_str).name))
                except Exception: pass
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error listing RAG docs: {e}")
    return sorted(managed_docs, key=lambda x: x.filename)
@store_files_router.delete("/files/{filename}")
async def delete_rag_document_from_datastore(datastore_id: str, filename: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    ds_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not ds_record or not user_db_record or ds_record.owner_user_id != user_db_record.id: raise HTTPException(status_code=403, detail="Only owner can delete.")
    s_filename = secure_filename(filename)
    if not s_filename or s_filename != filename: raise HTTPException(status_code=400, detail="Invalid filename.")
    file_to_delete_path = get_user_datastore_root_path(current_user.username) / "safestore_docs" / datastore_id / s_filename
    if not file_to_delete_path.is_file(): raise HTTPException(status_code=404, detail=f"Doc '{s_filename}' not found.")
    ss = get_safe_store_instance(current_user.username, datastore_id, db)
    try:
        with ss: ss.delete_document_by_path(str(file_to_delete_path))
        file_to_delete_path.unlink(); return {"message": f"Doc '{s_filename}' deleted."}
    except Exception as e:
        if file_to_delete_path.exists(): raise HTTPException(status_code=500, detail=f"Could not delete '{s_filename}': {e}")
        else: return {"message": f"Doc '{s_filename}' file deleted, potential DB cleanup issue."}
app.include_router(store_files_router)

# --- Prompts API (New) ---
prompts_router = APIRouter(prefix="/api/prompts", tags=["Prompts"])
@prompts_router.post("", response_model=PromptPublic, status_code=201)
async def create_prompt(prompt_data: PromptCreate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> PromptPublic:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    if db.query(DBPrompt).filter_by(owner_user_id=user_db_record.id, name=prompt_data.name).first():
        raise HTTPException(status_code=400, detail=f"Prompt name '{prompt_data.name}' already exists for this user.")
    new_db_prompt = DBPrompt(owner_user_id=user_db_record.id, **prompt_data.model_dump())
    try:
        db.add(new_db_prompt); db.commit(); db.refresh(new_db_prompt)
        return PromptPublic.model_validate(new_db_prompt, context={"owner_username": current_user.username})
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@prompts_router.get("/mine", response_model=List[PromptPublic])
async def get_my_prompts(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[PromptPublic]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    prompts_db = db.query(DBPrompt).filter(DBPrompt.owner_user_id == user_db_record.id).order_by(DBPrompt.name).all()
    return [PromptPublic.model_validate(p, context={"owner_username": current_user.username}) for p in prompts_db]
@prompts_router.get("/store", response_model=List[PromptPublic])
async def get_public_prompts_store(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[PromptPublic]:
    prompts_db = db.query(DBPrompt).options(joinedload(DBPrompt.owner)).filter(DBPrompt.is_public == True).order_by(DBPrompt.owner.has(DBUser.username == current_user.username).desc(), DBPrompt.name).all() # Show own public prompts first
    return [PromptPublic.model_validate(p, context={"owner_username": p.owner.username}) for p in prompts_db]
@prompts_router.get("/{prompt_id}", response_model=PromptPublic)
async def get_prompt_details(prompt_id: int, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> PromptPublic:
    prompt_db = db.query(DBPrompt).options(joinedload(DBPrompt.owner)).filter(DBPrompt.id == prompt_id).first()
    if not prompt_db: raise HTTPException(status_code=404, detail="Prompt not found.")
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.") # Should not happen
    if prompt_db.owner_user_id != user_db_record.id and not prompt_db.is_public:
        raise HTTPException(status_code=403, detail="Access denied to this prompt.")
    return PromptPublic.model_validate(prompt_db, context={"owner_username": prompt_db.owner.username})
@prompts_router.put("/{prompt_id}", response_model=PromptPublic)
async def update_prompt(prompt_id: int, prompt_data: PromptUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> PromptPublic:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    prompt_db = db.query(DBPrompt).filter(DBPrompt.id == prompt_id, DBPrompt.owner_user_id == user_db_record.id).first()
    if not prompt_db: raise HTTPException(status_code=404, detail="Prompt not found or not owner.")
    if prompt_data.name != prompt_db.name and db.query(DBPrompt).filter(DBPrompt.owner_user_id == user_db_record.id, DBPrompt.name == prompt_data.name, DBPrompt.id != prompt_id).first():
        raise HTTPException(status_code=400, detail=f"Prompt name '{prompt_data.name}' already exists.")
    for field, value in prompt_data.model_dump().items(): setattr(prompt_db, field, value)
    try: db.commit(); db.refresh(prompt_db); return PromptPublic.model_validate(prompt_db, context={"owner_username": current_user.username})
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@prompts_router.delete("/{prompt_id}", status_code=200)
async def delete_prompt(prompt_id: int, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    prompt_db = db.query(DBPrompt).filter(DBPrompt.id == prompt_id, DBPrompt.owner_user_id == user_db_record.id).first()
    if not prompt_db: raise HTTPException(status_code=404, detail="Prompt not found or not owner.")
    try: db.delete(prompt_db); db.commit(); return {"message": f"Prompt '{prompt_db.name}' deleted."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@prompts_router.post("/{prompt_id}/add_to_my_prompts", response_model=PromptPublic, status_code=201)
async def copy_public_prompt_to_mine(prompt_id: int, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> PromptPublic:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    public_prompt = db.query(DBPrompt).filter(DBPrompt.id == prompt_id, DBPrompt.is_public == True).first()
    if not public_prompt: raise HTTPException(status_code=404, detail="Public prompt not found.")
    if public_prompt.owner_user_id == user_db_record.id: raise HTTPException(status_code=400, detail="Cannot copy your own prompt.")
    
    new_name = public_prompt.name
    if db.query(DBPrompt).filter_by(owner_user_id=user_db_record.id, name=new_name).first():
        new_name = f"{public_prompt.name} (Copied)" # Basic conflict resolution
        if db.query(DBPrompt).filter_by(owner_user_id=user_db_record.id, name=new_name).first(): # Still conflict
            new_name = f"{public_prompt.name} (Copied {uuid.uuid4().hex[:4]})"

    copied_prompt_db = DBPrompt(
        owner_user_id=user_db_record.id, name=new_name, category=public_prompt.category,
        description=public_prompt.description, content=public_prompt.content, is_public=False
    )
    try:
        db.add(copied_prompt_db); db.commit(); db.refresh(copied_prompt_db)
        return PromptPublic.model_validate(copied_prompt_db, context={"owner_username": current_user.username})
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error copying prompt: {e}")
app.include_router(prompts_router)

# --- Friendships API (New) ---
friendships_router = APIRouter(prefix="/api/friendships", tags=["Friendships"])
def get_friendship_response(friendship_db: DBFriendship, current_user_id: int) -> FriendshipPublic:
    friend_user = friendship_db.addressee if friendship_db.requester_id == current_user_id else friendship_db.requester
    return FriendshipPublic(
        id=friendship_db.id, friend_username=friend_user.username, status=friendship_db.status,
        initiated_by_me=(friendship_db.requester_id == current_user_id),
        created_at=friendship_db.created_at, updated_at=friendship_db.updated_at
    )
@friendships_router.post("/request", response_model=FriendshipPublic)
async def send_friend_request(request_data: FriendshipRequestCreate, current_user_db: DBUser = Depends(get_current_db_user), db: Session = Depends(get_db)) -> FriendshipPublic:
    if current_user_db.username == request_data.target_username: raise HTTPException(status_code=400, detail="Cannot send friend request to yourself.")
    addressee_db = db.query(DBUser).filter(DBUser.username == request_data.target_username).first()
    if not addressee_db: raise HTTPException(status_code=404, detail=f"User '{request_data.target_username}' not found.")
    existing_friendship = db.query(DBFriendship).filter(
        ((DBFriendship.requester_id == current_user_db.id) & (DBFriendship.addressee_id == addressee_db.id)) |
        ((DBFriendship.requester_id == addressee_db.id) & (DBFriendship.addressee_id == current_user_db.id))
    ).first()
    if existing_friendship:
        if existing_friendship.status == 'pending': raise HTTPException(status_code=400, detail="Friend request already pending.")
        if existing_friendship.status == 'accepted': raise HTTPException(status_code=400, detail="Already friends.")
        if existing_friendship.status == 'declined' or existing_friendship.status.startswith('blocked'): # Allow re-request after decline/block cleanup? Or separate unblock. For now, allow.
             db.delete(existing_friendship) # Clean up old declined/blocked before new pending. This is a simplification.
    new_req = DBFriendship(requester_id=current_user_db.id, addressee_id=addressee_db.id, status='pending')
    try: db.add(new_req); db.commit(); db.refresh(new_req); return get_friendship_response(new_req, current_user_db.id)
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@friendships_router.get("/requests/incoming", response_model=List[FriendshipPublic])
async def list_incoming_friend_requests(current_user_db: DBUser = Depends(get_current_db_user), db: Session = Depends(get_db)) -> List[FriendshipPublic]:
    reqs_db = db.query(DBFriendship).options(joinedload(DBFriendship.requester)).filter(DBFriendship.addressee_id == current_user_db.id, DBFriendship.status == 'pending').all()
    return [get_friendship_response(req, current_user_db.id) for req in reqs_db]
@friendships_router.get("/requests/outgoing", response_model=List[FriendshipPublic])
async def list_outgoing_friend_requests(current_user_db: DBUser = Depends(get_current_db_user), db: Session = Depends(get_db)) -> List[FriendshipPublic]:
    reqs_db = db.query(DBFriendship).options(joinedload(DBFriendship.addressee)).filter(DBFriendship.requester_id == current_user_db.id, DBFriendship.status == 'pending').all()
    return [get_friendship_response(req, current_user_db.id) for req in reqs_db]
@friendships_router.put("/requests/{friendship_id}/accept", response_model=FriendshipPublic)
async def accept_friend_request(friendship_id: int, current_user_db: DBUser = Depends(get_current_db_user), db: Session = Depends(get_db)) -> FriendshipPublic:
    req_db = db.query(DBFriendship).options(joinedload(DBFriendship.requester)).filter(DBFriendship.id == friendship_id, DBFriendship.addressee_id == current_user_db.id, DBFriendship.status == 'pending').first()
    if not req_db: raise HTTPException(status_code=404, detail="Incoming friend request not found or not pending.")
    req_db.status = 'accepted'; req_db.updated_at = datetime.datetime.now(datetime.timezone.utc)
    try: db.commit(); db.refresh(req_db); return get_friendship_response(req_db, current_user_db.id)
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@friendships_router.put("/requests/{friendship_id}/decline", response_model=FriendshipPublic)
async def decline_friend_request(friendship_id: int, current_user_db: DBUser = Depends(get_current_db_user), db: Session = Depends(get_db)) -> FriendshipPublic:
    req_db = db.query(DBFriendship).options(joinedload(DBFriendship.requester)).filter(DBFriendship.id == friendship_id, DBFriendship.addressee_id == current_user_db.id, DBFriendship.status == 'pending').first()
    if not req_db: raise HTTPException(status_code=404, detail="Incoming friend request not found or not pending.")
    req_db.status = 'declined'; req_db.updated_at = datetime.datetime.now(datetime.timezone.utc)
    try: db.commit(); db.refresh(req_db); return get_friendship_response(req_db, current_user_db.id) # Or just return success message
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@friendships_router.delete("/requests/{friendship_id}/cancel", status_code=200)
async def cancel_outgoing_friend_request(friendship_id: int, current_user_db: DBUser = Depends(get_current_db_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    req_db = db.query(DBFriendship).filter(DBFriendship.id == friendship_id, DBFriendship.requester_id == current_user_db.id, DBFriendship.status == 'pending').first()
    if not req_db: raise HTTPException(status_code=404, detail="Outgoing friend request not found or not pending.")
    try: db.delete(req_db); db.commit(); return {"message": "Friend request cancelled."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@friendships_router.get("", response_model=List[FriendshipPublic])
async def list_friends(current_user_db: DBUser = Depends(get_current_db_user), db: Session = Depends(get_db)) -> List[FriendshipPublic]:
    friends_db = db.query(DBFriendship).options(joinedload(DBFriendship.requester), joinedload(DBFriendship.addressee)).filter(
        ((DBFriendship.requester_id == current_user_db.id) | (DBFriendship.addressee_id == current_user_db.id)),
        DBFriendship.status == 'accepted'
    ).all()
    return [get_friendship_response(f, current_user_db.id) for f in friends_db]
@friendships_router.delete("/{friend_username}", status_code=200) # Unfriend by username
async def unfriend_user(friend_username: str, current_user_db: DBUser = Depends(get_current_db_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    friend_user_db = db.query(DBUser).filter(DBUser.username == friend_username).first()
    if not friend_user_db: raise HTTPException(status_code=404, detail=f"User '{friend_username}' not found.")
    friendship_db = db.query(DBFriendship).filter(
        ((DBFriendship.requester_id == current_user_db.id) & (DBFriendship.addressee_id == friend_user_db.id)) |
        ((DBFriendship.requester_id == friend_user_db.id) & (DBFriendship.addressee_id == current_user_db.id)),
        DBFriendship.status == 'accepted'
    ).first()
    if not friendship_db: raise HTTPException(status_code=404, detail=f"You are not friends with '{friend_username}'.")
    try: db.delete(friendship_db); db.commit(); return {"message": f"Unfriended '{friend_username}'."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
app.include_router(friendships_router)

# --- Admin API (Updates for new user fields) ---
admin_router = APIRouter(prefix="/api/admin", tags=["Administration"], dependencies=[Depends(get_current_admin_user)])
@admin_router.get("/users", response_model=List[UserPublic])
async def admin_get_all_users(db: Session = Depends(get_db)) -> List[DBUser]: return db.query(DBUser).all()
@admin_router.post("/users", response_model=UserPublic, status_code=201) # Updated to include new User fields
async def admin_add_new_user(user_data: UserCreateAdmin, db: Session = Depends(get_db)) -> DBUser:
    if db.query(DBUser).filter(DBUser.username == user_data.username).first(): raise HTTPException(status_code=400, detail="Username already registered.")
    new_db_user = DBUser(
        username=user_data.username, hashed_password=hash_password(user_data.password), is_admin=user_data.is_admin,
        lollms_model_name=user_data.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name"),
        safe_store_vectorizer=user_data.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
        llm_temperature=user_data.llm_temperature if user_data.llm_temperature is not None else LOLLMS_CLIENT_DEFAULTS.get("temperature"),
        llm_top_k=user_data.llm_top_k if user_data.llm_top_k is not None else LOLLMS_CLIENT_DEFAULTS.get("top_k"),
        llm_top_p=user_data.llm_top_p if user_data.llm_top_p is not None else LOLLMS_CLIENT_DEFAULTS.get("top_p"),
        llm_repeat_penalty=user_data.llm_repeat_penalty if user_data.llm_repeat_penalty is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
        llm_repeat_last_n=user_data.llm_repeat_last_n if user_data.llm_repeat_last_n is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n"),
        theme_preference=user_data.theme_preference or 'system', # New
        rag_top_k=user_data.rag_top_k or DEFAULT_RAG_TOP_K # New
    )
    try: db.add(new_db_user); db.commit(); db.refresh(new_db_user); return new_db_user
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@admin_router.post("/users/{user_id}/reset-password") # Unchanged
async def admin_reset_user_password(user_id: int, payload: UserPasswordResetAdmin, db: Session = Depends(get_db)) -> Dict[str, str]:
    user_to_update = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_update: raise HTTPException(status_code=404, detail="User not found.")
    user_to_update.hashed_password = hash_password(payload.new_password)
    try: db.commit(); return {"message": f"Password for user '{user_to_update.username}' reset."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
@admin_router.delete("/users/{user_id}") # Unchanged (DB cascade handles new tables like Prompt, Friendship)
async def admin_remove_user(user_id: int, db: Session = Depends(get_db), current_admin: UserAuthDetails = Depends(get_current_admin_user), background_tasks: BackgroundTasks = BackgroundTasks()) -> Dict[str, str]:
    user_to_delete = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_delete: raise HTTPException(status_code=404, detail="User not found.")
    initial_admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
    if initial_admin_username and user_to_delete.username == initial_admin_username and user_to_delete.is_admin: raise HTTPException(status_code=403, detail="Initial superadmin cannot be deleted.")
    if user_to_delete.username == current_admin.username: raise HTTPException(status_code=403, detail="Admins cannot delete themselves.")
    user_data_dir_to_delete = get_user_data_root(user_to_delete.username)
    try:
        if user_to_delete.username in user_sessions: del user_sessions[user_to_delete.username]
        db.delete(user_to_delete); db.commit()
        if user_data_dir_to_delete.exists(): background_tasks.add_task(shutil.rmtree, user_data_dir_to_delete, ignore_errors=True)
        return {"message": f"User '{user_to_delete.username}' and their data deleted."}
    except Exception as e: db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB/file error during user deletion: {e}")
app.include_router(admin_router)

# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    host = SERVER_CONFIG.get("host", "127.0.0.1"); port = int(SERVER_CONFIG.get("port", 9642))
    try: APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e: print(f"CRITICAL: Could not create main data directory {APP_DATA_DIR}: {e}")
    print(f"--- Simplified LoLLMs Chat API Server (v{APP_VERSION}) ---")
    print(f"Access UI at: http://{host}:{port}/")
    print(f"Access Admin Panel at: http://{host}:{port}/admin (requires admin login)")
    print("--------------------------------------------------------------------")
    uvicorn.run("main:app", host=host, port=port, reload=False)
