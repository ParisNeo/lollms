from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

class FlowNodeDefBase(BaseModel):
    name: str
    label: str
    description: Optional[str] = None
    color: str = "bg-gray-100 border-gray-500"
    inputs: List[Dict[str, Any]] = []
    outputs: List[Dict[str, Any]] = []
    code: str
    class_name: str = "CustomNode"

class FlowNodeDefCreate(FlowNodeDefBase):
    pass

class FlowNodeDefPublic(FlowNodeDefBase):
    id: str
    is_public: bool
    created_at: datetime

    class Config:
        from_attributes = True

# ... (Previous FlowBase, etc.)
class FlowBase(BaseModel):
    name: str
    description: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=lambda: {"nodes": [], "edges": []})

class FlowCreate(FlowBase):
    pass

class FlowUpdate(FlowBase):
    pass

class FlowPublic(FlowBase):
    id: str
    owner_user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class FlowExecuteRequest(BaseModel):
    flow_id: str
    inputs: Optional[Dict[str, Any]] = None
