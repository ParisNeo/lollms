# routers/auth.py
# --- Standard Library Imports ---
import traceback
import datetime
import base64
import io
from typing import Dict

# --- Third-Party Imports ---
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Response, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from PIL import Image
# --- NEW: Import Argon2 for password verification ---
import pipmaster as pm
pm.ensure_packages(["argon2-cffi"])
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from typing import Optional

from fastapi import Form, Depends, HTTPException, status
from jose import JWTError, jwt

# --- Local Application Imports ---
from backend.database_setup import (
    User as DBUser,
    Personality as DBPersonality,
    get_db,
)
from backend.models import (
    Token,
    UserCreatePublic,
    UserPublic,
    UserAuthDetails,
    UserUpdate,
    UserPasswordChange,
)
from backend.session import (
    get_current_active_user, 
    get_current_db_user_from_token, 
    get_user_by_username, 
    user_sessions,
)

from backend.config import (
    LOLLMS_CLIENT_DEFAULTS,
    SAFE_STORE_DEFAULTS
)
from backend.security import get_password_hash, verify_password, create_access_token, decode_access_token
from backend.settings import settings

# --- Auth API Router ---
auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# --- NEW: Argon2 password hasher instance ---
ph = PasswordHasher()


@auth_router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """
    Logs in a user, handling both native bcrypt and migrated argon2 passwords.
    If a migrated password is used, it's automatically upgraded to bcrypt.
    """
    user = get_user_by_username(db, username=form_data.username)

    is_password_correct = False
    
    if user:
        # --- MODIFIED: Multi-hash verification logic ---
        # Check for the argon2 hash marker we added during migration
        if user.hashed_password.startswith("argon2_hash:"):
            # This is a migrated user with an old password hash
            argon2_hash = user.hashed_password.split(":", 1)[1]
            try:
                # Verify the password using the argon2 hasher
                ph.verify(argon2_hash, form_data.password)
                is_password_correct = True
                
                # --- PASSWORD UPGRADE ---
                # The old password is correct. Upgrade the hash to bcrypt.
                print(f"INFO: Upgrading password hash for migrated user: {user.username}")
                try:
                    user.hashed_password = get_password_hash(form_data.password)
                    db.commit()
                except Exception as e:
                    db.rollback()
                    print(f"ERROR: Could not upgrade password hash for user {user.username}. Error: {e}")
                    # We still allow login, but the hash won't be upgraded this time.

            except VerifyMismatchError:
                # Password was incorrect
                is_password_correct = False
            except Exception as e:
                # Handle other argon2 errors
                print(f"ERROR: Argon2 verification failed for user {user.username}. Error: {e}")
                is_password_correct = False
        else:
            # This is a standard user with a bcrypt password
            is_password_correct = verify_password(form_data.password, user.hashed_password)

    # Note: Timing attack mitigation is implicitly handled because even if a user
    # doesn't exist, we don't exit early. The `is_password_correct` flag will simply be false.
    
    if not user or not is_password_correct:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is inactive. Please wait for an administrator to approve it.",
        )

    access_token = create_access_token(data={"sub": user.username})
    
    if user.username not in user_sessions:
        print(f"INFO: Initializing session state for user: {user.username}")
        initial_lollms_model = user.lollms_model_name or settings.get("default_model_name", LOLLMS_CLIENT_DEFAULTS.get("default_model_name"))
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
            "access_token":access_token
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

@auth_router.post("/introspect")
async def introspect_token(
    token: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Verifies a token (allows other apps to authenticate users over lollms).
    """
    payload = decode_access_token(token)
    if payload is None:
        return {"active": False}
        
    username: str = payload.get("sub")
    if username is None:
        return {"active": False}

    user = get_user_by_username(db, username=username)
    if not user or not user.is_active:
        return {"active": False}

    # --- LA PARTIE ENRICHIE ---
    # Le token est valide. Retournons des informations utiles.
    return {
        "active": True,
        "username": user.username,
        "sub": user.username,
        "exp": payload.get("exp"),
        
        "user_id": user.id,
        # we can add more infos
    }

@auth_router.put("/me/icon", response_model=Dict[str, str])
async def update_my_icon(
    file: UploadFile = File(...),
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Allows a user to upload and update their profile icon.
    The image is resized, converted to PNG, and stored as a Base64 string.
    """
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
    if file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds the limit of 5MB.")

    content_type = file.content_type
    if content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Only JPG, PNG, and WEBP are accepted.")

    try:
        # Read image data into a buffer
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))

        # Resize the image to a maximum of 128x128, preserving aspect ratio
        image.thumbnail((128, 128))

        # Convert to PNG and save to a new buffer
        # Converting to PNG is good practice for consistency and transparency support.
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        
        # Get the Base64 representation
        base64_encoded_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        # Create the data URI for the frontend
        data_uri = f"data:image/png;base64,{base64_encoded_image}"

        # Save to the database
        db_user.icon = data_uri
        db.commit()

        # Update the icon in the active session if it exists
        if db_user.username in user_sessions:
            user_sessions[db_user.username]['icon'] = data_uri

        return {"message": "Icon updated successfully", "icon_url": data_uri}

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Could not process and save the image: {e}")


