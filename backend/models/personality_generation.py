from pydantic import BaseModel, constr
from typing import Optional

class GeneratePersonalityFromPromptRequest(BaseModel):
    prompt: str
    
class EnhancePromptRequest(BaseModel):
    prompt_text: str
    modification_prompt: Optional[str] = None

class EnhancePromptResponse(BaseModel):
    enhanced_prompt: str

class GenerateIconRequest(BaseModel):
    prompt: str