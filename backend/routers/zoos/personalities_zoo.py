import re
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

def _build_installed_handbag_index(global_root: Path) -> dict:
    """Build a lookup map of installed handbags, keyed by every plausible identity.

    The map stores a ``Path`` for each of the following keys per handbag:

    * the raw on-disk folder name,
    * the folder name **without** a trailing archive/handbag extension,
    * the manifest-declared ``name`` field (``handbag.yaml`` → ``description.yaml``
      → ``config.yaml``).

    This makes "is installed?" detection resilient to installers that slugify,
    rename, or extension-strip the destination folder — the root cause of the
    "installed personas still show an Install button" report.
    """
    index: dict = {}
    if not global_root.is_dir():
        return index
    try:
        entries = list(global_root.iterdir())
    except OSError as exc:
        print(f"WARNING: could not enumerate global handbags at {global_root}: {exc}")
        return index

    for entry in entries:
        if not entry.is_dir():
            continue
        index.setdefault(entry.name, entry)
        for ext in (".handbag", ".personality", ".zip"):
            if entry.name.endswith(ext):
                index.setdefault(entry.name[:-len(ext)], entry)
                break
        for manifest_file in ("handbag.yaml", "description.yaml", "config.yaml"):
            manifest_path = entry / manifest_file
            if not manifest_path.exists():
                continue
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception as exc:
                print(f"WARNING: could not read manifest {manifest_path}: {exc}")
                continue
            manifest_name = data.get("name")
            if manifest_name:
                index.setdefault(str(manifest_name), entry)
            break
    return index


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


def _resolve_zoo_source(repo_name: str, folder_name: str) -> Path:
    """Resolve ``root/repo/folder_name`` and reject traversal outside the repo.

    ``folder_name`` may legitimately be a nested relative path inside the zoo
    repository (e.g. ``"simulators/python interpreter"``), so we cannot assume
    it is a flat folder name. However we must still guarantee the resolved
    source stays *inside* the target repository directory.
    """
    repo_root = (PERSONALITIES_ZOO_ROOT_PATH / repo_name).resolve()
    source_path = (repo_root / folder_name).resolve()
    if repo_root not in source_path.parents and source_path != repo_root:
        raise ValueError(
            f"Personality folder '{folder_name}' escapes repository "
            f"'{repo_name}'."
        )
    return source_path


_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_handbag_folder_name(*candidates: Optional[str]) -> str:
    """Derive a single, safe destination folder name for a handbag.

    The zoo's ``folder_name`` is a repository-relative path that may contain
    path separators and whitespace (e.g. ``"simulators/python interpreter"``),
    which ``backend.personalities._safe_resolve`` rightly rejects because a
    handbag must be a single directory component under the global root.

    We therefore try, in order, each candidate (manifest name, then the
    folder's basename). Each candidate is sanitized to a single path
    component. If none yields a usable name, we fall back to a stable slug.
    """
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        # Take only the final path segment, regardless of separators.
        leaf = candidate.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].strip()
        # Drop filesystem-hostile characters and collapse whitespace runs.
        leaf = _UNSAFE_FILENAME_CHARS.sub("_", leaf)
        leaf = re.sub(r"\s+", " ", leaf).strip(" .")
        if leaf and leaf not in (".", "..") and not leaf.startswith("."):
            return leaf
    return "personality"


