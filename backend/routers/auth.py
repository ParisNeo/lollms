# backend/routers/auth.py
import traceback
import datetime
from datetime import timezone, timedelta
import base64
import io
from typing import Dict, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Response, UploadFile, File, Form, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from PIL import Image
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt
from pydantic import BaseModel

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.config import LLMBinding as DBLLMBinding
from backend.models.user import (
    UserCreatePublic,
    UserPublic,
    UserAuthDetails,
    UserUpdate,
    UserPasswordChange,
    ForgotPasswordRequest,
    PasswordResetRequest,
    UserCreateAdmin,
    DataZoneUpdate,
    MemoryUpdate
)
from backend.models.auth import Token
from backend.session import (
    get_current_active_user, 
    get_current_db_user_from_token, 
    get_user_by_username, 
    user_sessions,
    build_lollms_client_from_params
)
from backend.config import SAFE_STORE_DEFAULTS
from backend.security import get_password_hash, verify_password, create_access_token, decode_main_access_token, create_reset_token, send_password_reset_email
from backend.settings import settings
from backend.ws_manager import manager
from backend.task_manager import task_manager, Task
from ascii_colors import trace_exception
from lollms_client import LollmsClient


auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])
ph = PasswordHasher()

class GenerateAvatarRequest(BaseModel):
    prompt: Optional[str] = None

def _generate_user_avatar_task_logic(task: Task, user_id: int, prompt: str, tti_binding_name: str, lollms_model_name:str):
    db = None
    try:
        task.set_progress(5)
        task.log("Initializing TTI client")
        db = next(get_db())
        user = db.query(DBUser).filter(DBUser.id == user_id).first()
        if not user:
            raise Exception("User not found")
        username = user.username

        tti_binding_alias = None
        tti_model_name_part = None
        if tti_binding_name and '/' in tti_binding_name:
            tti_binding_alias, tti_model_name_part = tti_binding_name.split('/', 1)

        client = build_lollms_client_from_params(
            username=username,
            tti_binding_alias=tti_binding_alias,
            tti_model_name=tti_model_name_part,
            load_llm=False,
            load_tti=True
        )
        
        if not client.tti:
            raise Exception("TTI client could not be initialized.")

        task.set_progress(20)
        task.log("Generating image")
        
        def progress_callback(progress, task_data):
            current_progress = 20 + int(progress * 0.7)
            task.set_progress(current_progress)
            task.set_description(task_data.get('status_text', 'Generating...'))

        b64_img = client.tti.paint(prompt, negative_prompt="bad quality, ugly, deformed, text, watermark", width=256, height=256, callback=progress_callback)
        
        if not b64_img:
            raise Exception("Image generation failed.")

        task.set_progress(95)
        task.log("Processing and saving icon")
        
        image_data = base64.b64decode(b64_img)
        image = Image.open(io.BytesIO(image_data))
        image.thumbnail((128, 128))
        
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        base64_encoded_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_encoded_image}"

        user.icon = data_uri
        db.commit()

        if username in user_sessions:
            user_sessions[username]['icon'] = data_uri
        
        task.log("Avatar updated!")
        task.set_progress(100)
        return {"new_icon_url": data_uri}

    except Exception as e:
        trace_exception(e)
        if db: db.rollback()
        raise
    finally:
        if db: db.close()

@auth_router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    user = db.query(DBUser).filter(
        or_(
            DBUser.username == form_data.username,
            DBUser.email == form_data.username
        )
    ).first()

    is_password_correct = False
    
    if user:
        if user.hashed_password.startswith("argon2_hash:"):
            argon2_hash = user.hashed_password.split(":", 1)
            try:
                ph.verify(argon2_hash, form_data.password)
                is_password_correct = True
                print(f"INFO: Upgrading password hash for migrated user: {user.username}")
                try:
                    user.hashed_password = get_password_hash(form_data.password)
                    db.commit()
                except Exception as e:
                    db.rollback()
                    print(f"ERROR: Could not upgrade password hash for user {user.username}. Error: {e}")
            except VerifyMismatchError:
                is_password_correct = False
            except Exception as e:
                print(f"ERROR: Argon2 verification failed for user {user.username}. Error: {e}")
                is_password_correct = False
        else:
            is_password_correct = verify_password(form_data.password, user.hashed_password)
    
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
        
        default_binding = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).order_by(DBLLMBinding.id).first()
        initial_model_name = user.lollms_model_name
        if not initial_model_name and default_binding:
            if default_binding.alias and default_binding.default_model_name:
                initial_model_name = f"{default_binding.alias}/{default_binding.default_model_name}"

        initial_vectorizer = user.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer")
        
        session_llm_params = {
            "ctx_size": user.llm_ctx_size,
            "temperature": user.llm_temperature,
            "top_k": user.llm_top_k,
            "top_p": user.llm_top_p,
            "repeat_penalty": user.llm_repeat_penalty,
            "repeat_last_n": user.llm_repeat_last_n,
        }
        session_llm_params = {k: v for k, v in session_llm_params.items() if v is not None}

        user_sessions[user.username] = {
            "safe_store_instances": {},
            "discussions": {}, "discussion_titles": {},
            "active_vectorizer": initial_vectorizer, 
            "lollms_model_name": initial_model_name,
            "llm_params": session_llm_params,
            "active_personality_id": user.active_personality_id, 
            "active_personality_prompt": None,
            "access_token":access_token
        }
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
    payload = decode_main_access_token(token)
    if payload is None:
        return {"active": False}
        
    username: str = payload.get("sub")
    if username is None:
        return {"active": False}

    user = get_user_by_username(db, username=username)
    if not user or not user.is_active:
        return {"active": False}

    return {
        "active": True,
        "username": user.username,
        "sub": user.username,
        "exp": payload.get("exp"),
        "user_id": user.id,
    }

