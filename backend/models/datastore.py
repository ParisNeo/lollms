import datetime
from typing import Optional
from pydantic import BaseModel, Field, constr, field_validator

class SafeStoreDocumentInfo(BaseModel):
    filename: str

class DataStoreBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

class DataStoreCreate(DataStoreBase):
    pass

class DataStoreEdit(DataStoreBase):
    new_name: constr(min_length=1, max_length=100)

class DataStorePublic(DataStoreBase):
    id: str
    owner_username: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    permission_level: Optional[str] = None
    class Config:
        from_attributes = True

class SharedWithUserPublic(BaseModel):
    user_id: int
    username: str
    icon: Optional[str] = None
    permission_level: str

    class Config:
        from_attributes = True

class DataStoreShareRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)
    permission_level: str = "read_query"

    @field_validator('permission_level')
    def permission_level_must_be_valid(cls, value):
        if value not in ["read_query", "read_write", "revectorize"]:
            raise ValueError("Invalid permission level")
        return value