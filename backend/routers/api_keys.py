# backend/routers/api_keys.py
import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database_setup import get_db, OpenAIAPIKey as DBAPIKey, User as DBUser
from backend.models import UserAuthDetails, APIKeyCreate, APIKeyPublic, NewAPIKeyResponse
from backend.security import generate_api_key, hash_api_key
from backend.session import get_current_active_user
from backend.settings import settings

api_keys_router = APIRouter(
    prefix="/api/api-keys",
    tags=["API Keys"],
    dependencies=[Depends(get_current_active_user)]
)

@api_keys_router.get("", response_model=List[APIKeyPublic])
def get_user_api_keys(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lists all API keys for the currently authenticated user.
    """
    if not settings.get("openai_api_service_enabled", False):
        raise HTTPException(status_code=403, detail="OpenAI API service is not enabled by the administrator.")
    
    keys = db.query(DBAPIKey).filter(DBAPIKey.user_id == current_user.id).all()
    return keys

@api_keys_router.post("", response_model=NewAPIKeyResponse, status_code=201)
def create_new_api_key(
    key_data: APIKeyCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Creates a new API key for the user. The full key is only returned once.
    """
    if not settings.get("openai_api_service_enabled", False):
        raise HTTPException(status_code=403, detail="OpenAI API service is not enabled by the administrator.")

    # Check if an alias already exists for this user
    existing_key = db.query(DBAPIKey).filter_by(user_id=current_user.id, alias=key_data.alias).first()
    if existing_key:
        raise HTTPException(status_code=400, detail="An API key with this alias already exists.")

    full_key, key_prefix = generate_api_key()
    hashed_key = hash_api_key(full_key)

    new_db_key = DBAPIKey(
        user_id=current_user.id,
        alias=key_data.alias,
        key_prefix=key_prefix,
        key_hash=hashed_key
    )
    
    db.add(new_db_key)
    db.commit()
    db.refresh(new_db_key)

    return NewAPIKeyResponse(
        id=new_db_key.id,
        alias=new_db_key.alias,
        created_at=new_db_key.created_at,
        last_used_at=new_db_key.last_used_at,
        key_prefix=new_db_key.key_prefix,
        full_key=full_key  # Return the full key just this once
    )

@api_keys_router.delete("/{key_id}", status_code=204)
def delete_api_key(
    key_id: int,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Deletes an API key by its ID.
    """
    key_to_delete = db.query(DBAPIKey).filter_by(id=key_id).first()

    if not key_to_delete:
        raise HTTPException(status_code=404, detail="API key not found.")

    if key_to_delete.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this API key.")

    db.delete(key_to_delete)
    db.commit()
    
    return None