def _install_personality_task(task, repo_name: str, folder_name: str):
    try:
        task.log(
            f"Starting install of '{folder_name}' from repo '{repo_name}'...",
            "INFO",
        )
        source_path = _resolve_zoo_source(repo_name, folder_name)
        if not source_path.is_dir():
            raise FileNotFoundError(
                f"Source personality folder does not exist: {source_path}. "
                f"The zoo cache may be stale — try 'Rescan' from the admin panel."
            )

        try:
            manifest_kind, raw_config = _read_personality_manifest(source_path)
            config = _normalize_personality_config(manifest_kind, raw_config)
            task.log(f"Resolved manifest kind='{manifest_kind}'.", "INFO")
        except FileNotFoundError as manifest_err:
            # A pack with an unrecognised manifest (e.g. `meta.yaml`) must
            # not abort BEFORE the folder is copied; degrade gracefully.
            task.log(
                f"No recognised manifest in source: {manifest_err}. "
                f"Continuing install with folder-name-derived metadata.",
                "WARNING",
            )
            config = {"name": Path(folder_name).name or folder_name}
            raw_config = config

        ensure_personality_roots()
        dest_name = _safe_handbag_folder_name(config.get("name"), folder_name)
        final_path = install_handbag_from_folder(
            Path(source_path),
            global_personalities_root(),
            handbag_name=dest_name,
        )
        task.log(f"Handbag files copied to {final_path}.", "INFO")

        # --- Best-effort: finalize handbag.yaml (version normalization) ----
        try:
            _write_handbag_manifest_from_legacy(final_path, config)
            installed_manifest_path = final_path / "handbag.yaml"
            installed_manifest: dict = {}
            if installed_manifest_path.is_file():
                installed_manifest = yaml.safe_load(
                    installed_manifest_path.read_text(encoding="utf-8")
                ) or {}
            if config.get("version") and not installed_manifest.get("version"):
                installed_manifest["version"] = str(config["version"])
                installed_manifest_path.write_text(
                    yaml.safe_dump(installed_manifest, allow_unicode=True),
                    encoding="utf-8",
                )
        except Exception as manifest_io_err:
            task.log(
                f"Warning: could not finalize handbag manifest at "
                f"{final_path}: {manifest_io_err}",
                "WARNING",
            )

        # --- Best-effort: materialize icon.png from manifest base64 --------
        try:
            icon_names = ("icon.png", "icon.jpg", "icon.jpeg", "icon.svg", "icon.webp")
            has_icon_file = any((final_path / n).is_file() for n in icon_names)
            if not has_icon_file and (final_path / "assets").is_dir():
                has_icon_file = any(
                    (final_path / "assets" / n).is_file() for n in icon_names
                )
            if not has_icon_file:
                # Legacy `config.yaml` packs lose `icon` when normalized, so
                # fall back to the raw manifest dict.
                declared_icon = (
                    config.get("icon")
                    or config.get("icon_base64")
                    or (isinstance(raw_config, dict) and (
                        raw_config.get("icon") or raw_config.get("icon_base64")))
                    or None
                )
                if isinstance(declared_icon, str) and declared_icon.strip():
                    payload = (
                        declared_icon.split(",", 1)[-1]
                        if declared_icon.startswith("data:")
                        else declared_icon
                    )
                    try:
                        (final_path / "icon.png").write_bytes(
                            base64.b64decode(payload, validate=True)
                        )
                    except Exception as decode_err:
                        task.log(
                            f"Warning: icon field for '{folder_name}' is not "
                            f"valid base64 ({decode_err}); skipping materialization.",
                            "WARNING",
                        )
        except Exception as icon_err:
            task.log(
                f"Warning: could not materialize handbag icon at "
                f"{final_path}: {icon_err}",
                "WARNING",
            )

        display_name = config.get("name") or dest_name
        task.log(
            f"Personality '{display_name}' installed to {final_path}.",
            "INFO",
        )
        return {"message": "Personality installed.", "path": str(final_path)}

    except Exception as exc:
        # Surface the real failure to the user AND to the Tasks panel.
        task.log(f"Installation failed: {type(exc).__name__}: {exc}", "ERROR")
        raise

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
    installed_index = _build_installed_handbag_index(global_personalities_root())
    print(
        f"INFO: personality zoo detected {len(installed_index)} installed-handbag identifiers "
        f"under {global_personalities_root()}."
    )

    all_items = []
    for info in all_items_raw:
        try:
            folder_name = info.get('folder_name')
            name = info.get('name')
            installed_path: Optional[Path] = None
            if folder_name and folder_name in installed_index:
                installed_path = installed_index[folder_name]
            elif name and name in installed_index:
                installed_path = installed_index[name]
                # Diagnostic: the on-disk folder differs from the zoo's
                # folder_name. The handbag is installed under a different
                # identity (slugified, extension-suffixed, or named after the
                # manifest). Report the true state and log the drift so it
                # fails loudly if it ever gets worse.
                print(
                    f"INFO: Personality '{name}' matched installed handbag by manifest name "
                    f"(zoo folder '{folder_name}', on-disk folder '{installed_path.name}')."
                )
            is_installed = installed_path is not None
            update_available = False
            if is_installed:
                # Best-effort version comparison against the installed handbag
                # manifest (handbag.yaml). Any read/parse failure degrades to
                # "no update available" rather than erroring the whole listing.
                try:
                    installed_version = _handbag_manifest_version(installed_path)
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
