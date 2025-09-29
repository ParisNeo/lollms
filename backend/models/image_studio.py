# backend/models/image_studio.py
import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ImageStudioGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model_name: str = Field(..., description="Full model ID, e.g., 'tti_binding/model_name'")
    size: Optional[str] = Field(None, description="Image resolution, e.g., '1024x1024'")
    quality: Optional[str] = Field(None, description="Quality setting, e.g., 'standard', 'hd'")
    style: Optional[str] = Field(None, description="Style preset, e.g., 'vivid', 'natural'")
    # Additional optional parameters
    steps: Optional[int] = Field(None, ge=1)
    sampler_name: Optional[str] = None
    cfg_scale: Optional[float] = Field(None, ge=0)
    seed: Optional[int] = Field(None, ge=0)

class ImageFilePublic(BaseModel):
    file_name: str = Field(..., description="The unique file name on the server.")
    image_url: str = Field(..., description="The accessible URL for the image.")
    timestamp: datetime.datetime = Field(..., description="Creation/modification timestamp.")
    
    class Config:
        from_attributes = True

class ImageStudioSettings(BaseModel):
    # This will typically mirror the model's parameters and be retrieved from API/store
    parameters: List[Dict[str, Any]] = Field(default_factory=list)