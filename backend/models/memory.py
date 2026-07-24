from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

class MemoryBase(BaseModel):
    title: str
    content: str

class MemoryCreate(MemoryBase):
    pass

class MemoryUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

class MemoryPublic(MemoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

class MemoriesImport(BaseModel):
    memories: List[MemoryCreate]