@auth_router.put("/me/icon", response_model=Dict[str, str])
async def update_my_icon(
    file: UploadFile = File(...),
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    MAX_FILE_SIZE = 5 * 1024 * 1024
    if file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds the limit of 5MB.")

    content_type = file.content_type
    if content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Only JPG, PNG, and WEBP are accepted.")

    try:
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        image.thumbnail((128, 128))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        base64_encoded_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_encoded_image}"
        db_user.icon = data_uri
        db.commit()

        if db_user.username in user_sessions:
            user_sessions[db_user.username]['icon'] = data_uri

        return {"message": "Icon updated successfully", "icon_url": data_uri}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Could not process and save the image: {e}")

@auth_router.post("/me/generate-icon", response_model=Dict[str, Any])
async def generate_my_icon(
    payload: GenerateAvatarRequest,
    db_user: DBUser = Depends(get_current_db_user_from_token)
):
    if not db_user.tti_binding_model_name:
        raise HTTPException(status_code=400, detail="No Text-to-Image model is configured for your account.")

    user_prompt = payload.prompt
    if not user_prompt:
        name_parts = [db_user.first_name, db_user.family_name]
        full_name = " ".join(part for part in name_parts if part)
        
        prompt_parts = ["a professional and friendly avatar icon, digital art style"]
        if full_name:
            prompt_parts.append(f"for a person named {full_name}")
        if db_user.data_zone:
            prompt_parts.append(f"whose description is: {db_user.data_zone[:200]}")
        
        user_prompt = ", ".join(prompt_parts) + "."

    task = task_manager.submit_task(
        target=_generate_user_avatar_task_logic,
        name="Generate User Avatar",
        description="AI is generating a new avatar for your profile.",
        args=(db_user.id, user_prompt, db_user.tti_binding_model_name, db_user.lollms_model_name),
        owner_username=db_user.username
    )
    return task.model_dump()


@auth_router.get("/me/data-zone", response_model=Dict[str, str])
async def get_my_data_zone(
    db_user: DBUser = Depends(get_current_db_user_from_token)
):
    return {"content": db_user.data_zone or ""}

@auth_router.get("/me/memory", response_model=Dict[str, str])
async def get_my_memory(
    db_user: DBUser = Depends(get_current_db_user_from_token)
):
    return {"content": db_user.memories or ""}

