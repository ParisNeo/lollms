import shutil
import yaml
import base64
from pathlib import Path
from typing import List, Optional, Tuple
from packaging import version as packaging_version
import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import ValidationError as PydanticValidationError

from backend.db import get_db
from backend.db.models.service import PersonalityZooRepository as DBPersonalityZooRepository
from backend.db.models.personality import Personality as DBPersonality
from backend.models import (
    ZooAppInfo as ZooPersonalityInfo,
    ZooAppInfoResponse as ZooPersonalityInfoResponse,
    PromptInstallRequest as PersonalityInstallRequest,
    TaskInfo,
    UserAuthDetails
)
from backend.session import get_current_admin_user
from backend.config import PERSONALITIES_ZOO_ROOT_PATH
from backend.task_manager import task_manager, Task
from backend.zoo_cache import get_all_items, get_all_categories, force_build_full_cache
from backend.routers.extensions.app_utils import to_task_info, pull_repo_task
from backend.routers.zoos.prompts_zoo import PromptZooRepositoryCreate, PromptZooRepositoryPublic
from backend.personalities import (
    ensure_personality_roots,
    global_personalities_root,
    install_handbag_from_folder,
)

personalities_zoo_router = APIRouter(
    prefix="/api/personalities_zoo",
    tags=["Personalities Zoo Management"],
    dependencies=[Depends(get_current_admin_user)]
)

def _handbag_manifest_version(handbag_dir: Path) -> Optional[str]:
    """Return the declared version from a handbag's handbag.yaml, or None."""
    manifest = handbag_dir / "handbag.yaml"
    if not manifest.exists():
        return None
    try:
        with open(manifest, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        v = data.get("version")
        return str(v) if v is not None else None
    except Exception:
        return None

def _refresh_zoo_cache_task(task: Task):
    """Wrapper function to run the zoo cache build as a background task."""
    task.log("Starting Zoo cache refresh.")
    task.set_progress(10)
    force_build_full_cache()
    task.set_progress(100)
    task.log("Zoo cache refresh completed.")
    return {"message": "Zoo cache refreshed successfully."}

def _read_personality_manifest(source_path: Path) -> Tuple[str, dict]:
    """Resolve the manifest for a zoo pack and return (kind, raw_dict).

    Modern LOLLMS handbags ship ``handbag.yaml``. Legacy personality packs
    ship ``description.yaml``; the oldest ship ``config.yaml``. Attempting
    only the legacy pair made every modern handbag install raise
    ``FileNotFoundError`` BEFORE the handbag folder was written to disk —
    that was the reported "install shows but nothing appears" symptom.
    """
    for filename, kind in (
        ("handbag.yaml", "handbag"),
        ("description.yaml", "description"),
        ("config.yaml", "config"),
    ):
        candidate = source_path / filename
        if candidate.exists():
            with open(candidate, "r", encoding="utf-8") as f:
                return kind, (yaml.safe_load(f) or {})
    raise FileNotFoundError(
        f"No recognised manifest (handbag.yaml, description.yaml or "
        f"config.yaml) found in {source_path}"
    )


def _normalize_personality_config(kind: str, raw: dict) -> dict:
    """Normalize a zoo manifest dict into the common field shape."""
    if kind == "config":
        return {
            "name": raw.get("name"),
            "version": str(raw.get("version", "N/A")),
            "author": raw.get("author"),
            "category": raw.get("category"),
            "description": raw.get("personality_description"),
            "prompt_text": raw.get("personality_conditioning"),
            "disclaimer": raw.get("disclaimer"),
            "tools": raw.get("dependencies", []),
        }
    # handbag.yaml and description.yaml already share the common shape.
    return raw


def _write_handbag_manifest_from_legacy(installed_path: Path, config: dict) -> None:
    """Synthesize handbag.yaml for legacy installs (no-op if present)."""
    manifest_path = installed_path / "handbag.yaml"
    if manifest_path.exists():
        return
    manifest = {k: v for k, v in (
        ("name", config.get("name")),
        ("description", config.get("description")),
        ("author", config.get("author")),
        ("category", config.get("category")),
        ("version", config.get("version")),
    ) if v}
    if not manifest:
        return
    try:
        manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
    except Exception as exc:
        print(f"WARNING: could not synthesize handbag.yaml at {manifest_path}: {exc}")


def _install_personality_task(task, repo_name: str, folder_name: str):
    source_path = PERSONALITIES_ZOO_ROOT_PATH / repo_name / folder_name

    manifest_kind, raw_config = _read_personality_manifest(source_path)
    config = _normalize_personality_config(manifest_kind, raw_config)

    ensure_personality_roots()
    final_path = install_handbag_from_folder(
        Path(source_path),
        global_personalities_root(),
        handbag_name=folder_name,
    )
    _write_handbag_manifest_from_legacy(final_path, config)
    task.log(
        f"Personality '{config.get('name') or folder_name}' installed to {final_path}.",
        "INFO",
    )
    return {"message": "Personality installed.", "path": str(final_path)}

@personalities_zoo_router.post("/rescan", response_model=TaskInfo, status_code=202)
def rescan_all_zoos(current_user: UserAuthDetails = Depends(get_current_admin_user)):
    """Triggers a background task to refresh the entire Zoo cache."""
    task = task_manager.submit_task(
        name="Refreshing Zoo Cache",
        target=_refresh_zoo_cache_task,
        description="Scanning all Zoo repositories and rebuilding the cache.",
        owner_username=current_user.username
    )
    return task

@personalities_zoo_router.get("/categories", response_model=List[str])
def get_personality_zoo_categories():
    return get_all_categories('personality')

@personalities_zoo_router.get("/repositories", response_model=list[PromptZooRepositoryPublic])
def get_repositories(db: Session = Depends(get_db)):
    return db.query(DBPersonalityZooRepository).all()

@personalities_zoo_router.post("/repositories", response_model=PromptZooRepositoryPublic, status_code=201)
def add_repository(repo: PromptZooRepositoryCreate, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_admin_user)):
    if db.query(DBPersonalityZooRepository).filter(DBPersonalityZooRepository.name == repo.name).first():
        raise HTTPException(status_code=409, detail="A repository with this name already exists.")
    
    repo_path = getattr(repo, "path", None)
    repo_url = getattr(repo, "url", None)

    if repo_path:
        repo_type = "local"
        url_or_path = repo_path
        if not Path(url_or_path).is_dir():
            raise HTTPException(status_code=400, detail="Local path is not a valid directory.")
    elif repo_url:
        repo_type = "git"
        url_or_path = repo_url
    else:
        raise HTTPException(
            status_code=400,
            detail="Either 'path' (for a local repository) or 'url' (for a Git repository) must be provided.",
        )

    new_repo = DBPersonalityZooRepository(name=repo.name, url=url_or_path, type=repo_type)
    db.add(new_repo); db.commit(); db.refresh(new_repo)
    task_manager.submit_task(
        name=f"Refreshing Zoo Cache after adding personality repo '{repo.name}'",
        target=_refresh_zoo_cache_task,
        owner_username=current_user.username
    )
    return new_repo

