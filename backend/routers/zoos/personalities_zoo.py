# backend/routers/personalities_zoo.py
import shutil
import yaml
import base64
from pathlib import Path
from typing import List, Optional
from packaging import version as packaging_version
import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import ValidationError as PydanticValidationError

from backend.db import get_db
from backend.db.models.service import PersonalityZooRepository as DBPersonalityZooRepository
from backend.db.models.personality import Personality as DBPersonality
from backend.models import (
    ZooAppInfo as ZooPersonalityInfo, # Re-using for structure
    ZooAppInfoResponse as ZooPersonalityInfoResponse, # Re-using for structure
    PromptInstallRequest as PersonalityInstallRequest, # CORRECTED MODEL
    TaskInfo
)
from backend.session import get_current_admin_user
from backend.config import PERSONALITIES_ZOO_ROOT_PATH
from backend.task_manager import task_manager
from backend.zoo_cache import get_all_items, get_all_categories, build_full_cache
from backend.routers.app_utils import to_task_info, pull_repo_task
from backend.routers.zoos.prompts_zoo import PromptZooRepositoryCreate, PromptZooRepositoryPublic # Re-using for structure

personalities_zoo_router = APIRouter(
    prefix="/api/personalities_zoo",
    tags=["Personalities Zoo Management"],
    dependencies=[Depends(get_current_admin_user)]
)

