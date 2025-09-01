import datetime
from pydantic import BaseModel, constr
from backend.db.base import FriendshipStatus
from typing import Optional

class FriendshipBase(BaseModel):
    pass

class FriendRequestCreate(BaseModel):
    target_username: constr(min_length=3, max_length=50)

class FriendshipAction(BaseModel):
    action: str

class FriendPublic(BaseModel):
    id: int
    username: str
    icon: Optional[str] = None
    friendship_id: int
    status_with_current_user: FriendshipStatus
    class Config:
        from_attributes = True

class FriendshipRequestPublic(BaseModel):
    friendship_id: int
    requesting_user_id: int
    requesting_username: str
    requested_at: datetime.datetime
    status: FriendshipStatus
    class Config:
        from_attributes = True