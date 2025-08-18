# backend/routers/discussion.py

import threading
# Standard Library Imports
import os
import shutil
import uuid
import json
from pathlib import Path
from typing import List, Dict, Optional, Any, AsyncGenerator
import datetime
import asyncio
import threading
import traceback
import base64
from functools import partial
from ascii_colors import trace_exception
from fastapi.encoders import jsonable_encoder
from fastapi.responses import PlainTextResponse
import zipfile
import io
import re
# Third-Party Imports
from fastapi import (
    HTTPException, Depends, Form, File, UploadFile,
    APIRouter, Query, BackgroundTasks, status)
from pydantic import BaseModel
from backend.models import DiscussionRagDatastoreUpdate # Make sure it's the updated one
from fastapi.responses import (
    HTMLResponse,
    StreamingResponse,
    JSONResponse,
    FileResponse,
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from lollms_client import (
    LollmsClient, MSG_TYPE, LollmsPersonality
)
from lollms_client import LollmsDiscussion, LollmsMessage
import fitz  # PyMuPDF

from ascii_colors import ASCIIColors, trace_exception
# Local Application Imports
from backend.db import get_db
from backend.db.models.user import User as DBUser, UserStarredDiscussion, UserMessageGrade
from backend.db.models.db_task import DBTask
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.config import TTIBinding as DBTTIBinding
from backend.models import (
    UserAuthDetails, DiscussionInfo, DiscussionTitleUpdate,
    DiscussionRagDatastoreUpdate, MessageOutput, MessageContentUpdate,
    MessageGradeUpdate, DiscussionBranchSwitchRequest, DiscussionSendRequest,
    DiscussionExportRequest, ExportData, DiscussionImportRequest, ContextStatusResponse,
    DiscussionDataZoneUpdate, DataZones, TaskInfo, ManualMessageCreate, MessageUpdateWithImages,
    MessageCodeExportRequest
)
from backend.session import (
    get_current_active_user, get_user_lollms_client,
    get_user_temp_uploads_path, get_user_discussion_assets_path,
    user_sessions, get_safe_store_instance
)
from backend.discussion import get_user_discussion_manager, get_user_discussion
from backend.config import APP_VERSION, SERVER_CONFIG
from backend.task_manager import task_manager, Task
from backend.session import get_current_db_user_from_token
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


# Define the lock at the module level
message_grade_lock = threading.Lock()

discussion_router = APIRouter(prefix="/api/discussions", tags=["Discussions"])

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
        created_at=db_task.created_at, started_at=db_task.started_at, completed_at=db_task.completed_at,
        file_name=db_task.file_name, total_files=db_task.total_files,
        owner_username=db_task.owner.username if db_task.owner else "System"
    )

# --- Task Functions ---
def _generate_image_task(task: Task, username: str, discussion_id: str, prompt: str):
    task.log("Starting image generation task...")
    task.set_progress(5)

    with task.db_session_factory() as db:
        # Get the user to determine their preferred TTI model
        user = db.query(DBUser).filter(DBUser.username == username).first()
        if not user:
            raise Exception(f"User '{username}' not found.")

        user_tti_model_full = user.tti_binding_model_name
        
        selected_binding = None
        selected_model_name = None

        if user_tti_model_full and '/' in user_tti_model_full:
            binding_alias, model_name = user_tti_model_full.split('/', 1)
            selected_binding = db.query(DBTTIBinding).filter(DBTTIBinding.alias == binding_alias, DBTTIBinding.is_active == True).first()
            selected_model_name = model_name
        
        # Fallback to the first active binding if user's preference is not set or invalid
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
        task.set_progress(10)
        
        # Prepare config for LollmsClient, including the selected model and any alias settings
        binding_config = selected_binding.config.copy() if selected_binding.config else {}
        if selected_model_name:
            binding_config['model_name'] = selected_model_name
            
        model_aliases = selected_binding.model_aliases or {}
        alias_info = model_aliases.get(selected_model_name)
        if alias_info:
            task.log(f"Applying settings from model alias '{alias_info.get('title', selected_model_name)}'.")
            # Merge alias parameters into the binding config. This allows aliases to set things like image size, quality, etc.
            for key, value in alias_info.items():
                if key not in ['title', 'description', 'icon'] and value is not None:
                    binding_config[key] = value

    try:
        lc = LollmsClient(
            tti_binding_name=selected_binding.name,
            tti_binding_config=binding_config
        )
        task.log("LollmsClient initialized for TTI.")
        task.set_progress(20)

        # The model name is now in the config, which is what lollms-client TTI bindings expect.
        image_bytes = lc.tti.generate_image(prompt=prompt)
        task.log("Image data received from binding.")
        task.set_progress(80)

        if not image_bytes:
            raise Exception("TTI binding returned empty image data.")

        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        discussion = get_user_discussion(username, discussion_id)
        if not discussion:
            raise Exception("Discussion not found after image generation.")
        
        discussion.add_discussion_image(b64_image)
        discussion.commit()
        task.log("Image added to discussion and saved.")
        task.set_progress(100)
        
        all_images_info = discussion.get_discussion_images()
        
        return {
            "discussion_id": discussion_id,
            "zone": "discussion_images",
            "new_images": [img_info['data'] for img_info in all_images_info],
            "new_active_images": [img_info['active'] for img_info in all_images_info]
        }
    except Exception as e:
        task.log(f"Image generation failed: {e}", "ERROR")
        trace_exception(e)
        raise e


