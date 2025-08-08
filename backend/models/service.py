# backend/models/service.py
import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, constr, field_validator, model_validator

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
    model_aliases: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class LLMBindingPublicAdmin(LLMBindingPublic):
    service_key: Optional[str] = None

# NEW: Model Alias Management Models
class ModelAlias(BaseModel):
    icon: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    has_vision: bool = True

class ModelAliasUpdate(BaseModel):
    original_model_name: str
    alias: ModelAlias

class ModelAliasDelete(BaseModel):
    original_model_name: str

class BindingModel(BaseModel):
    original_model_name: str
    alias: Optional[ModelAlias] = None

# END NEW

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

class ZooAppInfo(BaseModel):
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
    tags: Optional[List[str]] = None
    is_installed: bool = False
    autostart: bool = False
    port: Optional[int] = None

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
    has_config_schema: bool = False
    item_type: Optional[str] = 'app'

    @field_validator('sso_user_infos_to_share', mode='before')
    def provide_default_for_sso_infos(cls, v):
        return v if v is not None else []

    class Config:
        from_attributes = True

class ToolInfo(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = False

class AppLog(BaseModel):
    log_content: str