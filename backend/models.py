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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, constr, field_validator, validator, EmailStr

class UserLLMParams(BaseModel):
    llm_temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    llm_top_k: Optional[int] = Field(None, ge=1)
    llm_top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    llm_repeat_penalty: Optional[float] = Field(None, ge=0.0)
    llm_repeat_last_n: Optional[int] = Field(None, ge=0)
    put_thoughts_in_context: Optional[bool] = False

class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    family_name: Optional[str] = None
    birth_date: Optional[datetime.date] = None # Use datetime for date fields

class UserCreate(UserBase):
    password: str

class UserAuthDetails(UserLLMParams):
    username: str
    is_admin: bool
    first_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[str] = None
    birth_date: Optional[datetime.date] = None # Using datetime.date for date only

    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None # UUID string of active personality

    # RAG parameters
    rag_top_k: Optional[int] = Field(None, ge=1)
    max_rag_len: Optional[int] = Field(None, ge=1)
    rag_n_hops: Optional[int] = Field(None, ge=0)
    rag_min_sim_percent: Optional[float] = Field(None, ge=0, le=100)
    rag_use_graph: bool = False
    rag_graph_response_type: Optional[str] = Field("chunks_summary", pattern="^(graph_only|chunks_summary|full)$")

    lollms_client_ai_name: Optional[str] = None # From LollmsClient, not a DB field

class UserCreateAdmin(UserLLMParams):
    username: constr(min_length=3, max_length=50)
    password: constr(min_length=8)
    is_admin: bool = False

    first_name: Optional[str] = Field(None, max_length=100)
    family_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255) # Consider email validation if needed
    birth_date: Optional[datetime.date] = None

    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None # Can be set on creation

    # RAG parameters
    rag_top_k: Optional[int] = Field(None, ge=1)
    max_rag_len: Optional[int] = Field(None, ge=1)
    rag_n_hops: Optional[int] = Field(None, ge=0)
    rag_min_sim_percent: Optional[float] = Field(None, ge=0, le=100)
    rag_use_graph: Optional[bool] = False # Optional on create, will default in DB
    rag_graph_response_type: Optional[str] = Field("chunks_summary", pattern="^(graph_only|chunks_summary|full)$")

class UserPasswordResetAdmin(BaseModel):
    new_password: constr(min_length=8)
    
class UserPasswordChange(BaseModel):
    current_password: str
    new_password: constr(min_length=8)
class UserPublic(UserLLMParams):
    id: int
    username: str
    is_admin: bool

    first_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[str] = None # Be cautious about exposing email publicly
    birth_date: Optional[datetime.date] = None # Also be cautious

    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None

    # RAG parameters
    rag_top_k: Optional[int] = None
    max_rag_len: Optional[int] = None
    rag_n_hops: Optional[int] = None
    rag_min_sim_percent: Optional[float] = None
    rag_use_graph: bool
    rag_graph_response_type: Optional[str] = None

    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class DiscussionInfo(BaseModel):
    id: str
    title: str
    is_starred: bool
    rag_datastore_id: Optional[str] = None # Datastore used for RAG in this discussion

class DiscussionTitleUpdate(BaseModel):
    title: constr(min_length=1, max_length=255)

class DiscussionRagDatastoreUpdate(BaseModel):
    rag_datastore_id: Optional[str] = None


class MessageOutput(BaseModel):
    id: str
    sender: str
    content: str
    parent_message_id: Optional[str] = None
    binding_name: Optional[str] = None
    model_name: Optional[str] = None
    token_count: Optional[int] = None
    sources: Optional[List[Dict]] = None
    image_references: List[str] = []
    user_grade: int = 0

    @field_validator('user_grade', mode='before')
    def provide_default_grade(cls, value):
        return value if value is not None else 0

class MessageContentUpdate(BaseModel): content: str
class MessageGradeUpdate(BaseModel):
    change: int
    @field_validator('change')
    def change_must_be_one_or_minus_one(cls, value):
        if value not in [1, -1]: raise ValueError('Grade change must be 1 or -1')
        return value

class SafeStoreDocumentInfo(BaseModel): filename: str

class DiscussionExportRequest(BaseModel): discussion_ids: Optional[List[str]] = None
class ExportData(BaseModel):
    exported_by_user: str
    export_timestamp: str
    application_version: str
    user_settings_at_export: Dict[str, Optional[Any]] # Includes LLM & RAG params, active_personality_id
    datastores_info: Dict[str, Any] = Field(default_factory=dict)
    personalities_info: Dict[str, Any] = Field(default_factory=dict) # For owned and active
    discussions: List[Dict[str, Any]]

