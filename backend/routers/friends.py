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
    FriendshipStatus,Friendship, 
    get_db,
    get_friendship_record,
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
    get_current_db_user_from_token,
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



# --- FastAPI Router for Friendships ---
friends_router = APIRouter(prefix="/api/friends", tags=["Friends Management"])

def get_friend_public_from_friendship(friendship: Friendship, current_user_id: int) -> FriendPublic:
    """
    Helper to determine who the 'friend' is in a friendship record
    relative to the current_user_id and format it as FriendPublic.
    """
    friend_user_obj = None
    if friendship.user1_id == current_user_id:
        friend_user_obj = friendship.user2 # The other user is user2
    elif friendship.user2_id == current_user_id:
        friend_user_obj = friendship.user1 # The other user is user1
    
    if not friend_user_obj:
        # This should not happen if the friendship involves the current_user_id
        raise ValueError("Friendship record does not involve the current user.")

    return FriendPublic(
        id=friend_user_obj.id,
        username=friend_user_obj.username,
        friendship_id=friendship.id,
        status_with_current_user=friendship.status # The status of the friendship itself
    )

@friends_router.post("/request", response_model=FriendshipRequestPublic, status_code=201)
async def send_friend_request(
    request_data: FriendRequestCreate,
    current_db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> FriendshipRequestPublic:
    if current_db_user.username == request_data.target_username:
        raise HTTPException(status_code=400, detail="You cannot send a friend request to yourself.")

    target_user = db.query(DBUser).filter(DBUser.username == request_data.target_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User '{request_data.target_username}' not found.")

    # Ensure canonical order for user1_id and user2_id to prevent duplicate entries
    # (user1_id < user2_id)
    user1_id, user2_id = sorted((current_db_user.id, target_user.id))

    existing_friendship = db.query(Friendship).filter(
        Friendship.user1_id == user1_id,
        Friendship.user2_id == user2_id
    ).first()

    if existing_friendship:
        if existing_friendship.status == FriendshipStatus.ACCEPTED:
            raise HTTPException(status_code=400, detail="You are already friends with this user.")
        elif existing_friendship.status == FriendshipStatus.PENDING and existing_friendship.action_user_id == current_db_user.id:
            raise HTTPException(status_code=400, detail="You have already sent a friend request to this user.")
        elif existing_friendship.status == FriendshipStatus.PENDING and existing_friendship.action_user_id == target_user.id:
            raise HTTPException(status_code=400, detail="This user has already sent you a friend request. Please respond to it.")
        elif existing_friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and user1_id == current_db_user.id: # You blocked them
            raise HTTPException(status_code=403, detail="You have blocked this user. Unblock them to send a request.")
        elif existing_friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and user2_id == current_db_user.id: # You blocked them
             raise HTTPException(status_code=403, detail="You have blocked this user. Unblock them to send a request.")
        elif (existing_friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and user1_id == target_user.id) or \
             (existing_friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and user2_id == target_user.id): # They blocked you
            raise HTTPException(status_code=403, detail="You cannot send a friend request to this user as they have blocked you.")
        # If other statuses, potentially allow re-request or overwrite (e.g., after a decline)
        # For now, if any record exists and isn't one of the above, it's an edge case or needs specific handling.
        # Let's assume we can overwrite a previously declined/removed one by setting status to PENDING.
        existing_friendship.status = FriendshipStatus.PENDING
        existing_friendship.action_user_id = current_db_user.id # Current user is sending the request
        db_friendship_to_return = existing_friendship
    else:
        new_friendship = Friendship(
            user1_id=user1_id,
            user2_id=user2_id,
            status=FriendshipStatus.PENDING,
            action_user_id=current_db_user.id # Current user is sending the request
        )
        db.add(new_friendship)
        db_friendship_to_return = new_friendship
    
    try:
        db.commit()
        db.refresh(db_friendship_to_return)
        return FriendshipRequestPublic(
            friendship_id=db_friendship_to_return.id,
            requesting_user_id=current_db_user.id, # The one who sent the request
            requesting_username=current_db_user.username,
            requested_at=db_friendship_to_return.created_at, # Or updated_at if overwriting
            status=db_friendship_to_return.status
        )
    except IntegrityError: # Should be caught by existing_friendship check mostly
        db.rollback()
        raise HTTPException(status_code=400, detail="Friendship request conflict.")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@friends_router.get("/requests/pending", response_model=List[FriendshipRequestPublic])
async def get_pending_friend_requests(
    current_db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> List[FriendshipRequestPublic]:
    """Gets friend requests sent TO the current user that are pending."""
    pending_requests_db = db.query(Friendship).options(
        joinedload(Friendship.user1), # Eager load user1 (potential requester)
        joinedload(Friendship.user2)  # Eager load user2 (potential requester)
    ).filter(
        or_(
            and_(Friendship.user1_id == current_db_user.id, Friendship.action_user_id != current_db_user.id), # Request sent by user2 to user1
            and_(Friendship.user2_id == current_db_user.id, Friendship.action_user_id != current_db_user.id)  # Request sent by user1 to user2
        ),
        Friendship.status == FriendshipStatus.PENDING
    ).all()

    response_list = []
    for req in pending_requests_db:
        requester = req.user1 if req.user2_id == current_db_user.id else req.user2
        if requester: # Ensure requester object is loaded
            response_list.append(FriendshipRequestPublic(
                friendship_id=req.id,
                requesting_user_id=requester.id,
                requesting_username=requester.username,
                requested_at=req.updated_at, # Use updated_at as it reflects when request was made/last actioned
                status=req.status
            ))
    return response_list

@friends_router.put("/requests/{friendship_id}", response_model=FriendPublic)
async def respond_to_friend_request(
    friendship_id: int,
    response_data: FriendshipAction, # e.g., {"action": "accept"} or {"action": "reject"}
    current_db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> FriendPublic:
    friendship = db.query(Friendship).filter(Friendship.id == friendship_id).first()

    if not friendship:
        raise HTTPException(status_code=404, detail="Friend request not found.")

    # Ensure the current user is the recipient of this pending request
    is_recipient = (friendship.user1_id == current_db_user.id and friendship.action_user_id != current_db_user.id) or \
                   (friendship.user2_id == current_db_user.id and friendship.action_user_id != current_db_user.id)

    if not is_recipient or friendship.status != FriendshipStatus.PENDING:
        raise HTTPException(status_code=403, detail="Not a valid pending request for you to respond to.")

    action = response_data.action.lower()
    if action == "accept":
        friendship.status = FriendshipStatus.ACCEPTED
        friendship.action_user_id = current_db_user.id # Current user accepted
    elif action == "reject":
        # Option 1: Delete the request
        db.delete(friendship)
        db.commit()
        # Return a specific response or raise an exception that the frontend can interpret as "rejected and removed"
        # For simplicity, let's just say it's gone. The frontend won't see it in pending list.
        # Or, if you want to keep a "declined" state:
        # friendship.status = FriendshipStatus.DECLINED 
        # friendship.action_user_id = current_db_user.id
        # For now, deleting is simpler.
        raise HTTPException(status_code=200, detail="Friend request rejected and removed.") # 200 or 204
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'accept' or 'reject'.")

    try:
        db.commit()
        db.refresh(friendship)
        # Eager load related users for get_friend_public_from_friendship
        db.refresh(friendship, attribute_names=['user1', 'user2'])
        return get_friend_public_from_friendship(friendship, current_db_user.id)
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@friends_router.get("", response_model=List[FriendPublic]) # Get list of accepted friends
async def get_my_friends(
    current_db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> List[FriendPublic]:
    # Friendships where current user is user1 OR user2, and status is ACCEPTED
    friendships_db = db.query(Friendship).options(
        joinedload(Friendship.user1), joinedload(Friendship.user2)
    ).filter(
        or_(Friendship.user1_id == current_db_user.id, Friendship.user2_id == current_db_user.id),
        Friendship.status == FriendshipStatus.ACCEPTED
    ).order_by(Friendship.updated_at.desc()).all() # Or order by friend's username

    friends_list = []
    for fs in friendships_db:
        try:
            friends_list.append(get_friend_public_from_friendship(fs, current_db_user.id))
        except ValueError: # Should not happen with the query filter
            pass 
    
    # Sort by username for consistent display
    friends_list.sort(key=lambda f: f.username.lower())
    return friends_list


@friends_router.delete("/{friend_user_id_or_username}", status_code=200) # Unfriend or cancel sent request
async def remove_friend_or_cancel_request(
    friend_user_id_or_username: str,
    current_db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    other_user = None
    try:
        other_user_id = int(friend_user_id_or_username)
        other_user = db.query(DBUser).filter(DBUser.id == other_user_id).first()
    except ValueError:
        other_user = db.query(DBUser).filter(DBUser.username == friend_user_id_or_username).first()

    if not other_user:
        raise HTTPException(status_code=404, detail="Target user not found.")
    if other_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="Cannot perform this action on yourself.")

    user1_id, user2_id = sorted((current_db_user.id, other_user.id))

    friendship = db.query(Friendship).filter(
        Friendship.user1_id == user1_id,
        Friendship.user2_id == user2_id
    ).first()

    if not friendship:
        raise HTTPException(status_code=404, detail="No friendship or request found with this user.")

    action_taken = ""
    if friendship.status == FriendshipStatus.ACCEPTED:
        # Unfriend: Delete the record
        db.delete(friendship)
        action_taken = "unfriended"
    elif friendship.status == FriendshipStatus.PENDING and friendship.action_user_id == current_db_user.id:
        # Cancel sent request: Delete the record
        db.delete(friendship)
        action_taken = "friend request cancelled"
    elif friendship.status == FriendshipStatus.PENDING and friendship.action_user_id == other_user.id:
        # Reject incoming request: Delete the record (same as /requests/{id} with "reject")
        db.delete(friendship)
        action_taken = "friend request rejected"
    else:
        # E.g., trying to unfriend someone you blocked, or a non-pending/non-accepted state
        raise HTTPException(status_code=400, detail=f"Cannot perform this action on current friendship status: {friendship.status.value}")

    try:
        db.commit()
        return {"message": f"Successfully {action_taken} user '{other_user.username}'."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# --- New Block/Unblock Endpoints ---
@friends_router.put("/block/{user_id_or_username}", response_model=FriendPublic)
async def block_user(
    user_id_or_username: str,
    current_db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> FriendPublic:
    other_user = None
    try:
        other_user_id_val = int(user_id_or_username)
        other_user = db.query(DBUser).filter(DBUser.id == other_user_id_val).first()
    except ValueError:
        other_user = db.query(DBUser).filter(DBUser.username == user_id_or_username).first()

    if not other_user:
        raise HTTPException(status_code=404, detail="Target user not found.")
    if other_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="You cannot block yourself.")

    friendship = get_friendship_record(db, current_db_user.id, other_user.id)
    
    user1_id_ordered, user2_id_ordered = sorted((current_db_user.id, other_user.id))

    if not friendship:
        friendship = Friendship(
            user1_id=user1_id_ordered,
            user2_id=user2_id_ordered,
            action_user_id=current_db_user.id
        )
        db.add(friendship)
    else:
        # Check if already blocked by the other user
        if (friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and friendship.user1_id == other_user.id) or \
           (friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and friendship.user2_id == other_user.id):
            raise HTTPException(status_code=403, detail="Cannot block a user who has blocked you.")
        friendship.action_user_id = current_db_user.id


    if user1_id_ordered == current_db_user.id: # Current user is user1 in the canonical pair
        friendship.status = FriendshipStatus.BLOCKED_BY_USER1
    else: # Current user is user2 in the canonical pair
        friendship.status = FriendshipStatus.BLOCKED_BY_USER2
    
    try:
        db.commit()
        db.refresh(friendship)
        db.refresh(friendship, attribute_names=['user1', 'user2'])
        return get_friend_public_from_friendship(friendship, current_db_user.id)
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@friends_router.put("/unblock/{user_id_or_username}", response_model=FriendPublic)
async def unblock_user(
    user_id_or_username: str,
    current_db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> FriendPublic:
    other_user = None
    try:
        other_user_id_val = int(user_id_or_username)
        other_user = db.query(DBUser).filter(DBUser.id == other_user_id_val).first()
    except ValueError:
        other_user = db.query(DBUser).filter(DBUser.username == user_id_or_username).first()

    if not other_user:
        raise HTTPException(status_code=404, detail="Target user not found.")
    if other_user.id == current_db_user.id: # Should not happen if UI prevents
        raise HTTPException(status_code=400, detail="Invalid action.")

    friendship = get_friendship_record(db, current_db_user.id, other_user.id)

    if not friendship:
        raise HTTPException(status_code=404, detail="No relationship record found with this user to unblock.")

    # Check if the current user actually initiated the block
    is_blocker = (friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and friendship.user1_id == current_db_user.id) or \
                 (friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and friendship.user2_id == current_db_user.id)

    if not is_blocker:
        raise HTTPException(status_code=400, detail="You have not blocked this user, or they blocked you.")

    # Unblocking sets the status back to PENDING (or you could delete the record if no prior friendship)
    # If you want to restore previous friendship status, that's more complex (need to store pre-block status)
    # For simplicity, unblocking could mean the relationship is removed, or goes to a neutral state.
    # Let's assume unblocking removes the record, allowing for a fresh start.
    # Or, set to PENDING, with action_user being the one unblocking, effectively "offering" a re-connection.
    # For now, let's just delete the record to signify the end of the block.
    # A more nuanced approach might set it to a neutral state or revert to pre-block status.
    # Let's change this: unblocking will remove the friendship record entirely.
    # This means if they were friends before, they are no longer. They'd have to re-request.
    # This is simpler than trying to restore a previous state.
    
    # Alternative: Set to a neutral state, e.g., if they were friends, they remain friends.
    # If it was PENDING before block, it's gone.
    # This is complex. Let's make unblock simply remove the record for now.
    # If you want to "unblock and revert to previous state", you'd need to store that state.

    # Simpler: Unblocking removes the friendship record. User can re-initiate.
    # db.delete(friendship)

    # More user-friendly: Unblocking sets status to what it might have been before, or neutral.
    # If they were friends, they become friends again. If nothing, then nothing.
    # For now, let's set status to PENDING, with current user as action_user,
    # effectively making them "open" to re-friending. The other user would see nothing changed
    # until a new request is made or accepted.
    # This is still not ideal. The simplest "unblock" is to remove the block status.
    # What was the status before the block? If it was ACCEPTED, should it go back?
    # Let's assume unblocking means the relationship is now "neutral" (no record or a new PENDING if one wants to re-initiate).
    # For this implementation, let's just remove the record.
    
    # Revised: Unblocking sets the status to what it would be if no block existed.
    # If they were friends, they are friends. If it was pending, it's pending from other user.
    # This is too complex without storing pre-block state.
    # Simplest: Unblock removes the record.
    
    # Let's try this: unblocking sets the status to PENDING, with the action_user_id being the one who unblocked.
    # This means the relationship is now open for the other person to accept if they wish, or for the unblocker to send a new request.
    # This is still not perfect.
    # The most straightforward "unblock" is to simply remove the block status.
    # If they were friends before, they are friends again.
    # If the request was pending from the other user, it remains pending from them.
    # If the request was pending from the current user (blocker), it's now unblocked and still pending from them.

    # Let's assume the previous state was "nothing" or "pending from other".
    # Unblocking will effectively delete the friendship record, requiring a new request.
    # This is the cleanest break.
    
    # Final Decision for this iteration: Unblocking removes the friendship record.
    # This forces a re-evaluation of the relationship.
    db.delete(friendship)
    action_message = f"User '{other_user.username}' unblocked. Any previous friendship status is cleared."


    try:
        db.commit()
        # Since the record is deleted, we can't return FriendPublic of the old record.
        # We return a message. The frontend should update its state.
        return JSONResponse(status_code=200, content={"message": action_message})
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

