# backend/models/files.py
from pydantic import BaseModel, Field
from typing import List

class ExtractionAndEmbeddingResponse(BaseModel):
    text_content: str
    discussion_images: List[str] = Field(default_factory=list)
    active_discussion_images: List[bool] = Field(default_factory=list)

class ContentExportRequest(BaseModel):
    content: str
    format: str