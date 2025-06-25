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
    HTTPException, Depends, Request, File, UploadFile, Form,
    APIRouter, Query, BackgroundTasks)
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
from backend.database_setup import (
    User as DBUser, UserStarredDiscussion, UserMessageGrade, get_db,
    Personality as DBPersonality
)
from backend.models import (
    UserAuthDetails, DiscussionInfo, DiscussionTitleUpdate,
    DiscussionRagDatastoreUpdate, MessageOutput, MessageContentUpdate,
    MessageGradeUpdate, DiscussionBranchSwitchRequest, DiscussionSendRequest,
    DiscussionExportRequest, ExportData, DiscussionImportRequest
)
from backend.session import (
    get_current_active_user, get_user_lollms_client,
    get_user_temp_uploads_path, get_user_discussion_assets_path,
    user_sessions, get_safe_store_instance
)
from backend.discussion import get_user_discussion_manager, get_user_discussion
from backend.config import APP_VERSION

# safe_store is needed for RAG callbacks
try:
    import safe_store
except ImportError:
    safe_store = None

# Define the lock at the module level
message_grade_lock = threading.Lock()

discussion_router = APIRouter(prefix="/api/discussions", tags=["Discussions"])

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
        active_branch_id=None,
        created_at=discussion_obj.created_at,
        last_activity_at=discussion_obj.updated_at
    )

@discussion_router.get("/{discussion_id}", response_model=List[MessageOutput])
async def get_messages_for_discussion(discussion_id: str, branch_id: Optional[str] = Query(None), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[MessageOutput]:
    username = current_user.username
    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    branch_tip_to_load = branch_id or discussion_obj.active_branch_id
    messages_in_branch = discussion_obj.get_branch(branch_tip_to_load)

    user_grades = {g.message_id: g.grade for g in db.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id).all()}

    messages_output = []
    for msg in messages_in_branch:
        full_image_refs = [f"/user_assets/{username}/{discussion_id}/{img['path']}" for img in (msg.images or []) if 'path' in img]
        msg_metadata = msg.metadata or {}
        messages_output.append(
            MessageOutput(
                id=msg.id,
                sender=msg.sender,
                sender_type=msg.sender_type,
                content=msg.content,
                parent_message_id=msg.parent_id,
                binding_name=msg.binding_name,
                model_name=msg.model_name,
                token_count=msg.tokens,
                sources=msg_metadata.get('sources'),
                steps=msg_metadata.get('steps'),
                image_references=full_image_refs,
                user_grade=user_grades.get(msg.id, 0),
                created_at=msg.created_at,
                branch_id=branch_tip_to_load,
                branches=None
            )
        )
    return messages_output

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

    if discussion_obj.metadata is None:
        discussion_obj.metadata = {}
    discussion_obj.metadata['title'] = title_update.title
    discussion_obj.commit()

    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    is_starred = db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).first() is not None
    return DiscussionInfo(
        id=discussion_id,
        title=title_update.title,
        is_starred=is_starred,
        rag_datastore_ids=discussion_obj.metadata.get('rag_datastore_ids'),
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
        active_branch_id=discussion_obj.active_branch_id,
        created_at=discussion_obj.created_at,
        last_activity_at=discussion_obj.updated_at
    )

# --- FIX: Replace the existing update_discussion_rag_datastore endpoint ---
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

    # Validate all provided datastore IDs
    if update_payload.rag_datastore_ids:
        for ds_id in update_payload.rag_datastore_ids:
            try:
                # This helper validates existence and permissions
                get_safe_store_instance(username, ds_id, db)
            except HTTPException as e:
                raise HTTPException(status_code=400, detail=f"Invalid or inaccessible RAG datastore ID: {ds_id} ({e.detail})")

    # Store the list of datastore IDs in the discussion's metadata
    if discussion_obj.metadata is None:
        discussion_obj.metadata = {}
    discussion_obj.metadata['rag_datastore_ids'] = update_payload.rag_datastore_ids
    discussion_obj.commit()

    user_db = db.query(DBUser).filter(DBUser.username == username).one()
    is_starred = db.query(UserStarredDiscussion).filter_by(user_id=user_db.id, discussion_id=discussion_id).first() is not None

    return DiscussionInfo(
        id=discussion_id,
        title=discussion_obj.metadata.get('title', "Untitled"),
        is_starred=is_starred,
        rag_datastore_ids=discussion_obj.metadata.get('rag_datastore_ids'),
        active_branch_id=discussion_obj.active_branch_id,
        created_at=discussion_obj.created_at,
        last_activity_at=discussion_obj.updated_at
    )

