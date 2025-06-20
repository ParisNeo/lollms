
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
#from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import (
    HTMLResponse,
    StreamingResponse,
    JSONResponse,
    FileResponse,
)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
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

from backend.session import (get_current_active_user, get_current_db_user_from_token, get_user_lollms_client, get_user_temp_uploads_path, get_user_by_username, user_sessions)
from backend.config import (LOLLMS_CLIENT_DEFAULTS, SAFE_STORE_DEFAULTS)
from backend.security import get_password_hash, verify_password, create_access_token
from backend.models import Token, TokenData

auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])
#security = HTTPBasic()


@auth_router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """
    Logs in a user and returns a JWT access token.
    This function is designed to be resistant to timing attacks for username enumeration.
    """
    user = get_user_by_username(db, username=form_data.username)

    # --- TIMING ATTACK MITIGATION ---
    # We perform a password verification even if the user is not found.
    # This prevents attackers from guessing valid usernames by measuring response times.
    if user:
        # User exists, use their actual hashed password.
        hashed_password = user.hashed_password
        is_user_valid = True
    else:
        # User does not exist. Create a dummy hash for a bogus comparison.
        # The content of the string doesn't matter, as it will never match.
        # This ensures the verify_password call takes a similar amount of time.
        hashed_password = get_password_hash("dummy_password_for_timing_attack_mitigation")
        is_user_valid = False

    # Perform the verification. This call will now always execute.
    is_password_correct = verify_password(form_data.password, hashed_password)

    # Now, check the combined result.
    if not is_user_valid or not is_password_correct:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # If we reach here, both the user and password are valid.
    # Proceed with token creation and session initialization as before.
    access_token = create_access_token(
        data={"sub": user.username}
    )
    # Initialize user session upon successful login if not already present
    # This ensures that subsequent calls to get_current_active_user have a session to work with
    if user.username not in user_sessions:
        print(f"INFO: Initializing session state for user: {user.username}")
        initial_lollms_model = user.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
        initial_vectorizer = user.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer")
        
        session_llm_params = {
            "ctx_size": user.llm_ctx_size if user.llm_ctx_size is not None else LOLLMS_CLIENT_DEFAULTS.get("ctx_size"),
            "temperature": user.llm_temperature if user.llm_temperature is not None else LOLLMS_CLIENT_DEFAULTS.get("temperature"),
            "top_k": user.llm_top_k if user.llm_top_k is not None else LOLLMS_CLIENT_DEFAULTS.get("top_k"),
            "top_p": user.llm_top_p if user.llm_top_p is not None else LOLLMS_CLIENT_DEFAULTS.get("top_p"),
            "repeat_penalty": user.llm_repeat_penalty if user.llm_repeat_penalty is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
            "repeat_last_n": user.llm_repeat_last_n if user.llm_repeat_last_n is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n"),
        }
        session_llm_params = {k: v for k, v in session_llm_params.items() if v is not None}

        user_sessions[user.username] = {
            "lollms_client": None, "safe_store_instances": {}, 
            "discussions": {}, "discussion_titles": {},
            "active_vectorizer": initial_vectorizer, 
            "lollms_model_name": initial_lollms_model,
            "llm_params": session_llm_params,
            # Session stores active personality details for quick access if needed by LollmsClient
            "active_personality_id": user.active_personality_id, 
            "active_personality_prompt": None, # Will be loaded if personality is active
        }
        # If user has an active personality, load its prompt into session
        if user.active_personality_id:
            db_session_for_init = next(get_db())
            try:
                active_pers = db_session_for_init.query(DBPersonality.prompt_text).filter(DBPersonality.id == user.active_personality_id).scalar()
                if active_pers:
                    user_sessions[user.username]["active_personality_prompt"] = active_pers
            finally:
                db_session_for_init.close()

    return {"access_token": access_token, "token_type": "bearer"}


@auth_router.post("/logout")
async def logout(
    response: Response, # To potentially clear cookies if you use them
    current_user_details: UserAuthDetails = Depends(get_current_active_user), # Authenticates
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> Dict[str, str]:
    username = current_user_details.username
    
    # Your existing session cleanup logic
    if username in user_sessions:
        # temp_dir = get_user_temp_uploads_path(username) # Define this function
        # if temp_dir.exists():
        #     background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)
        
        if "safe_store_instances" in user_sessions[username]:
            for ds_id, ss_instance in user_sessions[username]["safe_store_instances"].items():
                if hasattr(ss_instance, 'close') and callable(ss_instance.close):
                    try: background_tasks.add_task(ss_instance.close)
                    except Exception as e_ss_close: print(f"Error closing SafeStore {ds_id} for {username} on logout: {e_ss_close}")
        
        del user_sessions[username] # Clear the in-memory session data
        print(f"INFO: User '{username}' session cleared from server.")

    # For JWT, logout is primarily client-side (deleting the token).
    # Server-side, if you implement a token denylist, you'd add the token JTI here.
    # For now, we just clear the session data. The client should discard the token.
    
    # The 401 is not strictly necessary here if the client correctly removes the token.
    # A 200 OK with a success message is also fine.
    # response.status_code = status.HTTP_200_OK 
    return {"message": "Logout successful. Please discard your token."}


@auth_router.get("/me", response_model=UserAuthDetails)
async def get_my_details(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails: 
    return current_user
# New endpoint for updating user settings
@auth_router.put("/me", response_model=UserAuthDetails) # Returns the updated user details
async def update_my_details(
    user_update_data: UserUpdate,
    db_user: DBUser = Depends(get_current_db_user_from_token), # Get the DBUser object
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
            if field in ["lollms_model_name", "llm_ctx_size", "llm_temperature", "llm_top_k", "llm_top_p", "llm_repeat_penalty", "llm_repeat_last_n", "put_thoughts_in_context"]:
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
            
            if "llm_ctx_size" in updated_fields: session_llm_params["ctx_size"] = db_user.llm_ctx_size
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
            llm_ctx_size=current_session_llm_params.get("ctx_size"),
            llm_temperature=current_session_llm_params.get("temperature"),
            llm_top_k=current_session_llm_params.get("top_k"),
            llm_top_p=current_session_llm_params.get("top_p"),
            llm_repeat_penalty=current_session_llm_params.get("repeat_penalty"),
            llm_repeat_last_n=current_session_llm_params.get("repeat_last_n"),
            put_thoughts_in_context=current_session_llm_params.get("put_thoughts_in_context"),
            rag_top_k=db_user.rag_top_k,
            max_rag_len=db_user.max_rag_len,
            rag_n_hops=db_user.rag_n_hops,
            rag_min_sim_percent=db_user.rag_min_sim_percent,
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


@auth_router.post("/change-password")
async def change_user_password(
    payload: UserPasswordChange,
    db_user_record: DBUser = Depends(get_current_db_user_from_token), # Directly get the DBUser object
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
