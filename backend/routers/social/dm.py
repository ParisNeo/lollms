# [UPDATE] backend/routers/social/dm.py
import uuid
import json
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc, func, update, and_
from werkzeug.utils import secure_filename
from datetime import datetime
from pydantic import BaseModel, Field

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.dm import DirectMessage as DBDirectMessage, Conversation as DBConversation, ConversationMember as DBConversationMember
from backend.models import UserAuthDetails, DirectMessagePublic, CreateGroupRequest, ConversationPublic, ConversationMemberPublic, AddMemberRequest
from backend.session import get_current_active_user, get_user_dm_assets_path
from backend.ws_manager import manager
from backend.config import DM_ASSETS_DIR_NAME
from backend.task_manager import task_manager, Task

dm_router = APIRouter(prefix="/api/dm", tags=["Direct Messaging"])

class BroadcastDMRequest(BaseModel):
    content: str = Field(..., min_length=1)

def _broadcast_dm_task(task: Task, sender_id: int, content: str):
    db = next(get_db())
    try:
        sender = db.query(DBUser).filter(DBUser.id == sender_id).first()
        if not sender:
            raise Exception("Sender not found")
        
        # Get all active users except sender
        users = db.query(DBUser).filter(DBUser.id != sender_id, DBUser.is_active == True).all()
        total = len(users)
        
        task.log(f"Starting broadcast to {total} users...")
        
        for i, user in enumerate(users):
            if task.cancellation_event.is_set():
                task.log("Broadcast cancelled.", "WARNING")
                break
            
            new_message = DBDirectMessage(
                sender_id=sender_id,
                receiver_id=user.id,
                content=content
            )
            db.add(new_message)
            # Commit frequently to ensure messages are saved
            db.commit()
            db.refresh(new_message)
            
            message_payload = {
                "type": "new_dm",
                "data": {
                    "id": new_message.id,
                    "sender_id": sender.id,
                    "receiver_id": user.id,
                    "content": new_message.content,
                    "sent_at": new_message.sent_at.isoformat(),
                    "read_at": None,
                    "sender_username": sender.username,
                    "receiver_username": user.username,
                    "sender_icon": sender.icon,
                    "receiver_icon": user.icon,
                    "image_references": []
                }
            }
            manager.send_personal_message_sync(message_payload, user.id)
            
            if i % 10 == 0 or i == total - 1:
                task.set_progress(int(((i + 1) / total) * 100))
                
        task.set_progress(100)
        return {"message": f"Broadcasted DM to {total} users."}
    except Exception as e:
        task.log(f"Error broadcasting DM: {e}", "ERROR")
        raise e
    finally:
        db.close()

