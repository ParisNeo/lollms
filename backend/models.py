# backend/models.py
import datetime
from typing import List, Dict, Optional, Any

from pydantic import BaseModel, Field, constr, field_validator, validator, EmailStr, computed_field
from backend.database_setup import FriendshipStatus
from enum import Enum
from backend.database_setup import FriendshipStatus, PostVisibility as DBPostVisibility
# --- User Management & Authentication Models ---

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

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

# --- NEW: Public User Registration Model ---
class UserCreatePublic(BaseModel):
    username: constr(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)

class UserCreateAdmin(UserLLMParams):
    username: constr(min_length=3, max_length=50)
    password: constr(min_length=8)
    is_admin: bool = False
    first_name: Optional[str] = Field(None, max_length=100)
    family_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = Field(None, max_length=255)
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

class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    family_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = Field(None, max_length=255)
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
    put_thoughts_in_context: Optional[bool] = None
    rag_top_k: Optional[int] = Field(None, ge=1)
    max_rag_len: Optional[int] = Field(None, ge=1)
    rag_n_hops: Optional[int] = Field(None, ge=1)
    rag_min_sim_percent: Optional[float] = Field(None, ge=0, le=100)
    rag_use_graph: Optional[bool] = None
    rag_graph_response_type: Optional[str] = Field(None, pattern="^(graph_only|chunks_summary|full)$")
    auto_title: Optional[bool] = False
    user_ui_level: Optional[int] = 0
    chat_active: Optional[bool] = False
    first_page: Optional[str] = "feed"
    ai_response_language: Optional[str] = "auto"
    fun_mode: Optional[bool] = False

class UserPasswordChange(BaseModel):
    current_password: str
    new_password: constr(min_length=8)

class UserPasswordResetAdmin(BaseModel):
    new_password: constr(min_length=8)

class PostVisibility(str, Enum):
    PUBLIC = "PUBLIC"
    FOLLOWERS = "FOLLOWERS"
    FRIENDS = "FRIENDS"


class AuthorPublic(BaseModel):
    id: int
    username: str
    icon: Optional[str] = None
    model_config = {"from_attributes": True}

class PostBase(BaseModel):
    content: str = Field(..., max_length=10000)
    visibility: PostVisibility = PostVisibility.PUBLIC

class PostCreate(PostBase):
    media: Optional[List[Dict[str, Any]]] = None # e.g., [{"type": "image", "url": "..."}, {"type": "link", "url": "..."}]

class PostUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=10000)
    visibility: Optional[PostVisibility] = None

class PostPublic(PostBase):
    id: int
    author: AuthorPublic
    media: Optional[List[Dict[str, Any]]] = None
    visibility: str  # 👈 fix here
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = {"from_attributes": True}


class UserPublic(UserLLMParams):
    id: int
    username: str
    is_admin: bool
    is_active: bool
    last_activity_at: Optional[datetime.datetime] = None
    icon: Optional[str] = None
    first_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[EmailStr] = None
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

class UserAuthDetails(UserLLMParams):
    id: int
    username: str
    is_admin: bool
    is_active: bool
    icon: Optional[str] = None 
    first_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[EmailStr] = None
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
    auto_title: Optional[bool] = False
    user_ui_level: Optional[int] = 0
    chat_active: Optional[bool] = False
    first_page: Optional[str] = "feed"

    ai_response_language: Optional[str] = "auto"
    fun_mode: Optional[bool] = False

# --- Global Configuration Models ---

class GlobalConfigPublic(BaseModel):
    key: str
    value: Any
    type: str
    description: Optional[str] = None
    category: str

class GlobalConfigUpdate(BaseModel):
    configs: Dict[str, Any]

# --- Discussion & Message Models ---

class DiscussionInfo(BaseModel):
    id: str
    title: str
    is_starred: bool
    rag_datastore_ids: Optional[List[str]] = None
    active_tools: List[str] = Field(default_factory=list)
    created_at: Optional[datetime.datetime] = None
    last_activity_at: Optional[datetime.datetime] = None
    active_branch_id: Optional[str] = None

class DiscussionBranchSwitchRequest(BaseModel):
    active_branch_id: str

class DiscussionTitleUpdate(BaseModel):
    title: constr(min_length=1, max_length=255)

class DiscussionRagDatastoreUpdate(BaseModel):
    rag_datastore_ids: Optional[List[str]] = None

class DiscussionToolsUpdate(BaseModel):
    tools: List[str]

class MessageOutput(BaseModel):
    id: str
    sender: str
    sender_type: str
    content: str
    parent_message_id: Optional[str] = None
    binding_name: Optional[str] = None
    model_name: Optional[str] = None
    token_count: Optional[int] = None
    sources: Optional[List[Dict]] = None
    events: Optional[List[Dict[str, Any]]] = None
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

# --- DataStore (SafeStore) Models ---

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

# --- Personality Models ---

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

class PersonalitySendRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)

# --- MCP (Multi-Computer-Protocol) Models ---

class MCPBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    url: str
    active: Optional[bool] = True
    type: Optional[str] = "user"
    authentication_type: Optional[str] = "none"
    authentication_key: Optional[str] = ""

class MCPCreate(MCPBase):
    pass

class MCPUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=100)] = None
    url: Optional[str] = None
    active: Optional[bool] = True
    type: Optional[str] = "user"
    authentication_type: Optional[str] = "none"
    authentication_key: Optional[str] = ""


class MCPPublic(MCPBase):
    id: str
    owner_username: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = {"from_attributes": True}

# --- Tool Models ---

class ToolInfo(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = False

# --- Friendship Models ---

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

# --- Direct Message Models ---

class DirectMessageBase(BaseModel):
    content: constr(min_length=1)

class DirectMessageCreate(DirectMessageBase):
    receiver_user_id: int = Field(..., alias='receiverUserId')
    image_references_json: Optional[str] = None
    class Config:
        # This allows Pydantic to work with aliases
        populate_by_name = True
class DirectMessagePublic(DirectMessageBase):
    id: int
    sender_id: int
    receiver_id: int
    sent_at: datetime.datetime
    read_at: Optional[datetime.datetime] = None
    sender_username: str  # The API will provide this
    receiver_username: str # The API will provide this



class RelationshipStatus(BaseModel):
    """
    Describes the relationship from the current user's perspective
    to the user whose profile is being viewed.
    """
    is_following: bool
    friendship_status: Optional[FriendshipStatus] = None

class UserProfileResponse(BaseModel):
    """
    The complete data structure returned by the GET /api/users/{username} endpoint.
    """
    user: UserPublic
    relationship: RelationshipStatus


class CommentBase(BaseModel):
    content: constr(min_length=1, max_length=2000)

class CommentCreate(CommentBase):
    pass

class CommentPublic(CommentBase):
    id: int
    author: "AuthorPublic" # Forward reference to the existing AuthorPublic model
    created_at: datetime.datetime
    model_config = {"from_attributes": True}

class PostVisibility(str, Enum):
    PUBLIC = "public"
    FOLLOWERS = "followers"
    FRIENDS = "friends"

class PostPublic(PostBase):
    id: int
    author: AuthorPublic
    media: Optional[List[Dict[str, Any]]] = None
    visibility: DBPostVisibility
    created_at: datetime.datetime
    updated_at: datetime.datetime
    comments: List[CommentPublic] = []
    
    # --- ADD THESE NEW FIELDS ---
    like_count: int = 0
    has_liked: bool = False
    
    model_config = {"from_attributes": True}