def _install_personality_task(task, repo_name: str, folder_name: str):
    source_path = PERSONALITIES_ZOO_ROOT_PATH / repo_name / folder_name
    
    desc_path = source_path / "description.yaml"
    conf_path = source_path / "config.yaml"
    
    if not desc_path.exists() and not conf_path.exists():
        raise FileNotFoundError(f"Neither description.yaml nor config.yaml found in {source_path}")

    config = {}
    if desc_path.exists():
        with open(desc_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
    else: # Legacy config.yaml
        with open(conf_path, 'r', encoding='utf-8') as f:
            legacy_data = yaml.safe_load(f) or {}
        config = {
            'name': legacy_data.get('name'), 'version': str(legacy_data.get('version', 'N/A')),
            'author': legacy_data.get('author'), 'category': legacy_data.get('category'),
            'description': legacy_data.get('personality_description'),
            'prompt_text': legacy_data.get('personality_conditioning'),
            'disclaimer': legacy_data.get('disclaimer'), 'active_mcps': legacy_data.get('dependencies', [])
        }

    with task.db_session_factory() as db:
        if db.query(DBPersonality).filter(DBPersonality.name == config['name'], DBPersonality.owner_user_id.is_(None)).first():
            task.log(f"Personality '{config['name']}' is already installed.", "WARNING")
            return {"message": "Personality already installed."}
        
        icon_path = next((p for p in [source_path / "icon.png", source_path / "assets" / "logo.png"] if p.exists()), None)
        icon_b64 = None
        if icon_path:
            with open(icon_path, 'rb') as f:
                icon_b64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
        
        new_personality = DBPersonality(
            name=config.get('name'), author=config.get('author'), category=config.get('category'),
            description=config.get('description'), prompt_text=config.get('prompt_text', ''),
            disclaimer=config.get('disclaimer'), icon_base64=icon_b64, active_mcps=config.get('active_mcps'),
            owner_user_id=None, is_public=True, version=str(config.get('version', 'N/A')),
            repository=repo_name, folder_name=folder_name
        )
        db.add(new_personality)
        db.commit()
    
    task.log(f"Personality '{config['name']}' installed successfully.", "INFO")
    return {"message": "Personality installed."}

@personalities_zoo_router.get("/categories", response_model=List[str])
def get_personality_zoo_categories():
    return get_all_categories('personality')

@personalities_zoo_router.get("/repositories", response_model=list[PromptZooRepositoryPublic])
def get_repositories(db: Session = Depends(get_db)):
    return db.query(DBPersonalityZooRepository).all()

@personalities_zoo_router.post("/repositories", response_model=PromptZooRepositoryPublic, status_code=201)
def add_repository(repo: PromptZooRepositoryCreate, db: Session = Depends(get_db)):
    if db.query(DBPersonalityZooRepository).filter(DBPersonalityZooRepository.name == repo.name).first():
        raise HTTPException(status_code=409, detail="A repository with this name already exists.")
    
    repo_type = "local" if repo.path else "git"
    url_or_path = repo.path if repo.path else repo.url
    if repo_type == "local" and not Path(url_or_path).is_dir():
        raise HTTPException(status_code=400, detail="Local path is not a valid directory.")
    
    new_repo = DBPersonalityZooRepository(name=repo.name, url=url_or_path, type=repo_type)
    db.add(new_repo); db.commit(); db.refresh(new_repo)
    build_full_cache()
    return new_repo

@personalities_zoo_router.delete("/repositories/{repo_id}", status_code=204)
def delete_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBPersonalityZooRepository).filter(DBPersonalityZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    if not repo.is_deletable: raise HTTPException(status_code=403, detail="This is a default repository.")
    if repo.type == 'git': shutil.rmtree(PERSONALITIES_ZOO_ROOT_PATH / repo.name, ignore_errors=True)
    db.delete(repo); db.commit(); build_full_cache()

@personalities_zoo_router.post("/repositories/{repo_id}/pull", response_model=TaskInfo, status_code=202)
def pull_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBPersonalityZooRepository).filter(DBPersonalityZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    task = task_manager.submit_task(
        name=f"Pulling Personality repo: {repo.name}",
        target=pull_repo_task,
        args=(repo_id, DBPersonalityZooRepository, PERSONALITIES_ZOO_ROOT_PATH, 'personality')
    )
    return to_task_info(task)

@personalities_zoo_router.get("/available", response_model=ZooPersonalityInfoResponse)
def get_available(
    db: Session = Depends(get_db), 
    page: int = 1, 
    page_size: int = 24, 
    sort_by: str = 'last_update_date', 
    sort_order: str = 'desc', 
    category: Optional[str] = None, 
    search_query: Optional[str] = None, 
    installation_status: Optional[str] = None, 
    repository: Optional[str] = None,
    starred_names: Optional[List[str]] = Query(None)
):
    all_items_raw = get_all_items('personality')
    
    installed_recs = db.query(DBPersonality).filter(DBPersonality.owner_user_id.is_(None)).all()
    installed_map = {p.name: p for p in installed_recs}

    all_items = []
    for info in all_items_raw:
        try:
            is_installed = info.get('name') in installed_map
            
            update_available = False
            if is_installed:
                installed_p = installed_map[info.get('name')]
                try:
                    if installed_p.version and info.get('version') and packaging_version.parse(str(info.get('version'))) > packaging_version.parse(str(installed_p.version)):
                        update_available = True
                except (packaging_version.InvalidVersion, TypeError):
                    pass

            model_data = { 
                **info, 
                "is_installed": is_installed,
                "update_available": update_available,
                "has_readme": (PERSONALITIES_ZOO_ROOT_PATH / info['repository'] / info['folder_name'] / "README.md").exists() 
            }
            all_items.append(ZooPersonalityInfo(**model_data))
        except (PydanticValidationError, Exception) as e:
            print(f"ERROR: Could not process cached personality data for {info.get('name')}. Error: {e}")

    # --- FILTERING ---
    filtered_items = all_items
    if starred_names is not None:
        filtered_items = [i for i in filtered_items if i.name in starred_names]
    if installation_status:
        if installation_status == 'Installed':
            filtered_items = [i for i in filtered_items if i.is_installed]
        elif installation_status == 'Uninstalled':
            filtered_items = [i for i in filtered_items if not i.is_installed]
    if repository and repository != 'All':
        filtered_items = [item for item in filtered_items if item.repository == repository]
    if category and category != 'All':
        filtered_items = [i for i in filtered_items if i.category == category]
    if search_query:
        q = search_query.lower()
        filtered_items = [i for i in filtered_items if q in i.name.lower() or (i.description and q in i.description.lower())]
    
    # --- SORTING ---
    def sort_key_func(item):
        val = getattr(item, sort_by, None)
        if 'date' in sort_by and val:
            try:
                return datetime.datetime.fromisoformat(val).timestamp()
            except (ValueError, TypeError):
                return 0.0
        return str(val or '').lower()
    
    filtered_items.sort(key=sort_key_func, reverse=(sort_order == 'desc'))
    
    # --- PAGINATION ---
    total = len(filtered_items)
    start = (page - 1) * page_size
    paginated = filtered_items[start:start + page_size]

    return ZooPersonalityInfoResponse(items=paginated, total=total, page=page, pages=(total + page_size - 1) // page_size if page_size > 0 else 0)

@personalities_zoo_router.get("/readme", response_class=PlainTextResponse)
def get_readme(repository: str, folder_name: str):
    readme_path = PERSONALITIES_ZOO_ROOT_PATH / repository / folder_name / "README.md"
    if not readme_path.exists(): raise HTTPException(status_code=404, detail="README.md not found.")
    return readme_path.read_text(encoding="utf-8")

@personalities_zoo_router.post("/install", response_model=TaskInfo, status_code=202)
def install_personality(request: PersonalityInstallRequest):
    task = task_manager.submit_task(
        name=f"Installing personality: {request.folder_name}",
        target=_install_personality_task,
        args=(request.repository, request.folder_name)
    )
    return to_task_info(task)