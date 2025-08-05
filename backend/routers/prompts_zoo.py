import base64
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import datetime
import yaml

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import ValidationError as PydanticValidationError

from backend.db import get_db
from backend.db.models.service import PromptZooRepository as DBPromptZooRepository
from backend.db.models.prompt import SavedPrompt as DBSavedPrompt
from backend.models import (
    PromptZooRepositoryCreate, PromptZooRepositoryPublic, ZooPromptInfo, ZooPromptInfoResponse,
    PromptInstallRequest, TaskInfo, AppActionResponse
)
from backend.session import get_current_admin_user
from backend.config import PROMPTS_ZOO_ROOT_PATH
from backend.task_manager import task_manager
from backend.zoo_cache import get_all_items, get_all_categories
from .app_utils import to_task_info, pull_repo_task

prompts_zoo_router = APIRouter(
    prefix="/api/prompts_zoo",
    tags=["Prompts Zoo Management"],
    dependencies=[Depends(get_current_admin_user)]
)

@prompts_zoo_router.get("/categories", response_model=List[str])
def get_prompt_zoo_categories():
    return get_all_categories('prompt')

@prompts_zoo_router.get("/repositories", response_model=list[PromptZooRepositoryPublic])
def get_prompt_zoo_repositories(db: Session = Depends(get_db)):
    return db.query(DBPromptZooRepository).all()

@prompts_zoo_router.post("/repositories", response_model=PromptZooRepositoryPublic, status_code=201)
def add_prompt_zoo_repository(repo: PromptZooRepositoryCreate, db: Session = Depends(get_db)):
    if db.query(DBPromptZooRepository).filter(DBPromptZooRepository.name == repo.name).first():
        raise HTTPException(status_code=409, detail="A repository with this name already exists.")
    new_repo = DBPromptZooRepository(**repo.model_dump(), is_deletable=True)
    db.add(new_repo)
    db.commit()
    db.refresh(new_repo)
    return new_repo

@prompts_zoo_router.delete("/repositories/{repo_id}", status_code=204)
def delete_prompt_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBPromptZooRepository).filter(DBPromptZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    if not repo.is_deletable: raise HTTPException(status_code=403, detail="This is a default repository.")
    shutil.rmtree(PROMPTS_ZOO_ROOT_PATH / repo.name, ignore_errors=True)
    db.delete(repo)
    db.commit()

@prompts_zoo_router.post("/repositories/{repo_id}/pull", response_model=TaskInfo, status_code=202)
def pull_prompt_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBPromptZooRepository).filter(DBPromptZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    task = task_manager.submit_task(
        name=f"Pulling Prompt repository: {repo.name}",
        target=pull_repo_task,
        args=(repo_id, DBPromptZooRepository, PROMPTS_ZOO_ROOT_PATH, 'prompt')
    )
    return to_task_info(task)

@prompts_zoo_router.get("/available", response_model=ZooPromptInfoResponse)
def get_available_zoo_prompts(db: Session = Depends(get_db), page: int = 1, page_size: int = 24, sort_by: str = 'last_update_date', sort_order: str = 'desc', category: Optional[str] = None, search_query: Optional[str] = None, installation_status: Optional[str] = None):
    all_items_raw = get_all_items('prompt')
    installed_items = {item.name for item in db.query(DBSavedPrompt.name).filter(DBSavedPrompt.owner_user_id.is_(None)).all()}
    
    all_items = []
    for info in all_items_raw:
        try:
            model_data = {
                "name": info.get('name'), "repository": info.get('repository'), "folder_name": info.get('folder_name'),
                "icon": info.get('icon'), "is_installed": info.get('name') in installed_items,
                "has_readme": (PROMPTS_ZOO_ROOT_PATH / info['repository'] / info['folder_name'] / "README.md").exists(),
                **{f: info.get(f) for f in ZooPromptInfo.model_fields if f not in ['name', 'repository', 'folder_name', 'is_installed', 'has_readme', 'icon']}
            }
            all_items.append(ZooPromptInfo(**model_data))
        except (PydanticValidationError, Exception) as e:
            print(f"ERROR: Could not process cached prompt data for {info.get('name')}. Error: {e}")

    # --- FILTERING ---
    if installation_status:
        if installation_status == 'Installed': all_items = [item for item in all_items if item.is_installed]
        elif installation_status == 'Uninstalled': all_items = [item for item in all_items if not item.is_installed]
    if category and category != 'All': all_items = [item for item in all_items if item.category == category]
    if search_query:
        q = search_query.lower()
        all_items = [item for item in all_items if q in item.name.lower() or (item.description and q in item.description.lower()) or (item.author and q in item.author.lower())]
    
    # --- SORTING ---
    def sort_key_func(item):
        val = getattr(item, sort_by, None)
        if 'date' in sort_by and val:
            try: return datetime.datetime.fromisoformat(val).timestamp()
            except (ValueError, TypeError): return 0.0
        return str(val or '').lower()
    
    all_items.sort(key=sort_key_func, reverse=(sort_order == 'desc'))

    # --- PAGINATION ---
    total_items = len(all_items)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_items = all_items[start:end]

    return ZooPromptInfoResponse(items=paginated_items, total=total_items, page=page, pages=(total_items + page_size - 1) // page_size if page_size > 0 else 0)

@prompts_zoo_router.get("/readme", response_class=PlainTextResponse)
def get_prompt_readme(repository: str, folder_name: str):
    readme_path = PROMPTS_ZOO_ROOT_PATH / repository / folder_name / "README.md"
    if not readme_path.exists(): raise HTTPException(status_code=404, detail="README.md not found.")
    return readme_path.read_text(encoding="utf-8")

@prompts_zoo_router.post("/install", response_model=AppActionResponse, status_code=201)
def install_zoo_prompt(request: PromptInstallRequest, db: Session = Depends(get_db)):
    prompt_folder = PROMPTS_ZOO_ROOT_PATH / request.repository / request.folder_name
    
    if not prompt_folder.is_dir():
        raise HTTPException(status_code=404, detail="Prompt folder not found.")

    desc_path = prompt_folder / "description.yaml"
    prompt_path = prompt_folder / "prompt.txt"
    icon_path = prompt_folder / "icon.png"

    if not desc_path.exists() or not prompt_path.exists():
        raise HTTPException(status_code=404, detail="Required prompt files (description.yaml, prompt.txt) not found.")

    try:
        with open(desc_path, 'r', encoding='utf-8') as f:
            metadata = yaml.safe_load(f)
        
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_content = f.read()

        icon_b64 = None
        if icon_path.exists():
            with open(icon_path, 'rb') as f:
                icon_b64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"

        prompt_name = metadata.get('name')
        if not prompt_name:
            raise HTTPException(status_code=422, detail="description.yaml must contain a 'name' field.")

        existing_prompt = db.query(DBSavedPrompt).filter(DBSavedPrompt.name == prompt_name, DBSavedPrompt.owner_user_id.is_(None)).first()
        if existing_prompt:
            raise HTTPException(status_code=409, detail=f"A system prompt with the name '{prompt_name}' already exists.")

        new_prompt = DBSavedPrompt(
            name=prompt_name,
            content=prompt_content,
            owner_user_id=None,
            category=metadata.get('category'),
            author=metadata.get('author'),
            description=metadata.get('description'),
            icon=icon_b64
        )
        db.add(new_prompt)
        db.commit()

        return AppActionResponse(success=True, message=f"Prompt '{prompt_name}' installed successfully.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to install prompt: {e}")