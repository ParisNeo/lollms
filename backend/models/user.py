# backend/models/user.py
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, date

class UserCreatePublic(BaseModel):
    username: str
    password: str
    email: Optional[EmailStr] = None

class UserCreateAdmin(BaseModel):
    username: str
    password: str
    email: Optional[EmailStr] = None
    is_admin: bool = False

class UserPasswordResetAdmin(BaseModel):
    user_id: int
    new_password: str

class AdminUserUpdate(BaseModel):
    is_admin: Optional[bool] = None
    is_moderator: Optional[bool] = None
    user_ui_level: Optional[int] = None
    status: Optional[str] = None # NEW

class BatchUsersSettingsUpdate(BaseModel):
    user_ids: List[int]
    settings: Dict[str, Any]

class EmailUsersRequest(BaseModel):
    subject: str
    body: str
    recipients: List[int] = []
    send_to_all: bool = False

class EnhanceEmailRequest(BaseModel):
    content: str

class EnhancedEmailResponse(BaseModel):
    content: str

class UserPasswordChange(BaseModel):
    current_password: str
    new_password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class PasswordResetRequest(BaseModel):
    token: str
    new_password: str

class DataZoneUpdate(BaseModel):
    data_zone: str

class MemoryUpdate(BaseModel):
    memory: str

class UserLLMParams(BaseModel):
    llm_ctx_size: Optional[int] = None
    llm_temperature: Optional[float] = None
    llm_top_k: Optional[int] = None
    llm_top_p: Optional[float] = None
    llm_repeat_penalty: Optional[float] = None
    llm_repeat_last_n: Optional[int] = None
    put_thoughts_in_context: Optional[bool] = None
    reasoning_activation: Optional[bool] = None
    reasoning_effort: Optional[str] = None
    reasoning_summary: Optional[bool] = None

class AuthorPublic(BaseModel):
    id: int
    username: str
    icon: Optional[str] = None
    is_admin: bool = False
    is_moderator: bool = False
    status: str = "active" # NEW
    
    class Config:
        from_attributes = True

class UserPublic(BaseModel):
    id: int
    username: str
    icon: Optional[str] = None
    is_admin: bool = False
    is_moderator: bool = False
    is_active: bool = True
    status: str = "active" # NEW
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserProfileResponse(BaseModel):
    id: int
    username: str
    icon: Optional[str] = None
    first_name: Optional[str] = None
    family_name: Optional[str] = None
    is_admin: bool = False
    is_moderator: bool = False
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserAuthDetails(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_moderator: bool = False
    is_active: bool
    status: str = "active" # NEW
    icon: Optional[str] = None
    first_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[str] = None
    birth_date: Optional[date] = None
    receive_notification_emails: bool = True
    is_searchable: bool = True
    first_login_done: bool = False
    data_zone: Optional[str] = None
    user_personal_info: Optional[str] = None
    share_personal_info_with_llm: bool = False
    
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
    lollms_client_ai_name: Optional[str] = None
    
    llm_ctx_size: Optional[int] = None
    llm_temperature: Optional[float] = None
    llm_top_k: Optional[int] = None
    llm_top_p: Optional[float] = None
    llm_repeat_penalty: Optional[float] = None
    llm_repeat_last_n: Optional[int] = None
    put_thoughts_in_context: bool = False
    
    # RAG Settings
    rag_top_k: Optional[int] = 10
    max_rag_len: Optional[int] = 80000
    rag_n_hops: Optional[int] = 0
    rag_min_sim_percent: Optional[float] = 50.0
    rag_use_graph: bool = False
    rag_graph_response_type: Optional[str] = 'chunks_summary'
    
    # RAG Default Settings for DataStore Creation
    default_rag_chunk_size: Optional[int] = 1024
    default_rag_chunk_overlap: Optional[int] = 256
    default_rag_metadata_mode: Optional[str] = "none"

    auto_title: bool = False
    user_ui_level: int = 0
    chat_active: bool = True
    first_page: str = "feed"
    ai_response_language: Optional[str] = "auto"
    force_ai_response_language: bool = False
    fun_mode: bool = False
    show_token_counter: bool = True
    
    openai_api_service_enabled: bool = False
    openai_api_require_key: bool = True
    ollama_service_enabled: bool = False
    ollama_require_key: bool = True
    
    include_memory_date_in_context: bool = False
    llm_settings_overridden: bool = False
    tti_model_forced: bool = False
    iti_model_forced: bool = False
    
    latex_builder_enabled: bool = False
    allow_user_chunking_config: bool = True
    default_chunk_size: int = 2048 # System-wide default from config, not user pref
    default_chunk_overlap: int = 256 # System-wide default from config, not user pref
    
    coding_style_constraints: Optional[str] = None
    programming_language_preferences: Optional[str] = None
    tell_llm_os: bool = False
    share_dynamic_info_with_llm: bool = True
    message_font_size: int = 14
    
    image_studio_prompt: Optional[str] = None
    image_studio_negative_prompt: Optional[str] = None
    image_studio_image_size: Optional[str] = "1024x1024"
    image_studio_n_images: int = 1
    image_studio_seed: int = -1
    image_studio_generation_params: Optional[Dict[str, Any]] = None
    
    image_generation_enabled: bool = False
    image_generation_system_prompt: Optional[str] = None
    image_annotation_enabled: bool = False
    note_generation_enabled: bool = False
    preferred_name: Optional[str] = None
    
    reasoning_activation: bool = False
    reasoning_effort: Optional[str] = None
    reasoning_summary: bool = False

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[str] = None
    birth_date: Optional[date] = None
    icon: Optional[str] = None
    preferred_name: Optional[str] = None
    
    lollms_model_name: Optional[str] = None
    tti_binding_model_name: Optional[str] = None
    iti_binding_model_name: Optional[str] = None
    tts_binding_model_name: Optional[str] = None
    stt_binding_model_name: Optional[str] = None
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
    
    rag_top_k: Optional[int] = None
    max_rag_len: Optional[int] = None
    rag_n_hops: Optional[int] = None
    rag_min_sim_percent: Optional[float] = None
    rag_use_graph: Optional[bool] = None
    rag_graph_response_type: Optional[str] = None
    
    default_rag_chunk_size: Optional[int] = None
    default_rag_chunk_overlap: Optional[int] = None
    default_rag_metadata_mode: Optional[str] = None

    put_thoughts_in_context: Optional[bool] = None
    auto_title: Optional[bool] = None
    user_ui_level: Optional[int] = None
    chat_active: Optional[bool] = None
    first_page: Optional[str] = None
    ai_response_language: Optional[str] = None
    force_ai_response_language: Optional[bool] = None
    fun_mode: Optional[bool] = None
    receive_notification_emails: Optional[bool] = None
    show_token_counter: Optional[bool] = None
    is_searchable: Optional[bool] = None
    first_login_done: Optional[bool] = None
    data_zone: Optional[str] = None
    user_personal_info: Optional[str] = None
    share_personal_info_with_llm: Optional[bool] = None
    include_memory_date_in_context: Optional[bool] = None
    
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
    image_generation_system_prompt: Optional[str] = None
    image_annotation_enabled: Optional[bool] = None
    note_generation_enabled: Optional[bool] = None
    
    reasoning_activation: Optional[bool] = None
    reasoning_effort: Optional[str] = None
    reasoning_summary: Optional[bool] = None
