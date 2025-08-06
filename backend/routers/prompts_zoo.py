import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
import datetime
import yaml

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
from backend.zoo_cache import get_all_items, get_all_categories
from backend.settings import settings
from .app_utils import to_task_info, pull_repo_task

prompts_zoo_router = APIRouter(
    prefix="/api/prompts_zoo",
    tags=["Prompts Zoo Management"],
    dependencies=[Depends(get_current_admin_user)]
)

# --- Task for Prompt Generation ---
def _generate_prompt_task(task: Task, username: str, prompt: str):
    task.log("Starting prompt generation...")
    task.set_progress(10)

    with task.db_session_factory() as db_session:
        lc = get_user_lollms_client(username)

        prompt_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Short, descriptive name for the prompt."},
                "content": {"type": "string", "description": "The main content of the prompt. This MUST include placeholders for user input where appropriate."},
                "category": {"type": "string", "description": "A category for the prompt (e.g., 'Writing', 'Coding', 'Creative')."},
                "author": {"type": "string", "description": "The author of the prompt. Default to 'AI Generated'."},
                "description": {"type": "string", "description": "A brief explanation of what the prompt does."},
                "icon": {"type": "string", "description": "A base64 encoded icon for the prompt. Can be null or an empty string."}
            },
            "required": ["name", "content"],
        }

        system_prompt = """You are an expert prompt designer for AI chatbots. Your task is to create a new prompt based on the user's instructions.

**IMPORTANT INSTRUCTIONS ON PLACEHOLDERS:**
If the prompt needs user input, you MUST define placeholders. A placeholder has two parts:
1.  **Usage:** Use `@<placeholder_name>@` directly in the prompt content where the user's input should go.
2.  **Definition:** Define the placeholder on a new line after its first use. The definition block starts with `@<placeholder_name>@` and ends with `@</placeholder_name>@`. Inside this block, you must specify `title`, `type`, and `help`. You can optionally add `options` for `str` type and `default` for any type.

**Example of a placeholder with a default value:**
Translate the following text to @<language>@.
@<language>@
title: Language
type: str
options: English, French, Spanish, German
default: English
help: The language to translate the text into.
@</language>@

Now, create a JSON object for the new prompt based on the user's request.
"""

        task.log("Sending prompt to LLM for JSON generation...")
        task.set_progress(30)
        
        generated_data_dict = lc.generate_structured_content(
            prompt,
            system_prompt=system_prompt,
            schema=prompt_schema,
            n_predict=settings.get("default_llm_ctx_size")
        )

        task.log("Creating new system prompt in the database...")
        task.set_progress(90)

        new_prompt = DBSavedPrompt(
            owner_user_id=None,
            **generated_data_dict
        )
        db_session.add(new_prompt)
        db_session.commit()

        task.log("Prompt created and saved successfully.")
        task.set_progress(100)
        
        return {"message": f"Prompt '{new_prompt.name}' created successfully."}


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
            owner_user_id=None
        )
        db.add(new_prompt)
        db.commit()
    
    task.log(f"Prompt '{config['name']}' installed successfully.", "INFO")
    return {"message": "Prompt installed."}


@prompts_zoo_router.post("/generate_from_prompt", response_model=TaskInfo, status_code=202)
async def generate_prompt_from_prompt(
    payload: GeneratePromptRequest,
    current_user: dict = Depends(get_current_admin_user)
):
    db_task = task_manager.submit_task(
        name=f"Generate Prompt: {payload.prompt[:30]}...",
        target=_generate_prompt_task,
        args=(current_user.username, payload.prompt),
        description=f"Generating a new system prompt based on the instruction: '{payload.prompt[:100]}...'",
        owner_username=current_user.username
    )
    return to_task_info(db_task)
    
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
                "icon": info.get('icon'),
                "is_installed": info.get('name') in installed_items, "has_readme": (PROMPTS_ZOO_ROOT_PATH / info['repository'] / info['folder_name'] / "README.md").exists(),
                **{f: info.get(f) for f in ZooPromptInfo.model_fields if f not in ['name', 'repository', 'folder_name', 'is_installed', 'has_readme', 'icon']}
            }
            all_items.append(ZooPromptInfo(**model_data))
        except (PydanticValidationError, Exception) as e:
            print(f"ERROR: Could not process cached prompt data for {info.get('name')}. Error: {e}")
    
    if installation_status: all_items = [item for item in all_items if (item.is_installed if installation_status == 'Installed' else not item.is_installed)]
    if category and category != 'All': all_items = [item for item in all_items if item.category == category]
    if search_query: q = search_query.lower(); all_items = [item for item in all_items if q in item.name.lower()]
    
    def sort_key_func(item): val = getattr(item, sort_by, None); return str(val or '').lower()
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
        target=_install_prompt_task,
        args=(request.repository, request.folder_name)
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
    if not prompt: raise HTTPException(status_code=404, detail="System prompt not found.")
    update_data = prompt_data.model_dump(exclude_unset=True)
    for key, value in update_data.items(): setattr(prompt, key, value)
    db.commit()
    db.refresh(prompt)
    return prompt

@prompts_zoo_router.delete("/installed/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_system_prompt(prompt_id: str, db: Session = Depends(get_db)):
    prompt = db.query(DBSavedPrompt).filter(DBSavedPrompt.id == prompt_id, DBSavedPrompt.owner_user_id.is_(None)).first()
    if not prompt: raise HTTPException(status_code=404, detail="System prompt not found.")
    db.delete(prompt)
    db.commit()