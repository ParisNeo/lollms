# backend/discussion_manager.py
from lollms_client import LollmsDataManager
from backend.session import user_sessions, get_user_data_root

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