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

class UrlImportRequest(BaseModel):
    url: str


def _to_task_info(db_task: DBTask) -> TaskInfo:
    """Converts a DBTask SQLAlchemy model to a TaskInfo Pydantic model."""
    if not db_task:
        return None
    return TaskInfo(
        id=db_task.id, name=db_task.name, description=db_task.description,
        status=db_task.status, progress=db_task.progress,
        logs=[log for log in (db_task.logs or [])], result=db_task.result, error=db_task.error,
        created_at=db_task.created_at, started_at=db_task.started_at, updated_at=db_task.updated_at, completed_at=db_task.completed_at,
        file_name=db_task.file_name, total_files=db_task.total_files,
        owner_username=db_task.owner.username if db_task.owner else "System"
    )


def _generate_image_task(task: Task, username: str, discussion_id: str, prompt: str):
    task.log("Starting image generation task...")
    task.set_progress(5)

    with task.db_session_factory() as db:
        user = db.query(DBUser).filter(DBUser.username == username).first()
        if not user:
            raise Exception(f"User '{username}' not found.")

        user_tti_model_full = user.tti_binding_model_name
        
        selected_binding = None
        selected_model_name = None
        binding_config = {}

        if user_tti_model_full and '/' in user_tti_model_full:
            binding_alias, model_name = user_tti_model_full.split('/', 1)
            selected_binding = db.query(DBTTIBinding).filter(DBTTIBinding.alias == binding_alias, DBTTIBinding.is_active == True).first()
            selected_model_name = model_name
        
        if not selected_binding:
            task.log("User's preferred TTI model not found or not set. Falling back to the first available active TTI binding.", "WARNING")
            selected_binding = db.query(DBTTIBinding).filter(DBTTIBinding.is_active == True).order_by(DBTTIBinding.id).first()
            if selected_binding:
                selected_model_name = selected_binding.default_model_name
        
        if not selected_binding:
            raise Exception("No active TTI (Text-to-Image) binding found in system settings.")
        
        task.log(f"Using TTI binding: {selected_binding.alias}")
        if selected_model_name:
            task.log(f"Using TTI model: {selected_model_name}")
        
        binding_config = selected_binding.config.copy() if selected_binding.config else {}
        
        model_aliases = selected_binding.model_aliases or {}
        alias_info = model_aliases.get(selected_model_name)
        
        if alias_info:
            task.log(f"Applying settings from model alias '{alias_info.get('title', selected_model_name)}'.")
            for key, value in alias_info.items():
                if key not in ['title', 'description', 'icon'] and value is not None:
                    binding_config[key] = value
        
        allow_override = (alias_info or {}).get('allow_parameters_override', True)
        if allow_override:
            user_configs = user.tti_models_config or {}
            model_user_config = user_configs.get(user_tti_model_full)
            if model_user_config:
                task.log("Applying user-specific settings for this model.")
                for key, value in model_user_config.items():
                    if value is not None:
                        binding_config[key] = value
        else:
            task.log("User overrides are disabled by admin for this model alias.")

        if selected_model_name:
            binding_config['model_name'] = selected_model_name
            
        task.set_progress(10)

    try:
        lc = LollmsClient(
            tti_binding_name=selected_binding.name,
            tti_binding_config=binding_config
        )
        task.log("LollmsClient initialized for TTI.")
        task.set_progress(20)

        image_bytes = lc.tti.generate_image(prompt=prompt)
        task.log("Image data received from binding.")
        task.set_progress(80)

        if not image_bytes:
            raise Exception("TTI binding returned empty image data.")

        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        discussion = get_user_discussion(username, discussion_id)
        if not discussion:
            raise Exception("Discussion not found after image generation.")
        
        discussion.add_discussion_image(b64_image, source="generation")
        discussion.commit()
        task.log("Image added to discussion and saved.")
        task.set_progress(100)
        
        all_images_info = discussion.get_discussion_images()
        
        return {
            "discussion_id": discussion_id,
            "zone": "discussion_images",
            "discussion_images": [img_info['data'] for img_info in all_images_info],
            "active_discussion_images": [img_info['active'] for img_info in all_images_info]
        }
    except Exception as e:
        task.log(f"Image generation failed: {e}", "ERROR")
        trace_exception(e)
        raise e

