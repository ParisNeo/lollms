from pydantic import BaseModel, constr
from typing import Optional
class GeneratePersonalityFromPromptRequest(BaseModel):
    prompt: constr(min_length=10)
    
class EnhancePromptRequest(BaseModel):
    prompt_text: str
    modification_prompt: Optional[str] = None

class EnhancePromptResponse(BaseModel):
    enhanced_prompt: str
