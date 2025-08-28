import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, constr

class PersonalityBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    author: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None)
    prompt_text: str
    disclaimer: Optional[str] = Field(None)
    script_code: Optional[str] = None
    icon_base64: Optional[str] = None
    active_mcps: Optional[List[str]] = Field(default_factory=list)
    data_source_type: Optional[str] = "none"
    data_source: Optional[str] = None


class PersonalityCreate(PersonalityBase):
    is_public: Optional[bool] = False
    owner_type: Optional[str] = 'user' # For admins to specify 'system' or 'user'

class PersonalityUpdate(PersonalityBase):
    name: Optional[constr(min_length=1, max_length=100)] = None
    prompt_text: Optional[str] = None
    is_public: Optional[bool] = None

class PersonalityPublic(PersonalityBase):
    id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_public: bool
    owner_username: Optional[str] = None
    class Config:
        from_attributes = True

class PersonalitySendRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)
