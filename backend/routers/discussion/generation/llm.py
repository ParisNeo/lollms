# Standard Library Imports
import base64
import io
import json
import re
import shutil
import uuid
import types
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union
import traceback
import threading
import asyncio
import zipfile
import platform
import time
import requests
from concurrent.futures import ThreadPoolExecutor

# Third-Party Imports
import fitz  # PyMuPDF
from PIL import Image # Needed for image resizing
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
from sqlalchemy.sql import func
from ascii_colors import ASCIIColors, trace_exception

# Local Application Imports
from backend.config import APP_VERSION, SERVER_CONFIG
from backend.db import get_db
from backend.db.models.config import TTIBinding as DBTTIBinding
from backend.db.models.db_task import DBTask, ScheduledTask
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.discussion import SharedDiscussionLink as DBSharedDiscussionLink
from backend.db.models.user import (User as DBUser, UserMessageGrade,
                                     UserStarredDiscussion)
from backend.db.models.memory import UserMemory
from backend.db.models.config import LLMBinding as DBLLMBinding
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
                             get_user_temp_uploads_path, user_sessions,
                             build_lollms_client_from_params)
from backend.task_manager import task_manager, Task
from backend.ws_manager import manager
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request
from backend.tasks.image_generation_tasks import _generate_slides_task
from concurrent.futures import ThreadPoolExecutor, as_completed
# Google Search Tools
try:
    from googleapiclient.discovery import build as google_build
except ImportError:
    google_build = None

from scrapemaster import ScrapeMaster

# Create a thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=50)


import pipmaster as pm


def _sanitize_b64(data: str) -> str:
    """Removes data URI scheme if present to return raw base64."""
    if "base64," in data:
        return data.split("base64,")[1]
    return data

def resize_base64_image(b64_str: str, max_width: int = -1, max_height: int = -1) -> str:
    """
    Resizes and compresses a base64 encoded image.
    1. Resizes if dimensions exceed max_width/max_height.
    2. Converts to JPEG (quality 85) to reduce payload size, unless transparency is present.
    Returns the raw base64 string (no header).
    """
    try:
        # Strip header if present
        data = b64_str
        if "base64," in b64_str:
            _, data = b64_str.split("base64,", 1)

        img_data = base64.b64decode(data)
        img = Image.open(io.BytesIO(img_data))
        
        original_width, original_height = img.size
        new_width, new_height = original_width, original_height
        should_resize = False

        # Calculate new dimensions
        if max_width > 0 and new_width > max_width:
            ratio = max_width / new_width
            new_width = max_width
            new_height = int(new_height * ratio)
            should_resize = True

        if max_height > 0 and new_height > max_height:
            ratio = max_height / new_height
            new_height = max_height
            new_width = int(new_width * ratio)
            should_resize = True
        
        # Determine format and mode
        # If image has transparency (RGBA, LA) or is P with transparency, keep as PNG or convert to RGB for JPEG
        has_transparency = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        
        if should_resize:
             img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        buffered = io.BytesIO()
        
        # Always prefer JPEG for non-transparent images to save space (Ollama body size limit)
        if has_transparency:
            img.save(buffered, format="PNG")
        else:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(buffered, format="JPEG", quality=85)
            
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    except Exception as e:
        print(f"Error resizing/compressing image: {e}")
        # Return original (sanitized) on error
        return _sanitize_b64(b64_str)

def build_image_dicts(images_b64):
    """Helper to convert list of b64 strings/urls into structured dicts for export."""
    if not images_b64: return []
    res = []
    for img in images_b64:
        if isinstance(img, str):
            if img.startswith("http"):
                res.append({'type': 'url', 'data': img})
            else:
                 res.append({'type': 'base64', 'data': _sanitize_b64(img)})
        elif isinstance(img, dict) and 'data' in img:
             # Handle already structured dicts if present
             data = img['data']
             if data.startswith("http"):
                res.append({'type': 'url', 'data': data})
             else:
                res.append({'type': 'base64', 'data': _sanitize_b64(data)})
    return res


def process_memory_tags(text: str, user_id: int, db: Session) -> Tuple[str, bool]:
    """
    Parses memory tags from the AI output, executes the corresponding DB operations,
    and returns the cleaned text (with tags removed) and a boolean indicating if any memory action was taken.
    """
    if not text:
        return text, False

    actions_performed = False

    # Regex for tags
    new_mem_pattern = re.compile(r'<new_memory>(.*?)</new_memory>', re.DOTALL | re.IGNORECASE)
    update_mem_pattern = re.compile(r'<update_memory:(\d+)>(.*?)</update_memory:\1>', re.DOTALL | re.IGNORECASE)
    delete_mem_pattern = re.compile(r'<delete_memory:(\d+)>(.*?)</delete_memory:\1>', re.DOTALL | re.IGNORECASE)
    
    # Process New Memories
    for match in new_mem_pattern.finditer(text):
        content = match.group(1).strip()
        if content:
            title = content[:30] + "..." if len(content) > 30 else content
            try:
                new_memory = UserMemory(owner_user_id=user_id, title=title, content=content)
                db.add(new_memory)
                db.commit()
                actions_performed = True
                print(f"INFO: New memory added for user {user_id}: {title}")
            except Exception as e:
                print(f"ERROR: Failed to add memory: {e}")
                db.rollback()

    # Pre-fetch memories to resolve indices for Update/Delete
    current_memories = db.query(UserMemory).filter(UserMemory.owner_user_id == user_id).order_by(UserMemory.created_at.asc()).all()

    # Process Updates
    for match in update_mem_pattern.finditer(text):
        try:
            index = int(match.group(1)) - 1
            new_content = match.group(2).strip()
            
            if 0 <= index < len(current_memories) and new_content:
                memory_to_update = current_memories[index]
                memory = db.query(UserMemory).filter(UserMemory.id == memory_to_update.id).first()
                if memory:
                    memory.content = new_content
                    memory.updated_at = func.now()
                    db.commit()
                    actions_performed = True
                    print(f"INFO: Memory #{index+1} (ID: {memory.id}) updated for user {user_id}")
            else:
                print(f"WARNING: Invalid memory index {index+1} for update.")
        except Exception as e:
            print(f"ERROR: Failed to update memory: {e}")
            db.rollback()

    # Process Deletes
    for match in delete_mem_pattern.finditer(text):
        try:
            index = int(match.group(1)) - 1
            if 0 <= index < len(current_memories):
                memory_to_delete = current_memories[index]
                db.query(UserMemory).filter(UserMemory.id == memory_to_delete.id).delete()
                db.commit()
                actions_performed = True
                print(f"INFO: Memory #{index+1} (ID: {memory_to_delete.id}) deleted for user {user_id}")
            else:
                print(f"WARNING: Invalid memory index {index+1} for deletion.")
        except Exception as e:
            print(f"ERROR: Failed to delete memory: {e}")
            db.rollback()
    
    # Strip tags from output
    cleaned_text = text
    cleaned_text = new_mem_pattern.sub('', cleaned_text)
    cleaned_text = update_mem_pattern.sub('', cleaned_text)
    cleaned_text = delete_mem_pattern.sub('', cleaned_text)
    
    return cleaned_text, actions_performed

