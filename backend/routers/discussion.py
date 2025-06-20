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
from ascii_colors import trace_exception

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
    LollmsClient, MSG_TYPE, LollmsDiscussion, LollmsPersonality
)

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
            rag_datastore_id=metadata.get('rag_datastore_id'),
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
        rag_datastore_id=None,
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
        rag_datastore_id=metadata.get('rag_datastore_id'),
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
        rag_datastore_id=discussion_obj.metadata.get('rag_datastore_id'),
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
        rag_datastore_id=metadata.get('rag_datastore_id'),
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
        rag_datastore_id=metadata.get('rag_datastore_id'),
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
        rag_datastore_id=discussion_obj.metadata.get('rag_datastore_ids'), # Return the list
        active_branch_id=discussion_obj.active_branch_id,
        created_at=discussion_obj.created_at,
        last_activity_at=discussion_obj.updated_at
    )


@discussion_router.post("/{discussion_id}/chat")
async def chat_in_existing_discussion(discussion_id: str, prompt: str = Form(...), image_server_paths_json: str = Form("[]"), is_resend: bool = Form(False), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> StreamingResponse:
    
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    # --- RAG Callback now handles multiple datastores ---
    rag_datastore_ids = (discussion_obj.metadata or {}).get('rag_datastore_ids', [])
    def query_rag_callback(query: str) -> Optional[str]:
        if not safe_store:
            return None

        # Get the list of datastore IDs from metadata
        if not rag_datastore_ids:
            return None

        all_results = []
        print(f"RAG Querying across {len(rag_datastore_ids)} datastores.")

        for ds_id in rag_datastore_ids:
            try:
                ss = get_safe_store_instance(username, ds_id, db)
                results = ss.query(
                    query,
                    vectorizer_name=db_user.safe_store_vectorizer,
                    top_k=db_user.rag_top_k
                )
                # Add the source datastore ID to each result for context
                for r in results:
                    r['datastore_id'] = ds_id
                all_results.extend(results)
            except Exception as e:
                trace_exception(e)
                # Optionally add an error message to the context
                return f"Error during RAG query on datastore {ds_id}: {e}"

        # De-duplicate results based on chunk_text to avoid redundancy
        unique_chunks = {}
        for r in all_results:
            if r['chunk_text'] not in unique_chunks:
                unique_chunks[r['chunk_text']] = r

        # Sort all unique results by similarity score, highest first
        sorted_unique_results = sorted(unique_chunks.values(), key=lambda x: x['similarity_percent'], reverse=True)

        # Combine the top results into a single context string
        return "\n---\n".join([r['chunk_text'] for r in sorted_unique_results])
    def create_generic_personality():
        return LollmsPersonality(
            name="Generic Personality",
            author="System",
            category="Default",
            description="A generic personality for default operations.",
            system_prompt="You are a helpful assistant.",
            script="",
            query_rag_callback=query_rag_callback
        )

    # Get the user's Lollms client and database user
    lc = get_user_lollms_client(username)
    db_user = db.query(DBUser).filter(DBUser.username == username).one()

    # Initialize active_personality to None
    active_personality = None

    # Check if there is an active personality in the database
    if db_user.active_personality_id:
        db_pers = db.query(DBPersonality).filter(DBPersonality.id == db_user.active_personality_id).first()
        if db_pers:
            active_personality = LollmsPersonality(
                name=db_pers.name,
                author=db_pers.author,
                category=db_pers.category,
                description=db_pers.description,
                system_prompt=db_pers.prompt_text,
                script=db_pers.script_code,
                query_rag_callback=query_rag_callback
            )
        else:
            db_pers = None
            active_personality = create_generic_personality()
    else:
        db_pers = None
        active_personality = create_generic_personality()



    # Use the active or generic personality
    active_personality = LollmsPersonality(
        name=db_pers.name if db_pers else "Generic Personality",
        author=db_pers.author if db_pers else "System",
        category=db_pers.category if db_pers else "Default",
        description=db_pers.description if db_pers else "A generic personality for default operations.",
        system_prompt=db_pers.prompt_text if db_pers else "You are a helpful assistant.",
        script=db_pers.script_code if db_pers else "",
        query_rag_callback=query_rag_callback
    )
        
    main_loop = asyncio.get_event_loop()
    stream_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
    stop_event = threading.Event()
    user_sessions.setdefault(username, {}).setdefault("active_generation_control", {})[discussion_id] = stop_event

    async def stream_generator() -> AsyncGenerator[str, None]:
        def llm_callback(chunk: str, msg_type: MSG_TYPE, params: Optional[Dict] = None, **kwargs) -> bool:
            if stop_event.is_set():
                return False
            payload = {}
            if msg_type == MSG_TYPE.MSG_TYPE_CHUNK:
                payload = {"type": "chunk", "content": chunk}
            elif msg_type == MSG_TYPE.MSG_TYPE_THOUGHT_CHUNK:
                payload = {"type": "thought", "content": chunk}
            elif msg_type == MSG_TYPE.MSG_TYPE_STEP:
                payload = {"type": "step", "content": chunk, "status": "done"}
            elif msg_type == MSG_TYPE.MSG_TYPE_STEP_START:
                payload = {"type": "step_start", "content": chunk, "id": params.get("id"), "status": "pending"}
            elif msg_type == MSG_TYPE.MSG_TYPE_STEP_END:
                payload = {"type": "step_end", "content": chunk, "id": params.get("id"), "status": "done"}
            elif msg_type == MSG_TYPE.MSG_TYPE_EXCEPTION:
                payload = {"type": "error", "content": f"LLM Error: {chunk}"}
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(payload) + "\n")
                return False
            else:
                return True
            main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps(payload) + "\n")
            return True

        def blocking_call():
            try:
                # Handle image uploads and convert them to the format LollmsMessage expects
                images_for_message = []
                image_server_paths = json.loads(image_server_paths_json)
                if image_server_paths:
                    temp_path = get_user_temp_uploads_path(username)
                    assets_path = get_user_discussion_assets_path(username) / discussion_id
                    assets_path.mkdir(parents=True, exist_ok=True)
                    for temp_rel_path in image_server_paths:
                        filename = Path(temp_rel_path).name
                        if (temp_path/filename).exists():
                            persistent_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
                            shutil.move(str(temp_path/filename), str(assets_path/persistent_filename))
                            b64_data = base64.b64encode((assets_path/persistent_filename).read_bytes()).decode('utf-8')
                            images_for_message.append({
                                "type": "base64", 
                                "data": b64_data, 
                                "path": persistent_filename
                            })
                if rag_datastore_ids and len(rag_datastore_ids)>0:
                    final_content = lc.generate_text_with_rag(
                                        prompt=discussion_obj.format_discussion(lc.default_ctx_size),
                                        system_prompt=discussion_obj.system_prompt,
                                        temperature=current_user.llm_temperature, top_k=current_user.llm_top_k, top_p=current_user.llm_top_p,
                                        repeat_penalty=current_user.llm_repeat_penalty, repeat_last_n=current_user.llm_repeat_last_n,
                                        ctx_size =current_user.llm_ctx_size  if current_user.llm_ctx_size>0 else None,
                                        rag_query_function=query_rag_callback, rag_vectorizer_name=current_user.safe_store_vectorizer,
                                        max_rag_hops=current_user.rag_n_hops if current_user.rag_n_hops else 1,
                                        rag_top_k=current_user.rag_top_k if current_user.rag_top_k  else 10,
                                        rag_min_similarity_percent=current_user.rag_min_sim_percent if current_user.rag_min_sim_percent  else 0,
                                        stream=True, streaming_callback=llm_callback,
                                    )
                    sources = [{"document":Path(r["document"]).name,"similarity":r["similarity"],"content":r["content"]} for r in final_content.get("all_retrieved_sources", [])]      
                    ai_message_obj = discussion_obj.add_message(
                        sender="assistant", sender_type="assistant", content=final_content,
                        raw_content=final_raw_response, thoughts="", tokens=token_count,
                        binding_name=self.lollmsClient.binding.binding_name,
                        model_name=self.lollmsClient.binding.model_name,
                        generation_speed=tok_per_sec
                    )              
                if is_resend:
                    # For regeneration, the user message with images already exists.
                    # We just call regenerate_branch.
                    discussion_obj.regenerate_branch(
                        personality=active_personality, # Pass personality here too
                        streaming_callback=llm_callback
                    )
                else:
                    discussion_obj.add_message(
                        sender="user", 
                        sender_type="user", 
                        content=prompt,
                        images=images_for_message if images_for_message else None
                    )
                    
                    # 2. Now, call chat with an empty prompt. It will generate a response
                    # to the last message we just added. We no longer pass the images argument here.
                    discussion_obj.chat(
                        user_message="", # The prompt is already in the history.
                        personality=active_personality,
                        streaming_callback=llm_callback,
                    )
                

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
