import datetime
from typing import List, Dict, Optional, Any, TypeVar, Generic

from pydantic import BaseModel, Field, constr, field_validator, validator, EmailStr, computed_field
from backend.database_setup import FriendshipStatus
from enum import Enum
from backend.database_setup import FriendshipStatus, PostVisibility as DBPostVisibility

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    has_more: bool

class LLMBindingBase(BaseModel):
    alias: constr(min_length=1, max_length=100)
    name: constr(min_length=1, max_length=100)
    host_address: Optional[str] = None
    models_path: Optional[str] = None
    default_model_name: Optional[str] = None
    verify_ssl_certificate: Optional[bool] = True
    is_active: bool = True

class LLMBindingCreate(LLMBindingBase):
    service_key: Optional[str] = None

class LLMBindingUpdate(BaseModel):
    alias: Optional[constr(min_length=1, max_length=100)] = None
    name: Optional[constr(min_length=1, max_length=100)] = None
    host_address: Optional[str] = None
    models_path: Optional[str] = None
    service_key: Optional[str] = None
    default_model_name: Optional[str] = None
    verify_ssl_certificate: Optional[bool] = True
    is_active: Optional[bool] = None

class LLMBindingPublic(LLMBindingBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class ModelInfo(BaseModel):
    name: str
    id: Optional[str] = None
    icon_base64: Optional[str] = None

class AdminDashboardStats(BaseModel):
    total_users: int
    active_users_24h: int
    new_users_7d: int
    pending_approval: int
    pending_password_resets: int

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
    receive_notification_emails: bool = True
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
    receive_notification_emails: Optional[bool] = None
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
    show_token_counter: Optional[bool] = None
    is_searchable: Optional[bool] = None

class AdminUserUpdate(BaseModel):
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
    lollms_model_name: Optional[str] = None
    llm_ctx_size: Optional[int] = Field(None, ge=0)
    safe_store_vectorizer: Optional[str] = None
    class Config:
        from_attributes = True

class BatchUsersSettingsUpdate(BaseModel):
    user_ids: List[int]
    lollms_model_name: Optional[str] = None
    llm_ctx_size: Optional[int] = Field(None, ge=0)
    safe_store_vectorizer: Optional[str] = None

class ForceSettingsPayload(BaseModel):
    model_name: str
    context_size: Optional[int] = None

class UserPasswordChange(BaseModel):
    current_password: str
    new_password: constr(min_length=8)

class ForgotPasswordRequest(BaseModel):
    username_or_email: str

class PasswordResetRequest(BaseModel):
    token: str
    new_password: constr(min_length=8)

class UserPasswordResetAdmin(BaseModel):
    new_password: constr(min_length=8)

class EmailUsersRequest(BaseModel):
    subject: constr(min_length=1)
    body: constr(min_length=1)
    user_ids: List[int]
    background_color: Optional[str] = None
    send_as_text: bool = False

class EnhanceEmailRequest(BaseModel):
    subject: str
    body: str
    background_color: Optional[str] = None
    prompt: Optional[str] = None

class EnhancedEmailResponse(BaseModel):
    subject: str
    body: str
    background_color: Optional[str] = None

class PostVisibility(str, Enum):
    PUBLIC = "public"
    FOLLOWERS = "followers"
    FRIENDS = "friends"


class AuthorPublic(BaseModel):
    id: int
    username: str
    icon: Optional[str] = None
    class Config:
        from_attributes = True

class PostBase(BaseModel):
    content: str = Field(..., max_length=10000)
    visibility: PostVisibility = PostVisibility.PUBLIC

class PostCreate(PostBase):
    media: Optional[List[Dict[str, Any]]] = None

class PostUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=10000)
    visibility: Optional[PostVisibility] = None

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
    receive_notification_emails: bool
    is_searchable: bool
    password_reset_token: Optional[str] = None
    reset_token_expiry: Optional[datetime.datetime] = None
    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None
    rag_top_k: Optional[int] = None
    max_rag_len: Optional[int] = None
    rag_n_hops: Optional[int] = None
    rag_min_sim_percent: Optional[float] = None
    rag_use_graph: bool
    rag_graph_response_type: Optional[str] = None
    class Config:
        from_attributes = True

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
    receive_notification_emails: bool
    is_searchable: bool
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
    show_token_counter: Optional[bool] = True
    openai_api_service_enabled: bool = False

class GlobalConfigPublic(BaseModel):
    key: str
    value: Any
    type: str
    description: Optional[str] = None
    category: str

class GlobalConfigUpdate(BaseModel):
    configs: Dict[str, Any]

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

class ContextStatusResponse(BaseModel):
    current_tokens: int
    max_tokens: Optional[int]

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
    discussion_id: str
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
    permission_level: Optional[str] = None
    class Config:
        from_attributes = True