def process_image_generation_tags(text: str, user: DBUser, db: Session, discussion_obj: LollmsDiscussion, main_loop=None, stream_queue=None) -> Tuple[str, List[str], List[Dict], List[Dict]]:
    """
    Parses <generate_image> tags, generates images via TTI binding.
    Returns: (cleaned_text, list_of_base64_images, list_of_image_metadata, list_of_groups)
    """
    # Pattern: <generate_image width="512" height="512" n="1">prompt</generate_image>
    pattern = re.compile(r'<generate_image\b([^>]*)>(.*?)</generate_image>', re.DOTALL | re.IGNORECASE)
    
    matches = list(pattern.finditer(text))
    if not matches:
        return text, [], [], []

    error_messages = []

    try:
        lc = build_lollms_client_from_params(
            username=user.username,
            load_llm=False,
            load_tti=True
        )
        if not lc.tti:
            # Explicit warning if TTI not available, but preserve original tag for user info
            return text, [], [], []
            
    except Exception as e:
        print(f"TTI Client Init Error: {e}")
        return text, [], [], []

    images_b64 = []
    generation_infos = []
    generated_groups = []
    
    current_image_count = 0

    # Process matches
    for match in matches:
        attr_str = match.group(1)
        prompt = match.group(2).strip()
        
        width = 1024
        height = 1024
        n_variants = 1
        
        for attr in re.findall(r'(\w+)="(\d+)"', attr_str):
            key, val = attr
            if key == 'width': width = int(val)
            elif key == 'height': height = int(val)
            elif key == 'n': n_variants = int(val)
        
        n_variants = max(1, min(n_variants, 10))
        
        if main_loop and stream_queue:
            payload = {"type": "step_start", "content": f"Generating image: {prompt[:30]}..."}
            main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder(payload)) + "\n")

        # Track indices for this group
        group_indices = []
        
        for _ in range(n_variants):
            try:
                image_bytes = lc.tti.generate_image(prompt=prompt, width=width, height=height)
                if image_bytes:
                    b64 = base64.b64encode(image_bytes).decode('utf-8')
                    images_b64.append(b64)
                    
                    generation_infos.append({
                        "index": current_image_count,
                        "prompt": prompt,
                        "model": lc.tti.config.get("model_name", "unknown"),
                        "width": width,
                        "height": height
                    })
                    group_indices.append(current_image_count)
                    current_image_count += 1
                else:
                    error_messages.append(f"Generator returned no data for prompt: {prompt[:20]}...")
            except Exception as e:
                error_messages.append(f"Generation failed: {str(e)}")
                print(f"Image generation failed for prompt '{prompt}': {e}")
        
        if group_indices:
            generated_groups.append({
                "id": str(uuid.uuid4()),
                "prompt": prompt,
                "indices": group_indices,
                "type": "generated",
                "selected_index": 0 # New: Default selected variant
            })

        if main_loop and stream_queue:
            payload = {"type": "step_end", "content": "Image generation step complete.", "id": None}
            main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder(payload)) + "\n")

    # Important: Return original text to preserve tags in chat history
    return text, images_b64, generation_infos, generated_groups

def process_slide_generation_tags(text: str, user: DBUser, db: Session, discussion_obj: LollmsDiscussion, message_id: str, main_loop=None, stream_queue=None) -> Tuple[str, Optional[str]]:
    """
    Parses <generate_slides> tags, extracting inner <Slide> contents or raw prompt, and triggers the slide generation task.
    Returns: (cleaned_text, task_id) where task_id is the ID of the background task if one was triggered, else None.
    """
    # Regex to capture the whole block including attributes
    # Pattern: <generate_slides attr="val"> ... <Slide>desc</Slide> ... </generate_slides>
    block_pattern = re.compile(r'<generate_slides\b([^>]*)>(.*?)</generate_slides>', re.DOTALL | re.IGNORECASE)
    slide_pattern = re.compile(r'<Slide>(.*?)</Slide>', re.DOTALL | re.IGNORECASE)
    
    matches = list(block_pattern.finditer(text))
    if not matches:
        return text, None

    triggered_task_id = None

    for match in matches:
        attr_str = match.group(1)
        content_str = match.group(2)
        
        width = 1024
        height = 768
        
        # Parse attributes from the parent tag
        width_match = re.search(r'width="(\d+)"', attr_str)
        if width_match: width = int(width_match.group(1))
        
        height_match = re.search(r'height="(\d+)"', attr_str)
        if height_match: height = int(height_match.group(1))
        
        # Extract individual slide prompts if present
        slides = [m.group(1).strip() for m in slide_pattern.finditer(content_str) if m.group(1).strip()]
        
        # If no explicit slides found, use the inner text as the "topic" prompt
        final_slides_arg = slides if slides else content_str.strip()
        
        if final_slides_arg:
            try:
                task_description = f"Creating {len(slides)} slides..." if slides else f"Planning slides for topic: {final_slides_arg[:30]}..."
                
                new_task = task_manager.submit_task(
                    name=f"Generating Slides",
                    target=_generate_slides_task,
                    args=(user.username, discussion_obj.id, message_id, final_slides_arg, width, height),
                    description=task_description,
                    owner_username=user.username
                )
                triggered_task_id = new_task.id
                
                if main_loop and stream_queue:
                    payload = {"type": "info", "content": "Started slide generation task."}
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder(payload)) + "\n")
                    
            except Exception as e:
                 print(f"Failed to start slide generation task: {e}")

    # Return original text to preserve tags
    return text, triggered_task_id

def process_street_view_tags(text: str, user: DBUser, db: Session, discussion_obj: LollmsDiscussion, main_loop=None, stream_queue=None) -> Tuple[str, List[str], List[Dict], List[Dict]]:
    """
    Parses <street_view> tags and fetches images from Google Street View Static API.
    """
    pattern = re.compile(r'<street_view>(.*?)</street_view>', re.DOTALL | re.IGNORECASE)
    matches = list(pattern.finditer(text))
    if not matches or not user.google_api_key:
        return text, [], [], []

    images_b64 = []
    generation_infos = []
    generated_groups = []
    current_image_count = 0

    for match in matches:
        location = match.group(1).strip()
        if location:
            if main_loop and stream_queue:
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "step_start", "content": f"Fetching Street View: {location}"})) + "\n")
            
            try:
                url = f"https://maps.googleapis.com/maps/api/streetview?size=600x400&location={location}&key={user.google_api_key}"
                resp = requests.get(url)
                if resp.status_code == 200:
                    b64 = base64.b64encode(resp.content).decode('utf-8')
                    images_b64.append(b64)
                    generation_infos.append({"index": current_image_count, "prompt": f"Street View: {location}", "model": "google_street_view", "type": "street_view"})
                    generated_groups.append({"id": str(uuid.uuid4()), "title": f"Street View: {location}", "type": "street_view", "indices": [current_image_count], "images": [b64]})
                    current_image_count += 1
            except Exception as e:
                print(f"Street View Error: {e}")

    return text, images_b64, generation_infos, generated_groups

