# [UPDATE] backend/models/user.py
# [UPDATE] backend/models/user.py
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
    # New reasoning fields
    reasoning_activation: Optional[bool] = False
    reasoning_effort: Optional[str] = None
    reasoning_summary: Optional[bool] = False

class DataZoneUpdate(BaseModel):
    content: str

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
    is_moderator: bool = False
    first_name: Optional[str] = Field(None, max_length=100)
    family_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = Field(None, max_length=255)
    birth_date: Optional[datetime.date] = None
    receive_notification_emails: bool = True
    lollms_model_name: Optional[str] = None
    tti_binding_model_name: Optional[str] = None # NEW
    iti_binding_model_name: Optional[str] = None
    tti_models_config: Optional[Dict[str, Any]] = None # NEW
    tts_binding_model_name: Optional[str] = None # NEW
    tts_models_config: Optional[Dict[str, Any]] = None # NEW
    stt_binding_model_name: Optional[str] = None
    stt_models_config: Optional[Dict[str, Any]] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None
    active_voice_id: Optional[str] = None
    rag_top_k: Optional[int] = Field(None, ge=1)
    max_rag_len: Optional[int] = Field(None, ge=1)
    rag_n_hops: Optional[int] = Field(None, ge=1)
    rag_min_sim_percent: Optional[float] = Field(None, ge=0, le=100)
    rag_use_graph: Optional[bool] = False
    rag_graph_response_type: Optional[str] = Field("chunks_summary", pattern="^(graph_only|chunks_summary|full)$")
    put_thoughts_in_context: Optional[bool] = False
    include_memory_date_in_context: Optional[bool] = False
    first_login_done: Optional[bool] = False
    coding_style_constraints: Optional[str] = None
    programming_language_preferences: Optional[str] = None
    tell_llm_os: Optional[bool] = False
    share_dynamic_info_with_llm: Optional[bool] = True
    message_font_size: Optional[int] = None
    fun_mode: Optional[bool] = False
    ai_response_language: Optional[str] = "auto"
    force_ai_response_language: Optional[bool] = False
    note_generation_enabled: Optional[bool] = False # NEW

class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    family_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = Field(None, max_length=255)
    birth_date: Optional[datetime.date] = None
    receive_notification_emails: Optional[bool] = None
    is_searchable: Optional[bool] = None
    data_zone: Optional[str] = None
    lollms_model_name: Optional[str] = None
    tti_binding_model_name: Optional[str] = None
    iti_binding_model_name: Optional[str] = None
    tti_models_config: Optional[Dict[str, Any]] = None
    tts_binding_model_name: Optional[str] = None
    tts_models_config: Optional[Dict[str, Any]] = None
    stt_binding_model_name: Optional[str] = None
    stt_models_config: Optional[Dict[str, Any]] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None
    active_voice_id: Optional[str] = None
    last_discussion_id: Optional[str] = None
    llm_ctx_size: Optional[int] = None
    llm_temperature: Optional[float] = None
    llm_top_k: Optional[int] = None
    llm_top_p: Optional[float] = None
    llm_repeat_penalty: Optional[float] = None
    llm_repeat_last_n: Optional[int] = None
    put_thoughts_in_context: Optional[bool] = None
    include_memory_date_in_context: Optional[bool] = None
    rag_top_k: Optional[int] = None
    max_rag_len: Optional[int] = None
    rag_n_hops: Optional[int] = None
    rag_min_sim_percent: Optional[float] = None
    rag_use_graph: Optional[bool] = None
    rag_graph_response_type: Optional[str] = None
    auto_title: Optional[bool] = None
    user_ui_level: Optional[int] = None
    chat_active: Optional[bool] = None
    first_page: Optional[str] = None
    ai_response_language: Optional[str] = None
    force_ai_response_language: Optional[bool] = None
    fun_mode: Optional[bool] = None
    show_token_counter: Optional[bool] = None
    is_searchable: Optional[bool] = None
    data_zone: Optional[str] = None
    coding_style_constraints: Optional[str] = None
    programming_language_preferences: Optional[str] = None
    tell_llm_os: Optional[bool] = None
    share_dynamic_info_with_llm: Optional[bool] = None
    message_font_size: Optional[int] = None
    image_studio_prompt: Optional[str] = None
    image_studio_negative_prompt: Optional[str] = None
    image_studio_image_size: Optional[str] = None
    image_studio_n_images: Optional[int] = None
    image_studio_seed: Optional[int] = None
    image_studio_generation_params: Optional[Dict[str, Any]] = None
    image_generation_enabled: Optional[bool] = None
    image_annotation_enabled: Optional[bool] = None
    note_generation_enabled: Optional[bool] = None # NEW
    # New fields
    reasoning_activation: Optional[bool] = None
    reasoning_effort: Optional[str] = None
    reasoning_summary: Optional[bool] = None
    
    # NEW FIELDS for User Personal Info
    preferred_name: Optional[str] = None
    user_personal_info: Optional[str] = None
    share_personal_info_with_llm: Optional[bool] = None

