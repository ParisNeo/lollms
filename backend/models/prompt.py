from pydantic import BaseModel, constr
from typing import Optional

class PromptBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    content: str

class PromptCreate(PromptBase):
    pass

class PromptUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=100)] = None
    content: Optional[str] = None

class PromptPublic(PromptBase):
    id: str

    class Config:
        from_attributes = True

class PromptShareRequest(BaseModel):
    prompt_content: str
    target_username: constr(min_length=3, max_length=50)