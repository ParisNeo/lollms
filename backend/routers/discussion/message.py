# backend/routers/discussion.py
# Standard Library Imports
import base64
import io
import json
import re
import shutil
import uuid
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
import traceback
import threading
import asyncio
import zipfile

# Third-Party Imports
import fitz  # PyMuPDF
from docx import Document as DocxDocument
from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query,
    UploadFile, status)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               PlainTextResponse, StreamingResponse)
from lollms_client import (LollmsClient, LollmsDiscussion, LollmsMessage,
                           LollmsPersonality, MSG_TYPE)
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ascii_colors import ASCIIColors, trace_exception

# Local Application Imports
from backend.config import APP_VERSION, SERVER_CONFIG
from backend.db import get_db
from backend.db.models.config import TTIBinding as DBTTIBinding
from backend.db.models.db_task import DBTask
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.user import (User as DBUser, UserMessageGrade,
                                     UserStarredDiscussion)
from backend.discussion import get_user_discussion, get_user_discussion_manager
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request
from backend.models import (UserAuthDetails, ArtefactInfo, ContextStatusResponse,
                            DataZones, DiscussionBranchSwitchRequest,
                            DiscussionDataZoneUpdate, DiscussionExportRequest,
                            DiscussionImageUpdateResponse,
                            DiscussionInfo, DiscussionImportRequest,
                            DiscussionRagDatastoreUpdate, DiscussionSendRequest,
                            DiscussionTitleUpdate, ExportContextRequest,
                            ExportData, LoadArtefactRequest, ManualMessageCreate,
                            MessageCodeExportRequest, MessageContentUpdate,
                            MessageGradeUpdate, MessageOutput,
                            MessageUpdateWithImages, TaskInfo,
                            UnloadArtefactRequest, ArtefactCreateManual, ArtefactUpdate)
from backend.session import (get_current_active_user,
                             get_current_db_user_from_token,
                             get_safe_store_instance,
                             get_user_discussion_assets_path,
                             get_user_lollms_client,
                             get_user_temp_uploads_path, user_sessions)
from backend.task_manager import task_manager, Task

# safe_store is needed for RAG callbacks
try:
    import safe_store
except ImportError:
    safe_store = None

