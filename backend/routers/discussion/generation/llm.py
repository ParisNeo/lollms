# backend/routers/discussion/generation/llm.py
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
from backend.db.models.discussion import SharedDiscussionLink as DBSharedDiscussionLink
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
                             get_safe_store_instance,
                             get_user_discussion_assets_path,
                             get_user_lollms_client,
                             get_user_temp_uploads_path, user_sessions)
from backend.task_manager import task_manager, Task
from backend.ws_manager import manager
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request
from lollms_client import MSG_TYPE, LollmsPersonality
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request

from backend.db import get_db



def build_llm_generation_router(router: APIRouter):
    @router.post("/{discussion_id}/chat")
    async def chat_in_existing_discussion(
        discussion_id: str,
        prompt: str = Form(...),
        image_server_paths_json: str = Form("[]"),
        is_resend: bool = Form(False),
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

        discussion_obj.memory = "\n".join(["---"+m.title+"---\n"+m.content+"\n------" for m in owner_db_user.memories]) if owner_db_user and owner_db_user.memories else ""
        rag_datastore_ids = (discussion_obj.metadata or {}).get('rag_datastore_ids', [])
        
        use_rag = {}
        for ds_id in rag_datastore_ids:
            ss = get_safe_store_instance(owner_username, ds_id, db)
            if ss:
                use_rag[ss.name] = {"name": ss.name, "description": ss.description, "callable": partial(query_rag_callback, ss=ss)}

        db_pers = db.query(DBPersonality).filter(DBPersonality.id == owner_db_user.active_personality_id).first() if owner_db_user.active_personality_id else None
        
        user_data_zone = owner_db_user.data_zone or ""
        now = datetime.now()
        replacements = {
            "{{date}}": now.strftime("%Y-%m-%d"),
            "{{time}}": now.strftime("%H:%M:%S"),
            "{{datetime}}": now.strftime("%Y-%m-%d %H:%M:%S"),
            "{{user_name}}": current_user.username,
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
                        results = ds.query(query, top_k=owner_db_user.rag_top_k)
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
        user_sessions.setdefault(current_user.username, {}).setdefault("active_generation_control", {})[discussion_id] = stop_event

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

                    if is_resend:
                        result = discussion_obj.regenerate_branch(
                            personality=active_personality, 
                            use_mcps=combined_mcps, 
                            use_data_store=use_rag, 
                            streaming_callback=llm_callback,
                            user_name=current_user.username,
                            user_icon=current_user.icon
                        )
                    else:
                        result = discussion_obj.chat(
                            user_message=prompt, 
                            personality=active_personality, 
                            use_mcps=combined_mcps,
                            use_data_store=use_rag, 
                            images=images_for_message,
                            streaming_callback=llm_callback, 
                            max_reasoning_steps=owner_db_user.rag_n_hops,
                            rag_top_k=owner_db_user.rag_top_k, 
                            rag_min_similarity_percent=owner_db_user.rag_min_sim_percent,
                            debug=SERVER_CONFIG.get("debug", False),
                            user_name=current_user.username,
                            user_icon=current_user.icon
                        )
                    
                    ai_message_obj = result.get('ai_message')
                    if ai_message_obj:
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

                        return {
                            "id": msg.id, "sender": msg.sender, "content": msg.content,
                            "created_at": msg.created_at, "parent_message_id": msg.parent_id,
                            "discussion_id": msg.discussion_id, "metadata": msg.metadata,
                            "tokens": msg.tokens, "sender_type": msg.sender_type,
                            "binding_name": msg.binding_name, "model_name": msg.model_name,
                            "sources": sources,
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

        return StreamingResponse(stream_generator(), media_type="application/x-ndjson")
    @router.post("/{discussion_id}/stop_generation", status_code=200)
    async def stop_discussion_generation(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user)):
        username = current_user.username
        stop_event = user_sessions.get(username, {}).get("active_generation_control", {}).get(discussion_id)
        if stop_event and isinstance(stop_event, threading.Event):
            stop_event.set()
            return {"message": "Stop signal sent."}
        else:
            raise HTTPException(status_code=404, detail="No active generation found for this discussion.")