def _import_url_task(task: Task, username: str, discussion_id: str, url: str):
    if ScrapeMaster is None:
        raise ImportError("ScrapeMaster library is not installed and could not be installed automatically.")
    
    task.log("Starting URL import task...")
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

        current_content = discussion.discussion_data_zone or ""

        # Prepare the new document block from the scraped content
        document_block = f"--- Document: {url} ---\n{markdown_content.strip()}\n--- End Document: {url} ---\n"

        # Append the new block to the existing content
        if current_content.strip():
            # If there's existing content, ensure there's a clear separation
            if not current_content.endswith('\n\n'):
                if not current_content.endswith('\n'):
                    current_content += '\n'
                current_content += '\n'
            new_content = current_content + document_block
        else:
            # If the data zone is empty, just add the new block
            new_content = document_block

        discussion.discussion_data_zone = new_content
        discussion.commit()
        task.set_progress(100)
        
        task.log("Content appended to data zone and saved.")
        return {"discussion_id": discussion_id, "new_content": new_content, "zone": "discussion"}
    except Exception as e:
        task.log(f"Failed to import from URL: {e}", "ERROR")
        trace_exception(e)
        raise e

def _process_data_zone_task(task: Task, username: str, discussion_id: str, contextual_prompt: Optional[str]):
    task.log("Starting data zone processing task...")
    discussion = get_user_discussion(username, discussion_id)
    if not discussion:
        raise ValueError("Discussion not found.")
    
    all_images_info = discussion.get_discussion_images()
    
    if (not discussion.discussion_data_zone or not discussion.discussion_data_zone.strip()) and not all_images_info:
        task.log("Data zone is empty (no text or images), nothing to process.", "WARNING")
        return {"discussion_id": discussion_id, "new_content": ""}
    
    def summary_callback(message: str, msg_type: Any, params: Optional[Dict] = None):
        """Callback to update the task in real-time."""
        task.log(message)
        task.set_description(message)
        if params and 'progress' in params:
            task.set_progress(int(params['progress']))

    prompt_to_use = contextual_prompt
    if (not discussion.discussion_data_zone or not discussion.discussion_data_zone.strip()) and not prompt_to_use and all_images_info:
        prompt_to_use = "Describe the attached image(s) in detail."
        task.log(f"No text found. Using default prompt: '{prompt_to_use}'")

    discussion_images_b64 = [img_info['data'] for img_info in all_images_info if img_info.get('active', True)]
    lc = get_user_lollms_client(username)
    summary = lc.long_context_processing(
        discussion.discussion_data_zone,
        images=discussion_images_b64,
        contextual_prompt=prompt_to_use,
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
    task.set_progress(50) # Set progress before starting the heavy loop
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
                
                # REMOVED progress update from here to prevent DB lock
            
            db.commit()

            # Set progress to 100% only after the loop and commit are done
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

class TokenizeRequest(BaseModel):
    text: str

@discussion_router.post("/tokenize", response_model=Dict[str, int])
async def tokenize_text(
    request: TokenizeRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """Tokenizes text using the user's current LLM client."""
    try:
        lc = get_user_lollms_client(current_user.username)
        tokens = lc.tokenize(request.text)
        return {"tokens": len(tokens)}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to tokenize text: {e}")


@discussion_router.get("", response_model=List[DiscussionInfo])
async def list_all_discussions(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[DiscussionInfo]:
    username = current_user.username
    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    dm = get_user_discussion_manager(username)

    discussions_from_db = dm.list_discussions()
    starred_ids = {star.discussion_id for star in db.query(UserStarredDiscussion.discussion_id).filter(UserStarredDiscussion.user_id == db_user.id).all()}

    infos = []
    for disc_data in discussions_from_db:
        disc_id = disc_data['id']
        metadata = disc_data.get('discussion_metadata', {})
        
        image_data = metadata.get("discussion_images", {})
        discussion_images_b64 = []
        active_discussion_images = []

        if isinstance(image_data, dict) and 'data' in image_data:
            discussion_images_b64 = image_data.get('data', [])
            active_discussion_images = image_data.get('active', [])
        elif isinstance(image_data, list):
             # handle legacy format if migration hasn't run for some reason
            for item in image_data:
                if isinstance(item, dict) and 'image' in item:
                    discussion_images_b64.append(item['image'])
                    active_discussion_images.append(item.get('active', True))
                elif isinstance(item, str):
                    discussion_images_b64.append(item)
                    active_discussion_images.append(True)

        infos.append(DiscussionInfo(
            id=disc_id,
            title=metadata.get('title', f"Discussion {disc_id[:8]}"),
            is_starred=(disc_id in starred_ids),
            rag_datastore_ids=metadata.get('rag_datastore_ids'),
            active_tools=metadata.get('active_tools', []),
            active_branch_id=disc_data.get('active_branch_id'),
            created_at=disc_data.get('created_at'),
            last_activity_at=disc_data.get('updated_at'),
            discussion_images=discussion_images_b64,
            active_discussion_images=active_discussion_images
        ))
    return sorted(infos, key=lambda d: d.last_activity_at or datetime.datetime.min, reverse=True)

@discussion_router.post("", response_model=DiscussionInfo, status_code=201)
async def create_new_discussion(current_user: UserAuthDetails = Depends(get_current_active_user)) -> DiscussionInfo:
    username = current_user.username
    discussion_id = str(uuid.uuid4())
    discussion_obj = get_user_discussion(username, discussion_id, create_if_missing=True)
    if not discussion_obj:
        raise HTTPException(status_code=500, detail="Failed to create new discussion.")

    metadata = discussion_obj.metadata or {}
    return DiscussionInfo(
        id=discussion_obj.id,
        title=metadata.get('title', f"New Discussion {discussion_id[:8]}"),
        is_starred=False,
        rag_datastore_ids=None,
        active_tools=[],
        active_branch_id=None,
        created_at=discussion_obj.created_at,
        last_activity_at=discussion_obj.updated_at
    )

@discussion_router.get("/{discussion_id}/export-code", response_class=StreamingResponse)
async def export_discussion_code(
    discussion_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Exports all code blocks from a discussion into a single ZIP file.
    """
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    code_files = []
    code_block_counter = 1
    
    code_block_pattern = re.compile(r"```(\w*)\n([\s\S]*?)\n```")
    filename_pattern = re.compile(
        r"^(?:----?\s*)?(?:\[(?:CREATE|UPDATE)\]\s*)?([a-zA-Z0-9_./\\-]+?\.\w+)(?:\s*----?)?$",
        re.MULTILINE
    )
    lang_ext_map = {
        'python': 'py', 'javascript': 'js', 'typescript': 'ts', 'html': 'html',
        'css': 'css', 'json': 'json', 'xml': 'xml', 'sql': 'sql', 'bash': 'sh',
        'shell': 'sh', 'text': 'txt', 'markdown': 'md', 'java': 'java',
        'c++': 'cpp', 'cpp': 'cpp', 'c': 'c', 'csharp': 'cs', 'go': 'go',
        'rust': 'rs', 'php': 'php', 'ruby': 'rb', 'swift': 'swift',
        'kotlin': 'kt', 'yaml': 'yaml', 'yml': 'yaml'
    }

    all_messages_orm = discussion_obj.db_manager.get_all_messages(discussion_id)
    if not all_messages_orm:
        raise HTTPException(status_code=404, detail="No messages in discussion to export from.")

    for msg in all_messages_orm:
        if not msg.content or '```' not in msg.content:
            continue
        
        parts = code_block_pattern.split(msg.content)
        if len(parts) < 3:
            continue

        preceding_texts = parts[0::3]
        languages = parts[1::3]
        codes = parts[2::3]

        for i in range(len(codes)):
            preceding_text = preceding_texts[i]
            lang = languages[i].lower()
            code_content = codes[i]
            filename = ""

            lines_before = preceding_text.strip().split('\n')
            if lines_before:
                for line in reversed(lines_before[-5:]):
                    match = filename_pattern.match(line.strip())
                    if match:
                        filename = match.group(1)
                        break
            
            if filename:
                if ".." in filename or Path(filename).is_absolute():
                    filename = ""
                else:
                    filename = filename.replace("\\", "/")

            if not filename:
                ext = lang_ext_map.get(lang, 'txt')
                filename = f"script_{code_block_counter}.{ext}"
                code_block_counter += 1
            
            code_files.append((filename, code_content))

    if not code_files:
        raise HTTPException(status_code=404, detail="No valid code blocks found to export.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filepath, content in code_files:
            zf.writestr(filepath, content)
    
    zip_buffer.seek(0)
    
    safe_title = re.sub(r'[^a-zA-Z0-9_-]', '', discussion_obj.metadata.get('title', 'discussion').replace(' ', '_'))
    zip_filename = f"code_export_{safe_title}_{discussion_id[:8]}.zip"
    
    headers = {'Content-Disposition': f'attachment; filename="{zip_filename}"'}
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)

@discussion_router.post("/export-message-code", response_class=StreamingResponse)
async def export_message_code(
    payload: MessageCodeExportRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Exports all code blocks from a single message content string into a ZIP file.
    """
    code_files = []
    code_block_counter = 1
    
    code_block_pattern = re.compile(r"```(\w*)\n([\s\S]*?)\n```")
    filename_pattern = re.compile(
        r"^(?:----?\s*)?(?:\[(?:CREATE|UPDATE)\]\s*)?([a-zA-Z0-9_./\\-]+?\.\w+)(?:\s*----?)?$",
        re.MULTILINE
    )
    lang_ext_map = {
        'python': 'py', 'javascript': 'js', 'typescript': 'ts', 'html': 'html',
        'css': 'css', 'json': 'json', 'xml': 'xml', 'sql': 'sql', 'bash': 'sh',
        'shell': 'sh', 'text': 'txt', 'markdown': 'md', 'java': 'java',
        'c++': 'cpp', 'cpp': 'cpp', 'c': 'c', 'csharp': 'cs', 'go': 'go',
        'rust': 'rs', 'php': 'php', 'ruby': 'rb', 'swift': 'swift',
        'kotlin': 'kt', 'yaml': 'yaml', 'yml': 'yaml'
    }

    content = payload.content
    if not content or '```' not in content:
        raise HTTPException(status_code=404, detail="No code blocks found in the provided content.")

    parts = code_block_pattern.split(content)
    if len(parts) < 3:
        raise HTTPException(status_code=404, detail="No valid code blocks found in the provided content.")

    preceding_texts = parts[0::3]
    languages = parts[1::3]
    codes = parts[2::3]

    for i in range(len(codes)):
        preceding_text = preceding_texts[i]
        lang = languages[i].lower()
        code_content = codes[i]
        filename = ""

        lines_before = preceding_text.strip().split('\n')
        if lines_before:
            for line in reversed(lines_before[-5:]): # Check last 5 lines before code block for filename
                match = filename_pattern.match(line.strip())
                if match:
                    filename = match.group(1)
                    break
        
        if filename:
            # Sanitize filename
            if ".." in filename or Path(filename).is_absolute():
                filename = "" # Discard unsafe path
            else:
                filename = filename.replace("\\", "/")

        if not filename:
            ext = lang_ext_map.get(lang, 'txt')
            filename = f"script_{code_block_counter}.{ext}"
            code_block_counter += 1
        
        code_files.append((filename, code_content))

    if not code_files:
        raise HTTPException(status_code=404, detail="No valid code blocks found to export.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filepath, content in code_files:
            zf.writestr(filepath, content)
    
    zip_buffer.seek(0)
    
    safe_title = re.sub(r'[^a-zA-Z0-9_-]', '', payload.discussion_title.replace(' ', '_'))
    zip_filename = f"code_export_{safe_title}.zip"
    
    headers = {'Content-Disposition': f'attachment; filename="{zip_filename}"'}
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)

@discussion_router.get("/{discussion_id}/data_zones", response_model=DataZones)
def get_all_data_zones(
    discussion_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    discussion = get_user_discussion(current_user.username, discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    discussion.memory = db_user.memory
    
    return DataZones(
        user_data_zone=db_user.data_zone if db_user else "",
        discussion_data_zone=discussion.discussion_data_zone,
        personality_data_zone=discussion.personality_data_zone,
        memory=discussion.memory,
        discussion_images=discussion.images or [],
        active_discussion_images=discussion.active_images or []
    )


@discussion_router.get("/{discussion_id}/data_zone", response_model=Dict[str, str])
def get_discussion_data_zone(
    discussion_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    discussion = get_user_discussion(current_user.username, discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    return {"content": discussion.discussion_data_zone or ""}

@discussion_router.put("/{discussion_id}/data_zone", status_code=200)
def update_discussion_data_zone(
    discussion_id: str,
    payload: DiscussionDataZoneUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    discussion = get_user_discussion(current_user.username, discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    try:
        discussion.discussion_data_zone = payload.content
        discussion.commit()
        return {"message": "Data Zone updated successfully."}
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to update Data Zone: {e}")

@discussion_router.post("/{discussion_id}/generate_image", response_model=TaskInfo, status_code=202)
def generate_image_from_data_zone(
    discussion_id: str,
    prompt: str = Form(...),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    discussion = get_user_discussion(current_user.username, discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")

    db_task = task_manager.submit_task(
        name=f"Generating image for: {discussion.metadata.get('title', 'Untitled')}",
        target=_generate_image_task,
        args=(current_user.username, discussion_id, prompt),
        description=f"Generating image with prompt: '{prompt[:50]}...'",
        owner_username=current_user.username
    )
    return _to_task_info(db_task)


@discussion_router.post("/{discussion_id}/import_url", response_model=TaskInfo, status_code=202)
def import_from_url(
    discussion_id: str,
    request: UrlImportRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    discussion = get_user_discussion(current_user.username, discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")

    db_task = task_manager.submit_task(
        name=f"Importing URL for: {discussion.metadata.get('title', 'Untitled')}",
        target=_import_url_task,
        args=(current_user.username, discussion_id, request.url),
        description=f"Scraping content from: {request.url}",
        owner_username=current_user.username
    )
    return _to_task_info(db_task)

@discussion_router.post("/{discussion_id}/process_data_zone", response_model=TaskInfo, status_code=202)
def summarize_discussion_data_zone(
    discussion_id: str,
    prompt: Optional[str] = Form(None),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    discussion = get_user_discussion(current_user.username, discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    db_task = task_manager.submit_task(
        name=f"Processing Data Zone for: {discussion.metadata.get('title', 'Untitled')}",
        target=_process_data_zone_task,
        args=(current_user.username, discussion_id, prompt),
        description=f"AI is processing the discussion data zone content.",
        owner_username=current_user.username
    )
    return _to_task_info(db_task)


@discussion_router.post("/{discussion_id}/memorize", response_model=TaskInfo, status_code=202)
def memorize_ltm(
    discussion_id: str,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)    
):
    
    discussion = get_user_discussion(current_user.username, discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")

    db_task = task_manager.submit_task(
        name=f"Memorize LTM for: {discussion.metadata.get('title', 'Untitled')}",
        target=_memorize_ltm_task,
        args=(current_user.username, discussion_id, db),
        description="AI is analyzing the conversation to extract key facts for long-term memory.",
        owner_username=current_user.username
    )
    return _to_task_info(db_task)


@discussion_router.post("/{discussion_id}/images", response_model=Dict[str, List[Any]])
async def add_discussion_image(
    discussion_id: str,
    file: UploadFile = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    discussion = get_user_discussion(current_user.username, discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")

    try:
        content_type = file.content_type
        images_b64 = []

        if content_type.startswith("image/"):
            image_bytes = await file.read()
            images_b64.append(base64.b64encode(image_bytes).decode('utf-8'))
        elif content_type == "application/pdf":
            pdf_bytes = await file.read()
            pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page_num in range(len(pdf_doc)):
                page = pdf_doc.load_page(page_num)
                pix = page.get_pixmap(dpi=150)  # Render at 150 DPI
                img_bytes = pix.tobytes("png")
                images_b64.append(base64.b64encode(img_bytes).decode('utf-8'))
            pdf_doc.close()
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Please upload an image or a PDF.")

        for b64_data in images_b64:
            discussion.add_discussion_image(b64_data)
        
        discussion.commit()
        
        all_images_info = discussion.get_discussion_images()
        discussion_images_b64 = [img_info['data'] for img_info in all_images_info]
        active_discussion_images = [img_info['active'] for img_info in all_images_info]
        
        return {
            "discussion_images": discussion_images_b64,
            "active_discussion_images": active_discussion_images
        }
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to add file to discussion: {str(e)}")
    finally:
        await file.close()


@discussion_router.put("/{discussion_id}/images/{image_index}/toggle", response_model=Dict[str, List[Any]])
async def toggle_discussion_image(
    discussion_id: str,
    image_index: int,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    discussion = get_user_discussion(current_user.username, discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    try:
        discussion.toggle_discussion_image_activation(image_index)
        discussion.commit()

        all_images_info = discussion.get_discussion_images()
        discussion_images_b64 = [img_info['data'] for img_info in all_images_info]
        active_discussion_images = [img_info['active'] for img_info in all_images_info]
        
        return {
            "discussion_images": discussion_images_b64,
            "active_discussion_images": active_discussion_images
        }
    except IndexError:
        raise HTTPException(status_code=404, detail="Image index out of bounds.")
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to toggle image activation: {str(e)}")

@discussion_router.delete("/{discussion_id}/images/{image_index}", response_model=Dict[str, List[Any]])
async def delete_discussion_image_from_discussion(
    discussion_id: str,
    image_index: int,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    discussion = get_user_discussion(current_user.username, discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    try:
        discussion.remove_discussion_image(image_index)
        discussion.commit()

        all_images_info = discussion.get_discussion_images()
        discussion_images_b64 = [img_info['data'] for img_info in all_images_info]
        active_discussion_images = [img_info['active'] for img_info in all_images_info]
        
        return {
            "discussion_images": discussion_images_b64,
            "active_discussion_images": active_discussion_images
        }
    except IndexError:
        raise HTTPException(status_code=404, detail="Image index out of bounds.")
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to delete image from discussion: {str(e)}")

@discussion_router.post("/prune", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def prune_empty_discussions(current_user: UserAuthDetails = Depends(get_current_active_user)):
    """
    Triggers a background task to delete all discussions for the current user 
    that are empty or contain only one message.
    """
    db_task = task_manager.submit_task(
        name=f"Prune empty discussions for {current_user.username}",
        target=_prune_empty_discussions_task,
        args=(current_user.username,),
        description="Scans and deletes discussions with 0 or 1 message.",
        owner_username=current_user.username
    )
    return _to_task_info(db_task)


@discussion_router.post("/{discussion_id}/auto-title", response_model=DiscussionInfo)
async def generate_discussion_auto_title(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    Generates and sets a new title for a discussion automatically based on its content.
    """
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    try:
        new_title = discussion_obj.auto_title()
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to generate title: {e}")

    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    is_starred = db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).first() is not None
    metadata = discussion_obj.metadata or {}
    
    return DiscussionInfo(
        id=discussion_id,
        title=new_title,
        is_starred=is_starred,
        rag_datastore_ids=metadata.get('rag_datastore_ids'),
        active_tools=metadata.get('active_tools', []),
        active_branch_id=discussion_obj.active_branch_id,
        created_at=discussion_obj.created_at,
        last_activity_at=discussion_obj.updated_at
    )

@discussion_router.get("/{discussion_id}", response_model=List[MessageOutput])
async def get_messages_for_discussion(discussion_id: str, branch_id: Optional[str] = Query(None), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[MessageOutput]:
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    branch_tip_to_load = branch_id or discussion_obj.active_branch_id
    messages_in_branch = discussion_obj.get_branch(branch_tip_to_load)

    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    user_grades = {g.message_id: g.grade for g in db.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id).all()}

    # Fetch all messages in the discussion to build the children map
    all_messages_in_discussion = discussion_obj.get_all_messages_flat()
    children_map = {}
    for msg_obj in all_messages_in_discussion:
        if msg_obj.parent_id:
            if msg_obj.parent_id not in children_map:
                children_map[msg_obj.parent_id] = []
            children_map[msg_obj.parent_id].append(msg_obj.id)


    messages_output = []
    for msg in messages_in_branch:
        # --- START FIX ---
        # Robustly handle message image data which could be a JSON string, a list of strings (legacy),
        # or a list of dictionaries (current).
        images_list_raw = msg.images or []
        images_list = []
        if isinstance(images_list_raw, str):
            try: images_list = json.loads(images_list_raw)
            except json.JSONDecodeError: images_list = []
        elif isinstance(images_list_raw, list):
            images_list = images_list_raw
        
        full_image_refs = []
        active_images_bools = []
        for img_data in images_list:
            if isinstance(img_data, dict) and 'image' in img_data:
                full_image_refs.append(f"data:image/png;base64,{img_data['image']}")
                active_images_bools.append(img_data.get('active', True))
            elif isinstance(img_data, str):
                full_image_refs.append(f"data:image/png;base64,{img_data}")
                active_images_bools.append(True) # Legacy format is always active

        msg_metadata_raw = msg.metadata
        if isinstance(msg_metadata_raw, str):
            try: msg_metadata = json.loads(msg_metadata_raw) if msg_metadata_raw else {}
            except json.JSONDecodeError: msg_metadata = {}
        else:
            msg_metadata = msg_metadata_raw or {}

        # Populate the branches field if this message has multiple children
        # This typically applies to user messages with multiple AI responses
        msg_branches = None
        if msg.id in children_map and len(children_map[msg.id]) > 1:
            msg_branches = children_map[msg.id]

        messages_output.append(
            MessageOutput(
                id=msg.id, sender=msg.sender, sender_type=msg.sender_type, content=msg.content,
                parent_message_id=msg.parent_id, binding_name=msg.binding_name, model_name=msg.model_name,
                token_count=msg.tokens, sources=msg_metadata.get('sources'), events=msg_metadata.get('events'),
                image_references=full_image_refs,
                active_images=active_images_bools,
                user_grade=user_grades.get(msg.id, 0),
                created_at=msg.created_at, branch_id=branch_tip_to_load, branches=msg_branches
            )
        )
    return messages_output

@discussion_router.get("/{discussion_id}/full_tree", response_model=List[MessageOutput])
async def get_full_discussion_tree(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user)) -> List[MessageOutput]:
    """
    Retrieves all messages for a given discussion, including their parent/child relationships,
    to enable building a complete discussion tree in the frontend.
    """
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    all_messages_in_discussion = discussion_obj.get_all_messages_flat()
    
    # Build a map of parent_id -> [child_ids]
    children_map: Dict[Optional[str], List[str]] = {}
    for msg_obj in all_messages_in_discussion:
        parent_id = msg_obj.parent_id
        if parent_id not in children_map:
            children_map[parent_id] = []
        children_map[parent_id].append(msg_obj.id)

    # Convert LollmsMessage objects to MessageOutput Pydantic models
    # and populate the 'branches' field if it's a branching point.
    messages_output = []
    # Fetch user grades once for the entire discussion
    db_session_for_grades = next(get_db())
    try:
        db_user = db_session_for_grades.query(DBUser).filter(DBUser.username == username).one()
        user_grades = {g.message_id: g.grade for g in db_session_for_grades.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id).all()}
    finally:
        db_session_for_grades.close()


    for msg_obj in all_messages_in_discussion:
        msg_branches = None
        if msg_obj.id in children_map and len(children_map[msg_obj.id]) > 1:
            msg_branches = children_map[msg_obj.id]
            
        images_list_raw = msg_obj.images or []
        images_list = []
        if isinstance(images_list_raw, str):
            try: images_list = json.loads(images_list_raw)
            except json.JSONDecodeError: images_list = []
        elif isinstance(images_list_raw, list):
            images_list = images_list_raw
        
        full_image_refs = []
        active_images_bools = []
        for img_data in images_list:
            if isinstance(img_data, dict) and 'image' in img_data:
                full_image_refs.append(f"data:image/png;base64,{img_data['image']}")
                active_images_bools.append(img_data.get('active', True))
            elif isinstance(img_data, str):
                full_image_refs.append(f"data:image/png;base64,{img_data}")
                active_images_bools.append(True) # Legacy format is always active
                
        msg_metadata_raw = msg_obj.metadata
        if isinstance(msg_metadata_raw, str):
            try: msg_metadata = json.loads(msg_metadata_raw) if msg_metadata_raw else {}
            except json.JSONDecodeError: msg_metadata = {}
        else:
            msg_metadata = msg_metadata_raw or {}


        messages_output.append(
            MessageOutput(
                id=msg_obj.id,
                sender=msg_obj.sender,
                sender_type=msg_obj.sender_type,
                content=msg_obj.content,
                parent_message_id=msg_obj.parent_id,
                binding_name=msg_obj.binding_name,
                model_name=msg_obj.model_name,
                token_count=msg_obj.tokens,
                sources=msg_metadata.get('sources'),
                events=msg_metadata.get('events'),
                image_references=full_image_refs,
                active_images=active_images_bools,
                user_grade=user_grades.get(msg_obj.id, 0),
                created_at=msg_obj.created_at,
                branch_id=discussion_obj.active_branch_id, # This is the currently active branch for the discussion
                branches=msg_branches, # Branches *originating from this message*
                vision_support=True # Default true, logic for model-specific vision support is handled by LollmsClient
            )
        )
    return messages_output

@discussion_router.get("/{discussion_id}/context_status", response_model=ContextStatusResponse)
def get_discussion_context_status(
    discussion_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    discussion = get_user_discussion(current_user.username, discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    try:
        status = discussion.get_context_status()
        return status
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to get context status: {e}")
@discussion_router.put("/{discussion_id}/active_branch", response_model=DiscussionInfo)
async def update_discussion_active_branch(discussion_id: str, branch_request: DiscussionBranchSwitchRequest, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DiscussionInfo:
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    try:
        discussion_obj.switch_to_branch(branch_request.active_branch_id)
        discussion_obj.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    is_starred = db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).first() is not None
    metadata = discussion_obj.metadata or {}
    return DiscussionInfo(
        id=discussion_id,
        title=metadata.get('title', "Untitled"),
        is_starred=is_starred,
        rag_datastore_ids=metadata.get('rag_datastore_ids'),
        active_tools=metadata.get('active_tools', []),
        active_branch_id=discussion_obj.active_branch_id,
        created_at=discussion_obj.created_at,
        last_activity_at=discussion_obj.updated_at
    )

@discussion_router.put("/{discussion_id}/title", response_model=DiscussionInfo)
async def update_discussion_title(discussion_id: str, title_update: DiscussionTitleUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    discussion_obj.set_metadata_item('title',title_update.title)

    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    is_starred = db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).first() is not None
    return DiscussionInfo(
        id=discussion_id,
        title=title_update.title,
        is_starred=is_starred,
        rag_datastore_ids=discussion_obj.metadata.get('rag_datastore_ids'),
        active_tools=discussion_obj.metadata.get('active_tools', []),
        active_branch_id=discussion_obj.active_branch_id,
        created_at=discussion_obj.created_at,
        last_activity_at=discussion_obj.updated_at
    )

@discussion_router.delete("/{discussion_id}", status_code=200)
async def delete_specific_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()):
    username = current_user.username
    dm = get_user_discussion_manager(username)
    dm.delete_discussion(discussion_id)

    assets_path = get_user_discussion_assets_path(username) / discussion_id
    if assets_path.exists() and assets_path.is_dir():
        background_tasks.add_task(shutil.rmtree, assets_path, ignore_errors=True)

    try:
        db_user = db.query(DBUser).filter(DBUser.username == username).one()
        db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).delete(synchronize_session=False)
        db.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id).delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"ERROR: Failed to delete main DB entries for discussion {discussion_id}: {e}")

    return {"message": f"Discussion '{discussion_id}' deleted successfully."}

@discussion_router.post("/{discussion_id}/star", status_code=201, response_model=DiscussionInfo)
async def star_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DiscussionInfo:
    username = current_user.username
    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    if not db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).first():
        db.add(UserStarredDiscussion(user_id=db_user.id, discussion_id=discussion_id))
        db.commit()

    metadata = discussion_obj.metadata or {}
    return DiscussionInfo(
        id=discussion_id,
        title=metadata.get('title', "Untitled"),
        is_starred=True,
        rag_datastore_ids=metadata.get('rag_datastore_ids'),
        active_tools=metadata.get('active_tools', []),
        active_branch_id=discussion_obj.active_branch_id,
        created_at=discussion_obj.created_at,
        last_activity_at=discussion_obj.updated_at
    )

@discussion_router.delete("/{discussion_id}/star", status_code=200, response_model=DiscussionInfo)
async def unstar_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DiscussionInfo:
    username = current_user.username
    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    star = db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).first()
    if star:
        db.delete(star)
        db.commit()

    metadata = discussion_obj.metadata or {}
    return DiscussionInfo(
        id=discussion_id,
        title=metadata.get('title', "Untitled"),
        is_starred=False,
        rag_datastore_ids=metadata.get('rag_datastore_ids'),
        active_tools=metadata.get('active_tools', []),
        active_branch_id=discussion_obj.active_branch_id,
        created_at=discussion_obj.created_at,
        last_activity_at=discussion_obj.updated_at
    )

@discussion_router.put("/{discussion_id}/rag_datastore", response_model=DiscussionInfo)
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

@discussion_router.post("/{discussion_id}/chat")
async def chat_in_existing_discussion(
    discussion_id: str,
    prompt: str = Form(...),
    image_server_paths_json: str = Form("[]"),
    is_resend: bool = Form(False),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> StreamingResponse:
    username = current_user.username
    user_model_full = current_user.lollms_model_name
    binding_alias = None
    if user_model_full and '/' in user_model_full:
        binding_alias, _ = user_model_full.split('/', 1)
    
    lc = get_user_lollms_client(current_user.username, binding_alias)
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    
    # The LollmsClient is now correctly attached to the discussion object
    if not lc:
        async def error_stream():
            yield json.dumps({"type": "error", "content": "Failed to get a valid LLM Client from the discussion object."}) + "\n"
        return StreamingResponse(error_stream(), media_type="application/x-ndjson")


    def query_rag_callback(query: str, ss, rag_top_k, rag_min_similarity_percent) -> List[Dict]:
        if not ss: return []
        try:
            retrieved_chunks = ss.query(query, vectorizer_name=db_user.safe_store_vectorizer, top_k=rag_top_k, min_similarity_percent=rag_min_similarity_percent)
            revamped_chunks=[]
            for entry in retrieved_chunks:
                revamped_entry = {}
                if "file_path" in entry:
                    revamped_entry["document"]=Path(entry["file_path"]).name
                if "chunk_text" in entry:
                    revamped_entry["content"]=entry["chunk_text"]
                if "similarity" in entry:
                    revamped_entry["similarity_percent"] = entry["similarity"] * 100
                revamped_chunks.append(revamped_entry)
            return revamped_chunks
        except Exception as e:
            trace_exception(e)
            return [{"error": f"Error during RAG query on datastore {ss.name}: {e}"}]

    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    discussion_obj.memory = db_user.memory
    rag_datastore_ids = (discussion_obj.metadata or {}).get('rag_datastore_ids', [])
    
    use_rag = {}
    for ds_id in rag_datastore_ids:
        ss = get_safe_store_instance(username, ds_id, db)
        if ss:
            use_rag[ss.name] = {"name": ss.name, "description": ss.description, "callable": partial(query_rag_callback, ss=ss)}

    db_pers = db.query(DBPersonality).filter(DBPersonality.id == db_user.active_personality_id).first() if db_user.active_personality_id else None
    
    # --- REFINED: Placeholder replacement and data zone combination ---
    user_data_zone = db_user.data_zone or ""
    now = datetime.datetime.now()
    replacements = {
        "{{date}}": now.strftime("%Y-%m-%d"),
        "{{time}}": now.strftime("%H:%M:%S"),
        "{{datetime}}": now.strftime("%Y-%m-%d %H:%M:%S"),
        "{{user_name}}": current_user.username,
    }
    # Apply replacements to a copy
    processed_user_data_zone = user_data_zone
    for placeholder, value in replacements.items():
        processed_user_data_zone = processed_user_data_zone.replace(placeholder, value)
        
    discussion_obj.user_data_zone = processed_user_data_zone

    # Combine MCPs from discussion metadata and personality
    use_mcps_from_discussion = (discussion_obj.metadata or {}).get('active_tools', [])
    use_mcps_from_personality = db_pers.active_mcps if db_pers and db_pers.active_mcps else []
    combined_mcps = list(set(use_mcps_from_discussion + use_mcps_from_personality))

    # --- Build LollmsPersonality with data_source ---
    data_source_runtime = None
    if db_pers:
        if db_pers.data_source_type == "raw_text":
            data_source_runtime = db_pers.data_source
        elif db_pers.data_source_type == "datastore" and db_pers.data_source:
            # Create a callable for the dynamic data source
            def query_personality_datastore(query: str) -> str:
                ds_id = db_pers.data_source
                ds = get_safe_store_instance(username, ds_id, db)
                if not ds: return f"Error: Personality datastore '{ds_id}' not found or inaccessible."
                try:
                    results = ds.query(query, vectorizer_name=db_user.safe_store_vectorizer, top_k=db_user.rag_top_k)
                    return "\n".join([chunk.get("chunk_text", "") for chunk in results])
                except Exception as e:
                    return f"Error querying personality datastore: {e}"
            data_source_runtime = query_personality_datastore

    active_personality = LollmsPersonality(
        name=db_pers.name if db_pers else "Generic Assistant",
        author=db_pers.author if db_pers else "System",
        category=db_pers.category if db_pers else "Default",
        description=db_pers.description if db_pers else "A generic, helpful assistant.",
        system_prompt=db_pers.prompt_text if db_pers else "You are a helpful AI assistant.",
        script=db_pers.script_code if db_pers else None,
        active_mcps=db_pers.active_mcps or [] if db_pers else [],
        data_source=data_source_runtime
    )
    

    main_loop = asyncio.get_event_loop()
    stream_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
    stop_event = threading.Event()
    user_sessions.setdefault(username, {}).setdefault("active_generation_control", {})[discussion_id] = stop_event

    async def stream_generator() -> AsyncGenerator[str, None]:
        all_events = []
        def llm_callback(chunk: str, msg_type: MSG_TYPE, params: Optional[Dict] = None, **kwargs) -> bool:
            if stop_event.is_set(): return False
            if not params: params = {}
            
            payload_map = {
                MSG_TYPE.MSG_TYPE_CHUNK: {"type": "chunk", "content": chunk},
                MSG_TYPE.MSG_TYPE_STEP_START: {"type": "step_start", "content": chunk, "id": params.get("id")},
                MSG_TYPE.MSG_TYPE_STEP_END: {"type": "step_end", "content": chunk, "id": params.get("id"), "status": "done"},
                MSG_TYPE.MSG_TYPE_INFO: {"type": "info", "content": chunk},
                MSG_TYPE.MSG_TYPE_OBSERVATION: {"type": "observation", "content": chunk},
                MSG_TYPE.MSG_TYPE_THOUGHT_CONTENT: {"type": "thought", "content": chunk},
                MSG_TYPE.MSG_TYPE_REASONING: {"type": "reasoning", "content": chunk},
                MSG_TYPE.MSG_TYPE_TOOL_CALL: {"type": "tool_call", "content": chunk},
                MSG_TYPE.MSG_TYPE_SCRATCHPAD: {"type": "scratchpad", "content": chunk},
                MSG_TYPE.MSG_TYPE_EXCEPTION: {"type": "exception", "content": chunk},
                MSG_TYPE.MSG_TYPE_ERROR: {"type": "error", "content": chunk}
            }
            
            payload = payload_map.get(msg_type)
            if payload:
                if payload['type']!="chunk":
                    all_events.append(payload)
                json_compatible_payload = jsonable_encoder(payload)
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(json_compatible_payload) + "\n")
            return True

        def blocking_call():
            try:
                images_for_message = []
                image_server_paths = json.loads(image_server_paths_json)
                if image_server_paths and not is_resend:
                    temp_path = get_user_temp_uploads_path(username)
                    assets_path = get_user_discussion_assets_path(username) / discussion_id
                    assets_path.mkdir(parents=True, exist_ok=True)
                    for temp_rel_path in image_server_paths:
                        filename = Path(temp_rel_path).name
                        if (temp_path / filename).exists():
                            persistent_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
                            shutil.move(str(temp_path / filename), str(assets_path / persistent_filename))
                            b64_data = base64.b64encode((assets_path / persistent_filename).read_bytes()).decode('utf-8')
                            images_for_message.append(b64_data)

                if is_resend:
                    result = discussion_obj.regenerate_branch(personality=active_personality, use_mcps=combined_mcps, use_data_store=use_rag, streaming_callback=llm_callback)
                else:
                    result = discussion_obj.chat(
                        user_message=prompt, personality=active_personality, use_mcps=combined_mcps,
                        use_data_store=use_rag, images=images_for_message,
                        streaming_callback=llm_callback, max_reasoning_steps=db_user.rag_n_hops,
                        rag_top_k=db_user.rag_top_k, rag_min_similarity_percent=db_user.rag_min_sim_percent,
                        debug=SERVER_CONFIG.get("debug", False)
                    )
                
                ai_message_obj = result.get('ai_message')
                if ai_message_obj:
                    ai_message_obj.set_metadata_item('events', all_events, discussion_obj)

                def lollms_message_to_output(msg):
                    if not msg: return None
                    
                    full_image_refs = []
                    if hasattr(msg, 'images') and msg.images:
                        full_image_refs = [ f"data:image/png;base64,{img}" for img in msg.images or []]

                    return {
                        "id": msg.id, "sender": msg.sender, "content": msg.content,
                        "created_at": msg.created_at, "parent_message_id": msg.parent_id,
                        "discussion_id": msg.discussion_id, "metadata": msg.metadata,
                        "tokens": msg.tokens, "sender_type": msg.sender_type,
                        "binding_name": msg.binding_name, "model_name": msg.model_name,
                        "image_references": full_image_refs
                    }
                
                final_messages_payload = {
                    'user_message': lollms_message_to_output(result.get('user_message')),
                    'ai_message': lollms_message_to_output(result.get('ai_message'))
                }
                
                new_title = None
                if current_user.auto_title and (discussion_obj.metadata is None or discussion_obj.metadata.get('title',"").startswith("New Discussion")):
                    event_title_building = jsonable_encoder({"type": "new_title_start"})
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(event_title_building) + "\n")
                    new_title = discussion_obj.auto_title()
                    event_title_building = jsonable_encoder({"type": "new_title_end", "new_title": new_title})
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(event_title_building) + "\n")
                
                finalize_payload = {"type": "finalize", "data": final_messages_payload}
                if new_title:
                    finalize_payload["new_title"] = new_title
                json_compatible_event = jsonable_encoder(finalize_payload)
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(json_compatible_event) + "\n")
            except Exception as e:
                trace_exception(e)
                err_msg = f"LLM generation failed: {e}"
                if main_loop.is_running():
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_msg}) + "\n")
            finally:
                if username in user_sessions and "active_generation_control" in user_sessions[username]:
                    user_sessions[username]["active_generation_control"].pop(discussion_id, None)
                if main_loop.is_running():
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)
        
        threading.Thread(target=blocking_call, daemon=True).start()        
        while True:
            item = await stream_queue.get()
            if item is None: break
            yield item

    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")

@discussion_router.post("/{discussion_id}/stop_generation", status_code=200)
async def stop_discussion_generation(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user)):
    username = current_user.username
    stop_event = user_sessions.get(username, {}).get("active_generation_control", {}).get(discussion_id)
    if stop_event and isinstance(stop_event, threading.Event):
        stop_event.set()
        return {"message": "Stop signal sent."}
    else:
        raise HTTPException(status_code=404, detail="No active generation found for this discussion.")

@discussion_router.put("/{discussion_id}/messages/{message_id}/grade", response_model=MessageOutput)
async def grade_discussion_message(discussion_id: str, message_id: str, grade_update: MessageGradeUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    username = current_user.username
    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    discussion_obj = get_user_discussion(username, discussion_id)
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

@discussion_router.put("/{discussion_id}/messages/{message_id}", response_model=MessageOutput)
async def update_discussion_message(
    discussion_id: str,
    message_id: str,
    payload: MessageUpdateWithImages,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
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
            final_images_b64.append(b64_data_uri) # Assume raw base64
    
    target_message.images = final_images_b64
    discussion_obj.commit()

    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    grade = db.query(UserMessageGrade.grade).filter_by(user_id=db_user.id, discussion_id=discussion_id, message_id=message_id).scalar() or 0
    
    full_image_refs = [f"data:image/png;base64,{img}" for img in target_message.images or []]
    active_images = [True] * len(full_image_refs) # Edited images are always active

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

@discussion_router.post("/{discussion_id}/messages", response_model=MessageOutput)
async def add_manual_message(
    discussion_id: str,
    payload: ManualMessageCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
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

    # Build the response
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

@discussion_router.delete("/{discussion_id}/messages/{message_id}", status_code=200)
async def delete_discussion_message(discussion_id: str, message_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail="Discussion not found.")
    try: discussion_obj.delete_branch(message_id)
    except ValueError as e: raise HTTPException(status_code=404, detail=str(e))
    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    db.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id, message_id=message_id).delete(synchronize_session=False)
    db.commit()
    return {"message": "Message and its branch deleted successfully."}
@discussion_router.get("/{discussion_id}/export_context", response_class=PlainTextResponse)
async def export_discussion_context(
    discussion_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Exports the full discussion context as a single string, exactly as it would be presented to the LLM.
    """
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
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to export discussion context: {e}")