from pydantic import BaseModel, Field
from typing import Optional

class PersonalityPromptGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Prompt describing the persona to generate")

# Alias for backward compatibility
GeneratePersonalityFromPromptRequest = PersonalityPromptGenerateRequest

class EnhancePromptRequest(BaseModel):
    prompt_text: str
    modification_prompt: Optional[str] = None

class EnhancePromptResponse(BaseModel):
    enhanced_prompt: str

class GenerateIconRequest(BaseModel):
    prompt: str