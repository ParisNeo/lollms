# backend/routers/admin/account_management.py
"""Admin endpoints for mesh / agent service principals.

Mesh accounts represent peer LoLLMs instances (corporate consumption buckets);
agent accounts represent AI/bot identities. Both are API-only: they are created
here with a ready-to-use API key, are excluded from interactive login, and are
metered through the exact same quota + ``GenerationMetric`` pipeline as human
users (see ``backend/token_quota.py``).

Endpoints:
    * GET    /api/admin/accounts                — list service principals
    * POST   /api/admin/accounts                — create one (+ first API key)
    * POST   /api/admin/accounts/{id}/api-keys  — issue an additional API key
    * GET    /api/admin/accounts/{id}/usage     — consumption summary
    * DELETE /api/admin/accounts/{id}           — delete (and its keys)
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.account_types import MESH, AGENT, normalize_account_type
from backend.api_key_provisioning import provision_api_key
from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.generation_metric import GenerationMetric
from backend.models.account_management import (
    ServiceAccountCreate,
    ServiceAccountRead,
    ServiceAccountWithKey,
    ServiceAccountUsage,
)
from backend.models.user import UserAuthDetails
from backend.session import get_current_admin_user

account_management_router = APIRouter(
    prefix="/api/admin/accounts",
    tags=["Admin - Service Accounts (Mesh / Agents)"],
)

# Bcrypt convention: hash inputs longer than 72 bytes are truncated by the
# algorithm. Slicing explicitly keeps behavior deterministic across backends.
_PASSWORD_HASH_INPUT_LIMIT = 72


def _to_read(user: DBUser) -> ServiceAccountRead:
    return ServiceAccountRead(
        id=user.id,
        username=user.username,
        account_type=getattr(user, "account_type", "human") or "human",
        display_name=getattr(user, "first_name", None),
        description=getattr(user, "family_name", None),
        is_active=bool(user.is_active),
        created_at=getattr(user, "created_at", None),
        last_activity_at=getattr(user, "last_activity_at", None),
    )


def _get_service_account_or_404(db: Session, user_id: int) -> DBUser:
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Account not found.")
    if normalize_account_type(getattr(user, "account_type", "human")) not in (MESH, AGENT):
        raise HTTPException(
            status_code=400,
            detail="This endpoint manages service principals only (mesh/agent).",
        )
    return user


@account_management_router.get("", response_model=List[ServiceAccountRead])
def list_service_accounts(
    db: Session = Depends(get_db),
    _admin: UserAuthDetails = Depends(get_current_admin_user),
):
    rows = (
        db.query(DBUser)
        .filter(DBUser.account_type.in_((MESH, AGENT)))
        .order_by(DBUser.id.desc())
        .all()
    )
    return [_to_read(u) for u in rows]


@account_management_router.post(
    "", response_model=ServiceAccountWithKey, status_code=status.HTTP_201_CREATED
)
def create_service_account(
    payload: ServiceAccountCreate,
    db: Session = Depends(get_db),
    _admin: UserAuthDetails = Depends(get_current_admin_user),
):
    username = payload.username.strip()
    if db.query(DBUser).filter(DBUser.username == username).first():
        raise HTTPException(status_code=409, detail="Username already exists.")

    account_type = normalize_account_type(payload.account_type)
    if account_type not in (MESH, AGENT):
        raise HTTPException(status_code=400, detail="account_type must be 'mesh' or 'agent'.")

    # Service principals never receive a usable password. We still store a
    # valid-looking bcrypt hash of a random, discarded secret so the NOT NULL
    # constraint on ``hashed_password`` is satisfied and no plaintext value can
    # ever authenticate. Interactive login is additionally blocked at the auth
    # layer for non-human account types.
    import secrets as _secrets
    from backend.security import get_password_hash as _hash_password
    _throwaway_password = _secrets.token_urlsafe(48)
    # Bcrypt truncates to 72 bytes; slice to stay within the limits.
    _unusable_hash = _hash_password(_throwaway_password[:_PASSWORD_HASH_INPUT_LIMIT])

    user_kwargs = dict(
        username=username,
        email=None,
        hashed_password=_unusable_hash,
        is_active=True,
        is_admin=False,
        is_moderator=False,
        first_name=payload.display_name,
        family_name=payload.description,
    )
    # Only pass ``account_type`` when the model actually declares it. This keeps
    # account creation working even if a deployment skipped the model/migration
    # step, instead of raising ``TypeError: 'account_type' is an invalid keyword``.
    if hasattr(DBUser, "account_type"):
        user_kwargs["account_type"] = account_type
    user = DBUser(**user_kwargs)
    db.add(user)
    db.commit()
    db.refresh(user)

    # Apply optional per-account quota ceilings if provided. The quota engine
    # already falls back to global defaults when these are 0/None.
    gave_quota = False
    try:
        if (
            payload.quota_input_tokens
            or payload.quota_output_tokens
            or payload.quota_period
        ):
            from backend.token_quota import set_user_quota  # local import: optional

            set_user_quota(
                db,
                user_id=user.id,
                input_tokens=payload.quota_input_tokens or 0,
                output_tokens=payload.quota_output_tokens or 0,
                period=payload.quota_period,
            )
            gave_quota = True
    except Exception:
        # Quota schema is optional; never fail account creation over it.
        gave_quota = False

    key = provision_api_key(db, user_id=user.id, name=f"{account_type}:{username}")

    return ServiceAccountWithKey(
        account=_to_read(user),
        api_key={
            "id": key["id"],
            "name": key["name"],
            "key": key["key"],
            "user_id": user.id,
            "account_username": username,
            "created_at": key["created_at"],
        },
    )


@account_management_router.post("/{user_id}/api-keys")
def issue_additional_api_key(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: UserAuthDetails = Depends(get_current_admin_user),
):
    user = _get_service_account_or_404(db, user_id)
    key = provision_api_key(
        db, user_id=user.id, name=f"{user.account_type}:{user.username}"
    )
    return {
        "id": key["id"],
        "name": key["name"],
        "key": key["key"],
        "user_id": user.id,
        "account_username": user.username,
        "created_at": key["created_at"],
    }


@account_management_router.get("/{user_id}/usage", response_model=ServiceAccountUsage)
def get_service_account_usage(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: UserAuthDetails = Depends(get_current_admin_user),
):
    user = _get_service_account_or_404(db, user_id)
    row = (
        db.query(
            func.coalesce(func.sum(GenerationMetric.total_tokens), 0),
            func.coalesce(func.sum(GenerationMetric.prompt_tokens), 0),
            func.coalesce(func.sum(GenerationMetric.completion_tokens), 0),
            func.count(GenerationMetric.id),
        )
        .filter(GenerationMetric.user_id == user.id)
        .one()
    )
    return ServiceAccountUsage(
        user_id=user.id,
        username=user.username,
        account_type=getattr(user, "account_type", "agent") or "agent",
        total_tokens=int(row[0] or 0),
        prompt_tokens=int(row[1] or 0),
        completion_tokens=int(row[2] or 0),
        calls=int(row[3] or 0),
    )


@account_management_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service_account(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: UserAuthDetails = Depends(get_current_admin_user),
):
    user = _get_service_account_or_404(db, user_id)
    # Remove owned API keys first (FK safety), then the account row.
    try:
        from backend.db.models.api_key import OpenAIAPIKey

        db.query(OpenAIAPIKey).filter(OpenAIAPIKey.user_id == user.id).delete()
    except Exception:
        pass
    db.delete(user)
    db.commit()
