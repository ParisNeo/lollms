# backend/models/shared.py
import datetime
from typing import List, Optional, Any, TypeVar, Generic, Dict
from pydantic import BaseModel
from .service import ModelAlias

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    has_more: bool

class ModelInfo(BaseModel):
    name: str
    id: Optional[str] = None
    alias: Optional[ModelAlias] = None # NEW: Rich alias information


class AdminDashboardStats(BaseModel):
    total_users: int
    active_users_24h: int
    new_users_7d: int
    pending_approval: int
    pending_password_resets: int

class GPUInfo(BaseModel):
    id: int
    name: str
    vram_total_gb: float
    vram_used_gb: float
    vram_usage_percent: float

class DiskInfo(BaseModel):
    mount_point: str
    total_gb: float
    used_gb: float
    available_gb: float
    usage_percent: float
    is_app_disk: bool
    is_data_disk: bool

class SystemUsageStats(BaseModel):
    cpu_ram_total_gb: float
    cpu_ram_used_gb: float
    cpu_ram_available_gb: float
    cpu_ram_usage_percent: float
    
    disks: List[DiskInfo]
    
    gpus: List[GPUInfo]