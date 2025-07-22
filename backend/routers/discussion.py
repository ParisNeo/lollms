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
# Third-Party Imports
from fastapi import (
    HTTPException, Depends, Form,
    APIRouter, Query, BackgroundTasks)
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
    LollmsClient, MSG_TYPE, LollmsDiscussion, LollmsPersonality, LollmsMessage
)
from ascii_colors import ASCIIColors, trace_exception
# Local Application Imports
from backend.db import get_db
from backend.db.models.user import User as DBUser, UserStarredDiscussion, UserMessageGrade
from backend.db.models.personality import Personality as DBPersonality
from backend.models import (
    UserAuthDetails, DiscussionInfo, DiscussionTitleUpdate,
    DiscussionRagDatastoreUpdate, MessageOutput, MessageContentUpdate,
    MessageGradeUpdate, DiscussionBranchSwitchRequest, DiscussionSendRequest,
    DiscussionExportRequest, ExportData, DiscussionImportRequest, ContextStatusResponse,
    DiscussionDataZoneUpdate
)
from backend.session import (
    get_current_active_user, get_user_lollms_client,
    get_user_temp_uploads_path, get_user_discussion_assets_path,
    user_sessions, get_safe_store_instance
)
from backend.discussion import get_user_discussion_manager, get_user_discussion
from backend.config import APP_VERSION, SERVER_CONFIG

# safe_store is needed for RAG callbacks
try:
    import safe_store
except ImportError:
    safe_store = None

# Define the lock at the module level
message_grade_lock = threading.Lock()