@dm_router.post("/conversations/group", response_model=ConversationPublic, status_code=201)
async def create_group_conversation(
    payload: CreateGroupRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    new_conv = DBConversation(name=payload.name, is_group=1)
    db.add(new_conv)
    db.commit()
    db.refresh(new_conv)
    
    # Add creator
    creator_member = DBConversationMember(conversation_id=new_conv.id, user_id=current_user.id)
    db.add(creator_member)
    
    # Add participants
    members_public = [ConversationMemberPublic(user_id=current_user.id, username=current_user.username, icon=current_user.icon)]
    
    for uid in payload.participant_ids:
        if uid != current_user.id:
            user = db.query(DBUser).filter(DBUser.id == uid).first()
            if user:
                member = DBConversationMember(conversation_id=new_conv.id, user_id=uid)
                db.add(member)
                members_public.append(ConversationMemberPublic(user_id=user.id, username=user.username, icon=user.icon))
    
    db.commit()
    
    # Notify participants
    notification = {
        "type": "new_conversation",
        "data": {
            "id": new_conv.id,
            "name": new_conv.name,
            "is_group": True,
            "last_message": "Group created",
            "last_message_at": new_conv.created_at.isoformat(),
            "unread_count": 0
        }
    }
    for m in members_public:
        # Try direct send for instant feedback
        if m.user_id in manager.active_connections:
            await manager.send_personal_message(notification, m.user_id)
        # Also queue for reliability
        if m.user_id != current_user.id:
            manager.send_personal_message_sync(notification, m.user_id)
            
    return ConversationPublic(
        id=new_conv.id,
        name=new_conv.name,
        is_group=True,
        last_message="Group created",
        last_message_at=new_conv.created_at,
        members=members_public
    )

@dm_router.post("/conversations/{conversation_id}/members", response_model=ConversationPublic)
async def add_member_to_group(
    conversation_id: int,
    payload: AddMemberRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    conv = db.query(DBConversation).filter(DBConversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if not conv.is_group:
         raise HTTPException(status_code=400, detail="Cannot add members to a direct message")
         
    # Check if current user is member
    is_member = db.query(DBConversationMember).filter_by(conversation_id=conversation_id, user_id=current_user.id).first()
    if not is_member and not current_user.is_admin:
         raise HTTPException(status_code=403, detail="You must be a member to add others")

    new_user = db.query(DBUser).filter(DBUser.id == payload.user_id).first()
    if not new_user:
         raise HTTPException(status_code=404, detail="User to add not found")

    existing = db.query(DBConversationMember).filter_by(conversation_id=conversation_id, user_id=payload.user_id).first()
    if not existing:
        new_member = DBConversationMember(conversation_id=conversation_id, user_id=payload.user_id)
        db.add(new_member)
        db.commit()
        
        # System message
        sys_msg = DBDirectMessage(
            sender_id=current_user.id,
            conversation_id=conversation_id,
            content=f"{new_user.username} was added to the group."
        )
        db.add(sys_msg)
        db.commit()
        
        # Notify
        notification = {"type": "conversation_update", "data": {"id": conversation_id, "action": "member_added"}}
        # Try direct send
        if payload.user_id in manager.active_connections:
            await manager.send_personal_message(notification, payload.user_id)
        manager.send_personal_message_sync(notification, payload.user_id)

    return await get_conversation_details_internal(conversation_id, current_user.id, db)

@dm_router.post("/send", response_model=DirectMessagePublic, status_code=201)
async def send_direct_message(
    receiver_user_id: Optional[int] = Form(None, alias="receiverUserId"),
    conversation_id: Optional[int] = Form(None, alias="conversationId"),
    content: str = Form(..., min_length=1),
    files: Optional[List[UploadFile]] = File(None),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not receiver_user_id and not conversation_id:
        raise HTTPException(status_code=400, detail="Either receiverUserId or conversationId must be provided.")

    image_paths = []
    if files:
        dm_assets_path = get_user_dm_assets_path(current_user.username)
        for file in files:
            if not file.filename: continue
            s_filename = secure_filename(file.filename or "image.png")
            unique_filename = f"{uuid.uuid4().hex}{Path(s_filename).suffix}"
            file_path = dm_assets_path / unique_filename
            try:
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                # Save a URL path that the frontend can use to fetch the image via the new endpoint
                image_paths.append(f"/api/dm/file/{current_user.username}/{unique_filename}")
            finally:
                file.file.close()

    new_message = DBDirectMessage(
        sender_id=current_user.id,
        content=content,
        image_references=image_paths if image_paths else None
    )

    recipient_ids = []

    if conversation_id:
        # Group or linked conversation
        conv = db.query(DBConversation).filter(DBConversation.id == conversation_id).first()
        if not conv: raise HTTPException(status_code=404, detail="Conversation not found")
        new_message.conversation_id = conversation_id
        
        # Get recipients
        members = db.query(DBConversationMember).filter(DBConversationMember.conversation_id == conversation_id).all()
        recipient_ids = [m.user_id for m in members if m.user_id != current_user.id]
        
    elif receiver_user_id:
        # Legacy 1-on-1
        if current_user.id == receiver_user_id:
            raise HTTPException(status_code=400, detail="Cannot message self.")
        new_message.receiver_id = receiver_user_id
        recipient_ids = [receiver_user_id]

    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    
    # Prepare response
    resp = DirectMessagePublic(
        id=new_message.id,
        sender_id=new_message.sender_id,
        receiver_id=new_message.receiver_id or 0,
        conversation_id=new_message.conversation_id,
        content=new_message.content,
        sent_at=new_message.sent_at,
        sender_username=current_user.username,
        receiver_username="", 
        image_references=new_message.image_references if isinstance(new_message.image_references, list) else []
    )

    payload = { "type": "new_dm", "data": json.loads(resp.model_dump_json()) }
    
    # 1. Send Immediately to recipients if connected locally (Realtime Fix)
    for uid in recipient_ids:
        if uid in manager.active_connections:
            await manager.send_personal_message(payload, uid)
            
    # Echo back to sender immediately for consistency across tabs
    if current_user.id in manager.active_connections:
        await manager.send_personal_message(payload, current_user.id)

    # 2. Queue for Broadcast (Multi-worker support & Persistence guarantee)
    # The frontend is responsible for de-duplicating messages if it receives both
    for uid in recipient_ids:
        manager.send_personal_message_sync(payload, uid)
    manager.send_personal_message_sync(payload, current_user.id) 

    return resp

@dm_router.get("/file/{username}/{filename}")
async def get_dm_attachment(
    username: str, 
    filename: str, 
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    # Basic access check: currently allows any authenticated user to fetch if they have the link.
    # In a stricter system, we would check conversation membership.
    file_path = get_user_dm_assets_path(username) / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)

async def get_conversation_details_internal(conv_id, user_id, db):
    conv = db.query(DBConversation).filter(DBConversation.id == conv_id).first()
    if not conv: return None
    
    # Get members
    members_db = db.query(DBConversationMember).options(joinedload(DBConversationMember.user)).filter(DBConversationMember.conversation_id == conv_id).all()
    members = [ConversationMemberPublic(user_id=m.user.id, username=m.user.username, icon=m.user.icon) for m in members_db]
    
    # Get last message
    last_msg = db.query(DBDirectMessage).filter(DBDirectMessage.conversation_id == conv_id).order_by(desc(DBDirectMessage.sent_at)).first()
    
    return ConversationPublic(
        id=conv.id,
        name=conv.name,
        is_group=bool(conv.is_group),
        members=members,
        last_message=last_msg.content if last_msg else None,
        last_message_at=last_msg.sent_at if last_msg else conv.created_at,
        unread_count=0
    )

@dm_router.get("/conversations", response_model=List[ConversationPublic])
async def get_user_conversations(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # 1. Fetch Group Conversations
    group_conv_ids = db.query(DBConversationMember.conversation_id).filter(DBConversationMember.user_id == current_user.id).all()
    group_ids = [g[0] for g in group_conv_ids]
    
    groups = []
    if group_ids:
        groups_db = db.query(DBConversation).filter(DBConversation.id.in_(group_ids)).all()
        for g in groups_db:
            last_msg = db.query(DBDirectMessage).filter(DBDirectMessage.conversation_id == g.id).order_by(desc(DBDirectMessage.sent_at)).first()
            groups.append(ConversationPublic(
                id=g.id,
                name=g.name or "Group Chat",
                is_group=True,
                last_message=last_msg.content if last_msg else "No messages",
                last_message_at=last_msg.sent_at if last_msg else g.created_at
            ))

    # 2. Fetch Legacy 1-on-1 DMs
    subquery = db.query(
        DBDirectMessage.id,
        func.row_number().over(
            partition_by=(
                func.min(DBDirectMessage.sender_id, DBDirectMessage.receiver_id),
                func.max(DBDirectMessage.sender_id, DBDirectMessage.receiver_id)
            ),
            order_by=DBDirectMessage.sent_at.desc()
        ).label('rn')
    ).filter(
        DBDirectMessage.conversation_id == None
    ).subquery()

    latest_dms = db.query(DBDirectMessage).join(subquery, DBDirectMessage.id == subquery.c.id).filter(
        subquery.c.rn == 1,
        or_(DBDirectMessage.sender_id == current_user.id, DBDirectMessage.receiver_id == current_user.id)
    ).options(joinedload(DBDirectMessage.sender), joinedload(DBDirectMessage.receiver)).order_by(desc(DBDirectMessage.sent_at)).all()

    dms = []
    for msg in latest_dms:
        partner = msg.sender if msg.receiver_id == current_user.id else msg.receiver
        unread = db.query(DBDirectMessage).filter(
            DBDirectMessage.sender_id == partner.id,
            DBDirectMessage.receiver_id == current_user.id,
            DBDirectMessage.read_at == None,
            DBDirectMessage.conversation_id == None
        ).count()
        
        dms.append(ConversationPublic(
            id=partner.id,
            is_group=False,
            partner_user_id=partner.id,
            partner_username=partner.username,
            partner_icon=partner.icon,
            last_message=msg.content,
            last_message_at=msg.sent_at,
            unread_count=unread
        ))

    all_convos = groups + dms
    all_convos.sort(key=lambda x: x.last_message_at or datetime.min, reverse=True)
    return all_convos

@dm_router.get("/conversation/{target_id}", response_model=List[DirectMessagePublic])
async def get_conversation_messages(
    target_id: int,
    is_group: bool = False,
    skip: int = 0,
    limit: int = 50,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(DBDirectMessage).options(joinedload(DBDirectMessage.sender))
    
    if is_group:
        member = db.query(DBConversationMember).filter_by(conversation_id=target_id, user_id=current_user.id).first()
        if not member and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not a member of this group")
        query = query.filter(DBDirectMessage.conversation_id == target_id)
    else:
        query = query.filter(
            or_(
                and_(DBDirectMessage.sender_id == current_user.id, DBDirectMessage.receiver_id == target_id),
                and_(DBDirectMessage.sender_id == target_id, DBDirectMessage.receiver_id == current_user.id)
            ),
            DBDirectMessage.conversation_id == None
        )

    messages = query.order_by(desc(DBDirectMessage.sent_at)).offset(skip).limit(limit).all()
    
    return [DirectMessagePublic(
        id=m.id, sender_id=m.sender_id, receiver_id=m.receiver_id or 0, conversation_id=m.conversation_id,
        content=m.content, sent_at=m.sent_at, read_at=m.read_at,
        sender_username=m.sender.username, 
        # Safely handle image_references being 'null' string, None, or list
        image_references=m.image_references if isinstance(m.image_references, list) else []
    ) for m in messages]

@dm_router.post("/conversation/{user_id}/read", status_code=200)
async def mark_conversation_as_read(
    user_id: int,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
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

@dm_router.delete("/messages/{message_id}", status_code=200)
async def delete_direct_message(
    message_id: int,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    msg = db.query(DBDirectMessage).filter(DBDirectMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if msg.sender_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="You can only delete your own messages")
        
    db.delete(msg)
    db.commit()
    
    return {"message": "Message deleted"}

@dm_router.delete("/conversations/{conversation_id}", status_code=200)
async def delete_conversation_or_leave_group(
    conversation_id: int,
    is_group: bool = False,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if is_group:
        # Leave group
        member = db.query(DBConversationMember).filter_by(conversation_id=conversation_id, user_id=current_user.id).first()
        if member:
            db.delete(member)
            
            # Check if group is empty
            remaining = db.query(DBConversationMember).filter_by(conversation_id=conversation_id).count()
            if remaining == 0:
                conv = db.query(DBConversation).filter_by(id=conversation_id).first()
                if conv: db.delete(conv)
                
            db.commit()
        return {"message": "Left group"}
    else:
        # Delete ALL messages between these two users to clear history physically
        partner_id = conversation_id 
        
        msgs = db.query(DBDirectMessage).filter(
             or_(
                and_(DBDirectMessage.sender_id == current_user.id, DBDirectMessage.receiver_id == partner_id),
                and_(DBDirectMessage.sender_id == partner_id, DBDirectMessage.receiver_id == current_user.id)
            ),
            DBDirectMessage.conversation_id == None
        ).all()
        
        for m in msgs:
            db.delete(m)
        
        db.commit()
        return {"message": "Conversation deleted"}

@dm_router.post("/broadcast", status_code=202)
async def broadcast_direct_message(
    payload: BroadcastDMRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can broadcast DMs.")
        
    task = task_manager.submit_task(
        name="Broadcast DM",
        target=_broadcast_dm_task,
        args=(current_user.id, payload.content),
        description=f"Sending DM to all users: {payload.content[:30]}...",
        owner_username=current_user.username
    )
    return task
