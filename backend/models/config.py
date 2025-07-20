from pydantic import BaseModel
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