@auth_router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register_new_user(user_data: UserCreatePublic, db: Session = Depends(get_db)):
    """
    Handles new user registration, governed by global settings.
    """
    if not settings.get("allow_new_registrations", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User registration is currently disabled by the administrator.")

    if db.query(DBUser).filter(DBUser.username == user_data.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is already registered.")
    if db.query(DBUser).filter(DBUser.email == user_data.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account with this email address already exists.")

    registration_mode = settings.get("registration_mode", "admin_approval")
    is_active_on_creation = (registration_mode == "direct")
    
    new_user = DBUser(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        is_active=is_active_on_creation,
        is_admin=False, # New users are never admins by default
        # Set defaults for a new user from the global settings
        lollms_model_name=settings.get("default_lollms_model_name"),
        safe_store_vectorizer=settings.get("default_safe_store_vectorizer"),
        llm_ctx_size=settings.get("default_llm_ctx_size"),
        llm_temperature=settings.get("default_llm_temperature"),
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        # TODO: If mode is 'email_validation', generate and save an activation_token
        # and trigger an email sending service here.
        return new_user
    except IntegrityError:
        db.rollback()
        # This is a fallback for race conditions.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with that username or email already exists.")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create user account due to a server error.")


@auth_router.post("/logout")
async def logout(
    current_user_details: UserAuthDetails = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> Dict[str, str]:
    """
    Logs out the user by clearing their session data from the server's memory.
    """
    username = current_user_details.username
    if username in user_sessions:
        # Schedule cleanup of any active SafeStore instances
        if "safe_store_instances" in user_sessions[username]:
            for ds_id, ss_instance in user_sessions[username]["safe_store_instances"].items():
                if hasattr(ss_instance, 'close') and callable(ss_instance.close):
                    try:
                        background_tasks.add_task(ss_instance.close)
                    except Exception as e:
                        print(f"Error scheduling SafeStore {ds_id} closure for {username}: {e}")
        
        del user_sessions[username]
        print(f"INFO: User '{username}' session cleared from server memory.")
    
    return {"message": "Logout successful. Please discard your token."}


@auth_router.get("/me", response_model=UserAuthDetails)
async def get_my_details(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails: 
    """
    Returns the details of the currently authenticated user.
    """
    return current_user


@auth_router.put("/me", response_model=UserAuthDetails)
async def update_my_details(
    user_update_data: UserUpdate,
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> UserAuthDetails:
    """
    Allows a user to update their own profile information and settings.
    """
    updated_fields = user_update_data.model_dump(exclude_unset=True)
    
    if 'email' in updated_fields and updated_fields['email'] != db_user.email:
        if db.query(DBUser).filter(DBUser.email == updated_fields['email'], DBUser.id != db_user.id).first():
            raise HTTPException(status_code=400, detail="This email address is already in use by another account.")

    # Update the user object in the database
    for field, value in updated_fields.items():
        if hasattr(db_user, field):
            setattr(db_user, field, value)
    
    try:
        db.commit()
        db.refresh(db_user)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Data integrity error: {e.orig}")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"A database error occurred: {e}")

    # If critical session data changed, update the session cache
    username = db_user.username
    if username in user_sessions:
        session = user_sessions[username]
        client_needs_reinit = False
        
        if "active_personality_id" in updated_fields:
            session["active_personality_id"] = db_user.active_personality_id
        if "lollms_model_name" in updated_fields:
            session["lollms_model_name"] = db_user.lollms_model_name
            client_needs_reinit = True
        
        llm_params_to_update = [
            "llm_ctx_size", "llm_temperature", "llm_top_k", "llm_top_p",
            "llm_repeat_penalty", "llm_repeat_last_n", "put_thoughts_in_context"
        ]
        session_llm_params = session.get("llm_params", {})
        for param in llm_params_to_update:
            if param in updated_fields:
                session_key = param.replace("llm_", "") # Convert DB key to session key
                session_llm_params[session_key] = updated_fields[param]
                client_needs_reinit = True
        session["llm_params"] = {k: v for k, v in session_llm_params.items() if v is not None}
        
        if client_needs_reinit:
            session["lollms_client"] = None # Force re-initialization on next use
    
    # Return the fully updated user details by re-running the dependency
    return get_current_active_user(db_user)


@auth_router.post("/change-password", response_model=Dict[str, str])
async def change_user_password(
    payload: UserPasswordChange,
    db_user_record: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Allows an authenticated user to change their own password.
    """
    if not verify_password(payload.current_password, db_user_record.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password.")

    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password cannot be the same as the current password.")
        
    db_user_record.hashed_password = get_password_hash(payload.new_password)

    try:
        db.commit()
        return {"message": "Password changed successfully."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"A database error occurred: {e}")
