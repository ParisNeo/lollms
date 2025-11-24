# backend/models/service.py
import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, constr, field_validator, model_validator

# --- NEW: Model for dynamic LLM Binding config ---
class LLMBindingBase(BaseModel):
    alias: constr(min_length=1, max_length=100)
    name: constr(min_length=1, max_length=100) # binding_name
    config: Dict[str, Any] = Field(default_factory=dict)
    default_model_name: Optional[str] = None
    is_active: bool = True

class LLMBindingCreate(LLMBindingBase):
    pass

class LLMBindingUpdate(BaseModel):
    alias: Optional[constr(min_length=1, max_length=100)] = None
    name: Optional[constr(min_length=1, max_length=100)] = None
    config: Optional[Dict[str, Any]] = None
    default_model_name: Optional[str] = None
    is_active: Optional[bool] = None

class LLMBindingPublicAdmin(LLMBindingBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_aliases: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

# --- NEW: TTI Binding Models ---
class TTIBindingBase(BaseModel):
    alias: constr(min_length=1, max_length=100)
    name: constr(min_length=1, max_length=100) # binding_name
    config: Dict[str, Any] = Field(default_factory=dict)
    default_model_name: Optional[str] = None
    is_active: bool = True

class TTIBindingCreate(TTIBindingBase):
    pass

class TTIBindingUpdate(BaseModel):
    alias: Optional[constr(min_length=1, max_length=100)] = None
    name: Optional[constr(min_length=1, max_length=100)] = None
    config: Optional[Dict[str, Any]] = None
    default_model_name: Optional[str] = None
    is_active: Optional[bool] = None

class TTIBindingPublicAdmin(TTIBindingBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_aliases: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
# --- END TTI Binding Models ---


# --- NEW: Model Alias Management Models ---
class ModelAlias(BaseModel):
    icon: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    has_vision: bool = True
    ctx_size: Optional[int] = Field(None, ge=1)
    ctx_size_locked: bool = False
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    top_k: Optional[int] = Field(None, ge=1)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    repeat_penalty: Optional[float] = Field(None, ge=0.0)
    repeat_last_n: Optional[int] = Field(None, ge=0)
    allow_parameters_override: bool = True
    # NEW REASONING FIELDS
    reasoning_activation: Optional[bool] = False
    reasoning_effort: Optional[str] = None # low, medium, high
    reasoning_summary: Optional[bool] = False

class ModelAliasUpdate(BaseModel):
    original_model_name: str
    alias: ModelAlias

# --- NEW: Flexible TTI Alias Update Model ---
class TtiModelAliasUpdate(BaseModel):
    original_model_name: str
    alias: Dict[str, Any]

class ModelAliasDelete(BaseModel):
    original_model_name: str

class BindingModel(BaseModel):
    original_model_name: str
    alias: Optional[Dict[str, Any]] = None # FIX: Changed from ModelAlias to support flexible TTI/LLM params

class ModelNamePayload(BaseModel):
    model_name: str
# --- END NEW ---


class MCPBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    client_id: Optional[str] = None
    url: str
    icon: Optional[str] = None
    active: Optional[bool] = True
    type: Optional[str] = "user"
    authentication_type: Optional[str] = "none"
    authentication_key: Optional[str] = ""
    sso_redirect_uri: Optional[str] = None
    sso_user_infos_to_share: List[str] = Field(default_factory=list)

    @field_validator('sso_user_infos_to_share', mode='before')
    @classmethod
    def validate_sso_user_infos(cls, v: Any) -> List[str]:
        if v is None:
            return []
        return v
        
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
    owner_username: Optional[str|None] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    class Config:
        from_attributes = True

class AppZooRepositoryCreate(BaseModel):
    name: constr(min_length=1, max_length=100)
    url: Optional[str] = None
    path: Optional[str] = None

    @model_validator(mode='before')
    def check_url_or_path_exclusive(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        url, path = values.get('url'), values.get('path')
        if not (url or path) or (url and path):
            raise ValueError('Either url or path must be provided, but not both.')
        return values

class AppZooRepositoryPublic(BaseModel):
    id: int
    name: str
    url: str
    type: str
    last_pulled_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    is_deletable: bool = True
    class Config:
        from_attributes = True

class MCPZooRepositoryCreate(BaseModel):
    name: constr(min_length=1, max_length=100)
    url: Optional[str] = None
    path: Optional[str] = None

    @model_validator(mode='before')
    def check_url_or_path_exclusive(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        url, path = values.get('url'), values.get('path')
        if not (url or path) or (url and path):
            raise ValueError('Either url or path must be provided, but not both.')
        return values

class MCPZooRepositoryPublic(BaseModel):
    id: int
    name: str
    url: str
    type: str
    last_pulled_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    is_deletable: bool = True
    class Config:
        from_attributes = True

class PromptZooRepositoryCreate(BaseModel):
    name: constr(min_length=1, max_length=100)
    url: Optional[str] = None
    path: Optional[str] = None

    @model_validator(mode='before')
    def check_url_or_path_exclusive(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        url, path = values.get('url'), values.get('path')
        if not (url or path) or (url and path):
            raise ValueError('Either url or path must be provided, but not both.')
        return values

class PromptZooRepositoryPublic(BaseModel):
    id: int
    name: str
    url: str
    type: str
    last_pulled_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    is_deletable: bool = True
    class Config:
        from_attributes = True

class PersonalityZooRepositoryCreate(BaseModel):
    name: constr(min_length=1, max_length=100)
    url: Optional[str] = None
    path: Optional[str] = None

    @model_validator(mode='before')
    def check_url_or_path_exclusive(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        url, path = values.get('url'), values.get('path')
        if not (url or path) or (url and path):
            raise ValueError('Either url or path must be provided, but not both.')
        return values

class PersonalityZooRepositoryPublic(BaseModel):
    id: int
    name: str
    url: str
    type: str
    last_pulled_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    is_deletable: bool = True
    class Config:
        from_attributes = True
        
class ZooAppInfo(BaseModel):
    id: Optional[str] = None
    name: str
    repository: str
    folder_name: str
    icon: Optional[str] = None
    is_installed: bool = False
    is_broken: bool = False
    is_legacy_scripted: bool = False
    has_readme: bool = False
    author: Optional[str] = None
    category: Optional[str] = None
    creation_date: Optional[str] = None
    description: Optional[str] = None
    disclaimer: Optional[str] = None
    last_update_date: Optional[str] = None
    model: Optional[str] = None
    version: Optional[str] = None
    features: Optional[Any] = None
    tags: Optional[List[str]] = None
    license: Optional[str] = None
    documentation: Optional[str] = None
    update_available: bool = False
    status: Optional[str] = None
    port: Optional[int] = None
    url: Optional[str] = None
    autostart: bool = False
    has_config_schema: bool = False # ADDED THIS LINE
    has_dot_env_config: bool = False
    
    @field_validator('version', 'creation_date', 'last_update_date', mode='before')
    def coerce_to_string(cls, v):
        if v is not None:
            return str(v)
        return v
    
    class Config:
        populate_by_name = True

class ZooAppInfoResponse(BaseModel):
    items: List[ZooAppInfo]
    total: int
    page: int
    pages: int

class ZooMCPInfo(BaseModel):
    id: Optional[str] = None
    name: str
    repository: str
    folder_name: str
    icon: Optional[str] = None
    is_installed: bool = False
    is_broken: bool = False
    has_readme: bool = False
    author: Optional[str] = None
    category: Optional[str] = None
    creation_date: Optional[str] = None
    description: Optional[str] = None
    disclaimer: Optional[str] = None
    last_update_date: Optional[str] = None
    model: Optional[str] = None
    version: Optional[str] = None
    features: Optional[Any] = None
    tags: Optional[List[str]] = None
    license: Optional[str] = None
    documentation: Optional[str] = None
    update_available: bool = False
    status: Optional[str] = None
    port: Optional[int] = None
    url: Optional[str] = None
    autostart: bool = False
    has_config_schema: bool = False # ADDED THIS LINE
    has_dot_env_config: bool = False

    @field_validator('version', 'creation_date', 'last_update_date', mode='before')
    def coerce_to_string(cls, v):
        if v is not None:
            return str(v)
        return v
    
    class Config:
        populate_by_name = True

class ZooMCPInfoResponse(BaseModel):
    items: List[ZooMCPInfo]
    total: int
    page: int
    pages: int

class ZooPromptInfo(BaseModel):
    id: Optional[str] = None
    name: str
    repository: str
    folder_name: str
    icon: Optional[str] = None
    is_installed: bool = False
    has_readme: bool = False
    author: Optional[str] = None
    category: Optional[str] = None
    creation_date: Optional[str] = None
    description: Optional[str] = None
    disclaimer: Optional[str] = None
    last_update_date: Optional[str] = None
    version: Optional[str] = None
    tags: Optional[List[str]] = None
    update_available: bool = False
    content: Optional[str] = None
    repo_version: Optional[str] = None
    
    @field_validator('version', 'creation_date', 'last_update_date', mode='before')
    def coerce_to_string(cls, v):
        if v is not None:
            return str(v)
        return v
    
    class Config:
        populate_by_name = True

class ZooPromptInfoResponse(BaseModel):
    items: List[ZooPromptInfo]
    total: int
    page: int
    pages: int


class AppInstallRequest(BaseModel):
    repository: str
    folder_name: str
    port: int = Field(..., gt=1024, lt=65536)
    autostart: bool = False

class PromptInstallRequest(BaseModel):
    repository: str
    folder_name: str

class AppActionResponse(BaseModel):
    success: bool
    message: str

class AppBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    client_id: Optional[str] = None
    url: Optional[str] = None
    icon: Optional[str] = None
    active: Optional[bool] = True
    type: Optional[str] = "user"
    authentication_type: Optional[str] = "none"
    authentication_key: Optional[str] = ""
    sso_redirect_uri: Optional[str] = None
    sso_user_infos_to_share: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    is_installed: bool = False
    autostart: bool = False
    port: Optional[int] = None
    allow_openai_api_access: bool = False

    @field_validator('sso_user_infos_to_share', 'tags', mode='before')
    @classmethod
    def validate_to_list(cls, v: Any) -> List[str]:
        if v is None:
            return []
        return v

class AppCreate(AppBase):
    @model_validator(mode='after')
    def check_url_or_installed(self) -> 'AppCreate':
        if not self.is_installed and not self.url:
            raise ValueError('URL is required for non-installed apps')
        return self

class AppUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=100)] = None
    url: Optional[str] = None
    icon: Optional[str] = None
    active: Optional[bool] = None
    type: Optional[str] = None
    authentication_type: Optional[str] = None
    authentication_key: Optional[str] = None
    sso_redirect_uri: Optional[str] = None
    sso_user_infos_to_share: Optional[List[str]] = None
    description: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    autostart: Optional[bool] = None
    port: Optional[int] = None
    allow_openai_api_access: Optional[bool] = None

class AppPublic(AppBase):
    id: str
    owner_username: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    status: Optional[str] = None
    pid: Optional[int] = None
    autostart: bool = False
    update_available: bool = False
    repo_version: Optional[str] = None
    has_config_schema: bool = False # ADDED THIS LINE
    has_dot_env_config: bool = False
    item_type: Optional[str] = 'app'

    class Config:
        from_attributes = True

class ToolInfo(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = False

class AppLog(BaseModel):
    log_content: str
