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
    llm_ctx_size: Optional[int] = Field(None, ge=0)
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
    birth_date: Optional[datetime.date] = None

class UserCreate(UserBase):
    password: str

class UserAuthDetails(UserLLMParams):
    username: str
    is_admin: bool
    first_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[str] = None
    birth_date: Optional[datetime.date] = None

    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None

    rag_top_k: Optional[int] = Field(None, ge=1)
    max_rag_len: Optional[int] = Field(None, ge=1)
    rag_n_hops: Optional[int] = Field(None, ge=1)
    rag_min_sim_percent: Optional[float] = Field(None, ge=0, le=100)
    rag_use_graph: bool = False
    rag_graph_response_type: Optional[str] = Field("chunks_summary", pattern="^(graph_only|chunks_summary|full)$")

    lollms_client_ai_name: Optional[str] = None

class UserCreateAdmin(UserLLMParams):
    username: constr(min_length=3, max_length=50)
    password: constr(min_length=8)
    is_admin: bool = False

    first_name: Optional[str] = Field(None, max_length=100)
    family_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    birth_date: Optional[datetime.date] = None

    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None

    rag_top_k: Optional[int] = Field(None, ge=1)
    max_rag_len: Optional[int] = Field(None, ge=1)
    rag_n_hops: Optional[int] = Field(None, ge=1)
    rag_min_sim_percent: Optional[float] = Field(None, ge=0, le=100)
    rag_use_graph: Optional[bool] = False
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
    email: Optional[str] = None
    birth_date: Optional[datetime.date] = None

    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None

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
    rag_datastore_id: Optional[str] = None
    active_tools: List[str] = Field(default_factory=list)
    created_at: Optional[datetime.datetime] = None
    last_activity_at: Optional[datetime.datetime] = None
    active_branch_id: Optional[str] = None

class DiscussionBranchSwitchRequest(BaseModel):
    active_branch_id: str

class DiscussionTitleUpdate(BaseModel):
    title: constr(min_length=1, max_length=255)

class DiscussionRagDatastoreUpdate(BaseModel):
    rag_datastore_id: Optional[str] = None

class DiscussionToolsUpdate(BaseModel):
    tools: List[str]

class MessageOutput(BaseModel):
    id: str
    sender: str
    content: str
    parent_message_id: Optional[str] = None
    binding_name: Optional[str] = None
    model_name: Optional[str] = None
    token_count: Optional[int] = None
    sources: Optional[List[Dict]] = None
    steps: Optional[List[Dict]] = None
    image_references: List[str] = []
    user_grade: int = 0
    created_at: Optional[datetime.datetime] = None
    branch_id: Optional[str] = None
    branches: Optional[List[str]] = None
    
    @field_validator('user_grade', mode='before')
    def provide_default_grade(cls, value):
        return value if value is not None else 0

class MessageContentUpdate(BaseModel):
    content: str

class MessageGradeUpdate(BaseModel):
    change: int
    @field_validator('change')
    def change_must_be_one_or_minus_one(cls, value):
        if value not in [1, -1]:
            raise ValueError('Grade change must be 1 or -1')
        return value

class SafeStoreDocumentInfo(BaseModel):
    filename: str

class DiscussionExportRequest(BaseModel):
    discussion_ids: Optional[List[str]] = None

class ExportData(BaseModel):
    exported_by_user: str
    export_timestamp: str
    application_version: str
    user_settings_at_export: Dict[str, Optional[Any]]
    datastores_info: Dict[str, Any] = Field(default_factory=dict)
    personalities_info: Dict[str, Any] = Field(default_factory=dict)
    discussions: List[Dict[str, Any]]

class DiscussionImportRequest(BaseModel):
    discussion_ids_to_import: List[str]

class DiscussionSendRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)

class DataStoreBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

class DataStoreCreate(DataStoreBase):
    pass

class DataStoreEdit(DataStoreBase):
    new_name: constr(min_length=1, max_length=100)

class DataStorePublic(DataStoreBase):
    id: str
    owner_username: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = {"from_attributes": True}

class DataStoreShareRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)
    permission_level: str = "read_query"

    @validator('permission_level')
    def permission_level_must_be_valid(cls, value):
        if value not in ["read_query"]:
            raise ValueError("Invalid permission level")
        return value

class PersonalityBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    author: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    prompt_text: str
    disclaimer: Optional[str] = Field(None, max_length=1000)
    script_code: Optional[str] = None
    icon_base64: Optional[str] = None

class PersonalityCreate(PersonalityBase):
    is_public: Optional[bool] = False

class PersonalityUpdate(PersonalityBase):
    name: Optional[constr(min_length=1, max_length=100)] = None
    prompt_text: Optional[str] = None
    is_public: Optional[bool] = None

class PersonalityPublic(PersonalityBase):
    id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_public: bool
    owner_username: Optional[str] = None
    model_config = {"from_attributes": True}

class MCPBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    url: str

class MCPCreate(MCPBase):
    pass

class MCPUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=100)] = None
    url: Optional[str] = None

class MCPPublic(MCPBase):
    id: str
    owner_username: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = {"from_attributes": True}

class ToolInfo(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = False

class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    family_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    birth_date: Optional[datetime.date] = None

    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None

    llm_ctx_size: Optional[int] = Field(None, ge=0)
    llm_temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    llm_top_k: Optional[int] = Field(None, ge=1)
    llm_top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    llm_repeat_penalty: Optional[float] = Field(None, ge=0.0)
    llm_repeat_last_n: Optional[int] = Field(None, ge=0)

    rag_top_k: Optional[int] = Field(None, ge=1)
    max_rag_len: Optional[int] = Field(None, ge=1)
    rag_n_hops: Optional[int] = Field(None, ge=1)
    rag_min_sim_percent: Optional[float] = Field(None, ge=0, le=100)
    rag_use_graph: Optional[bool] = None
    rag_graph_response_type: Optional[str] = Field(None, pattern="^(graph_only|chunks_summary|full)$")    

class FriendshipBase(BaseModel):
    pass

class FriendRequestCreate(BaseModel):
    target_username: constr(min_length=3, max_length=50)

class FriendshipAction(BaseModel):
    action: str

class FriendPublic(BaseModel):
    id: int
    username: str
    friendship_id: int
    status_with_current_user: FriendshipStatus
    model_config = {"from_attributes": True}

class FriendshipRequestPublic(BaseModel):
    friendship_id: int
    requesting_user_id: int
    requesting_username: str
    requested_at: datetime.datetime
    status: FriendshipStatus
    model_config = {"from_attributes": True}

class DirectMessageBase(BaseModel):
    content: constr(min_length=1)

class DirectMessageCreate(DirectMessageBase):
    receiver_user_id: int
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