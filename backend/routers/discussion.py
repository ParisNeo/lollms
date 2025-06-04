# Standard Library Imports
import os
import shutil
import uuid
import json
from pathlib import Path
from typing import List, Dict, Optional, Any, cast, Union, Tuple, AsyncGenerator
import datetime
import asyncio
import threading
import traceback
import io
from ascii_colors import trace_exception, ASCIIColors

# Third-Party Imports
import toml
import yaml
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
    File,
    UploadFile,
    Form,
    APIRouter,
    Response,
    Query,
    BackgroundTasks
)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import (
    HTMLResponse,
    StreamingResponse,
    JSONResponse,
    FileResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, constr, field_validator, validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import (
    or_, and_ # Add this line
)
from dataclasses import dataclass, field as dataclass_field
from werkzeug.utils import secure_filename
from pydantic import BaseModel, Field, constr, field_validator, validator # Ensure these are imported
import datetime # Ensure datetime is imported

from backend.database_setup import Personality as DBPersonality # Add this import at the top of main.py

# Local Application Imports
from backend.database_setup import (
    User as DBUser,
    UserStarredDiscussion,
    UserMessageGrade,
    FriendshipStatus,Friendship, 
    DataStore as DBDataStore,
    SharedDataStoreLink as DBSharedDataStoreLink,
    init_database,
    get_db,
    hash_password,
    DATABASE_URL_CONFIG_KEY,
)
from lollms_client import (
    LollmsClient,
    MSG_TYPE,
    LollmsDiscussion as LollmsClientDiscussion,
    ELF_COMPLETION_FORMAT, # For client params
)

# safe_store is expected to be installed
try:
    import safe_store
    from safe_store import (
        LogLevel as SafeStoreLogLevel,
    )
except ImportError:
    print(
        "WARNING: safe_store library not found. RAG features will be disabled. Install with: pip install safe_store[all]"
    )
    safe_store = None
    SafeStoreLogLevel = None

# --- Pydantic Models for API ---
from backend.models import (
UserLLMParams,
UserAuthDetails,
UserCreateAdmin,
UserPasswordResetAdmin,UserPasswordChange,
UserPublic,
DiscussionInfo,
DiscussionTitleUpdate,
DiscussionRagDatastoreUpdate,MessageOutput,
MessageContentUpdate,
MessageGradeUpdate,
SafeStoreDocumentInfo,
DiscussionExportRequest,
ExportData,
DiscussionImportRequest,
DiscussionSendRequest,
DataStoreBase,
DataStoreCreate,
DataStorePublic,
DataStoreShareRequest,
PersonalityBase,
PersonalityCreate,
PersonalityUpdate,
PersonalityPublic,
UserUpdate,
FriendshipBase,
FriendRequestCreate,
FriendshipAction,
FriendPublic,
FriendshipRequestPublic,
PersonalitySendRequest,

DirectMessagePublic,
DirectMessageCreate
)
from backend.config import (
    TEMP_UPLOADS_DIR_NAME
)
from backend.session import (
    get_current_active_user,
    get_current_admin_user,
    get_current_db_user_from_token,
    get_datastore_db_path,
    get_db, get_safe_store_instance,
    get_user_data_root, get_user_datastore_root_path,
    get_user_discussion, get_user_discussion_assets_path,
    get_user_discussion_path,
    get_user_lollms_client,
    get_user_temp_uploads_path,
    _load_user_discussions,
    save_user_discussion,
    
    message_grade_lock,
    user_sessions,
    )
from backend.config import (LOLLMS_CLIENT_DEFAULTS, SAFE_STORE_DEFAULTS)
from backend.discussion import (AppLollmsDiscussion)

security = HTTPBasic()


# --- Discussion API ---
discussion_router = APIRouter(prefix="/api/discussions", tags=["Discussions"])

@discussion_router.get("", response_model=List[DiscussionInfo])
async def list_all_discussions(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[DiscussionInfo]:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found in DB.")
    
    session_discussions = user_sessions[username].get("discussions", {})
    starred_ids = {star.discussion_id for star in db.query(UserStarredDiscussion.discussion_id).filter(UserStarredDiscussion.user_id == user_id).all()}
    
    infos = []
    for disc_id, disc_obj in session_discussions.items():
        infos.append(DiscussionInfo(
            id=disc_id, title=disc_obj.title, 
            is_starred=(disc_id in starred_ids),
            rag_datastore_id=disc_obj.rag_datastore_id
        ))
    return infos

@discussion_router.post("", response_model=DiscussionInfo, status_code=201)
async def create_new_discussion(current_user: UserAuthDetails = Depends(get_current_active_user)) -> DiscussionInfo:
    username = current_user.username
    discussion_id = str(uuid.uuid4())
    discussion_obj = get_user_discussion(username, discussion_id, create_if_missing=True)
    if not discussion_obj: raise HTTPException(status_code=500, detail="Failed to create new discussion.")
    return DiscussionInfo(id=discussion_id, title=discussion_obj.title, is_starred=False, rag_datastore_id=None)

@discussion_router.get("/{discussion_id}", response_model=List[MessageOutput])
async def get_messages_for_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[MessageOutput]:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    user_grades_for_discussion = {
        grade.message_id: grade.grade
        for grade in db.query(UserMessageGrade.message_id, UserMessageGrade.grade)
        .filter(UserMessageGrade.user_id == user_id, UserMessageGrade.discussion_id == discussion_id).all()
    }
    messages_output = []
    for msg in discussion_obj.messages:
        # Construct full URL for image assets if any
        full_image_refs = []
        if msg.image_references:
            for ref in msg.image_references:
                # Assuming ref is like "discussion_assets_dir_name/discussion_id/image_filename"
                # or just "image_filename" if stored directly under discussion_assets/discussion_id
                # Client-side, it will request /user_assets/<username>/<discussion_id>/<filename>
                asset_filename = Path(ref).name # Get the filename part
                full_image_refs.append(f"/user_assets/{username}/{discussion_obj.discussion_id}/{asset_filename}")

        messages_output.append(
            MessageOutput(
                id=msg.id, sender=msg.sender, content=msg.content,
                parent_message_id=msg.parent_message_id, binding_name=msg.binding_name,
                model_name=msg.model_name, token_count=msg.token_count,
                sources = msg.sources,
                image_references=full_image_refs, # Use full URLs for client
                user_grade=user_grades_for_discussion.get(msg.id, 0)
            )
        )
    return messages_output

@discussion_router.put("/{discussion_id}/title", response_model=DiscussionInfo)
async def update_discussion_title(discussion_id: str, title_update: DiscussionTitleUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DiscussionInfo:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    discussion_obj.title = title_update.title
    save_user_discussion(username, discussion_id, discussion_obj)
    is_starred = db.query(UserStarredDiscussion).filter_by(user_id=user_id, discussion_id=discussion_id).first() is not None
    return DiscussionInfo(id=discussion_id, title=discussion_obj.title, is_starred=is_starred, rag_datastore_id=discussion_obj.rag_datastore_id)

@discussion_router.put("/{discussion_id}/rag_datastore", response_model=DiscussionInfo)
async def update_discussion_rag_datastore(discussion_id: str, update_payload: DiscussionRagDatastoreUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DiscussionInfo:
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    if update_payload.rag_datastore_id: # Validate datastore existence and user access
        try: get_safe_store_instance(username, update_payload.rag_datastore_id, db)
        except HTTPException as e:
            if e.status_code == 404 or e.status_code == 403:
                raise HTTPException(status_code=400, detail=f"Invalid or inaccessible RAG datastore ID: {update_payload.rag_datastore_id}")
            raise e # Re-raise other HTTPExceptions
        except Exception as e_val:
             raise HTTPException(status_code=500, detail=f"Error validating RAG datastore: {str(e_val)}")


    discussion_obj.rag_datastore_id = update_payload.rag_datastore_id
    save_user_discussion(username, discussion_id, discussion_obj)
    
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found in DB for star check.") # Should not happen if active_user works
    is_starred = db.query(UserStarredDiscussion).filter_by(user_id=user_id, discussion_id=discussion_id).first() is not None
    
    return DiscussionInfo(id=discussion_id, title=discussion_obj.title, is_starred=is_starred, rag_datastore_id=discussion_obj.rag_datastore_id)


@discussion_router.delete("/{discussion_id}", status_code=200)
async def delete_specific_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()) -> Dict[str, str]:
    username = current_user.username
    try: uuid.UUID(discussion_id)
    except ValueError: raise HTTPException(status_code=400, detail="Invalid discussion ID format.")
    session = user_sessions[username]
    discussion_exists_in_session = discussion_id in session.get("discussions", {})
    safe_filename = secure_filename(f"{discussion_id}.yaml")
    file_path = get_user_discussion_path(username) / safe_filename
    discussion_exists_on_disk = file_path.exists()
    if not discussion_exists_in_session and not discussion_exists_on_disk:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    session.get("discussions", {}).pop(discussion_id, None)
    session.get("discussion_titles", {}).pop(discussion_id, None)
    if discussion_exists_on_disk:
        try: file_path.unlink()
        except OSError as e:
            if file_path.exists(): print(f"ERROR: Failed to delete discussion file {file_path}: {e}")
    # Delete associated assets
    assets_path = get_user_discussion_assets_path(username) / discussion_id
    if assets_path.exists() and assets_path.is_dir():
        background_tasks.add_task(shutil.rmtree, assets_path, ignore_errors=True)

    try:
        db.query(UserStarredDiscussion).filter_by(discussion_id=discussion_id).delete()
        db.query(UserMessageGrade).filter_by(discussion_id=discussion_id).delete()
        db.commit()
    except Exception as e_db:
        db.rollback()
        print(f"ERROR: Failed to delete DB entries for discussion {discussion_id}: {e_db}")
    return {"message": f"Discussion '{discussion_id}' deleted successfully."}

@discussion_router.post("/{discussion_id}/star", status_code=201)
async def star_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    if not get_user_discussion(username, discussion_id): raise HTTPException(status_code=404, detail="Discussion not found.")
    if db.query(UserStarredDiscussion).filter_by(user_id=user_id, discussion_id=discussion_id).first():
        return {"message": "Discussion already starred."}
    new_star = UserStarredDiscussion(user_id=user_id, discussion_id=discussion_id)
    try: db.add(new_star); db.commit(); return {"message": "Discussion starred successfully."}
    except IntegrityError: db.rollback(); return {"message": "Discussion already starred (race condition handled)."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"Database error: {e}")

@discussion_router.delete("/{discussion_id}/star", status_code=200)
async def unstar_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    star_to_delete = db.query(UserStarredDiscussion).filter_by(user_id=user_id, discussion_id=discussion_id).first()
    if not star_to_delete: return {"message": "Discussion was not starred."}
    try: db.delete(star_to_delete); db.commit(); return {"message": "Discussion unstarred successfully."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"Database error: {e}")

@discussion_router.post("/{discussion_id}/chat")
async def chat_in_existing_discussion(
    discussion_id: str, prompt: str = Form(...),
    image_server_paths_json: str = Form("[]"), # JSON string of server_paths from upload
    use_rag: bool = Form(False),
    rag_datastore_id: Optional[str] = Form(None), # Datastore to use if RAG is active
    parent_message_id: Optional[str] = Form(None),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()
) -> StreamingResponse:
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    lc = get_user_lollms_client(username)
    
    # Process and persist uploaded images
    final_image_references_for_message: List[str] = []
    llm_image_paths: List[str] = [] # Absolute paths for LollmsClient

    try: image_server_paths = json.loads(image_server_paths_json)
    except json.JSONDecodeError: raise HTTPException(status_code=400, detail="Invalid image_server_paths_json format.")

    if image_server_paths:
        user_temp_uploads_path = get_user_temp_uploads_path(username)
        discussion_assets_path = get_user_discussion_assets_path(username) / discussion_id
        discussion_assets_path.mkdir(parents=True, exist_ok=True)

        for temp_rel_path in image_server_paths:
            if not temp_rel_path.startswith(TEMP_UPLOADS_DIR_NAME + "/"):
                print(f"WARNING: Invalid temporary image path format: {temp_rel_path}")
                continue
            
            image_filename = Path(temp_rel_path).name
            temp_abs_path = user_temp_uploads_path / image_filename
            
            if temp_abs_path.is_file():
                persistent_filename = f"{uuid.uuid4().hex[:8]}_{image_filename}"
                persistent_abs_path = discussion_assets_path / persistent_filename
                try:
                    shutil.move(str(temp_abs_path), str(persistent_abs_path))
                    final_image_references_for_message.append(persistent_filename)
                    llm_image_paths.append(str(persistent_abs_path))
                except Exception as e_move:
                    print(f"ERROR moving image {temp_abs_path} to {persistent_abs_path}: {e_move}")
            else:
                print(f"WARNING: Temporary image file not found: {temp_abs_path}")
    
    user_token_count = lc.binding.count_tokens(prompt) if prompt else 0
    discussion_obj.add_message(
        sender=lc.user_name, content=prompt, parent_message_id=parent_message_id,
        token_count=user_token_count, image_references=final_image_references_for_message
    )

    extra_content = ""

    main_loop = asyncio.get_event_loop()
    stream_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

    stop_event = threading.Event()
    shared_state = {
        "accumulated_ai_response": "", 
        "generation_error": None, 
        "final_message_id": None, 
        "binding_name": None, 
        "model_name": None,
        "stop_event": stop_event,
    }

    if username not in user_sessions: user_sessions[username] = {} 
    user_sessions[username].setdefault("active_generation_control", {})[discussion_id] = stop_event

    async def stream_generator() -> AsyncGenerator[str, None]:
        generation_thread: Optional[threading.Thread] = None 
        
        def llm_callback(chunk: str, msg_type: MSG_TYPE, params: Optional[Dict[str, Any]] = None, turn_history: Optional[List] = None) -> bool:
            if shared_state["stop_event"].is_set():
                stop_message_payload = json.dumps({"type": "info", "content": "Generation stopped by user."}) + "\n"
                if main_loop.is_running(): 
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, stop_message_payload)
                else:
                    print(f"WARNING: asyncio loop not running when trying to send stop message for {username}/{discussion_id}")
                print(f"INFO: LLM Callback for {username}/{discussion_id} detected stop signal. Halting generation.")
                return False 

            if msg_type == MSG_TYPE.MSG_TYPE_CHUNK:
                shared_state["accumulated_ai_response"] += chunk
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "chunk", "content": chunk}) + "\n")
            elif msg_type == MSG_TYPE.MSG_TYPE_STEP_START:
                step_type = params.get("type", "step")
                hop = params.get("hop", "")
                info = params.get("query", chunk) if step_type == "rag_query_generation" or step_type == "rag_retrieval" else chunk
                ASCIIColors.yellow(f"\n>> RAG Step Start (Hop {hop}): {step_type} - Info: {str(info)[:100]}...", flush=True)
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "step_update", "content": chunk +"\n"}) + "\n")
            elif msg_type == MSG_TYPE.MSG_TYPE_STEP_END:
                step_type = params.get("type", "step")
                hop = params.get("hop", "")
                num_chunks = params.get("num_chunks", "")
                query = params.get("query", "")
                decision = params.get("decision", "")
                
                info_str = ""
                if step_type == "rag_query_generation" and query: info_str = f"Generated Query: {query}"
                elif step_type == "rag_retrieval": info_str = f"Retrieved {num_chunks} chunks"
                elif step_type == "rag_llm_decision": info_str = f"LLM Decision: {json.dumps(decision)}"
                elif step_type == "final_answer_generation": info_str = "Final answer generation complete."
                else: info_str = chunk
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "step_update", "content": chunk +"\n"}) + "\n")

                ASCIIColors.green(f"\n<< RAG Step End (Hop {hop}): {step_type} - {info_str}", flush=True)

            elif msg_type in (MSG_TYPE.MSG_TYPE_EXCEPTION, MSG_TYPE.MSG_TYPE_EXCEPTION):
                err_content = f"LLM Error: {str(chunk)}"
                shared_state["generation_error"] = err_content
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_content +"\n"}) + "\n")
                return False
            elif msg_type == MSG_TYPE.MSG_TYPE_FULL_INVISIBLE_TO_USER:
                if params and "final_message_id" in params: shared_state["final_message_id"] = params["final_message_id"]
            elif msg_type == MSG_TYPE.MSG_TYPE_FINISHED_MESSAGE: return False
            return True

        try: 
            
            sources =[]
            def blocking_call(rag_datastore_id, sources):
                try:
                    # Fetch active personality prompt from user's session
                    active_personality_prompt_text = user_sessions[username].get("active_personality_prompt")
                    user_puts_thoughts_in_context = user_sessions[username].get("llm_params", {}).get("put_thoughts_in_context", False)

                    shared_state["binding_name"] = lc.binding.binding_name if lc.binding else "unknown_binding"
                    shared_state["model_name"] = lc.binding.model_name if lc.binding and hasattr(lc.binding, "model_name") else user_sessions[username].get("lollms_model_name", "unknown_model")
                    
                    # Prepare the main prompt (history + current user input)
                    main_prompt_content = discussion_obj.prepare_query_for_llm(
                        extra_content # This is the user's current text input, possibly augmented by RAG
                        # max_total_tokens can be passed if needed, or rely on LollmsClient defaults
                    )
                    if not user_puts_thoughts_in_context:
                        main_prompt_content = lc.remove_thinking_blocks(main_prompt_content)
                    

                    if use_rag and safe_store:
                        if not rag_datastore_id:
                            rag_datastore_id = discussion_obj.rag_datastore_id
                            if not rag_datastore_id:
                                # Fallback to user's default datastore is not implemented here,
                                # user_sessions[username].get("active_vectorizer") is actually the default vectorizer name, not datastore_id.
                                # For RAG, a datastore must be selected for the discussion or explicitly passed.
                                print(f"WARNING: RAG requested by {username} but no datastore specified for discussion.")

                        if rag_datastore_id:
                            try:
                                ss = get_safe_store_instance(username, rag_datastore_id, db)
                                # User's default vectorizer from their settings or global default.
                                # This is for querying; documents are added with a specific vectorizer.
                                # SafeStore can query using any vectorizer it has embeddings for.
                                # If not specified, SafeStore might use its own default or the one most docs are vectorized with.
                                # For now, let's rely on SafeStore's internal logic if vectorizer_name is None for query.
                                # Or, use the user's preferred one IF the datastore has it.
                                def rqf(query, vectorizer_name, top_k, min_similarity_percent):
                                    results = ss.query(query, vectorizer_name, top_k, min_similarity_percent)
                                    return [{"file_path":Path(r["file_path"]).name,"similarity_percent":r["similarity_percent"],"chunk_text":r["chunk_text"]} for r in results]
                                active_vectorizer_for_store = user_sessions[username].get("active_vectorizer") # This is the name of vectorizer model, not datastore                    
                                classic_rag_result = lc.generate_text_with_rag(
                                        prompt=main_prompt_content,
                                        system_prompt=active_personality_prompt_text,
                                        rag_query_function=rqf,
                                        rag_vectorizer_name=active_vectorizer_for_store,
                                        # rag_query_text=None, # Will use `prompt` for query
                                        max_rag_hops=current_user.rag_n_hops if current_user.rag_n_hops else 1,
                                        rag_top_k=current_user.rag_top_k if current_user.rag_top_k  else 10, # Get 2 best chunks
                                        rag_min_similarity_percent=current_user.rag_min_sim_percent if current_user.rag_min_sim_percent  else 0,
                                        stream=True,
                                        streaming_callback=llm_callback,
                                    )
                                sources+=[{"document":Path(r["document"]).name,"similarity":r["similarity"],"content":r["content"]} for r in classic_rag_result["all_retrieved_sources"]]

                                print(classic_rag_result["final_answer"])
                            except Exception as ex:
                                trace_exception(ex)
                        else:
                            # Call generate_text with the separate system_prompt parameter
                            lc.generate_text(
                                prompt=main_prompt_content,
                                system_prompt=active_personality_prompt_text, # Pass system prompt here
                                images=llm_image_paths, 
                                stream=True, 
                                streaming_callback=llm_callback,
                                split=True
                                # Other parameters like temperature, top_k, etc., are assumed to be set
                                # on the LollmsClient instance itself or can be overridden here if needed.
                            )

                    else:
                        # Call generate_text with the separate system_prompt parameter
                        lc.generate_text(
                            prompt=main_prompt_content,
                            system_prompt=active_personality_prompt_text, # Pass system prompt here
                            images=llm_image_paths, 
                            stream=True, 
                            streaming_callback=llm_callback,
                            split=True
                            # Other parameters like temperature, top_k, etc., are assumed to be set
                            # on the LollmsClient instance itself or can be overridden here if needed.
                        )
                except Exception as e_gen:
                    err_msg = f"LLM generation failed: {str(e_gen)}"
                    shared_state["generation_error"] = err_msg
                    if main_loop.is_running():
                            main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_msg}) + "\n")
                    traceback.print_exc() 
                finally: 
                    if main_loop.is_running():
                        main_loop.call_soon_threadsafe(stream_queue.put_nowait, None) 
            
            generation_thread = threading.Thread(target=blocking_call, args=[rag_datastore_id, sources], daemon=True)
            generation_thread.start()

            while True:
                item = await stream_queue.get()
                if item is None: stream_queue.task_done(); break
                yield item; stream_queue.task_done()
            
            if generation_thread: generation_thread.join(timeout=10) 

            ai_response_content = shared_state["accumulated_ai_response"]
            ai_token_count = lc.binding.count_tokens(ai_response_content) if ai_response_content else 0
            ai_parent_id = discussion_obj.messages[-1].id if discussion_obj.messages and discussion_obj.messages[-1].sender == lc.user_name else None
            ai_sources = sources
            if ai_response_content and not shared_state["generation_error"]:
                if shared_state["stop_event"].is_set():
                    print(f"INFO: Saving partial AI response for {username}/{discussion_id} as generation was stopped.")
                
                ai_message = discussion_obj.add_message(
                    sender=lc.ai_name, content=ai_response_content, parent_message_id=ai_parent_id,
                    binding_name=shared_state.get("binding_name"), model_name=shared_state.get("model_name"),
                    token_count=ai_token_count,sources=ai_sources
                )
                if shared_state.get("final_message_id"): ai_message.id = shared_state["final_message_id"]
            elif shared_state["generation_error"]:
                 discussion_obj.add_message(sender="system", content=shared_state["generation_error"], parent_message_id=ai_parent_id)
            
            save_user_discussion(username, discussion_id, discussion_obj)

        except Exception as e_outer:
            error_msg = f"Chat stream error: {str(e_outer)}"; traceback.print_exc()
            try: discussion_obj.add_message(sender="system", content=error_msg); save_user_discussion(username, discussion_id, discussion_obj)
            except Exception as save_err: print(f"ERROR: Failed to save discussion after outer stream error: {save_err}")
            yield json.dumps({"type": "error", "content": error_msg}) + "\n"
        finally:
            if username in user_sessions and "active_generation_control" in user_sessions[username]:
                active_gen_control = user_sessions[username]["active_generation_control"]
                if discussion_id in active_gen_control and active_gen_control.get(discussion_id) == stop_event:
                    del active_gen_control[discussion_id]
                if not active_gen_control: 
                    del user_sessions[username]["active_generation_control"]
            
            if generation_thread and generation_thread.is_alive(): 
                print(f"WARNING: LLM gen thread for {username}/{discussion_id} still alive after stream_generator's main loop. Signaling stop forcefully.")
                if not shared_state["stop_event"].is_set():
                    shared_state["stop_event"].set() 
                generation_thread.join(timeout=5) 
                if generation_thread.is_alive():
                    print(f"CRITICAL: LLM gen thread for {username}/{discussion_id} did not terminate after stop signal and extended wait.")

            if image_server_paths:
                user_temp_uploads_path = get_user_temp_uploads_path(username)
                for temp_rel_path in image_server_paths:
                    image_filename = Path(temp_rel_path).name
                    temp_abs_path = user_temp_uploads_path / image_filename
                    if temp_abs_path.exists(): 
                        background_tasks.add_task(temp_abs_path.unlink, missing_ok=True)

    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")

