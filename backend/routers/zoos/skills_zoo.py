import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
import datetime
import yaml
from packaging import version as packaging_version

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from backend.db import get_db
from backend.db.models.skill import Skill as DBSkill
from backend.db.models.service import SkillZooRepository as DBSkillZooRepository
from backend.models import TaskInfo, UserAuthDetails
from backend.session import get_current_admin_user, get_current_active_user
from backend.config import SKILLS_ZOO_ROOT_PATH
from backend.task_manager import task_manager, Task
from backend.zoo_cache import get_all_items, get_all_categories, force_build_full_cache
from backend.routers.extensions.app_utils import pull_repo_task

skills_zoo_router = APIRouter(
    prefix="/api/skills_zoo",
    tags=["Skills Zoo Management"]
)

class SkillZooRepositoryCreate(BaseModel):
    name: Optional[str] = None
    url: str
    path: Optional[str] = None
    is_enabled: bool = True

class SkillZooRepositoryPublic(BaseModel):
    id: int
    name: str
    url: str
    type: str
    is_deletable: bool = True

class SkillZooItemPublic(BaseModel):
    id: Optional[str] = None
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    repository: Optional[str] = None
    repository_id: Optional[int] = None
    repository_url: Optional[str] = None
    folder_name: str
    icon: Optional[str] = None
    content: Optional[str] = None
    is_installed: bool = False
    stars: Optional[int] = 0
    last_update_date: Optional[str] = None
    has_readme: bool = False
    license: Optional[str] = None

class SkillZooAvailableResponse(BaseModel):
    items: List[SkillZooItemPublic]
    total: int
    page: int = 1
    pages: int = 1

class SkillInstallRequest(BaseModel):
    repository: str
    folder_name: str
    item_name: Optional[str] = None

def _refresh_zoo_cache_task(task: Task):
    task.log("Starting Zoo cache refresh.")
    task.set_progress(10)
    force_build_full_cache()
    task.set_progress(100)
    task.log("Zoo cache refresh completed.")
    return {"message": "Zoo cache refreshed successfully."}

def _resolve_safe_skill_root(repo_name: str) -> Path:
    clean = repo_name.rstrip('/\\').split('/')[-1].split('\\')[-1]
    if clean.endswith('.git'):
        clean = clean[:-4]
    for cand in [clean, repo_name, "lollms_skills_zoo"]:
        if ':' in cand:
            continue
        try:
            target = SKILLS_ZOO_ROOT_PATH / cand
            if target.is_dir():
                return target
        except OSError:
            continue
    try:
        dirs = [d for d in SKILLS_ZOO_ROOT_PATH.iterdir() if d.is_dir() and not d.name.startswith('.')]
        if dirs:
            return dirs[0]
    except Exception:
        pass
    return SKILLS_ZOO_ROOT_PATH / clean

def _install_skill_task(task: Task, repo_name: str, folder_name: str, item_name: Optional[str] = None):
    task.log(f"Installing skill from {repo_name}/{folder_name}...")
    task.set_progress(10)
    repo_root = _resolve_safe_skill_root(repo_name)
    skill_path = repo_root / folder_name

    from backend.zoo_cache import _parse_skill_metadata
    meta = _parse_skill_metadata(skill_path, repo_path=repo_root)

    name = item_name or meta.get('name') or folder_name.split('/')[-1].replace('_', ' ').replace('-', ' ').title()
    category = meta.get('category', 'Development')
    description = meta.get('description', '')
    author = meta.get('author', 'Community')
    version = str(meta.get('version', '1.0.0'))
    content = meta.get('content', '')

    task.set_progress(60)
    with task.db_session_factory() as db:
        existing = db.query(DBSkill).filter(DBSkill.name == name).first()
        if existing:
            existing.description = description
            existing.content = content
            existing.category = category
            existing.author = author
            existing.version = version
            db.commit()
            task.log(f"Skill '{name}' updated in active library.", "INFO")
        else:
            new_skill = DBSkill(
                name=name,
                category=category,
                description=description,
                content=content,
                author=author,
                version=version
            )
            db.add(new_skill)
            db.commit()
            task.log(f"Skill '{name}' installed successfully.", "INFO")

    task.set_progress(100)
    return {"status": "success", "message": f"Skill '{name}' installed."}