def lollms_message_to_output(
    msg: LollmsMessage,
    username: str,
    discussion_id: str,
    branch_id: str,
    user_grade: int = 0
) -> MessageOutput:
    full_image_refs = [f"/user_assets/{username}/{discussion_id}/{img['path']}" for img in (msg.images or []) if 'path' in img]
    msg_metadata = msg.metadata or {}
    return MessageOutput(
        id=msg.id,
        sender=msg.sender,
        sender_type=msg.sender_type,
        content=msg.content,
        parent_message_id=msg.parent_id,
        binding_name=msg.binding_name,
        model_name=msg.model_name,
        token_count=msg.tokens,
        sources=msg_metadata.get('sources'),
        steps=msg_metadata.get('steps'),
        image_references=full_image_refs,
        user_grade=user_grade,
        created_at=msg.created_at,
        branch_id=branch_id,
        branches=None
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
    """Handles a chat request within an existing discussion, supporting streaming and agentic capabilities.

    This endpoint is the primary interaction point for a user's conversation.
    It manages standard chat messages, message regeneration, and complex agentic
    turns involving tools (MCP) and retrieval-augmented generation (RAG).

    The function operates asynchronously, using a queue and a separate thread
    to handle the potentially long-running blocking calls to the LLM, ensuring
    the server remains responsive.

    It streams results back to the client using a server-sent events (SSE) like
    format (newline-delimited JSON), providing real-time updates:
    - `chunk`: A piece of the final answer text.
    - `thought`: A segment of the agent's internal reasoning.
    - `step_start`/`step_end`: Notifications about the agent's high-level actions.
    - `finalize`: A final message containing the complete, updated user and AI
                  message objects, including all agentic metadata (scratchpad,
                  tool calls, sources).

    Args:
        discussion_id: The ID of the discussion to interact with.
        prompt: The user's text prompt.
        image_server_paths_json: A JSON string array of temporary paths for
                                 user-uploaded images.
        is_resend: A boolean flag indicating if this is a request to regenerate
                   the last AI response.
        current_user: The authenticated user object, injected by FastAPI's
                      dependency system.
        db: The database session, injected by FastAPI's dependency system.

    Returns:
        A StreamingResponse that sends newline-delimited JSON objects to the client,
        enabling a real-time conversational experience.
    """
    # --- 1. Setup and Authorization ---
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id, db)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    # --- 2. Configure Agentic Capabilities (RAG & MCP) ---
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
                if "similarity_percent" in entry:
                    revamped_entry["similarity_percent"]=entry["similarity_percent"]
                revamped_chunks.append(revamped_entry)
            return revamped_chunks
        except Exception as e:
            trace_exception(e)
            return [{"error": f"Error during RAG query on datastore {ss.id}: {e}"}]

    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    rag_datastore_ids = (discussion_obj.metadata or {}).get('rag_datastore_ids', [])
    use_mcps = (discussion_obj.metadata or {}).get('active_tools', [])
    use_rag = {}
    for ds_id in rag_datastore_ids:
        ss = get_safe_store_instance(username, ds_id, db)
        if ss:
            use_rag[ss.name] = {"name": ss.name, "description": ss.description, "callable": partial(query_rag_callback, ss=ss)}

    # --- 3. Setup Personality and LLM Client ---
    lc = get_user_lollms_client(username)
    active_personality = None
    db_pers = None
    if db_user.active_personality_id:
        # Try to find the user's active personality in the database
        db_pers = db.query(DBPersonality).filter(DBPersonality.id == db_user.active_personality_id).first()

    if db_pers:
        # If found, create a LollmsPersonality instance from the DB record
        active_personality = LollmsPersonality(
            name=db_pers.name,
            author=db_pers.author,
            category=db_pers.category,
            description=db_pers.description,
            system_prompt=db_pers.prompt_text,
            script=db_pers.script_code,
            # query_rag_callback can be set here if personalities have their own RAG
            query_rag_callback=None
        )
    else:
        # If no active personality is set, or if it wasn't found, create a generic one
        active_personality = LollmsPersonality(
            name="Generic Assistant",
            author="System",
            category="Default",
            description="A generic, helpful assistant.",
            system_prompt="You are a helpful AI assistant, ready to answer questions and follow instructions.",
            script="",
            query_rag_callback=None
        )
    # --- 4. Asynchronous Streaming Setup ---
    main_loop = asyncio.get_event_loop()
    stream_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
    stop_event = threading.Event()
    user_sessions.setdefault(username, {}).setdefault("active_generation_control", {})[discussion_id] = stop_event
    async def stream_generator() -> AsyncGenerator[str, None]:
        # Callback function passed to the LLM/agent to stream data back
        def llm_callback(
            chunk: str,
            msg_type: MSG_TYPE,
            params: Optional[Dict] = None,
            **kwargs
        ) -> bool:
            """
            This function is called by the LollmsClient/LollmsDiscussion from a
            separate thread. It formats the received data into a JSON payload
            and puts it onto the asyncio queue to be sent to the client.

            Args:
                chunk: The main text content of the event.
                msg_type: An enum indicating the type of the message.
                params: A dictionary containing metadata about the event,
                        such as step IDs, types, and results.

            Returns:
                False if the generation should be stopped, True otherwise.
            """
            # 1. Handle Stop Event: Immediately stop if requested by the client.
            if stop_event.is_set():
                return False
            
            payload = None
            params = params or {}

            # 2. Dispatcher: Format payload based on message type.
            # This now handles all the rich event types from our advanced agent.
            match msg_type:
                case MSG_TYPE.MSG_TYPE_CHUNK:
                    # A piece of the final answer text.
                    payload = {"type": "chunk", "content": chunk}
                case MSG_TYPE.MSG_TYPE_INFO if params.get("type") == "thought":
                    # An internal thought or reasoning step from the agent.
                    payload = {"type": "thought", "content": chunk}

                case MSG_TYPE.MSG_TYPE_STEP_START:
                    # The beginning of a stateful, long-running step.
                    # Includes the unique ID for frontend correlation.
                    payload = {
                        "type": "step_start",
                        "content": chunk,  # The human-readable description
                        "id": params["id"]     # Contains the unique 'id' and other metadata
                    }
                
                case MSG_TYPE.MSG_TYPE_STEP_END:
                    # The end of a stateful, long-running step.
                    # Includes the same unique ID as the corresponding start event.
                    payload = {
                        "type": "step_end",
                        "content": chunk,    # The same description as the start event
                        "id": params["id"],     # Contains the unique 'id' and other metadata
                        "status": "done"
                    }
                
                case MSG_TYPE.MSG_TYPE_STEP:
                    # A simple, instantaneous step that doesn't have a start/end duration.
                    payload = {"type": "step", "content": chunk, "data": params}

                case MSG_TYPE.MSG_TYPE_EXCEPTION:
                    # An error occurred during generation.
                    payload = {"type": "error", "content": f"LLM Error: {chunk}"}
                    # Put the error on the queue and signal to stop generation.
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(payload) + "\n")
                    return False
                
                case _:
                    # For any other message types we don't explicitly handle,
                    # we do nothing to keep the client-side stream clean.
                    return True

            # 3. Queue the Payload: Safely put the formatted payload onto the queue.
            if payload:
                # jsonable_encoder is used here to be safe, although for these
                # simple payloads, it might not be strictly necessary. It's good practice.
                json_compatible_payload = jsonable_encoder(payload)
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(json_compatible_payload) + "\n")
            
            return True

        # Function to run the blocking LLM call in a separate thread
        def blocking_call():
            try:
                # --- Image Handling ---
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

                # --- Main Call to Discussion Logic ---
                if is_resend:
                    result = discussion_obj.regenerate_branch(
                        personality=active_personality,
                        use_mcps=use_mcps,
                        use_data_store=use_rag,
                        streaming_callback=llm_callback
                    )
                else:
                    result = discussion_obj.chat(
                        user_message=prompt,
                        personality=active_personality,
                        use_mcps=use_mcps,
                        use_data_store=use_rag,
                        images=images_for_message,
                        streaming_callback=llm_callback,
                        rag_top_k=db_user.rag_top_k,
                        rag_min_similarity_percent=db_user.rag_min_sim_percent
                    )
                
                # --- Finalization Event ---
                def lollms_message_to_output(msg):
                    # In a real app, this would return an instance of a Pydantic model
                    return {
                        "id": msg.id, "sender": msg.sender, "content": msg.content,
                        "created_at": msg.created_at, "parent_id": msg.parent_id,
                        "discussion_id": msg.discussion_id, "metadata": msg.metadata,
                        "scratchpad": msg.scratchpad
                    }
                
                final_messages_payload = {
                    'ai_message': lollms_message_to_output(result['ai_message'])
                }
                if 'user_message' in result:
                    final_messages_payload['user_message'] = lollms_message_to_output(result['user_message'])
                
                # Use jsonable_encoder to safely serialize the entire payload
                json_compatible_event = jsonable_encoder(
                    {"type": "finalize", "data": final_messages_payload}
                )
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(json_compatible_event) + "\n")

            except Exception as e:
                trace_exception(e)
                err_msg = f"LLM generation failed: {e}"
                if main_loop.is_running():
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_msg}) + "\n")
            finally:
                # Cleanup
                if username in user_sessions and "active_generation_control" in user_sessions[username]:
                    user_sessions[username]["active_generation_control"].pop(discussion_id, None)
                if main_loop.is_running():
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)
        
        # --- Start and Stream ---
        threading.Thread(target=blocking_call, daemon=True).start()
        while True:
            item = await stream_queue.get()
            if item is None:
                break
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
    if not discussion_obj:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    with message_grade_lock:
        grade = db.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id, message_id=message_id).first()
        if grade:
            grade.grade += grade_update.change
        else:
            grade = UserMessageGrade(user_id=db_user.id, discussion_id=discussion_id, message_id=message_id, grade=grade_update.change)
            db.add(grade)
        db.commit()
        db.refresh(grade)
        current_grade = grade.grade

    branch = discussion_obj.get_branch(discussion_obj.active_branch_id)
    target_message = next((msg for msg in branch if msg.id == message_id), None)
    if not target_message:
        raise HTTPException(status_code=404, detail="Message not found in active branch.")

    full_image_refs = [f"/user_assets/{username}/{discussion_id}/{img['path']}" for img in (target_message.images or []) if 'path' in img]
    msg_metadata = target_message.metadata or {}
    return MessageOutput(
        id=target_message.id,
        sender=target_message.sender,
        sender_type=target_message.sender_type,
        content=target_message.content,
        parent_message_id=target_message.parent_id,
        binding_name=target_message.binding_name,
        model_name=target_message.model_name,
        token_count=target_message.tokens,
        sources=msg_metadata.get('sources'),
        steps=msg_metadata.get('steps'),
        image_references=full_image_refs,
        user_grade=current_grade,
        created_at=target_message.created_at,
        branch_id=discussion_obj.active_branch_id,
        branches=None
    )

