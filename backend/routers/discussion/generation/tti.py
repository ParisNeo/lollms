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


def build_tti_generation_router(router: APIRouter):
    @router.post("/{discussion_id}/generate_image", response_model=TaskInfo, status_code=202)
    def generate_image_from_data_zone(
        discussion_id: str,
        prompt: str = Form(...),
        negative_prompt: str = Form(""),
        width: Optional[int] = Form(None),
        height: Optional[int] = Form(None),
        parent_message_id: Optional[str] = Form(None),
        generation_params_json: str = Form("{}"),
        current_user: UserAuthDetails = Depends(get_current_active_user)
    ):
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

    @router.post("/{discussion_id}/messages/{message_id}/trigger_tag", response_model=TaskInfo, status_code=202)
    def trigger_message_tag_generation(
        discussion_id: str,
        message_id: str,
        tag_content: str = Form(...),
        tag_type: str = Form(...), # generate, slides, edit
        width: int = Form(1024),
        height: int = Form(1024),
        num_images: int = Form(1),
        custom_prompt: Optional[str] = Form(None), # NEW: Added support for prompt override
        current_user: UserAuthDetails = Depends(get_current_active_user)
    ):
        """
        Manually triggers a generation task based on a tag found in a message.
        Allows prompt control by accepting a custom_prompt parameter.
        """
        discussion = get_user_discussion(current_user.username, discussion_id)
        if not discussion:
            raise HTTPException(status_code=404, detail="Discussion not found")
        
        msg = discussion.get_message(message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")

        task = None
        # Use custom_prompt if provided, otherwise fallback to the tag's inner content
        final_prompt = custom_prompt if custom_prompt and custom_prompt.strip() else tag_content
        
        if tag_type == 'slides':
            task = task_manager.submit_task(
                name="Generating Slides (Regenerate)",
                target=_generate_slides_task,
                args=(current_user.username, discussion_id, message_id, final_prompt, width, height, num_images),
                description=f"Regenerating slides for: {final_prompt[:30]}...",
                owner_username=current_user.username
            )
        elif tag_type == 'generate':
            task = task_manager.submit_task(
                name="Generating Image (Regenerate)",
                target=_generate_image_task,
                # Passing the existing message_id as parent to preserve history
                args=(current_user.username, discussion_id, final_prompt, "", width, height, {}, msg.id),
                description=f"Regenerating image for: {final_prompt[:30]}...",
                owner_username=current_user.username
            )
        elif tag_type == 'edit':
             # For edit, logic would involve resolving the source image from the tag index
             # and passing it to the _image_studio_edit_task logic. 
             # Implementation depends on the task signature.
             pass

        if not task:
             raise HTTPException(status_code=400, detail=f"Unsupported tag type or configuration for regeneration: {tag_type}")

        return task