message_grade_lock = threading.Lock()
def build_message_router(router: APIRouter):
    @router.put("/{discussion_id}/messages/{message_id}/grade", response_model=MessageOutput)
    async def grade_discussion_message(discussion_id: str, message_id: str, grade_update: MessageGradeUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
        username = current_user.username
        db_user = db.query(DBUser).filter(DBUser.username == username).one()
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        if not discussion_obj: raise HTTPException(status_code=404, detail="Discussion not found.")
        with message_grade_lock:
            grade = db.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id, message_id=message_id).first()
            if grade: grade.grade += grade_update.change
            else:
                grade = UserMessageGrade(user_id=db_user.id, discussion_id=discussion_id, message_id=message_id, grade=grade_update.change)
                db.add(grade)
            db.commit()
            db.refresh(grade)
            current_grade = grade.grade
        branch = discussion_obj.get_branch(discussion_obj.active_branch_id)
        target_message = next((msg for msg in branch if msg.id == message_id), None)
        if not target_message: raise HTTPException(status_code=404, detail="Message not found in active branch.")
        full_image_refs = [ f"data:image/png;base64,{img}" for img in target_message.images or []]

        msg_metadata = target_message.metadata or {}
        return MessageOutput(
            id=target_message.id, sender=target_message.sender, sender_type=target_message.sender_type, content=target_message.content,
            parent_message_id=target_message.parent_id, binding_name=target_message.binding_name, model_name=target_message.model_name,
            token_count=target_message.tokens, sources=msg_metadata.get('sources'), events=msg_metadata.get('events'),
            image_references=full_image_refs, user_grade=current_grade, created_at=target_message.created_at,
            branch_id=discussion_obj.active_branch_id, branches=None
        )

    @router.put("/{discussion_id}/messages/{message_id}", response_model=MessageOutput)
    async def update_discussion_message(
        discussion_id: str,
        message_id: str,
        payload: MessageUpdateWithImages,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        username = current_user.username
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        if not discussion_obj:
            raise HTTPException(status_code=404, detail="Discussion not found.")
        
        target_message = discussion_obj.get_message(message_id)
        if not target_message:
            raise HTTPException(status_code=404, detail="Message not found in discussion.")

        target_message.content = payload.content

        final_images_b64 = []
        final_images_b64.extend(payload.kept_images_b64)

        for b64_data_uri in payload.new_images_b64:
            try:
                _, encoded = b64_data_uri.split(",", 1)
                final_images_b64.append(encoded)
            except ValueError:
                final_images_b64.append(b64_data_uri)
        
        target_message.images = final_images_b64
        discussion_obj.commit()

        db_user = db.query(DBUser).filter(DBUser.username == username).one()
        grade = db.query(UserMessageGrade.grade).filter_by(user_id=db_user.id, discussion_id=discussion_id, message_id=message_id).scalar() or 0
        
        full_image_refs = [f"data:image/png;base64,{img}" for img in target_message.images or []]
        active_images = [True] * len(full_image_refs)

        msg_metadata = target_message.metadata or {}
        return MessageOutput(
            id=target_message.id, sender=target_message.sender, sender_type=target_message.sender_type,
            content=target_message.content, parent_message_id=target_message.parent_id,
            binding_name=target_message.binding_name, model_name=target_message.model_name,
            token_count=target_message.tokens, sources=msg_metadata.get('sources'),
            events=msg_metadata.get('events'), image_references=full_image_refs,
            active_images=active_images, user_grade=grade,
            created_at=target_message.created_at, branch_id=discussion_obj.active_branch_id
        )

    @router.post("/{discussion_id}/messages", response_model=MessageOutput)
    async def add_manual_message(
        discussion_id: str,
        payload: ManualMessageCreate,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        username = current_user.username
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, "interact")
        if not discussion_obj:
            raise HTTPException(status_code=404, detail="Discussion not found.")

        if payload.sender_type not in ['user', 'assistant']:
            raise HTTPException(status_code=400, detail="Invalid sender_type.")

        sender_name = username
        if payload.sender_type == 'assistant':
            db_pers = db.query(DBPersonality).filter(DBPersonality.id == current_user.active_personality_id).first()
            sender_name = db_pers.name if db_pers else "assistant"

        try:
            new_message = discussion_obj.add_message(
                sender=sender_name,
                content=payload.content,
                parent_id=payload.parent_message_id,
                sender_type=payload.sender_type
            )
            discussion_obj.commit()
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to add message to discussion: {e}")

        return MessageOutput(
            id=new_message.id,
            sender=new_message.sender,
            sender_type=new_message.sender_type,
            content=new_message.content,
            parent_message_id=new_message.parent_id,
            binding_name=new_message.binding_name,
            model_name=new_message.model_name,
            token_count=new_message.tokens,
            sources=[],
            events=[],
            image_references=[],
            user_grade=0,
            created_at=new_message.created_at,
            branch_id=discussion_obj.active_branch_id
        )

    @router.delete("/{discussion_id}/messages/{message_id}", status_code=200)
    async def delete_discussion_message(discussion_id: str, message_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
        username = current_user.username
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        if not discussion_obj: raise HTTPException(status_code=404, detail="Discussion not found.")
        try: discussion_obj.delete_branch(message_id)
        except ValueError as e: raise HTTPException(status_code=404, detail=str(e))
        db_user = db.query(DBUser).filter(DBUser.username == username).one()
        db.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id, message_id=message_id).delete(synchronize_session=False)
        db.commit()
        return {"message": "Message and its branch deleted successfully."}

