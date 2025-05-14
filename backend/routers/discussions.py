# backend/routers/discussions.py
import asyncio
import json
import shutil
import traceback
import uuid
import datetime
from pathlib import Path
from typing import List, Optional, Dict, AsyncGenerator, Any

from fastapi import (
    APIRouter, HTTPException, Depends, Form, Request,
    BackgroundTasks, UploadFile, File
)
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from backend.models.api_models import (
    DiscussionInfo, DiscussionTitleUpdate, DiscussionRagDatastoreUpdate,
    MessageOutput, MessageContentUpdate, MessageGradeUpdate,
    DiscussionExportRequest, ExportData, DiscussionImportRequest,
    DiscussionSendRequest
)
from backend.models.app_models import AppLollmsMessage, AppLollmsDiscussion
from backend.database.setup import (
    User as DBUser, UserStarredDiscussion, UserMessageGrade,
    DataStore as DBDataStore, SharedDataStoreLink as DBSharedDataStoreLink,
    Prompt as DBPrompt, Friendship as DBFriendship, get_db
)
from backend.services.auth_service import get_current_active_user, UserAuthDetails
from backend.services.lollms_service import get_user_lollms_client
from backend.services.discussion_service import (
    get_user_discussion, save_user_discussion, _load_user_discussions
)
from backend.services.rag_service import get_safe_store_instance
from backend.utils.path_helpers import (
    get_user_discussion_path, get_user_discussion_assets_path,
    get_user_temp_uploads_path, secure_filename
)
from backend.core.global_state import user_sessions
from backend.config import (
    APP_VERSION, TEMP_UPLOADS_DIR_NAME, DEFAULT_RAG_TOP_K
)

try:
    import safe_store
except ImportError:
    safe_store = None

from lollms_client import MSG_TYPE

discussion_router = APIRouter(prefix="/api/discussions", tags=["Discussions"])

