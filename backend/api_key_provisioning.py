
# backend/api_key_provisioning.py
"""Shared API-key creation used by the mesh/agent account onboarding flow.

Kept separate from ``backend/routers/api_keys.py`` so the service-principal
router can mint a key without duplicating (or risking drift with) the user
router. The hashing scheme intentionally matches the application's existing
verifier (``OpenAIAPIKey``): ``sha256`` of the raw key, with a short
human-readable prefix stored for display/audit.
"""
from __future__ import annotations

import hashlib
import secrets
from typing import Dict

from sqlalchemy.orm import Session

from backend.db.models.api_key import OpenAIAPIKey

RAW_KEY_PREFIX: str = "lollms_"
PREFIX_DISPLAY_LEN: int = 8


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_raw_key() -> str:
    return f"{RAW_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def provision_api_key(
    db: Session,
    *,
    user_id: int,
    name: str,
) -> Dict[str, object]:
    """Create and persist a new API key for ``user_id``.

    Returns a dict with the raw key (only exposed once) plus stored metadata.
    The caller is responsible for committing/refreshing if it wants a single
    transaction around user + key creation; this helper commits to keep the
    contract simple and match the existing router behaviour.
    """
    raw_key = generate_raw_key()
    prefix = raw_key[:PREFIX_DISPLAY_LEN]
    db_key = OpenAIAPIKey(
        alias=name,
        key_prefix=prefix,
        key_hash=hash_api_key(raw_key),
        user_id=user_id,
    )
    db.add(db_key)
    db.commit()
    db.refresh(db_key)
    return {
        "id": db_key.id,
        "name": db_key.alias,
        "key": raw_key,
        "prefix": prefix,
        "user_id": user_id,
        "created_at": getattr(db_key, "created_at", None),
    }
