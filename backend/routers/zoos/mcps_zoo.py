import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
import datetime
import yaml
from packaging import version as packaging_version

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import ValidationError as PydanticValidationError

from backend.db import get_db
from backend.db.models.service import MCPZooRepository as DBMCPZooRepository, App as DBApp
from backend.models import (
    MCPZooRepositoryCreate, MCPZooRepositoryPublic, ZooMCPInfo, ZooMCPInfoResponse,
    AppInstallRequest, TaskInfo
)
from backend.session import get_current_admin_user
from backend.config import MCPS_ZOO_ROOT_PATH, MCPS_ROOT_PATH
from backend.task_manager import task_manager
from backend.zoo_cache import get_all_items, get_all_categories, build_full_cache
from backend.routers.app_utils import to_task_info, pull_repo_task, install_item_task, get_installed_app_path
from backend.utils import get_accessible_host

mcps_zoo_router = APIRouter(
    prefix="/api/mcps_zoo",
    tags=["MCPs Zoo Management"],
    dependencies=[Depends(get_current_admin_user)]
)

@mcps_zoo_router.get("/categories", response_model=List[str])
def get_mcp_zoo_categories():
    return get_all_categories('mcp')

@mcps_zoo_router.get("/repositories", response_model=list[MCPZooRepositoryPublic])
def get_mcp_zoo_repositories(db: Session = Depends(get_db)):
    return db.query(DBMCPZooRepository).all()

@mcps_zoo_router.post("/repositories", response_model=MCPZooRepositoryPublic, status_code=201)
def add_mcp_zoo_repository(repo: MCPZooRepositoryCreate, db: Session = Depends(get_db)):
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
    build_full_cache()
    return new_repo

@mcps_zoo_router.delete("/repositories/{repo_id}", status_code=204)
def delete_mcp_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBMCPZooRepository).filter(DBMCPZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    if not repo.is_deletable: raise HTTPException(status_code=403, detail="This is a default repository.")
    
    if repo.type == 'git':
        shutil.rmtree(MCPS_ZOO_ROOT_PATH / repo.name, ignore_errors=True)
        
    db.delete(repo)
    db.commit()
    build_full_cache()

@mcps_zoo_router.post("/repositories/{repo_id}/pull", response_model=TaskInfo, status_code=202)
def pull_mcp_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBMCPZooRepository).filter(DBMCPZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    task = task_manager.submit_task(
        name=f"Pulling MCP repository: {repo.name}",
        target=pull_repo_task,
        args=(repo_id, DBMCPZooRepository, MCPS_ZOO_ROOT_PATH, 'mcp')
    )
    return to_task_info(task)

@mcps_zoo_router.get("/available", response_model=ZooMCPInfoResponse)
def get_available_zoo_mcps(
    db: Session = Depends(get_db),
    page: int = 1, page_size: int = 24, sort_by: str = 'last_update_date', sort_order: str = 'desc',
    category: Optional[str] = None, search_query: Optional[str] = None,
    installation_status: Optional[str] = None, repository: Optional[str] = None
):
    all_zoo_items_raw = get_all_items('mcp')
    all_db_mcps = db.query(DBApp).filter(DBApp.app_metadata['item_type'].as_string() == 'mcp').all()
    installed_folders = {f.name for f in MCPS_ROOT_PATH.iterdir() if f.is_dir()}
    accessible_host = get_accessible_host()

    processed_keys = set()
    all_items_map = {}

    for info in all_zoo_items_raw:
        key = f"zoo::{info['repository']}/{info['folder_name']}"
        processed_keys.add(key)
        all_items_map[key] = info

    for mcp in all_db_mcps:
        repo = (mcp.app_metadata or {}).get('repository')
        folder = (mcp.app_metadata or {}).get('folder_name')
        key = f"zoo::{repo}/{folder}" if repo and folder else f"db::{mcp.id}"

        item_data_from_db = {
            'id': mcp.id, 'name': mcp.name, 'folder_name': mcp.folder_name or mcp.name,
            'icon': mcp.icon, 'is_installed': mcp.is_installed, 'description': mcp.description,
            'author': mcp.author, 'version': mcp.version, 'category': mcp.category,
            'tags': mcp.tags or [], 'status': mcp.status, 'port': mcp.port, 'autostart': mcp.autostart,
            'item_type': (mcp.app_metadata or {}).get('item_type', 'mcp')
        }
        
        if item_data_from_db['status'] == 'running' and item_data_from_db['port']:
            item_data_from_db['url'] = f"http://{accessible_host}:{item_data_from_db['port']}"

        if mcp.is_installed:
            try:
                item_path = get_installed_app_path(db, mcp.id)
                if (item_path / 'config.schema.json').exists():
                    item_data_from_db['has_config_schema'] = True
            except Exception as e:
                print(f"Could not check schema for {mcp.name}: {e}")

        if key in all_items_map:
            all_items_map[key].update(item_data_from_db)
        else:
            all_items_map[key] = {**item_data_from_db, 'repository': 'Registered'}
        processed_keys.add(key)

    db_installed_folders = {mcp.folder_name for mcp in all_db_mcps if mcp.is_installed and mcp.folder_name}
    for folder in installed_folders - db_installed_folders:
        key = f"broken::{folder}"
        if key not in processed_keys:
            desc_path = MCPS_ROOT_PATH / folder / "description.yaml"
            metadata = {'name': folder}
            if desc_path.exists():
                with open(desc_path, 'r', encoding='utf-8') as f: metadata.update(yaml.safe_load(f) or {})
            all_items_map[key] = {
                'is_broken': True,
                'item_type': 'mcp',
                'repository': 'Broken',
                **metadata,
                'folder_name': folder
            }

    final_list = []
    for item_data in all_items_map.values():
        try:
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
        -1 if item.is_broken else (0 if item.is_installed else 1),
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
    return to_task_info(task)