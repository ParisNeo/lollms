# backend/models/voice.py
from pydantic import BaseModel, Field
from typing import Optional, Dict
import datetime

class UserVoiceBase(BaseModel):
    alias: str = Field(..., min_length=1, max_length=100)
    language: str = Field(..., min_length=2, max_length=10)
    pitch: float = Field(1.0, gt=0, le=2.0)
    speed: float = Field(1.0, gt=0, le=3.0)
    gain: float = Field(0.0, ge=-20.0, le=20.0)
    reverb_params: Optional[Dict] = None

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
    speed: Optional[float] = 1.0
    gain: Optional[float] = 0.0
    reverb_delay: Optional[int] = 0
    reverb_attenuation: Optional[float] = 0.0