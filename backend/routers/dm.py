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

dm_router = APIRouter(prefix="/api/dm", tags=["Direct Messaging"])

@dm_router.post("/send", response_model=DirectMessagePublic, status_code=201)
async def send_direct_message(
    dm_data: DirectMessageCreate,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> DirectMessagePublic:
    if current_db_user.id == dm_data.receiver_user_id:
        raise HTTPException(status_code=400, detail="You cannot send a message to yourself.")

    receiver_user = db.query(DBUser).filter(DBUser.id == dm_data.receiver_user_id).first()
    if not receiver_user:
        raise HTTPException(status_code=404, detail="Receiver user not found.")

    # Check friendship status and blocks
    friendship = get_friendship_record(db, current_db_user.id, receiver_user.id) # Uses helper from friends_router

    if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
        # Check for blocks even if not "ACCEPTED" friends, as a block overrides everything
        if friendship: # A record exists, check its status
            if (friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and friendship.user1_id == current_db_user.id) or \
               (friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and friendship.user2_id == current_db_user.id):
                raise HTTPException(status_code=403, detail="You have blocked this user. Unblock them to send messages.")
            if (friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and friendship.user1_id == receiver_user.id) or \
               (friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and friendship.user2_id == receiver_user.id):
                raise HTTPException(status_code=403, detail="You cannot send a message to this user as they have blocked you.")
        # If no record or not accepted (and not blocked by receiver)
        raise HTTPException(status_code=403, detail="You can only send messages to accepted friends who have not blocked you.")


    new_dm = DirectMessage(
        sender_id=current_db_user.id,
        receiver_id=receiver_user.id,
        content=dm_data.content
        # image_references_json=dm_data.image_references_json # If supporting images
    )
    db.add(new_dm)
    try:
        db.commit()
        db.refresh(new_dm)
        # Eager load sender and receiver for username in response
        db.refresh(new_dm, attribute_names=['sender', 'receiver'])
        
        return DirectMessagePublic(
            id=new_dm.id,
            sender_id=new_dm.sender_id,
            sender_username=new_dm.sender.username,
            receiver_id=new_dm.receiver_id,
            receiver_username=new_dm.receiver.username,
            content=new_dm.content,
            sent_at=new_dm.sent_at,
            read_at=new_dm.read_at
            # image_references_json=new_dm.image_references_json
        )
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error sending message: {str(e)}")


@dm_router.get("/conversation/{other_user_id_or_username}", response_model=List[DirectMessagePublic])
async def get_dm_conversation(
    other_user_id_or_username: str,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db),
    before_message_id: Optional[int] = None, # For pagination: load messages before this ID
    limit: int = Query(50, ge=1, le=100) # Pagination limit
) -> List[DirectMessagePublic]:
    other_user = None
    try:
        other_user_id_val = int(other_user_id_or_username)
        other_user = db.query(DBUser).filter(DBUser.id == other_user_id_val).first()
    except ValueError:
        other_user = db.query(DBUser).filter(DBUser.username == other_user_id_or_username).first()

    if not other_user:
        raise HTTPException(status_code=404, detail="Other user not found.")
    if other_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="Cannot fetch conversation with yourself.")

    # Optional: Check friendship status before allowing to view conversation
    # friendship = get_friendship_record(db, current_db_user.id, other_user.id)
    # if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
    #     raise HTTPException(status_code=403, detail="You can only view conversations with accepted friends.")
    # For now, allow viewing even if unfriended, but sending is restricted.

    query = db.query(DirectMessage).options(
        joinedload(DirectMessage.sender), joinedload(DirectMessage.receiver)
    ).filter(
        or_(
            and_(DirectMessage.sender_id == current_db_user.id, DirectMessage.receiver_id == other_user.id),
            and_(DirectMessage.sender_id == other_user.id, DirectMessage.receiver_id == current_db_user.id)
        )
    ).order_by(DirectMessage.sent_at.desc()) # Get newest first for pagination

    if before_message_id:
        before_message = db.query(DirectMessage).filter(DirectMessage.id == before_message_id).first()
        if before_message:
            query = query.filter(DirectMessage.sent_at < before_message.sent_at)
        else: # Invalid before_message_id, return empty or error
            return [] 
            
    messages_db = query.limit(limit).all()
    
    # Mark messages sent by the other user to current_user as read (if not already)
    # This should ideally be a separate endpoint hit when user opens a conversation
    unread_message_ids = [
        msg.id for msg in messages_db 
        if msg.receiver_id == current_db_user.id and msg.read_at is None
    ]
    if unread_message_ids:
        db.query(DirectMessage).filter(
            DirectMessage.id.in_(unread_message_ids)
        ).update({"read_at": datetime.datetime.now(datetime.timezone.utc)}, synchronize_session=False)
        db.commit()
        # Re-fetch to get updated read_at times for the response (or update in-memory)
        for msg in messages_db:
            if msg.id in unread_message_ids:
                msg.read_at = datetime.datetime.now(datetime.timezone.utc) # Approximate

    response_list = [
        DirectMessagePublic(
            id=msg.id,
            sender_id=msg.sender_id,
            sender_username=msg.sender.username,
            receiver_id=msg.receiver_id,
            receiver_username=msg.receiver.username,
            content=msg.content,
            sent_at=msg.sent_at,
            read_at=msg.read_at
            # image_references_json=msg.image_references_json
        ) for msg in reversed(messages_db) # Reverse to show oldest first in the fetched page
    ]
    return response_list

