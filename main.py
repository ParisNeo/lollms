# -*- coding: utf-8 -*-
import os
import shutil
import uuid
import datetime
import traceback
from pathlib import Path
from typing import List, Dict, Optional

from fastapi import (
    FastAPI, HTTPException, Depends, Request, File, UploadFile,
    Form, APIRouter
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename

from backend.config import (
    APP_SETTINGS, APP_VERSION, APP_DATA_DIR, APP_DB_URL,
    INITIAL_ADMIN_USER_CONFIG, SERVER_CONFIG, TEMP_UPLOADS_DIR_NAME, DEFAULT_PERSONALITIES
)
from backend.database_setup import (
    init_database, get_db, hash_password,
    User as DBUser, Personality as DBPersonality, DataStore as DBDataStore,
    SharedDataStoreLink as DBSharedDataStoreLink, LLMBinding as DBLLMBinding
)
from backend.discussion import LegacyDiscussion
from backend.session import (
    get_user_data_root, get_user_discussion_path, get_current_active_user,
    get_user_lollms_client, get_user_temp_uploads_path, user_sessions,
    get_user_discussion_assets_path
)
from lollms_client import LollmsDataManager
from backend.models import UserLLMParams, UserAuthDetails, ModelInfo

from backend.routers.auth import auth_router
from backend.routers.discussion import discussion_router
from backend.routers.admin import admin_router
from backend.routers.languages import languages_router
from backend.routers.personalities import personalities_router
from backend.routers.friends import friends_router
from backend.routers.dm import dm_router
from backend.routers.stores import store_files_router, datastore_router
from backend.routers.mcp import apps_router, mcp_router, discussion_tools_router
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
    if APP_SETTINGS.get("migrate"):
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
                    user_sessions[username] = {
                                                "lollms_clients": {}, 
                                                "lollms_model_name": user.lollms_model_name,
                                                "llm_params": {}
                                            }
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
                if username in user_sessions: user_sessions[username]['lollms_clients'] = {}
            
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

# --- Root and Static File Endpoints ---

@app.get("/user_assets/{username}/{discussion_id}/{filename}", include_in_schema=False)
async def get_discussion_asset(
    username: str, discussion_id: str, filename: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> FileResponse:
    if current_user.username != username:
        raise HTTPException(status_code=403, detail="Forbidden to access assets of another user.")

    asset_path = get_user_discussion_assets_path(username) / discussion_id / secure_filename(filename)
    if not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found.")
    return FileResponse(asset_path)

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
app.include_router(apps_router)
app.include_router(mcp_router)
app.include_router(discussion_tools_router)
app.include_router(store_files_router)
app.include_router(datastore_router)
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

@lollms_config_router.get("/lollms-models", response_model=List[ModelInfo])
async def get_available_lollms_models(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    all_models = []
    active_bindings = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()

    for binding in active_bindings:
        try:
            lc = get_user_lollms_client(current_user.username, binding.alias)
            models = lc.listModels()
            
            if isinstance(models, list):
                for item in models:
                    model_name = None
                    if isinstance(item, str):
                        model_name = item
                    elif isinstance(item, dict):
                        model_name = item.get("name") or item.get("id") or item.get("model_name")
                    
                    if model_name:
                        # Ensure every entry has a consistent structure with a fully qualified ID
                        all_models.append({
                            "id": f"{binding.alias}/{model_name}",
                            "name": model_name
                        })
        except Exception as e:
            print(f"WARNING: Could not fetch models from binding '{binding.alias}': {e}")
            continue

    if not all_models:
        raise HTTPException(status_code=404, detail="No models found from any active bindings.")
    
    unique_models = {m["id"]: m for m in all_models}
    return sorted(list(unique_models.values()), key=lambda x: x['id'])


@lollms_config_router.post("/lollms-model")
async def set_user_lollms_model(model_name: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    db_user_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user_record: raise HTTPException(status_code=404, detail="User not found.")
    user_sessions[current_user.username]["lollms_model_name"] = model_name
    user_sessions[current_user.username]["lollms_clients"] = {} # Invalidate all clients
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
        user_sessions[current_user.username]["lollms_clients"] = {} # Invalidate all clients
        return {"message": "LLM parameters updated. Client will re-initialize."}
    return {"message": "No changes to LLM parameters."}
app.include_router(lollms_config_router)

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