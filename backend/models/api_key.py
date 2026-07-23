import datetime
from typing import Optional
from pydantic import BaseModel, constr, ConfigDict

class APIKeyBase(BaseModel):
    alias: constr(min_length=1, max_length=100)

class APIKeyCreate(APIKeyBase):
    pass

class APIKeyPublic(APIKeyBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime.datetime
    last_used_at: Optional[datetime.datetime] = None
    key_prefix: str

class NewAPIKeyResponse(APIKeyPublic):
    full_key: str