# Endpoint to explicitly mark messages as read (better than doing it in GET)
@dm_router.post("/conversation/{other_user_id}/mark_read", status_code=200)
async def mark_dm_conversation_as_read(
    other_user_id: int,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
):
    # Mark all unread messages received by current_db_user from other_user_id as read
    updated_count = db.query(DirectMessage).filter(
        DirectMessage.sender_id == other_user_id,
        DirectMessage.receiver_id == current_db_user.id,
        DirectMessage.read_at == None
    ).update({"read_at": datetime.datetime.now(datetime.timezone.utc)}, synchronize_session=False)
    
    db.commit()
    return {"message": f"{updated_count} messages marked as read."}


# Placeholder for listing DM conversations (threads)
# This would typically involve getting the latest message from each unique correspondent.
@dm_router.get("/conversations", response_model=List[Dict[str, Any]]) # Response model needs to be defined
async def list_dm_conversations(
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
):
    # This is a complex query to get distinct conversation partners and last message.
    # Using a subquery to get the latest message_id for each conversation pair.
    # SQL might look like:
    # SELECT dm.*, u.username as partner_username FROM direct_messages dm
    # JOIN (
    #   SELECT
    #     CASE WHEN sender_id = :current_user_id THEN receiver_id ELSE sender_id END as partner_id,
    #     MAX(id) as max_id
    #   FROM direct_messages
    #   WHERE sender_id = :current_user_id OR receiver_id = :current_user_id
    #   GROUP BY partner_id
    # ) latest_msg ON dm.id = latest_msg.max_id
    # JOIN users u ON u.id = latest_msg.partner_id
    # ORDER BY dm.sent_at DESC;

    # SQLAlchemy equivalent is more involved. For now, a simplified version:
    # Get all friends, then for each friend, get the last message. This is N+1.
    # A more optimized query is needed for production.

    # Simplified approach: Get all friends, then fetch last message for each.
    friends_response = await get_my_friends(current_db_user, db) # Re-use existing friends list endpoint logic
    
    conversations = []
    for friend in friends_response:
        last_message = db.query(DirectMessage).filter(
            or_(
                and_(DirectMessage.sender_id == current_db_user.id, DirectMessage.receiver_id == friend.id),
                and_(DirectMessage.sender_id == friend.id, DirectMessage.receiver_id == current_db_user.id)
            )
        ).order_by(DirectMessage.sent_at.desc()).first()

        unread_count = db.query(DirectMessage).filter(
            DirectMessage.sender_id == friend.id, # Messages from friend
            DirectMessage.receiver_id == current_db_user.id, # To me
            DirectMessage.read_at == None
        ).count() or 0

        if last_message:
            conversations.append({
                "partner_user_id": friend.id,
                "partner_username": friend.username,
                "last_message_content": last_message.content[:50] + "..." if last_message.content and len(last_message.content) > 50 else last_message.content,
                "last_message_sent_at": last_message.sent_at,
                "last_message_sender_id": last_message.sender_id,
                "unread_count": unread_count
            })
        # else: # Friend with no messages yet, could still be listed
        #    conversations.append({ "partner_user_id": friend.id, "partner_username": friend.username, "unread_count": 0})


    # Sort conversations by last message time, descending
    conversations.sort(key=lambda x: x.get("last_message_sent_at", datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)), reverse=True)
    return conversations

