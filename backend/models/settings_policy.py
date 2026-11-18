# backend/models/settings_policy.py
"""
Pydantic contracts for the admin Settings Policy panel.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PolicyField(BaseModel):
    """Metadata for a governable field, used to render the admin panel."""
    field_name: str
    label: str
    category: str
    type: str  # "boolean" | "int" | "float" | "string" | "enum" | "json"
    choices: Optional[List[str]] = None
    description: str = ""


class PolicyFieldState(BaseModel):
    """Current policy for a single field."""
    field_name: str
    locked: bool = False
    forced: bool = False
    forced_value: Optional[Any] = None


class PolicyFieldChange(BaseModel):
    """Desired policy change for a single field.

    Any field left ``None`` is untouched. To clear a lock/force, send
    ``locked=False``/``forced=False`` explicitly.
    """
    locked: Optional[bool] = None
    forced: Optional[bool] = None
    forced_value: Optional[Any] = None


class SettingsPolicyUpdateRequest(BaseModel):
    """Bulk update payload: one entry per field to change."""
    policies: Dict[str, PolicyFieldChange] = Field(default_factory=dict)


class SettingsPolicyResponse(BaseModel):
    """Full snapshot returned by GET/PUT."""
    fields: List[PolicyField] = Field(default_factory=list)
    policies: Dict[str, PolicyFieldState] = Field(default_factory=dict)


class UserPolicySummaryResponse(BaseModel):
    """Non-admin view: current user's effective field policies (lock/force)."""
    policies: Dict[str, PolicyFieldState] = Field(default_factory=dict)