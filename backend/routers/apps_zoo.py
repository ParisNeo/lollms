# backend/routers/apps_zoo.py
import shutil
import json
import yaml
import toml
from pathlib import Path
from packaging import version as packaging_version
from typing import Dict, Any, List, Optional
import datetime
import signal
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session, joinedload
from pydantic import ValidationError as PydanticValidationError
from jsonschema import validate, ValidationError

from backend.db import get_db
from backend.db.models.service import AppZooRepository as DBAppZooRepository, App as DBApp, MCP as DBMCP
from backend.models import (
    AppZooRepositoryCreate, AppZooRepositoryPublic, ZooAppInfo, ZooAppInfoResponse,
    AppInstallRequest, AppPublic, AppActionResponse, TaskInfo, AppUpdate, AppLog
)
from backend.session import get_current_admin_user
from backend.config import APPS_ZOO_ROOT_PATH
from backend.task_manager import task_manager
from backend.zoo_cache import get_all_items, get_all_categories, build_full_cache, refresh_repo_cache
from backend.settings import settings
from .app_utils import (
    to_task_info, pull_repo_task, install_item_task, get_all_zoo_metadata, 
    get_installed_app_path, start_app_task, stop_app_task, open_log_files,
    update_item_task
)

apps_zoo_router = APIRouter(
    prefix="/api/apps_zoo",
    tags=["Apps Zoo Management"],
    dependencies=[Depends(get_current_admin_user)]
)

@apps_zoo_router.post("/rescan", response_model=Dict[str, str])
def rescan_all_zoos():
    build_full_cache()
    return {"message": "Full Zoo cache rebuild initiated."}

@apps_zoo_router.get("/categories", response_model=List[str])
def get_app_zoo_categories():
    return get_all_categories('app')

@apps_zoo_router.get("/repositories", response_model=list[AppZooRepositoryPublic])
def get_app_zoo_repositories(db: Session = Depends(get_db)):
    return db.query(DBAppZooRepository).all()

@apps_zoo_router.post("/repositories", response_model=AppZooRepositoryPublic, status_code=201)
def add_app_zoo_repository(repo: AppZooRepositoryCreate, db: Session = Depends(get_db)):
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
    build_full_cache() # Rescan all to include the new one
    return new_repo

