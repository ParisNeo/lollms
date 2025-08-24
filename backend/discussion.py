# backend/discussion.py
# Standard Library Imports
from pathlib import Path
from typing import List, Optional, Any, Dict
from lollms_client import LollmsClient, LollmsDataManager, LollmsDiscussion
from backend.session import user_sessions, get_user_data_root, get_user_lollms_client

def get_user_discussion_manager(username: str) -> LollmsDataManager:
    """
    Retrieves or creates a LollmsDataManager for a given user.
    """
    if "discussion_manager" in user_sessions.get(username, {}):
        manager = user_sessions[username].get("discussion_manager")
        if manager:
            return manager

    user_data_path = get_user_data_root(username)
    db_path = user_data_path / "discussions.db"
    db_url = f"sqlite:///{db_path.resolve()}"
    manager = LollmsDataManager(db_path=db_url)
    
    if username in user_sessions:
        user_sessions[username]["discussion_manager"] = manager
    else:
        user_sessions[username] = {"discussion_manager": manager}
    return manager

def get_user_discussion(username: str, discussion_id: str, create_if_missing: bool = False, lollms_client: Optional[LollmsClient] = None) -> Optional[LollmsDiscussion]:
    """
    Retrieves or creates a LollmsDiscussion object for a user.
    This function now relies on the lollms-client's native LollmsDiscussion class.
    """
    lc = lollms_client if lollms_client is not None else get_user_lollms_client(username)
    dm = get_user_discussion_manager(username)
    
    max_context_size = user_sessions[username].get("llm_params", {}).get("ctx_size", None) or lc.get_ctx_size() or 4096
    
    discussion = dm.get_discussion(
        lollms_client=lc,
        discussion_id=discussion_id,
        max_context_size=max_context_size,
        autosave=True
    )
    
    if discussion:
        discussion.lollms_client = lc
        discussion.max_context_size = max_context_size
        
        # The get_discussion_images method in the updated library handles its own migration.
        # This call ensures that any necessary migration is triggered on discussion load.
        try:
            discussion.get_discussion_images()
        except Exception as e:
            print(f"Warning: A non-critical error occurred during discussion image check. Trusting library. Error: {e}")

        return discussion
    elif create_if_missing:
        new_discussion = LollmsDiscussion.create_new(
            lollms_client=lc,
            db_manager=dm,
            id=discussion_id,
            max_context_size=max_context_size,
            autosave=True,
            discussion_metadata={"title": f"New Discussion {discussion_id[:8]}"},
        )
        return new_discussion
    return None