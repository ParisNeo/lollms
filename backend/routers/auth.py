# backend/routers/auth.py
import shutil
from fastapi import APIRouter, Depends, HTTPException, Response, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict

from backend.models.api_models import UserAuthDetails, UserPasswordChange, UserPreferences
from backend.database.setup import User as DBUser, get_db, hash_password
from backend.services.auth_service import get_current_active_user, get_current_db_user
from backend.core.global_state import user_sessions
from backend.utils.path_helpers import get_user_temp_uploads_path

# Routers for /api/auth and /api/users/me
auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])
user_self_router = APIRouter(prefix="/api/users/me", tags=["User Self Management"])


@auth_router.get("/me", response_model=UserAuthDetails)
async def get_my_details(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails:
    return current_user

@auth_router.post("/logout")
async def logout(
    response: Response,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> Dict[str, str]:
    username = current_user.username
    if username in user_sessions:
        temp_dir = get_user_temp_uploads_path(username)
        if temp_dir.exists():
            background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)
        
        if "safe_store_instances" in user_sessions[username]:
            for ds_id, ss_instance in user_sessions[username]["safe_store_instances"].items():
                if hasattr(ss_instance, 'close') and callable(ss_instance.close):
                    try:
                        # Depending on SafeStore, close might need to be awaited or run in thread
                        background_tasks.add_task(ss_instance.close) 
                    except Exception as e_ss_close:
                        print(f"Error closing SafeStore {ds_id} for {username} on logout: {e_ss_close}")
        
        del user_sessions[username]
        print(f"INFO: User '{username}' session cleared. Temp files scheduled for cleanup.")
    # Note: FastAPI does not have built-in session management to "clear" a basic auth session.
    # The client must stop sending the Authorization header.
    # We can set a 401 to prompt re-login, but that's often not desired for a "logout" button.
    # response.status_code = 401 # Optional: to force client re-authentication
    # response.headers["WWW-Authenticate"] = "Basic realm=\"logout\""
    return {"message": "Logout successful. Session cleared on server. Please clear credentials in your client."}


@user_self_router.put("/password")
async def user_change_password(
    payload: UserPasswordChange,
    current_user_db: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    if not current_user_db.verify_password(payload.current_password):
        raise HTTPException(status_code=400, detail="Incorrect current password.")
    current_user_db.hashed_password = hash_password(payload.new_password)
    try:
        db.commit()
        return {"message": "Password changed successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {e}")


@user_self_router.get("/preferences", response_model=UserPreferences)
async def get_user_preferences(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserPreferences:
    return UserPreferences(theme_preference=current_user.theme_preference, rag_top_k=current_user.rag_top_k)


@user_self_router.put("/preferences")
async def update_user_preferences(
    preferences: UserPreferences,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    username = current_user.username
    db_user_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not db_user_record: # Should not happen
        raise HTTPException(status_code=404, detail="User not found.")
    
    updated = False
    if preferences.theme_preference is not None and db_user_record.theme_preference != preferences.theme_preference:
        db_user_record.theme_preference = preferences.theme_preference
        user_sessions[username]["theme_preference"] = preferences.theme_preference
        updated = True
    if preferences.rag_top_k is not None and db_user_record.rag_top_k != preferences.rag_top_k:
        db_user_record.rag_top_k = preferences.rag_top_k
        user_sessions[username]["rag_top_k"] = preferences.rag_top_k
        updated = True
    
    if updated:
        try:
            db.commit()
            return {"message": "Preferences updated successfully."}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"DB error: {e}")
    return {"message": "No changes to preferences."}