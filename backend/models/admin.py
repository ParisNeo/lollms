from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, EmailStr, ConfigDict, model_validator
import datetime

class ForceGlobalConfigPayload(BaseModel):
    lollms_model_name: Optional[str] = None
    tti_binding_model_name: Optional[str] = None
    tts_binding_model_name: Optional[str] = None
    stt_binding_model_name: Optional[str] = None
    iti_binding_model_name: Optional[str] = None
    ttv_binding_model_name: Optional[str] = None
    ttm_binding_model_name: Optional[str] = None

class ForceSettingsPayload(BaseModel):
    model_name: str
    context_size: Optional[int] = None

class RagVectorizerAlias(BaseModel):
    vectorizer_name: str
    vectorizer_config: Dict[str, Any] = Field(default_factory=dict)
    title: Optional[str] = None
    description: Optional[str] = None

class RagVectorizerAliasUpdate(BaseModel):
    alias_name: str
    alias_data: RagVectorizerAlias

class RagVectorizerAliasDelete(BaseModel):
    alias_name: str

class RAGBindingCreate(BaseModel):
    alias: str
    name: str
    config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

class RAGBindingUpdate(BaseModel):
    alias: Optional[str] = None
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class RAGBindingPublicAdmin(RAGBindingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    model_aliases: Optional[Dict[str, Any]] = None

class LLMBindingCreate(BaseModel):
    alias: str
    name: str
    config: Dict[str, Any] = Field(default_factory=dict)
    default_model_name: Optional[str] = None
    is_active: bool = True

class LLMBindingUpdate(BaseModel):
    alias: Optional[str] = None
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    default_model_name: Optional[str] = None
    is_active: Optional[bool] = None

class LLMBindingPublicAdmin(LLMBindingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    model_aliases: Optional[Dict[str, Any]] = None

class TTIBindingCreate(BaseModel):
    alias: str
    name: str
    config: Dict[str, Any] = Field(default_factory=dict)
    default_model_name: Optional[str] = None
    is_active: bool = True

class TTIBindingUpdate(BaseModel):
    alias: Optional[str] = None
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    default_model_name: Optional[str] = None
    is_active: Optional[bool] = None

class TTIBindingPublicAdmin(TTIBindingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    model_aliases: Optional[Dict[str, Any]] = None

class TTSBindingCreate(BaseModel):
    alias: str
    name: str
    config: Dict[str, Any] = Field(default_factory=dict)
    default_model_name: Optional[str] = None
    is_active: bool = True

class TTSBindingUpdate(BaseModel):
    alias: Optional[str] = None
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    default_model_name: Optional[str] = None
    is_active: Optional[bool] = None

class TTSBindingPublicAdmin(TTSBindingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    model_aliases: Optional[Dict[str, Any]] = None

class STTBindingCreate(BaseModel):
    alias: str
    name: str
    config: Dict[str, Any] = Field(default_factory=dict)
    default_model_name: Optional[str] = None
    is_active: bool = True

class STTBindingUpdate(BaseModel):
    alias: Optional[str] = None
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    default_model_name: Optional[str] = None
    is_active: Optional[bool] = None

class STTBindingPublicAdmin(STTBindingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    model_aliases: Optional[Dict[str, Any]] = None

class TTVBindingCreate(BaseModel):
    alias: str
    name: str
    config: Dict[str, Any] = Field(default_factory=dict)
    default_model_name: Optional[str] = None
    is_active: bool = True

class TTVBindingUpdate(BaseModel):
    alias: Optional[str] = None
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    default_model_name: Optional[str] = None
    is_active: Optional[bool] = None

class TTVBindingPublicAdmin(TTVBindingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    model_aliases: Optional[Dict[str, Any]] = None

class TTMBindingCreate(BaseModel):
    alias: str
    name: str
    config: Dict[str, Any] = Field(default_factory=dict)
    default_model_name: Optional[str] = None
    is_active: bool = True

class TTMBindingUpdate(BaseModel):
    alias: Optional[str] = None
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    default_model_name: Optional[str] = None
    is_active: Optional[bool] = None

class TTMBindingPublicAdmin(TTMBindingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    model_aliases: Optional[Dict[str, Any]] = None

class ModelAlias(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    has_vision: bool = False
    vision_enabled: Optional[bool] = None
    ctx_size_locked: bool = False
    allow_parameters_override: bool = True
    ctx_size: Optional[int] = None
    forced_context_size: Optional[int] = None
    temperature: Optional[float] = None
    top_k: Optional[int] = None
    top_p: Optional[float] = None
    repeat_penalty: Optional[float] = None
    repeat_last_n: Optional[int] = None
    icon: Optional[str] = None
    reasoning_activation: Optional[bool] = False
    reasoning_effort: Optional[str] = None
    reasoning_summary: Optional[bool] = False
    routing_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    vlm_model_profile: Optional[str] = None

    @model_validator(mode='after')
    def sync_universal_profile_fields(self):
        if self.vision_enabled is not None:
            self.has_vision = bool(self.vision_enabled)
        else:
            self.vision_enabled = bool(self.has_vision)

        if self.forced_context_size is not None:
            self.ctx_size = self.forced_context_size
        elif self.ctx_size is not None:
            self.forced_context_size = self.ctx_size
        return self

class TtiModelAlias(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    allow_parameters_override: bool = True
    routing_config: Optional[Dict[str, Any]] = Field(default_factory=dict)

class TtsModelAlias(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    allow_parameters_override: bool = True
    routing_config: Optional[Dict[str, Any]] = Field(default_factory=dict)

class SttModelAlias(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    allow_parameters_override: bool = True
    routing_config: Optional[Dict[str, Any]] = Field(default_factory=dict)

class TtvModelAlias(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    allow_parameters_override: bool = True
    routing_config: Optional[Dict[str, Any]] = Field(default_factory=dict)

class TtmModelAlias(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    allow_parameters_override: bool = True
    routing_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
class RagModelAlias(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    allow_parameters_override: bool = True

class ModelAliasUpdate(BaseModel):
    original_model_name: str
    new_model_name: Optional[str] = None
    alias: ModelAlias

class TtiModelAliasUpdate(BaseModel):
    original_model_name: str
    new_model_name: Optional[str] = None
    alias: TtiModelAlias

class TtsModelAliasUpdate(BaseModel):
    original_model_name: str
    new_model_name: Optional[str] = None
    alias: TtsModelAlias

class SttModelAliasUpdate(BaseModel):
    original_model_name: str
    new_model_name: Optional[str] = None
    alias: SttModelAlias

class TtvModelAliasUpdate(BaseModel):
    original_model_name: str
    new_model_name: Optional[str] = None
    alias: TtvModelAlias

class TtmModelAliasUpdate(BaseModel):
    original_model_name: str
    new_model_name: Optional[str] = None
    alias: TtmModelAlias
    
class RagModelAliasUpdate(BaseModel):
    original_model_name: str
    new_model_name: Optional[str] = None
    alias: RagModelAlias

class ModelAliasDelete(BaseModel):
    original_model_name: str

class BindingModel(BaseModel):
    original_model_name: str
    alias: Optional[Any] = None

class ModelNamePayload(BaseModel):
    model_name: str

class AdminDashboardStats(BaseModel):
    total_users: int
    active_users_24h: int
    new_users_7d: int
    pending_approval: int
    pending_password_resets: int

class UserActivityStat(BaseModel):
    date: datetime.date
    count: int

class UserStats(BaseModel):
    tasks_per_day: List[UserActivityStat]
    messages_per_day: List[UserActivityStat]

class GlobalGenerationStats(BaseModel):
    generations_per_day: List[UserActivityStat]
    mean_per_weekday: Dict[str, float]
    variance_per_weekday: Dict[str, float]

class UserForAdminPanel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: Optional[EmailStr] = None
    icon: Optional[str] = None
    is_admin: bool = False
    is_moderator: bool = False
    is_active: bool = True
    status: str = "active"
    created_at: datetime.datetime
    last_activity_at: Optional[datetime.datetime] = None
    
    is_online: bool = False
    connection_count: int = 0
    api_key_count: int = 0
    task_count: int = 0
    generation_count: int = 0

class RequirementInfo(BaseModel):
    name: str
    required_version: Optional[str]
    installed_version: Optional[str]
    status: str

class InstallReqPayload(BaseModel):
    name: str
    version: Optional[str] = None