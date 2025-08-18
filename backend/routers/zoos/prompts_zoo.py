# backend/routers/zoos/prompts_zoo.py
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
import datetime
import yaml
from packaging import version as packaging_version

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import ValidationError as PydanticValidationError

from backend.db import get_db
from backend.db.models.prompt import SavedPrompt as DBSavedPrompt
from backend.db.models.service import PromptZooRepository as DBPromptZooRepository
from backend.models import (
    PromptZooRepositoryCreate, PromptZooRepositoryPublic, ZooPromptInfo, ZooPromptInfoResponse,
    PromptInstallRequest, TaskInfo, PromptPublic, PromptCreate, PromptUpdate, GeneratePromptRequest
)
from backend.session import get_current_admin_user, get_user_lollms_client
from backend.config import PROMPTS_ZOO_ROOT_PATH
from backend.task_manager import task_manager, Task
from backend.zoo_cache import get_all_items, get_all_categories, build_full_cache
from backend.settings import settings
from backend.routers.app_utils import to_task_info, pull_repo_task

prompts_zoo_router = APIRouter(
    prefix="/api/prompts_zoo",
    tags=["Prompts Zoo Management"],
    dependencies=[Depends(get_current_admin_user)]
)

def _install_prompt_task(task: Task, repo_name: str, folder_name: str):
    prompt_path = PROMPTS_ZOO_ROOT_PATH / repo_name / folder_name
    config_path = prompt_path / "description.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError("description.yaml not found in prompt folder.")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    with task.db_session_factory() as db:
        if db.query(DBSavedPrompt).filter(DBSavedPrompt.name == config['name'], DBSavedPrompt.owner_user_id.is_(None)).first():
            task.log(f"Prompt '{config['name']}' is already installed.", "WARNING")
            return {"message": "Prompt already installed."}

        new_prompt = DBSavedPrompt(
            name=config.get('name'),
            author=config.get('author'),
            description=config.get('description'),
            content=config.get('content', ''),
            category=config.get('category'),
            owner_user_id=None,
            version=str(config.get('version', 'N/A')),
            repository=repo_name,
            folder_name=folder_name
        )
        db.add(new_prompt)
        db.commit()
    
    task.log(f"Prompt '{config['name']}' installed successfully.", "INFO")
    return {"message": "Prompt installed."}

def _update_prompt_task(task: Task, prompt_id: str):
    task.log("Starting prompt update process...")
    with task.db_session_factory() as db:
        prompt = db.query(DBSavedPrompt).filter(DBSavedPrompt.id == prompt_id).first()
        if not prompt:
            raise ValueError("Prompt to update not found in database.")
        
        if not prompt.repository or not prompt.folder_name:
            raise ValueError("Prompt is not from a zoo, cannot update.")

        task.set_progress(10)
        
        source_path = PROMPTS_ZOO_ROOT_PATH / prompt.repository / prompt.folder_name
        config_path = source_path / "description.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Source description.yaml not found at {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        task.log(f"Updating prompt '{prompt.name}' from version {prompt.version} to {config.get('version')}")
        task.set_progress(50)

        prompt.name = config.get('name', prompt.name)
        prompt.author = config.get('author', prompt.author)
        prompt.description = config.get('description', prompt.description)
        prompt.content = config.get('content', prompt.content)
        prompt.category = config.get('category', prompt.category)
        prompt.version = str(config.get('version', prompt.version))
        
        db.commit()
        task.set_progress(100)
        task.log("Prompt updated successfully in the database.")
    
    return {"message": "Update successful."}

def _generate_prompt_task(task: Task, user_prompt: str, current_admin_user: dict):
    from lollms_client import LollmsClient
    task.log("Starting prompt generation task...")
    
    lc = get_user_lollms_client(current_admin_user.username)
    task.set_progress(10)
    
    generation_prompt = f"""
Create a detailed and effective prompt for an AI assistant based on the user's request.
The output must be a single, valid JSON object containing the following keys: "name", "author", "category", "description", and "content".
- `name`: A concise, descriptive title for the prompt.
- `author`: The author, which should be set to "AI Generated".
- `category`: A relevant category (e.g., "Coding", "Writing", "General", "Productivity").
- `description`: A brief, one-sentence explanation of what the prompt does.
- `content`: The full prompt text. This content should be well-structured, clear, and designed to guide the AI effectively. It can include placeholders like `@<variable>@` for user input.

User's Request:
---
{user_prompt}
---

Return ONLY the JSON object. Do not add any extra text or explanations.
"""
    
    response = lc.generate_text(generation_prompt, stream=False)
    task.set_progress(80)

    try:
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        json_string = response[json_start:json_end]
        prompt_data = yaml.safe_load(json_string)

        with task.db_session_factory() as db:
            new_prompt = DBSavedPrompt(
                name=prompt_data.get('name', 'Untitled AI Prompt'),
                author=prompt_data.get('author', 'AI Generated'),
                description=prompt_data.get('description', ''),
                content=prompt_data.get('content', ''),
                category=prompt_data.get('category', 'AI Generated'),
                owner_user_id=None
            )
            db.add(new_prompt)
            db.commit()
            db.refresh(new_prompt)
            task.set_progress(100)
            task.log("Prompt generated and saved successfully.")
            return PromptPublic.from_orm(new_prompt).model_dump()
    except Exception as e:
        task.log(f"Failed to parse AI response or save prompt. Error: {e}\nRaw Response: {response}", "ERROR")
        raise
    
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

    repo_type = "local" if repo.path else "git"
    url_or_path = repo.path if repo.path else repo.url

    if repo_type == "local":
        path = Path(url_or_path)
        if not path.is_dir() or not path.exists():
            raise HTTPException(status_code=400, detail=f"The provided local path is not a valid directory: {url_or_path}")

    new_repo = DBPromptZooRepository(name=repo.name, url=url_or_path, type=repo_type, is_deletable=True)
    db.add(new_repo)
    db.commit()
    db.refresh(new_repo)
    build_full_cache()
    return new_repo

