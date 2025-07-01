from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, union, distinct, select
from typing import List

from backend.database_setup import get_db, User as DBUser, DirectMessage as DBDirectMessage
from backend.models import UserAuthDetails, UserPublic, DirectMessageCreate, DirectMessagePublic
from backend.session import get_current_active_user
from backend.ws_manager import manager

dm_router = APIRouter(
    prefix="/api/dm",
    tags=["Direct Messages"],
    dependencies=[Depends(get_current_active_user)]
)

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
    
    # Create a union of the two queries
    partner_ids_query = union(sent_to_ids, received_from_ids)

    # FIX: Use the .subquery() method as required by SQLAlchemy for IN clauses.
    # This turns the union into a proper subquery that can be used in the filter.
    partners_subquery = partner_ids_query.subquery()
    
    partners_db = db.query(DBUser).filter(DBUser.id.in_(select(partners_subquery))).all()

    # Explicitly convert each SQLAlchemy DBUser object into a Pydantic UserPublic model.
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
    
    response_list = [DirectMessagePublic.model_validate(msg) for msg in messages]
    
    return response_list[::-1]


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
    
    response_data = DirectMessagePublic.model_validate(new_message)

    await manager.send_personal_message(message_data=response_data.model_dump(mode="json"), user_id=dm_data.receiver_user_id)

    return response_data