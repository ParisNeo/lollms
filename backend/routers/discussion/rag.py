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

try:
    from scrapemaster import ScrapeMaster
except ImportError:
    try:
        import pipmaster as pm
        print("ScrapeMaster not installed. Installing it for you.")
        pm.install("ScrapeMaster")
        from scrapemaster import ScrapeMaster
    except Exception as ex:
        traceback.print_exc()
        print("Couldn't install ScrapeMaster. Please install it manually (`pip install ScrapeMaster`)")
        ScrapeMaster = None

def build_rag_router(router: APIRouter):
    ## -- rag datastores ----
    @router.put("/{discussion_id}/rag_datastore", response_model=DiscussionInfo)
    async def update_discussion_rag_datastores(
        discussion_id: str,
        update_payload: DiscussionRagDatastoreUpdate,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ) -> DiscussionInfo:
        username = current_user.username
        discussion_obj = get_user_discussion(username, discussion_id)
        if not discussion_obj:
            raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

        if update_payload.rag_datastore_ids:
            for ds_id in update_payload.rag_datastore_ids:
                try:
                    get_safe_store_instance(username, ds_id, db)
                except HTTPException as e:
                    raise HTTPException(status_code=400, detail=f"Invalid or inaccessible RAG datastore ID: {ds_id} ({e.detail})")

        discussion_obj.set_metadata_item('rag_datastore_ids', update_payload.rag_datastore_ids)

        user_db = db.query(DBUser).filter(DBUser.username == username).one()
        is_starred = db.query(UserStarredDiscussion).filter_by(user_id=user_db.id, discussion_id=discussion_id).first() is not None

        return DiscussionInfo(
            id=discussion_id,
            title=discussion_obj.metadata.get('title', "Untitled"),
            is_starred=is_starred,
            rag_datastore_ids=discussion_obj.metadata.get('rag_datastore_ids'),
            active_tools=discussion_obj.metadata.get('active_tools', []),
            active_branch_id=discussion_obj.active_branch_id,
            created_at=discussion_obj.created_at,
            last_activity_at=discussion_obj.updated_at
        )