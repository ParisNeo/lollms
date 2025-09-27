# [CREATE] backend/models/admin.py
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

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