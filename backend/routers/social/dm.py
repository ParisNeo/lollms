# backend/routers/social/dm.py
import uuid
import json
import shutil
import re
import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc, func, update, and_
from werkzeug.utils import secure_filename
from pydantic import BaseModel, Field

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.dm import DirectMessage as DBDirectMessage, Conversation as DBConversation, ConversationMember as DBConversationMember
from backend.models.dm import (
    DirectMessagePublic, CreateGroupRequest, ConversationPublic,
    ConversationMemberPublic, AddMemberRequest, MessageReactionRequest,
    BulkDeleteMessagesRequest, CleanConversationRequest, TypingSignalRequest
)
from backend.models.user import UserAuthDetails
from backend.session import (
    get_current_active_user, get_user_dm_assets_path,
    build_lollms_client_from_params
)
from backend.ws_manager import manager
from backend.config import DM_ASSETS_DIR_NAME
from backend.task_manager import task_manager, Task
from backend.security import sanitize_content
from backend.settings import settings
from ascii_colors import trace_exception

dm_router = APIRouter(prefix="/api/dm", tags=["Direct Messaging"])

class BroadcastDMRequest(BaseModel):
    content: str = Field(..., min_length=1)

def _respond_to_dm_task(task: Task, conversation_id: Optional[int], partner_user_id: int, trigger_message_id: int):
    task.log("AI Assistant @lollms generating conversational DM reply...")
    db = next(get_db())
    try:
        settings.refresh(db)
        if not settings.get("ai_bot_enabled", False):
            return

        bot_user = db.query(DBUser).filter(DBUser.username == 'lollms').first()
        if not bot_user:
            return

        # Fetch triggering message
        trigger_msg = db.query(DBDirectMessage).filter(DBDirectMessage.id == trigger_message_id).first()
        if not trigger_msg:
            return

        # Build message history for conversational context
        if conversation_id:
            history = db.query(DBDirectMessage).options(joinedload(DBDirectMessage.sender))\
                .filter(DBDirectMessage.conversation_id == conversation_id)\
                .order_by(desc(DBDirectMessage.sent_at)).limit(15).all()
        else:
            history = db.query(DBDirectMessage).options(joinedload(DBDirectMessage.sender))\
                .filter(
                    or_(
                        and_(DBDirectMessage.sender_id == partner_user_id, DBDirectMessage.receiver_id == bot_user.id),
                        and_(DBDirectMessage.sender_id == bot_user.id, DBDirectMessage.receiver_id == partner_user_id)
                    ),
                    DBDirectMessage.conversation_id.is_(None)
                ).order_by(desc(DBDirectMessage.sent_at)).limit(15).all()

        history_reversed = list(reversed(history))
        dialogue_lines = []
        for m in history_reversed:
            sender_name = m.sender.username if m.sender else "User"
            dialogue_lines.append(f"{sender_name}: {m.content}")

        context_prompt = "\n".join(dialogue_lines)

        system_prompt = (
            "You are @lollms, a friendly, intelligent, and natural conversational AI companion in a direct chat. "
            "Respond helpfully, concisely, and naturally as if texting. Support markdown formatting for code and emphasis."
        )

        lc = build_lollms_client_from_params(username='lollms')
        full_prompt = f"Chat History:\n{context_prompt}\n\nRespond as @lollms directly to the last message:"
        reply_content = lc.generate_text(full_prompt, system_prompt=system_prompt, max_new_tokens=1024)

        clean_reply = sanitize_content(reply_content.strip())
        if not clean_reply:
            return

        ai_message = DBDirectMessage(
            sender_id=bot_user.id,
            receiver_id=partner_user_id if not conversation_id else None,
            conversation_id=conversation_id,
            content=clean_reply,
            reply_to_id=trigger_message_id,
            sent_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(ai_message)
        db.commit()
        db.refresh(ai_message)

        resp_public = _map_direct_message_public(ai_message, db)
        payload = { "type": "new_dm", "data": resp_public.model_dump(mode="json") }

        if conversation_id:
            members = db.query(DBConversationMember).filter(DBConversationMember.conversation_id == conversation_id).all()
            for m in members:
                manager.send_personal_message_sync(payload, m.user_id)
        else:
            manager.send_personal_message_sync(payload, partner_user_id)

    except Exception as e:
        trace_exception(e)
    finally:
        db.close()

def _map_direct_message_public(m: DBDirectMessage, db: Session) -> DirectMessagePublic:
    sender_username = m.sender.username if m.sender else "Unknown"
    sender_icon = m.sender.icon if m.sender else None
    receiver_username = m.receiver.username if m.receiver else None

    reply_to_content = None
    reply_to_sender = None
    if m.reply_to_id:
        parent = db.query(DBDirectMessage).options(joinedload(DBDirectMessage.sender)).filter(DBDirectMessage.id == m.reply_to_id).first()
        if parent:
            reply_to_content = parent.content[:150]
            reply_to_sender = parent.sender.username if parent.sender else "Unknown"

    return DirectMessagePublic(
        id=m.id,
        sender_id=m.sender_id,
        receiver_id=m.receiver_id,
        conversation_id=m.conversation_id,
        content=m.content,
        sent_at=m.sent_at,
        read_at=m.read_at,
        sender_username=sender_username,
        receiver_username=receiver_username,
        sender_icon=sender_icon,
        image_references=m.image_references if isinstance(m.image_references, list) else [],
        media=m.media if isinstance(m.media, list) else [],
        reply_to_id=m.reply_to_id,
        reply_to_content=reply_to_content,
        reply_to_sender=reply_to_sender,
        reactions=m.reactions if isinstance(m.reactions, dict) else {},
        is_ai_generated=bool(sender_username.lower() == "lollms")
    )

def _broadcast_dm_task(task: Task, sender_id: int, content: str):
    db = next(get_db())
    try:
        sender = db.query(DBUser).filter(DBUser.id == sender_id).first()
        if not sender:
            raise Exception("Sender not found")
        
        # Sanitize broadcast content
        clean_content = sanitize_content(content)

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
                content=clean_content
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
    # Sanitize group name
    clean_name = sanitize_content(payload.name)
    
    new_conv = DBConversation(name=clean_name, is_group=1)
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
    reply_to_id: Optional[int] = Form(None, alias="replyToId"),
    content: str = Form(..., min_length=1),
    files: Optional[List[UploadFile]] = File(None),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not receiver_user_id and not conversation_id:
        raise HTTPException(status_code=400, detail="Either receiverUserId or conversationId must be provided.")

    clean_content = sanitize_content(content)
    media_items = []
    legacy_image_paths = []

    if files:
        dm_assets_path = get_user_dm_assets_path(current_user.username)
        for file in files:
            if not file.filename:
                continue

            s_filename = secure_filename(file.filename or "attachment")
            ext = Path(s_filename).suffix.lower()
            content_type = (file.content_type or "").lower()
            unique_filename = f"{uuid.uuid4().hex}{ext}"
            file_path = dm_assets_path / unique_filename

            # Determine media type & validate
            media_type = "file"
            if content_type.startswith("image/") or ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                try:
                    file.file.seek(0)
                    img = Image.open(file.file)
                    img.verify()
                    file.file.seek(0)
                except Exception:
                    pass
                media_type = "image"
            elif content_type.startswith("video/") or ext in [".mp4", ".webm", ".ogv", ".mov"]:
                media_type = "video"
            elif content_type.startswith("audio/") or ext in [".wav", ".mp3", ".ogg", ".webm", ".m4a"]:
                media_type = "audio"

            try:
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                url_path = f"/api/dm/file/{current_user.username}/{unique_filename}"
                if media_type == "image":
                    legacy_image_paths.append(url_path)

                media_items.append({
                    "type": media_type,
                    "url": url_path,
                    "filename": s_filename,
                    "size": file_path.stat().st_size
                })
            finally:
                file.file.close()

    new_message = DBDirectMessage(
        sender_id=current_user.id,
        content=clean_content,
        image_references=legacy_image_paths if legacy_image_paths else None,
        media=media_items if media_items else None,
        reply_to_id=reply_to_id,
        reactions={}
    )

    recipient_ids = []
    is_bot_recipient = False

    if conversation_id:
        conv = db.query(DBConversation).filter(DBConversation.id == conversation_id).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        new_message.conversation_id = conversation_id

        members = db.query(DBConversationMember).filter(DBConversationMember.conversation_id == conversation_id).all()
        recipient_ids = [m.user_id for m in members if m.user_id != current_user.id]

    elif receiver_user_id:
        if current_user.id == receiver_user_id:
            raise HTTPException(status_code=400, detail="Cannot message self.")
        new_message.receiver_id = receiver_user_id
        recipient_ids = [receiver_user_id]

        target_receiver = db.query(DBUser).filter(DBUser.id == receiver_user_id).first()
        if target_receiver and target_receiver.username.lower() == 'lollms':
            is_bot_recipient = True

    db.add(new_message)
    db.commit()
    db.refresh(new_message)

    resp = _map_direct_message_public(new_message, db)
    payload = { "type": "new_dm", "data": resp.model_dump(mode="json") }

    # Send immediately
    for uid in recipient_ids:
        if uid in manager.active_connections:
            await manager.send_personal_message(payload, uid)

    if current_user.id in manager.active_connections:
        await manager.send_personal_message(payload, current_user.id)

    for uid in recipient_ids:
        manager.send_personal_message_sync(payload, uid)
    manager.send_personal_message_sync(payload, current_user.id)

    # Trigger AI bot response if communicating with @lollms or mentioned
    if is_bot_recipient or (conversation_id and re.search(r'\B@lollms\b', clean_content, re.IGNORECASE)):
        task_manager.submit_task(
            name=f"AI DM Reply to {current_user.username}",
            target=_respond_to_dm_task,
            args=(conversation_id, current_user.id, new_message.id),
            description=f"AI synthesizing direct message reply",
            owner_username='lollms'
        )

    return resp

@dm_router.post("/messages/{message_id}/reactions", response_model=DirectMessagePublic)
async def toggle_dm_reaction(
    message_id: int,
    payload: MessageReactionRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    msg = db.query(DBDirectMessage).filter(DBDirectMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    emoji = payload.emoji.strip()
    current_reactions = dict(msg.reactions or {})

    user_list = list(current_reactions.get(emoji, []))
    if current_user.id in user_list:
        user_list.remove(current_user.id)
        if not user_list:
            del current_reactions[emoji]
        else:
            current_reactions[emoji] = user_list
    else:
        user_list.append(current_user.id)
        current_reactions[emoji] = user_list

    msg.reactions = current_reactions
    db.commit()
    db.refresh(msg)

    resp = _map_direct_message_public(msg, db)
    sync_payload = {
        "type": "dm_reaction",
        "data": {
            "message_id": msg.id,
            "conversation_id": msg.conversation_id,
            "partner_id": msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id,
            "reactions": msg.reactions
        }
    }

    if msg.conversation_id:
        members = db.query(DBConversationMember).filter(DBConversationMember.conversation_id == msg.conversation_id).all()
        for m in members:
            manager.send_personal_message_sync(sync_payload, m.user_id)
    else:
        partner_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        manager.send_personal_message_sync(sync_payload, current_user.id)
        if partner_id:
            manager.send_personal_message_sync(sync_payload, partner_id)

    return resp

@dm_router.post("/typing", status_code=200)
async def send_typing_signal(
    payload: TypingSignalRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    typing_payload = {
        "type": "dm_typing",
        "data": {
            "user_id": current_user.id,
            "username": current_user.username,
            "is_group": payload.is_group,
            "target_id": payload.target_id
        }
    }

    if payload.is_group:
        members = db.query(DBConversationMember).filter(DBConversationMember.conversation_id == payload.target_id).all()
        for m in members:
            if m.user_id != current_user.id:
                manager.send_personal_message_sync(typing_payload, m.user_id)
    else:
        manager.send_personal_message_sync(typing_payload, payload.target_id)

    return {"status": "ok"}

@dm_router.post("/messages/bulk-delete", status_code=200)
async def bulk_delete_messages(
    payload: BulkDeleteMessagesRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not payload.message_ids:
        return {"deleted_count": 0}

    query = db.query(DBDirectMessage).filter(DBDirectMessage.id.in_(payload.message_ids))
    if not current_user.is_admin:
        query = query.filter(or_(DBDirectMessage.sender_id == current_user.id, DBDirectMessage.receiver_id == current_user.id))

    messages_to_delete = query.all()
    deleted_ids = [m.id for m in messages_to_delete]

    for m in messages_to_delete:
        db.delete(m)
    db.commit()

    broadcast = {
        "type": "dm_bulk_deleted",
        "data": { "message_ids": deleted_ids }
    }
    manager.broadcast_sync(broadcast)
    return {"deleted_count": len(deleted_ids)}

@dm_router.post("/conversation/{target_id}/clean", status_code=200)
async def clean_conversation_history(
    target_id: int,
    payload: CleanConversationRequest,
    is_group: bool = False,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(DBDirectMessage)
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
            DBDirectMessage.conversation_id.is_(None)
        )

    if payload.only_my_messages:
        query = query.filter(DBDirectMessage.sender_id == current_user.id)

    if payload.days and payload.days > 0:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=payload.days)
        query = query.filter(DBDirectMessage.sent_at < cutoff)

    deleted_count = query.delete(synchronize_session=False)
    db.commit()

    sync_payload = {
        "type": "dm_cleaned",
        "data": {
            "conversation_id": target_id if is_group else None,
            "partner_id": target_id if not is_group else None
        }
    }
    if is_group:
        members = db.query(DBConversationMember).filter(DBConversationMember.conversation_id == target_id).all()
        for m in members:
            manager.send_personal_message_sync(sync_payload, m.user_id)
    else:
        manager.send_personal_message_sync(sync_payload, current_user.id)
        manager.send_personal_message_sync(sync_payload, target_id)

    return {"deleted_count": deleted_count}

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

    # 2. Fetch Legacy 1-on-1 DMs with window function for speed
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
    partner_ids = []
    
    # Collect partners to batch query unread counts
    for msg in latest_dms:
        partner = msg.sender if msg.receiver_id == current_user.id else msg.receiver
        partner_ids.append(partner.id)

    # Batch fetch unread counts
    if partner_ids:
        unread_counts_rows = db.query(
            DBDirectMessage.sender_id,
            func.count(DBDirectMessage.id)
        ).filter(
            DBDirectMessage.sender_id.in_(partner_ids),
            DBDirectMessage.receiver_id == current_user.id,
            DBDirectMessage.read_at == None,
            DBDirectMessage.conversation_id == None
        ).group_by(DBDirectMessage.sender_id).all()
        unread_counts = {r[0]: r[1] for r in unread_counts_rows}
    else:
        unread_counts = {}

    for msg in latest_dms:
        partner = msg.sender if msg.receiver_id == current_user.id else msg.receiver
        unread = unread_counts.get(partner.id, 0)
        
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
    min_date = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    all_convos.sort(
        key=lambda x: (
            x.last_message_at.replace(tzinfo=datetime.timezone.utc) 
            if x.last_message_at and x.last_message_at.tzinfo is None 
            else (x.last_message_at or min_date)
        ), 
        reverse=True
    )
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
    return [_map_direct_message_public(m, db) for m in messages]

@dm_router.post("/conversation/{user_id}/read", status_code=200)
async def mark_conversation_as_read(
    user_id: int,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    stmt = (
        update(DBDirectMessage)
        .where(
            DBDirectMessage.sender_id == user_id,
            DBDirectMessage.receiver_id == current_user.id,
            DBDirectMessage.read_at.is_(None)
        )
        .values(read_at=now_utc)
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
    
    # Permission check: Sender, Recipient, or Admin
    # This allows either party to clear content from the conversation.
    is_sender = msg.sender_id == current_user.id
    is_recipient = msg.receiver_id == current_user.id
    
    if not (is_sender or is_recipient or current_user.is_admin):
        raise HTTPException(status_code=403, detail="You do not have permission to delete this message.")
    
    convo_id = msg.conversation_id
    partner_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id

    db.delete(msg)
    db.commit()
    
    # Notify involved parties to refresh their view
    refresh_payload = {
        "type": "dm_deleted",
        "data": {
            "message_id": message_id,
            "conversation_id": convo_id,
            "partner_id": partner_id
        }
    }
    
    if convo_id:
        # Group: notify all members
        members = db.query(DBConversationMember).filter_by(conversation_id=convo_id).all()
        for m in members:
            manager.send_personal_message_sync(refresh_payload, m.user_id)
    else:
        # 1-on-1: notify both
        manager.send_personal_message_sync(refresh_payload, current_user.id)
        manager.send_personal_message_sync(refresh_payload, partner_id)

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
