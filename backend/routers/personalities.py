# Standard Library Imports
import os
import shutil
import uuid
import json
from pathlib import Path
from typing import List, Dict, Optional, Any, cast, Union, Tuple, AsyncGenerator
import datetime
import asyncio
import threading
import traceback
import io

# Third-Party Imports
import toml
import yaml
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
    File,
    UploadFile,
    Form,
    APIRouter,
    Response,
    Query,
    BackgroundTasks
)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import (
    HTMLResponse,
    StreamingResponse,
    JSONResponse,
    FileResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, constr, field_validator, validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import (
    or_, and_ # Add this line
)
from dataclasses import dataclass, field as dataclass_field
from werkzeug.utils import secure_filename
from pydantic import BaseModel, Field, constr, field_validator, validator # Ensure these are imported
import datetime # Ensure datetime is imported

from backend.database_setup import Personality as DBPersonality # Add this import at the top of main.py

# Local Application Imports
from backend.database_setup import (
    User as DBUser,
    UserStarredDiscussion,
    UserMessageGrade,
    FriendshipStatus,Friendship, 
    DataStore as DBDataStore,
    SharedDataStoreLink as DBSharedDataStoreLink,
    init_database,
    get_db,
    hash_password,
    DATABASE_URL_CONFIG_KEY,
)
from lollms_client import (
    LollmsClient,
    MSG_TYPE,
    LollmsDiscussion as LollmsClientDiscussion,
    ELF_COMPLETION_FORMAT, # For client params
)

# safe_store is expected to be installed
try:
    import safe_store
    from safe_store import (
        LogLevel as SafeStoreLogLevel,
    )
except ImportError:
    print(
        "WARNING: safe_store library not found. RAG features will be disabled. Install with: pip install safe_store[all]"
    )
    safe_store = None
    SafeStoreLogLevel = None

# --- Pydantic Models for API ---
from backend.models import (
UserLLMParams,
UserAuthDetails,
UserCreateAdmin,
UserPasswordResetAdmin,UserPasswordChange,
UserPublic,
DiscussionInfo,
DiscussionTitleUpdate,
DiscussionRagDatastoreUpdate,MessageOutput,
MessageContentUpdate,
MessageGradeUpdate,
SafeStoreDocumentInfo,
DiscussionExportRequest,
ExportData,
DiscussionImportRequest,
DiscussionSendRequest,
DataStoreBase,
DataStoreCreate,
DataStorePublic,
DataStoreShareRequest,
PersonalityBase,
PersonalityCreate,
PersonalityUpdate,
PersonalityPublic,
UserUpdate,
FriendshipBase,
FriendRequestCreate,
FriendshipAction,
FriendPublic,
FriendshipRequestPublic,
PersonalitySendRequest,

DirectMessagePublic,
DirectMessageCreate
)
from backend.config import (
    TEMP_UPLOADS_DIR_NAME
)
from backend.session import (
    get_current_active_user,
    get_current_admin_user,
    get_current_db_user,
    get_datastore_db_path,
    get_db, get_safe_store_instance,
    get_user_data_root, get_user_datastore_root_path,
    get_user_discussion, get_user_discussion_assets_path,
    get_user_discussion_path,
    get_user_lollms_client,
    get_user_temp_uploads_path,
    _load_user_discussions,
    save_user_discussion,
    
    message_grade_lock,
    user_sessions,
    )
from backend.config import (LOLLMS_CLIENT_DEFAULTS, SAFE_STORE_DEFAULTS)
from backend.discussion import (AppLollmsDiscussion)

security = HTTPBasic()


# --- FastAPI Router for Personalities ---
personalities_router = APIRouter(prefix="/api/personalities", tags=["Personalities"])

def get_personality_public_from_db(db_personality: DBPersonality, owner_username: Optional[str] = None) -> PersonalityPublic:
    """Helper to convert DBPersonality to PersonalityPublic, fetching owner username if needed."""
    if owner_username is None and db_personality.owner_user_id and db_personality.owner:
        owner_username = db_personality.owner.username
    elif owner_username is None and db_personality.owner_user_id and not db_personality.owner:
        # This case should be rare if relationships are loaded, but as a fallback:
        # db = next(get_db()) # Avoid creating new session if possible
        # owner = db.query(DBUser.username).filter(DBUser.id == db_personality.owner_user_id).scalar()
        # owner_username = owner if owner else "Unknown"
        # db.close()
        # For simplicity, if owner not loaded, it will be None. Caller should ensure owner is loaded.
        pass


    return PersonalityPublic(
        id=db_personality.id,
        name=db_personality.name,
        category=db_personality.category,
        author=db_personality.author,
        description=db_personality.description,
        prompt_text=db_personality.prompt_text,
        disclaimer=db_personality.disclaimer,
        script_code=db_personality.script_code,
        icon_base64=db_personality.icon_base64,
        created_at=db_personality.created_at,
        updated_at=db_personality.updated_at,
        is_public=db_personality.is_public,
        owner_username=owner_username
    )

@personalities_router.post("", response_model=PersonalityPublic, status_code=201)
async def create_personality(
    personality_data: PersonalityCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> PersonalityPublic:
    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Check for name conflict for this user
    existing_personality = db.query(DBPersonality).filter(
        DBPersonality.owner_user_id == db_user.id,
        DBPersonality.name == personality_data.name
    ).first()
    if existing_personality:
        raise HTTPException(status_code=400, detail=f"You already have a personality named '{personality_data.name}'.")

    # If admin tries to create a public personality
    owner_id_for_new_pers = db_user.id
    if personality_data.is_public and current_user.is_admin:
        # Admin can create a truly public (system) personality with no owner,
        # or a public personality owned by themselves.
        # For simplicity, let's assume admin-created public personalities are system-level (owner_user_id = None)
        # Or, if you want admin to "own" public ones they create:
        # owner_id_for_new_pers = db_user.id
        # For truly public/system, set owner_id_for_new_pers = None
        # Let's make admin-created public personalities owned by them for now, simpler.
        pass # is_public will be set from personality_data
    elif personality_data.is_public and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only administrators can create public personalities.")
    
    db_personality = DBPersonality(
        **personality_data.model_dump(exclude={"is_public"}), # Exclude is_public if handled separately
        owner_user_id=owner_id_for_new_pers, # User owns their created personalities
        is_public=personality_data.is_public if current_user.is_admin else False # User-created are private
    )

    try:
        db.add(db_personality)
        db.commit()
        db.refresh(db_personality)
        return get_personality_public_from_db(db_personality, current_user.username)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Personality name conflict (race condition).")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@personalities_router.get("/my", response_model=List[PersonalityPublic])
async def get_my_personalities(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[PersonalityPublic]:
    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    owned_personalities_db = db.query(DBPersonality).filter(DBPersonality.owner_user_id == db_user.id).order_by(DBPersonality.name).all()
    return [get_personality_public_from_db(p, current_user.username) for p in owned_personalities_db]

@personalities_router.get("/public", response_model=List[PersonalityPublic])
async def get_public_personalities(
    db: Session = Depends(get_db)
    # No auth needed to view public personalities, but could be added if desired
) -> List[PersonalityPublic]:
    # Load owner relationship to get owner_username
    public_personalities_db = db.query(DBPersonality).options(joinedload(DBPersonality.owner)).filter(DBPersonality.is_public == True).order_by(DBPersonality.category, DBPersonality.name).all()
    return [get_personality_public_from_db(p) for p in public_personalities_db]


@personalities_router.get("/{personality_id}", response_model=PersonalityPublic)
async def get_personality(
    personality_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user), # Auth to check ownership for non-public
    db: Session = Depends(get_db)
) -> PersonalityPublic:
    db_personality = db.query(DBPersonality).options(joinedload(DBPersonality.owner)).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user: # Should not happen if current_user is valid
        raise HTTPException(status_code=404, detail="Requesting user not found.")

    is_owner = (db_personality.owner_user_id == db_user.id)

    if not db_personality.is_public and not is_owner:
        raise HTTPException(status_code=403, detail="You do not have permission to view this personality.")
    
    return get_personality_public_from_db(db_personality)


@personalities_router.put("/{personality_id}", response_model=PersonalityPublic)
async def update_personality(
    personality_id: str,
    personality_data: PersonalityUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> PersonalityPublic:
    db_personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    is_owner = (db_personality.owner_user_id == db_user.id)

    if not is_owner and not current_user.is_admin: # Only owner or admin can update
        raise HTTPException(status_code=403, detail="You do not have permission to update this personality.")
    
    # If admin is updating a personality not owned by them, they can change its public status.
    # If user is updating their own, they cannot make it public unless they are also admin.
    if personality_data.is_public is not None:
        if not current_user.is_admin:
            # Non-admin trying to change public status of their own personality
            if is_owner and personality_data.is_public != db_personality.is_public:
                 raise HTTPException(status_code=403, detail="Only administrators can change the public status of a personality.")
        # If admin, they can change is_public for any personality
        # If it's an admin updating their own, they can change it.
        # If it's an admin updating someone else's, they can change it.
        # If it's an admin updating a system (owner_user_id=None) personality, they can change it.
        if current_user.is_admin:
            db_personality.is_public = personality_data.is_public
    
    update_data = personality_data.model_dump(exclude_unset=True, exclude={"is_public"}) # is_public handled above

    if "name" in update_data and update_data["name"] != db_personality.name:
        # Check for name conflict for this user if it's their personality
        # Or global conflict if it's a public personality being renamed by admin
        owner_id_for_check = db_personality.owner_user_id
        if db_personality.is_public and owner_id_for_check is None: # System personality
             existing_conflict = db.query(DBPersonality).filter(
                DBPersonality.owner_user_id == None, # Check among system personalities
                DBPersonality.name == update_data["name"],
                DBPersonality.id != personality_id
            ).first()
        else: # User-owned or admin-owned public
            existing_conflict = db.query(DBPersonality).filter(
                DBPersonality.owner_user_id == owner_id_for_check,
                DBPersonality.name == update_data["name"],
                DBPersonality.id != personality_id
            ).first()
        if existing_conflict:
            raise HTTPException(status_code=400, detail=f"A personality named '{update_data['name']}' already exists.")

    for field, value in update_data.items():
        if hasattr(db_personality, field):
            setattr(db_personality, field, value)
    
    try:
        db.commit()
        db.refresh(db_personality)
        # Reload owner for username if it was an admin editing someone else's
        db.refresh(db_personality, attribute_names=['owner']) 
        return get_personality_public_from_db(db_personality)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Personality name conflict (race condition).")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@personalities_router.delete("/{personality_id}", status_code=200)
async def delete_personality(
    personality_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    db_personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    is_owner = (db_personality.owner_user_id == db_user.id)

    if not is_owner and not (current_user.is_admin and db_personality.is_public):
        # User can delete their own.
        # Admin can delete any public personality (even if owned by another user, or system-owned).
        raise HTTPException(status_code=403, detail="You do not have permission to delete this personality.")

    # If this personality is active for any user, set their active_personality_id to None
    users_with_this_active_personality = db.query(DBUser).filter(DBUser.active_personality_id == personality_id).all()
    for user_to_update in users_with_this_active_personality:
        user_to_update.active_personality_id = None
        # Clear from session if user is active
        if user_to_update.username in user_sessions:
            user_sessions[user_to_update.username]["active_personality_id"] = None
            user_sessions[user_to_update.username]["active_personality_prompt"] = None
            # If this affects the current_user, their session will be updated.
            # If it affects other users, their session will update on their next /me or relevant action.

    try:
        db.delete(db_personality)
        db.commit()
        return {"message": f"Personality '{db_personality.name}' deleted successfully."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@personalities_router.post("/{personality_id}/send", response_model=PersonalityPublic)
async def send_personality_to_user(
    personality_id: str,
    send_request: PersonalitySendRequest,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> PersonalityPublic:
    original_personality = db.query(DBPersonality).filter(
        DBPersonality.id == personality_id,
        # User can send their own, or an admin can send any public one
        or_(
            DBPersonality.owner_user_id == current_db_user.id,
            and_(DBPersonality.is_public == True, current_db_user.is_admin == True)
        )
    ).first()

    if not original_personality:
        raise HTTPException(status_code=404, detail="Personality not found or you don't have permission to send it.")

    target_user = db.query(DBUser).filter(DBUser.username == send_request.target_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Target user '{send_request.target_username}' not found.")
    
    if target_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="Cannot send a personality to yourself.")

    # Check if target user already has a personality with the same name
    existing_target_pers = db.query(DBPersonality).filter(
        DBPersonality.owner_user_id == target_user.id,
        DBPersonality.name == original_personality.name
    ).first()
    if existing_target_pers:
        raise HTTPException(status_code=400, detail=f"User '{target_user.username}' already has a personality named '{original_personality.name}'.")

    copied_personality = DBPersonality(
        name=original_personality.name, # Or prompt for a new name if desired
        category=original_personality.category,
        author=original_personality.author, # Or set to sender: current_db_user.username
        description=original_personality.description,
        prompt_text=original_personality.prompt_text,
        disclaimer=original_personality.disclaimer,
        script_code=original_personality.script_code,
        icon_base64=original_personality.icon_base64,
        owner_user_id=target_user.id, # New owner is the target user
        is_public=False # Copies are private to the recipient
    )
    db.add(copied_personality)
    try:
        db.commit()
        db.refresh(copied_personality)
        return get_personality_public_from_db(copied_personality, target_user.username)
    except IntegrityError: # Should be caught by name check above
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to send personality due to a name conflict for the target user.")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error sending personality: {str(e)}")
