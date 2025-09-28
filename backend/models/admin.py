# backend/models/admin.py
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, EmailStr
import datetime

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
    id: int
    model_aliases: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

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
    id: int
    model_aliases: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

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
    id: int
    model_aliases: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class ModelAlias(BaseModel):
    name: str
    has_vision: bool = False
    ctx_size_locked: bool = False
    allow_parameters_override: bool = True
    ctx_size: Optional[int] = None
    temperature: Optional[float] = None
    top_k: Optional[int] = None
    top_p: Optional[float] = None
    repeat_penalty: Optional[float] = None
    repeat_last_n: Optional[int] = None
    icon: Optional[str] = None

class TtiModelAlias(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    allow_parameters_override: bool = True

class TtsModelAlias(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    allow_parameters_override: bool = True

class ModelAliasUpdate(BaseModel):
    original_model_name: str
    alias: ModelAlias

class TtiModelAliasUpdate(BaseModel):
    original_model_name: str
    alias: TtiModelAlias

class TtsModelAliasUpdate(BaseModel):
    original_model_name: str
    alias: TtsModelAlias

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
    id: int
    username: str
    email: Optional[EmailStr] = None
    icon: Optional[str] = None
    is_admin: bool = False
    is_moderator: bool = False
    is_active: bool = True
    created_at: datetime.datetime
    last_activity_at: Optional[datetime.datetime] = None
    
    is_online: bool = False
    connection_count: int = 0
    api_key_count: int = 0
    task_count: int = 0
    generation_count: int = 0

    class Config:
        from_attributes = True