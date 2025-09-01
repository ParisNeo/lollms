# backend/routers/discussion/core.py
import json
import shutil
import uuid
import threading
import asyncio
import base64
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from ascii_colors import trace_exception

from backend.db import get_db
from backend.db.models.user import User as DBUser, UserMessageGrade, UserStarredDiscussion
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.discussion import SharedDiscussionLink as DBSharedDiscussionLink
from backend.discussion import get_user_discussion, get_user_discussion_manager
from backend.models import UserAuthDetails, ContextStatusResponse, DiscussionInfo, MessageOutput, DiscussionBranchSwitchRequest, DiscussionTitleUpdate, ManualMessageCreate, MessageGradeUpdate, MessageUpdateWithImages
from backend.session import get_current_active_user, get_safe_store_instance, get_user_discussion_assets_path, get_user_lollms_client, get_user_temp_uploads_path, user_sessions
from backend.config import SERVER_CONFIG
from backend.ws_manager import manager
from .helpers import get_discussion_and_owner_for_request
from lollms_client import MSG_TYPE, LollmsPersonality
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request

from backend.db import get_db



def build_context_router(router: APIRouter):
    @router.get("/{discussion_id}/context_status", response_model=ContextStatusResponse)
    async def get_discussion_context_status(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)  
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        if not discussion:
            raise HTTPException(status_code=404, detail="Discussion not found")
        
        try:
            status = discussion.get_context_status()
            return status
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to get context status: {e}")


    @router.get("/{discussion_id}/export_context", response_class=PlainTextResponse)
    async def export_discussion_context(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        user_model_full = current_user.lollms_model_name
        binding_alias = None
        if user_model_full and '/' in user_model_full:
            binding_alias, _ = user_model_full.split('/', 1)
        
        lc = get_user_lollms_client(current_user.username, binding_alias)
        discussion_obj = get_user_discussion(current_user.username, discussion_id, lollms_client=lc)
        if not discussion_obj:
            raise HTTPException(status_code=404, detail="Discussion not found.")

        try:
            context_string = discussion_obj.export("markdown")
            if type(context_string)==str:
                return PlainTextResponse(content=context_string)
            else:
                return PlainTextResponse(content="error")
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to export discussion context: {e}")
