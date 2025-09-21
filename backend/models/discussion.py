# backend/models/discussion.py
import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, constr, field_validator
from .shared import PaginatedResponse

# --- NEW: Discussion Group Models ---
class DiscussionGroupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

class DiscussionGroupCreate(DiscussionGroupBase):
    parent_id: Optional[str] = None

class DiscussionGroupUpdate(DiscussionGroupBase):
    parent_id: Optional[str] = None

class DiscussionGroupPublic(DiscussionGroupBase):
    id: str
    parent_id: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

# --- END NEW ---

class ArtefactInfo(BaseModel):
    title: str
    version: int
    is_loaded: bool = False
    author: Optional[str] = None
    created_at: str
    updated_at: str
    content: Optional[str] = None # Will be populated only on single-artefact fetch
    images: Optional[List[str]] = None

class LoadArtefactRequest(BaseModel):
    title: str
    version: Optional[int] = None

class UnloadArtefactRequest(BaseModel):
    title: str
    version: Optional[int] = None

class ExportContextRequest(BaseModel):
    title: constr(min_length=1)

class DiscussionInfo(BaseModel):
    id: str
    title: str
    is_starred: bool
    rag_datastore_ids: Optional[List[str]] = None
    active_tools: List[str] = Field(default_factory=list)
    created_at: Optional[datetime.datetime] = None
    last_activity_at: Optional[datetime.datetime] = None
    active_branch_id: Optional[str] = None
    data_zone: Optional[str] = None
    discussion_images: List[dict|str] = Field(default_factory=list)
    active_discussion_images: List[bool] = Field(default_factory=list)
    # New fields for shared discussions
    owner_username: Optional[str] = None
    permission_level: Optional[str] = None
    share_id: Optional[int] = None
    group_id: Optional[str] = None # NEW

class DiscussionCreate(BaseModel):
    group_id: Optional[str] = None

class DiscussionGroupUpdatePayload(BaseModel):
    group_id: Optional[str] = None

class DataZones(BaseModel):
    user_data_zone: Optional[str] = None
    discussion_data_zone: Optional[str] = None
    personality_data_zone: Optional[str] = None
    memory: Optional[str] = None
    discussion_images: List[str] = Field(default_factory=list)
    active_discussion_images: List[bool] = Field(default_factory=list)

class DiscussionBranchSwitchRequest(BaseModel):
    active_branch_id: str

class DiscussionTitleUpdate(BaseModel):
    title: constr(min_length=1, max_length=255)

class DiscussionDataZoneUpdate(BaseModel):
    content: str

class DiscussionRagDatastoreUpdate(BaseModel):
    rag_datastore_ids: Optional[List[str]] = None

class DiscussionToolsUpdate(BaseModel):
    tools: List[str]

class ContextBreakdownItem(BaseModel):
    content: str
    tokens: int

class ContextZoneDetail(BaseModel):
    content: Optional[str] = None
    tokens: int
    breakdown: Optional[Dict[str, Any]] = None
    message_count: Optional[int] = None

class ContextStatusResponse(BaseModel):
    current_tokens: int
    max_tokens: Optional[int]
    zones: Dict[str, ContextZoneDetail]


class MessageOutput(BaseModel):
    id: str
    sender: str
    sender_type: str
    content: str
    parent_message_id: Optional[str] = None
    binding_name: Optional[str] = None
    model_name: Optional[str] = None
    token_count: Optional[int] = None
    sources: Optional[List[Dict]] = None
    events: Optional[List[Dict[str, Any]]] = None
    image_references: List[str] = []
    active_images: List[bool] = Field(default_factory=list)
    user_grade: int = 0
    created_at: Optional[datetime.datetime] = None
    branch_id: Optional[str] = None
    branches: Optional[List[str]] = None
    vision_support: bool = True
    
    @field_validator('user_grade', mode='before')
    def provide_default_grade(cls, value):
        return value if value is not None else 0

class MessageContentUpdate(BaseModel):
    content: str

class MessageUpdateWithImages(BaseModel):
    content: str
    kept_images_b64: List[str] = Field(default_factory=list)
    new_images_b64: List[str] = Field(default_factory=list)

class DiscussionImageAddRequest(BaseModel):
    image_b64: str

class DiscussionImageUpdateResponse(BaseModel):
    discussion_id: str
    zone: str
    discussion_images: List[str]
    active_discussion_images: List[bool]

class ManualMessageCreate(BaseModel):
    content: str
    sender_type: str
    parent_message_id: Optional[str] = None

class MessageGradeUpdate(BaseModel):
    change: int
    @field_validator('change')
    def change_must_be_one_or_minus_one(cls, value):
        if value not in [1, -1]:
            raise ValueError('Grade change must be 1 or -1')
        return value

class DiscussionExportRequest(BaseModel):
    discussion_ids: Optional[List[str]] = None

class ExportData(BaseModel):
    exported_by_user: str
    export_timestamp: str
    application_version: str
    user_settings_at_export: Dict[str, Optional[Any]]
    datastores_info: Dict[str, Any] = Field(default_factory=dict)
    personalities_info: Dict[str, Any] = Field(default_factory=dict)
    discussions: List[Dict[str, Any]]

class DiscussionImportRequest(BaseModel):
    discussion_ids_to_import: List[str]

class DiscussionSendRequest(BaseModel):
    discussion_id: str
    target_username: constr(min_length=3, max_length=50)

class MessageCodeExportRequest(BaseModel):
    content: str
    discussion_title: Optional[str] = "discussion"

class DiscussionShareRequest(BaseModel):
    target_user_id: int
    permission_level: str = "view"

    @field_validator('permission_level')
    def permission_level_must_be_valid(cls, value):
        if value not in ["view", "interact"]:
            raise ValueError("Invalid permission level")
        return value

class SharedDiscussionInfo(BaseModel):
    share_id: int
    discussion_id: str
    discussion_title: str
    permission_level: str
    shared_at: datetime.datetime
    owner_id: int
    owner_username: str
    owner_icon: Optional[str] = None
    shared_with_user_id: int
    shared_with_username: str
    shared_with_user_icon: Optional[str] = None

class PaginatedDiscussionInfo(PaginatedResponse[DiscussionInfo]):
    pass

class PaginatedSharedDiscussionInfo(PaginatedResponse[SharedDiscussionInfo]):
    pass

class PaginatedMessageOutput(PaginatedResponse[MessageOutput]):
    pass

class ArtefactCreateManual(BaseModel):
    title: constr(min_length=1)
    content: str = ""
    images_b64: List[str] = Field(default_factory=list)

class ArtefactUpdate(BaseModel):
    new_content: str
    new_images_b64: List[str] = Field(default_factory=list)
    kept_images_b64: List[str] = Field(default_factory=list)
    version: Optional[int] = None
    update_in_place: bool = False

class MessageExportPayload(BaseModel):
    format: str
class UrlImportRequest(BaseModel):
    url: str
class ArtefactAndDataZoneUpdateResponse(BaseModel):
    discussion_data_zone: str
    artefacts: List[ArtefactInfo]
    discussion_data_zone_tokens: int