def process_scheduler_tags(text: str, user: DBUser, db: Session) -> Tuple[str, List[str]]:
    """
    Parses <schedule_task name="..." cron="...">prompt</schedule_task> tags.
    """
    pattern = re.compile(r'<schedule_task\b([^>]*)>(.*?)</schedule_task>', re.DOTALL | re.IGNORECASE)
    matches = list(pattern.finditer(text))
    messages = []
    
    if not matches: return text, []
    
    for match in matches:
        attr_str = match.group(1)
        prompt = match.group(2).strip()
        name = "Untitled Task"
        cron = "0 8 * * *" # Default daily 8am
        
        for attr in re.findall(r'(\w+)="([^"]*)"', attr_str):
            if attr[0] == 'name': name = attr[1]
            if attr[0] == 'cron': cron = attr[1]
            
        try:
            new_task = ScheduledTask(owner_user_id=user.id, name=name, cron_expression=cron, prompt=prompt, is_active=True)
            db.add(new_task)
            db.commit()
            messages.append(f"Scheduled task '{name}' created with cron '{cron}'.")
        except Exception as e:
            messages.append(f"Failed to schedule task '{name}': {e}")
            
    return text, messages

def process_google_workspace_tags(text: str, user: DBUser, main_loop=None, stream_queue=None) -> Tuple[str, List[str]]:
    """
    Parses Google Workspace tags. Currently a placeholder for full OAuth implementation.
    """
    # Drive
    drive_list = re.findall(r'<google_drive_list>(.*?)</google_drive_list>', text, re.DOTALL | re.IGNORECASE)
    # Calendar
    calendar_add = re.findall(r'<calendar_add\b([^>]*)>(.*?)</calendar_add>', text, re.DOTALL | re.IGNORECASE)
    # Gmail
    gmail_send = re.findall(r'<gmail_send\b([^>]*)>(.*?)</gmail_send>', text, re.DOTALL | re.IGNORECASE)
    
    messages = []
    
    if drive_list:
        messages.append("Google Drive: Listing files (Mock execution - OAuth pending).")
    
    if calendar_add:
        messages.append("Google Calendar: Event creation received (Mock execution - OAuth pending).")

    if gmail_send:
        messages.append("Gmail: Email sending request received (Mock execution - OAuth pending).")

    return text, messages

def process_image_editing_tags(text: str, user: DBUser, db: Session, discussion_obj: LollmsDiscussion, main_loop=None, stream_queue=None, current_turn_images: List[str] = None) -> Tuple[str, List[str], List[Dict], List[Dict]]:
    """
    Parses <edit_image> tags to edit previously generated images.
    Returns: (cleaned_text, list_of_base64_images, list_of_image_metadata, list_of_groups)
    """
    # Pattern: <edit_image source_index="-1" strength="0.75" width="1024" height="1024">prompt</edit_image>
    pattern = re.compile(r'<edit_image\b([^>]*)>(.*?)</edit_image>', re.DOTALL | re.IGNORECASE)
    
    matches = list(pattern.finditer(text))
    if not matches:
        return text, [], [], []

    error_messages = []

    try:
        lc = build_lollms_client_from_params(
            username=user.username,
            load_llm=False,
            load_tti=True
        )
        if not lc.tti:
             # Preserve tags
            return text, [], [], []
            
    except Exception as e:
        print(f"TTI Client Init Error: {e}")
        return text, [], [], []

    images_b64 = []
    generation_infos = []
    generated_groups = []
    current_image_count = 0

    # [FIX] Robustly gather all images in chronological order
    all_available_images = []
    
    # 1. Load historical messages if needed to ensure we have the images
    if discussion_obj.messages is None:
        if hasattr(discussion_obj, 'load_messages'):
            discussion_obj.load_messages()
        else:
            discussion_obj.messages = []
    # 2. Iterate chronologically through all messages
    for msg in discussion_obj.messages:
        # Check for images in 'images' list or 'image_references'
        # lollms_client usually stores as list of b64 strings in `images`
        msg_images = msg.get_active_images() # Returns list of b64 strings
        for img in msg_images:
            all_available_images.append(_sanitize_b64(img))
            
    # 3. Append current turn images (if any were uploaded this turn and passed in)
    if current_turn_images:
        for img in current_turn_images:
            all_available_images.append(_sanitize_b64(img))

    for match in matches:
        attr_str = match.group(1)
        prompt = match.group(2).strip()
        
        source_index = -1
        strength = 0.75
        width = None
        height = None
        
        for attr in re.findall(r'(\w+)="([^"]*)"', attr_str):
            key, val = attr
            if key == 'source_index': source_index = int(val)
            elif key == 'strength': strength = float(val)
            elif key == 'width': width = int(val)
            elif key == 'height': height = int(val)

        # Resolve source image using collected chronological list
        source_image_b64 = None
        try:
            # Indices are 0-based for absolute, or negative for relative to end
            if source_index < 0:
                # e.g. -1 is last image, -2 is second to last
                final_idx = len(all_available_images) + source_index
                if 0 <= final_idx < len(all_available_images):
                    source_image_b64 = all_available_images[final_idx]
            else:
                if source_index < len(all_available_images):
                    source_image_b64 = all_available_images[source_index]
        except Exception as e:
            print(f"Error resolving index {source_index}: {e}")

        if not source_image_b64:
            error_messages.append(f"Could not find source image at index {source_index} for editing. (Total images: {len(all_available_images)})")
            continue

        # [FIX] Infer dimensions from source image if missing, to prevent 'NoneType' division errors
        if width is None or height is None:
            try:
                img_data = base64.b64decode(source_image_b64)
                with Image.open(io.BytesIO(img_data)) as img:
                    if width is None: width = img.width
                    if height is None: height = img.height
            except Exception as e:
                print(f"Error extracting dimensions from source image: {e}")
                # Fallback to defaults if image is corrupted or undecodable
                if width is None: width = 1024
                if height is None: height = 1024

        if main_loop and stream_queue:
            payload = {"type": "step_start", "content": f"Editing image: {prompt[:30]}..."}
            main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder(payload)) + "\n")

        try:
            # Check for correct edit method signature
            if hasattr(lc.tti, 'edit_image'):
                # Correct signature: images, prompt, ...
                image_bytes = lc.tti.edit_image(
                    images=source_image_b64,
                    prompt=prompt,
                    width=width,
                    height=height,
                    strength=strength
                )
            else:
                # Fallback: img2img via generate_image (uses 'image' kwarg)
                # This depends on specific binding implementation details
                image_bytes = lc.tti.generate_image(
                    image=source_image_b64,
                    prompt=prompt,
                    width=width,
                    height=height,
                    strength=strength
                )

            if image_bytes:
                b64 = base64.b64encode(image_bytes).decode('utf-8')
                images_b64.append(b64)
                
                generation_infos.append({
                    "index": current_image_count,
                    "prompt": prompt,
                    "model": lc.tti.config.get("model_name", "unknown"),
                    "type": "edit",
                    "source_index": source_index
                })
                
                generated_groups.append({
                    "id": str(uuid.uuid4()),
                    "prompt": prompt,
                    "indices": [current_image_count],
                    "type": "edited",
                    "selected_index": 0 # New
                })
                
                current_image_count += 1
            else:
                error_messages.append("TTI edit returned no data.")

        except Exception as e:
            error_messages.append(f"Image editing failed: {str(e)}")
            trace_exception(e)
        
        if main_loop and stream_queue:
            payload = {"type": "step_end", "content": "Image editing complete.", "id": None}
            main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder(payload)) + "\n")

    # Important: Return original text to preserve tags
    return text, images_b64, generation_infos, generated_groups



