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
from pydantic import ValidationError as PydanticValidationError
from jsonschema import validate, ValidationError

from backend.db import get_db
from backend.db.models.service import MCPZooRepository as DBMCPZooRepository, App as DBApp, MCP as DBMCP
from backend.models import (
    MCPZooRepositoryCreate, MCPZooRepositoryPublic, ZooMCPInfo, ZooMCPInfoResponse,
    AppInstallRequest, TaskInfo, UserAuthDetails
)
from backend.session import get_current_admin_user
from backend.config import MCPS_ZOO_ROOT_PATH, MCPS_ROOT_PATH
from backend.task_manager import task_manager, Task
from backend.zoo_cache import get_all_items, get_all_categories, force_build_full_cache
from backend.routers.extensions.app_utils import to_task_info, pull_repo_task, install_item_task, get_installed_app_path
from backend.utils import get_accessible_host
from ascii_colors import trace_exception

mcps_zoo_router = APIRouter(
    prefix="/api/mcps_zoo",
    tags=["MCPs Zoo Management"],
    dependencies=[Depends(get_current_admin_user)]
)

def _refresh_zoo_cache_task(task: Task):
    """Wrapper function to run the zoo cache build as a background task."""
    task.log("Starting Zoo cache refresh.")
    task.set_progress(10)
    force_build_full_cache()
    task.set_progress(100)
    task.log("Zoo cache refresh completed.")
    return {"message": "Zoo cache refreshed successfully."}

@mcps_zoo_router.post("/rescan", response_model=TaskInfo, status_code=202)
def rescan_all_zoos(current_user: UserAuthDetails = Depends(get_current_admin_user)):
    """Triggers a background task to refresh the entire Zoo cache."""
    task = task_manager.submit_task(
        name="Refreshing Zoo Cache",
        target=_refresh_zoo_cache_task,
        description="Scanning all Zoo repositories and rebuilding the cache.",
        owner_username=current_user.username
    )
    return task


@mcps_zoo_router.get("/categories", response_model=List[str])
def get_mcp_zoo_categories():
    return get_all_categories('mcp')

@mcps_zoo_router.get("/repositories", response_model=list[MCPZooRepositoryPublic])
def get_mcp_zoo_repositories(db: Session = Depends(get_db)):
    return db.query(DBMCPZooRepository).all()

@mcps_zoo_router.post("/repositories", response_model=MCPZooRepositoryPublic, status_code=201)
def add_mcp_zoo_repository(repo: MCPZooRepositoryCreate, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_admin_user)):
    if db.query(DBMCPZooRepository).filter(DBMCPZooRepository.name == repo.name).first():
        raise HTTPException(status_code=409, detail="A repository with this name already exists.")
    
    repo_type = "local" if repo.path else "git"
    url_or_path = repo.path if repo.path else repo.url

    if repo_type == "local":
        path = Path(url_or_path)
        if not path.is_dir() or not path.exists():
            raise HTTPException(status_code=400, detail=f"The provided local path is not a valid directory: {url_or_path}")

    new_repo = DBMCPZooRepository(name=repo.name, url=url_or_path, type=repo_type, is_deletable=True)
    db.add(new_repo)
    db.commit()
    db.refresh(new_repo)
    task_manager.submit_task(
        name=f"Refreshing Zoo Cache after adding MCP repo '{repo.name}'",
        target=_refresh_zoo_cache_task,
        owner_username=current_user.username
    )
    return new_repo

