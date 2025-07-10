import json
import shutil
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from lollms_client.lollms_llm_binding import get_available_bindings

from backend.database_setup import (
    User as DBUser,
    GlobalConfig as DBGlobalConfig,
    LLMBinding as DBLLMBinding,
    get_db,
    hash_password,
)
from backend.models import (
    UserAuthDetails,
    UserCreateAdmin,
    UserPasswordResetAdmin,
    UserPublic,
    GlobalConfigPublic,
    GlobalConfigUpdate,
    AdminUserUpdate,
    ModelInfo,
    ForceSettingsPayload,
    EmailUsersRequest,
    AdminDashboardStats,
    EnhanceEmailRequest,
    EnhancedEmailResponse,
    LLMBindingCreate,
    LLMBindingUpdate,
    LLMBindingPublic,
)
from backend.session import (
    get_user_data_root,
    get_current_admin_user,
    get_user_temp_uploads_path,
    user_sessions,
    get_user_lollms_client,
)
from backend.security import create_reset_token, send_generic_email
from backend.settings import settings
from backend.config import INITIAL_ADMIN_USER_CONFIG
from backend.migration_utils import run_openwebui_migration


admin_router = APIRouter(prefix="/api/admin", tags=["Administration"], dependencies=[Depends(get_current_admin_user)])

# --- Bindings Management Endpoints ---

@admin_router.get("/bindings/available_types", response_model=List[str])
async def get_available_binding_types():
    try:
        return get_available_bindings()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get available binding types: {e}")

@admin_router.get("/bindings", response_model=List[LLMBindingPublic])
async def get_all_bindings(db: Session = Depends(get_db)):
    return db.query(DBLLMBinding).all()