discussion_router = APIRouter(prefix="/api/discussions", tags=["Discussions"])

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
        infos.append(DiscussionInfo(
            id=disc_id,
            title=metadata.get('title', f"Discussion {disc_id[:8]}"),
            is_starred=(disc_id in starred_ids),
            rag_datastore_ids=metadata.get('rag_datastore_ids'),
            active_tools=metadata.get('active_tools', []),
            active_branch_id=disc_data.get('active_branch_id'),
            created_at=disc_data.get('created_at'),
            last_activity_at=disc_data.get('updated_at')
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

@discussion_router.get("/{discussion_id}/data_zone", response_model=Dict[str, str])
def get_discussion_data_zone(
    discussion_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    discussion = get_user_discussion(current_user.username, discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    return {"content": discussion.data_zone or ""}

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
        discussion.data_zone = payload.content
        discussion.commit()
        return {"message": "Data Zone updated successfully."}
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to update Data Zone: {e}")


@discussion_router.post("/prune", status_code=200)
async def prune_empty_discussions(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    Deletes all discussions for the current user that are empty or contain only one message.
    """
    username = current_user.username
    dm = get_user_discussion_manager(username)
    all_discs_infos = dm.list_discussions()
    deleted_count = 0
    discussions_to_delete = []

    for disc_info in all_discs_infos:
        discussion_id = disc_info['id']
        try:
            # get_user_discussion will use the correct client settings internally
            discussion = get_user_discussion(username, discussion_id)
            if discussion and len(discussion.messages) <= 1:
                discussions_to_delete.append(discussion_id)
        except Exception as e:
            print(f"Could not process discussion {discussion_id} for pruning: {e}")

    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    for discussion_id in discussions_to_delete:
        try:
            dm.delete_discussion(discussion_id)
            assets_path = get_user_discussion_assets_path(username) / discussion_id
            if assets_path.exists() and assets_path.is_dir():
                background_tasks.add_task(shutil.rmtree, assets_path, ignore_errors=True)
            
            db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).delete(synchronize_session=False)
            db.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id).delete(synchronize_session=False)

            deleted_count += 1
        except Exception as e:
            print(f"Failed to delete discussion {discussion_id} during prune: {e}")
            db.rollback()
    
    if deleted_count > 0:
        db.commit()

    return {"message": f"Successfully pruned {deleted_count} empty or single-message discussions.", "deleted_count": deleted_count}


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

    messages_output = []
    for msg in messages_in_branch:
        images_list = msg.images or []
        if isinstance(images_list, str):
            try: images_list = json.loads(images_list)
            except json.JSONDecodeError: images_list = []
        if not isinstance(images_list, list): images_list = []
        full_image_refs = [ f"data:image/png;base64,{img}" for img in images_list]
        
        msg_metadata_raw = msg.metadata
        if isinstance(msg_metadata_raw, str):
            try: msg_metadata = json.loads(msg_metadata_raw) if msg_metadata_raw else {}
            except json.JSONDecodeError: msg_metadata = {}
        else:
            msg_metadata = msg_metadata_raw or {}

        messages_output.append(
            MessageOutput(
                id=msg.id, sender=msg.sender, sender_type=msg.sender_type, content=msg.content,
                parent_message_id=msg.parent_id, binding_name=msg.binding_name, model_name=msg.model_name,
                token_count=msg.tokens, sources=msg_metadata.get('sources'), events=msg_metadata.get('events'),
                image_references=full_image_refs, user_grade=user_grades.get(msg.id, 0),
                created_at=msg.created_at, branch_id=branch_tip_to_load, branches=None
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
        return ContextStatusResponse(current_tokens=status['current_tokens'], max_tokens=status['max_tokens'])
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
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    
    # The LollmsClient is now correctly attached to the discussion object
    lc = discussion_obj.lollms_client
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
    rag_datastore_ids = (discussion_obj.metadata or {}).get('rag_datastore_ids', [])
    
    use_rag = {}
    for ds_id in rag_datastore_ids:
        ss = get_safe_store_instance(username, ds_id, db)
        if ss:
            use_rag[ss.name] = {"name": ss.name, "description": ss.description, "callable": partial(query_rag_callback, ss=ss)}

    db_pers = db.query(DBPersonality).filter(DBPersonality.id == db_user.active_personality_id).first() if db_user.active_personality_id else None
    
    # --- REFINED: Placeholder replacement and data zone combination ---
    user_scratchpad = db_user.scratchpad or ""
    discussion_scratchpad_original = discussion_obj.data_zone or "" # Use the original, un-replaced version
    now = datetime.datetime.now()
    replacements = {
        "{{date}}": now.strftime("%Y-%m-%d"),
        "{{time}}": now.strftime("%H:%M:%S"),
        "{{datetime}}": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
    # Apply replacements to a copy
    processed_user_scratchpad = user_scratchpad
    for placeholder, value in replacements.items():
        processed_user_scratchpad = processed_user_scratchpad.replace(placeholder, value)

    # Combine scratchpads with clear separation for the context
    combined_data_zone_parts = []
    if processed_user_scratchpad:
        combined_data_zone_parts.append(f"### User Scratchpad\n{processed_user_scratchpad}")
    if discussion_scratchpad_original:
        combined_data_zone_parts.append(f"### Discussion Scratchpad\n{discussion_scratchpad_original}")
    
    temp_data_zone_for_generation = "\n\n".join(combined_data_zone_parts).strip()


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
    
    # Correctly combine data_zone content for the client library
    # The library expects data_source on the personality object to be the primary driver
    # for additional context. We will append our combined scratchpad to it.
    if data_source_runtime:
        if isinstance(data_source_runtime, str):
            active_personality.data_source = f"{data_source_runtime}\n\n{temp_data_zone_for_generation}".strip()
        # If it's a callable, we can't easily combine it. The scratchpad will be the main data source.
        # A more advanced lollms-client version might handle multiple sources better.
        # For now, we prioritize the scratchpad if a callable is also present.
        else:
             active_personality.data_source = temp_data_zone_for_generation
    else:
        active_personality.data_source = temp_data_zone_for_generation
    
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
async def update_discussion_message(discussion_id: str, message_id: str, payload: MessageContentUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail="Discussion not found.")
    branch = discussion_obj.get_branch(discussion_obj.active_branch_id)
    target_message = next((msg for msg in branch if msg.id == message_id), None)
    if not target_message: raise HTTPException(status_code=404, detail="Message not found in active branch.")
    target_message.content = payload.content
    discussion_obj.commit()
    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    grade = db.query(UserMessageGrade.grade).filter_by(user_id=db_user.id, discussion_id=discussion_id, message_id=message_id).scalar() or 0
    full_image_refs = [ f"data:image/png;base64,{img}" for img in target_message.images or []]

    msg_metadata = target_message.metadata or {}
    return MessageOutput(
        id=target_message.id, sender=target_message.sender, sender_type=target_message.sender_type, content=target_message.content,
        parent_message_id=target_message.parent_id, binding_name=target_message.binding_name, model_name=target_message.model_name,
        token_count=target_message.tokens, sources=msg_metadata.get('sources'), events=msg_metadata.get('events'),
        image_references=full_image_refs, user_grade=grade, created_at=target_message.created_at,
        branch_id=discussion_obj.active_branch_id, branches=None
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