@skills_zoo_router.post("/rescan", response_model=TaskInfo, status_code=202)
def rescan_all_zoos(current_user: UserAuthDetails = Depends(get_current_admin_user)):
    task = task_manager.submit_task(
        name="Refreshing Skills Zoo Cache",
        target=_refresh_zoo_cache_task,
        description="Scanning skill repositories and rebuilding the cache.",
        owner_username=current_user.username
    )
    return task

@skills_zoo_router.get("/categories", response_model=List[str])
def get_skill_zoo_categories():
    return get_all_categories('skill')

@skills_zoo_router.get("/repositories", response_model=List[SkillZooRepositoryPublic])
def get_skill_zoo_repositories(db: Session = Depends(get_db)):
    return db.query(DBSkillZooRepository).all()

@skills_zoo_router.post("/repositories", response_model=SkillZooRepositoryPublic, status_code=201)
def add_skill_zoo_repository(
    repo: SkillZooRepositoryCreate,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_admin_user)
):
    repo_name = repo.name
    if not repo_name:
        parsed_name = repo.url.rstrip('/').split('/')[-1]
        if parsed_name.endswith('.git'):
            parsed_name = parsed_name[:-4]
        repo_name = parsed_name or "skill_repo"

    if db.query(DBSkillZooRepository).filter(DBSkillZooRepository.name == repo_name).first():
        raise HTTPException(status_code=409, detail="A repository with this name already exists.")

    repo_type = "local" if repo.path else "git"
    url_or_path = repo.path if repo.path else repo.url

    if repo_type == "local":
        path = Path(url_or_path)
        if not path.is_dir() or not path.exists():
            raise HTTPException(status_code=400, detail=f"The provided local path is not a valid directory: {url_or_path}")

    new_repo = DBSkillZooRepository(name=repo_name, url=url_or_path, type=repo_type, is_deletable=True)
    db.add(new_repo)
    db.commit()
    db.refresh(new_repo)

    task_manager.submit_task(
        name=f"Refreshing Zoo Cache after adding skill repo '{repo_name}'",
        target=_refresh_zoo_cache_task,
        owner_username=current_user.username
    )
    return new_repo

