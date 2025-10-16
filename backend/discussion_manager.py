# backend/discussion_manager.py
from lollms_client import LollmsDataManager
from backend.session import user_sessions, get_user_data_root

def get_user_discussion_manager(username: str) -> LollmsDataManager:
    """
    Creates a new LollmsDataManager instance for a given user for each request.
    This ensures that each request (e.g., from a different browser tab) has an
    isolated discussion management context, preventing state mingling.
    """
    user_data_path = get_user_data_root(username)
    db_path = user_data_path / "discussions.db"
    db_url = f"sqlite:///{db_path.resolve()}"
    manager = LollmsDataManager(db_path=db_url)
    return manager