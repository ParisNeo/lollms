# backend/models/image_studio.py
import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class UserImagePublic(BaseModel):
    id: str
    filename: str
    prompt: Optional[str] = None
    model: Optional[str] = None
    created_at: datetime.datetime
    
    class Config:
        from_attributes = True

class UserImageUpdate(BaseModel):
    prompt: Optional[str] = None

class ImageGenerationRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    n: int = Field(default=1, ge=1, le=4)
    size: Optional[str] = "1024x1024"

class ImageEditRequest(BaseModel):
    image_ids: List[str]
    prompt: str
    model: Optional[str] = None
    mask: Optional[str] = None # Base64 encoded mask image

class MoveImageToDiscussionRequest(BaseModel):
    discussion_id: str