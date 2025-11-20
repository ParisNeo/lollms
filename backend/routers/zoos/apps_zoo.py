# backend/routers/zoos/apps_zoo.py
import shutil
import yaml
from pathlib import Path
from packaging import version as packaging_version
from typing import Dict, Any, List, Optional
import datetime
import signal
import os
import json
import traceback

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from pydantic import BaseModel, ValidationError as PydanticValidationError
from jsonschema import validate, ValidationError

from backend.db import get_db
from backend.db.models.service import AppZooRepository as DBAppZooRepository, App as DBApp, MCP as DBMCP
from backend.models import (
    AppZooRepositoryCreate, AppZooRepositoryPublic, ZooAppInfo, ZooAppInfoResponse,
    AppInstallRequest, AppPublic, AppActionResponse, TaskInfo, AppUpdate, AppLog, UserAuthDetails
)
from backend.session import get_current_admin_user
from backend.config import APPS_ZOO_ROOT_PATH, APPS_ROOT_PATH
from backend.task_manager import task_manager, Task
from backend.zoo_cache import get_all_items, get_all_categories, force_build_full_cache
from backend.settings import settings
from backend.routers.extensions.app_utils import (
    to_task_info, pull_repo_task, install_item_task, get_all_zoo_metadata, 
    get_installed_app_path, start_app_task, stop_app_task, open_log_files,
    update_item_task, sync_installs_task, restart_app_task
)
from backend.utils import find_next_available_port, get_accessible_host
from ascii_colors import trace_exception

apps_zoo_router = APIRouter(
    prefix="/api/apps_zoo",
    tags=["Apps Zoo Management"],
    dependencies=[Depends(get_current_admin_user)]
)

class BrokenItemPayload(BaseModel):
    item_type: str
    folder_name: str

class EnvUpdateRequest(BaseModel):
    content: str

def _refresh_zoo_cache_task(task: Task):
    """Wrapper function to run the zoo cache build as a background task."""
    task.log("Starting Zoo cache refresh.")
    task.set_progress(10)
    force_build_full_cache()
    task.set_progress(100)
    task.log("Zoo cache refresh completed.")
    return {"message": "Zoo cache refreshed successfully."}

@apps_zoo_router.post("/purge-broken", response_model=TaskInfo, status_code=202)
def purge_broken_installation(payload: BrokenItemPayload):
    from backend.routers.extensions.app_utils import _purge_broken_task
    task = task_manager.submit_task(
        name=f"Purging broken item: {payload.folder_name}",
        target=_purge_broken_task,
        args=(payload.item_type, payload.folder_name)
    )
    return task

@apps_zoo_router.post("/fix-broken", response_model=TaskInfo, status_code=202)
def fix_broken_installation(payload: BrokenItemPayload):
    from backend.routers.extensions.app_utils import _fix_broken_task
    task = task_manager.submit_task(
        name=f"Fixing broken item: {payload.folder_name}",
        target=_fix_broken_task,
        args=(payload.item_type, payload.folder_name)
    )
    return task


@apps_zoo_router.post("/sync-installs", response_model=TaskInfo, status_code=202)
def sync_installed_items():
    """
    Triggers a background task to synchronize the filesystem installations with the database.
    Fixes ghost installations and removes orphaned database records.
    """
    task = task_manager.submit_task(
        name="Sync Installed Items",
        target=sync_installs_task,
        description="Scanning installation folders and database to fix inconsistencies."
    )
    return task

@apps_zoo_router.post("/rescan", response_model=TaskInfo, status_code=202)
def rescan_all_zoos(current_user: UserAuthDetails = Depends(get_current_admin_user)):
    """Triggers a background task to refresh the entire Zoo cache."""
    task = task_manager.submit_task(
        name="Refreshing Zoo Cache",
        target=_refresh_zoo_cache_task,
        description="Scanning all Zoo repositories and rebuilding the cache.",
        owner_username=current_user.username
    )
    return task

@apps_zoo_router.get("/categories", response_model=List[str])
def get_app_zoo_categories():
    return get_all_categories('app')

@apps_zoo_router.get("/repositories", response_model=list[AppZooRepositoryPublic])
def get_app_zoo_repositories(db: Session = Depends(get_db)):
    return db.query(DBAppZooRepository).all()

