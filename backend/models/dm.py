import datetime
from typing import Optional
from pydantic import BaseModel, Field, constr

class DirectMessageBase(BaseModel):
    content: constr(min_length=1)

class DirectMessageCreate(DirectMessageBase):
    receiver_user_id: int = Field(..., alias='receiverUserId')
    image_references_json: Optional[str] = None
    class Config:
        populate_by_name = True

class DirectMessagePublic(DirectMessageBase):
    id: int
    sender_id: int
    receiver_id: int
    sent_at: datetime.datetime
    read_at: Optional[datetime.datetime] = None
    sender_username: str
    receiver_username: str