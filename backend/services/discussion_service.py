# backend/services/discussion_service.py
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename
from typing import Optional
from fastapi import HTTPException

from backend.models.app_models import AppLollmsDiscussion, LollmsClient
from backend.utils.path_helpers import get_user_discussion_path
from backend.core.global_state import user_sessions
# from .lollms_service import get_user_lollms_client # Avoid direct import if circular

def _load_user_discussions(username: str, lollms_client: LollmsClient) -> None: # Pass client
    # lc = get_user_lollms_client(username) # Avoids direct import
    discussion_dir = get_user_discussion_path(username)
    session = user_sessions[username] # Assume session is initialized by auth_service
    session["discussions"] = {}
    session["discussion_titles"] = {}
    loaded_count = 0
    for file_path in discussion_dir.glob("*.yaml"):
        if file_path.name.startswith('.'):  # Skip hidden files
            continue
        discussion_id = file_path.stem
        discussion_obj = AppLollmsDiscussion.load_from_disk(lollms_client, file_path)
        if discussion_obj:
            discussion_obj.discussion_id = discussion_id # Ensure ID matches filename stem
            session["discussions"][discussion_id] = discussion_obj
            session["discussion_titles"][discussion_id] = discussion_obj.title
            loaded_count += 1
        else:
            print(f"WARNING: Failed to load discussion from {file_path} for user {username}.")
    print(f"INFO: Loaded {loaded_count} discussions for user {username}.")


def get_user_discussion(username: str, discussion_id: str, lollms_client: LollmsClient, create_if_missing: bool = False) -> Optional[AppLollmsDiscussion]:
    session = user_sessions.get(username)
    if not session:
        raise HTTPException(status_code=500, detail="User session not found.")

    if discussion_id in session["discussions"]:
        return session["discussions"][discussion_id]

    try: # Validate if discussion_id is a UUID, if not and create_if_missing, generate one
        uuid.UUID(discussion_id)
    except ValueError:
        if not create_if_missing:
            return None # Not a valid UUID and not creating
        else: # Generate a new valid UUID for the new discussion
            discussion_id = str(uuid.uuid4())


    # Use secure_filename to prevent path traversal or invalid characters
    safe_filename = secure_filename(f"{discussion_id}.yaml")
    if not safe_filename.endswith(".yaml") or safe_filename == ".yaml": # Basic check
        # This should not happen if discussion_id is a valid UUID
        raise HTTPException(status_code=400, detail="Invalid discussion ID format for filename.")

    file_path = get_user_discussion_path(username) / safe_filename
    
    # lc = get_user_lollms_client(username) # Avoids direct import, pass it
    if file_path.exists():
        disk_obj = AppLollmsDiscussion.load_from_disk(lollms_client, file_path)
        if disk_obj:
            disk_obj.discussion_id = discussion_id # Ensure ID consistency
            session["discussions"][discussion_id] = disk_obj
            session["discussion_titles"][discussion_id] = disk_obj.title
            return disk_obj
    
    if create_if_missing:
        new_discussion = AppLollmsDiscussion(lollms_client_instance=lollms_client, discussion_id=discussion_id)
        session["discussions"][discussion_id] = new_discussion
        session["discussion_titles"][discussion_id] = new_discussion.title
        save_user_discussion(username, discussion_id, new_discussion) # Save immediately
        return new_discussion
        
    return None


def save_user_discussion(username: str, discussion_id: str, discussion_obj: AppLollmsDiscussion) -> None:
    try:
        uuid.UUID(discussion_id) # Ensure it's a valid UUID format before saving
    except ValueError:
        # Log or handle error: attempt to save discussion with non-UUID id
        print(f"ERROR: Attempted to save discussion with invalid ID format: {discussion_id}")
        return

    safe_filename = secure_filename(f"{discussion_id}.yaml")
    if not safe_filename.endswith(".yaml") or safe_filename == ".yaml":
        print(f"ERROR: Invalid filename generated for discussion ID {discussion_id}")
        return

    file_path = get_user_discussion_path(username) / safe_filename
    try:
        discussion_obj.save_to_disk(file_path)
        if username in user_sessions: # Update title in session cache
             user_sessions[username]["discussion_titles"][discussion_id] = discussion_obj.title
    except Exception as e:
        # Log the error properly
        print(f"ERROR: Failed to save discussion {discussion_id} for user {username} to {file_path}: {e}")
        import traceback
        traceback.print_exc()