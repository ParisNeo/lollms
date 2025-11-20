# backend/routers/social/dm.py
import uuid
import json
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile, Body
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

dm_router = APIRouter(prefix="/api/dm", tags=["Direct Messaging"])

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
                image_paths.append(f"{DM_ASSETS_DIR_NAME}/{unique_filename}")
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
    
    # Prepare response manually to handle conditional fields
    resp = DirectMessagePublic(
        id=new_message.id,
        sender_id=new_message.sender_id,
        receiver_id=new_message.receiver_id or 0, # Avoid validation error if null
        conversation_id=new_message.conversation_id,
        content=new_message.content,
        sent_at=new_message.sent_at,
        sender_username=current_user.username,
        receiver_username="", # Populated on frontend if needed
        image_references=new_message.image_references
    )

    payload = { "type": "new_dm", "data": json.loads(resp.model_dump_json()) }
    
    for uid in recipient_ids:
        manager.send_personal_message_sync(payload, uid)
    manager.send_personal_message_sync(payload, current_user.id) # Echo back

    return resp

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
        unread_count=0 # Logic for unread count in groups is complex, simplifying for now
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
            # Basic info, detailed members fetching might be heavy for list, optimize later
            last_msg = db.query(DBDirectMessage).filter(DBDirectMessage.conversation_id == g.id).order_by(desc(DBDirectMessage.sent_at)).first()
            groups.append(ConversationPublic(
                id=g.id,
                name=g.name or "Group Chat",
                is_group=True,
                last_message=last_msg.content if last_msg else "No messages",
                last_message_at=last_msg.sent_at if last_msg else g.created_at
            ))

    # 2. Fetch Legacy 1-on-1 DMs (Virtual Conversations)
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
        DBDirectMessage.conversation_id == None # Only legacy
    ).subquery()

    latest_dms = db.query(DBDirectMessage).join(subquery, DBDirectMessage.id == subquery.c.id).filter(
        subquery.c.rn == 1,
        or_(DBDirectMessage.sender_id == current_user.id, DBDirectMessage.receiver_id == current_user.id)
    ).options(joinedload(DBDirectMessage.sender), joinedload(DBDirectMessage.receiver)).order_by(desc(DBDirectMessage.sent_at)).all()

    dms = []
    for msg in latest_dms:
        partner = msg.sender if msg.receiver_id == current_user.id else msg.receiver
        # Calculate unread
        unread = db.query(DBDirectMessage).filter(
            DBDirectMessage.sender_id == partner.id,
            DBDirectMessage.receiver_id == current_user.id,
            DBDirectMessage.read_at == None,
            DBDirectMessage.conversation_id == None
        ).count()
        
        dms.append(ConversationPublic(
            id=partner.id, # Virtual ID for 1-on-1 is partner ID (client handles distinction)
            is_group=False,
            partner_user_id=partner.id,
            partner_username=partner.username,
            partner_icon=partner.icon,
            last_message=msg.content,
            last_message_at=msg.sent_at,
            unread_count=unread
        ))

    # Combine and Sort
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
        # Check membership
        member = db.query(DBConversationMember).filter_by(conversation_id=target_id, user_id=current_user.id).first()
        if not member and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Not a member of this group")
        query = query.filter(DBDirectMessage.conversation_id == target_id)
    else:
        # 1-on-1
        query = query.filter(
            or_(
                and_(DBDirectMessage.sender_id == current_user.id, DBDirectMessage.receiver_id == target_id),
                and_(DBDirectMessage.sender_id == target_id, DBDirectMessage.receiver_id == current_user.id)
            ),
            DBDirectMessage.conversation_id == None
        )

    messages = query.order_by(desc(DBDirectMessage.sent_at)).offset(skip).limit(limit).all()
    
    # Map to public
    return [DirectMessagePublic(
        id=m.id, sender_id=m.sender_id, receiver_id=m.receiver_id or 0, conversation_id=m.conversation_id,
        content=m.content, sent_at=m.sent_at, read_at=m.read_at,
        sender_username=m.sender.username, image_references=m.image_references
    ) for m in messages]