def perform_google_search(query: str, api_key: str, cse_id: str) -> List[Dict[str, str]]:
    if not google_build: return []
    try:
        service = google_build("customsearch", "v1", developerKey=api_key)
        res = service.cse().list(q=query, cx=cse_id, num=5).execute()
        items = res.get('items', [])
        return [{'title': item.get('title'), 'link': item.get('link'), 'snippet': item.get('snippet')} for item in items]
    except Exception: return []

def perform_wikipedia_search(query: str) -> List[Dict[str, str]]:
    pm.ensure_packages(["wikipedia-api", "wikipedia"])
    import wikipediaapi
    import wikipedia
    wiki = wikipediaapi.Wikipedia('LollmsWebAgent/1.0', 'en')
    page = wiki.page(query)
    if page.exists():
        return [{'title': page.title, 'link': page.fullurl, 'snippet': page.summary[:1000]}]
    search_results = wikipedia.search(query)
    res = []
    for title in search_results[:3]:
        p = wiki.page(title)
        if p.exists():
            res.append({'title': p.title, 'link': p.fullurl, 'snippet': p.summary[:500]})
    return res

def perform_search_single(query: str, provider: str, user: DBUser) -> List[Dict[str, str]]:
    """Handler for a single search engine turn."""
    if provider == "wikipedia": return perform_wikipedia_search(query)
    
    site_map = {
        "reddit": "site:reddit.com",
        "stackoverflow": "site:stackoverflow.com",
        "x": "site:x.com",
        "github": "site:github.com"
    }
    
    actual_query = query
    base_provider = provider
    if provider in site_map:
        actual_query = f"{site_map[provider]} {query}"
        base_provider = "google" if (user.google_api_key and user.google_cse_id) else "duckduckgo"

    if base_provider == "google" and user.google_api_key and user.google_cse_id:
        return perform_google_search(actual_query, user.google_api_key, user.google_cse_id)
    
    if base_provider == "duckduckgo" or base_provider in site_map:
        pm.ensure_packages("duckduckgo_search")
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = [r for r in ddgs.text(actual_query, max_results=5)]
                return [{'title': r.get('title'), 'link': r.get('href'), 'snippet': r.get('body')} for r in results]
        except Exception: pass
    return []

def perform_multi_search(query: str, providers: List[str], user: DBUser) -> List[Dict[str, Any]]:
    """Runs multiple engine searches in parallel and deduplicates."""
    all_results = []
    with ThreadPoolExecutor(max_workers=len(providers)) as pool:
        future_to_provider = {pool.submit(perform_search_single, query, p, user): p for p in providers}
        for future in as_completed(future_to_provider):
            try:
                results = future.result()
                for r in results: r['engine'] = future_to_provider[future]
                all_results.extend(results)
            except Exception: pass

    seen_links = set()
    unique_results = []
    for r in all_results:
        if r['link'] not in seen_links:
            seen_links.add(r['link'])
            unique_results.append(r)
    for i, res in enumerate(unique_results): res['index'] = i + 1
    return unique_results

