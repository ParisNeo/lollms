# backend/routers/discussion/generation/tti.py
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
from concurrent.futures import ThreadPoolExecutor

# Third-Party Imports
import fitz  # PyMuPDF
from docx import Document as DocxDocument
from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query,
    UploadFile, status, Body
)
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
from backend.tasks.image_generation_tasks import _generate_image_task, _generate_slides_task, _image_studio_edit_task
from backend.tasks.utils import _to_task_info
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

# Create a thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=50)

class TriggerTagRequest(BaseModel):
    tag_content: str
    tag_type: str  # generate, slides, edit
    width: int = 1024
    height: int = 1024
    num_images: int = 1
    custom_prompt: Optional[str] = None
    source_image_index: Optional[int] = None  # For edit operations

def build_tti_generation_router(router: APIRouter):
    @router.post("/{discussion_id}/generate_image", response_model=TaskInfo, status_code=202)
    async def generate_image_from_data_zone(
        discussion_id: str,
        prompt: str = Form(...),
        negative_prompt: str = Form(""),
        width: Optional[int] = Form(None),
        height: Optional[int] = Form(None),
        parent_message_id: Optional[str] = Form(None),
        generation_params_json: str = Form("{}"),
        current_user: UserAuthDetails = Depends(get_current_active_user)
    ):
        loop = asyncio.get_running_loop()

        def _execute():
            discussion = get_user_discussion(current_user.username, discussion_id)
            if not discussion:
                raise HTTPException(status_code=404, detail="Discussion not found")

            try:
                generation_params = json.loads(generation_params_json)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid format for generation parameters (kwargs).")

            db_task = task_manager.submit_task(
                name=f"Generating image for: {discussion.metadata.get('title', 'Untitled')}",
                target=_generate_image_task,
                args=(current_user.username, discussion_id, prompt, negative_prompt, width, height, generation_params, parent_message_id),
                description=f"Generating image with prompt: '{prompt[:50]}...'",
                owner_username=current_user.username
            )
            return db_task

        return await loop.run_in_executor(executor, _execute)

    @router.post("/{discussion_id}/messages/{message_id}/trigger_tag", response_model=TaskInfo, status_code=202)
    async def trigger_message_tag_generation(
        discussion_id: str,
        message_id: str,
        request: TriggerTagRequest = Body(...),
        current_user: UserAuthDetails = Depends(get_current_active_user)
    ):
        """
        Manually triggers a generation task based on a tag found in a message.
        Supports generate, slides, and edit operations.
        """
        loop = asyncio.get_running_loop()

        def _execute():
            discussion = get_user_discussion(current_user.username, discussion_id)
            if not discussion:
                raise HTTPException(status_code=404, detail="Discussion not found")

            msg = discussion.get_message(message_id)
            if not msg:
                raise HTTPException(status_code=404, detail="Message not found")

            task = None
            # Use custom_prompt if provided, otherwise fallback to the tag's inner content
            final_prompt = request.custom_prompt if request.custom_prompt and request.custom_prompt.strip() else request.tag_content

            if request.tag_type == 'slides':
                task = task_manager.submit_task(
                    name="Generating Slides (Regenerate)",
                    target=_generate_slides_task,
                    args=(current_user.username, discussion_id, message_id, final_prompt, request.width, request.height, request.num_images),
                    description=f"Regenerating slides for: {final_prompt[:30]}...",
                    owner_username=current_user.username
                )
            elif request.tag_type == 'generate':
                task = task_manager.submit_task(
                    name="Generating Image (Regenerate)",
                    target=_generate_image_task,
                    # Passing the existing message_id as parent to preserve history
                    args=(current_user.username, discussion_id, final_prompt, "", request.width, request.height, {}, msg.id),
                    description=f"Regenerating image for: {final_prompt[:30]}...",
                    owner_username=current_user.username
                )
            elif request.tag_type == 'edit':
                if request.source_image_index is None:
                    raise HTTPException(status_code=400, detail="source_image_index is required for edit operations")

                task = task_manager.submit_task(
                    name="Editing Image",
                    target=_image_studio_edit_task,
                    args=(current_user.username, discussion_id, message_id, request.source_image_index, final_prompt, request.width, request.height),
                    description=f"Editing image with prompt: {final_prompt[:30]}...",
                    owner_username=current_user.username
                )
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported tag type: {request.tag_type}")

            if not task:
                raise HTTPException(status_code=500, detail="Failed to create generation task")

            return task

        return await loop.run_in_executor(executor, _execute)
