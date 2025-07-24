from pydantic import BaseModel
from typing import Optional

class EnhancePromptRequest(BaseModel):
    prompt_text: str
    modification_prompt: Optional[str] = None

class EnhancePromptResponse(BaseModel):
    enhanced_prompt: str