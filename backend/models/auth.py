from pydantic import BaseModel, Field
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str
    email_verification_required: bool = False
    temp_token: Optional[str] = None
    email_hint: Optional[str] = None

class TokenData(BaseModel):
    username: Optional[str] = None

class VerifyEmailCodeRequest(BaseModel):
    temp_token: str = Field(..., min_length=1)
    code: str = Field(..., min_length=4, max_length=10)

class ResendVerificationCodeRequest(BaseModel):
    temp_token: str = Field(..., min_length=1)

class TestEmailRequest(BaseModel):
    to_email: str = Field(..., min_length=3)