def _import_artefact_from_url_task(task: Task, username: str, discussion_id: str, url: str):
    if ScrapeMaster is None:
        raise ImportError("ScrapeMaster library is not installed and could not be installed automatically.")
    
    task.log("Starting URL import task for artefact...")
    task.set_progress(5)
    
    try:
        task.log(f"Scraping URL: {url}")
        scraper = ScrapeMaster(url)
        markdown_content = scraper.scrape_markdown()
        task.set_progress(70)

        if not markdown_content or not markdown_content.strip():
            task.log("No main content could be extracted from the URL.", "WARNING")
            raise ValueError("No main content found at the provided URL.")

        task.log(f"Successfully scraped {len(markdown_content)} characters.")
        discussion = get_user_discussion(username, discussion_id)
        if not discussion:
            raise ValueError("Discussion not found after scraping.")

        artefact_info = discussion.add_artefact(
            title=url,
            content=markdown_content.strip(),
            author=username
        )
        discussion.commit()
        task.set_progress(100)
        
        task.log(f"Artefact '{url}' imported from URL and saved.")
        if isinstance(artefact_info.get('created_at'), datetime):
            artefact_info['created_at'] = artefact_info['created_at'].isoformat()
        if isinstance(artefact_info.get('updated_at'), datetime):
            artefact_info['updated_at'] = artefact_info['updated_at'].isoformat()
        
        return artefact_info
    except Exception as e:
        task.log(f"Failed to import from URL: {e}", "ERROR")
        trace_exception(e)
        raise e

def _process_data_zone_task(task: Task, username: str, discussion_id: str, contextual_prompt: Optional[str]):
    task.log("Starting data zone processing task...")
    discussion = get_user_discussion(username, discussion_id)
    if not discussion:
        raise ValueError("Discussion not found.")
    
    with task.db_session_factory() as db:
        db_user = db.query(DBUser).filter(DBUser.username == username).first()
        if not db_user:
            raise Exception(f"User '{username}' not found.")
        
        user_data_zone = db_user.data_zone or ""
        now = datetime.now()
        replacements = {
            "{{date}}": now.strftime("%Y-%m-%d"),
            "{{time}}": now.strftime("%H:%M:%S"),
            "{{datetime}}": now.strftime("%Y-%m-%d %H:%M:%S"),
            "{{user_name}}": username,
        }
        processed_user_data_zone = user_data_zone
        for placeholder, value in replacements.items():
            processed_user_data_zone = processed_user_data_zone.replace(placeholder, value)
    
    all_images_info = discussion.get_discussion_images()
    
    if (not discussion.discussion_data_zone or not discussion.discussion_data_zone.strip()) and not all_images_info and (not contextual_prompt or not contextual_prompt.strip()):
        task.log("Data zone and prompt are empty, nothing to process.", "WARNING")
        return {"discussion_id": discussion_id, "new_content": ""}
    
    def summary_callback(message: str, msg_type: Any, params: Optional[Dict] = None):
        """Callback to update the task in real-time."""
        task.log(message)
        task.set_description(message)
        if params and 'progress' in params:
            task.set_progress(int(params['progress']))
        return True

    prompt_to_use = contextual_prompt
    if (not discussion.discussion_data_zone or not discussion.discussion_data_zone.strip()) and not prompt_to_use and all_images_info:
        prompt_to_use = "Describe the attached image(s) in detail."
        task.log(f"No text found. Using default prompt: '{prompt_to_use}'")

    discussion_images_b64 = [img_info['data'] for img_info in all_images_info if img_info.get('active', True)]
    lc = get_user_lollms_client(username)
    task.log(f"Processing:")
    task.log(f"content: {discussion.discussion_data_zone[:1000] if discussion.discussion_data_zone else 'No text'}")
    task.log(f"prompt: {prompt_to_use}")
    task.log(f"Nb images: {len(discussion_images_b64) if discussion_images_b64 else 0}")
    
    summary = lc.long_context_processing(
        discussion.discussion_data_zone,
        images=discussion_images_b64,
        contextual_prompt=prompt_to_use,
        system_prompt=processed_user_data_zone,
        streaming_callback=summary_callback
    )
    
    if isinstance(summary, dict) and 'error' in summary:
        error_message = f"Failed to process data zone: {summary['error']}"
        task.log(error_message, "ERROR")
        raise Exception(error_message)

    if not isinstance(summary, str):
        task.log(f"Unexpected non-string result from processing: {type(summary)}. Converting to string.", "WARNING")
        summary = str(summary)
        
    discussion.discussion_data_zone = summary
    discussion.commit()
    
    task.set_progress(100)
    task.set_description("Processing complete and saved.")
    task.log("Processing complete and saved.")
    
    return {"discussion_id": discussion_id, "new_content": summary, "zone": "discussion"}

