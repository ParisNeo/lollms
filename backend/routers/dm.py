import uuid
import yaml
import traceback
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, union, distinct, select
from typing import List

from backend.database_setup import get_db, User as DBUser, DirectMessage as DBDirectMessage, FriendshipStatus, get_friendship_record
from backend.models import UserAuthDetails, UserPublic, DirectMessageCreate, DirectMessagePublic, DiscussionSendRequest
from backend.session import get_current_active_user, get_user_data_root, get_user_by_username
from backend.ws_manager import manager

dm_router = APIRouter(
    prefix="/api/dm",
    tags=["Direct Messages"],
    dependencies=[Depends(get_current_active_user)]
)

@dm_router.post("/send-discussion", status_code=200)
async def send_discussion_to_friend(
    payload: DiscussionSendRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    sender_user = db.query(DBUser).filter(DBUser.id == current_user.id).first()
    receiver_user = get_user_by_username(db, payload.target_username)

    if not receiver_user:
        raise HTTPException(status_code=404, detail="Recipient user not found.")

    if sender_user.id == receiver_user.id:
        raise HTTPException(status_code=400, detail="Cannot send a discussion to yourself.")

    friendship = get_friendship_record(db, sender_user.id, receiver_user.id)
    if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
        raise HTTPException(status_code=403, detail="You can only send discussions to friends.")

    sender_discussions_path = get_user_data_root(sender_user.username) / "discussions"
    original_file_path = sender_discussions_path / f"{payload.discussion_id}.yaml"
    if not original_file_path.exists():
        raise HTTPException(status_code=404, detail="Original discussion not found.")

    try:
        with open(original_file_path, 'r', encoding='utf-8') as f:
            discussion_data = yaml.safe_load(f)

        new_discussion_id = str(uuid.uuid4())
        discussion_data['id'] = new_discussion_id
        original_title = discussion_data.get('title', 'Untitled')
        discussion_data['title'] = f"[Shared from {sender_user.username}] {original_title}"
        discussion_data['starred'] = False

        receiver_discussions_path = get_user_data_root(receiver_user.username) / "discussions"
        receiver_discussions_path.mkdir(parents=True, exist_ok=True)
        new_file_path = receiver_discussions_path / f"{new_discussion_id}.yaml"

        with open(new_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(discussion_data, f, allow_unicode=True, sort_keys=False)
            
        return {"message": f"Discussion successfully sent to {payload.target_username}."}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred while sending the discussion: {e}")

@dm_router.get("/conversations", response_model=List[UserPublic])
def get_user_conversations(
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Retrieves a list of users with whom the current user has had a conversation.
    """
    sent_to_ids = select(distinct(DBDirectMessage.receiver_id)).where(DBDirectMessage.sender_id == current_user.id)
    received_from_ids = select(distinct(DBDirectMessage.sender_id)).where(DBDirectMessage.receiver_id == current_user.id)
    
    partner_ids_query = union(sent_to_ids, received_from_ids)
    partners_subquery = partner_ids_query.subquery()
    
    partners_db = db.query(DBUser).filter(DBUser.id.in_(select(partners_subquery))).all()

    response_list = [UserPublic.model_validate(user) for user in partners_db]
    
    return response_list


@dm_router.get("/conversation/{other_user_id}", response_model=List[DirectMessagePublic])
def get_message_history(
    other_user_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 50
):
    """
    Retrieves the message history between the current user and another user.
    """
    query = (
        db.query(DBDirectMessage)
        .options(joinedload(DBDirectMessage.sender), joinedload(DBDirectMessage.receiver))
        .filter(
            or_(
                (DBDirectMessage.sender_id == current_user.id) & (DBDirectMessage.receiver_id == other_user_id),
                (DBDirectMessage.sender_id == other_user_id) & (DBDirectMessage.receiver_id == current_user.id)
            )
        )
        .order_by(DBDirectMessage.sent_at.desc())
        .offset(skip)
        .limit(limit)
    )
    messages = query.all()
    
    # --- FIX: Manually construct the response to prevent model validation errors ---
    response_list = []
    for msg in messages:
        response_list.append(DirectMessagePublic(
            id=msg.id,
            content=msg.content,
            sender_id=msg.sender_id,
            receiver_id=msg.receiver_id,
            sent_at=msg.sent_at,
            read_at=msg.read_at,
            sender_username=msg.sender.username,
            receiver_username=msg.receiver.username
        ))
    
    return response_list[::-1] # Reverse to show oldest first in the final list


@dm_router.post("/send", response_model=DirectMessagePublic, status_code=status.HTTP_201_CREATED)
async def send_direct_message(
    dm_data: DirectMessageCreate,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Saves a direct message to the database and pushes it to the recipient
    via WebSocket if they are connected.
    """
    if current_user.id == dm_data.receiver_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot send a message to yourself.")

    receiver = db.query(DBUser).filter(DBUser.id == dm_data.receiver_user_id).first()
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiver user not found.")

    new_message = DBDirectMessage(sender_id=current_user.id, receiver_id=dm_data.receiver_user_id, content=dm_data.content)
    db.add(new_message)
    db.commit()
    db.refresh(new_message, ['sender', 'receiver'])
    
    response_data = DirectMessagePublic(
        id=new_message.id,
        content=new_message.content,
        sender_id=new_message.sender_id,
        receiver_id=new_message.receiver_id,
        sent_at=new_message.sent_at,
        read_at=new_message.read_at,
        sender_username=new_message.sender.username,
        receiver_username=new_message.receiver.username,
    )

    await manager.send_personal_message(message_data=response_data.model_dump(mode="json"), user_id=dm_data.receiver_user_id)

    return response_data