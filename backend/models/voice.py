from pydantic import BaseModel, Field
from typing import Optional
import datetime

class UserVoiceBase(BaseModel):
    alias: str = Field(..., min_length=1, max_length=100)
    language: str = Field(..., min_length=2, max_length=10)
    pitch: float = Field(1.0, gt=0, le=2.0)

class UserVoiceCreate(UserVoiceBase):
    pass

class UserVoiceUpdate(UserVoiceBase):
    pass

class UserVoicePublic(UserVoiceBase):
    id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

class TestTTSRequest(BaseModel):
    text: str
    voice_id: str
    pitch: Optional[float] = 1.0