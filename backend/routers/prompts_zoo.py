import shutil
import yaml
import base64
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import ValidationError as PydanticValidationError
import datetime

from backend.db import get_db
from backend.db.models.service import PromptZooRepository as DBPromptZooRepository
from backend.db.models.prompt import SavedPrompt as DBSavedPrompt
from backend.models import (
    PromptZooRepositoryCreate, PromptZooRepositoryPublic, ZooPromptInfo, ZooPromptInfoResponse,
    PromptInstallRequest, TaskInfo, PromptCreate, PromptUpdate
)
from backend.session import get_current_admin_user
from backend.config import PROMPTS_ZOO_ROOT_PATH
from backend.task_manager import task_manager, Task
from backend.models.prompt import PromptPublic
from backend.zoo_cache import get_all_items, get_all_categories
from .app_utils import to_task_info, pull_repo_task

prompts_zoo_router = APIRouter(
    prefix="/api/prompts_zoo",
    tags=["Prompts Zoo Management"],
    dependencies=[Depends(get_current_admin_user)]
)

def install_prompt_task(task: Task, repository: str, folder_name: str):
    task.log(f"Installing prompt: {folder_name} from {repository}")
    zoo_path = PROMPTS_ZOO_ROOT_PATH / repository / folder_name
    
    # FIX: Prioritize description.yaml, fallback to config.yaml
    config_path = zoo_path / 'description.yaml'
    if not config_path.is_file():
        config_path = zoo_path / 'config.yaml'
        if not config_path.is_file():
            raise FileNotFoundError(f"Config file not found at {zoo_path / 'description.yaml'} or {zoo_path / 'config.yaml'}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)
    
    prompt_name = config_data.get('name')
    if not prompt_name:
        raise ValueError("Prompt name not found in configuration file.")

    with task.db_session_factory() as db:
        existing_prompt = db.query(DBSavedPrompt).filter(DBSavedPrompt.name == prompt_name, DBSavedPrompt.owner_user_id.is_(None)).first()
        if existing_prompt:
            task.log(f"Prompt '{prompt_name}' already exists. Overwriting.", "WARNING")
            db.delete(existing_prompt)
            db.commit()

        icon_path = zoo_path / config_data.get('icon', 'icon.png')
        icon_b64 = None
        if icon_path.exists():
            try:
                icon_b64 = "data:image/png;base64," + base64.b64encode(icon_path.read_bytes()).decode('utf-8')
            except Exception as e:
                task.log(f"Could not encode icon: {e}", "WARNING")
        
        prompt_content = config_data.get('prompt', '')
        if not prompt_content and (zoo_path / 'prompt.txt').exists():
            prompt_content = (zoo_path / 'prompt.txt').read_text(encoding='utf-8')

        new_prompt = DBSavedPrompt(
            name=prompt_name, content=prompt_content,
            category=config_data.get('category'), author=config_data.get('author'),
            description=config_data.get('description'), icon=icon_b64,
            owner_user_id=None # System prompt
        )
        db.add(new_prompt)
        db.commit()
        task.log(f"Prompt '{new_prompt.name}' installed successfully.")
    return {"message": "Installation successful"}

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
    installed_items = {p.name for p in db.query(DBSavedPrompt.name).filter(DBSavedPrompt.owner_user_id.is_(None)).all()}

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

    if installation_status:
        if installation_status == 'Installed': all_items = [item for item in all_items if item.is_installed]
        elif installation_status == 'Uninstalled': all_items = [item for item in all_items if not item.is_installed]
    if category and category != 'All': all_items = [item for item in all_items if item.category == category]
    if search_query:
        q = search_query.lower()
        all_items = [item for item in all_items if q in item.name.lower() or (item.description and q in item.description.lower()) or (item.author and q in item.author.lower())]
    
    def sort_key_func(item):
        val = getattr(item, sort_by, None)
        if 'date' in sort_by and val:
            try: return datetime.datetime.fromisoformat(val).timestamp()
            except (ValueError, TypeError): return 0.0
        return str(val or '').lower()
    
    all_items.sort(key=sort_key_func, reverse=(sort_order == 'desc'))

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

@prompts_zoo_router.post("/install", response_model=TaskInfo, status_code=202)
def install_zoo_prompt(request: PromptInstallRequest):
    task = task_manager.submit_task(
        name=f"Installing prompt: {request.folder_name}",
        target=install_prompt_task,
        args=(request.repository, request.folder_name)
    )
    return to_task_info(task)

# --- Manual System Prompt Management ---
@prompts_zoo_router.post("/installed", response_model=PromptPublic, status_code=status.HTTP_201_CREATED)
def create_system_prompt(prompt_data: PromptCreate, db: Session = Depends(get_db)):
    if db.query(DBSavedPrompt).filter(DBSavedPrompt.name == prompt_data.name, DBSavedPrompt.owner_user_id.is_(None)).first():
        raise HTTPException(status_code=409, detail="A system prompt with this name already exists.")
    
    new_prompt = DBSavedPrompt(
        owner_user_id=None,
        **prompt_data.model_dump()
    )
    db.add(new_prompt)
    db.commit()
    db.refresh(new_prompt)
    return new_prompt

@prompts_zoo_router.put("/installed/{prompt_id}", response_model=PromptPublic)
def update_system_prompt(prompt_id: str, prompt_data: PromptUpdate, db: Session = Depends(get_db)):
    prompt_to_update = db.query(DBSavedPrompt).filter(DBSavedPrompt.id == prompt_id, DBSavedPrompt.owner_user_id.is_(None)).first()
    if not prompt_to_update:
        raise HTTPException(status_code=404, detail="System prompt not found.")
    
    update_data = prompt_data.model_dump(exclude_unset=True)
    if 'name' in update_data and update_data['name'] != prompt_to_update.name:
        if db.query(DBSavedPrompt).filter(DBSavedPrompt.name == update_data['name'], DBSavedPrompt.owner_user_id.is_(None), DBSavedPrompt.id != prompt_id).first():
            raise HTTPException(status_code=409, detail="Another system prompt with this name already exists.")

    for key, value in update_data.items():
        setattr(prompt_to_update, key, value)
    
    db.commit()
    db.refresh(prompt_to_update)
    return prompt_to_update

@prompts_zoo_router.delete("/installed/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_system_prompt(prompt_id: str, db: Session = Depends(get_db)):
    prompt_to_delete = db.query(DBSavedPrompt).filter(DBSavedPrompt.id == prompt_id, DBSavedPrompt.owner_user_id.is_(None)).first()
    if not prompt_to_delete:
        raise HTTPException(status_code=404, detail="System prompt not found.")
    
    db.delete(prompt_to_delete)
    db.commit()
    return None