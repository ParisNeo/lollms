# backend/models/discussion.py
import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, constr, field_validator
from .shared import PaginatedResponse

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
    discussion_images: List[str] = Field(default_factory=list)
    active_discussion_images: List[bool] = Field(default_factory=list)

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

class PaginatedDiscussionInfo(PaginatedResponse[DiscussionInfo]):
    pass

class PaginatedMessageOutput(PaginatedResponse[MessageOutput]):
    pass