class SharedWithUserPublic(BaseModel):
    user_id: int
    username: str
    icon: Optional[str] = None
    permission_level: str

    class Config:
        from_attributes = True

class DataStoreShareRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)
    permission_level: str = "read_query"

    @validator('permission_level')
    def permission_level_must_be_valid(cls, value):
        if value not in ["read_query", "read_write", "revectorize"]:
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
    class Config:
        from_attributes = True

class PersonalitySendRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)

class MCPBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    url: str
    icon: Optional[str] = None
    active: Optional[bool] = True
    type: Optional[str] = "user"
    authentication_type: Optional[str] = "none"
    authentication_key: Optional[str] = ""
    sso_redirect_uri: Optional[str] = None
    sso_user_infos_to_share: List[str] = Field(default_factory=list)

class MCPCreate(MCPBase):
    pass

class MCPUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=100)] = None
    url: Optional[str] = None
    icon: Optional[str] = None
    active: Optional[bool] = True
    type: Optional[str] = "user"
    authentication_type: Optional[str] = "none"
    authentication_key: Optional[str] = ""
    sso_redirect_uri: Optional[str] = None
    sso_user_infos_to_share: Optional[List[str]] = None

class MCPPublic(MCPBase):
    id: str
    owner_username: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    sso_secret_exists: bool = False
    class Config:
        from_attributes = True

class AppBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    url: str
    icon: Optional[str] = None
    active: Optional[bool] = True
    type: Optional[str] = "user"
    authentication_type: Optional[str] = "none"
    authentication_key: Optional[str] = ""
    sso_redirect_uri: Optional[str] = None
    sso_user_infos_to_share: List[str] = Field(default_factory=list)

class AppCreate(AppBase):
    pass

class AppUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=100)] = None
    url: Optional[str] = None
    icon: Optional[str] = None
    active: Optional[bool] = True
    type: Optional[str] = "user"
    authentication_type: Optional[str] = "none"
    authentication_key: Optional[str] = ""
    sso_redirect_uri: Optional[str] = None
    sso_user_infos_to_share: Optional[List[str]] = None

class AppPublic(AppBase):
    id: str
    owner_username: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    sso_secret_exists: bool = False
    class Config:
        from_attributes = True

class SSOSecretResponse(BaseModel):
    sso_secret: str

class ToolInfo(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = False

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
    class Config:
        from_attributes = True

class FriendshipRequestPublic(BaseModel):
    friendship_id: int
    requesting_user_id: int
    requesting_username: str
    requested_at: datetime.datetime
    status: FriendshipStatus
    class Config:
        from_attributes = True

class DirectMessageBase(BaseModel):
    content: constr(min_length=1)

class DirectMessageCreate(DirectMessageBase):
    receiver_user_id: int = Field(..., alias='receiverUserId')
    image_references_json: Optional[str] = None
    class Config:
        populate_by_name = True
class DirectMessagePublic(DirectMessageBase):
    id: int
    sender_id: int
    receiver_id: int
    sent_at: datetime.datetime
    read_at: Optional[datetime.datetime] = None
    sender_username: str
    receiver_username: str

class RelationshipStatus(BaseModel):
    is_following: bool
    friendship_status: Optional[FriendshipStatus] = None

class UserProfileResponse(BaseModel):
    user: UserPublic
    relationship: RelationshipStatus


class CommentBase(BaseModel):
    content: constr(min_length=1, max_length=2000)

class CommentCreate(CommentBase):
    pass

class CommentPublic(CommentBase):
    id: int
    author: "AuthorPublic"
    created_at: datetime.datetime
    class Config:
        from_attributes = True

class PostPublic(PostBase):
    id: int
    author: AuthorPublic
    media: Optional[List[Dict[str, Any]]] = None
    visibility: DBPostVisibility
    created_at: datetime.datetime
    updated_at: datetime.datetime
    comments: List[CommentPublic] = []
    
    like_count: int = 0
    has_liked: bool = False
    
    class Config:
        from_attributes = True

class APIKeyBase(BaseModel):
    alias: constr(min_length=1, max_length=100)

class APIKeyCreate(APIKeyBase):
    pass

class APIKeyPublic(APIKeyBase):
    id: int
    created_at: datetime.datetime
    last_used_at: Optional[datetime.datetime] = None
    key_prefix: str

    class Config:
        from_attributes = True

class NewAPIKeyResponse(APIKeyPublic):
    full_key: str

class PaginatedDiscussionInfo(PaginatedResponse[DiscussionInfo]):
    pass

class PaginatedMessageOutput(PaginatedResponse[MessageOutput]):
    pass