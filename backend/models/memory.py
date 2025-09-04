import datetime
from typing import Optional, List
from pydantic import BaseModel, constr

class MemoryBase(BaseModel):
    title: constr(min_length=1)
    content: str

class MemoryCreate(MemoryBase):
    pass

class MemoryUpdate(BaseModel):
    title: Optional[constr(min_length=1)] = None
    content: Optional[str] = None

class MemoryPublic(MemoryBase):
    id: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class MemoryExport(MemoryBase):
    created_at: str

class MemoriesImport(BaseModel):
    memories: List[MemoryExport]