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
    model_name: Optional[str] = None
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
    model_name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    allow_parameters_override: bool = True
    routing_config: Optional[Dict[str, Any]] = Field(default_factory=dict)

class TtsModelAlias(BaseModel):
    model_config = ConfigDict(extra="allow")
    model_name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    allow_parameters_override: bool = True
    routing_config: Optional[Dict[str, Any]] = Field(default_factory=dict)

class SttModelAlias(BaseModel):
    model_config = ConfigDict(extra="allow")
    model_name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    allow_parameters_override: bool = True
    routing_config: Optional[Dict[str, Any]] = Field(default_factory=dict)

class TtvModelAlias(BaseModel):
    model_config = ConfigDict(extra="allow")
    model_name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    allow_parameters_override: bool = True
    routing_config: Optional[Dict[str, Any]] = Field(default_factory=dict)

class TtmModelAlias(BaseModel):
    model_config = ConfigDict(extra="allow")
    model_name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    allow_parameters_override: bool = True
    routing_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
class RagModelAlias(BaseModel):
    model_config = ConfigDict(extra="allow")
    model_name: Optional[str] = None
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

class SourceConsumptionBreakdown(BaseModel):
    webui_tokens: int = 0
    api_tokens: int = 0
    total_tokens: int = 0
    webui_requests: int = 0
    api_requests: int = 0
    total_requests: int = 0
    webui_ratio: float = 0.0
    api_ratio: float = 0.0
    webui_energy_kwh: float = 0.0
    api_energy_kwh: float = 0.0
    webui_co2_g: float = 0.0
    api_co2_g: float = 0.0

class UserStats(BaseModel):
    tasks_per_day: List[UserActivityStat]
    messages_per_day: List[UserActivityStat]
    tokens_per_day: List[UserActivityStat] = Field(default_factory=list)
    webui_tokens_per_day: List[UserActivityStat] = Field(default_factory=list)
    api_tokens_per_day: List[UserActivityStat] = Field(default_factory=list)

    # Richer per-day series (all computed server-side so the modal does not
    # have to reconstruct them client-side; defaults keep older clients safe).
    generations_per_day: List[UserActivityStat] = Field(default_factory=list)
    prompt_tokens_per_day: List[UserActivityStat] = Field(default_factory=list)
    completion_tokens_per_day: List[UserActivityStat] = Field(default_factory=list)

    # Rolling-window rollups. Computed with their own aggregate queries because
    # a client-side sum over the daily series would be wrong whenever the
    # response window is truncated (e.g. when the endpoint is asked for 7 days).
    tokens_last_7d: int = 0
    tokens_last_30d: int = 0
    generations_last_7d: int = 0
    generations_last_30d: int = 0
    total_generations_30d: int = 0

    # Mean generation count per weekday across the 30-day window. Keys are
    # "Monday".."Sunday" (English, matching the global dashboard's convention).
    weekday_generation_mean: Dict[str, float] = Field(default_factory=dict)

    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_energy_kwh: float = 0.0
    total_co2_g: float = 0.0
    co2_equivalents: Dict[str, float] = Field(default_factory=dict)
    top_models: List[Dict[str, Any]] = Field(default_factory=list)
    source_breakdown: SourceConsumptionBreakdown = Field(default_factory=SourceConsumptionBreakdown)
    # Per-API-key consumption breakdown. Each item:
    # {api_key_id, name, key_prefix, is_active, total_tokens, prompt_tokens,
    #  completion_tokens, calls, last_used_at}. Token counters are populated
    # only when the metering table records a per-key attribution; otherwise the
    # key listing is still returned (with zero counters) so the dashboard can
    # show the user's keys and their status without fabricating usage.
    api_key_usage: List[Dict[str, Any]] = Field(default_factory=list)

class GlobalGenerationStats(BaseModel):
    generations_per_day: List[UserActivityStat] = Field(default_factory=list)
    tokens_per_day: List[UserActivityStat] = Field(default_factory=list)
    # Input (prompt) vs Output (completion) split — these are charted as distinct
    # curves on the admin dashboard because they do not carry the same cost.
    prompt_tokens_per_day: List[UserActivityStat] = Field(default_factory=list)
    completion_tokens_per_day: List[UserActivityStat] = Field(default_factory=list)
    webui_tokens_per_day: List[UserActivityStat] = Field(default_factory=list)
    api_tokens_per_day: List[UserActivityStat] = Field(default_factory=list)
    webui_generations_per_day: List[UserActivityStat] = Field(default_factory=list)
    api_generations_per_day: List[UserActivityStat] = Field(default_factory=list)
    mean_per_weekday: Dict[str, float] = Field(default_factory=dict)
    variance_per_weekday: Dict[str, float] = Field(default_factory=dict)
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_energy_kwh: float = 0.0
    total_co2_g: float = 0.0
    co2_equivalents: Dict[str, float] = Field(default_factory=dict)
    source_breakdown: SourceConsumptionBreakdown = Field(default_factory=SourceConsumptionBreakdown)

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
    total_logins: int = 0

    # Account hygiene flags: distinguishable from "has email" so admins can tell
    # verified accounts from just-declared ones.
    email_verified: bool = False
    has_pending_password_reset: bool = False

    is_online: bool = False
    connection_count: int = 0
    api_key_count: int = 0
    task_count: int = 0
    generation_count: int = 0

    # Per-user token telemetry (aggregated from GenerationMetric).
    # Defaults are zero so older clients / partial queries stay compatible.
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_energy_kwh: float = 0.0
    total_co2_g: float = 0.0
    webui_tokens: int = 0
    api_tokens: int = 0

# ──────────────────────────────────────────────────────────────────────────────
# Per-user token quota (rate limiting). ``None`` on a numeric field means
# "inherit the global default"; ``0`` means "unlimited".
# ──────────────────────────────────────────────────────────────────────────────
class TokenQuotaUpdate(BaseModel):
    """Admin payload to set a user's quota overrides."""
    exempt: Optional[bool] = None
    enabled: Optional[bool] = None
    input_max: Optional[int] = None
    output_max: Optional[int] = None
    period: Optional[str] = None  # 'daily' | 'weekly' | 'monthly' | None(inherit)

class TokenQuotaUsage(BaseModel):
    input_used: int = 0
    input_max: int = 0
    output_used: int = 0
    output_max: int = 0
    period_start: Optional[datetime.datetime] = None
    period_end: Optional[datetime.datetime] = None

class TokenQuotaStatus(BaseModel):
    """Resolved effective quota for a user plus current-period usage."""
    enforced: bool = False
    exempt: bool = False
    period: str = "monthly"
    enabled: Optional[bool] = None
    input_max: Optional[int] = None
    output_max: Optional[int] = None
    reset_at: Optional[datetime.datetime] = None
    usage: TokenQuotaUsage = Field(default_factory=TokenQuotaUsage)

class RequirementInfo(BaseModel):
    name: str
    required_version: Optional[str]
    installed_version: Optional[str]
    status: str

class InstallReqPayload(BaseModel):
    name: str
    version: Optional[str] = None