import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, constr

class DirectMessageBase(BaseModel):
    content: constr(min_length=1)

class DirectMessageCreate(DirectMessageBase):
    receiver_user_id: Optional[int] = Field(None, alias='receiverUserId')
    conversation_id: Optional[int] = Field(None, alias='conversationId')
    class Config:
        populate_by_name = True

class CreateGroupRequest(BaseModel):
    name: str = Field(..., min_length=1)
    participant_ids: List[int]

class AddMemberRequest(BaseModel):
    user_id: int

class ConversationMemberPublic(BaseModel):
    user_id: int
    username: str
    icon: Optional[str] = None
    class Config:
        from_attributes = True

class ConversationPublic(BaseModel):
    id: int
    name: Optional[str] = None
    is_group: bool
    last_message: Optional[str] = None
    last_message_at: Optional[datetime.datetime] = None
    unread_count: int = 0
    # For 1-on-1
    partner_user_id: Optional[int] = None
    partner_username: Optional[str] = None
    partner_icon: Optional[str] = None
    # For groups
    members: List[ConversationMemberPublic] = []

class DirectMessagePublic(DirectMessageBase):
    id: int
    sender_id: int
    receiver_id: Optional[int] = None
    conversation_id: Optional[int] = None
    sent_at: datetime.datetime
    read_at: Optional[datetime.datetime] = None
    sender_username: str
    receiver_username: Optional[str] = None
    image_references: Optional[List[str]] = None

    class Config:
        from_attributes = True