class AdminUserUpdate(BaseModel):
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None    
    is_moderator: Optional[bool] = None
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
    is_admin: Optional[bool] = False
    is_moderator: Optional[bool] = False
    is_active: Optional[bool] = True
    last_activity_at: Optional[datetime.datetime] = None
    icon: Optional[str] = None
    first_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[EmailStr] = None
    birth_date: Optional[datetime.date] = None
    receive_notification_emails: Optional[bool] = True
    is_searchable: Optional[bool] = True
    password_reset_token: Optional[str] = None
    reset_token_expiry: Optional[datetime.datetime] = None
    lollms_model_name: Optional[str] = None
    tti_binding_model_name: Optional[str] = None # NEW
    iti_binding_model_name: Optional[str] = None
    tti_models_config: Optional[Dict[str, Any]] = None # NEW
    tts_binding_model_name: Optional[str] = None # NEW
    tts_models_config: Optional[Dict[str, Any]] = None # NEW
    stt_binding_model_name: Optional[str] = None
    stt_models_config: Optional[Dict[str, Any]] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None
    active_voice_id: Optional[str] = None
    rag_top_k: Optional[int] = None
    max_rag_len: Optional[int] = None
    rag_n_hops: Optional[int] = None
    rag_min_sim_percent: Optional[float] = None
    rag_use_graph: Optional[bool] = False
    rag_graph_response_type: Optional[str] = None
    first_login_done: Optional[bool] = False
    data_zone: Optional[str] = None
    memory: Optional[str] = None
    icon: Optional[str] = None
    coding_style_constraints: Optional[str] = None
    programming_language_preferences: Optional[str] = None
    tell_llm_os: Optional[bool] = None
    share_dynamic_info_with_llm: Optional[bool] = None
    fun_mode: Optional[bool] = None
    ai_response_language: Optional[str] = None
    force_ai_response_language: Optional[bool] = None
    class Config:
        from_attributes = True

class UserAuthDetails(UserPublic):
    id: int
    username: str
    is_admin: bool
    is_moderator: bool
    is_active: bool
    icon: Optional[str] = None
    first_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[EmailStr] = None
    birth_date: Optional[datetime.date] = None
    receive_notification_emails: bool
    is_searchable: bool
    first_login_done: bool
    data_zone: Optional[str] = None
    lollms_model_name: Optional[str] = None
    tti_binding_model_name: Optional[str] = None
    iti_binding_model_name: Optional[str] = None
    tti_models_config: Optional[Dict[str, Any]] = None
    tts_binding_model_name: Optional[str] = None
    tts_models_config: Optional[Dict[str, Any]] = None
    stt_binding_model_name: Optional[str] = None
    stt_models_config: Optional[Dict[str, Any]] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None
    active_voice_id: Optional[str] = None
    last_discussion_id: Optional[str] = None
    llm_ctx_size: Optional[int] = None
    llm_temperature: Optional[float] = None
    llm_top_k: Optional[int] = None
    llm_top_p: Optional[float] = None
    llm_repeat_penalty: Optional[float] = None
    llm_repeat_last_n: Optional[int] = None
    put_thoughts_in_context: bool
    include_memory_date_in_context: bool
    rag_top_k: Optional[int] = None
    max_rag_len: Optional[int] = None
    rag_n_hops: Optional[int] = None
    rag_min_sim_percent: Optional[float] = None
    rag_use_graph: Optional[bool] = None
    rag_graph_response_type: Optional[str] = None
    auto_title: bool
    user_ui_level: Optional[int] = None
    chat_active: bool
    first_page: str
    ai_response_language: Optional[str] = None
    force_ai_response_language: bool
    fun_mode: Optional[bool] = None
    show_token_counter: bool
    openai_api_service_enabled: bool
    openai_api_require_key: bool
    ollama_service_enabled: bool
    ollama_require_key: bool
    llm_settings_overridden: bool
    tti_model_forced: bool
    iti_model_forced: bool
    latex_builder_enabled: bool
    coding_style_constraints: Optional[str] = None
    programming_language_preferences: Optional[str] = None
    tell_llm_os: bool
    share_dynamic_info_with_llm: bool
    message_font_size: int
    allow_user_chunking_config: bool
    default_chunk_size: int
    default_chunk_overlap: int
    image_studio_prompt: Optional[str] = None
    image_studio_negative_prompt: Optional[str] = None
    image_studio_image_size: Optional[str] = None
    image_studio_n_images: Optional[int] = None
    image_studio_seed: Optional[int] = None
    image_studio_generation_params: Optional[Dict[str, Any]] = None
    image_generation_enabled: bool
    image_annotation_enabled: bool
    note_generation_enabled: bool # NEW
    
    # NEW: User Personal Info
    preferred_name: Optional[str] = None
    user_personal_info: Optional[str] = None
    share_personal_info_with_llm: bool

class RelationshipStatus(BaseModel):
    is_following: bool
    friendship_status: Optional[FriendshipStatus] = None

class UserProfileResponse(BaseModel):
    user: UserPublic
    relationship: RelationshipStatus


class MemoryUpdate(BaseModel):
    title: str
    content: str
