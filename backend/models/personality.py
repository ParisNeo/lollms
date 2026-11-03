import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, constr, ConfigDict


class PersonalityBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    author: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None)
    prompt_text: str
    disclaimer: Optional[str] = Field(None)
    script_code: Optional[str] = None
    icon_base64: Optional[str] = None
    tools: Optional[List[str]] = Field(default_factory=list)
    required_context_options: Optional[List[str]] = Field(default_factory=list)
    data_source_type: Optional[str] = "none"
    data_source: Optional[str] = None
    # Zoo metadata
    version: Optional[str] = Field(None, max_length=50)
    repository: Optional[str] = Field(None, max_length=255)
    folder_name: Optional[str] = Field(None, max_length=255)


class PersonalityCreate(PersonalityBase):
    is_public: Optional[bool] = False
    owner_type: Optional[str] = 'user'


class PersonalityUpdate(BaseModel):
    """All fields optional — partial update contract for the Studio form."""
    name: Optional[constr(min_length=1, max_length=100)] = None
    category: Optional[str] = Field(None, max_length=100)
    author: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    prompt_text: Optional[str] = None
    disclaimer: Optional[str] = None
    script_code: Optional[str] = None
    icon_base64: Optional[str] = None
    tools: Optional[List[str]] = None
    required_context_options: Optional[List[str]] = None
    data_source_type: Optional[str] = None
    data_source: Optional[str] = None
    version: Optional[str] = Field(None, max_length=50)
    repository: Optional[str] = Field(None, max_length=255)
    folder_name: Optional[str] = Field(None, max_length=255)
    is_public: Optional[bool] = None


class Personality(PersonalityBase):
    """Full response schema for the Zoo grid and Studio form."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_public: bool
    owner_user_id: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    # Computed for Studio/Zoo UI state
    author_name: Optional[str] = None


class PersonalityPublic(PersonalityBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_public: bool
    owner_username: Optional[str] = None


class PersonalitySendRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)


# ---------------------------------------------------------------------------
# Handbag sharing & preference schemas (filesystem-backed personalities)
# ---------------------------------------------------------------------------

class PersonalityShareCreate(BaseModel):
    handbag_name: constr(min_length=1, max_length=255)
    shared_with_user_id: Optional[int] = None
    group_id: Optional[str] = Field(None, max_length=255)
    permission: str = Field("read", pattern="^(read)$")  # extend pattern when write is supported


class PersonalityShareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_user_id: int
    handbag_name: str
    shared_with_user_id: Optional[int] = None
    group_id: Optional[str] = None
    permission: str


class UserPersonalityPreferenceSet(BaseModel):
    scope: str = Field(..., pattern="^(global|personal|shared)$")
    handbag_name: constr(min_length=1, max_length=255)
    owner_id: Optional[int] = None  # required when scope == "shared"


class UserPersonalityPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    scope: str
    handbag_name: str
    owner_id: Optional[int] = None