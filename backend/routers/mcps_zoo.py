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
from backend.config import MCPS_ZOO_ROOT_PATH
from backend.task_manager import task_manager
from backend.zoo_cache import get_all_items, get_all_categories, build_full_cache
from .app_utils import to_task_info, pull_repo_task, install_item_task

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
def get_available_zoo_mcps(db: Session = Depends(get_db), page: int = 1, page_size: int = 24, sort_by: str = 'last_update_date', sort_order: str = 'desc', category: Optional[str] = None, search_query: Optional[str] = None, installation_status: Optional[str] = None):
    all_items_raw = get_all_items('mcp')
    installed_mcps_q = db.query(DBApp).filter(DBApp.is_installed == True, DBApp.app_metadata['item_type'].as_string() == 'mcp').all()
    installed_mcps = {item.name: item for item in installed_mcps_q}
    
    all_items = []
    for info in all_items_raw:
        try:
            is_installed = info.get('name') in installed_mcps
            update_available = False
            if is_installed:
                installed_app = installed_mcps[info.get('name')]
                try:
                    if installed_app.version and info.get('version') and packaging_version.parse(str(info.get('version'))) > packaging_version.parse(str(installed_app.version)):
                        update_available = True
                except (packaging_version.InvalidVersion, TypeError):
                    pass

            model_data = {
                "name": info.get('name'), "repository": info.get('repository'), "folder_name": info.get('folder_name'),
                "icon": info.get('icon'), "is_installed": is_installed, "update_available": update_available,
                "has_readme": (MCPS_ZOO_ROOT_PATH / info['repository'] / info['folder_name'] / "README.md").exists(),
                **{f: info.get(f) for f in ZooMCPInfo.model_fields if f not in ['name', 'repository', 'folder_name', 'is_installed', 'has_readme', 'icon', 'update_available']}
            }
            all_items.append(ZooMCPInfo(**model_data))
        except (PydanticValidationError, Exception) as e:
            print(f"ERROR: Could not process cached mcp data for {info.get('name')}. Error: {e}")

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

    return ZooMCPInfoResponse(items=paginated_items, total=total_items, page=page, pages=(total_items + page_size - 1) // page_size if page_size > 0 else 0)

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