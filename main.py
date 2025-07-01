# -*- coding: utf-8 -*-
import os
import shutil
import uuid
import json
import datetime
import traceback
from pathlib import Path
from typing import List, Dict, Optional, Any, cast

from fastapi import (
    FastAPI, HTTPException, Depends, Request, File, UploadFile,
    Form, APIRouter, Response, Query, BackgroundTasks
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, constr
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename

from backend.config import (
    APP_VERSION, APP_DATA_DIR, APP_DB_URL, LOLLMS_CLIENT_DEFAULTS,
    INITIAL_ADMIN_USER_CONFIG, SERVER_CONFIG, TEMP_UPLOADS_DIR_NAME, DEFAULT_PERSONALITIES
)
from backend.database_setup import (
    init_database, get_db, hash_password,
    User as DBUser, Personality as DBPersonality, DataStore as DBDataStore,
    SharedDataStoreLink as DBSharedDataStoreLink
)
from backend.discussion import LegacyDiscussion
from backend.session import (
    get_user_data_root, get_user_discussion_path, get_current_active_user,
    get_user_lollms_client, get_user_temp_uploads_path, user_sessions, get_safe_store_instance,
    get_datastore_db_path
)
from lollms_client import LollmsClient, LollmsDataManager
from backend.models import UserLLMParams, UserAuthDetails, DataStoreCreate, DataStoreEdit, DataStoreShareRequest, DataStorePublic

from backend.routers.auth import auth_router
from backend.routers.discussion import discussion_router
from backend.routers.admin import admin_router
from backend.routers.languages import languages_router
from backend.routers.personalities import personalities_router
from backend.routers.friends import friends_router
from backend.routers.dm import dm_router
from backend.routers.stores import store_files_router
from backend.routers.mcp import mcp_router, discussion_tools_router
from backend.routers.social import social_router
from backend.routers.users import users_router
from backend.routers.dm_ws import dm_ws_router

app = FastAPI(
    title="Simplified LoLLMs Chat API",
    description="API for a multi-user LoLLMs and SafeStore chat application with social features.",
    version=APP_VERSION,
)

@app.on_event("startup")
async def on_startup() -> None:
    init_database(APP_DB_URL)
    print("Database initialized.")
    print("\n--- Running Automated Discussion Migration ---")
    db_session = None
    try:
        db_session = next(get_db())
        all_users = db_session.query(DBUser).all()
        for user in all_users:
            username = user.username
            old_discussion_path = get_user_discussion_path(username)
            if not (old_discussion_path.exists() and old_discussion_path.is_dir()):
                continue
            print(f"Found legacy discussion folder for '{username}'. Starting migration...")
            if username not in user_sessions:
                user_sessions[username] = {"lollms_client": None, "lollms_model_name": user.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name"), "llm_params": {}}
            db_path = get_user_data_root(username) / "discussions.db"
            dm = LollmsDataManager(db_path=f"sqlite:///{db_path.resolve()}")
            migrated_count = 0
            for file_path in old_discussion_path.glob("*.yaml"):
                discussion_db_session = None
                try:
                    old_disc = LegacyDiscussion.load_from_yaml(file_path)
                    if not old_disc: continue
                    discussion_db_session = dm.get_session()
                    if discussion_db_session.query(dm.DiscussionModel).filter_by(id=old_disc.discussion_id).first():
                        discussion_db_session.close()
                        continue
                    new_db_disc_orm = dm.DiscussionModel(id=old_disc.discussion_id, discussion_metadata={"title": old_disc.title, "rag_datastore_ids": old_disc.rag_datastore_ids}, active_branch_id=old_disc.active_branch_id)
                    discussion_db_session.add(new_db_disc_orm)
                    for msg in old_disc.messages:
                        msg_orm = dm.MessageModel(id=msg.id, discussion_id=new_db_disc_orm.id, parent_id=msg.parent_id, sender=msg.sender, sender_type=msg.sender_type, content=msg.content, created_at=msg.created_at, binding_name=msg.binding_name, model_name=msg.model_name, tokens=msg.token_count, message_metadata={"sources": msg.sources, "steps": msg.steps})
                        discussion_db_session.add(msg_orm)
                    discussion_db_session.commit()
                    migrated_count += 1
                except Exception as e:
                    if discussion_db_session: discussion_db_session.rollback()
                    print(f"    - FAILED to migrate {file_path.name}: {e}")
                finally:
                    if discussion_db_session: discussion_db_session.close()
            if migrated_count > 0:
                backup_path = old_discussion_path.parent / f"{old_discussion_path.name}_migrated_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                shutil.move(str(old_discussion_path), str(backup_path))
                print(f"Successfully migrated {migrated_count} discussions and backed up legacy folder.")
            if username in user_sessions: user_sessions[username]['lollms_client'] = None
    except Exception as e:
        print(f"CRITICAL ERROR during migration: {e}")
    finally:
        if db_session: db_session.close()
    print("--- Migration Finished ---\n")

    db_for_defaults: Optional[Session] = None
    try:
        db_for_defaults = next(get_db())
        admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
        admin_password = INITIAL_ADMIN_USER_CONFIG.get("password")
        if admin_username and admin_password and not db_for_defaults.query(DBUser).filter(DBUser.username == admin_username).first():
            new_admin = DBUser(username=admin_username, hashed_password=hash_password(admin_password), is_admin=True)
            db_for_defaults.add(new_admin)
            print(f"INFO: Initial admin user '{admin_username}' created successfully.")
        
        for default_pers_data in DEFAULT_PERSONALITIES:
            if not db_for_defaults.query(DBPersonality).filter(DBPersonality.name == default_pers_data["name"], DBPersonality.is_public == True, DBPersonality.owner_user_id == None).first():
                new_pers = DBPersonality(name=default_pers_data["name"], author=default_pers_data.get("author", "System"), description=default_pers_data.get("description"), prompt_text=default_pers_data["prompt_text"], is_public=True, owner_user_id=None, **{k:v for k,v in default_pers_data.items() if k not in ["name", "author", "description", "prompt_text"]})
                db_for_defaults.add(new_pers)
                print(f"INFO: Added default public personality: '{new_pers.name}'")
        db_for_defaults.commit()
    except Exception as e:
        if db_for_defaults: db_for_defaults.rollback()
    finally:
        if db_for_defaults: db_for_defaults.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(discussion_router)
app.include_router(admin_router)
app.include_router(languages_router)
app.include_router(personalities_router)
app.include_router(mcp_router)
app.include_router(discussion_tools_router)
app.include_router(store_files_router)
app.include_router(social_router)
app.include_router(friends_router)
app.include_router(dm_router)
app.include_router(users_router)
app.include_router(dm_ws_router)

upload_router = APIRouter(prefix="/api/upload", tags=["Uploads"])
MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_UPLOADS_PER_MESSAGE = 5
@upload_router.post("/chat_image", response_model=List[Dict[str,str]])
async def upload_chat_images(files: List[UploadFile] = File(...), current_user: UserAuthDetails = Depends(get_current_active_user)):
    if len(files) > MAX_IMAGE_UPLOADS_PER_MESSAGE: raise HTTPException(status_code=400, detail=f"Cannot upload more than {MAX_IMAGE_UPLOADS_PER_MESSAGE} images at once.")
    username = current_user.username
    temp_uploads_path = get_user_temp_uploads_path(username)
    temp_uploads_path.mkdir(parents=True, exist_ok=True)
    uploaded_file_infos = []
    for file_upload in files:
        if not file_upload.content_type or not file_upload.content_type.startswith("image/"): raise HTTPException(status_code=400, detail=f"File '{file_upload.filename}' is not a valid image type.")
        file_upload.file.seek(0, os.SEEK_END)
        if file_upload.file.tell() > MAX_IMAGE_SIZE_MB * 1024 * 1024: raise HTTPException(status_code=413, detail=f"Image '{file_upload.filename}' exceeds max size of {MAX_IMAGE_SIZE_MB}MB.")
        file_upload.file.seek(0)
        s_filename_base, s_filename_ext = os.path.splitext(secure_filename(file_upload.filename or "image"))
        if not s_filename_ext: s_filename_ext = ".png"
        final_filename = f"{s_filename_base}_{uuid.uuid4().hex[:8]}{s_filename_ext}"
        target_file_path = temp_uploads_path / final_filename
        try:
            with open(target_file_path, "wb") as buffer: shutil.copyfileobj(file_upload.file, buffer)
            uploaded_file_infos.append({"filename": file_upload.filename, "server_path": f"{TEMP_UPLOADS_DIR_NAME}/{final_filename}"})
        except Exception as e: raise HTTPException(status_code=500, detail=f"Could not save uploaded image '{file_upload.filename}': {str(e)}")
        finally: await file_upload.close()
    return uploaded_file_infos
app.include_router(upload_router)

# --- LoLLMs Configuration API ---
lollms_config_router = APIRouter(prefix="/api/config", tags=["LoLLMs Configuration"])

@lollms_config_router.get("/lollms-models", response_model=List[Dict[str, str]])
async def get_available_lollms_models(current_user: UserAuthDetails = Depends(get_current_active_user)):
    """
    Safely retrieves a list of available LLM models from the LollmsClient,
    with improved error handling and more robust parsing.
    """
    lc = get_user_lollms_client(current_user.username)
    models_set = set()

    # --- Step 1: Try to get models from the binding ---
    try:
        binding_models = lc.listModels()
        if isinstance(binding_models, list):
            # Use a clear for-loop for robust parsing
            for item in binding_models:
                if isinstance(item, str):
                    models_set.add(item)
                elif isinstance(item, dict):
                    # Handle different possible keys for the model name
                    model_name = item.get("name") or item.get("id") or item.get("model_name")
                    if model_name:
                        models_set.add(model_name)
    except Exception as e:
        print(f"CRITICAL ERROR: Could not list models from the LollmsClient binding. Please check your backend LLM service.")
        print("Full error details:")
        traceback.print_exc() # This will print the full stack trace for debugging

    # --- Step 2: Ensure user's selected model and the default are included as fallbacks ---
    user_model = user_sessions[current_user.username].get("lollms_model_name")
    default_model = LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
    if user_model:
        models_set.add(user_model)
    if default_model:
        models_set.add(default_model)

    # --- Step 3: Clean up any invalid entries ---
    models_set.discard(None)
    models_set.discard("")

    # --- Step 4: Provide a hardcoded list for OpenAI if the set is still empty ---
    if not models_set and lc.binding and "openai" in lc.binding.binding_name.lower():
        print("INFO: No models found, providing default OpenAI models as a fallback.")
        models_set.update(["gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"])

    # --- Step 5: Format and return the final list ---
    if not models_set:
        return [{"name": "No models found"}]
    
    return [{"name": name} for name in sorted(list(models_set))]


@lollms_config_router.post("/lollms-model")
async def set_user_lollms_model(model_name: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    db_user_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user_record: raise HTTPException(status_code=404, detail="User not found.")
    user_sessions[current_user.username]["lollms_model_name"] = model_name
    user_sessions[current_user.username]["lollms_client"] = None
    db_user_record.lollms_model_name = model_name
    try: db.commit()
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
    return {"message": f"Default LoLLMs model set to '{model_name}'. Client will re-initialize."}

@lollms_config_router.post("/llm-params")
async def set_user_llm_params(params: UserLLMParams, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    db_user_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user_record: raise HTTPException(status_code=404, detail="User not found.")
    session_llm_params = user_sessions[current_user.username].get("llm_params", {})
    db_updated = session_updated = False
    for key, value in params.model_dump(exclude_unset=True).items():
        db_key = key
        session_key = key.replace('llm_', '')
        if getattr(db_user_record, db_key) != value: setattr(db_user_record, db_key, value); db_updated = True
        if session_llm_params.get(session_key) != value: session_llm_params[session_key] = value; session_updated = True
    if db_updated:
        try: db.commit()
        except: db.rollback(); raise
    if session_updated:
        user_sessions[current_user.username]["llm_params"] = {k: v for k, v in session_llm_params.items() if v is not None}
        user_sessions[current_user.username]["lollms_client"] = None
        return {"message": "LLM parameters updated. Client will re-initialize."}
    return {"message": "No changes to LLM parameters."}
app.include_router(lollms_config_router)

datastore_router = APIRouter(prefix="/api/datastores", tags=["RAG DataStores"])
@datastore_router.post("", response_model=DataStorePublic, status_code=201)
async def create_datastore(ds_create: DataStoreCreate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if db.query(DBDataStore).filter_by(owner_user_id=user_db_record.id, name=ds_create.name).first(): raise HTTPException(status_code=400, detail=f"DataStore '{ds_create.name}' already exists.")
    new_ds_db_obj = DBDataStore(owner_user_id=user_db_record.id, name=ds_create.name, description=ds_create.description)
    try:
        db.add(new_ds_db_obj); db.commit(); db.refresh(new_ds_db_obj)
        get_safe_store_instance(current_user.username, new_ds_db_obj.id, db)
        return DataStorePublic.model_validate(new_ds_db_obj)
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
app.include_router(datastore_router)

VUE_APP_DIR = Path(__file__).resolve().parent / "frontend" / "dist"
if VUE_APP_DIR.exists() and (VUE_APP_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=VUE_APP_DIR / "assets"), name="vue-assets")
    @app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
    async def serve_vue_app(request: Request, full_path: str):
        return FileResponse(VUE_APP_DIR / "index.html")
else:
    print("WARNING: Frontend 'dist' directory not found. The web UI will not be served.")

if __name__ == "__main__":
    import uvicorn
    host = SERVER_CONFIG.get("host", "127.0.0.1")
    port = int(SERVER_CONFIG.get("port", 9642))
    print(f"--- LoLLMs Chat API Server (v{APP_VERSION}) ---")
    print(f"Access UI at: http://{host}:{port}/")
    uvicorn.run("main:app", host=host, port=port, reload=False)