@apps_zoo_router.post("/repositories", response_model=AppZooRepositoryPublic, status_code=201)
def add_app_zoo_repository(repo: AppZooRepositoryCreate, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_admin_user)):
    if db.query(DBAppZooRepository).filter(DBAppZooRepository.name == repo.name).first():
        raise HTTPException(status_code=409, detail="A repository with this name already exists.")

    repo_type = "local" if repo.path else "git"
    url_or_path = repo.path if repo.path else repo.url

    if repo_type == "local":
        path = Path(url_or_path)
        if not path.is_dir() or not path.exists():
            raise HTTPException(status_code=400, detail=f"The provided local path is not a valid directory: {url_or_path}")
    
    new_repo = DBAppZooRepository(name=repo.name, url=url_or_path, type=repo_type)
    db.add(new_repo)
    db.commit()
    db.refresh(new_repo)
    task_manager.submit_task(
        name=f"Refreshing Zoo Cache after adding repo '{repo.name}'",
        target=_refresh_zoo_cache_task,
        owner_username=current_user.username
    )
    return new_repo

@apps_zoo_router.delete("/repositories/{repo_id}", status_code=204)
def delete_app_zoo_repository(repo_id: int, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_admin_user)):
    repo = db.query(DBAppZooRepository).filter(DBAppZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    if not repo.is_deletable: raise HTTPException(status_code=403, detail="This is a default repository.")
    
    repo_name_for_task = repo.name
    if repo.type == 'git':
        shutil.rmtree(APPS_ZOO_ROOT_PATH / repo.name, ignore_errors=True)
    
    db.delete(repo)
    db.commit()
    task_manager.submit_task(
        name=f"Refreshing Zoo Cache after deleting repo '{repo_name_for_task}'",
        target=_refresh_zoo_cache_task,
        owner_username=current_user.username
    )

@apps_zoo_router.post("/repositories/{repo_id}/pull", response_model=TaskInfo, status_code=202)
def pull_app_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBAppZooRepository).filter(DBAppZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    task = task_manager.submit_task(
        name=f"Pulling App repository: {repo.name}",
        target=pull_repo_task,
        args=(repo_id, DBAppZooRepository, APPS_ZOO_ROOT_PATH, 'app')
    )
    return task

@apps_zoo_router.get("/available", response_model=ZooAppInfoResponse)
def get_available_zoo_apps(
    db: Session = Depends(get_db),
    page: int = 1, page_size: int = 24, sort_by: str = 'last_update_date', sort_order: str = 'desc',
    category: Optional[str] = None, search_query: Optional[str] = None,
    installation_status: Optional[str] = None, repository: Optional[str] = None
):
    all_zoo_items_raw = get_all_items('app')
    all_db_apps = db.query(DBApp).filter(or_(DBApp.app_metadata.is_(None), DBApp.app_metadata['item_type'].as_string() == 'app')).all()
    installed_folders = {f.name for f in APPS_ROOT_PATH.iterdir() if f.is_dir()}
    accessible_host = get_accessible_host()
    
    processed_keys = set()
    all_items_map = {}

    for info in all_zoo_items_raw:
        key = f"zoo::{info['repository']}/{info['folder_name']}"
        processed_keys.add(key)
        all_items_map[key] = info

    for app in all_db_apps:
        repo = (app.app_metadata or {}).get('repository')
        folder = (app.app_metadata or {}).get('folder_name')
        key = f"zoo::{repo}/{folder}" if repo and folder else f"db::{app.id}"

        item_data_from_db = {
            'id': app.id, 'name': app.name, 'folder_name': app.folder_name or app.name,
            'icon': app.icon, 'is_installed': app.is_installed, 'description': app.description,
            'author': app.author, 'version': app.version, 'category': app.category,
            'tags': app.tags or [], 'status': app.status, 'port': app.port, 'autostart': app.autostart,
            'item_type': (app.app_metadata or {}).get('item_type', 'app')
        }

        if app.is_installed and key in all_items_map:
            zoo_item = all_items_map[key]
            if app.version and zoo_item.get('version'):
                try:
                    installed_ver = str(app.version or '0.0.0')
                    repo_ver = str(zoo_item.get('version', '0.0.0'))
                    if packaging_version.parse(repo_ver) > packaging_version.parse(installed_ver):
                        item_data_from_db['update_available'] = True
                        item_data_from_db['repo_version'] = repo_ver
                except (packaging_version.InvalidVersion, TypeError):
                    pass

        if item_data_from_db['status'] == 'running' and item_data_from_db['port']:
            item_data_from_db['url'] = f"http://{accessible_host}:{item_data_from_db['port']}"

        if app.is_installed:
            try:
                item_path = get_installed_app_path(db, app.id)
                if (item_path / 'config.schema.json').exists():
                    item_data_from_db['has_config_schema'] = True
                if (item_path / '.env').exists() or (item_path / '.env.example').exists():
                    item_data_from_db['has_dot_env_config'] = True
            except Exception as e:
                print(f"Could not check schema for {app.name}: {e}")

        if key in all_items_map:
            all_items_map[key].update(item_data_from_db)
        else:
            all_items_map[key] = {**item_data_from_db, 'repository': 'Registered'}
        processed_keys.add(key)

    db_installed_folders = {app.folder_name for app in all_db_apps if app.is_installed and app.folder_name}
    for folder in installed_folders - db_installed_folders:
        key = f"broken::{folder}"
        if key not in processed_keys:
            desc_path = APPS_ROOT_PATH / folder / "description.yaml"
            metadata = {'name': folder}
            if desc_path.exists():
                with open(desc_path, 'r', encoding='utf-8') as f: metadata.update(yaml.safe_load(f) or {})
            all_items_map[key] = {
                'is_broken': True, 
                'item_type': 'app',
                'repository': 'Broken',
                **metadata, 
                'folder_name': folder,
                'has_dot_env_config': (APPS_ROOT_PATH / folder / ".env").exists() or (APPS_ROOT_PATH / folder / ".env.example").exists()
            }

    final_list = []
    for item_data in all_items_map.values():
        try:
            if 'update_available' not in item_data: item_data['update_available'] = False
            final_list.append(ZooAppInfo(**item_data))
        except PydanticValidationError as e:
            print(f"Validation error for item {item_data.get('name')}: {e}")

    # --- FILTERING ---
    filtered_items = final_list
    if installation_status:
        if installation_status == 'Installed': filtered_items = [i for i in final_list if i.is_installed]
        elif installation_status == 'Uninstalled': filtered_items = [i for i in final_list if not i.is_installed and not i.is_broken and i.repository != 'Registered']
        elif installation_status == 'Broken': filtered_items = [i for i in final_list if i.is_broken]
        elif installation_status == 'Registered': filtered_items = [i for i in final_list if not i.is_installed and i.repository == 'Registered']
    
    if repository and repository != 'All': filtered_items = [i for i in filtered_items if i.repository == repository]
    if category and category != 'All': filtered_items = [i for i in filtered_items if i.category == category]
    if search_query:
        q = search_query.lower()
        filtered_items = [i for i in filtered_items if q in i.name.lower() or (i.description and q in i.description.lower())]

    # --- SORTING ---
    filtered_items.sort(key=lambda item: (
        -1 if item.is_broken else 0,
        -1 if item.update_available else 0,
        0 if item.is_installed else 1,
        str(getattr(item, sort_by, '') or '').lower() if sort_order == 'asc' else str(getattr(item, sort_by, '') or '').lower()
    ), reverse=(sort_order == 'desc'))

    # --- PAGINATION ---
    total = len(filtered_items)
    start = (page - 1) * page_size
    paginated = filtered_items[start:start + page_size]

    return ZooAppInfoResponse(items=paginated, total=total, page=page, pages=(total + page_size - 1) // page_size if page_size > 0 else 0)


@apps_zoo_router.get("/readme", response_class=PlainTextResponse)
def get_app_readme(repository: str, folder_name: str):
    readme_path = APPS_ZOO_ROOT_PATH / repository / folder_name / "README.md"
    if not readme_path.exists(): raise HTTPException(status_code=404, detail="README.md not found.")
    return readme_path.read_text(encoding="utf-8")

@apps_zoo_router.post("/install", response_model=TaskInfo, status_code=202)
def install_zoo_app(request: AppInstallRequest):
    task = task_manager.submit_task(
        name=f"Installing app: {request.folder_name}",
        target=install_item_task,
        args=(request.repository, request.folder_name, request.port, request.autostart, APPS_ZOO_ROOT_PATH)
    )
    return task
    
@apps_zoo_router.get("/get-next-available-port", response_model=Dict[str, int])
def get_next_port(port: Optional[int] = None, db: Session = Depends(get_db)):
    start_port = port or 9601
    used_ports = {p[0] for p in db.query(DBApp.port).filter(DBApp.port.isnot(None)).all()}
    
    port_to_check = start_port
    while True:
        if port_to_check in used_ports:
            port_to_check += 1
            continue
        
        try:
            next_port = find_next_available_port(port_to_check)
            return {"port": next_port}
        except Exception: # If find_next_available_port fails, it means the port is likely used
             port_to_check += 1

# --- INSTALLED APP MANAGEMENT ---

@apps_zoo_router.get("/installed", response_model=List[AppPublic])
def get_installed_apps(db: Session = Depends(get_db)):
    installed_items = db.query(DBApp).filter(DBApp.is_installed == True).options(joinedload(DBApp.owner)).order_by(DBApp.updated_at.desc()).all()
    
    zoo_meta = get_all_zoo_metadata()
    accessible_host = get_accessible_host()
    
    response_items = []
    for item in installed_items:
        public_item = AppPublic.from_orm(item)
        public_item.item_type = (item.app_metadata or {}).get('item_type')
        
        # Dynamically construct the URL for running apps
        if public_item.status == 'running' and public_item.port:
            public_item.url = f"http://{accessible_host}:{public_item.port}"
        
        zoo_item = zoo_meta.get(item.name)
        if zoo_item and item.version:
            try:
                installed_ver = str(item.version or '0.0.0')
                repo_ver = str(zoo_item.get('version', '0.0.0'))
                if packaging_version.parse(repo_ver) > packaging_version.parse(installed_ver):
                    public_item.update_available = True
                    public_item.repo_version = repo_ver
            except (packaging_version.InvalidVersion, TypeError):
                pass
        
        item_path = get_installed_app_path(db, item.id)
        if (item_path / 'config.schema.json').exists():
            public_item.has_config_schema = True
        if (item_path / '.env').exists() or (item_path / '.env.example').exists():
            public_item.has_dot_env_config = True

        response_items.append(public_item)

    return response_items

@apps_zoo_router.post("/installed/{app_id}/start", response_model=TaskInfo, status_code=202)
def start_installed_app(app_id: str, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app: raise HTTPException(404, "Installed app not found.")
    
    task = task_manager.submit_task(
        name=f"Start app: {app.name} ({app.id})",
        target=start_app_task,
        args=(app.id,)
    )
    return task

@apps_zoo_router.post("/installed/{app_id}/stop", response_model=TaskInfo, status_code=202)
def stop_installed_app(app_id: str, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app: raise HTTPException(404, "Installed app not found.")

    task = task_manager.submit_task(
        name=f"Stop app: {app.name} ({app.id})",
        target=stop_app_task,
        args=(app.id,)
    )
    return task
    
@apps_zoo_router.post("/installed/{app_id}/restart", response_model=TaskInfo, status_code=202)
def restart_installed_app(app_id: str, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app: raise HTTPException(404, "Installed app not found.")
    
    task = task_manager.submit_task(
        name=f"Restart app: {app.name} ({app.id})",
        target=restart_app_task,
        args=(app.id,)
    )
    return task

@apps_zoo_router.post("/installed/{app_id}/update", response_model=TaskInfo, status_code=202)
def update_installed_app_from_zoo(app_id: str, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app: raise HTTPException(404, "Installed app not found.")

    task = task_manager.submit_task(
        name=f"Updating app: {app.name} ({app.id})",
        target=update_item_task,
        args=(app.id,)
    )
    return task

@apps_zoo_router.delete("/installed/{app_id}", response_model=AppActionResponse)
def uninstall_app(app_id: str, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app: raise HTTPException(404, "Installed app not found.")
    if app.status == 'running': raise HTTPException(400, "Cannot uninstall a running app. Please stop it first.")

    try:
        app_path = get_installed_app_path(db, app.id)
        if app_path.exists():
            shutil.rmtree(app_path)
        
        db.delete(app)
        db.commit()

        force_build_full_cache()
        
        return AppActionResponse(success=True, message=f"'{app.name}' uninstalled successfully.")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(500, f"Failed to uninstall: {e}")

@apps_zoo_router.put("/installed/{app_id}", response_model=AppPublic)
def update_installed_app_settings(app_id: str, payload: AppUpdate, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app: raise HTTPException(404, "Installed app not found.")
    if app.status == 'running': raise HTTPException(400, "Cannot change settings of a running app.")

    update_data = payload.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(app, key, val)
    db.commit()
    db.refresh(app)
    return AppPublic.from_orm(app)
    
@apps_zoo_router.get("/installed/{app_id}/logs", response_model=AppLog)
def get_app_logs(app_id: str, db: Session = Depends(get_db)):
    app_path = get_installed_app_path(db, app_id)
    log_file = app_path / "app.log"
    if not log_file.exists():
        return AppLog(log_content="Log file not found.")
    return AppLog(log_content=log_file.read_text(encoding='utf-8', errors='ignore'))
    
@apps_zoo_router.get("/installed/{app_id}/config-schema")
def get_app_config_schema(app_id: str, db: Session = Depends(get_db)):
    app_path = get_installed_app_path(db, app_id)
    schema_file = app_path / "config.schema.json"
    if not schema_file.exists():
        return {}
    return json.loads(schema_file.read_text())

@apps_zoo_router.get("/installed/{app_id}/config")
def get_app_config(app_id: str, db: Session = Depends(get_db)):
    app_path = get_installed_app_path(db, app_id)
    config_file = app_path / "config.yaml"
    
    schema_file = app_path / "config.schema.json"
    config_data = {}
    env_overrides = []

    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}
            
    if schema_file.exists():
        schema = json.loads(schema_file.read_text())
        for key, prop in schema.get('properties', {}).items():
            env_var = prop.get('envVar')
            if env_var and env_var in os.environ:
                env_val = os.environ[env_var]
                if prop.get('type') == 'integer': env_val = int(env_val)
                elif prop.get('type') == 'number': env_val = float(env_val)
                elif prop.get('type') == 'boolean': env_val = env_val.lower() in ['true', '1', 'yes']
                config_data[key] = env_val
                env_overrides.append(key)
    
    return {"config": config_data, "metadata": {"env_overrides": env_overrides}}

@apps_zoo_router.put("/installed/{app_id}/config", response_model=AppActionResponse)
def update_app_config(app_id: str, config: Dict[str, Any], db: Session = Depends(get_db)):
    app_path = get_installed_app_path(db, app_id)
    config_file = app_path / "config.yaml"
    schema_file = app_path / "config.schema.json"

    if schema_file.exists():
        try:
            schema = json.loads(schema_file.read_text())
            validate(instance=config, schema=schema)
        except (ValidationError, json.JSONDecodeError) as e:
            raise HTTPException(400, f"Configuration is invalid: {e}")
            
    with open(config_file, 'w', encoding='utf-8') as f:
        yaml.dump(config, f)
        
    return AppActionResponse(success=True, message="Configuration saved.")

@apps_zoo_router.get("/installed/{app_id}/env", response_class=PlainTextResponse)
def get_app_env(app_id: str, db: Session = Depends(get_db)):
    app_path = get_installed_app_path(db, app_id)
    env_file = app_path / ".env"
    
    if not env_file.exists():
        env_example_file = app_path / ".env.example"
        if env_example_file.exists():
            shutil.copy(env_example_file, env_file)
        else:
            raise HTTPException(404, ".env file not found for this app, and no .env.example to create it from.")

    env_content = env_file.read_text(encoding='utf-8')
    return PlainTextResponse(content=env_content)

@apps_zoo_router.put("/installed/{app_id}/env", response_model=AppActionResponse)
def update_app_env(app_id: str, payload: EnvUpdateRequest = Body(...), db: Session = Depends(get_db)):
    app_path = get_installed_app_path(db, app_id)
    env_file = app_path / ".env"
    
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(payload.content)
        
    return AppActionResponse(success=True, message=".env file updated successfully.")


@apps_zoo_router.post("/installed/{app_id}/start", response_model=TaskInfo, status_code=202)
def start_app(app_id: str, current_user: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found.")
    
    task = task_manager.submit_task(
        name=f"Starting app: {app.name}",
        target=start_app_process,
        args=(app.id, db.get_bind().url),
        description=f"Initiating startup sequence for {app.name}",
        owner_username=current_user.username
    )
    return task

@apps_zoo_router.post("/installed/{app_id}/stop", response_model=TaskInfo, status_code=202)
def stop_app(app_id: str, current_user: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found.")
        
    task = task_manager.submit_task(
        name=f"Stopping app: {app.name}",
        target=stop_app_process,
        args=(app.id, db.get_bind().url),
        description=f"Initiating shutdown sequence for {app.name}",
        owner_username=current_user.username
    )
    return task

@apps_zoo_router.get("/installed/{app_id}/logs", response_model=dict)
def get_app_log(app_id: str, current_user: UserAuthDetails = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    from backend.config import APPS_ROOT_PATH
    app = db.query(DBApp).filter(DBApp.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found.")
    
    if not app.folder_name:
        return {"log_content": "Log not available: App folder name is missing."}
        
    log_file_path = APPS_ROOT_PATH / app.folder_name / "log.log"
    if not log_file_path.exists():
        return {"log_content": f"Log file not found at: {log_file_path}"}
        
    try:
        with open(log_file_path, "r", encoding="utf-8") as f:
            # Read last 500 lines for performance
            lines = f.readlines()
            log_content = "".join(lines[-500:])
        return {"log_content": log_content}
    except Exception as e:
        return {"log_content": f"Error reading log file: {e}"}
