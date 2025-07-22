from typing import Optional
from pydantic import BaseModel, constr

class GeneratePersonalityFromPromptRequest(BaseModel):
    prompt: constr(min_length=10)

class EnhancePromptRequest(BaseModel):
    prompt_text: str
    custom_instruction: Optional[str] = None