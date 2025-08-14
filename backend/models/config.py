# backend/models/config.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class GlobalConfigPublic(BaseModel):
    key: str
    value: Any
    type: str
    description: Optional[str] = None
    category: str

class GlobalConfigUpdate(BaseModel):
    configs: Dict[str, Any]

class ForceSettingsPayload(BaseModel):
    model_name: str
    context_size: Optional[int] = None

class ModelDisplayModeUpdate(BaseModel):
    model_display_mode: str = Field(..., description="The display mode for models in selectors: 'mixed', 'aliased', 'original'")