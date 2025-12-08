# [UPDATE] backend/models/datastore.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class DataStoreBase(BaseModel):
    name: str
    description: Optional[str] = None

class DataStoreCreate(DataStoreBase):
    vectorizer_name: str
    vectorizer_config: Dict[str, Any] = Field(default_factory=dict)
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None

class DataStoreEdit(DataStoreBase):
    pass

class DataStorePublic(DataStoreBase):
    id: str
    owner_username: str
    permission_level: str
    vectorizer_name: str
    vectorizer_config: Dict[str, Any]
    chunk_size: int
    chunk_overlap: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class DataStoreShareRequest(BaseModel):
    target_username: str
    permission_level: str

class SharedWithUserPublic(BaseModel):
    user_id: int
    username: str
    icon: Optional[str]
    permission_level: str

class SafeStoreDocumentInfo(BaseModel):
    filename: str

class ScrapeRequest(BaseModel):
    url: str
    depth: int = 0