def process_herd_logic(
    user: DBUser, 
    discussion_obj: LollmsDiscussion, 
    prompt: str, 
    main_loop, 
    stream_queue, 
    db_session: Session
):
    """
    Executes the 4-phase Herd Mode workflow:
    1. Pre-code Brainstorming (Ideas)
    2. Answer Crafting (Leader Draft)
    3. Post-code Brainstorming (Critique)
    4. Final Answer (Leader Final)
    """
    precode_crew = []
    postcode_crew = []
    
    # --- DYNAMIC CREW GENERATION ---
    if user.herd_dynamic_mode and user.herd_model_pool:
        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "step_start", "content": "Herd Manager: analyzing task and assembling dynamic teams..."})) + "\n")
        
        try:
            # 1. Prepare inputs
            model_pool_desc = json.dumps(user.herd_model_pool, indent=2)
            leader_client = get_user_lollms_client(user.username)
            
            # 2. Construct Manager Prompt
            manager_prompt = f"""You are the Herd Manager.
Your goal is to assemble two teams of AI agents to solve a specific user request.
You must CREATE distinct personas (Name + Specific System Prompt) for each agent and assign them to the most appropriate 'model' from the Available Models list.

[USER REQUEST]
"{prompt}"

[AVAILABLE MODELS POOL]
{model_pool_desc}

[INSTRUCTIONS]
1. **Pre-code Crew**: Create 2-3 agents to brainstorm ideas, architecture, and high-level solutions. 
   - Define a unique `system_prompt` for each that gives them a specific perspective (e.g., "You are a database expert", "You are a creative thinker").
2. **Post-code Crew**: Create 2-3 agents to critique, review, and find flaws.
   - Define a unique `system_prompt` for each (e.g., "You are a security auditor", "You are a performance optimizer").
3. **Model Assignment**: For the `model` field, you MUST use one of the strings from the "model" key in the pool above.

[OUTPUT FORMAT]
Return ONLY a valid JSON object. No markdown formatting.
{{
  "pre_code_crew": [
    {{ "name": "Agent Name", "system_prompt": "You are...", "model": "model_id_from_pool" }}
  ],
  "post_code_crew": [
    {{ "name": "Agent Name", "system_prompt": "You are...", "model": "model_id_from_pool" }}
  ]
}}
"""
            # 3. Generate Configuration
            json_config_str = leader_client.generate_code(manager_prompt, language="json").strip()
            
            # Cleanup potential markdown code blocks if the model ignores instruction
            if json_config_str.startswith("```"):
                json_config_str = json_config_str.split('\n', 1)[1]
                if json_config_str.endswith("```"):
                    json_config_str = json_config_str.rsplit('\n', 1)[0]

            if json_config_str:
                try:
                    config = json.loads(json_config_str)
                    precode_crew = config.get("pre_code_crew", [])
                    postcode_crew = config.get("post_code_crew", [])
                    
                    # Mark as dynamic for the runner
                    for agent in precode_crew: agent['is_dynamic'] = True
                    for agent in postcode_crew: agent['is_dynamic'] = True
                    
                    msg = f"**Dynamic Teams Assembled:**\n\n*Pre-code Phase:*\n" + "\n".join([f"- {a['name']} ({a['model']})" for a in precode_crew])
                    msg += "\n\n*Post-code Phase:*\n" + "\n".join([f"- {a['name']} ({a['model']})" for a in postcode_crew])
                    
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "step_end", "content": msg})) + "\n")
                except json.JSONDecodeError as je:
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "step_end", "content": f"Failed to parse crew configuration: {je}. Using static fallback."})) + "\n")
            else:
                 main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "step_end", "content": "Model returned empty configuration. Using static fallback."})) + "\n")

        except Exception as e:
            trace_exception(e)
            main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "step_end", "content": f"Dynamic generation error: {e}. Falling back."})) + "\n")

    # --- FALLBACK TO STATIC IF DYNAMIC FAILED OR DISABLED ---
    if not precode_crew and not postcode_crew:
        precode_crew = user.herd_precode_participants or []
        postcode_crew = user.herd_postcode_participants or []
        
        # Legacy fallback
        if not precode_crew and not postcode_crew:
            legacy_crew = user.herd_participants or []
            precode_crew = legacy_crew
            postcode_crew = legacy_crew

    if not precode_crew and not postcode_crew:
        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "info", "content": "Herd mode active but no participants found. Proceeding with standard generation."})) + "\n")
        return ""

    rounds = user.herd_rounds if user.herd_rounds is not None else 2
    
    # [FIX] Load previous discussion history to provide context to agents
    history_text = ""
    # Ensure messages are loaded
    if discussion_obj.messages is None:
        if hasattr(discussion_obj, 'load_messages'):
            discussion_obj.load_messages()
        else:
            discussion_obj.messages = []

    
    # Simple approach: Take last 10 messages for context
    recent_messages = discussion_obj.messages[-10:] 
    
    for msg in recent_messages:
        # Skip the currently generating AI message (if it exists as a placeholder)
        if msg.sender_type == 'assistant' and not msg.content:
            continue
        
        sender = msg.sender
        text = msg.content
        history_text += f"{sender}: {text}\n"

    full_context_history = f"Discussion History:\n{history_text}\n\n[Current Task]: {prompt}\n\n"
    
    # Helper to run an agent
    def run_agent(agent_def, context, phase_name, round_num):
        model_full = agent_def.get('model')
        
        # Dynamic agents have explicit system prompts
        is_dynamic = agent_def.get('is_dynamic', False)
        
        persona_name = agent_def.get('name') if is_dynamic else agent_def.get('personality')
        display_name = persona_name or model_full or "Agent"
        
        # Resolve Binding/Model
        binding_alias = None
        model_name = None
        if model_full and '/' in model_full:
            binding_alias, model_name = model_full.split('/', 1)
        elif not model_full:
             # Fallback default
             default_binding = db_session.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).first()
             if default_binding:
                 binding_alias = default_binding.alias
                 model_name = default_binding.default_model_name

        # Resolve System Prompt
        sys_prompt = ""
        
        if is_dynamic:
            sys_prompt = agent_def.get('system_prompt', "You are a helpful assistant.")
        else:
            # Static Logic: Load from DB
            sys_prompt = f"You are participating in a {phase_name} session."
            if persona_name:
                pers = db_session.query(DBPersonality).filter(
                    (DBPersonality.name == persona_name) | (DBPersonality.id == persona_name)
                ).first()
                if pers:
                    sys_prompt = pers.prompt_text
            
            if phase_name == "Pre-code Brainstorming":
                sys_prompt += "\n\nTask: Brainstorm ideas, architecture, and high-level solutions for the user's request. Do not write full code yet. Critique previous ideas if any."
            elif phase_name == "Post-code Critique":
                sys_prompt += "\n\nTask: Review the proposed solution/code. Look for bugs, security issues, logic errors, or missing requirements. Be critical but constructive."

        # Emit step start
        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "step_start", "content": f"**{display_name}** ({phase_name} Round {round_num})" })) + "\n")
        
        try:
            temp_client = build_lollms_client_from_params(
                username=user.username,
                binding_alias=binding_alias,
                model_name=model_name,
                load_llm=True,
                load_tti=False,
                load_tts=False,
                load_stt=False,
                load_mcp=False
            )
            
            response = temp_client.generate_text(
                context, 
                system_prompt=sys_prompt,
                max_new_tokens=1024,
                temperature=0.7
            )
            
            # Emit step end with result content
            main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "step_end", "content": response })) + "\n")
            return f"\n\n[{phase_name} - {display_name}]:\n{response}"
        except Exception as e:
            err = f"Agent {display_name} failed: {e}"
            print(err)
            main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "step_end", "content": err, "status": "error"})) + "\n")
            return f"\n\n[{phase_name} - {display_name}]: [FAILED]"

    # --- PHASE 1: Pre-code Brainstorming ---
    if precode_crew:
        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "info", "content": "Phase 1: Pre-code Brainstorming"})) + "\n")
        
        for r in range(rounds):
            all_ready = True
            for agent in precode_crew:
                out = run_agent(agent, full_context_history, "Pre-code Brainstorming", r+1)
                full_context_history += out
                
                if "<ready/>" not in out.lower():
                    all_ready = False
            
            if all_ready and r > 0:
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "info", "content": "All agents ready. Proceeding."})) + "\n")
                break
        
    # --- PHASE 2: Answer Crafting (Leader Draft) ---
    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "step_start", "content": "Phase 2: Leader drafting solution..."})) + "\n")
    
    leader_client = get_user_lollms_client(user.username)
    leader_prompt = f"{full_context_history}\n\n[INSTRUCTION]: Act as the Team Leader. Based on the brainstorming above, create a complete draft solution/implementation."
    
    try:
        draft_response = leader_client.generate_text(leader_prompt, max_new_tokens=2048)
        full_context_history += f"\n\n[Leader Draft]:\n{draft_response}"
        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "step_end", "content": draft_response })) + "\n")
    except Exception as e:
        full_context_history += f"\n\n[Leader Draft]: [FAILED] {e}"
        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "step_end", "content": f"Draft generation failed: {e}", "status": "error"})) + "\n")

    # --- PHASE 3: Post-code Brainstorming ---
    if postcode_crew:
        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "info", "content": "Phase 3: Post-code Critique"})) + "\n")
        
        for r in range(rounds):
            all_ready = True
            for agent in postcode_crew:
                out = run_agent(agent, full_context_history, "Post-code Critique", r+1)
                full_context_history += out
                
                if "<ready/>" not in out.lower():
                    all_ready = False
            
            if all_ready and r > 0:
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "info", "content": "All agents satisfied."})) + "\n")
                break

    # --- PHASE 4: Final Answer (Handled by caller) ---
    return full_context_history