@mcps_zoo_router.delete("/repositories/{repo_id}", status_code=204)
def delete_mcp_zoo_repository(repo_id: int, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_admin_user)):
    repo = db.query(DBMCPZooRepository).filter(DBMCPZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    if not repo.is_deletable: raise HTTPException(status_code=403, detail="This is a default repository.")
    
    repo_name_for_task = repo.name
    if repo.type == 'git':
        shutil.rmtree(MCPS_ZOO_ROOT_PATH / repo.name, ignore_errors=True)
        
    db.delete(repo)
    db.commit()
    task_manager.submit_task(
        name=f"Refreshing Zoo Cache after deleting MCP repo '{repo_name_for_task}'",
        target=_refresh_zoo_cache_task,
        owner_username=current_user.username
    )

@mcps_zoo_router.post("/repositories/{repo_id}/pull", response_model=TaskInfo, status_code=202)
def pull_mcp_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBMCPZooRepository).filter(DBMCPZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    task = task_manager.submit_task(
        name=f"Pulling MCP repository: {repo.name}",
        target=pull_repo_task,
        args=(repo_id, DBMCPZooRepository, MCPS_ZOO_ROOT_PATH, 'mcp')
    )
    return task

@mcps_zoo_router.get("/available", response_model=ZooMCPInfoResponse)
def get_available_zoo_mcps(
    db: Session = Depends(get_db),
    page: int = 1, page_size: int = 24, sort_by: str = 'last_update_date', sort_order: str = 'desc',
    category: Optional[str] = None, search_query: Optional[str] = None,
    installation_status: Optional[str] = None, repository: Optional[str] = None
):
    all_zoo_items_raw = get_all_items('mcp')
    installed_db_mcps_from_apps = db.query(DBApp).filter(DBApp.app_metadata['item_type'].as_string() == 'mcp').all()
    registered_manual_mcps = db.query(DBMCP).all()
    installed_folders = {f.name for f in MCPS_ROOT_PATH.iterdir() if f.is_dir()}
    accessible_host = get_accessible_host()

    processed_keys = set()
    all_items_map = {}

    for info in all_zoo_items_raw:
        key = f"zoo::{info['repository']}/{info['folder_name']}"
        processed_keys.add(key)
        all_items_map[key] = info

    # Process manually registered MCPs from the dedicated MCP table
    for mcp in registered_manual_mcps:
        key = f"db_mcp::{mcp.id}"
        if key not in processed_keys:
            item_data_from_db = {
                'id': mcp.id, 'name': mcp.name, 'url': mcp.url, 'folder_name': mcp.name,
                'icon': mcp.icon, 'is_installed': False,
                'description': f"Manually registered MCP at {mcp.url}",
                'author': mcp.owner.username if mcp.owner else "System", 'version': 'N/A',
                'category': 'Registered', 'tags': [], 'status': 'stopped',
                'port': None, 'autostart': False, 'item_type': 'mcp', 'repository': 'Registered',
                'has_dot_env_config': False
            }
            all_items_map[key] = item_data_from_db
            processed_keys.add(key)

    # Process installed MCPs from the Apps table
    for mcp in installed_db_mcps_from_apps:
        repo = (mcp.app_metadata or {}).get('repository')
        folder = (mcp.app_metadata or {}).get('folder_name')
        key = f"zoo::{repo}/{folder}" if repo and folder else f"db_app::{mcp.id}"

        item_data_from_db = {
            'id': mcp.id, 'name': mcp.name, 'folder_name': mcp.folder_name or mcp.name,
            'icon': mcp.icon, 'is_installed': mcp.is_installed, 'description': mcp.description,
            'author': mcp.author, 'version': mcp.version, 'category': mcp.category,
            'tags': mcp.tags or [], 'status': mcp.status, 'port': mcp.port, 'autostart': mcp.autostart,
            'item_type': (mcp.app_metadata or {}).get('item_type', 'mcp')
        }
        
        if mcp.is_installed and key in all_items_map:
            zoo_item = all_items_map[key]
            if mcp.version and zoo_item.get('version'):
                try:
                    installed_ver = str(mcp.version or '0.0.0')
                    repo_ver = str(zoo_item.get('version', '0.0.0'))
                    if packaging_version.parse(repo_ver) > packaging_version.parse(installed_ver):
                        item_data_from_db['update_available'] = True
                        item_data_from_db['repo_version'] = repo_ver
                except (packaging_version.InvalidVersion, TypeError):
                    pass

        if item_data_from_db['status'] == 'running' and item_data_from_db['port']:
            item_data_from_db['url'] = f"http://{accessible_host}:{item_data_from_db['port']}"

        if mcp.is_installed:
            try:
                item_path = get_installed_app_path(db, mcp.id)
                if (item_path / 'config.schema.json').exists():
                    item_data_from_db['has_config_schema'] = True
                if (item_path / '.env').exists() or (item_path / '.env.example').exists():
                    item_data_from_db['has_dot_env_config'] = True
            except Exception as e:
                print(f"Could not check schema for {mcp.name}: {e}")

        if key in all_items_map:
            all_items_map[key].update(item_data_from_db)
        else:
            # This case might not be hit often for MCPs if they are either from Zoo or DBMCP
            all_items_map[key] = {**item_data_from_db, 'repository': 'Installed'}
        processed_keys.add(key)

    db_installed_folders = {mcp.folder_name for mcp in installed_db_mcps_from_apps if mcp.is_installed and mcp.folder_name}
    for folder in installed_folders - db_installed_folders:
        key = f"broken::{folder}"
        if key not in processed_keys:
            desc_path = MCPS_ROOT_PATH / folder / "description.yaml"
            metadata = {'name': folder}
            if desc_path.exists():
                with open(desc_path, 'r', encoding='utf-8') as f: metadata.update(yaml.safe_load(f) or {})
            all_items_map[key] = {
                'is_broken': True, 'item_type': 'mcp', 'repository': 'Broken', **metadata, 'folder_name': folder,
                'has_dot_env_config': (MCPS_ROOT_PATH / folder / ".env").exists() or (MCPS_ROOT_PATH / folder / ".env.example").exists()
            }

    final_list = []
    for item_data in all_items_map.values():
        try:
            if 'update_available' not in item_data: item_data['update_available'] = False
            final_list.append(ZooMCPInfo(**item_data))
        except PydanticValidationError as e:
            print(f"Validation error for MCP item {item_data.get('name')}: {e}")

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
    
    filtered_items.sort(key=lambda item: (
        -1 if item.is_broken else 0,
        -1 if item.update_available else 0,
        0 if item.is_installed else 1,
        str(getattr(item, sort_by, '') or '').lower() if sort_order == 'asc' else str(getattr(item, sort_by, '') or '').lower()
    ), reverse=(sort_order == 'desc'))

    total = len(filtered_items)
    start = (page - 1) * page_size
    paginated = filtered_items[start:start + page_size]
    
    return ZooMCPInfoResponse(items=paginated, total=total, page=page, pages=(total + page_size - 1) // page_size if page_size > 0 else 0)

@mcps_zoo_router.get("/readme", response_class=PlainTextResponse)
def get_mcp_readme(repository: str, folder_name: str):
    readme_path = MCPS_ZOO_ROOT_PATH / repository / folder_name / "README.md"
    if not readme_path.exists(): raise HTTPException(status_code=404, detail="README.md not found.")
    return readme_path.read_text(encoding="utf-8")

@mcps_zoo_router.post("/install", response_model=TaskInfo, status_code=202)
def install_zoo_mcp(request: AppInstallRequest):
    task = task_manager.submit_task(
        name=f"Installing MCP: {request.folder_name}",
        target=install_item_task,
        args=(request.repository, request.folder_name, request.port, request.autostart, MCPS_ZOO_ROOT_PATH)
    )
    return task
