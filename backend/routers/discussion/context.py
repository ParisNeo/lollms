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
            if not getattr(discussion, 'lollms_client', None):
                try:
                    discussion.lollms_client = get_user_lollms_client(current_user.username)
                except Exception:
                    pass

            # Ensure discussion max_context_size is healthy (> 1)
            if not getattr(discussion, 'max_context_size', None) or discussion.max_context_size <= 1:
                if getattr(discussion, 'lollms_client', None):
                    try:
                        ctx = discussion.lollms_client.get_ctx_size()
                        if ctx and int(ctx) > 1:
                            discussion.max_context_size = int(ctx)
                    except Exception:
                        pass
                if not getattr(discussion, 'max_context_size', None) or discussion.max_context_size <= 1:
                    cfg_ctx = getattr(discussion.lollms_client, 'llm_binding_config', {}).get('ctx_size') if getattr(discussion, 'lollms_client', None) else None
                    discussion.max_context_size = int(cfg_ctx) if cfg_ctx and int(cfg_ctx) > 1 else 4096

            status = discussion.get_context_status()

            # Guard against status returning max_tokens <= 1
            if isinstance(status, dict):
                if not status.get("max_tokens") or status.get("max_tokens") <= 1:
                    status["max_tokens"] = discussion.max_context_size or 4096
                    cur = status.get("current_tokens", 0)
                    status["percent"] = (cur / status["max_tokens"]) * 100 if status["max_tokens"] > 0 else 0
            elif hasattr(status, "max_tokens"):
                if not status.max_tokens or status.max_tokens <= 1:
                    status.max_tokens = discussion.max_context_size or 4096
                    status.percent = (status.current_tokens / status.max_tokens) * 100 if status.max_tokens > 0 else 0

            return status

        except Exception as e:
            trace_exception(e)
            resolved_max = getattr(discussion, 'max_context_size', 4096)
            if not resolved_max or resolved_max <= 1:
                resolved_max = 4096
            return ContextStatusResponse(current_tokens=0, max_tokens=resolved_max, zones={})

    @router.get("/{discussion_id}/generation_status")
    async def get_discussion_generation_status(
        discussion_id: str,
        current_user: DBUser = Depends(get_current_db_user_from_token),
        db: Session = Depends(get_db)
    ):
        """Returns whether a background generation is actively running for this discussion."""
        user_session = user_sessions.get(current_user.username, {})
        active_controls = user_session.get("active_generation_control", {})
        is_generating = discussion_id in active_controls and not active_controls[discussion_id].is_set()
        return {"discussion_id": discussion_id, "is_generating": is_generating}


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
