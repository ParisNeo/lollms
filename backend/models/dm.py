import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, constr, ConfigDict

class DirectMessageBase(BaseModel):
    content: str = Field(..., min_length=1)

class DirectMessageCreate(DirectMessageBase):
    model_config = ConfigDict(populate_by_name=True)
    receiver_user_id: Optional[int] = Field(None, alias='receiverUserId')
    conversation_id: Optional[int] = Field(None, alias='conversationId')
    reply_to_id: Optional[int] = Field(None, alias='replyToId')

class MessageReactionRequest(BaseModel):
    emoji: str = Field(..., min_length=1, max_length=10)

class BulkDeleteMessagesRequest(BaseModel):
    message_ids: List[int]

class CleanConversationRequest(BaseModel):
    days: Optional[int] = None
    only_my_messages: bool = False

class TypingSignalRequest(BaseModel):
    target_id: int
    is_group: bool = False

class CreateGroupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    participant_ids: List[int]

class AddMemberRequest(BaseModel):
    user_id: int

class ConversationMemberPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    username: str
    icon: Optional[str] = None

class ConversationPublic(BaseModel):
    id: int
    name: Optional[str] = None
    is_group: bool
    last_message: Optional[str] = None
    last_message_at: Optional[datetime.datetime] = None
    unread_count: int = 0
    partner_user_id: Optional[int] = None
    partner_username: Optional[str] = None
    partner_icon: Optional[str] = None
    members: List[ConversationMemberPublic] = []

class DirectMessagePublic(DirectMessageBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sender_id: int
    receiver_id: Optional[int] = None
    conversation_id: Optional[int] = None
    sent_at: datetime.datetime
    read_at: Optional[datetime.datetime] = None
    sender_username: str
    receiver_username: Optional[str] = None
    sender_icon: Optional[str] = None
    image_references: Optional[List[str]] = None
    media: Optional[List[Dict[str, Any]]] = None
    reply_to_id: Optional[int] = None
    reply_to_content: Optional[str] = None
    reply_to_sender: Optional[str] = None
    reactions: Optional[Dict[str, List[int]]] = None
    is_ai_generated: bool = False
