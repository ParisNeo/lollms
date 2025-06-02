
# --- Authentication API ---
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
    BackgroundTasks,
    status
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

from backend.session import (get_current_active_user, get_current_db_user, get_user_lollms_client, get_user_temp_uploads_path, user_sessions)
from backend.config import (LOLLMS_CLIENT_DEFAULTS)

auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])
security = HTTPBasic()



@auth_router.get("/me", response_model=UserAuthDetails)
async def get_my_details(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails: return current_user
# New endpoint for updating user settings
@auth_router.put("/me", response_model=UserAuthDetails) # Returns the updated user details
async def update_my_details(
    user_update_data: UserUpdate,
    db_user: DBUser = Depends(get_current_db_user), # Get the DBUser object
    db: Session = Depends(get_db)
) -> UserAuthDetails:
    updated_fields = user_update_data.model_dump(exclude_unset=True)
    session_needs_refresh = False
    lollms_client_needs_reinit = False

    for field, value in updated_fields.items():
        if hasattr(db_user, field):
            setattr(db_user, field, value)
            if field == "active_personality_id":
                session_needs_refresh = True
            if field in ["lollms_model_name", "llm_temperature", "llm_top_k", "llm_top_p", "llm_repeat_penalty", "llm_repeat_last_n", "put_thoughts_in_context"]:
                lollms_client_needs_reinit = True # Some LLM params might require client re-init
                session_needs_refresh = True # Also refresh session for these

    try:
        db.commit()
        db.refresh(db_user)

        # Update session if critical fields changed
        if session_needs_refresh and db_user.username in user_sessions:
            session = user_sessions[db_user.username]
            if "active_personality_id" in updated_fields:
                session["active_personality_id"] = db_user.active_personality_id
                if db_user.active_personality_id:
                    active_pers_prompt = db.query(DBPersonality.prompt_text).filter(DBPersonality.id == db_user.active_personality_id).scalar()
                    session["active_personality_prompt"] = active_pers_prompt
                else:
                    session["active_personality_prompt"] = None
            
            # Update session llm_params (non-prefixed keys)
            session_llm_params = session.get("llm_params", {})
            if "llm_temperature" in updated_fields: session_llm_params["temperature"] = db_user.llm_temperature
            if "llm_top_k" in updated_fields: session_llm_params["top_k"] = db_user.llm_top_k
            if "llm_top_p" in updated_fields: session_llm_params["top_p"] = db_user.llm_top_p
            if "llm_repeat_penalty" in updated_fields: session_llm_params["repeat_penalty"] = db_user.llm_repeat_penalty
            if "llm_repeat_last_n" in updated_fields: session_llm_params["repeat_last_n"] = db_user.llm_repeat_last_n
            if "put_thoughts_in_context" in updated_fields: session_llm_params["put_thoughts_in_context"] = db_user.put_thoughts_in_context
            
            session["llm_params"] = {k: v for k, v in session_llm_params.items() if v is not None}

            if "lollms_model_name" in updated_fields:
                session["lollms_model_name"] = db_user.lollms_model_name
                lollms_client_needs_reinit = True
         
            if lollms_client_needs_reinit:
                session["lollms_client"] = None # Force re-init on next use

        # Re-fetch UserAuthDetails to reflect all changes
        # This is a bit inefficient as it re-runs get_current_active_user logic,
        # but ensures consistency.
        # A more direct way would be to construct UserAuthDetails from db_user and session here.
        # For now, let's rely on a fresh call to get_current_active_user by the client after this.
        # Or, we can construct it manually:
        
        lc = get_user_lollms_client(db_user.username) # Ensure client is available for ai_name
        ai_name_for_user = getattr(lc, "ai_name", LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant"))
        current_session_llm_params = user_sessions[db_user.username].get("llm_params", {})


        return UserAuthDetails(
            username=db_user.username, is_admin=db_user.is_admin,
            first_name=db_user.first_name, family_name=db_user.family_name,
            email=db_user.email, birth_date=db_user.birth_date,
            lollms_model_name=db_user.lollms_model_name,
            safe_store_vectorizer=db_user.safe_store_vectorizer,
            active_personality_id=db_user.active_personality_id,
            lollms_client_ai_name=ai_name_for_user,
            llm_temperature=current_session_llm_params.get("temperature"),
            llm_top_k=current_session_llm_params.get("top_k"),
            llm_top_p=current_session_llm_params.get("top_p"),
            llm_repeat_penalty=current_session_llm_params.get("repeat_penalty"),
            llm_repeat_last_n=current_session_llm_params.get("repeat_last_n"),
            put_thoughts_in_context=current_session_llm_params.get("put_thoughts_in_context"),
            rag_top_k=db_user.rag_top_k,
            rag_use_graph=db_user.rag_use_graph,
            rag_graph_response_type=db_user.rag_graph_response_type
        )

    except IntegrityError as e:
        db.rollback()
        # Check for specific constraint violations if needed, e.g., unique email
        raise HTTPException(status_code=400, detail=f"Data integrity error: {e.orig}")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@auth_router.post("/logout")
async def logout(response: Response, current_user: UserAuthDetails = Depends(get_current_active_user), background_tasks: BackgroundTasks = BackgroundTasks()) -> Dict[str, str]:
    username = current_user.username
    if username in user_sessions:
        # Clean up temp uploads for the user
        temp_dir = get_user_temp_uploads_path(username)
        if temp_dir.exists():
            background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)
        
        # Close any open SafeStore instances for this user
        # This might be too aggressive if other sessions are active, but for single-session logout it's okay
        # More robust: reference counting or explicit close on instance when no longer needed.
        if "safe_store_instances" in user_sessions[username]:
            for ds_id, ss_instance in user_sessions[username]["safe_store_instances"].items():
                if hasattr(ss_instance, 'close') and callable(ss_instance.close):
                    try: background_tasks.add_task(ss_instance.close)
                    except Exception as e_ss_close: print(f"Error closing SafeStore {ds_id} for {username} on logout: {e_ss_close}")
        
        del user_sessions[username]
        print(f"INFO: User '{username}' session cleared (logged out). Temp files scheduled for cleanup.")
    response.status_code = status.HTTP_401_UNAUTHORIZED
    del response.headers['www-authenticate'] # Ensure no WWW-Authenticate header is sent
    return response#{"message": "Logout successful. Session cleared."}


@auth_router.post("/change-password")
async def change_user_password(
    payload: UserPasswordChange,
    db_user_record: DBUser = Depends(get_current_db_user), # Directly get the DBUser object
    db: Session = Depends(get_db) # Still need the session for commit
) -> Dict[str, str]:
    if not db_user_record.verify_password(payload.current_password):
        raise HTTPException(status_code=400, detail="Incorrect current password.")

    if payload.current_password == payload.new_password: # Check if new pass is same as old
        raise HTTPException(status_code=400, detail="New password cannot be the same as the current password.")
        
    db_user_record.hashed_password = hash_password(payload.new_password)

    try:
        # db.add(db_user_record) # Not strictly necessary if object is already session-managed
        db.commit()
        return {"message": "Password changed successfully."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