def _memorize_ltm_task(task: Task, username: str, discussion_id: str, db:Session):
    task.log("Starting long-term memory memorization task...")
    db_user = db.query(DBUser).filter(DBUser.username == username).first()
    
    discussion = get_user_discussion(username, discussion_id)
    if not discussion:
        raise ValueError("Discussion not found.")
    
    task.set_progress(20)
    discussion.memorize()
    discussion.commit()
    task.set_progress(100)
    db_user.memory = discussion.memory
    try:
        db.commit()
        db.refresh(db_user)
    except Exception as e:
        trace_exception(e)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    
    task.log("Memorization complete and saved.")
    return {"discussion_id": discussion_id, "new_content": discussion.memory, "zone": "memory"}


def _prune_empty_discussions_task(task: Task, username: str):
    task.log("Starting prune of empty and single-message discussions.")
    dm = get_user_discussion_manager(username)
    all_discs_infos = dm.list_discussions()
    total_discussions = len(all_discs_infos)
    discussions_to_delete = []

    task.log(f"Scanning {total_discussions} discussions for user '{username}'.")
    
    discussion_db_session = dm.get_session()
    try:
        for i, disc_info in enumerate(all_discs_infos):
            if task.cancellation_event.is_set():
                task.log("Scan for prunable discussions cancelled.", level="WARNING")
                break
            discussion_id = disc_info['id']
            try:
                message_count = discussion_db_session.query(dm.MessageModel).filter(dm.MessageModel.discussion_id == discussion_id).count()
                if message_count <= 1:
                    discussions_to_delete.append(discussion_id)
            except Exception as e:
                task.log(f"Could not process discussion {discussion_id} for pruning: {e}", level="WARNING")
            
            progress = int(50 * (i + 1) / total_discussions) if total_discussions > 0 else 50
            task.set_progress(progress)
    finally:
        discussion_db_session.close()

    if task.cancellation_event.is_set():
        return {"message": "Pruning task cancelled during scan.", "deleted_count": 0}

    if not discussions_to_delete:
        task.log("No empty discussions found to prune.")
        task.set_progress(100)
        return {"message": "Pruning complete. No empty discussions found.", "deleted_count": 0}

    task.log(f"Found {len(discussions_to_delete)} discussions to delete. Starting deletion process...")
    task.set_progress(50)
    deleted_count = 0
    failed_count = 0
    
    with task.db_session_factory() as db:
        try:
            db_user = db.query(DBUser).filter(DBUser.username == username).one()
            
            for discussion_id in discussions_to_delete:
                if task.cancellation_event.is_set():
                    break

                try:
                    dm.delete_discussion(discussion_id)
                    assets_path = get_user_discussion_assets_path(username) / discussion_id
                    if assets_path.exists() and assets_path.is_dir():
                        shutil.rmtree(assets_path, ignore_errors=True)
                    
                    db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).delete(synchronize_session=False)
                    db.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id).delete(synchronize_session=False)

                    deleted_count += 1
                except Exception as e:
                    print(f"ERROR: Failed to delete discussion {discussion_id} during prune: {e}")
                    failed_count += 1
            
            db.commit()

            task.set_progress(100)
            
            if deleted_count > 0:
                task.log(f"Successfully pruned {deleted_count} discussions.")
            if failed_count > 0:
                task.log(f"Failed to prune {failed_count} discussions. Check server console for details.", level="ERROR")
            if task.cancellation_event.is_set():
                task.log(f"Pruning cancelled after deleting {deleted_count} discussions.", level="WARNING")

            return {"message": f"Pruning complete. Deleted: {deleted_count}, Failed: {failed_count}.", "deleted_count": deleted_count, "failed_count": failed_count}
        except Exception as e:
            db.rollback()
            task.log(f"A critical database error occurred during the commit phase: {e}", level="CRITICAL")
            raise e