@discussion_router.put("/{discussion_id}/messages/{message_id}", response_model=MessageOutput)
async def update_discussion_message(discussion_id: str, message_id: str, payload: MessageContentUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    branch = discussion_obj.get_branch(discussion_obj.active_branch_id)
    target_message = next((msg for msg in branch if msg.id == message_id), None)
    if not target_message:
        raise HTTPException(status_code=404, detail="Message not found in active branch.")

    target_message.content = payload.content
    discussion_obj.commit()

    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    grade = db.query(UserMessageGrade.grade).filter_by(user_id=db_user.id, discussion_id=discussion_id, message_id=message_id).scalar() or 0
    full_image_refs = [f"/user_assets/{username}/{discussion_id}/{img['path']}" for img in (target_message.images or []) if 'path' in img]
    msg_metadata = target_message.metadata or {}
    return MessageOutput(
        id=target_message.id,
        sender=target_message.sender,
        sender_type=target_message.sender_type,
        content=target_message.content,
        parent_message_id=target_message.parent_id,
        binding_name=target_message.binding_name,
        model_name=target_message.model_name,
        token_count=target_message.tokens,
        sources=msg_metadata.get('sources'),
        steps=msg_metadata.get('steps'),
        image_references=full_image_refs,
        user_grade=grade,
        created_at=target_message.created_at,
        branch_id=discussion_obj.active_branch_id,
        branches=None
    )

@discussion_router.delete("/{discussion_id}/messages/{message_id}", status_code=200)
async def delete_discussion_message(discussion_id: str, message_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    try:
        discussion_obj.delete_branch(message_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    db_user = db.query(DBUser).filter(DBUser.username == username).one()
    db.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id, message_id=message_id).delete(synchronize_session=False)
    db.commit()
    return {"message": "Message and its branch deleted successfully."}
