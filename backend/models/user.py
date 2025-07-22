# backend/models/user.py
import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, constr, EmailStr
from backend.db.models.friends import FriendshipStatus

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
    put_thoughts_in_context: Optional[bool] = False # NEW: Explicitly set default for Admin creation

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
    put_thoughts_in_context: Optional[bool] = False # NEW: Ensure default value for updates
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
    # No direct user_ui_level here as it's typically set by admin role or default

    class Config:
        from_attributes = True

class BatchUsersSettingsUpdate(BaseModel):
    user_ids: List[int]
    lollms_model_name: Optional[str] = None
    llm_ctx_size: Optional[int] = Field(None, ge=0)
    safe_store_vectorizer: Optional[str] = None

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

class AuthorPublic(BaseModel):
    id: int
    username: str
    icon: Optional[str] = None
    class Config:
        from_attributes = True

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

class RelationshipStatus(BaseModel):
    is_following: bool
    friendship_status: Optional[FriendshipStatus] = None

class UserProfileResponse(BaseModel):
    user: UserPublic
    relationship: RelationshipStatus