@auth_router.put("/me/data-zone", status_code=status.HTTP_200_OK)
async def update_my_data_zone(
    payload: DataZoneUpdate,
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    db_user.data_zone = payload.content
    try:
        db.commit()
        return {"message": "Data zone updated successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@auth_router.put("/me/memory", status_code=status.HTTP_200_OK)
async def update_my_memory(
    payload: MemoryUpdate,
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    db_user.memories.append(title=payload.title, content=payload.content, created_at= datetime.datetime.now(timezone.utc), updated_at= datetime.datetime.now(timezone.utc))
    try:
        db.commit()
        return {"message": "Memory updated successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@auth_router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register_new_user(user_data: UserCreatePublic, db: Session = Depends(get_db)):
    if not settings.get("allow_new_registrations", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User registration is currently disabled by the administrator.")

    if db.query(DBUser).filter(DBUser.username == user_data.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is already registered.")
    if user_data.email and db.query(DBUser).filter(DBUser.email == user_data.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account with this email address already exists.")

    registration_mode = settings.get("registration_mode", "admin_approval")
    is_active_on_creation = (registration_mode == "direct")
    
    new_user = DBUser(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        is_active=is_active_on_creation,
        is_admin=False,
        lollms_model_name=settings.get("default_lollms_model_name"),
        safe_store_vectorizer=settings.get("default_safe_store_vectorizer"),
        llm_ctx_size=settings.get("default_llm_ctx_size"),
        llm_temperature=settings.get("default_llm_temperature"),
        first_login_done=True,
        user_ui_level=settings.get("default_user_ui_level", 0),
        auto_title=settings.get("default_auto_title", False)
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except IntegrityError:
        db.rollback()
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
    username = current_user_details.username
    if username in user_sessions:
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
    return current_user


@auth_router.put("/me", response_model=UserAuthDetails)
async def update_my_details(
    user_update_data: UserUpdate,
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> UserAuthDetails:
    updated_fields = user_update_data.model_dump(exclude_unset=True)
    
    if 'email' in updated_fields and updated_fields['email'] != db_user.email:
        if db.query(DBUser).filter(DBUser.email == updated_fields['email'], DBUser.id != db_user.id).first():
            raise HTTPException(status_code=400, detail="This email address is already in use by another account.")

    # Handle new fields explicitly if they are not automatically handled by setattr loop below (though loop handles them)
    # The new fields are: preferred_name, user_personal_info, share_personal_info_with_llm
    # They are part of UserUpdate so they are in updated_fields

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
                session_key = param.replace("llm_", "")
                session_llm_params[session_key] = updated_fields[param]
                client_needs_reinit = True
        session["llm_params"] = {k: v for k, v in session_llm_params.items() if v is not None}
        
        if client_needs_reinit:
            if username in user_sessions:
                user_sessions[username].pop("lollms_clients_cache", None)
                print(f"INFO: Invalidated LollmsClient cache for user '{username}'.")

    return get_current_active_user(db_user)

@auth_router.post("/change-password", response_model=Dict[str, str])
async def change_user_password(
    payload: UserPasswordChange,
    db_user_record: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
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

@auth_router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    request: ForgotPasswordRequest,
    fastapi_request: Request,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    user = db.query(DBUser).filter(
        or_(DBUser.username == request.username_or_email, DBUser.email == request.username_or_email)
    ).first()

    if user:
        recovery_mode = settings.get("password_recovery_mode", "manual")
        smtp_host = settings.get("smtp_host")
        
        is_automatic_possible = recovery_mode == 'automatic' and smtp_host and user.email

        if is_automatic_possible:
            token = create_reset_token()
            user.password_reset_token = token
            user.reset_token_expiry = datetime.datetime.now(timezone.utc) + timedelta(hours=1)
            try:
                db.commit()
                base_url = str(fastapi_request.base_url).strip('/')
                reset_link = f"{base_url}/reset-password?token={token}"
                background_tasks.add_task(send_password_reset_email, user.email, reset_link, user.username)
            except Exception as e:
                db.rollback()
                # Fallback to manual mode on DB or mail error
                await manager.broadcast_to_admins({
                    "id": 0, "sender_id": 0, "sender_username": "System Alert",
                    "receiver_id": -1, "receiver_username": "Admins",
                    "content": f"User '{user.username}' (ID: {user.id}) tried an automatic password reset, but it failed. Please assist them manually. Error: {e}",
                    "sent_at": datetime.datetime.now(timezone.utc).isoformat()
                })

        else: # Manual mode or automatic is not possible
            dm_notification = {
                "id": 0, "sender_id": 0, "sender_username": "System Alert",
                "receiver_id": -1, "receiver_username": "Admins",
                "content": f"User '{user.username}' (ID: {user.id}) has requested a password reset. Please go to the admin panel to generate a reset link for them.",
                "sent_at": datetime.datetime.now(timezone.utc).isoformat()
            }
            await manager.broadcast_to_admins(dm_notification)
    
    return {"message": "If an account with that username or email exists, a password reset process has been initiated."}

@auth_router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(request: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.password_reset_token == request.token).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token.")
    
    expiry_time = user.reset_token_expiry
    if expiry_time and expiry_time.tzinfo is None:
        expiry_time = expiry_time.replace(tzinfo=timezone.utc)

    if not expiry_time or expiry_time < datetime.datetime.now(timezone.utc):
        user.password_reset_token = None
        user.reset_token_expiry = None
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token.")

    user.hashed_password = get_password_hash(request.new_password)
    user.password_reset_token = None
    user.reset_token_expiry = None
    
    try:
        db.commit()
        return {"message": "Your password has been reset successfully. You can now log in."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="An error occurred while resetting the password.")

@auth_router.get("/admin_status", response_model=Dict[str, bool])
async def get_admin_status(db: Session = Depends(get_db)):
    """
    Checks if any admin user exists in the database.
    """
    admin_exists = db.query(DBUser).filter(DBUser.is_admin == True).first() is not None
    return {"admin_exists": admin_exists}

@auth_router.post("/create_first_admin", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def create_first_admin(user_data: UserCreateAdmin, db: Session = Depends(get_db)):
    """
    Creates the very first admin user account.
    This endpoint is only accessible if no admin users exist in the database.
    """
    admin_exists = db.query(DBUser).filter(DBUser.is_admin == True).first() is not None
    if admin_exists:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin user already exists. Cannot create another first admin.")

    if db.query(DBUser).filter(DBUser.username == user_data.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is already registered.")
    if user_data.email and db.query(DBUser).filter(DBUser.email == user_data.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account with this email address already exists.")

    # Ensure the first user is an admin
    new_user = DBUser(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        is_admin=True,  # Force to be admin
        is_active=True, # Force to be active
        lollms_model_name=settings.get("default_lollms_model_name"),
        safe_store_vectorizer=settings.get("default_safe_store_vectorizer"),
        llm_ctx_size=settings.get("default_llm_ctx_size"),
        llm_temperature=settings.get("default_llm_temperature"),
        user_ui_level=4,
        auto_title=True,
        first_login_done=False
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        print(f"INFO: First admin user '{new_user.username}' created successfully.")
        return new_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with that username or email already exists.")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create first admin account due to a server error.")
