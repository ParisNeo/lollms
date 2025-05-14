# backend/routers/admin.py
import shutil
import traceback
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from backend.models.api_models import (
    UserCreateAdmin, UserPublic, UserPasswordResetAdmin, UserAuthDetails
)
from backend.database.setup import User as DBUser, get_db, hash_password
from backend.services.auth_service import get_current_admin_user # Ensures admin privileges
from backend.core.global_state import user_sessions
from backend.utils.path_helpers import get_user_data_root
from backend.config import (
    INITIAL_ADMIN_USER_CONFIG, LOLLMS_CLIENT_DEFAULTS,
    SAFE_STORE_DEFAULTS, DEFAULT_RAG_TOP_K
)

admin_router = APIRouter(
    prefix="/api/admin",
    tags=["Administration"],
    dependencies=[Depends(get_current_admin_user)] # All routes here require admin
)

@admin_router.get("/users", response_model=List[UserPublic])
async def admin_get_all_users(db: Session = Depends(get_db)) -> List[DBUser]:
    # UserPublic.model_validate will map DBUser fields to UserPublic fields
    # FastAPI will automatically call model_validate for response_model
    return db.query(DBUser).order_by(DBUser.username).all()


@admin_router.post("/users", response_model=UserPublic, status_code=201)
async def admin_add_new_user(
    user_data: UserCreateAdmin, # Contains all necessary fields including LLM/UI defaults
    db: Session = Depends(get_db)
) -> DBUser: # Return DBUser, FastAPI handles conversion to UserPublic
    if db.query(DBUser).filter(DBUser.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already registered.")

    # Create new DBUser object, populating all fields from UserCreateAdmin
    # and falling back to global defaults where UserCreateAdmin fields are None/unset.
    new_db_user = DBUser(
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        is_admin=user_data.is_admin,
        
        lollms_model_name=user_data.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name"),
        safe_store_vectorizer=user_data.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
        
        llm_temperature=user_data.llm_temperature if user_data.llm_temperature is not None else LOLLMS_CLIENT_DEFAULTS.get("temperature"),
        llm_top_k=user_data.llm_top_k if user_data.llm_top_k is not None else LOLLMS_CLIENT_DEFAULTS.get("top_k"),
        llm_top_p=user_data.llm_top_p if user_data.llm_top_p is not None else LOLLMS_CLIENT_DEFAULTS.get("top_p"),
        llm_repeat_penalty=user_data.llm_repeat_penalty if user_data.llm_repeat_penalty is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
        llm_repeat_last_n=user_data.llm_repeat_last_n if user_data.llm_repeat_last_n is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n"),
        
        theme_preference=user_data.theme_preference or 'system',
        rag_top_k=user_data.rag_top_k if user_data.rag_top_k is not None else DEFAULT_RAG_TOP_K
    )
    
    try:
        db.add(new_db_user)
        db.commit()
        db.refresh(new_db_user)
        return new_db_user # FastAPI converts to UserPublic
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error creating user: {e}")


@admin_router.post("/users/{user_id}/reset-password")
async def admin_reset_user_password(
    user_id: int,
    payload: UserPasswordResetAdmin,
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    user_to_update = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found.")

    user_to_update.hashed_password = hash_password(payload.new_password)
    try:
        db.commit()
        return {"message": f"Password for user '{user_to_update.username}' has been reset."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error resetting password: {e}")


@admin_router.delete("/users/{user_id}")
async def admin_remove_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: UserAuthDetails = Depends(get_current_admin_user), # To check if admin deletes self
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> Dict[str, str]:
    user_to_delete = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User not found.")

    # Prevent deletion of the initial superadmin specified in config (if any)
    initial_admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
    if initial_admin_username and \
       user_to_delete.username == initial_admin_username and \
       user_to_delete.is_admin:
        raise HTTPException(status_code=403, detail="The initial superadmin account cannot be deleted.")

    # Prevent admin from deleting themselves
    if user_to_delete.username == current_admin.username:
        raise HTTPException(status_code=403, detail="Administrators cannot delete their own accounts via this endpoint.")

    username_for_message_and_path = user_to_delete.username
    user_data_dir_to_delete = get_user_data_root(username_for_message_and_path)

    try:
        # Remove from active sessions if present
        if username_for_message_and_path in user_sessions:
            # Consider closing SafeStore instances and other cleanup like in logout
            if "safe_store_instances" in user_sessions[username_for_message_and_path]:
                 for ds_id, ss_instance in user_sessions[username_for_message_and_path]["safe_store_instances"].items():
                    if hasattr(ss_instance, 'close') and callable(ss_instance.close):
                        try: background_tasks.add_task(ss_instance.close)
                        except Exception as e_ss_close: print(f"Error closing SafeStore {ds_id} for deleted user {username_for_message_and_path}: {e_ss_close}")
            del user_sessions[username_for_message_and_path]
            print(f"INFO: Active session for user '{username_for_message_and_path}' cleared during deletion.")

        # Delete user from database (cascades should handle related data like discussions, prompts, friendships)
        db.delete(user_to_delete)
        db.commit()
        
        # Schedule user's data directory for deletion
        if user_data_dir_to_delete.exists():
            background_tasks.add_task(shutil.rmtree, user_data_dir_to_delete, ignore_errors=True)
            print(f"INFO: Data directory for user '{username_for_message_and_path}' scheduled for background deletion.")
            
        return {"message": f"User '{username_for_message_and_path}' and their associated data (including discussions, prompts, datastores, friendships) have been deleted. Physical data directory scheduled for cleanup."}
    except Exception as e:
        db.rollback()
        traceback.print_exc() # For server logs
        raise HTTPException(status_code=500, detail=f"Database or file system error during user deletion: {e}")

