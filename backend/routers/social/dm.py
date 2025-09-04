# backend/routers/dm.py
import uuid
import json
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc, func, update
from werkzeug.utils import secure_filename
from datetime import datetime

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.dm import DirectMessage as DBDirectMessage
from backend.models import UserAuthDetails, DirectMessagePublic
from backend.session import get_current_active_user, get_user_dm_assets_path
from backend.ws_manager import manager
from backend.config import DM_ASSETS_DIR_NAME

dm_router = APIRouter(prefix="/api/dm", tags=["Direct Messaging"])

@dm_router.post("/send", response_model=DirectMessagePublic, status_code=201)
async def send_direct_message(
    content: str = Form(...),
    receiver_user_id: int = Form(..., alias="receiverUserId"),
    files: Optional[List[UploadFile]] = File(None),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    receiver = db.query(DBUser).filter(DBUser.id == receiver_user_id).first()
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiver user not found.")

    if current_user.id == receiver.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot send a message to yourself.")

    image_paths = []
    if files:
        dm_assets_path = get_user_dm_assets_path(current_user.username)
        for file in files:
            s_filename = secure_filename(file.filename or "image.png")
            ext = Path(s_filename).suffix
            unique_filename = f"{uuid.uuid4().hex}{ext}"
            file_path = dm_assets_path / unique_filename
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            relative_path = f"{DM_ASSETS_DIR_NAME}/{unique_filename}"
            image_paths.append(relative_path)

    new_message = DBDirectMessage(
        sender_id=current_user.id,
        receiver_id=receiver.id,
        content=content,
        image_references=image_paths if image_paths else None
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message, ['sender', 'receiver'])

    response_data = DirectMessagePublic.from_orm(new_message)
    response_data.sender_username = new_message.sender.username
    response_data.receiver_username = new_message.receiver.username
    
    message_payload = {
        "type": "new_dm",
        "data": response_data.model_dump(mode="json")
    }
    
    # Send to recipient
    await manager.send_personal_message(message_payload, receiver.id)
    # Send to sender for multi-device sync
    await manager.send_personal_message(message_payload, current_user.id)


    return response_data

@dm_router.get("/conversations", response_model=List[dict])
async def get_user_conversations(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    subquery = db.query(
        DBDirectMessage.id,
        func.row_number().over(
            partition_by=(
                func.least(DBDirectMessage.sender_id, DBDirectMessage.receiver_id),
                func.greatest(DBDirectMessage.sender_id, DBDirectMessage.receiver_id)
            ),
            order_by=DBDirectMessage.sent_at.desc()
        ).label('rn')
    ).subquery()

    latest_messages = db.query(DBDirectMessage).join(
        subquery, DBDirectMessage.id == subquery.c.id
    ).filter(
        subquery.c.rn == 1,
        or_(DBDirectMessage.sender_id == current_user.id, DBDirectMessage.receiver_id == current_user.id)
    ).options(
        joinedload(DBDirectMessage.sender),
        joinedload(DBDirectMessage.receiver)
    ).order_by(desc(DBDirectMessage.sent_at)).all()

    conversations = []
    for msg in latest_messages:
        partner = msg.sender if msg.receiver_id == current_user.id else msg.receiver
        unread_count = db.query(DBDirectMessage).filter(
            DBDirectMessage.sender_id == partner.id,
            DBDirectMessage.receiver_id == current_user.id,
            DBDirectMessage.read_at.is_(None)
        ).count()
        conversations.append({
            "partner_user_id": partner.id,
            "partner_username": partner.username,
            "partner_icon": partner.icon,
            "last_message": msg.content,
            "last_message_at": msg.sent_at,
            "unread_count": unread_count
        })

    return conversations

@dm_router.get("/conversation/{user_id}", response_model=List[DirectMessagePublic])
async def get_conversation_messages(
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    messages = db.query(DBDirectMessage).filter(
        or_(
            (DBDirectMessage.sender_id == current_user.id) & (DBDirectMessage.receiver_id == user_id),
            (DBDirectMessage.sender_id == user_id) & (DBDirectMessage.receiver_id == current_user.id)
        )
    ).options(
        joinedload(DBDirectMessage.sender),
        joinedload(DBDirectMessage.receiver)
    ).order_by(
        desc(DBDirectMessage.sent_at)
    ).offset(skip).limit(limit).all()

    response_data = []
    for msg in messages:
        msg_public = DirectMessagePublic(
            id=msg.id,
            sender_id=msg.sender_id,
            receiver_id=msg.receiver_id,
            sent_at=msg.sent_at,
            read_at=msg.read_at,
            sender_username=msg.sender.username,
            receiver_username=msg.receiver.username,
            content = msg.content
        )
        msg_public.sender_username = msg.sender.username
        msg_public.receiver_username = msg.receiver.username
        response_data.append(msg_public)

    return response_data

@dm_router.post("/conversation/{user_id}/read", status_code=200)
async def mark_conversation_as_read(
    user_id: int,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Marks all messages from a specific user to the current user as read."""
    stmt = (
        update(DBDirectMessage)
        .where(
            DBDirectMessage.sender_id == user_id,
            DBDirectMessage.receiver_id == current_user.id,
            DBDirectMessage.read_at.is_(None)
        )
        .values(read_at=datetime.utcnow())
    )
    result = db.execute(stmt)
    db.commit()
    
    return {"message": f"Marked {result.rowcount} messages as read."}