@personalities_zoo_router.delete("/repositories/{repo_id}", status_code=204)
def delete_repository(repo_id: int, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_admin_user)):
    repo = db.query(DBPersonalityZooRepository).filter(DBPersonalityZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    if not repo.is_deletable: raise HTTPException(status_code=403, detail="This is a default repository.")
    repo_name_for_task = repo.name
    if repo.type == 'git': shutil.rmtree(PERSONALITIES_ZOO_ROOT_PATH / repo.name, ignore_errors=True)
    db.delete(repo); db.commit()
    task_manager.submit_task(
        name=f"Refreshing Zoo Cache after deleting personality repo '{repo_name_for_task}'",
        target=_refresh_zoo_cache_task,
        owner_username=current_user.username
    )


@personalities_zoo_router.post("/repositories/{repo_id}/pull", response_model=TaskInfo, status_code=202)
def pull_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBPersonalityZooRepository).filter(DBPersonalityZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    task = task_manager.submit_task(
        name=f"Pulling Personality repo: {repo.name}",
        target=pull_repo_task,
        args=(repo_id, DBPersonalityZooRepository, PERSONALITIES_ZOO_ROOT_PATH, 'personality')
    )
    return task

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
    starred_names: Optional[List[str]] = Query(None, alias="starred_names[]")
):
    all_items_raw = get_all_items('personality')

    # Installed personas are filesystem handbags under the GLOBAL scope root
    # (see backend.personalities.install_handbag_from_folder). The legacy
    # DBPersonality table is only a migration source and must NOT be used to
    # determine installation state — doing so made every installed handbag
    # appear "not installed" (the reported bug).
    global_root = global_personalities_root()
    installed_handbags = {}
    try:
        if global_root.is_dir():
            for entry in global_root.iterdir():
                if entry.is_dir():
                    installed_handbags[entry.name] = entry
    except OSError as e:
        print(f"WARNING: could not enumerate global handbags at {global_root}: {e}")

    all_items = []
    for info in all_items_raw:
        try:
            folder_name = info.get('folder_name')
            is_installed = bool(folder_name) and folder_name in installed_handbags
            update_available = False
            if is_installed:
                # Best-effort version comparison against the installed handbag
                # manifest (handbag.yaml). Any read/parse failure degrades to
                # "no update available" rather than erroring the whole listing.
                try:
                    installed_version = _handbag_manifest_version(installed_handbags[folder_name])
                    zoo_version = info.get('version')
                    if installed_version and zoo_version and \
                       packaging_version.parse(str(zoo_version)) > packaging_version.parse(str(installed_version)):
                        update_available = True
                except (packaging_version.InvalidVersion, TypeError, OSError):
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
    if installation_status:
        if installation_status == 'Installed':
            filtered_items = [i for i in filtered_items if i.is_installed]
        elif installation_status == 'Uninstalled':
            filtered_items = [i for i in filtered_items if not i.is_installed]
    if repository and repository != 'All':
        filtered_items = [item for item in filtered_items if item.repository == repository]
    if category and category != 'All':
        if category == 'Starred':
            if starred_names:
                filtered_items = [i for i in filtered_items if i.name in starred_names]
            else:
                filtered_items = []
        else:
            filtered_items = [i for i in filtered_items if i.category == category]
            
    if search_query:
        q = search_query.lower()
        filtered_items = [i for i in filtered_items if q in i.name.lower() or (i.description and q in i.description.lower())]
    
    # --- SORTING ---
    filtered_items.sort(key=lambda item: (
        str(getattr(item, sort_by, '') or '').lower()
    ), reverse=(sort_order == 'desc'))
    
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
    return task
