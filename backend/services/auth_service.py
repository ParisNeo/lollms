# backend/services/auth_service.py
import os
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from backend.database.setup import User as DBUser, get_db, hash_password
from backend.models.api_models import UserAuthDetails
from backend.core.global_state import user_sessions
from backend.config import LOLLMS_CLIENT_DEFAULTS, SAFE_STORE_DEFAULTS, DEFAULT_RAG_TOP_K
# Import lollms_service carefully to avoid circular dependencies if it imports this
# from .lollms_service import get_user_lollms_client # This might cause circularity
# from .discussion_service import _load_user_discussions # This might cause circularity

# To break circular dependency, service functions will be called by routers,
# and they will call other service functions as needed.
# For get_current_active_user, it needs get_user_lollms_client and _load_user_discussions.
# These will be imported dynamically or passed. Let's use dynamic import for now.


security = HTTPBasic()

def get_current_db_user(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> DBUser:
    user = db.query(DBUser).filter(DBUser.username == credentials.username).first()
    if not user or not user.verify_password(credentials.password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user


def get_current_active_user(db_user: DBUser = Depends(get_current_db_user)) -> UserAuthDetails:
    # To avoid circular import, import services here or pass them as arguments from router
    from .lollms_service import get_user_lollms_client
    from .discussion_service import _load_user_discussions # Assuming this is needed here

    username = db_user.username
    if username not in user_sessions:
        print(f"INFO: Initializing session state for user: {username}")
        llm_params = {
            "temperature": db_user.llm_temperature if db_user.llm_temperature is not None else LOLLMS_CLIENT_DEFAULTS.get("temperature"),
            "top_k": db_user.llm_top_k if db_user.llm_top_k is not None else LOLLMS_CLIENT_DEFAULTS.get("top_k"),
            "top_p": db_user.llm_top_p if db_user.llm_top_p is not None else LOLLMS_CLIENT_DEFAULTS.get("top_p"),
            "repeat_penalty": db_user.llm_repeat_penalty if db_user.llm_repeat_penalty is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
            "repeat_last_n": db_user.llm_repeat_last_n if db_user.llm_repeat_last_n is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n"),
        }
        llm_params = {k: v for k, v in llm_params.items() if v is not None}
        
        user_sessions[username] = {
            "lollms_client": None,
            "safe_store_instances": {},
            "discussions": {},
            "discussion_titles": {},
            "active_vectorizer": db_user.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
            "lollms_model_name": db_user.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name"),
            "llm_params": llm_params,
            "theme_preference": db_user.theme_preference or 'system',
            "rag_top_k": db_user.rag_top_k or DEFAULT_RAG_TOP_K,
        }

    lc = get_user_lollms_client(username) # Uses user_sessions
    ai_name = getattr(lc, "ai_name", LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant"))
    
    if not user_sessions[username].get("discussions"):
        _load_user_discussions(username, lc) # Pass lc to avoid re-fetching in _load_user_discussions

    session_data = user_sessions[username]
    return UserAuthDetails(
        username=username,
        is_admin=db_user.is_admin,
        lollms_model_name=session_data["lollms_model_name"],
        safe_store_vectorizer=session_data["active_vectorizer"],
        lollms_client_ai_name=ai_name,
        llm_temperature=session_data["llm_params"].get("temperature"),
        llm_top_k=session_data["llm_params"].get("top_k"),
        llm_top_p=session_data["llm_params"].get("top_p"),
        llm_repeat_penalty=session_data["llm_params"].get("repeat_penalty"),
        llm_repeat_last_n=session_data["llm_params"].get("repeat_last_n"),
        theme_preference=session_data.get("theme_preference", 'system'),
        rag_top_k=session_data.get("rag_top_k", DEFAULT_RAG_TOP_K)
    )

def get_current_admin_user(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator privileges required.")
    return current_user

# hash_password is in database.setup, can be imported directly where needed or wrapped here
# For simplicity, let routers/admin.py import hash_password from database.setup