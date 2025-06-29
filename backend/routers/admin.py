import json
import shutil
import traceback
import uuid
from pathlib import Path
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.database_setup import (
    User as DBUser,
    GlobalConfig as DBGlobalConfig,
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
)
from backend.session import (
    get_user_data_root,
    get_current_admin_user,
    get_user_temp_uploads_path,
    user_sessions,
)
from backend.settings import settings
from backend.config import INITIAL_ADMIN_USER_CONFIG
from backend.migration_utils import run_openwebui_migration


admin_router = APIRouter(prefix="/api/admin", tags=["Administration"], dependencies=[Depends(get_current_admin_user)])

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
        lollms_model_name=user_data.lollms_model_name or settings.get("default_lollms_model_name"),
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

@admin_router.post("/users/{user_id}/activate", response_model=UserPublic)
async def admin_activate_user(user_id: int, db: Session = Depends(get_db)):
    user_to_activate = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_activate:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user_to_activate.is_active = True
    user_to_activate.activation_token = None
    
    try:
        db.commit()
        db.refresh(user_to_activate)
        return user_to_activate
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"A database error occurred: {e}")

@admin_router.post("/users/{user_id}/reset-password", response_model=Dict[str, str])
async def admin_reset_user_password(user_id: int, payload: UserPasswordResetAdmin, db: Session = Depends(get_db)):
    user_to_update = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user_to_update.hashed_password = hash_password(payload.new_password)
    try:
        db.commit()
        return {"message": f"Password for user '{user_to_update.username}' has been successfully reset."}
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