class DiscussionImportRequest(BaseModel): discussion_ids_to_import: List[str]

class DiscussionSendRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)

# DataStore Pydantic Models
class DataStoreBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

class DataStoreCreate(DataStoreBase): pass
class DataStoreEdit(DataStoreBase):
    new_name: constr(min_length=1, max_length=100)

class DataStorePublic(DataStoreBase):
    id: str
    owner_username: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    # Add shared_with: List[str] representing usernames shared with?
    model_config = {"from_attributes": True}

class DataStoreShareRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)
    permission_level: str = "read_query" # Default, can be extended

    @validator('permission_level')
    def permission_level_must_be_valid(cls, value):
        if value not in ["read_query"]: # Extend if more levels added
            raise ValueError("Invalid permission level")
        return value



class PersonalityBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    author: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    prompt_text: str # System prompt text
    disclaimer: Optional[str] = Field(None, max_length=1000)
    script_code: Optional[str] = None # Python script
    icon_base64: Optional[str] = None # Base64 encoded image string

class PersonalityCreate(PersonalityBase):
    is_public: Optional[bool] = False # For admin to create public ones, or user to create private

class PersonalityUpdate(PersonalityBase):
    # All fields from Base are optional for update
    name: Optional[constr(min_length=1, max_length=100)] = None
    prompt_text: Optional[str] = None # Make prompt_text optional for update
    # is_public can only be changed by admin for public personalities, or user for their own
    is_public: Optional[bool] = None


class PersonalityPublic(PersonalityBase):
    id: str # UUID string
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_public: bool
    owner_username: Optional[str] = None # Username of the owner if not public/system

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    family_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255) # Consider email validation
    birth_date: Optional[datetime.date] = None

    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None # Allow setting to None or a valid ID

    # LLM Params (can be updated here too)
    llm_temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    llm_top_k: Optional[int] = Field(None, ge=1)
    llm_top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    llm_repeat_penalty: Optional[float] = Field(None, ge=0.0)
    llm_repeat_last_n: Optional[int] = Field(None, ge=0)

    # RAG parameters
    rag_top_k: Optional[int] = Field(None, ge=1)
    max_rag_len: Optional[int] = Field(None, ge=1)
    rag_n_hops: Optional[int] = Field(None, ge=0)
    rag_min_sim_percent: Optional[float] = Field(None, ge=0, le=100)
    rag_use_graph: Optional[bool] = None
    rag_graph_response_type: Optional[str] = Field(None, pattern="^(graph_only|chunks_summary|full)$")    


class FriendshipBase(BaseModel):
    pass # Might not be needed if creation is just target_username

class FriendRequestCreate(BaseModel):
    target_username: constr(min_length=3, max_length=50)

class FriendshipAction(BaseModel):
    action: str # e.g., "accept", "reject", "unfriend", "block", "unblock"

class FriendPublic(BaseModel): # Represents a friend in a list
    id: int # User ID of the friend
    username: str
    # Optional: first_name, family_name, online_status (if you implement presence)
    friendship_id: int # ID of the Friendship record
    status_with_current_user: FriendshipStatus # e.g. ACCEPTED (for friend list)
    # last_message_preview: Optional[str] = None # For friend list UI
    # unread_message_count: int = 0 # For friend list UI

    model_config = {"from_attributes": True}

class FriendshipRequestPublic(BaseModel): # Represents a pending request
    friendship_id: int
    requesting_user_id: int
    requesting_username: str
    # Optional: requesting_user_first_name, etc.
    requested_at: datetime.datetime
    status: FriendshipStatus # Should be PENDING

    model_config = {"from_attributes": True}



class DirectMessageBase(BaseModel):
    content: constr(min_length=1)
    # image_references_json: Optional[str] = None # If supporting images

class DirectMessageCreate(DirectMessageBase):
    receiver_user_id: int # Send to userid
    image_references_json: Optional[str] = None

class DirectMessagePublic(DirectMessageBase):
    id: int
    sender_id: int
    sender_username: str
    receiver_id: int
    receiver_username: str
    sent_at: datetime.datetime
    read_at: Optional[datetime.datetime] = None

    model_config = {"from_attributes": True}

class PersonalitySendRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)

