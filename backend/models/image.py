# [UPDATE] backend/models/image.py
# backend/models/image.py
from pydantic import BaseModel, Field
from typing import Optional, List
import datetime

class UserImagePublic(BaseModel):
    id: str
    filename: str
    prompt: Optional[str] = None
    model: Optional[str] = None
    created_at: datetime.datetime
    discussion_id: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

    class Config:
        from_attributes = True

class ImageGenerationRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = ""
    model: Optional[str] = None
    n: int = Field(default=1, ge=1, le=10)
    size: Optional[str] = "1024x1024"
    width: Optional[int] = None
    height: Optional[int] = None
    seed: Optional[int] = -1
    sampler_name: Optional[str] = None
    steps: Optional[int] = None
    cfg_scale: Optional[float] = None

class MoveImageToDiscussionRequest(BaseModel):
    discussion_id: str

class ImageEditRequest(BaseModel):
    image_ids: Optional[List[str]] = None
    base_image_b64: Optional[str] = None
    prompt: str
    negative_prompt: Optional[str] = None
    mask: Optional[str] = None # base64 encoded mask
    model: Optional[str] = None
    seed: Optional[int] = -1
    sampler_name: Optional[str] = None
    steps: Optional[int] = None
    cfg_scale: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None


# Added for prompt enhancement
class ImagePromptEnhancementRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = ""
    model: Optional[str] = None
    target: str = "both"
    instructions: Optional[str] = None

class ImagePromptEnhancementResponse(BaseModel):
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None


class SaveCanvasRequest(BaseModel):
    base_image_b64: Optional[str] = None
    drawing_b64: Optional[str] = None
    prompt: str
    model: Optional[str] = None
    width: int
    height: int
    bg_color: str = "#FFFFFF"