@discussion_router.post("/{discussion_id}/stop_generation", status_code=200)
async def stop_discussion_generation(
    discussion_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> Dict[str, str]:
    username = current_user.username
    
    session_data = user_sessions.get(username)
    if not session_data:
        raise HTTPException(status_code=404, detail="User session not found. Cannot process stop generation request.")

    active_gen_control_map = session_data.get("active_generation_control", {})
    stop_event = active_gen_control_map.get(discussion_id)
    
    if stop_event and isinstance(stop_event, threading.Event):
        if not stop_event.is_set():
            stop_event.set()
            print(f"INFO: Stop signal sent for generation in discussion '{discussion_id}' for user '{username}'.")
            return {"message": "Stop signal sent. Generation will attempt to halt."}
        else:
            print(f"INFO: Stop signal for discussion '{discussion_id}' user '{username}' was already set, or generation is completing.")
            return {"message": "Generation is already stopping or has completed."}
    else:
        print(f"INFO: No active generation found to stop for discussion '{discussion_id}' user '{username}'.")
        raise HTTPException(status_code=404, detail="No active generation found for this discussion, or it has already completed and cleaned up.")

@discussion_router.put("/{discussion_id}/messages/{message_id}/grade", response_model=MessageOutput)
async def grade_discussion_message(discussion_id: str, message_id: str, grade_update: MessageGradeUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> MessageOutput:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail="Discussion not found.")
    target_message = next((msg for msg in discussion_obj.messages if msg.id == message_id), None)
    if not target_message: raise HTTPException(status_code=404, detail="Message not found in discussion.")
    lc = get_user_lollms_client(username)
    if target_message.sender == lc.user_name: raise HTTPException(status_code=400, detail="User messages cannot be graded.")
    with message_grade_lock:
        grade_record = db.query(UserMessageGrade).filter_by(user_id=user_id, discussion_id=discussion_id, message_id=message_id).first()
        if grade_record: grade_record.grade += grade_update.change
        else: grade_record = UserMessageGrade(user_id=user_id, discussion_id=discussion_id, message_id=message_id, grade=grade_update.change); db.add(grade_record)
        try: db.commit(); db.refresh(grade_record); current_user_grade = grade_record.grade
        except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error updating grade: {e}")

    full_image_refs = []
    if target_message.image_references:
        for ref in target_message.image_references:
            asset_filename = Path(ref).name
            full_image_refs.append(f"/user_assets/{username}/{discussion_obj.discussion_id}/{asset_filename}")

    return MessageOutput(
        id=target_message.id, sender=target_message.sender, content=target_message.content,
        parent_message_id=target_message.parent_message_id, binding_name=target_message.binding_name,
        model_name=target_message.model_name, token_count=target_message.token_count,
        image_references=full_image_refs, user_grade=current_user_grade
    )

@discussion_router.put("/{discussion_id}/messages/{message_id}", response_model=MessageOutput)
async def update_discussion_message(discussion_id: str, message_id: str, payload: MessageContentUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> MessageOutput:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj or not discussion_obj.edit_message(message_id, payload.content):
        raise HTTPException(status_code=404, detail="Message or discussion not found.")
    save_user_discussion(username, discussion_id, discussion_obj)
    updated_msg = next((m for m in discussion_obj.messages if m.id == message_id), None)
    if not updated_msg: raise HTTPException(status_code=500, detail="Error retrieving updated message.")
    user_grade = 0
    if user_id:
        grade_val = db.query(UserMessageGrade.grade).filter_by(user_id=user_id, discussion_id=discussion_id, message_id=message_id).scalar()
        if grade_val is not None: user_grade = grade_val

    full_image_refs = []
    if updated_msg.image_references:
        for ref in updated_msg.image_references:
            asset_filename = Path(ref).name
            full_image_refs.append(f"/user_assets/{username}/{discussion_obj.discussion_id}/{asset_filename}")
        
    return MessageOutput(
        id=updated_msg.id, sender=updated_msg.sender, content=updated_msg.content,
        parent_message_id=updated_msg.parent_message_id, binding_name=updated_msg.binding_name,
        model_name=updated_msg.model_name, token_count=updated_msg.token_count,
        image_references=full_image_refs, user_grade=user_grade
    )

@discussion_router.delete("/{discussion_id}/messages/{message_id}", status_code=200)
async def delete_discussion_message(discussion_id: str, message_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail="Discussion not found.")
    
    message_to_delete = next((msg for msg in discussion_obj.messages if msg.id == message_id), None)
    if not message_to_delete: raise HTTPException(status_code=404, detail="Message not found.")

    image_assets_to_delete = []
    if message_to_delete.image_references:
        disc_assets_path = get_user_discussion_assets_path(username) / discussion_id
        for ref in message_to_delete.image_references:
            asset_path = disc_assets_path / Path(ref).name
            if asset_path.is_file(): image_assets_to_delete.append(asset_path)

    if not discussion_obj.delete_message(message_id): 
        raise HTTPException(status_code=404, detail="Message deletion failed internally.") 
    
    save_user_discussion(username, discussion_id, discussion_obj)
    
    for asset_path in image_assets_to_delete:
        try: asset_path.unlink()
        except OSError as e: print(f"WARN: Could not delete asset file {asset_path}: {e}")

    try:
        db.query(UserMessageGrade).filter_by(discussion_id=discussion_id, message_id=message_id).delete()
        db.commit()
    except Exception as e: db.rollback(); print(f"WARN: Could not delete grades for message {message_id}: {e}")
    return {"message": "Message deleted successfully."}


@discussion_router.post("/{discussion_id}/send", status_code=200)
async def send_discussion_to_user(
    discussion_id: str, send_request: DiscussionSendRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    sender_username = current_user.username
    target_username = send_request.target_username

    if sender_username == target_username:
        raise HTTPException(status_code=400, detail="Cannot send a discussion to yourself.")

    target_user_db = db.query(DBUser).filter(DBUser.username == target_username).first()
    if not target_user_db:
        raise HTTPException(status_code=404, detail=f"Target user '{target_username}' not found.")

    original_discussion_obj = get_user_discussion(sender_username, discussion_id)
    if not original_discussion_obj:
        raise HTTPException(status_code=404, detail=f"Original discussion '{discussion_id}' not found for sender.")

    if target_username not in user_sessions:
        initial_lollms_model_target = target_user_db.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
        llm_params_target_session = { # non-prefixed for session
            "temperature": target_user_db.llm_temperature if target_user_db.llm_temperature is not None else LOLLMS_CLIENT_DEFAULTS.get("temperature"),
            "top_k": target_user_db.llm_top_k if target_user_db.llm_top_k is not None else LOLLMS_CLIENT_DEFAULTS.get("top_k"),
            "top_p": target_user_db.llm_top_p if target_user_db.llm_top_p is not None else LOLLMS_CLIENT_DEFAULTS.get("top_p"),
            "repeat_penalty": target_user_db.llm_repeat_penalty if target_user_db.llm_repeat_penalty is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
            "repeat_last_n": target_user_db.llm_repeat_last_n if target_user_db.llm_repeat_last_n is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n"),            
        }
        llm_params_target_session = {k: v for k, v in llm_params_target_session.items() if v is not None}
        user_sessions[target_username] = {
            "lollms_client": None, "safe_store_instances": {}, "discussions": {}, "discussion_titles": {},
            "lollms_model_name": initial_lollms_model_target, "llm_params": llm_params_target_session,
            "active_vectorizer": target_user_db.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
        }
        _load_user_discussions(target_username) 

    target_lc = get_user_lollms_client(target_username) 
    new_discussion_id_for_target = str(uuid.uuid4())
    
    copied_discussion_obj = AppLollmsDiscussion(
        lollms_client_instance=target_lc,
        discussion_id=new_discussion_id_for_target,
        title=f"Sent: {original_discussion_obj.title}"
    )
    copied_discussion_obj.rag_datastore_id = None 

    sender_assets_path = get_user_discussion_assets_path(sender_username) / discussion_id
    target_assets_path = get_user_discussion_assets_path(target_username) / new_discussion_id_for_target
    
    if original_discussion_obj.messages:
        if sender_assets_path.exists() and any(msg.image_references for msg in original_discussion_obj.messages):
            target_assets_path.mkdir(parents=True, exist_ok=True)

    for msg in original_discussion_obj.messages:
        new_image_refs = []
        if msg.image_references:
            for img_ref_filename in msg.image_references: 
                original_asset_file = sender_assets_path / img_ref_filename
                if original_asset_file.exists():
                    new_asset_filename = f"{uuid.uuid4().hex[:8]}_{img_ref_filename}" 
                    target_asset_file = target_assets_path / new_asset_filename
                    try:
                        shutil.copy2(str(original_asset_file), str(target_asset_file))
                        new_image_refs.append(new_asset_filename) 
                    except Exception as e_copy_asset:
                        print(f"ERROR copying asset {original_asset_file} for discussion send: {e_copy_asset}")
                else:
                    print(f"WARN: Asset {original_asset_file} for discussion send not found, skipping.")
        
        copied_discussion_obj.add_message(
            sender=msg.sender, content=msg.content,
            parent_message_id=msg.parent_message_id, 
            binding_name=msg.binding_name, model_name=msg.model_name,
            token_count=msg.token_count, image_references=new_image_refs
        )

    save_user_discussion(target_username, new_discussion_id_for_target, copied_discussion_obj)
    if target_username in user_sessions:
         user_sessions[target_username]["discussions"][new_discussion_id_for_target] = copied_discussion_obj
         user_sessions[target_username]["discussion_titles"][new_discussion_id_for_target] = copied_discussion_obj.title

    return {"message": f"Discussion '{original_discussion_obj.title}' sent to user '{target_username}'."}


@discussion_router.post("/export", response_model=ExportData)
async def export_user_data(export_request: DiscussionExportRequest, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> ExportData:
    username = current_user.username
    user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")

    # User settings are stored with llm_ prefix in DB, export them as is.
    user_settings = {
        "lollms_model_name": user_db_record.lollms_model_name,
        "safe_store_vectorizer": user_db_record.safe_store_vectorizer,
        "llm_temperature": user_db_record.llm_temperature,
        "llm_top_k": user_db_record.llm_top_k,
        "llm_top_p": user_db_record.llm_top_p,
        "llm_repeat_penalty": user_db_record.llm_repeat_penalty,
        "llm_repeat_last_n": user_db_record.llm_repeat_last_n,
    }
    
    owned_datastores_db = db.query(DBDataStore).filter(DBDataStore.owner_user_id == user_db_record.id).all()
    owned_ds_info = [{"id": ds.id, "name": ds.name, "description": ds.description} for ds in owned_datastores_db]
    
    shared_links = db.query(DBSharedDataStoreLink).options(joinedload(DBSharedDataStoreLink.datastore).joinedload(DBDataStore.owner))\
        .filter(DBSharedDataStoreLink.shared_with_user_id == user_db_record.id).all()
    shared_ds_info = [{"id": link.datastore.id, "name": link.datastore.name, "description": link.datastore.description, "owner_username": link.datastore.owner.username} for link in shared_links]

    datastores_export_info = {"owned": owned_ds_info, "shared_with_me": shared_ds_info, "safestore_library_error": None}
    if not safe_store: datastores_export_info["safestore_library_error"] = "SafeStore library not available on server."


    if not user_sessions[username].get("discussions"): _load_user_discussions(username)
    all_user_discussions_map = user_sessions[username].get("discussions", {})
    discussions_to_export_ids = set(all_user_discussions_map.keys())
    if export_request.discussion_ids is not None: discussions_to_export_ids &= set(export_request.discussion_ids)
        
    user_grades_for_export = {}
    if discussions_to_export_ids:
        grades_query = db.query(UserMessageGrade.discussion_id, UserMessageGrade.message_id, UserMessageGrade.grade)\
                         .filter(UserMessageGrade.user_id == user_db_record.id, UserMessageGrade.discussion_id.in_(discussions_to_export_ids)).all()
        for disc_id_db, msg_id_db, grade_db in grades_query:
            if disc_id_db not in user_grades_for_export: user_grades_for_export[disc_id_db] = {}
            user_grades_for_export[disc_id_db][msg_id_db] = grade_db

    discussions_data_list = []
    for disc_id in discussions_to_export_ids:
        disc_obj = all_user_discussions_map.get(disc_id)
        if not disc_obj: continue
        disc_dict = disc_obj.to_dict()
        grades_for_this_disc = user_grades_for_export.get(disc_id, {})
        augmented_messages = []
        for msg_data in disc_dict.get("messages", []):
            msg_id_yaml = msg_data.get("id")
            if msg_id_yaml and msg_id_yaml in grades_for_this_disc:
                msg_data["user_grade"] = grades_for_this_disc[msg_id_yaml]
            augmented_messages.append(msg_data)
        disc_dict["messages"] = augmented_messages
        is_starred = db.query(UserStarredDiscussion).filter_by(user_id=user_db_record.id, discussion_id=disc_id).first() is not None
        disc_dict["is_starred"] = is_starred
        discussions_data_list.append(disc_dict)

    return ExportData(
        exported_by_user=username, export_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        application_version=APP_VERSION, user_settings_at_export=user_settings,
        datastores_info=datastores_export_info, discussions=discussions_data_list
    )

@discussion_router.post("/import", status_code=200)
async def import_user_data(import_file: UploadFile = File(...), import_request_json: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    try: import_request = DiscussionImportRequest.model_validate_json(import_request_json)
    except Exception as e: raise HTTPException(status_code=400, detail=f"Invalid import request format: {e}")
    if import_file.content_type != "application/json": raise HTTPException(status_code=400, detail="Invalid file type.")
    try: content = await import_file.read(); import_data = json.loads(content.decode('utf-8'))
    except json.JSONDecodeError: raise HTTPException(status_code=400, detail="Invalid JSON file content.")
    except Exception as e: raise HTTPException(status_code=500, detail=f"Failed to read upload file: {e}")
    finally: await import_file.close()
    if not isinstance(import_data, dict) or "discussions" not in import_data: raise HTTPException(status_code=400, detail="Invalid export file format.")
    imported_discussions_data = import_data.get("discussions", [])
    if not isinstance(imported_discussions_data, list): raise HTTPException(status_code=400, detail="Format error: 'discussions' not a list.")

    lc = get_user_lollms_client(username); session = user_sessions[username]
    imported_count, skipped_count, errors = 0, 0, []
    if not session.get("discussions"): _load_user_discussions(username)

    imported_user_settings = import_data.get("user_settings_at_export")
    if imported_user_settings:
        print(f"INFO: User settings from import file for user {import_data.get('exported_by_user', 'unknown')}: {imported_user_settings}")
        # Note: Applying imported settings is not done automatically here. 
        # User can set them manually via UI if desired.

    for disc_data_from_file in imported_discussions_data:
        if not isinstance(disc_data_from_file, dict) or "discussion_id" not in disc_data_from_file:
            skipped_count += 1; errors.append({"original_id": "Unknown", "error": "Missing discussion_id in source."}); continue
        original_id = disc_data_from_file["discussion_id"]
        if original_id not in import_request.discussion_ids_to_import: continue
        try:
            new_discussion_id = str(uuid.uuid4())
            imported_discussion_obj = AppLollmsDiscussion(
                lollms_client_instance=lc, discussion_id=new_discussion_id,
                title=disc_data_from_file.get("title", f"Imported {original_id[:8]}")
            )
            imported_discussion_obj.rag_datastore_id = disc_data_from_file.get("rag_datastore_id") 

            messages_from_file = disc_data_from_file.get("messages", [])
            target_assets_path = get_user_discussion_assets_path(username) / new_discussion_id
            
            if isinstance(messages_from_file, list):
                for msg_data_from_file in messages_from_file:
                    if isinstance(msg_data_from_file, dict) and "sender" in msg_data_from_file and "content" in msg_data_from_file:
                        imported_message_obj = AppLollmsMessage.from_dict(msg_data_from_file)
                        imported_message_obj.image_references = [] 
                        imported_discussion_obj.messages.append(imported_message_obj)
                        imported_grade = msg_data_from_file.get("user_grade")
                        if imported_grade is not None and isinstance(imported_grade, int):
                             grade_rec = UserMessageGrade(user_id=user_id, discussion_id=new_discussion_id, message_id=imported_message_obj.id, grade=imported_grade)
                             db.add(grade_rec)
            save_user_discussion(username, new_discussion_id, imported_discussion_obj)
            session["discussions"][new_discussion_id] = imported_discussion_obj
            session["discussion_titles"][new_discussion_id] = imported_discussion_obj.title
            imported_count += 1
            if disc_data_from_file.get("is_starred", False):
                 star_rec = UserStarredDiscussion(user_id=user_id, discussion_id=new_discussion_id)
                 db.add(star_rec)
        except Exception as e_import:
            skipped_count += 1; errors.append({"original_id": original_id, "error": str(e_import)}); traceback.print_exc()
    try: db.commit()
    except Exception as e_db: db.rollback(); errors.append({"DB_COMMIT_ERROR": str(e_db)})
    return {"message": f"Import finished. Imported: {imported_count}, Skipped/Errors: {skipped_count}.", "imported_count": imported_count, "skipped_count": skipped_count, "errors": errors}
