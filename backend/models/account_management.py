# backend/models/account_management.py
"""Pydantic schemas for the mesh / agent account management endpoints.

Kept in a dedicated module so the existing user/admin schemas are untouched.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from backend.account_types import ALL_ACCOUNT_TYPES, normalize_account_type


class ServiceAccountCreate(BaseModel):
    """Payload to create a ``mesh`` or ``agent`` service principal.

    No password/email is accepted: these principals are API-only. The username
    is the single stable identity used everywhere (quota, metrics, audit).
    """

    username: str = Field(..., min_length=3, max_length=64)
    account_type: str = Field(..., description="'mesh' or 'agent'")
    display_name: Optional[str] = Field(
        default=None, max_length=128, description="Human label, e.g. 'Paris Node'"
    )
    description: Optional[str] = Field(default=None, max_length=1024)

    # Optional pre-provisioned quota ceilings (0/None = unlimited, inherited
    # from global defaults exactly like a normal user).
    quota_input_tokens: Optional[int] = Field(default=None, ge=0)
    quota_output_tokens: Optional[int] = Field(default=None, ge=0)
    quota_period: Optional[str] = Field(
        default=None, description="e.g. 'daily', 'monthly' (validated server-side)"
    )

    @field_validator("account_type")
    @classmethod
    def _validate_type(cls, value: str) -> str:
        normalized = normalize_account_type(value)
        if normalized not in ("mesh", "agent"):
            raise ValueError(
                f"account_type must be one of {ALL_ACCOUNT_TYPES} excluding 'human'"
            )
        return normalized


class ServiceAccountRead(BaseModel):
    id: int
    username: str
    account_type: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class IssuedApiKey(BaseModel):
    """A freshly-minted API key. ``key`` is only ever returned ONCE here."""

    id: int
    name: str
    key: str
    user_id: int
    account_username: str
    created_at: Optional[datetime] = None


class ServiceAccountWithKey(BaseModel):
    account: ServiceAccountRead
    api_key: IssuedApiKey


class ServiceAccountUsage(BaseModel):
    """Lightweight consumption summary for a service principal."""

    user_id: int
    username: str
    account_type: str
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0