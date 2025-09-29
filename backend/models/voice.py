# backend/models/voice.py
from pydantic import BaseModel, Field
from typing import Optional, Dict
import datetime

class ReverbParams(BaseModel):
    delay: int = Field(0, ge=0, le=200)
    attenuation: float = Field(0.0, ge=0.0, le=20.0)

class UserVoiceBase(BaseModel):
    alias: str = Field(..., min_length=1, max_length=100)
    language: str = Field(..., min_length=2, max_length=10)
    pitch: float = Field(1.0, gt=0, le=2.0)
    speed: float = Field(1.0, gt=0, le=3.0)
    gain: float = Field(0.0, ge=-20.0, le=20.0)
    reverb_params: Optional[ReverbParams] = None

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
    reverb_params: Optional[ReverbParams] = None

class ApplyEffectsRequest(BaseModel):
    audio_b64: str
    pitch: float = 1.0
    speed: float = 1.0
    gain: float = 0.0
    reverb_params: ReverbParams
    trim_start: Optional[float] = None # in seconds
    trim_end: Optional[float] = None # in seconds