@skills_zoo_router.delete("/repositories/{repo_id}", status_code=204)
def delete_skill_zoo_repository(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_admin_user)
):
    repo = db.query(DBSkillZooRepository).filter(DBSkillZooRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")
    if not repo.is_deletable:
        raise HTTPException(status_code=403, detail="This is a default repository.")

    repo_name_for_task = repo.name
    if repo.type == 'git':
        shutil.rmtree(SKILLS_ZOO_ROOT_PATH / repo.name, ignore_errors=True)

    db.delete(repo)
    db.commit()

    task_manager.submit_task(
        name=f"Refreshing Zoo Cache after deleting skill repo '{repo_name_for_task}'",
        target=_refresh_zoo_cache_task,
        owner_username=current_user.username
    )

@skills_zoo_router.post("/repositories/{repo_id}/pull", response_model=TaskInfo, status_code=202)
def pull_skill_zoo_repository(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_admin_user)
):
    repo = db.query(DBSkillZooRepository).filter(DBSkillZooRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")
    task = task_manager.submit_task(
        name=f"Pulling Skill repository: {repo.name}",
        target=pull_repo_task,
        args=(repo_id, DBSkillZooRepository, SKILLS_ZOO_ROOT_PATH, 'skill'),
        owner_username=current_user.username
    )
    return task

@skills_zoo_router.get("/available", response_model=SkillZooAvailableResponse)
def get_available_zoo_skills(
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: int = 24,
    sort_by: str = 'name',
    sort_order: str = 'asc',
    category: Optional[str] = None,
    search_query: Optional[str] = None,
    installation_status: Optional[str] = None,
    repository: Optional[str] = None,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    all_items_raw = get_all_items('skill')
    if not all_items_raw:
        force_build_full_cache()
        all_items_raw = get_all_items('skill')

    installed_skills = {s.name.lower(): s for s in db.query(DBSkill).all()}
    repos_map = {r.name: r for r in db.query(DBSkillZooRepository).all()}

    all_items = []
    for info in all_items_raw:
        is_installed = info.get('name', '').lower() in installed_skills
        repo_name = info.get('repository', '')
        repo_obj = repos_map.get(repo_name)

        safe_root = _resolve_safe_skill_root(repo_name)
        target_path = safe_root / info.get('folder_name', '')
        has_doc = target_path.is_file() or any((target_path / f).exists() for f in ["README.md", "readme.md", "SKILL.md", "skill.md"])

        model_data = {
            **info,
            "repository": repo_name,
            "repository_id": repo_obj.id if repo_obj else 1,
            "repository_url": repo_obj.url if repo_obj else repo_name,
            "is_installed": is_installed,
            "has_readme": has_doc,
            "license": info.get("license") or "Open Source"
        }
        all_items.append(SkillZooItemPublic(**model_data))

    filtered_items = all_items
    if installation_status:
        if installation_status.lower() == 'installed':
            filtered_items = [i for i in filtered_items if i.is_installed]
        elif installation_status.lower() == 'not_installed':
            filtered_items = [i for i in filtered_items if not i.is_installed]

    if repository and repository != 'All':
        filtered_items = [i for i in filtered_items if i.repository == repository or i.repository_url == repository]

    if category and category != 'All':
        filtered_items = [i for i in filtered_items if i.category == category]

    if search_query:
        q = search_query.lower()
        filtered_items = [
            i for i in filtered_items 
            if q in (i.name or '').lower() or q in (i.description or '').lower() or q in (i.category or '').lower()
        ]

    filtered_items.sort(
        key=lambda item: str(getattr(item, sort_by, '') or '').lower(),
        reverse=(sort_order == 'desc')
    )

    total_items = len(filtered_items)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = filtered_items[start:end]

    return SkillZooAvailableResponse(
        items=paginated,
        total=total_items,
        page=page,
        pages=(total_items + page_size - 1) // page_size if page_size > 0 else 0
    )

@skills_zoo_router.get("/readme", response_class=PlainTextResponse)
def get_skill_readme(repository: str, folder_name: str):
    repo_root = _resolve_safe_skill_root(repository)
    target = repo_root / folder_name
    if target.is_file():
        return target.read_text(encoding="utf-8", errors="replace")

    for cand in ["README.md", "readme.md", "SKILL.md", "skill.md", "skill.xml"]:
        candidate_file = target / cand
        if candidate_file.exists():
            return candidate_file.read_text(encoding="utf-8", errors="replace")

    raise HTTPException(status_code=404, detail="Documentation not found for this skill.")

@skills_zoo_router.get("/license", response_class=PlainTextResponse)
def get_skill_license_text(repository: str, folder_name: str):
    repo_root = _resolve_safe_skill_root(repository)
    target = repo_root / folder_name

    lic_candidates = ["LICENSE", "LICENSE.txt", "LICENSE.md", "license.txt", "license", "license.md"]
    if target.is_dir():
        for cand in lic_candidates:
            if (target / cand).is_file():
                return (target / cand).read_text(encoding="utf-8", errors="replace")

    if repo_root.is_dir():
        for cand in lic_candidates:
            if (repo_root / cand).is_file():
                return (repo_root / cand).read_text(encoding="utf-8", errors="replace")

    return "Standard Open Source License (No explicit LICENSE text provided in skill folder)."

@skills_zoo_router.post("/install", response_model=TaskInfo, status_code=202)
def install_zoo_skill(
    request: SkillInstallRequest,
    current_user: UserAuthDetails = Depends(get_current_admin_user)
):
    task = task_manager.submit_task(
        name=f"Installing skill: {request.folder_name}",
        target=_install_skill_task,
        args=(request.repository, request.folder_name, request.item_name),
        description=f"Installing skill '{request.folder_name}' from repository '{request.repository}'",
        owner_username=current_user.username
    )
    return task