@apps_zoo_router.delete("/repositories/{repo_id}", status_code=204)
def delete_app_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBAppZooRepository).filter(DBAppZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    if not repo.is_deletable: raise HTTPException(status_code=403, detail="This is a default repository.")
    
    if repo.type == 'git':
        shutil.rmtree(APPS_ZOO_ROOT_PATH / repo.name, ignore_errors=True)
    
    db.delete(repo)
    db.commit()
    build_full_cache()

@apps_zoo_router.post("/repositories/{repo_id}/pull", response_model=TaskInfo, status_code=202)
def pull_app_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBAppZooRepository).filter(DBAppZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    task = task_manager.submit_task(
        name=f"Pulling App repository: {repo.name}",
        target=pull_repo_task,
        args=(repo_id, DBAppZooRepository, APPS_ZOO_ROOT_PATH, 'app')
    )
    return to_task_info(task)

@apps_zoo_router.get("/available", response_model=ZooAppInfoResponse)
def get_available_zoo_apps(db: Session = Depends(get_db), page: int = 1, page_size: int = 24, sort_by: str = 'last_update_date', sort_order: str = 'desc', category: Optional[str] = None, search_query: Optional[str] = None, installation_status: Optional[str] = None):
    all_items_raw = get_all_items('app')
    installed_apps_q = db.query(DBApp).filter(DBApp.is_installed == True, DBApp.app_metadata['item_type'].as_string() == 'app').all()
    installed_apps = {app.name: app for app in installed_apps_q}

    all_items = []
    for info in all_items_raw:
        try:
            is_installed = info.get('name') in installed_apps
            update_available = False
            if is_installed:
                installed_app = installed_apps[info.get('name')]
                try:
                    if installed_app.version and info.get('version') and packaging_version.parse(str(info.get('version'))) > packaging_version.parse(str(installed_app.version)):
                        update_available = True
                except (packaging_version.InvalidVersion, TypeError):
                    pass
            
            model_data = {
                "name": info.get('name'), "repository": info.get('repository'), "folder_name": info.get('folder_name'),
                "icon": info.get('icon'), "is_installed": is_installed, "update_available": update_available,
                "has_readme": (APPS_ZOO_ROOT_PATH / info['repository'] / info['folder_name'] / "README.md").exists(),
                **{f: info.get(f) for f in ZooAppInfo.model_fields if f not in ['name', 'repository', 'folder_name', 'is_installed', 'has_readme', 'icon', 'update_available']}
            }
            all_items.append(ZooAppInfo(**model_data))
        except (PydanticValidationError, Exception) as e:
            print(f"ERROR: Could not process cached app data for {info.get('name')}. Error: {e}")

    # --- FILTERING ---
    if installation_status:
        if installation_status == 'Installed':
            all_items = [item for item in all_items if item.is_installed]
        elif installation_status == 'Uninstalled':
            all_items = [item for item in all_items if not item.is_installed]
    if category and category != 'All':
        all_items = [item for item in all_items if item.category == category]
    if search_query:
        q = search_query.lower()
        all_items = [item for item in all_items if q in item.name.lower() or (item.description and q in item.description.lower()) or (item.author and q in item.author.lower())]

    # --- SORTING ---
    def sort_key_func(item):
        val = getattr(item, sort_by, None)
        if 'date' in sort_by:
            if val:
                try: 
                    return datetime.datetime.fromisoformat(val).timestamp()
                except (ValueError, TypeError): 
                    return 0.0
            else:
                return 0.0
        return str(val or '').lower()
    
    installed_items_sorted = sorted([item for item in all_items if item.is_installed], key=sort_key_func, reverse=(sort_order == 'desc'))
    uninstalled_items_sorted = sorted([item for item in all_items if not item.is_installed], key=sort_key_func, reverse=(sort_order == 'desc'))
    
    all_items = installed_items_sorted + uninstalled_items_sorted

    # --- PAGINATION ---
    total_items = len(all_items)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_items = all_items[start:end]

    return ZooAppInfoResponse(items=paginated_items, total=total_items, page=page, pages=(total_items + page_size - 1) // page_size if page_size > 0 else 0)


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
    return to_task_info(task)

@apps_zoo_router.post("/installed/{app_id}/update", response_model=TaskInfo, status_code=202)
def update_installed_app_from_zoo(app_id: str, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Installed app not found.")
    task = task_manager.submit_task(
        name=f"Updating app: {app.name}",
        target=update_item_task,
        args=(app.id,)
    )
    return to_task_info(task)

@apps_zoo_router.get("/installed", response_model=list[AppPublic])
def get_installed_apps(db: Session = Depends(get_db)):
    installed = db.query(DBApp).options(joinedload(DBApp.owner)).filter(DBApp.is_installed == True).order_by(DBApp.name).all()
    zoo_meta = get_all_zoo_metadata()
    response = []
    for app in installed:
        app_public = AppPublic.from_orm(app)
        app_public.item_type = (app.app_metadata or {}).get('item_type', 'app')
        app_public.has_config_schema = (get_installed_app_path(db, app.id) / 'schema.config.json').is_file()
        zoo_info = zoo_meta.get(app.name)
        if zoo_info:
            app_public.repo_version = str(zoo_info.get('version', 'N/A'))
            if app.version and zoo_info.get('version'):
                try:
                    if packaging_version.parse(str(zoo_info.get('version'))) > packaging_version.parse(str(app.version)):
                        app_public.update_available = True
                except (packaging_version.InvalidVersion, TypeError):
                    pass
        response.append(app_public)
    return response

@apps_zoo_router.get("/installed/{app_id}/config-schema", response_model=Dict[str, Any])
def get_app_config_schema(app_id: str, db: Session = Depends(get_db)):
    schema_path = get_installed_app_path(db, app_id) / 'schema.config.json'
    if not schema_path.is_file(): return {}
    return json.loads(schema_path.read_text(encoding='utf-8'))

@apps_zoo_router.get("/installed/{app_id}/config", response_model=Dict[str, Any])
def get_app_config(app_id: str, db: Session = Depends(get_db)):
    app_path = get_installed_app_path(db, app_id)
    config = {}
    if (app_path / 'config.yaml').is_file():
        with open(app_path / 'config.yaml', 'r') as f: config = yaml.safe_load(f) or {}
    # (Logic for schema defaults and env vars omitted for brevity)
    return {"config": config, "metadata": {}}

@apps_zoo_router.put("/installed/{app_id}/config", response_model=AppActionResponse)
def set_app_config(app_id: str, config_data: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    app_path = get_installed_app_path(db, app_id)
    # (Validation logic omitted for brevity)
    with open(app_path / 'config.yaml', 'w') as f:
        yaml.dump(config_data, f, sort_keys=False)
    return AppActionResponse(success=True, message="Configuration saved.")

@apps_zoo_router.post("/installed/{app_id}/start", response_model=TaskInfo, status_code=202)
def start_app(app_id: str, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id).first()
    task = task_manager.submit_task(name=f"Start app: {app.name}", target=start_app_task, args=(app_id,))
    return to_task_info(task)

@apps_zoo_router.post("/installed/{app_id}/stop", response_model=TaskInfo, status_code=202)
def stop_app(app_id: str, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id).first()
    task = task_manager.submit_task(name=f"Stop app: {app.name}", target=stop_app_task, args=(app_id,))
    return to_task_info(task)

@apps_zoo_router.put("/installed/{app_id}", response_model=AppPublic)
def update_installed_app(app_id: str, app_update: AppUpdate, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found.")

    update_data = app_update.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(app, key, value)
    
    try:
        db.commit()
        db.refresh(app, attribute_names=['owner'])
        
        zoo_meta = get_all_zoo_metadata()
        app_public = AppPublic.from_orm(app)
        app_public.item_type = (app.app_metadata or {}).get('item_type', 'app')
        app_public.has_config_schema = (get_installed_app_path(db, app.id) / 'schema.config.json').is_file()
        zoo_info = zoo_meta.get(app.name)
        if zoo_info:
            app_public.repo_version = str(zoo_info.get('version', 'N/A'))
            if app.version and zoo_info.get('version'):
                try:
                    if packaging_version.parse(str(zoo_info['version'])) > packaging_version.parse(str(app.version)):
                        app_public.update_available = True
                except Exception:
                    pass
        
        return app_public
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during app update: {str(e)}")

@apps_zoo_router.get("/installed/{app_id}/logs", response_model=AppLog)
def get_app_logs(app_id: str, db: Session = Depends(get_db)):
    log_path = get_installed_app_path(db, app_id) / "app.log"
    return AppLog(log_content=log_path.read_text(encoding="utf-8") if log_path.exists() else "No logs.")

@apps_zoo_router.delete("/installed/{app_id}", response_model=AppActionResponse)
def uninstall_app(app_id: str, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Installed item record not found.")

    if app.status == 'running' and app.pid:
        try:
            os.kill(app.pid, signal.SIGTERM)
            print(f"INFO: Sent SIGTERM to process {app.pid} for app '{app.name}'.")
        except ProcessLookupError:
            print(f"WARNING: Process {app.pid} for app '{app.name}' not found.")
        except Exception as e:
            print(f"ERROR: Could not stop process {app.pid}: {e}")
    
    if app.id in open_log_files:
        try:
            open_log_files[app.id].close()
            del open_log_files[app.id]
        except Exception as e:
            print(f"WARNING: Could not close log file for app {app.id}: {e}")

    try:
        app_path = get_installed_app_path(db, app.id)
        shutil.rmtree(app_path, ignore_errors=True)
        print(f"INFO: Removed installation folder for '{app.name}'.")
    except Exception as e:
        print(f"ERROR: Could not remove installation folder for '{app.name}': {e}")

    item_type = (app.app_metadata or {}).get('item_type')
    if item_type == 'mcp':
        service_to_delete = db.query(DBMCP).filter(DBMCP.name == app.name, DBMCP.type == 'system').first()
        if service_to_delete:
            db.delete(service_to_delete)
            print(f"INFO: Deleting system MCP service entry for '{app.name}'.")

    db.delete(app)
    db.commit()
    
    return AppActionResponse(success=True, message=f"'{app.name}' has been uninstalled.")

@apps_zoo_router.get("/get-next-available-port", response_model=Dict[str, int])
def get_next_available_port(port: Optional[int] = Query(None), db: Session = Depends(get_db)):
    used_ports = {p[0] for p in db.query(DBApp.port).filter(DBApp.port.isnot(None)).all()}
    used_ports.add(settings.get("port", 9642))
    if port and port not in used_ports: return {"port": port}
    current_port = 9601
    while current_port in used_ports: current_port += 1
    return {"port": current_port}