def build_llm_generation_router(router: APIRouter):
    @router.post("/{discussion_id}/chat")
    async def chat_in_existing_discussion(
        discussion_id: str,
        prompt: str = Form(...),
        image_server_paths_json: str = Form("[]"),
        parent_message_id: Optional[str] = Form(None), 
        is_resend: bool = Form(False),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ) -> StreamingResponse:
        """
        Main chat endpoint. Handles text generation, RAG, Web Search, Herd Mode, 
        and internal tool execution (Image Gen/Edit, Memory).
        """
        # 1. Retrieve discussion and owner details
        discussion_obj, owner_username, permission, owner_db_user = await get_discussion_and_owner_for_request(
            discussion_id, current_user, db, 'interact'
        )

        # 2. Setup LLM Client
        user_model_full = current_user.lollms_model_name
        binding_alias = None
        if user_model_full and '/' in user_model_full:
            binding_alias, _ = user_model_full.split('/', 1)
        
        lc = get_user_lollms_client(owner_username, binding_alias)
        discussion_obj.lollms_client = lc
        
        if not lc:
            async def error_stream():
                yield json.dumps({"type": "error", "content": "Failed to get a valid LLM Client. Check your binding settings."}) + "\n"
            return StreamingResponse(error_stream(), media_type="application/x-ndjson")

        # 3. Setup RAG Callback
        def query_rag_callback(query: str, ss, rag_top_k=None, rag_min_similarity_percent=None) -> List[Dict]:
            if not ss: return []
            try:
                if rag_top_k is None:
                    rag_top_k = current_user.rag_top_k if current_user.rag_top_k is not None else 5
                if rag_min_similarity_percent is None:
                    rag_min_similarity_percent = current_user.rag_min_sim_percent if current_user.rag_min_sim_percent is not None else 50
                retrieved_chunks = ss.query(query, top_k=rag_top_k, min_similarity_percent=rag_min_similarity_percent)
                revamped_chunks=[]
                for entry in retrieved_chunks:
                    revamped_entry = {
                        "metadata": entry.get('document_metadata', {}),
                        "title": Path(entry.get("file_path", "unknown")).name,
                        "content": entry.get("chunk_text", ""),
                        "score": float(entry.get("similarity_percent", 0))
                    }
                    revamped_chunks.append(revamped_entry)
                return revamped_chunks
            except Exception as e:
                trace_exception(e)
                return [{"error": f"Error during RAG query: {e}"}]
        
        # 4. Construct Context (Memory + Dynamic Preamble)
        memory_content = ""
        memory_instructions = ""
        if owner_db_user.memory_enabled:
            memories = db.query(UserMemory).filter(UserMemory.owner_user_id == owner_db_user.id).order_by(UserMemory.created_at.asc()).all()
            if memories:
                memory_text = "\n".join([f"[Memory #{idx+1}] {m.title}: {m.content}" for idx, m in enumerate(memories)])
                memory_content = f"\n## Long-Term Memory Bank\nYou have access to the following memories:\n{memory_text}\n"
            else:
                memory_content = "\n## Long-Term Memory Bank\nThe memory bank is currently empty.\n"
            
            memory_instructions = (
                "\n## Memory Management\n"
                "Manage memories using these tags (refer to Index #):\n"
                "- Add: `<new_memory>info</new_memory>`\n"
                "- Update: `<update_memory:INDEX>content</update_memory:INDEX>`\n"
                "- Delete: `<delete_memory:INDEX></delete_memory:INDEX>`\n"
            )
            if owner_db_user.auto_memory_enabled:
                memory_instructions += "Save important user details automatically using `<new_memory>` tags.\n"

        discussion_obj.memory = memory_content
        
        # Get personality if active
        db_pers = db.query(DBPersonality).filter(DBPersonality.id == owner_db_user.active_personality_id).first() if owner_db_user.active_personality_id else None
        
        # NEW: Prepare personality data_source parameter
        personality_data_source = None
        if db_pers:
            if db_pers.data_source_type == 'static_text' and db_pers.data_source:
                # Mode 1: Static text - pass as string
                personality_data_source = db_pers.data_source
            
            elif db_pers.data_source_type == 'datastore' and db_pers.data_source:
                # Mode 2: RAG datastore - pass as callable
                try:
                    pers_ss = get_safe_store_instance(owner_username, db_pers.data_source, db, permission_level="read_query")
                    # Create a callable that queries the datastore
                    def personality_rag_query(query: str) -> str|List[dict]:
                        """Query the personality's RAG datastore and return formatted context."""
                        try:
                            if current_user.rag_top_k is None:
                                rag_top_k = 5
                            else:
                                rag_top_k = current_user.rag_top_k
                            if current_user.rag_min_sim_percent is None:
                                rag_min_sim_percent = 50
                            else:
                                rag_min_sim_percent = current_user.rag_min_sim_percent
                                
                            retrieved_chunks = pers_ss.query(query, top_k=rag_top_k, min_similarity_percent=rag_min_sim_percent)
                            
                            if not retrieved_chunks:
                                return ""
                            
                            # Format the retrieved chunks into the expected dictionary structure
                            formatted_chunks = []
                            for entry in retrieved_chunks:
                                chunk_text = entry.get("chunk_text", "")
                                file_path = entry.get("file_path", "unknown")
                                similarity = entry.get("similarity_percent", 0)
                                
                                formatted_chunks.append({
                                    "content": chunk_text,
                                    "text": chunk_text,  # Alias for compatibility
                                    "source": Path(file_path).name,
                                    "score": similarity,  # Already in percent (0-100)
                                    "value": similarity,  # Alias for compatibility
                                    "similarity_percent": similarity  # Keep original field too
                                })
                            
                            return formatted_chunks
                        except Exception as e:
                            trace_exception(e)
                            return f"[Error querying personality knowledge base: {e}]"
                    
                    personality_data_source = personality_rag_query
                except Exception as e:
                    print(f"Warning: Could not load personality datastore {db_pers.data_source}: {e}")
                    personality_data_source = None
        
        rag_datastore_ids = (discussion_obj.metadata or {}).get('rag_datastore_ids', [])
        use_rag = {ss.name: {"name": ss.name, "description": ss.description, "callable": partial(query_rag_callback, ss=ss)} 
                   for ds_id in rag_datastore_ids if (ss := get_safe_store_instance(owner_username, ds_id, db))}

        # 5. Build Dynamic Preamble
        preamble_parts = []
        if owner_db_user.share_dynamic_info_with_llm:
            now = datetime.now()
            preamble_parts.append(f"- Current Date: {now.strftime('%A, %B %d, %Y')}")
            preamble_parts.append(f"- Current Time: {now.strftime('%H:%M:%S')}")
            if owner_db_user.tell_llm_os: preamble_parts.append(f"- User's OS: {platform.system()}")

        if owner_db_user.fun_mode: preamble_parts.append("- Fun Mode: Be humorous and use emojis.")
        if owner_db_user.force_ai_response_language and owner_db_user.ai_response_language != 'auto':
            preamble_parts.append(f"- Respond exclusively in: {owner_db_user.ai_response_language}")
        if owner_db_user.share_personal_info_with_llm and owner_db_user.user_personal_info:
            preamble_parts.append(f"## User Personal Information:\n{owner_db_user.user_personal_info}")

        # Feature Specific Instructions
        if owner_db_user.image_annotation_enabled: preamble_parts.append("## Image Annotation: Use <annotate>[JSON]</annotate> for bounding boxes/points.")
        if owner_db_user.image_generation_enabled: preamble_parts.append("## Image Gen: Use <generate_image width=\"W\" height=\"H\" n=\"N\">prompt</generate_image>.")
        if owner_db_user.slide_maker_enabled: preamble_parts.append("## Slides: Use <generate_slides><Slide>desc</Slide></generate_slides>.")
        if owner_db_user.image_editing_enabled: preamble_parts.append("## Image Edit: Use <edit_image source_index=\"-1\" strength=\"0.8\">prompt</edit_image>.")
        if owner_db_user.street_view_enabled and owner_db_user.google_api_key: preamble_parts.append("## Street View: Use <street_view>location</street_view>.")
        if owner_db_user.scheduler_enabled: preamble_parts.append("## Scheduler: Use <schedule_task name=\"Title\" cron=\"* * * * *\">Prompt to run</schedule_task>. Cron format: min hour day month dow.")
        if owner_db_user.google_drive_enabled: preamble_parts.append("## Google Drive: Use <google_drive_list>folder_id</google_drive_list> to list files. Use <google_drive_read>file_id</google_drive_read> to read.")
        if owner_db_user.google_calendar_enabled: preamble_parts.append("## Calendar: Use <calendar_list>today</calendar_list> or <calendar_add start=\"ISO\" end=\"ISO\">Title</calendar_add>.")
        if owner_db_user.google_gmail_enabled: preamble_parts.append("## Gmail: Use <gmail_send to=\"email\">Subject|Body</gmail_send> or <gmail_list>count</gmail_list>.")

        if getattr(owner_db_user, 'note_generation_enabled', False): preamble_parts.append("## Notes: Use ```note ... ``` for structured data.")
        if memory_instructions: preamble_parts.append(memory_instructions)

        dynamic_preamble = "## Dynamic Context\n" + "\n".join(preamble_parts) + "\n\n" if preamble_parts else ""
        
        # User Data Zone processing
        user_data_zone = owner_db_user.data_zone or ""
        username_to_use = owner_db_user.preferred_name or current_user.username
        replacements = {"{{date}}": now.strftime("%Y-%m-%d"), "{{time}}": now.strftime("%H:%M:%S"), "{{user_name}}": username_to_use}
        for k, v in replacements.items(): user_data_zone = user_data_zone.replace(k, v)
        discussion_obj.user_data_zone = user_data_zone

        # 6. Setup Personality & Tools
        combined_mcps = list(set(((discussion_obj.metadata or {}).get('active_tools', [])) + (db_pers.active_mcps if db_pers and db_pers.active_mcps else [])))
        active_personality = LollmsPersonality(
            name=db_pers.name if db_pers else "Assistant",
            author=db_pers.author,
            category=db_pers.category,
            description=db_pers.description,
            system_prompt=dynamic_preamble + (db_pers.prompt_text if db_pers else "You are a helpful assistant."),
            active_mcps=combined_mcps,
            data_source=personality_data_source  # Now correctly passes string OR callable
        )

        main_loop = asyncio.get_running_loop()
        stream_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        stop_event = threading.Event()
        user_sessions.setdefault(current_user.username, {}).setdefault("active_generation_control", {})[discussion_id] = stop_event

        async def stream_generator() -> AsyncGenerator[str, None]:
            all_events = []
            
            def blocking_call():
                start_time = time.time()
                first_chunk_time = None

                def llm_callback(chunk: Any, msg_type: MSG_TYPE, params: Optional[Dict] = None, **kwargs) -> bool:
                    nonlocal first_chunk_time
                    if stop_event.is_set(): return False
                    if msg_type == MSG_TYPE.MSG_TYPE_CHUNK and first_chunk_time is None:
                        first_chunk_time = time.time()
                        ttft = (first_chunk_time - start_time) * 1000
                        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "ttft", "content": round(ttft, 2)}) + "\n")

                    payload_map = {
                        MSG_TYPE.MSG_TYPE_CHUNK: {"type": "chunk", "content": chunk},
                        MSG_TYPE.MSG_TYPE_STEP_START: {"type": "step_start", "content": chunk, "id": (params or {}).get("id")},
                        MSG_TYPE.MSG_TYPE_STEP_END: {"type": "step_end", "content": chunk, "id": (params or {}).get("id"), "status": "done"},
                        MSG_TYPE.MSG_TYPE_INFO: {"type": "info", "content": chunk},
                        MSG_TYPE.MSG_TYPE_THOUGHT_CONTENT: {"type": "thought", "content": chunk},
                        MSG_TYPE.MSG_TYPE_SOURCES_LIST: {"type": "sources", "content": chunk}
                    }
                    payload = payload_map.get(msg_type)
                    if payload:
                        if payload['type'] != "chunk": all_events.append(payload)
                        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder(payload)) + "\n")
                    return True

                try:
                    # Initial Image Handling
                    images_for_message = []
                    image_server_paths = json.loads(image_server_paths_json)
                    if image_server_paths and not is_resend:
                        temp_path = get_user_temp_uploads_path(current_user.username)
                        assets_path = get_user_discussion_assets_path(owner_username) / discussion_id
                        assets_path.mkdir(parents=True, exist_ok=True)
                        for temp_rel_path in image_server_paths:
                            filename = Path(temp_rel_path).name
                            if (temp_path / filename).exists():
                                persistent_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
                                shutil.move(str(temp_path / filename), str(assets_path / persistent_filename))
                                b64 = base64.b64encode((assets_path / persistent_filename).read_bytes()).decode('utf-8')
                                images_for_message.append(resize_base64_image(b64, owner_db_user.max_image_width, owner_db_user.max_image_height))

                    # --- WEB SEARCH AGENT (Persistent Source of Truth) ---
                    search_context = ""
                    search_sources_list = []
                    
                    if owner_db_user.web_search_enabled:
                        active_providers = owner_db_user.web_search_providers or ["google"]
                        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "step_start", "content": "Web Agent: Analyzing need for search..."}) + "\n")
                        
                        pre_flight = f"User: \"{prompt}\". Do you need to search the internet? Respond JSON: {{ \"search\": true/false, \"query\": \"terms\" }}"
                        try:
                            decision_text = lc.generate_text(pre_flight, max_new_tokens=100, temperature=0.0)
                            json_match = re.search(r'\{.*\}', decision_text, re.DOTALL)
                            if json_match:
                                decision = json.loads(json_match.group(0))
                                if decision.get("search"):
                                    search_query = decision.get("query", prompt)
                                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "step_end", "content": f"Web Agent: Decided to search for '{search_query}'"}) + "\n")
                                    
                                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "step_start", "content": f"Web Agent: Searching {', '.join(active_providers)}..."}) + "\n")
                                    results = perform_multi_search(search_query, active_providers, owner_db_user)
                                    
                                    if results:
                                        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "step_end", "content": f"Web Agent: Found {len(results)} results."}) + "\n")
                                        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "step_start", "content": "Web Agent: Reading page contents..."}) + "\n")
                                        
                                        scraped = []
                                        scraper = ScrapeMaster()
                                        for res in results[:3]:
                                            try:
                                                c = scraper.scrape(res['link'])
                                                if c and len(c.strip()) > 500:
                                                    scraped.append(f"### {res['title']}\nURL: {res['link']}\n{c.strip()[:3500]}")
                                            except Exception: pass
                                        
                                        search_context = "### Web Search Context:\n" + "\n".join(scraped) + "\n"
                                        for i, res in enumerate(results):
                                            search_sources_list.append({"title": res['title'], "content": res['snippet'], "source": res['link'], "index": i+1})
                                        
                                        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "step_end", "content": f"Web Agent: Digested {len(scraped)} pages."}) + "\n")
                                        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "sources", "content": search_sources_list}) + "\n")
                                    else:
                                        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "step_end", "content": "Web Agent: No results found.", "status": "failed"}) + "\n")
                                else:
                                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "step_end", "content": "Web Agent: Decided search is unnecessary."}) + "\n")
                        except Exception as e:
                            main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "step_end", "content": f"Web Agent Error: {e}", "status": "failed"}) + "\n")

                    # --- HERD MODE ---
                    herd_context = ""
                    if owner_db_user.herd_mode_enabled:
                        db_herd = next(get_db())
                        try: herd_context = process_herd_logic(owner_db_user, discussion_obj, prompt, main_loop, stream_queue, db_herd)
                        finally: db_herd.close()

                    # Final Prompt Assembly
                    final_prompt = prompt
                    if search_context:
                        active_personality.system_prompt += f"\n\n{search_context}\nUse this context to answer. Cite using [1], [2] tags."
                    if herd_context:
                        final_prompt += f"\n\n[Debate History]:\n{herd_context}\n\n[Final Instruction]: Synthesize the definitive answer."

                    # Core Generation
                    result = discussion_obj.chat(
                        branch_tip_id=parent_message_id if is_resend else None,
                        user_message=final_prompt, personality=active_personality,
                        use_mcps=combined_mcps, use_data_store=use_rag, images=images_for_message,
                        streaming_callback=llm_callback, think=owner_db_user.reasoning_activation,
                        reasoning_effort=owner_db_user.reasoning_effort, add_user_message=not is_resend,
                        use_rlm=owner_db_user.rlm_enabled,

                    )
                    
                    ai_msg = result.get('ai_message')
                    if ai_msg:
                        # Update Metadata
                        # Fuse sources (RAG + Web Search)
                        current_sources = ai_msg.metadata.get('sources', [])
                        if search_sources_list:
                            # Re-index web sources to continue after RAG sources
                            start_index = len(current_sources) + 1
                            for i, src in enumerate(search_sources_list):
                                src['index'] = start_index + i
                            all_sources = current_sources + search_sources_list
                            ai_msg.set_metadata_item('sources', all_sources, discussion_obj)

                        # Process Internal Tags (Memory, Image Gen, Image Edit)
                        if owner_db_user.memory_enabled:
                            db_mem = next(get_db())
                            try:
                                cleaned, action = process_memory_tags(ai_msg.content, owner_db_user.id, db_mem)
                                if action: 
                                    ai_msg.content = cleaned
                                    manager.send_personal_message_sync({"type": "data_zone_processed", "data": {"zone": "memory"}}, current_user.id)
                            finally: db_mem.close()

                        if owner_db_user.image_generation_enabled:
                            db_img = next(get_db())
                            try:
                                _, imgs, meta, groups = process_image_generation_tags(ai_msg.content, owner_db_user, db_img, discussion_obj, main_loop, stream_queue)
                                _, slide_tid = process_slide_generation_tags(ai_msg.content, owner_db_user, db_img, discussion_obj, ai_msg.id, main_loop, stream_queue)
                                if imgs:
                                    ai_msg.add_image_pack(imgs, group_type="generated", active_by_default=owner_db_user.activate_generated_images, title=meta[0]['prompt'])
                                    ai_msg.set_metadata_item("generated_image_infos", (ai_msg.metadata.get("generated_image_infos", []) + meta), discussion_obj)
                                    ai_msg.set_metadata_item("generated_groups", (ai_msg.metadata.get("generated_groups", []) + groups), discussion_obj)
                                if slide_tid: ai_msg.set_metadata_item('active_task_id', slide_tid, discussion_obj)
                                discussion_obj.commit()
                            finally: db_img.close()
                        
                        # Google Street View
                        if owner_db_user.street_view_enabled:
                            db_sv = next(get_db())
                            try:
                                _, imgs, meta, groups = process_street_view_tags(ai_msg.content, owner_db_user, db_sv, discussion_obj, main_loop, stream_queue)
                                if imgs:
                                    ai_msg.add_image_pack(imgs, group_type="street_view", active_by_default=True, title=groups[0]['title'])
                                    discussion_obj.commit()
                            finally: db_sv.close()

                        # Scheduler
                        if owner_db_user.scheduler_enabled:
                            db_sched = next(get_db())
                            try:
                                _, msgs = process_scheduler_tags(ai_msg.content, owner_db_user, db_sched)
                                if msgs:
                                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "info", "content": " | ".join(msgs)})) + "\n")
                            finally: db_sched.close()

                        # Google Workspace (Drive, Calendar, Gmail)
                        if any([owner_db_user.google_drive_enabled, owner_db_user.google_calendar_enabled, owner_db_user.google_gmail_enabled]):
                            _, msgs = process_google_workspace_tags(ai_msg.content, owner_db_user, main_loop, stream_queue)
                            if msgs:
                                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder({"type": "info", "content": " | ".join(msgs)})) + "\n")

                        # Post-generation Stats
                        ttft = (first_chunk_time - start_time) * 1000 if first_chunk_time else 0
                        tps = (ai_msg.tokens - 1) / (time.time() - first_chunk_time) if first_chunk_time and ai_msg.tokens > 1 else 0
                        ai_msg.set_metadata_item('ttft', round(ttft, 2), discussion_obj)
                        ai_msg.set_metadata_item('tps', round(tps, 2), discussion_obj)
                        ai_msg.set_metadata_item('events', all_events, discussion_obj)

                    # Finalize
                    def msg_to_out(m): return None if not m else {"id": m.id, "sender": m.sender, "content": m.content, "metadata": m.metadata, "sender_type": m.sender_type, "image_references": [f"data:image/png;base64,{i}" for i in (m.images or [])]}
                    
                    finalize_payload = {
                        "type": "finalize",
                        "data": {"user_message": msg_to_out(result.get('user_message')), "ai_message": msg_to_out(ai_msg)},
                        "discussion": {"id": discussion_id, "discussion_data_zone": discussion_obj.discussion_data_zone}
                    }
                    if current_user.auto_title and discussion_obj.metadata.get('title',"").startswith("New Discussion"):
                        finalize_payload["new_title"] = discussion_obj.auto_title()
                    
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder(finalize_payload)) + "\n")

                except Exception as e:
                    trace_exception(e)
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": str(e)}) + "\n")
                finally:
                    user_sessions.get(current_user.username, {}).get("active_generation_control", {}).pop(discussion_id, None)
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)
            
            main_loop.run_in_executor(executor, blocking_call)
            while True:
                item = await stream_queue.get()
                if item is None: break
                yield item

        return StreamingResponse(stream_generator(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @router.post("/{discussion_id}/stop_generation", status_code=200)
    async def stop_discussion_generation(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user)):
        username = current_user.username
        stop_event = user_sessions.get(username, {}).get("active_generation_control", {}).get(discussion_id)
        if stop_event and isinstance(stop_event, threading.Event):
            stop_event.set()
            return {"message": "Stop signal sent."}
        else:
            raise HTTPException(status_code=404, detail="No active generation found for this discussion.")