@prompts_zoo_router.delete("/repositories/{repo_id}", status_code=204)
def delete_prompt_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBPromptZooRepository).filter(DBPromptZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    if not repo.is_deletable: raise HTTPException(status_code=403, detail="This is a default repository.")

    if repo.type == 'git':
        shutil.rmtree(PROMPTS_ZOO_ROOT_PATH / repo.name, ignore_errors=True)

    db.delete(repo)
    db.commit()
    build_full_cache()

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
def get_available_zoo_prompts(
    db: Session = Depends(get_db), 
    page: int = 1, page_size: int = 24, sort_by: str = 'last_update_date', sort_order: str = 'desc', 
    category: Optional[str] = None, search_query: Optional[str] = None, 
    installation_status: Optional[str] = None, repository: Optional[str] = None
):
    all_items_raw = get_all_items('prompt')
    installed_prompts_q = db.query(DBSavedPrompt).filter(DBSavedPrompt.owner_user_id.is_(None)).all()
    installed_prompts = {item.name.lower(): item for item in installed_prompts_q}
    
    all_items = []
    for info in all_items_raw:
        try:
            is_installed = info.get('name', '').lower() in installed_prompts
            update_available = False
            if is_installed:
                installed_prompt = installed_prompts[info.get('name').lower()]
                try:
                    if installed_prompt.version and info.get('version') and packaging_version.parse(str(info.get('version'))) > packaging_version.parse(str(installed_prompt.version)):
                        update_available = True
                except (packaging_version.InvalidVersion, TypeError):
                    pass

            model_data = {
                **info,
                "is_installed": is_installed, "update_available": update_available,
                "has_readme": (PROMPTS_ZOO_ROOT_PATH / info['repository'] / info['folder_name'] / "README.md").exists()
            }
            all_items.append(ZooPromptInfo(**model_data))
        except (PydanticValidationError, Exception) as e:
            print(f"ERROR: Could not process cached prompt data for {info.get('name')}. Error: {e}")
    
    # --- FILTERING ---
    filtered_items = all_items
    if installation_status:
        if installation_status == 'Installed': filtered_items = [item for item in filtered_items if item.is_installed]
        elif installation_status == 'Uninstalled': filtered_items = [item for item in filtered_items if not item.is_installed]
    if repository and repository != 'All': filtered_items = [item for item in filtered_items if item.repository == repository]
    if category and category != 'All': filtered_items = [item for item in filtered_items if item.category == category]
    if search_query:
        q = search_query.lower()
        filtered_items = [item for item in filtered_items if q in item.name.lower() or (item.description and q in item.description.lower())]
    
    # --- SORTING ---
    filtered_items.sort(key=lambda item: (
        str(getattr(item, sort_by, '') or '').lower()
    ), reverse=(sort_order == 'desc'))

    # --- PAGINATION ---
    total_items = len(filtered_items)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_items = filtered_items[start:end]
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
        target=_install_prompt_task,
        args=(request.repository, request.folder_name)
    )
    return to_task_info(task)
    
@prompts_zoo_router.post("/installed/{prompt_id}/update", response_model=TaskInfo, status_code=202)
def update_installed_prompt(prompt_id: str, db: Session = Depends(get_db)):
    prompt = db.query(DBSavedPrompt).filter(DBSavedPrompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Installed prompt not found.")
    task = task_manager.submit_task(
        name=f"Updating prompt: {prompt.name}",
        target=_update_prompt_task,
        args=(prompt.id,)
    )
    return to_task_info(task)

@prompts_zoo_router.post("/installed", response_model=PromptPublic, status_code=status.HTTP_201_CREATED)
def create_system_prompt(prompt_data: PromptCreate, db: Session = Depends(get_db)):
    new_prompt = DBSavedPrompt(**prompt_data.model_dump(), owner_user_id=None)
    db.add(new_prompt)
    db.commit()
    db.refresh(new_prompt)
    return new_prompt

@prompts_zoo_router.put("/installed/{prompt_id}", response_model=PromptPublic)
def update_system_prompt(prompt_id: str, prompt_data: PromptUpdate, db: Session = Depends(get_db)):
    prompt = db.query(DBSavedPrompt).filter(DBSavedPrompt.id == prompt_id, DBSavedPrompt.owner_user_id.is_(None)).first()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System prompt not found.")
    
    update_data = prompt_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(prompt, key, value)
    
    db.commit()
    db.refresh(prompt)
    return prompt

@prompts_zoo_router.delete("/installed/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_system_prompt(prompt_id: str, db: Session = Depends(get_db)):
    prompt = db.query(DBSavedPrompt).filter(DBSavedPrompt.id == prompt_id, DBSavedPrompt.owner_user_id.is_(None)).first()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System prompt not found.")
    db.delete(prompt)
    db.commit()

@prompts_zoo_router.post("/generate_from_prompt", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
def generate_prompt_from_ai(
    request: GeneratePromptRequest, 
    current_admin_user: dict = Depends(get_current_admin_user)
):
    task = task_manager.submit_task(
        name="Generate prompt from description",
        target=_generate_prompt_task,
        args=(request.prompt, current_admin_user),
        description=f"AI is creating a prompt based on: '{request.prompt[:50]}...'",
        owner_username=current_admin_user.username
    )
    return to_task_info(task)