@admin_router.post("/bindings", response_model=LLMBindingPublic, status_code=201)
async def create_binding(binding_data: LLMBindingCreate, db: Session = Depends(get_db)):
    if db.query(DBLLMBinding).filter(DBLLMBinding.alias == binding_data.alias).first():
        raise HTTPException(status_code=400, detail="A binding with this alias already exists.")
    
    new_binding = DBLLMBinding(**binding_data.model_dump())
    try:
        db.add(new_binding)
        db.commit()
        db.refresh(new_binding)
        return new_binding
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="A binding with this alias already exists.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@admin_router.put("/bindings/{binding_id}", response_model=LLMBindingPublic)
async def update_binding(binding_id: int, update_data: LLMBindingUpdate, db: Session = Depends(get_db)):
    binding_to_update = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding_to_update:
        raise HTTPException(status_code=404, detail="Binding not found.")
    
    if update_data.alias and update_data.alias != binding_to_update.alias:
        if db.query(DBLLMBinding).filter(DBLLMBinding.alias == update_data.alias).first():
            raise HTTPException(status_code=400, detail="A binding with the new alias already exists.")

    update_dict = update_data.model_dump(exclude_unset=True)
    if 'service_key' in update_dict and not update_dict['service_key']:
        del update_dict['service_key']

    for key, value in update_dict.items():
        setattr(binding_to_update, key, value)
    
    try:
        db.commit()
        db.refresh(binding_to_update)
        # Invalidate cached clients
        for session in user_sessions.values():
            if "lollms_clients" in session and binding_to_update.alias in session["lollms_clients"]:
                del session["lollms_clients"][binding_to_update.alias]
        return binding_to_update
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@admin_router.delete("/bindings/{binding_id}", response_model=Dict[str, str])
async def delete_binding(binding_id: int, db: Session = Depends(get_db)):
    binding_to_delete = db.query(DBLLMBinding).filter(DBLLMBinding.id == binding_id).first()
    if not binding_to_delete:
        raise HTTPException(status_code=404, detail="Binding not found.")
    
    try:
        db.delete(binding_to_delete)
        db.commit()
        return {"message": "Binding deleted successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


# --- Existing Admin Endpoints ---

@admin_router.get("/stats", response_model=AdminDashboardStats)
async def get_dashboard_stats(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    
    total_users = db.query(DBUser).count()
    
    active_24h_threshold = now - timedelta(hours=24)
    active_users_24h = db.query(DBUser).filter(DBUser.last_activity_at > active_24h_threshold).count()

    new_7d_threshold = now - timedelta(days=7)
    new_users_7d = db.query(DBUser).filter(DBUser.created_at > new_7d_threshold).count()
    
    registration_mode = settings.get("registration_mode", "admin_approval")
    pending_approval = 0
    if registration_mode == "admin_approval":
        pending_approval = db.query(DBUser).filter(DBUser.is_active == False, DBUser.activation_token.isnot(None)).count()
    
    pending_password_resets = db.query(DBUser).filter(
        DBUser.password_reset_token.isnot(None), 
        DBUser.reset_token_expiry > now
    ).count()

    return AdminDashboardStats(
        total_users=total_users,
        active_users_24h=active_users_24h,
        new_users_7d=new_users_7d,
        pending_approval=pending_approval,
        pending_password_resets=pending_password_resets
    )

@admin_router.post("/email-users", status_code=202)
async def email_users(
    payload: EmailUsersRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    email_mode = settings.get("password_recovery_mode")
    if email_mode not in ["automatic", "system_mail"]:
        raise HTTPException(status_code=412, detail=f"Email sending is not enabled or is set to manual. Current mode: '{email_mode}'.")

    if not payload.user_ids:
        raise HTTPException(status_code=400, detail="No users selected to email.")

    users_to_email = db.query(DBUser).filter(DBUser.id.in_(payload.user_ids)).all()

    if not users_to_email:
        raise HTTPException(status_code=404, detail="No valid users found for the provided IDs.")

    sent_count = 0
    for user in users_to_email:
        if user.email and user.receive_notification_emails:
            background_tasks.add_task(
                send_generic_email, 
                user.email, 
                payload.subject, 
                payload.body, 
                payload.background_color,
                payload.send_as_text
            )
            sent_count += 1
    
    return {"message": f"Email sending initiated for {sent_count} users."}

@admin_router.post("/enhance-email", response_model=EnhancedEmailResponse)
async def enhance_email_with_ai(
    payload: EnhanceEmailRequest,
    current_admin: UserAuthDetails = Depends(get_current_admin_user)
):
    try:
        # This will use the admin's default model for now.
        lc = get_user_lollms_client(current_admin.username)
        
        if payload.prompt and payload.prompt.strip():
            prompt = f"""{payload.prompt.strip()}

You must return ONLY a single valid JSON object with three keys: "subject", "body", and "background_color".
Do not add any text or explanation before or after the JSON object.

Here is the email content to work on:
---
Original Subject:
{payload.subject}

Original Body:
{payload.body}

Current Background Color:
{payload.background_color or "#FFFFFF"}
---
"""
        else:
            prompt = f"""You are an expert copywriter and designer. Your task is to enhance the following email draft to make it more engaging, professional, and clear.
You must also suggest a suitable HTML background color for the email's theme.
Return ONLY a single valid JSON object with three keys: "subject", "body", and "background_color". The background_color should be a valid hex code (e.g., "#f0f4f8").
Do not add any text or explanation before or after the JSON object.

Original Subject:
{payload.subject}

Original Body:
{payload.body}

Current Background Color:
{payload.background_color or "#FFFFFF"}
"""
        
        raw_response = lc.generate_text(prompt, stream=False)

        json_start = raw_response.find('{')
        json_end = raw_response.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            raise HTTPException(status_code=500, detail="AI did not return a valid JSON object.")
            
        json_string = raw_response[json_start:json_end]

        try:
            enhanced_data = json.loads(json_string)
            if "subject" not in enhanced_data or "body" not in enhanced_data:
                 raise ValueError("The JSON response from the AI is missing 'subject' or 'body' keys.")
            return EnhancedEmailResponse(
                subject=enhanced_data.get("subject", payload.subject),
                body=enhanced_data.get("body", payload.body),
                background_color=enhanced_data.get("background_color", payload.background_color)
            )
        except (json.JSONDecodeError, ValueError) as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {e}")

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred while enhancing the email: {e}")

@admin_router.get("/available-models", response_model=List[ModelInfo])
async def get_available_models(current_admin: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    all_models = []
    active_bindings = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()

    for binding in active_bindings:
        try:
            # We get a client instance specifically for this binding to list its models
            lc = get_user_lollms_client(current_admin.username, binding.alias)
            models = lc.listModels()
            
            if isinstance(models, list):
                for item in models:
                    model_id = None
                    if isinstance(item, str):
                        model_id = item
                    elif isinstance(item, dict):
                        model_id = item.get("name") or item.get("id") or item.get("model_name")
                    
                    if model_id:
                        all_models.append({
                            "id": f"{binding.alias}/{model_id}",
                            "name": f"{binding.alias}/{model_id}"
                        })
        except Exception as e:
            print(f"WARNING: Could not fetch models from binding '{binding.alias}': {e}")
            continue

    unique_models = {m["id"]: m for m in all_models}
    sorted_models = sorted(list(unique_models.values()), key=lambda x: x['name'])

    if not sorted_models:
        raise HTTPException(status_code=404, detail="No models found from any active bindings.")
    
    return sorted_models

@admin_router.post("/force-settings-once", response_model=Dict[str, str])
async def force_settings_once(payload: ForceSettingsPayload, db: Session = Depends(get_db)):
    forced_model = payload.model_name
    forced_ctx = payload.context_size

    if not forced_model:
        raise HTTPException(status_code=400, detail="A model name must be provided in the payload.")

    try:
        users = db.query(DBUser).all()
        for user in users:
            user.lollms_model_name = forced_model
            if forced_ctx is not None:
                user.llm_ctx_size = forced_ctx
        
        db.commit()
        
        user_sessions.clear()
        
        return {"message": f"Successfully applied model '{forced_model}' and context size '{forced_ctx or 'N/A'}' to {len(users)} users."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error while forcing settings: {e}")

@admin_router.post("/import-openwebui", response_model=Dict[str, str])
async def import_openwebui_data(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_admin: UserAuthDetails = Depends(get_current_admin_user)
):
    if not file:
        raise HTTPException(status_code=400, detail="No file was uploaded.")
    
    if file.filename != "webui.db":
        raise HTTPException(status_code=400, detail="Invalid file uploaded. Please upload the 'webui.db' file from OpenWebUI.")

    temp_import_dir = get_user_temp_uploads_path(current_admin.username) / f"owui_import_{uuid.uuid4()}"
    temp_import_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"INFO: Staging OpenWebUI import file in: {temp_import_dir}")
    
    try:
        file_path = temp_import_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    background_tasks.add_task(run_openwebui_migration, str(temp_import_dir))

    return {"message": "Migration process started in the background. Check server logs for progress."}

@admin_router.get("/settings", response_model=List[GlobalConfigPublic])
async def admin_get_global_settings(db: Session = Depends(get_db)):
    db_configs = db.query(DBGlobalConfig).order_by(DBGlobalConfig.category, DBGlobalConfig.key).all()
    response_models = []
    for config in db_configs:
        try:
            stored_data = json.loads(config.value)
            response_models.append(GlobalConfigPublic(
                key=config.key,
                value=stored_data.get('value'),
                type=stored_data.get('type', 'unknown'),
                description=config.description,
                category=config.category,
            ))
        except (json.JSONDecodeError, TypeError):
            response_models.append(GlobalConfigPublic(
                key=config.key, value=None, type='error',
                description=f"Error parsing value: {config.value}",
                category=config.category,
            ))
    return response_models

@admin_router.put("/settings", response_model=Dict[str, str])
async def admin_update_global_settings(
    update_data: GlobalConfigUpdate,
    db: Session = Depends(get_db)
):
    updated_keys = []
    try:
        for key, new_value in update_data.configs.items():
            db_config = db.query(DBGlobalConfig).filter(DBGlobalConfig.key == key).first()
            if db_config:
                if key == 'smtp_password' and not new_value:
                    continue
                stored_data = json.loads(db_config.value)
                stored_data['value'] = new_value
                db_config.value = json.dumps(stored_data)
                updated_keys.append(key)
            else:
                print(f"WARNING: Admin tried to update non-existent setting key: {key}")

        if updated_keys:
            db.commit()
            settings.refresh()
            print(f"INFO: Admin updated global settings: {', '.join(updated_keys)}")
        
        return {"message": f"Successfully updated {len(updated_keys)} settings."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error while updating settings: {e}")

@admin_router.get("/users", response_model=List[UserPublic])
async def admin_get_all_users(db: Session = Depends(get_db)) -> List[DBUser]:
    return db.query(DBUser).all()

@admin_router.get("/active-sessions", response_model=List[str])
async def get_active_sessions():
    return list(user_sessions.keys())

@admin_router.post("/users", response_model=UserPublic, status_code=201)
async def admin_add_new_user(user_data: UserCreateAdmin, db: Session = Depends(get_db)) -> DBUser:
    if db.query(DBUser).filter(DBUser.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username is already registered.")
    if user_data.email and db.query(DBUser).filter(DBUser.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email is already in use by another account.")

    new_db_user = DBUser(
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        is_admin=user_data.is_admin,
        email=user_data.email,
        lollms_model_name=user_data.lollms_model_name,
        safe_store_vectorizer=user_data.safe_store_vectorizer or settings.get("default_safe_store_vectorizer"),
        llm_ctx_size=user_data.llm_ctx_size if user_data.llm_ctx_size is not None else settings.get("default_llm_ctx_size"),
        llm_temperature=user_data.llm_temperature if user_data.llm_temperature is not None else settings.get("default_llm_temperature"),
        is_active=True
    )
    try:
        db.add(new_db_user)
        db.commit()
        db.refresh(new_db_user)
        return new_db_user
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"A user with that username or email already exists. Original error: {e.orig}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"A database error occurred: {e}")

@admin_router.put("/users/{user_id}", response_model=UserPublic)
async def admin_update_user(user_id: int, update_data: AdminUserUpdate, db: Session = Depends(get_db), current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    user_to_update = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found.")
    
    if user_to_update.id == current_admin.id and update_data.is_admin is False:
        raise HTTPException(status_code=403, detail="Administrators cannot revoke their own admin status.")
    
    initial_admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
    if initial_admin_username and user_to_update.username == initial_admin_username and update_data.is_admin is False:
        raise HTTPException(status_code=403, detail="The initial superadmin account cannot have its admin status revoked.")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(user_to_update, key, value)
    
    try:
        db.commit()
        db.refresh(user_to_update)
        
        if user_to_update.username in user_sessions:
            user_sessions[user_to_update.username]["lollms_clients"] = {}
        
        return user_to_update
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"A database error occurred: {e}")

@admin_router.post("/users/{user_id}/activate", response_model=UserPublic)
async def admin_activate_user(user_id: int, db: Session = Depends(get_db)):
    user_to_activate = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_activate:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user_to_activate.is_active = True
    user_to_activate.activation_token = None
    user_to_activate.password_reset_token = None
    user_to_activate.reset_token_expiry = None

    try:
        db.commit()
        db.refresh(user_to_activate)
        return user_to_activate
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"A database error occurred: {e}")

@admin_router.post("/users/{user_id}/deactivate", response_model=UserPublic)
async def admin_deactivate_user(user_id: int, db: Session = Depends(get_db), current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    user_to_deactivate = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_deactivate:
        raise HTTPException(status_code=404, detail="User not found.")
    
    if user_to_deactivate.id == current_admin.id:
        raise HTTPException(status_code=403, detail="Administrators cannot deactivate their own accounts.")
    
    user_to_deactivate.is_active = False
    
    try:
        db.commit()
        db.refresh(user_to_deactivate)
        if user_to_deactivate.username in user_sessions:
            del user_sessions[user_to_deactivate.username]
        return user_to_deactivate
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"A database error occurred: {e}")

@admin_router.post("/users/{user_id}/reset-password", response_model=Dict[str, str])
async def admin_reset_user_password(user_id: int, payload: UserPasswordResetAdmin, db: Session = Depends(get_db)):
    user_to_update = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user_to_update.hashed_password = hash_password(payload.new_password)
    user_to_update.password_reset_token = None
    user_to_update.reset_token_expiry = None

    try:
        db.commit()
        return {"message": f"Password for user '{user_to_update.username}' has been successfully reset."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"A database error occurred: {e}")

@admin_router.post("/users/{user_id}/generate-reset-link", response_model=Dict[str, str])
async def admin_generate_password_reset_link(user_id: int, request: Request, db: Session = Depends(get_db)):
    user_to_update = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found.")

    token = create_reset_token()
    user_to_update.password_reset_token = token
    user_to_update.reset_token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    
    try:
        db.commit()
        base_url = str(request.base_url).strip('/')
        reset_link = f"{base_url}/reset-password?token={token}"
        return {"reset_link": reset_link}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"A database error occurred: {e}")

@admin_router.delete("/users/{user_id}", response_model=Dict[str, str])
async def admin_remove_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    user_to_delete = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User not found.")
    
    initial_admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
    if initial_admin_username and user_to_delete.username == initial_admin_username:
        raise HTTPException(status_code=403, detail="The initial superadmin account cannot be deleted.")
    if user_to_delete.id == current_admin.id:
        raise HTTPException(status_code=403, detail="Administrators cannot delete their own accounts.")
    
    user_data_dir_to_delete = get_user_data_root(user_to_delete.username)

    try:
        if user_to_delete.username in user_sessions:
            del user_sessions[user_to_delete.username]

        db.delete(user_to_delete)
        db.commit()
        
        if user_data_dir_to_delete.exists():
            background_tasks.add_task(shutil.rmtree, user_data_dir_to_delete, ignore_errors=True)
            
        return {"message": f"User '{user_to_delete.username}' and their data have been deleted."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"A database or file system error occurred during user deletion: {e}")