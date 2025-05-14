# backend/models/api_models.py
from typing import List, Optional, Any, Dict
import datetime
from pydantic import BaseModel, Field, constr, field_validator, validator
from .app_models import AppLollmsMessage # Relative import for ExportedMessageData

class UserLLMParams(BaseModel):
    llm_temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    llm_top_k: Optional[int] = Field(None, ge=1)
    llm_top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    llm_repeat_penalty: Optional[float] = Field(None, ge=0.0)
    llm_repeat_last_n: Optional[int] = Field(None, ge=0)

class UserPreferences(BaseModel):
    theme_preference: Optional[str] = Field(None, pattern=r"^(light|dark|system)$")
    rag_top_k: Optional[int] = Field(None, ge=1, le=20)

class UserAuthDetails(UserLLMParams, UserPreferences):
    username: str
    is_admin: bool
    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    lollms_client_ai_name: Optional[str] = None

class UserCreateAdmin(UserLLMParams, UserPreferences):
    username: constr(min_length=3, max_length=50)
    password: constr(min_length=8)
    is_admin: bool = False
    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None

class UserPasswordResetAdmin(BaseModel):
    new_password: constr(min_length=8)

class UserPasswordChange(BaseModel):
    current_password: str
    new_password: constr(min_length=8)

class UserPublic(UserLLMParams, UserPreferences):
    id: int
    username: str
    is_admin: bool
    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    model_config = {"from_attributes": True}

class DiscussionInfo(BaseModel):
    id: str
    title: str
    is_starred: bool
    rag_datastore_id: Optional[str] = None

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
    image_references: List[str] = []
    user_grade: int = 0

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

class ExportedMessageData(AppLollmsMessage): # Needs AppLollmsMessage from app_models
    pass

class ExportData(BaseModel):
    exported_by_user: str
    export_timestamp: str
    application_version: str
    user_settings_at_export: Dict[str, Optional[Any]]
    datastores_info: Dict[str, Any] = Field(default_factory=dict)
    discussions: List[Dict[str, Any]]
    prompts: List[Dict[str, Any]] = Field(default_factory=list)

class DiscussionImportRequest(BaseModel):
    discussion_ids_to_import: List[str]

class DiscussionSendRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)

class DataStoreBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_public_in_store: bool = False

class DataStoreCreate(DataStoreBase):
    pass

class DataStorePublic(DataStoreBase):
    id: str
    owner_username: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = {"from_attributes": True}

class DataStoreShareRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)
    permission_level: str = "read_query"
    @validator('permission_level') # validator is deprecated, use field_validator if Pydantic v2
    def permission_level_must_be_valid(cls, value):
        if value not in ["read_query"]:
            raise ValueError("Invalid permission level")
        return value

class PromptBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    content: str
    is_public: bool = False

class PromptCreate(PromptBase):
    pass

class PromptUpdate(PromptBase):
    pass

class PromptPublic(PromptBase):
    id: int
    owner_username: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = {"from_attributes": True}

class FriendshipRequestCreate(BaseModel):
    target_username: constr(min_length=3, max_length=50)

class FriendshipPublic(BaseModel):
    id: int
    friend_username: str
    status: str
    initiated_by_me: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = {"from_attributes": True}