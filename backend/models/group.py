# [CREATE] backend/models/group.py
from pydantic import BaseModel, Field
from typing import List, Optional
from backend.models.user import AuthorPublic

class GroupMember(BaseModel):
    id: int
    username: str
    icon: Optional[str] = None

    class Config:
        from_attributes = True

class GroupPublic(BaseModel):
    id: int
    display_name: str = Field(..., alias="displayName")
    description: Optional[str] = None
    icon: Optional[str] = None
    owner: Optional[AuthorPublic] = None
    members: List[GroupMember] = []

    class Config:
        from_attributes = True
        allow_population_by_field_name = True

class GroupCreate(BaseModel):
    display_name: str
    description: Optional[str] = None

class GroupUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None

class MemberUpdate(BaseModel):
    user_id: int
