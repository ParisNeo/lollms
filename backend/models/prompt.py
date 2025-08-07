# backend/models/prompt.py
from pydantic import BaseModel, constr
from typing import Optional, List

class PromptBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    content: str
    category: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    version: Optional[str] = None
    repository: Optional[str] = None
    folder_name: Optional[str] = None

class PromptCreate(PromptBase):
    pass

class PromptUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=100)] = None
    content: Optional[str] = None
    category: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    version: Optional[str] = None

class PromptPublic(PromptBase):
    id: str
    update_available: bool = False
    repo_version: Optional[str] = None

    class Config:
        from_attributes = True

class PromptShareRequest(BaseModel):
    prompt_content: str
    target_username: constr(min_length=3, max_length=50)

class PromptsExport(BaseModel):
    prompts: List[PromptBase]

class PromptsImport(BaseModel):
    prompts: List[PromptBase]

class GeneratePromptRequest(BaseModel):
    prompt: constr(min_length=10)