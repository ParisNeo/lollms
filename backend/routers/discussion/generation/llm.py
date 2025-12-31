# backend/routers/discussion/generation/llm.py
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
from backend.db.models.db_task import DBTask
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.discussion import SharedDiscussionLink as DBSharedDiscussionLink
from backend.db.models.user import (User as DBUser, UserMessageGrade,
                                     UserStarredDiscussion)
from backend.db.models.memory import UserMemory
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

# Google Search Tools
try:
    from googleapiclient.discovery import build as google_build
except ImportError:
    google_build = None

from scrapemaster import ScrapeMaster

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
                "type": "generated"
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
    if not discussion_obj.messages:
        discussion_obj.load_messages()
    
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
                    "type": "edited"
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
    """Performs a Google Custom Search and returns a list of results."""
    if not google_build:
        raise ImportError("google-api-python-client is not installed.")
    
    try:
        service = google_build("customsearch", "v1", developerKey=api_key)
        res = service.cse().list(q=query, cx=cse_id, num=5).execute()
        items = res.get('items', [])
        return [{'title': item.get('title'), 'link': item.get('link'), 'snippet': item.get('snippet')} for item in items]
    except Exception as e:
        print(f"Google Search Error: {e}")
        return []

def build_llm_generation_router(router: APIRouter):
    @router.post("/{discussion_id}/chat")
    async def chat_in_existing_discussion(
        discussion_id: str,
        prompt: str = Form(...),
        image_server_paths_json: str = Form("[]"),
        parent_message_id: Optional[str] = Form(None), 
        is_resend: bool = Form(False),
        web_search_enabled: bool = Form(False), # New param from frontend
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ) -> StreamingResponse:
        discussion_obj, owner_username, permission, owner_db_user = await get_discussion_and_owner_for_request(
            discussion_id, current_user, db, 'interact'
        )

        user_model_full = current_user.lollms_model_name
        binding_alias = None
        if user_model_full and '/' in user_model_full:
            binding_alias, _ = user_model_full.split('/', 1)
        
        lc = get_user_lollms_client(owner_username, binding_alias)
        discussion_obj.lollms_client = lc
        
        if not lc:
            async def error_stream():
                yield json.dumps({"type": "error", "content": "Failed to get a valid LLM Client from the discussion object."}) + "\n"
            return StreamingResponse(error_stream(), media_type="application/x-ndjson")

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
                    revamped_entry = {}
                    if 'document_metadata' in entry:
                        revamped_entry["metadata"] = entry['document_metadata']
                    if "file_path" in entry:
                        revamped_entry["title"]=Path(entry["file_path"]).name
                    if "chunk_text" in entry:
                        revamped_entry["content"]=entry["chunk_text"]
                    if "similarity_percent" in entry:
                        revamped_entry["score"] = entry["similarity_percent"]
                    revamped_chunks.append(revamped_entry)
                return revamped_chunks
            except Exception as e:
                trace_exception(e)
                return [{"error": f"Error during RAG query on datastore {ss.name}: {e}"}]
        
        memory_content = ""
        memory_instructions = ""
        if owner_db_user.memory_enabled:
            memories = db.query(UserMemory).filter(UserMemory.owner_user_id == owner_db_user.id).order_by(UserMemory.created_at.asc()).all()
            if memories:
                memory_text = "\n".join([f"[Memory #{idx+1}] {m.title}: {m.content}" for idx, m in enumerate(memories)])
                memory_content = f"\n## Long-Term Memory Bank\nYou have access to the following memories:\n{memory_text}\n"
            else:
                memory_content = "\n## Long-Term Memory Bank\nThe memory bank is currently empty.\n"
            
            memory_instructions += "\n## Memory Management\n"
            memory_instructions += "You have access to a long-term memory bank (provided in context).\n"
            memory_instructions += "You can manage memories using these tags in your response. **Refer to memories by their Index number (#1, #2...)**.\n"
            memory_instructions += "- Add: `<new_memory>concise info</new_memory>`\n"
            memory_instructions += "- Update: `<update_memory:INDEX>new content</update_memory:INDEX>` (e.g. `<update_memory:1>...`)\n"
            memory_instructions += "- Delete: `<delete_memory:INDEX></delete_memory:INDEX>` (e.g. `<delete_memory:1></delete_memory:1>`)\n"
            
            if owner_db_user.auto_memory_enabled:
                memory_instructions += "IMPORTANT: You should automatically save important user details and preferences to memory using `<new_memory>` tags when appropriate, without being explicitly asked.\n"

        discussion_obj.memory = memory_content

        rag_datastore_ids = (discussion_obj.metadata or {}).get('rag_datastore_ids', [])
        
        use_rag = {}
        for ds_id in rag_datastore_ids:
            ss = get_safe_store_instance(owner_username, ds_id, db)
            if ss:
                use_rag[ss.name] = {"name": ss.name, "description": ss.description, "callable": partial(query_rag_callback, ss=ss)}

        db_pers = db.query(DBPersonality).filter(DBPersonality.id == owner_db_user.active_personality_id).first() if owner_db_user.active_personality_id else None
        
        dynamic_preamble = ""
        preamble_parts = []
        if owner_db_user.share_dynamic_info_with_llm:
            now = datetime.now()
            date_str = now.strftime("%A, %B %d, %Y")
            time_str = now.strftime("%H:%M:%S")
            preamble_parts.append(f"- Current Date: {date_str}")
            preamble_parts.append(f"- Current Time: {time_str}")
            if owner_db_user.tell_llm_os:
                preamble_parts.append(f"- User's OS: {platform.system()}")

        if owner_db_user.fun_mode:
            preamble_parts.append("- Fun Mode is active. Be humorous, witty, and engaging. Tell jokes and use emojis.")

        if owner_db_user.force_ai_response_language:
            if owner_db_user.ai_response_language and owner_db_user.ai_response_language.lower() != 'auto':
                preamble_parts.append(f"- IMPORTANT: You must respond exclusively in the following language: {owner_db_user.ai_response_language}")
            else:
                preamble_parts.append("- IMPORTANT: You must respond exclusively in the same language as the user's prompt.")
        
        if owner_db_user.share_personal_info_with_llm and owner_db_user.user_personal_info:
             preamble_parts.append(f"## User Personal Information:\n{owner_db_user.user_personal_info}")

        if owner_db_user.image_annotation_enabled:
            preamble_parts.append(
                "## Image Annotation Instructions\n"
                "When you are asked to annotate, highlight, or segment an object in an image, you MUST use the `<annotate>` tag. "
                "The tag must contain a JSON list of annotation objects. Each object must have a `label` and a shape. "
                "Supported shapes are `box`, `polygon`, and `point`.\n"
                "- `box`: A list of four numbers [x_min, y_min, x_max, y_max] for a bounding box.\n"
                "- `polygon`: A list of points, e.g., [[x1, y1], [x2, y2], ...], for irregular shapes.\n"
                "- `point`: A list of two numbers [x, y] for a single keypoint.\n"
                "All coordinates must be relative (from 0.0 to 1.0).\n"
                "Optionally, include a `display` object with `border_color` (hex) and `fill_opacity` (0.0-1.0).\n"
                "After the `<annotate>` block, you MUST provide a natural language description of your annotations.\n"
                "Example:\n"
                "<annotate>\n"
                "[\n"
                "  {\"box\": [0.25, 0.3, 0.75, 0.8], \"label\": \"cat\", \"display\": {\"border_color\": \"#FF0000\", \"fill_opacity\": 0.1}},\n"
                "  {\"point\": [0.5, 0.5], \"label\": \"cat_nose\"},\n"
                "  {\"polygon\": [[0.1, 0.1], [0.2, 0.1], [0.15, 0.2]], \"label\": \"cat_ear\"}\n"
                "]\n"
                "</annotate>\n"
                "Here is the annotation highlighting the cat, its nose, and one ear."
            )

        if owner_db_user.image_generation_enabled:
            preamble_parts.append(
                "## Image Generation Instructions\n"
                "To generate an image, use the tag `<generate_image width=\"W\" height=\"H\" n=\"N\">prompt</generate_image>`.\n"
                "- `width` (optional): Image width in pixels (e.g., 1024, 512).\n"
                "- `height` (optional): Image height in pixels (e.g., 1024, 768).\n"
                "- `n` (optional): Number of variants to generate (max 10).\n"
                "Example: `<generate_image width=\"1216\" height=\"832\" n=\"2\">A majestic lion in the savannah at sunset, photorealistic style</generate_image>`"
            )
            
            # --- NEW: Slide Generation Instruction ---
            preamble_parts.append(
                "## Slide Show Generation Instructions\n"
                "To generate a coherent set of slides (images) for a presentation, use the `<generate_slides>` tag.\n"
                "Inside this tag, provide a list of `<Slide>` tags, each containing a description of the slide's visual content.\n"
                "Attributes `width` and `height` can be set on the parent tag (default 1024x768).\n"
                "Example:\n"
                "<generate_slides width=\"1280\" height=\"720\">\n"
                "  <Slide>Title slide: A futuristic coffee shop robot, cinematic style</Slide>\n"
                "  <Slide>A diagram of the robot's internal components</Slide>\n"
                "  <Slide>Customers enjoying coffee served by the robot</Slide>\n"
                "</generate_slides>"
            )

        if owner_db_user.image_editing_enabled:
            preamble_parts.append(
                "## Image Editing Instructions\n"
                "You can edit images present in the discussion history.\n"
                "Use the tag `<edit_image source_index=\"-1\" strength=\"0.8\">instruction/prompt</edit_image>`\n"
                "- `source_index` (optional): Index of the image to edit relative to the end of the history. -1 is the last image, -2 is the one before, etc. Default: -1.\n"
                "- `strength` (optional): 0.0 to 1.0. How much to change the original image. Higher values mean more changes. Default: 0.75.\n"
                "- `width`/`height` (optional): Output dimensions. If omitted, preserves source dimensions."
            )

        if getattr(owner_db_user, 'note_generation_enabled', False):
            preamble_parts.append(
                "## Note Generation Instructions\n"
                "To create a note, output a code block with the language `note`. The content inside the block will be the note's body.\n"
                "Example:\n"
                "```note\n"
                "# Note title\n"
                "Structured markdown formatted note information depending on the user's request.\n"
                "You are encouraged to use tables, lists, sections, equations ...\n"
                "If you need to show code, use code environments with mandatory code language specifier.\n"
                "```"
            )

        if memory_instructions:
            preamble_parts.append(memory_instructions)

        if preamble_parts:
            dynamic_preamble = "## Dynamic Information\n" + "\n".join(preamble_parts) + "\n\n"

        system_prompt_text = db_pers.prompt_text if db_pers else "You are a helpful AI assistant."
        
        user_data_zone = owner_db_user.data_zone or ""
        now = datetime.now()
        username_to_use = owner_db_user.preferred_name if owner_db_user.preferred_name else current_user.username
        
        replacements = {
            "{{date}}": now.strftime("%Y-%m-%d"),
            "{{time}}": now.strftime("%H:%M:%S"),
            "{{datetime}}": now.strftime("%Y-%m-%d %H:%M:%S"),
            "{{user_name}}": username_to_use,
        }
        processed_user_data_zone = user_data_zone
        for placeholder, value in replacements.items():
            processed_user_data_zone = processed_user_data_zone.replace(placeholder, value)
            
        discussion_obj.user_data_zone = processed_user_data_zone

        use_mcps_from_discussion = (discussion_obj.metadata or {}).get('active_tools', [])
        use_mcps_from_personality = db_pers.active_mcps if db_pers and db_pers.active_mcps else []
        combined_mcps = list(set(use_mcps_from_discussion + use_mcps_from_personality))

        data_source_runtime = None
        if db_pers:
            if db_pers.data_source_type == "raw_text":
                data_source_runtime = db_pers.data_source
            elif db_pers.data_source_type == "datastore" and db_pers.data_source:
                def query_personality_datastore(query: str) -> str:
                    ds_id = db_pers.data_source
                    ds = get_safe_store_instance(owner_username, ds_id, db)
                    if not ds: return f"Error: Personality datastore '{ds_id}' not found or inaccessible."
                    try:
                        results = ds.query(query, top_k=owner_db_user.rag_top_k or 10)
                        return "\n".join([chunk.get("chunk_text", "") for chunk in results])
                    except Exception as e:
                        return f"Error querying personality datastore: {e}"
                data_source_runtime = query_personality_datastore

        active_personality = LollmsPersonality(
            name=db_pers.name if db_pers else "Generic Assistant",
            author=db_pers.author if db_pers else "System",
            category=db_pers.category if db_pers else "Default",
            description=db_pers.description if db_pers else "A generic, helpful assistant.",
            system_prompt=dynamic_preamble + system_prompt_text,
            script=db_pers.script_code if db_pers else None,
            active_mcps=db_pers.active_mcps or [] if db_pers else [],
            data_source=data_source_runtime
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
                        if start_time:
                            ttft = (first_chunk_time - start_time) * 1000
                            payload = {"type": "ttft", "content": round(ttft, 2)}
                            main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(jsonable_encoder(payload)) + "\n")

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
                        MSG_TYPE.MSG_TYPE_ERROR: {"type": "error", "content": chunk},
                        MSG_TYPE.MSG_TYPE_SOURCES_LIST: {"type": "sources", "content": chunk}
                    }
                    
                    payload = payload_map.get(msg_type)
                    if payload:
                        if payload['type']!="chunk":
                            all_events.append(payload)
                        json_compatible_payload = jsonable_encoder(payload)
                        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(json_compatible_payload) + "\n")
                    return True

                try:
                    # Sanitize active discussion images to remove data:image... prefixes
                    active_discussion_images_raw = [
                        _sanitize_b64(img['data']) for img in discussion_obj.get_discussion_images() 
                        if img.get('active', True)
                    ]
                    
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
                                b64_data = base64.b64encode((assets_path / persistent_filename).read_bytes()).decode('utf-8')
                                images_for_message.append(b64_data)

                    all_input_images = images_for_message # Fix: Do not append discussion images to prompt. They are part of system context via export.

                    # --- RESIZE AND COMPRESS LOGIC ---
                    # Check user settings for max dimensions
                    max_w = owner_db_user.max_image_width if owner_db_user.max_image_width is not None else -1
                    max_h = owner_db_user.max_image_height if owner_db_user.max_image_height is not None else -1
                    
                    # Apply resizing and compression
                    if all_input_images:
                        resized_images = []
                        for img_b64 in all_input_images:
                            resized_images.append(resize_base64_image(img_b64, max_w, max_h))
                        all_input_images = resized_images
                    # -------------------------

                    # --- Google Search "Agent" Loop ---
                    # If web search is enabled, we need to check if the AI wants to use it before final generation.
                    # This logic assumes "one-shot" tool usage (decide -> search -> answer), which is simpler than a full loop.
                    
                    search_context = ""
                    search_sources_list = []
                    
                    if web_search_enabled and owner_db_user.google_api_key and owner_db_user.google_cse_id:
                        # 1. Ask LLM if it needs to search
                        pre_flight_prompt = f"The user asked: \"{prompt}\".\nDo you need to search the internet for current information to answer this?\nReply with JSON: {{ \"search\": true/false, \"query\": \"search terms\" }}"
                        
                        try:
                            # Use a separate non-streaming call for decision
                            # Note: This adds latency.
                            decision_text = lc.generate_text(pre_flight_prompt, max_new_tokens=100, temperature=0.0)
                            try:
                                # Extract JSON
                                json_match = re.search(r'\{.*\}', decision_text, re.DOTALL)
                                if json_match:
                                    decision = json.loads(json_match.group(0))
                                    
                                    if decision.get("search"):
                                        query = decision.get("query")
                                        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "info", "content": f"Searching web for: {query}"}) + "\n")
                                        
                                        # Perform Search
                                        results = perform_google_search(query, owner_db_user.google_api_key, owner_db_user.google_cse_id)
                                        
                                        if results:
                                            # Optional: Deep Analysis (Scraping)
                                            scraped_content = []
                                            if owner_db_user.web_search_deep_analysis:
                                                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "info", "content": "Analyzing search results..."}) + "\n")
                                                scraper = ScrapeMaster()
                                                for res in results[:2]: # Limit deep read to top 2
                                                    try:
                                                        content = scraper.scrape(res['link'])
                                                        if content:
                                                            scraped_content.append(f"Source: {res['link']}\nContent: {content[:1500]}...") # Limit content size
                                                    except: pass
                                            
                                            # Construct Context
                                            search_context = "### Web Search Results:\n"
                                            for res in results:
                                                search_context += f"- Title: {res['title']}\n  Link: {res['link']}\n  Snippet: {res['snippet']}\n\n"
                                                search_sources_list.append({"title": res['title'], "content": res['snippet'], "source": res['link'], "score": 100})
                                            
                                            if scraped_content:
                                                search_context += "\n### Deep Content Analysis:\n" + "\n\n".join(scraped_content)
                                                
                                            # Send sources to frontend immediately
                                            main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "sources", "content": search_sources_list}) + "\n")

                                        else:
                                            search_context = "Web search returned no results."
                                    else:
                                        # AI decided no search needed
                                        pass
                                else:
                                    # Fallback if JSON parse fails
                                    pass
                            except Exception as e:
                                print(f"Search decision parse error: {e}")
                        except Exception as e:
                            print(f"Pre-flight search check failed: {e}")
                    
                    # Augment prompt if search context exists
                    final_user_message = prompt
                    if search_context:
                        final_user_message = f"{prompt}\n\n[Context from Web Search]:\n{search_context}\n\n[Instruction]: Answer the user's question using the provided search context. Cite sources where appropriate."

                    # FIX: Pass add_user_message=not is_resend to prevent duplication on regeneration
                    # FIX: Pass generation_tip_id which was set correctly above
                    result = discussion_obj.chat(
                        branch_tip_id= parent_message_id if is_resend else None, # This is the parent to branch from
                        user_message=final_user_message, 
                        personality=active_personality, 
                        use_mcps=combined_mcps, 
                        use_data_store=use_rag, 
                        images=all_input_images, 
                        streaming_callback=llm_callback, 
                        max_reasoning_steps=owner_db_user.rag_n_hops,
                        rag_top_k=owner_db_user.rag_top_k, 
                        rag_min_similarity_percent=owner_db_user.rag_min_sim_percent,
                        debug=SERVER_CONFIG.get("debug", False),
                        user_name=current_user.username,
                        user_icon=current_user.icon,
                        add_user_message=not is_resend, 

                        think=owner_db_user.reasoning_activation,
                        reasoning_effort=owner_db_user.reasoning_effort,
                        reasooning_summary=owner_db_user.reasoning_summary
                    )
                    
                    end_time = time.time()
                    
                    ai_message_obj = result.get('ai_message')
                    if ai_message_obj:
                        # Append search sources to message metadata so they persist
                        if search_sources_list:
                            existing_sources = (ai_message_obj.metadata or {}).get('sources', [])
                            ai_message_obj.set_metadata_item('sources', existing_sources + search_sources_list, discussion_obj)

                        if owner_db_user.memory_enabled:
                             # ... memory processing ...
                            db_mem = next(get_db())
                            try:
                                processed_content, memory_action = process_memory_tags(ai_message_obj.content, owner_db_user.id, db_mem)
                                if memory_action:
                                    manager.send_personal_message_sync({
                                        "type": "notification",
                                        "data": {"message": "Memorizing...", "type": "info", "duration": 3000}
                                    }, current_user.id)
                                    
                                    manager.send_personal_message_sync({
                                        "type": "data_zone_processed",
                                        "data": {"discussion_id": discussion_id, "zone": "memory"}
                                    }, current_user.id)

                                if processed_content != ai_message_obj.content:
                                    ai_message_obj.content = processed_content
                            except Exception as e:
                                print(f"Error processing memory tags: {e}")
                            finally:
                                db_mem.close()

                        # --- IMAGE GENERATION ---
                        if owner_db_user.image_generation_enabled:
                            db_img = next(get_db())
                            try:
                                # Standard Image Generation
                                processed_text, generated_images, generation_meta, generated_groups = process_image_generation_tags(ai_message_obj.content, owner_db_user, db_img, discussion_obj, main_loop, stream_queue)
                                
                                # Slides Generation
                                processed_text_slides, slide_task_id = process_slide_generation_tags(processed_text, owner_db_user, db_img, discussion_obj, ai_message_obj.id, main_loop, stream_queue)
                                
                                if generated_images:
                                    current_images = ai_message_obj.images or []
                                    start_index_for_meta = len(current_images)
                                    
                                    # Use add_image_pack method to handle image appending and metadata
                                    should_activate = owner_db_user.activate_generated_images
                                    if hasattr(ai_message_obj, 'add_image_pack'):
                                        # Use the first prompt from the generation batch as title for the pack
                                        title = generation_meta[0]['prompt'] if generation_meta else "Generated Images"
                                        ai_message_obj.add_image_pack(generated_images, group_type="generated", active_by_default=should_activate, title=title)
                                    
                                    if processed_text_slides != ai_message_obj.content:
                                        ai_message_obj.content = processed_text_slides
                                    
                                    existing_metadata = ai_message_obj.metadata or {}
                                    existing_gen_infos = existing_metadata.get("generated_image_infos", [])
                                    
                                    for info in generation_meta:
                                        info['index'] += start_index_for_meta
                                        existing_gen_infos.append(info)
                                    
                                    ai_message_obj.set_metadata_item("generated_image_infos", existing_gen_infos, discussion_obj)
                                    
                                    discussion_obj.commit()

                                    manager.send_personal_message_sync({
                                        "type": "notification",
                                        "data": {"message": f"Generated {len(generated_images)} image(s).", "type": "success", "duration": 3000}
                                    }, current_user.id)
                                    
                                if slide_task_id:
                                    # Attach task ID to message metadata so UI can show progress bar
                                    ai_message_obj.set_metadata_item('active_task_id', slide_task_id, discussion_obj)
                                    discussion_obj.commit()
                                
                                # Similar logic for image generation: keep tags?
                                # User: "First, for image generation, image edit and slide show generation, ALWAYS keep the original tag in the message."
                                # So we skip updating content with processed_text too.
                                pass 

                            except Exception as e:
                                print(f"Error processing image tags: {e}")
                                trace_exception(e)
                            finally:
                                db_img.close()
                                
                        # --- IMAGE EDITING ---
                        if owner_db_user.image_editing_enabled:
                            db_img_edit = next(get_db())
                            try:
                                processed_text, edited_images, edit_meta, edit_groups = process_image_editing_tags(
                                    ai_message_obj.content, 
                                    owner_db_user, 
                                    db_img_edit, 
                                    discussion_obj, 
                                    main_loop, 
                                    stream_queue,
                                    current_turn_images=all_input_images
                                )
                                if edited_images:
                                    current_images = ai_message_obj.images or []
                                    start_index = len(current_images)
                                    
                                    if hasattr(ai_message_obj, 'add_image_pack'):
                                        title = edit_meta[0]['prompt'] if edit_meta else "Edited Images"
                                        ai_message_obj.add_image_pack(edited_images, group_type="generated", active_by_default=True, title=title)
                                    
                                    # Skip content update to keep tags
                                    # if processed_text != ai_message_obj.content:
                                    #    ai_message_obj.content = processed_text

                                    existing_metadata = ai_message_obj.metadata or {}
                                    existing_gen_infos = existing_metadata.get("generated_image_infos", [])
                                    
                                    for info in edit_meta:
                                        info['index'] += start_index
                                        existing_gen_infos.append(info)
                                    
                                    ai_message_obj.set_metadata_item("generated_image_infos", existing_gen_infos, discussion_obj)

                                    discussion_obj.commit()

                                    manager.send_personal_message_sync({
                                        "type": "notification",
                                        "data": {"message": f"Edited {len(edited_images)} image(s).", "type": "success", "duration": 3000}
                                    }, current_user.id)
                                
                                # Skip content update to keep tags
                                    
                            except Exception as e:
                                print(f"Error processing image editing tags: {e}")
                                trace_exception(e)
                            finally:
                                db_img_edit.close()

                        ttft = (first_chunk_time - start_time) * 1000 if first_chunk_time else 0
                        total_tokens = ai_message_obj.tokens or 0
                        
                        tps = 0
                        if total_tokens > 1 and first_chunk_time and end_time > first_chunk_time:
                            streaming_time = end_time - first_chunk_time
                            tps = (total_tokens - 1) / streaming_time if streaming_time > 0 else 0

                        ai_message_obj.set_metadata_item('ttft', round(ttft, 2), discussion_obj)
                        ai_message_obj.set_metadata_item('tps', round(tps, 2), discussion_obj)
                        ai_message_obj.set_metadata_item('events', all_events, discussion_obj)

                    def lollms_message_to_output(msg):
                        if not msg: return None
                        
                        full_image_refs = []
                        if hasattr(msg, 'images') and msg.images:
                            full_image_refs = [ f"data:image/png;base64,{img}" for img in msg.images or []]

                        msg_metadata_raw = msg.metadata
                        if isinstance(msg_metadata_raw, str):
                            try: msg_metadata = json.loads(msg_metadata_raw) if msg_metadata_raw else {}
                            except json.JSONDecodeError: msg_metadata = {}
                        else:
                            msg_metadata = msg_metadata_raw or {}

                        sources = getattr(msg, 'sources', None)
                        if sources is None:
                            sources = msg_metadata.get('sources')
                        
                        if sources:
                            msg_metadata['sources'] = sources

                        return {
                            "id": msg.id, "sender": msg.sender, "content": msg.content,
                            "created_at": msg.created_at, "parent_message_id": msg.parent_id,
                            "discussion_id": msg.discussion_id, "metadata": msg_metadata,
                            "tokens": msg.tokens, "sender_type": msg.sender_type,
                            "binding_name": msg.binding_name, "model_name": msg.model_name,
                            "sources": sources,
                            "image_references": full_image_refs,
                            "active_images": getattr(msg, 'active_images', [])
                        }
                    
                    final_messages_payload = {
                        'user_message': lollms_message_to_output(result.get('user_message')),
                        'ai_message': lollms_message_to_output(result.get('ai_message'))
                    }
                    
                    new_title = None
                    if current_user.auto_title and (discussion_obj.metadata is None or discussion_obj.metadata.get('title',"").startswith("New Discussion")):
                         # ... title gen ...
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
                    
                    db_for_broadcast = next(get_db())
                    try:
                        shared_links = db_for_broadcast.query(DBSharedDiscussionLink).filter(DBSharedDiscussionLink.discussion_id == discussion_id).all()
                        if shared_links:
                            participant_ids = {link.owner_user_id for link in shared_links}
                            participant_ids.update({link.shared_with_user_id for link in shared_links})
                            
                            payload = {"type": "discussion_updated", "data": {"discussion_id": discussion_id, "sender_username": current_user.username}}
                            for user_id in participant_ids:
                                if user_id != current_user.id:
                                    manager.send_personal_message_sync(payload, user_id)
                    finally:
                        db_for_broadcast.close()

                except Exception as e:
                    trace_exception(e)
                    err_msg = f"LLM generation failed: {e}"
                    if main_loop.is_running():
                        main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_msg}) + "\n")
                finally:
                    if current_user.username in user_sessions and "active_generation_control" in user_sessions[current_user.username]:
                        user_sessions[current_user.username]["active_generation_control"].pop(discussion_id, None)
                    if main_loop.is_running():
                        main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)
            
            threading.Thread(target=blocking_call, daemon=True).start()        
            while True:
                item = await stream_queue.get()
                if item is None: break
                yield item

        return StreamingResponse(
            stream_generator(), 
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )    
    
    
    @router.post("/{discussion_id}/stop_generation", status_code=200)
    async def stop_discussion_generation(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user)):
        username = current_user.username
        stop_event = user_sessions.get(username, {}).get("active_generation_control", {}).get(discussion_id)
        if stop_event and isinstance(stop_event, threading.Event):
            stop_event.set()
            return {"message": "Stop signal sent."}
        else:
            raise HTTPException(status_code=404, detail="No active generation found for this discussion.")
