import datetime
from pydantic import BaseModel, constr, ConfigDict
from backend.db.base import FriendshipStatus
from typing import Optional

class FriendshipBase(BaseModel):
    pass

class FriendRequestCreate(BaseModel):
    target_username: constr(min_length=3, max_length=50)

class FriendshipAction(BaseModel):
    action: str

class FriendPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    icon: Optional[str] = None
    friendship_id: int
    status_with_current_user: FriendshipStatus
    mutual_friends_count: Optional[int] = 0
    status_message: Optional[str] = None

class FriendshipRequestPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    friendship_id: int
    requesting_user_id: int
    requesting_username: str
    requested_at: datetime.datetime
    status: FriendshipStatus
