# backend/routers/discussion/context.py
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
from ascii_colors import trace_exception, ASCIIColors

from backend.db import get_db
from backend.db.models.user import User as DBUser, UserMessageGrade, UserStarredDiscussion
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.discussion import SharedDiscussionLink as DBSharedDiscussionLink
from backend.discussion import get_user_discussion, get_user_discussion_manager
from backend.models import UserAuthDetails, ContextStatusResponse, DiscussionInfo, MessageOutput, DiscussionBranchSwitchRequest, DiscussionTitleUpdate, ManualMessageCreate, MessageGradeUpdate, MessageUpdateWithImages
from backend.session import get_current_active_user, get_current_db_user_from_token, get_safe_store_instance, get_user_discussion_assets_path, get_user_lollms_client, get_user_temp_uploads_path, user_sessions
from backend.config import SERVER_CONFIG
from backend.ws_manager import manager
from .helpers import get_discussion_and_owner_for_request
from lollms_client import MSG_TYPE, LollmsPersonality
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request

def build_context_router(router: APIRouter):
    @router.get("/{discussion_id}/context_status", response_model=ContextStatusResponse)
    async def get_discussion_context_status(
        discussion_id: str,
        current_user: DBUser = Depends(get_current_db_user_from_token),
        db: Session = Depends(get_db)  
    ):
        """
        Retrieves context status.
        Uses get_current_db_user_from_token to avoid heavy LollmsClient init on every poll.
        """
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        if not discussion:
            raise HTTPException(status_code=404, detail="Discussion not found")
        
        try:
            # Try to attach client for token counting, but fail gracefully if binding is down
            if not getattr(discussion, 'lollms_client', None):
                try:
                    # This might fail if the binding is not configured correctly
                    discussion.lollms_client = get_user_lollms_client(current_user.username)
                except Exception as e:
                    # Log but continue. get_context_status needs to handle None client or we return empty.
                    # Usually get_context_status checks if client exists.
                    pass
            
            # If client is still missing/failed, get_context_status might fail depending on implementation.
            # We wrap the call itself.
            status = discussion.get_context_status()
            return status

        except Exception as e:
            # Do NOT raise 500, or frontend polling will spam errors. Return degraded status.
            # trace_exception(e) # Optional: comment out to reduce log spam if this happens often
            return ContextStatusResponse(current_tokens=0, max_tokens=0, zones={})


    @router.get("/{discussion_id}/export_context", response_class=PlainTextResponse)
    async def export_discussion_context(
        discussion_id: str,
        current_user: DBUser = Depends(get_current_db_user_from_token),
        db: Session = Depends(get_db)
    ):
        # Exports might need the client for tokenization/formatting, but we try best effort.
        user_model_full = current_user.lollms_model_name
        binding_alias = None
        if user_model_full and '/' in user_model_full:
            binding_alias, _ = user_model_full.split('/', 1)
        
        lc = None
        try:
            lc = get_user_lollms_client(current_user.username, binding_alias)
        except Exception:
            pass

        discussion_obj = get_user_discussion(current_user.username, discussion_id, lollms_client=lc)
        if not discussion_obj:
            raise HTTPException(status_code=404, detail="Discussion not found.")

        try:
            context_string = discussion_obj.export("markdown")
            if isinstance(context_string, str):
                return PlainTextResponse(content=context_string)
            else:
                return PlainTextResponse(content="Error exporting context.")
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to export discussion context: {e}")