@discussion_router.get("", response_model=List[DiscussionInfo])
async def list_all_discussions(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[DiscussionInfo]:
    username = current_user.username
    user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.") # Should be caught by auth

    # Ensure discussions are loaded for the session
    if not user_sessions[username].get("discussions"):
        lc = get_user_lollms_client(username)
        _load_user_discussions(username, lc)

    session_discussions = user_sessions[username].get("discussions", {})
    starred_ids = {
        star.discussion_id for star in db.query(UserStarredDiscussion.discussion_id)
        .filter(UserStarredDiscussion.user_id == user_db_record.id).all()
    }
    
    return [
        DiscussionInfo(
            id=disc_id,
            title=disc_obj.title,
            is_starred=(disc_id in starred_ids),
            rag_datastore_id=disc_obj.rag_datastore_id
        ) for disc_id, disc_obj in session_discussions.items()
    ]

@discussion_router.post("", response_model=DiscussionInfo, status_code=201)
async def create_new_discussion(
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> DiscussionInfo:
    username = current_user.username
    discussion_id = str(uuid.uuid4())
    lc = get_user_lollms_client(username)
    discussion_obj = get_user_discussion(username, discussion_id, lc, create_if_missing=True)
    if not discussion_obj: # Should not happen if create_if_missing is True
        raise HTTPException(status_code=500, detail="Failed to create new discussion.")
    
    return DiscussionInfo(
        id=discussion_id,
        title=discussion_obj.title,
        is_starred=False, # New discussions are not starred by default
        rag_datastore_id=None
    )

@discussion_router.get("/{discussion_id}", response_model=List[MessageOutput])
async def get_messages_for_discussion(
    discussion_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[MessageOutput]:
    username = current_user.username
    user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.")

    lc = get_user_lollms_client(username)
    discussion_obj = get_user_discussion(username, discussion_id, lc)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    user_grades = {
        g.message_id: g.grade for g in db.query(UserMessageGrade.message_id, UserMessageGrade.grade)
        .filter(
            UserMessageGrade.user_id == user_db_record.id,
            UserMessageGrade.discussion_id == discussion_id
        ).all()
    }

    messages_output = []
    for msg in discussion_obj.messages:
        # Construct full, servable image references
        full_image_refs = []
        if msg.image_references:
            for ref_filename in msg.image_references:
                # This path needs to match the one served by the static file server
                full_image_refs.append(f"/user_assets/{username}/{discussion_obj.discussion_id}/{ref_filename}")
        
        messages_output.append(
            MessageOutput(
                id=msg.id,
                sender=msg.sender,
                content=msg.content,
                parent_message_id=msg.parent_message_id,
                binding_name=msg.binding_name,
                model_name=msg.model_name,
                token_count=msg.token_count,
                image_references=full_image_refs,
                user_grade=user_grades.get(msg.id, 0)
            )
        )
    return messages_output


@discussion_router.put("/{discussion_id}/title", response_model=DiscussionInfo)
async def update_discussion_title(
    discussion_id: str,
    title_update: DiscussionTitleUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> DiscussionInfo:
    username = current_user.username
    user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.")

    lc = get_user_lollms_client(username)
    discussion_obj = get_user_discussion(username, discussion_id, lc)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    discussion_obj.title = title_update.title
    save_user_discussion(username, discussion_id, discussion_obj)

    is_starred = db.query(UserStarredDiscussion).filter_by(
        user_id=user_db_record.id,
        discussion_id=discussion_id
    ).first() is not None
    
    return DiscussionInfo(
        id=discussion_id,
        title=discussion_obj.title,
        is_starred=is_starred,
        rag_datastore_id=discussion_obj.rag_datastore_id
    )

@discussion_router.put("/{discussion_id}/rag_datastore", response_model=DiscussionInfo)
async def update_discussion_rag_datastore(
    discussion_id: str,
    update_payload: DiscussionRagDatastoreUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> DiscussionInfo:
    username = current_user.username
    lc = get_user_lollms_client(username)
    discussion_obj = get_user_discussion(username, discussion_id, lc)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    if update_payload.rag_datastore_id:
        try:
            # Validate if the user can access this datastore
            get_safe_store_instance(username, update_payload.rag_datastore_id, db)
        except HTTPException as e:
            if e.status_code in [404, 403]: # Datastore not found or not accessible
                raise HTTPException(status_code=400, detail=f"Invalid or inaccessible RAG datastore: {update_payload.rag_datastore_id}")
            raise e # Re-raise other HTTPExceptions (e.g., 500 from SafeStore init)
        except Exception as e_val: # Catch other potential errors during validation
            print(f"Error validating RAG datastore {update_payload.rag_datastore_id}: {e_val}")
            raise HTTPException(status_code=500, detail=f"Error validating RAG datastore.")
            
    discussion_obj.rag_datastore_id = update_payload.rag_datastore_id
    save_user_discussion(username, discussion_id, discussion_obj)

    user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found for star check.")
    is_starred = db.query(UserStarredDiscussion).filter_by(
        user_id=user_db_record.id,
        discussion_id=discussion_id
    ).first() is not None
    
    return DiscussionInfo(
        id=discussion_id,
        title=discussion_obj.title,
        is_starred=is_starred,
        rag_datastore_id=discussion_obj.rag_datastore_id
    )


@discussion_router.delete("/{discussion_id}", status_code=200)
async def delete_specific_discussion(
    discussion_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> Dict[str, str]:
    username = current_user.username
    try:
        uuid.UUID(discussion_id) # Validate format
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid discussion ID format.")

    session = user_sessions[username] # Assumes session exists
    
    # Check if discussion exists in session or on disk
    disc_exists_session = discussion_id in session.get("discussions", {})
    
    # Construct path to discussion file
    safe_filename = secure_filename(f"{discussion_id}.yaml")
    file_path = get_user_discussion_path(username) / safe_filename
    disc_exists_disk = file_path.exists()

    if not disc_exists_session and not disc_exists_disk:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    # Remove from session
    session.get("discussions", {}).pop(discussion_id, None)
    session.get("discussion_titles", {}).pop(discussion_id, None)

    # Remove from disk
    if disc_exists_disk:
        try:
            file_path.unlink()
        except OSError as e:
            if file_path.exists(): # Check if it still exists despite error
                 print(f"ERROR: Failed to delete discussion file {file_path}: {e}")
            # If it doesn't exist, it might have been deleted by another process or unlink succeeded despite error
    
    # Remove associated assets
    assets_path = get_user_discussion_assets_path(username) / discussion_id
    if assets_path.exists() and assets_path.is_dir():
        background_tasks.add_task(shutil.rmtree, assets_path, ignore_errors=True)

    # Remove related database entries
    try:
        user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
        if user_db_record: # Should exist
            db.query(UserStarredDiscussion).filter_by(user_id=user_db_record.id, discussion_id=discussion_id).delete()
            db.query(UserMessageGrade).filter_by(user_id=user_db_record.id, discussion_id=discussion_id).delete()
        db.commit()
    except Exception as e_db:
        db.rollback()
        print(f"ERROR: Failed to delete DB entries for discussion {discussion_id}: {e_db}")
        # Don't raise HTTPException here as file deletion might have succeeded.
        # The client will see success, but an error is logged.

    return {"message": f"Discussion '{discussion_id}' and its associated data deleted."}


@discussion_router.post("/{discussion_id}/star", status_code=201)
async def star_discussion(
    discussion_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    username = current_user.username
    user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.")

    lc = get_user_lollms_client(username)
    if not get_user_discussion(username, discussion_id, lc): # Check if discussion exists
        raise HTTPException(status_code=404, detail="Discussion not found.")

    existing_star = db.query(UserStarredDiscussion).filter_by(
        user_id=user_db_record.id,
        discussion_id=discussion_id
    ).first()
    if existing_star:
        return {"message": "Discussion already starred."}

    new_star = UserStarredDiscussion(user_id=user_db_record.id, discussion_id=discussion_id)
    try:
        db.add(new_star)
        db.commit()
        return {"message": "Discussion starred."}
    except IntegrityError: # Race condition
        db.rollback()
        return {"message": "Discussion already starred (encountered race condition)."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@discussion_router.delete("/{discussion_id}/star", status_code=200)
async def unstar_discussion(
    discussion_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    username = current_user.username
    user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.")

    star_to_delete = db.query(UserStarredDiscussion).filter_by(
        user_id=user_db_record.id,
        discussion_id=discussion_id
    ).first()
    
    if not star_to_delete:
        return {"message": "Discussion not starred or already unstarred."}

    try:
        db.delete(star_to_delete)
        db.commit()
        return {"message": "Discussion unstarred."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@discussion_router.put("/{discussion_id}/messages/{message_id}/grade", response_model=MessageOutput)
async def grade_discussion_message(
    discussion_id: str,
    message_id: str,
    grade_update: MessageGradeUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> MessageOutput:
    username = current_user.username
    user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.")

    lc = get_user_lollms_client(username)
    discussion_obj = get_user_discussion(username, discussion_id, lc)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    target_message = next((msg for msg in discussion_obj.messages if msg.id == message_id), None)
    if not target_message:
        raise HTTPException(status_code=404, detail="Message not found in discussion.")

    # Prevent grading own (user) messages; only AI/assistant messages can be graded
    if target_message.sender.lower() == lc.user_name.lower(): # type: ignore
        raise HTTPException(status_code=400, detail="User messages cannot be graded.")

    # Using the global lock from core.global_state
    from backend.core.global_state import message_grade_lock
    with message_grade_lock:
        grade_record = db.query(UserMessageGrade).filter_by(
            user_id=user_db_record.id,
            discussion_id=discussion_id,
            message_id=message_id
        ).first()

        if grade_record:
            grade_record.grade += grade_update.change # Change is 1 or -1
            # Clamp grade between -1 and 1 if that's the desired behavior, or allow accumulation
            # Original code implies accumulation then clamping to -1,0,1 is not explicitly done.
            # Let's assume it's fine for grade to go beyond +/-1 for now based on original logic.
        else:
            grade_record = UserMessageGrade(
                user_id=user_db_record.id,
                discussion_id=discussion_id,
                message_id=message_id,
                grade=grade_update.change
            )
            db.add(grade_record)
        
        try:
            db.commit()
            db.refresh(grade_record) # Get the updated grade from DB
            current_user_grade = grade_record.grade
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error updating grade: {e}")
    
    full_image_refs = [f"/user_assets/{username}/{discussion_obj.discussion_id}/{Path(ref).name}" for ref in target_message.image_references or []]
    return MessageOutput(
        id=target_message.id, sender=target_message.sender, content=target_message.content,
        parent_message_id=target_message.parent_message_id, binding_name=target_message.binding_name,
        model_name=target_message.model_name, token_count=target_message.token_count,
        image_references=full_image_refs, user_grade=current_user_grade
    )

@discussion_router.put("/{discussion_id}/messages/{message_id}", response_model=MessageOutput)
async def update_discussion_message(
    discussion_id: str,
    message_id: str,
    payload: MessageContentUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> MessageOutput:
    username = current_user.username
    user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.")

    lc = get_user_lollms_client(username)
    discussion_obj = get_user_discussion(username, discussion_id, lc)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    # Edit message and save discussion
    if not discussion_obj.edit_message(message_id, payload.content):
        raise HTTPException(status_code=404, detail="Message not found or edit failed.")
    save_user_discussion(username, discussion_id, discussion_obj)
    
    updated_msg = next((m for m in discussion_obj.messages if m.id == message_id), None)
    if not updated_msg: # Should not happen if edit_message succeeded
        raise HTTPException(status_code=500, detail="Error retrieving updated message after edit.")

    user_grade = db.query(UserMessageGrade.grade).filter_by(
        user_id=user_db_record.id,
        discussion_id=discussion_id,
        message_id=message_id
    ).scalar() or 0

    full_image_refs = [f"/user_assets/{username}/{discussion_obj.discussion_id}/{Path(ref).name}" for ref in updated_msg.image_references or []]
    return MessageOutput(
        id=updated_msg.id, sender=updated_msg.sender, content=updated_msg.content,
        parent_message_id=updated_msg.parent_message_id, binding_name=updated_msg.binding_name,
        model_name=updated_msg.model_name, token_count=updated_msg.token_count,
        image_references=full_image_refs, user_grade=user_grade
    )

@discussion_router.delete("/{discussion_id}/messages/{message_id}", status_code=200)
async def delete_discussion_message(
    discussion_id: str,
    message_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
    # background_tasks: BackgroundTasks = BackgroundTasks() # No BG tasks here in original for asset deletion
) -> Dict[str, str]:
    username = current_user.username
    lc = get_user_lollms_client(username)
    discussion_obj = get_user_discussion(username, discussion_id, lc)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    message_to_delete = next((msg for msg in discussion_obj.messages if msg.id == message_id), None)
    if not message_to_delete:
        raise HTTPException(status_code=404, detail="Message not found in discussion.")

    image_assets_to_delete_paths: List[Path] = []
    if message_to_delete.image_references:
        disc_assets_path = get_user_discussion_assets_path(username) / discussion_id
        for ref_filename in message_to_delete.image_references:
            asset_path = disc_assets_path / ref_filename # Assuming ref_filename is just the name
            if asset_path.is_file():
                image_assets_to_delete_paths.append(asset_path)

    if not discussion_obj.delete_message(message_id):
        # This should not happen if message_to_delete was found
        raise HTTPException(status_code=404, detail="Message deletion failed internally.")
    save_user_discussion(username, discussion_id, discussion_obj)

    # Delete associated image assets
    for asset_path in image_assets_to_delete_paths:
        try:
            asset_path.unlink()
        except OSError as e:
            print(f"WARNING: Could not delete asset {asset_path} for deleted message {message_id}: {e}")

    # Delete grades for this message
    try:
        user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
        if user_db_record: # Should exist
            db.query(UserMessageGrade).filter_by(
                user_id=user_db_record.id, # Grade is user-specific
                discussion_id=discussion_id,
                message_id=message_id
            ).delete()
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"WARNING: Could not delete grades for message {message_id} in discussion {discussion_id}: {e}")

    return {"message": "Message deleted successfully."}

@discussion_router.post("/{discussion_id}/chat")
async def chat_in_existing_discussion(
    discussion_id: str,
    prompt: str = Form(...),
    image_server_paths_json: str = Form("[]"), # List of temp server paths from upload
    use_rag: bool = Form(False),
    rag_datastore_id: Optional[str] = Form(None), # Specific datastore for this query
    parent_message_id: Optional[str] = Form(None),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> StreamingResponse:
    username = current_user.username
    lc = get_user_lollms_client(username)
    discussion_obj = get_user_discussion(username, discussion_id, lc)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    final_image_references_for_message: List[str] = [] # Filenames stored in AppLollmsMessage
    llm_image_paths: List[str] = [] # Absolute paths for LollmsClient

    try:
        image_server_paths: List[str] = json.loads(image_server_paths_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for image_server_paths_json.")

    if image_server_paths:
        user_temp_uploads_path = get_user_temp_uploads_path(username)
        discussion_assets_path = get_user_discussion_assets_path(username) / discussion_id
        discussion_assets_path.mkdir(parents=True, exist_ok=True)

        for temp_rel_path_from_client in image_server_paths:
            # Validate client path format (e.g., "temp_uploads/image.png")
            if not temp_rel_path_from_client.startswith(TEMP_UPLOADS_DIR_NAME + "/"):
                print(f"WARN: Invalid temporary image path format: {temp_rel_path_from_client}")
                continue
            
            image_filename = Path(temp_rel_path_from_client).name # Extract filename
            temp_abs_path = user_temp_uploads_path / image_filename

            if temp_abs_path.is_file():
                # Create a unique persistent filename for the discussion asset
                persistent_filename = f"{uuid.uuid4().hex[:8]}_{image_filename}"
                persistent_abs_path = discussion_assets_path / persistent_filename
                try:
                    shutil.move(str(temp_abs_path), str(persistent_abs_path))
                    final_image_references_for_message.append(persistent_filename) # Store just filename
                    llm_image_paths.append(str(persistent_abs_path)) # Full path for LLM
                except Exception as e_move:
                    print(f"ERROR moving image {temp_abs_path} to {persistent_abs_path}: {e_move}")
            else:
                print(f"WARNING: Temporary image file not found: {temp_abs_path}")
    
    user_token_count = 0
    if prompt and lc.binding:
        try:
            user_token_count = lc.binding.count_tokens(prompt)
        except Exception: # Fallback if count_tokens fails
            user_token_count = len(prompt) // 3


    # Add user message to discussion
    discussion_obj.add_message(
        sender=lc.user_name, # type: ignore
        content=prompt,
        parent_message_id=parent_message_id,
        token_count=user_token_count,
        image_references=final_image_references_for_message # Store only filenames
    )
    # Save discussion here to persist user message immediately
    save_user_discussion(username, discussion_id, discussion_obj)


    final_prompt_for_llm = prompt
    if use_rag and safe_store:
        # Determine which datastore to use: specific for query, discussion default, or user global default (not implemented here)
        effective_rag_datastore_id = rag_datastore_id or discussion_obj.rag_datastore_id
        
        if not effective_rag_datastore_id:
            print(f"WARNING: RAG requested by {username} but no datastore ID provided/set for discussion.")
        
        if effective_rag_datastore_id:
            try:
                ss = get_safe_store_instance(username, effective_rag_datastore_id, db)
                # User's global default vectorizer is usually set when SafeStore instance is created or managed
                # For query, we might need to let user specify or use store's default
                active_vectorizer_for_store = user_sessions[username].get("active_vectorizer") # User's global default
                
                rag_k = current_user.rag_top_k or DEFAULT_RAG_TOP_K # User's preference or global default

                with ss: # Ensure SafeStore connection is managed
                    rag_results = ss.query(prompt, vectorizer_name=active_vectorizer_for_store, top_k=rag_k)
                
                if rag_results:
                    context_str = "\n\nRelevant context from documents:\n"
                    max_rag_len = 2000  # Max length of RAG context string
                    current_rag_len = 0
                    sources = set()
                    for i, res in enumerate(rag_results):
                        chunk_text = res.get('chunk_text', '')
                        file_name = Path(res.get('file_path', '?')).name
                        
                        if current_rag_len + len(chunk_text) > max_rag_len and i > 0:
                            context_str += f"... (truncated {len(rag_results) - i} more results)\n"
                            break
                        context_str += f"{i+1}. From '{file_name}': {chunk_text}\n"
                        current_rag_len += len(chunk_text)
                        sources.add(file_name)
                    
                    final_prompt_for_llm = (
                        f"User question: {prompt}\n\n"
                        f"Use the following context from ({', '.join(sorted(list(sources)))}) to answer if relevant:\n{context_str.strip()}"
                    )
            except HTTPException as e_rag_access:
                # This could be 403 (access denied) or 404 (datastore not found for user)
                print(f"INFO: RAG query skipped for {username} on datastore {effective_rag_datastore_id}: {e_rag_access.detail}")
            except Exception as e_rag_query:
                print(f"ERROR: RAG query failed for {username} on datastore {effective_rag_datastore_id}: {e_rag_query}")
                traceback.print_exc()
        else: # No effective_rag_datastore_id
             print(f"WARNING: RAG requested by {username} but no RAG datastore was selected or available.")
    elif use_rag and not safe_store:
        print(f"WARNING: RAG requested by {username} but safe_store library is not available.")

    # Prepare for streaming LLM response
    main_loop = asyncio.get_event_loop()
    stream_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
    
    # Shared state between the generation thread and the async stream generator
    shared_state = {
        "accumulated_ai_response": "",
        "generation_error": None,
        "final_message_id": None, # For LollmsClient to optionally provide a specific ID
        "binding_name": None,
        "model_name": None
    }

    async def stream_generator_fn() -> AsyncGenerator[str, None]:
        # This callback runs in the LollmsClient's generation thread
        def llm_callback(chunk: str, msg_type: MSG_TYPE, params: Optional[Dict[str, Any]] = None) -> bool:
            if msg_type == MSG_TYPE.MSG_TYPE_CHUNK:
                shared_state["accumulated_ai_response"] += chunk
                # Schedule put_nowait on the main event loop
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "chunk", "content": chunk}) + "\n")
            elif msg_type in (MSG_TYPE.MSG_TYPE_EXCEPTION, MSG_TYPE.MSG_TYPE_ERROR):
                err_content = f"LLM Error: {str(chunk)}"
                shared_state["generation_error"] = err_content
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_content}) + "\n")
                return False # Stop generation
            elif msg_type == MSG_TYPE.MSG_TYPE_FULL_INVISIBLE_TO_USER and params and "final_message_id" in params:
                # If LollmsClient provides a final message ID (e.g., from a specific binding)
                shared_state["final_message_id"] = params["final_message_id"]
            elif msg_type == MSG_TYPE.MSG_TYPE_FINISHED_MESSAGE:
                return False # Stop generation
            return True # Continue generation

        generation_thread: Optional[threading.Thread] = None
        try:
            full_prompt_to_llm = discussion_obj.prepare_query_for_llm(final_prompt_for_llm, llm_image_paths)
            
            def blocking_llm_call():
                try:
                    # Get binding and model name from the active client
                    shared_state["binding_name"] = lc.binding.binding_name if lc.binding else "unknown" # type: ignore
                    shared_state["model_name"] = lc.binding.model_name if lc.binding and hasattr(lc.binding, "model_name") else user_sessions[username].get("lollms_model_name", "unknown") # type: ignore
                    
                    # This is a blocking call
                    lc.generate_text(
                        prompt=full_prompt_to_llm,
                        images=llm_image_paths, # Pass absolute paths of processed images
                        stream=True,
                        streaming_callback=llm_callback
                    )
                except Exception as e_gen:
                    err_msg = f"LLM generation failed: {str(e_gen)}"
                    shared_state["generation_error"] = err_msg
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_msg}) + "\n")
                    traceback.print_exc()
                finally:
                    # Signal end of stream from the generation thread
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)

            import threading
            generation_thread = threading.Thread(target=blocking_llm_call, daemon=True)
            generation_thread.start()

            # Async part: yield items from the queue
            while True:
                item = await stream_queue.get()
                if item is None: # End of stream signal
                    stream_queue.task_done()
                    break
                yield item
                stream_queue.task_done()
            
            # Wait for generation thread to finish, with a timeout
            if generation_thread:
                generation_thread.join(timeout=10) # 10-second timeout

            # After stream finishes, process the AI response
            ai_response_content = shared_state["accumulated_ai_response"]
            ai_token_count = 0
            if ai_response_content and lc.binding:
                try:
                    ai_token_count = lc.binding.count_tokens(ai_response_content)
                except Exception:
                     ai_token_count = len(ai_response_content) // 3


            # Determine parent message ID for AI response (should be the last user message)
            ai_parent_id = None
            if discussion_obj.messages and discussion_obj.messages[-1].sender.lower() == lc.user_name.lower(): # type: ignore
                ai_parent_id = discussion_obj.messages[-1].id
            
            if ai_response_content and not shared_state["generation_error"]:
                ai_message = discussion_obj.add_message(
                    sender=lc.ai_name, # type: ignore
                    content=ai_response_content,
                    parent_message_id=ai_parent_id,
                    binding_name=shared_state.get("binding_name"),
                    model_name=shared_state.get("model_name"),
                    token_count=ai_token_count
                )
                if shared_state.get("final_message_id"): # Override ID if provided by LollmsClient
                    ai_message.id = shared_state["final_message_id"] # type: ignore
            elif shared_state["generation_error"]:
                discussion_obj.add_message(
                    sender="system", # Or lc.ai_name with error prefix
                    content=str(shared_state["generation_error"]),
                    parent_message_id=ai_parent_id
                )
            
            # Save discussion again to include AI response or error
            save_user_discussion(username, discussion_id, discussion_obj)

        except Exception as e_outer:
            error_msg = f"Chat stream processing error: {str(e_outer)}"
            traceback.print_exc()
            # Try to save error to discussion
            try:
                if discussion_obj: # discussion_obj might not be defined if error is early
                    ai_parent_id_err = discussion_obj.messages[-1].id if discussion_obj.messages and discussion_obj.messages[-1].sender == lc.user_name else None # type: ignore
                    discussion_obj.add_message(sender="system", content=error_msg, parent_message_id=ai_parent_id_err)
                    save_user_discussion(username, discussion_id, discussion_obj)
            except Exception as save_err:
                print(f"ERROR: Failed to save discussion after outer stream error: {save_err}")
            # Yield error to client if stream hasn't started or after it has ended badly
            # Check if stream_queue is still being used (this is tricky)
            # For simplicity, if an error occurs here, it's likely before or after the main yield loop.
            if stream_queue.empty(): # Or some other check
                 yield json.dumps({"type": "error", "content": error_msg}) + "\n"
        finally:
            # Clean up any remaining temp image files that were successfully moved
            # (Original code had this, but they should be moved, so nothing to clean if successful)
            # If some images in image_server_paths were NOT moved (e.g., due to error before move),
            # they might still be in temp_uploads. This logic needs refinement if partial moves are possible.
            # The original code clears all `image_server_paths` from temp dir.
            if image_server_paths:
                user_temp_uploads_path = get_user_temp_uploads_path(username)
                for temp_rel_path in image_server_paths:
                    image_filename = Path(temp_rel_path).name
                    temp_abs_path_to_clean = user_temp_uploads_path / image_filename
                    if temp_abs_path_to_clean.exists(): # Only if it still exists (wasn't moved)
                        background_tasks.add_task(temp_abs_path_to_clean.unlink, missing_ok=True)
            
            if generation_thread and generation_thread.is_alive():
                print(f"WARNING: LLM generation thread for user {username} (discussion {discussion_id}) is still alive after stream_generator_fn finished.")
                # Potentially try to signal stop if LollmsClient supports it, or just log.

    return StreamingResponse(stream_generator_fn(), media_type="application/x-ndjson")


@discussion_router.post("/{discussion_id}/send", status_code=200)
async def send_discussion_to_user(
    discussion_id: str,
    send_request: DiscussionSendRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    sender_username = current_user.username
    target_username = send_request.target_username

    if sender_username == target_username:
        raise HTTPException(status_code=400, detail="Cannot send a discussion to yourself.")

    sender_user_db = db.query(DBUser).filter(DBUser.username == sender_username).first()
    target_user_db = db.query(DBUser).filter(DBUser.username == target_username).first()

    if not sender_user_db: # Should not happen due to Depends(get_current_active_user)
        raise HTTPException(status_code=404, detail="Sender user not found.")
    if not target_user_db:
        raise HTTPException(status_code=404, detail=f"Target user '{target_username}' not found.")

    # Check for friendship
    friendship = db.query(DBFriendship).filter(
        ((DBFriendship.requester_id == sender_user_db.id) & (DBFriendship.addressee_id == target_user_db.id)) |
        ((DBFriendship.requester_id == target_user_db.id) & (DBFriendship.addressee_id == sender_user_db.id)),
        DBFriendship.status == 'accepted'
    ).first()
    if not friendship:
        raise HTTPException(status_code=403, detail=f"You are not friends with '{target_username}'. Discussion cannot be sent.")

    sender_lc = get_user_lollms_client(sender_username)
    original_discussion_obj = get_user_discussion(sender_username, discussion_id, sender_lc)
    if not original_discussion_obj:
        raise HTTPException(status_code=404, detail=f"Original discussion '{discussion_id}' not found for sender.")

    # Prime target user's session and load their discussions if not already active
    if target_username not in user_sessions:
        from backend.services.auth_service import get_current_active_user # To initialize session
        # This is a bit of a hack. Ideally, target user interaction would prime their session.
        # For sending, we might need a more direct way to ensure their session structure exists.
        # Let's simulate parts of get_current_active_user for the target.
        print(f"INFO: Priming session for target user: {target_username} for discussion send.")
        from backend.config import LOLLMS_CLIENT_DEFAULTS as LCD, SAFE_STORE_DEFAULTS as SSD, DEFAULT_RAG_TOP_K as DRTK
        llm_params_target = {
            "temperature": target_user_db.llm_temperature if target_user_db.llm_temperature is not None else LCD.get("temperature"),
            "top_k": target_user_db.llm_top_k if target_user_db.llm_top_k is not None else LCD.get("top_k"), # etc.
        } # Simplified, copy full logic from get_current_active_user for llm_params
        llm_params_target = {k: v for k,v in llm_params_target.items() if v is not None}

        user_sessions[target_username] = {
            "lollms_client": None, "safe_store_instances": {}, "discussions": {}, "discussion_titles": {},
            "lollms_model_name": target_user_db.lollms_model_name or LCD.get("default_model_name"),
            "active_vectorizer": target_user_db.safe_store_vectorizer or SSD.get("global_default_vectorizer"),
            "llm_params": llm_params_target,
            "theme_preference": target_user_db.theme_preference or 'system',
            "rag_top_k": target_user_db.rag_top_k or DRTK,
        }
    
    target_lc = get_user_lollms_client(target_username) # Ensures target LollmsClient is available
    if not user_sessions[target_username].get("discussions"): # Check if discussions are loaded for target
        _load_user_discussions(target_username, target_lc)


    new_discussion_id_for_target = str(uuid.uuid4())
    copied_discussion_obj = AppLollmsDiscussion(
        lollms_client_instance=target_lc,
        discussion_id=new_discussion_id_for_target,
        title=f"Sent by {sender_username}: {original_discussion_obj.title}"
    )
    copied_discussion_obj.rag_datastore_id = None # RAG datastore is user/discussion specific

    # Copy messages and assets
    sender_assets_root_path = get_user_discussion_assets_path(sender_username)
    target_assets_root_path = get_user_discussion_assets_path(target_username)
    
    sender_discussion_assets_path = sender_assets_root_path / discussion_id
    target_discussion_assets_path = target_assets_root_path / new_discussion_id_for_target

    # Create target asset directory only if there are assets to copy
    if original_discussion_obj.messages and any(msg.image_references for msg in original_discussion_obj.messages):
        if sender_discussion_assets_path.exists():
             target_discussion_assets_path.mkdir(parents=True, exist_ok=True)


    for msg in original_discussion_obj.messages:
        new_image_refs_for_target_msg: List[str] = []
        if msg.image_references and sender_discussion_assets_path.exists():
            for img_ref_filename in msg.image_references:
                original_asset_file = sender_discussion_assets_path / img_ref_filename
                if original_asset_file.is_file():
                    # Create a new unique name for the copied asset in target's dir
                    new_target_asset_filename = f"{uuid.uuid4().hex[:8]}_{img_ref_filename}"
                    target_asset_file = target_discussion_assets_path / new_target_asset_filename
                    try:
                        shutil.copy2(str(original_asset_file), str(target_asset_file))
                        new_image_refs_for_target_msg.append(new_target_asset_filename)
                    except Exception as e_copy_asset:
                        print(f"ERROR copying asset {original_asset_file} to {target_asset_file}: {e_copy_asset}")
                else:
                    print(f"WARNING: Asset {original_asset_file} for original discussion not found, skipping.")
        
        copied_discussion_obj.add_message(
            sender=msg.sender, content=msg.content, parent_message_id=msg.parent_message_id,
            binding_name=msg.binding_name, model_name=msg.model_name, token_count=msg.token_count,
            image_references=new_image_refs_for_target_msg # Use newly copied asset filenames
        )

    save_user_discussion(target_username, new_discussion_id_for_target, copied_discussion_obj)
    
    # Update target's in-memory session if they are active
    if target_username in user_sessions:
         user_sessions[target_username]["discussions"][new_discussion_id_for_target] = copied_discussion_obj
         user_sessions[target_username]["discussion_titles"][new_discussion_id_for_target] = copied_discussion_obj.title

    return {"message": f"Discussion '{original_discussion_obj.title}' sent to friend '{target_username}'."}


@discussion_router.post("/export", response_model=ExportData)
async def export_user_data(
    export_request: DiscussionExportRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> ExportData:
    username = current_user.username
    user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.")

    # User settings for export
    user_settings_at_export = {
        "lollms_model_name": user_db_record.lollms_model_name,
        "safe_store_vectorizer": user_db_record.safe_store_vectorizer,
        "llm_temperature": user_db_record.llm_temperature,
        "llm_top_k": user_db_record.llm_top_k,
        "llm_top_p": user_db_record.llm_top_p,
        "llm_repeat_penalty": user_db_record.llm_repeat_penalty,
        "llm_repeat_last_n": user_db_record.llm_repeat_last_n,
        "theme_preference": user_db_record.theme_preference,
        "rag_top_k": user_db_record.rag_top_k
    }

    # DataStores info
    owned_datastores_db = db.query(DBDataStore).filter(DBDataStore.owner_user_id == user_db_record.id).all()
    owned_ds_info = [
        {"id": ds.id, "name": ds.name, "description": ds.description, "is_public_in_store": ds.is_public_in_store}
        for ds in owned_datastores_db
    ]
    
    shared_links = db.query(DBSharedDataStoreLink).options(
        joinedload(DBSharedDataStoreLink.datastore).joinedload(DBDataStore.owner)
    ).filter(DBSharedDataStoreLink.shared_with_user_id == user_db_record.id).all()
    shared_ds_info = [
        {"id": link.datastore.id, "name": link.datastore.name, "description": link.datastore.description,
         "owner_username": link.datastore.owner.username, "is_public_in_store": link.datastore.is_public_in_store}
        for link in shared_links
    ]
    datastores_export_info = {
        "owned": owned_ds_info,
        "shared_with_me": shared_ds_info,
        "safestore_library_error": None if safe_store else "SafeStore library not available on server during export."
    }

    # Discussions
    lc = get_user_lollms_client(username) # Needed for _load_user_discussions if not loaded
    if not user_sessions[username].get("discussions"):
        _load_user_discussions(username, lc)
    
    all_user_discussions_map = user_sessions[username].get("discussions", {})
    
    discussions_to_export_ids = set(all_user_discussions_map.keys())
    if export_request.discussion_ids is not None: # If specific IDs are requested, filter
        discussions_to_export_ids &= set(export_request.discussion_ids)

    user_grades_for_export: Dict[str, Dict[str, int]] = {}
    if discussions_to_export_ids:
        grades_query_results = db.query(
            UserMessageGrade.discussion_id, UserMessageGrade.message_id, UserMessageGrade.grade
        ).filter(
            UserMessageGrade.user_id == user_db_record.id,
            UserMessageGrade.discussion_id.in_(list(discussions_to_export_ids)) # Ensure it's a list
        ).all()
        for disc_id_db, msg_id_db, grade_db in grades_query_results:
            if disc_id_db not in user_grades_for_export:
                user_grades_for_export[disc_id_db] = {}
            user_grades_for_export[disc_id_db][msg_id_db] = grade_db
            
    discussions_data_list = []
    for disc_id_to_export in discussions_to_export_ids:
        disc_obj = all_user_discussions_map.get(disc_id_to_export)
        if not disc_obj:
            continue # Skip if discussion not found in memory (shouldn't happen if loaded)
        
        disc_dict = disc_obj.to_dict() # Get base discussion data
        grades_for_this_disc = user_grades_for_export.get(disc_id_to_export, {})
        
        augmented_messages = []
        for msg_data_dict in disc_dict.get("messages", []):
            msg_id_from_yaml = msg_data_dict.get("id")
            if msg_id_from_yaml and msg_id_from_yaml in grades_for_this_disc:
                msg_data_dict["user_grade"] = grades_for_this_disc[msg_id_from_yaml]
            else: # Ensure user_grade field exists even if 0
                msg_data_dict["user_grade"] = 0
            augmented_messages.append(msg_data_dict)
        disc_dict["messages"] = augmented_messages

        is_starred = db.query(UserStarredDiscussion).filter_by(
            user_id=user_db_record.id,
            discussion_id=disc_id_to_export
        ).first() is not None
        disc_dict["is_starred"] = is_starred
        discussions_data_list.append(disc_dict)

    # Prompts
    owned_prompts_db = db.query(DBPrompt).filter(DBPrompt.owner_user_id == user_db_record.id).all()
    prompts_export_data = [
        {"id": p.id, "name": p.name, "category": p.category, "description": p.description,
         "content": p.content, "is_public": p.is_public}
        for p in owned_prompts_db
    ]

    return ExportData(
        exported_by_user=username,
        export_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        application_version=APP_VERSION,
        user_settings_at_export=user_settings_at_export,
        datastores_info=datastores_export_info,
        discussions=discussions_data_list,
        prompts=prompts_export_data
    )


@discussion_router.post("/import", status_code=200)
async def import_user_data(
    import_file: UploadFile = File(...),
    import_request_json: str = Form(...), # Contains discussion_ids_to_import
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    username = current_user.username
    user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.")

    try:
        import_request = DiscussionImportRequest.model_validate_json(import_request_json)
    except Exception as e_val:
        raise HTTPException(status_code=400, detail=f"Invalid import request JSON format: {e_val}")

    if import_file.content_type != "application/json":
        raise HTTPException(status_code=400, detail="Invalid file type. Expected application/json.")

    try:
        content = await import_file.read()
        import_data_payload = json.loads(content.decode('utf-8'))
    except Exception as e_parse:
        await import_file.close()
        raise HTTPException(status_code=500, detail=f"Failed to read or parse uploaded file: {e_parse}")
    finally:
        await import_file.close()

    if not isinstance(import_data_payload, dict) or "discussions" not in import_data_payload:
        raise HTTPException(status_code=400, detail="Invalid export file format: 'discussions' key missing.")

    imported_discussions_data_from_file = import_data_payload.get("discussions", [])
    imported_prompts_data_from_file = import_data_payload.get("prompts", []) # Prompts are optional in file

    if not isinstance(imported_discussions_data_from_file, list):
        raise HTTPException(status_code=400, detail="Format error: 'discussions' in file is not a list.")
    if not isinstance(imported_prompts_data_from_file, list) and imported_prompts_data_from_file is not None:
         raise HTTPException(status_code=400, detail="Format error: 'prompts' in file must be a list if present.")


    lc = get_user_lollms_client(username)
    session = user_sessions[username] # Assume session exists
    if not session.get("discussions"): # Ensure discussions are loaded in memory
        _load_user_discussions(username, lc)

    imported_disc_count, skipped_disc_count, disc_errors = 0, 0, []
    imported_prompt_count, skipped_prompt_count, prompt_errors = 0, 0, []

    for disc_data_from_file in imported_discussions_data_from_file:
        if not isinstance(disc_data_from_file, dict) or "discussion_id" not in disc_data_from_file:
            skipped_disc_count += 1
            disc_errors.append({"id": "Unknown", "error": "Missing discussion_id in imported data."})
            continue
        
        original_id_from_file = disc_data_from_file["discussion_id"]
        if original_id_from_file not in import_request.discussion_ids_to_import:
            continue # Skip if not requested by client

        try:
            new_imported_disc_id = str(uuid.uuid4()) # Always generate a new ID for imported discussion
            
            imported_discussion_obj = AppLollmsDiscussion(
                lc,
                new_imported_disc_id,
                disc_data_from_file.get("title", f"Imported {original_id_from_file[:8]}")
            )
            # RAG datastore ID - try to preserve if user has access, otherwise clear
            # This requires validation similar to update_discussion_rag_datastore
            imported_rag_id = disc_data_from_file.get("rag_datastore_id")
            if imported_rag_id:
                try:
                    get_safe_store_instance(username, imported_rag_id, db) # Validate access
                    imported_discussion_obj.rag_datastore_id = imported_rag_id
                except HTTPException:
                    imported_discussion_obj.rag_datastore_id = None # Clear if not accessible
                    print(f"INFO: RAG datastore ID '{imported_rag_id}' from import for discussion '{original_id_from_file}' cleared as it's not accessible to user '{username}'.")
                except Exception:
                    imported_discussion_obj.rag_datastore_id = None
                    print(f"ERROR: Validating RAG datastore ID '{imported_rag_id}' during import failed. Clearing.")


            messages_from_file = disc_data_from_file.get("messages", [])
            if isinstance(messages_from_file, list):
                for msg_data in messages_from_file:
                    if isinstance(msg_data, dict) and "sender" in msg_data and "content" in msg_data:
                        # Create AppLollmsMessage, ensuring image_references are cleared as assets are not imported.
                        imported_msg_obj = AppLollmsMessage.from_dict(msg_data)
                        imported_msg_obj.image_references = [] # Crucial: Do not try to link to old assets
                        imported_discussion_obj.messages.append(imported_msg_obj)
                        
                        # Import grades if present
                        grade_val = msg_data.get("user_grade")
                        if grade_val is not None and isinstance(grade_val, int):
                            db.add(UserMessageGrade(
                                user_id=user_db_record.id,
                                discussion_id=new_imported_disc_id, # Use new discussion ID
                                message_id=imported_msg_obj.id, # Use message's original ID (or generate new if needed)
                                grade=grade_val
                            ))
            
            save_user_discussion(username, new_imported_disc_id, imported_discussion_obj)
            session["discussions"][new_imported_disc_id] = imported_discussion_obj
            session["discussion_titles"][new_imported_disc_id] = imported_discussion_obj.title
            imported_disc_count += 1

            if disc_data_from_file.get("is_starred", False):
                db.add(UserStarredDiscussion(user_id=user_db_record.id, discussion_id=new_imported_disc_id))

        except Exception as e_import_disc:
            skipped_disc_count += 1
            disc_errors.append({"id": original_id_from_file, "error": str(e_import_disc)})
            traceback.print_exc()

    # Import prompts
    if imported_prompts_data_from_file: # Only if prompts section exists in file
        for prompt_data_from_file in imported_prompts_data_from_file:
            if not isinstance(prompt_data_from_file, dict) or "name" not in prompt_data_from_file or "content" not in prompt_data_from_file:
                skipped_prompt_count += 1
                prompt_errors.append({"name": prompt_data_from_file.get("name", "Unknown"), "error": "Missing name or content."})
                continue
            try:
                prompt_name_from_file = prompt_data_from_file["name"]
                new_prompt_name_for_user = prompt_name_from_file
                
                # Handle name conflicts for prompts
                existing_prompt_with_name = db.query(DBPrompt).filter_by(
                    owner_user_id=user_db_record.id,
                    name=new_prompt_name_for_user
                ).first()
                if existing_prompt_with_name:
                    new_prompt_name_for_user = f"{prompt_name_from_file} (Imported {uuid.uuid4().hex[:4]})"
                
                new_db_prompt = DBPrompt(
                    owner_user_id=user_db_record.id,
                    name=new_prompt_name_for_user,
                    category=prompt_data_from_file.get("category"),
                    description=prompt_data_from_file.get("description"),
                    content=prompt_data_from_file["content"],
                    is_public=False # Imported prompts are private by default
                )
                db.add(new_db_prompt)
                imported_prompt_count += 1
            except Exception as e_import_prompt:
                skipped_prompt_count += 1
                prompt_errors.append({"name": prompt_data_from_file.get("name", "Unknown"), "error": str(e_import_prompt)})
                traceback.print_exc()

    try:
        db.commit()
    except Exception as e_db_commit:
        db.rollback()
        # Add a general commit error, as specific errors are already in lists
        error_summary = f"Database commit failed after processing imports: {e_db_commit}"
        disc_errors.append({"id": "DB_COMMIT", "error": error_summary})
        if imported_prompts_data_from_file: # Only add prompt commit error if prompts were processed
            prompt_errors.append({"name": "DB_COMMIT", "error": error_summary})
        # Note: Counts might be inaccurate if commit fails. Client needs to be aware.

    return {
        "message": "Import process finished.",
        "discussions": {"imported": imported_disc_count, "skipped": skipped_disc_count, "errors": disc_errors},
        "prompts": {"imported": imported_prompt_count, "skipped": skipped_prompt_count, "errors": prompt_errors}
    }
