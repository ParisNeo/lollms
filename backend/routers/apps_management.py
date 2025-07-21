import base64
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
import os
import signal
import datetime
from packaging import version as packaging_version

import yaml
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session, joinedload

from backend.db import get_db
from backend.db.models.service import AppZooRepository as DBAppZooRepository, App as DBApp
from backend.models import (
    AppZooRepositoryCreate, AppZooRepositoryPublic, ZooAppInfo, 
    AppInstallRequest, AppPublic, AppActionResponse, TaskInfo,
    AppUpdate, AppLog
)
from backend.session import get_current_admin_user
from backend.config import APP_DATA_DIR, ZOO_DIR_NAME, APPS_DIR_NAME, CUSTOM_APPS_DIR_NAME
from backend.task_manager import task_manager, Task

from backend.settings import settings
from typing import Optional, Dict

apps_management_router = APIRouter(
    prefix="/api/apps-management",
    tags=["Apps Management"],
    dependencies=[Depends(get_current_admin_user)]
)

ZOO_ROOT_PATH = APP_DATA_DIR / ZOO_DIR_NAME
ZOO_ROOT_PATH.mkdir(parents=True, exist_ok=True)
APPS_ROOT_PATH = APP_DATA_DIR / APPS_DIR_NAME
APPS_ROOT_PATH.mkdir(parents=True, exist_ok=True)
CUSTOM_APPS_ROOT_PATH = APP_DATA_DIR / CUSTOM_APPS_DIR_NAME
CUSTOM_APPS_ROOT_PATH.mkdir(parents=True, exist_ok=True)


# --- Task Functions ---
def _start_app_task(task: Task, app_id: str):
    db_session = next(get_db())
    try:
        app = db_session.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
        if not app:
            raise ValueError("Installed app not found.")
        
        app_folder_name = app.folder_name
        if not app_folder_name:
            raise ValueError("App installation is corrupted: missing folder name.")
            
        app_path = APPS_ROOT_PATH / app_folder_name

        if not app_path.exists():
            app.status = 'error'
            db_session.commit()
            raise FileNotFoundError(f"App directory not found at {app_path}")

        venv_path = app_path / "venv"
        python_executable = venv_path / ("Scripts" if sys.platform == "win32" else "bin") / "python"
        log_file_path = app_path / "app.log"
        
        command = None
        if app.app_metadata and 'run_command' in app.app_metadata:
            run_command_template = app.app_metadata['run_command']
            command = [str(arg).replace("{python_executable}", str(python_executable)).replace("{port}", str(app.port)) for arg in run_command_template]
        else: 
            command = [str(python_executable), "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", str(app.port)]

        task.log(f"Executing start command: {' '.join(command)}")
        task.set_progress(50)

        log_file = open(log_file_path, "a", encoding="utf-8")
        log_file.write(f"\n--- Starting app at {datetime.datetime.now().isoformat()} ---\n")
        log_file.flush()
        
        process = subprocess.Popen(command, cwd=str(app_path), stdout=log_file, stderr=subprocess.STDOUT)
        
        app.pid = process.pid
        app.status = 'running'
        app.url = f"http://localhost:{app.port}"
        app.active = True
        db_session.commit()
        
        task.log(f"App '{app.name}' process started with PID {process.pid} on port {app.port}.")
        task.set_progress(100)
        task.result = {"success": True, "message": f"App '{app.name}' started successfully."}

    except Exception as e:
        task.log(f"Failed to start app: {e}", level="CRITICAL")
        app_to_fail = db_session.query(DBApp).filter(DBApp.id == app_id).first()
        if app_to_fail:
            app_to_fail.status = 'error'
            db_session.commit()
        raise e
    finally:
        db_session.close()


@apps_management_router.get("/apps/get-next-available-port", response_model=Dict[str, int])
def get_next_available_port(port: Optional[int] = Query(None), db: Session = Depends(get_db)):
    """
    Finds the next available port. If a port is provided, it checks its availability.
    If available, it returns the same port. If not, it raises a 409 conflict.
    If no port is provided, it finds and returns the next available one.
    """
    base_port = 9601
    
    used_ports = {p[0] for p in db.query(DBApp.port).filter(DBApp.port.isnot(None)).all()}
    main_app_port = settings.get("port", 9642)
    used_ports.add(main_app_port)

    if port is not None:
        if port in used_ports:
            raise HTTPException(status_code=409, detail=f"Port {port} is already in use.")
        return {"port": port}
    else:
        current_port = base_port
        while current_port in used_ports:
            current_port += 1
            if current_port > 65535:
                raise HTTPException(status_code=500, detail="No available ports.")
        return {"port": current_port}

# --- App Zoo Repository Management ---

@apps_management_router.get("/zoo/repositories", response_model=list[AppZooRepositoryPublic])
def get_zoo_repositories(db: Session = Depends(get_db)):
    """
    Lists all configured App Zoo repositories.
    """
    return db.query(DBAppZooRepository).all()

@apps_management_router.post("/zoo/repositories", response_model=AppZooRepositoryPublic, status_code=201)
def add_zoo_repository(repo_data: AppZooRepositoryCreate, db: Session = Depends(get_db)):
    """
    Adds a new App Zoo repository to the database.
    """
    if db.query(DBAppZooRepository).filter(DBAppZooRepository.url == repo_data.url).first():
        raise HTTPException(status_code=409, detail="A repository with this URL already exists.")
    if db.query(DBAppZooRepository).filter(DBAppZooRepository.name == repo_data.name).first():
        raise HTTPException(status_code=409, detail="A repository with this name already exists.")

    new_repo = DBAppZooRepository(name=repo_data.name, url=repo_data.url)
    db.add(new_repo)
    db.commit()
    db.refresh(new_repo)
    return new_repo

@apps_management_router.delete("/zoo/repositories/{repo_id}", status_code=204)
def delete_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    """
    Deletes an App Zoo repository and its cached files.
    """
    repo_to_delete = db.query(DBAppZooRepository).filter(DBAppZooRepository.id == repo_id).first()
    if not repo_to_delete:
        raise HTTPException(status_code=404, detail="Repository not found.")
    
    repo_path = ZOO_ROOT_PATH / repo_to_delete.name
    if repo_path.exists():
        shutil.rmtree(repo_path, ignore_errors=True)
        
    db.delete(repo_to_delete)
    db.commit()
    return None

def _pull_repo_task(task: Task, repo_id: int, repo_name: str, repo_url: str):
    repo_path = ZOO_ROOT_PATH / repo_name
    task.log(f"Starting pull for repository '{repo_name}' from {repo_url} into {repo_path}")
    task.set_progress(10)
    
    try:
        if task.cancellation_event.is_set(): return

        if repo_path.exists() and (repo_path / ".git").exists():
            task.log("Existing repository found. Forcefully updating to match remote...")
            
            # 1. Fetch all updates from the remote
            fetch_command = ["git", "-C", str(repo_path), "fetch", "--all"]
            subprocess.run(fetch_command, capture_output=True, text=True, check=True)
            task.log("Fetched remote updates.")

            # 2. Find the default branch of the remote 'origin'
            try:
                symref_command = ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "origin/HEAD"]
                result = subprocess.run(symref_command, capture_output=True, text=True, check=True)
                default_branch = result.stdout.strip().replace("origin/", "")
                task.log(f"Identified remote default branch as '{default_branch}'.")
            except subprocess.CalledProcessError:
                task.log("Could not auto-detect default branch. Falling back to 'main'.", level="WARNING")
                default_branch = "main"

            # 3. Force reset the local state to match the remote branch
            reset_command = ["git", "-C", str(repo_path), "reset", "--hard", f"origin/{default_branch}"]
            subprocess.run(reset_command, capture_output=True, text=True, check=True)
            task.log(f"Reset local repository to 'origin/{default_branch}'.")

            # 4. Remove any untracked files and directories
            clean_command = ["git", "-C", str(repo_path), "clean", "-dfx"]
            subprocess.run(clean_command, capture_output=True, text=True, check=True)
            task.log("Removed untracked files and directories.")

            task.log(f"Successfully forced update for '{repo_name}'.")
        else:
            task.log("New repository. Cloning...")
            if repo_path.exists():
                shutil.rmtree(repo_path)
            command = ["git", "clone", repo_url, str(repo_path)]
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            task.log(f"Successfully cloned '{repo_name}'.\n{result.stdout}")
        
        if task.cancellation_event.is_set(): return
        task.set_progress(90)
        session = next(get_db())
        try:
            repo_in_db = session.query(DBAppZooRepository).filter(DBAppZooRepository.id == repo_id).first()
            if repo_in_db:
                from datetime import datetime, timezone
                repo_in_db.last_pulled_at = datetime.now(timezone.utc)
                session.commit()
                task.log("Updated last pulled timestamp in database.")
        finally:
            session.close()

    except subprocess.CalledProcessError as e:
        task.log(f"Git command failed. Stderr: {e.stderr}", level="ERROR")
        raise e
    except Exception as e:
        task.log(f"An unexpected error occurred: {e}", level="CRITICAL")
        raise e

@apps_management_router.post("/zoo/repositories/{repo_id}/pull", response_model=TaskInfo)
def pull_zoo_repository(repo_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    repo = db.query(DBAppZooRepository).filter(DBAppZooRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")

    task = task_manager.submit_task(
        name=f"Pulling repository: {repo.name}",
        target=_pull_repo_task,
        args=(repo.id, repo.name, repo.url)
    )
    background_tasks.add_task(task.run)
    return TaskInfo(**task.__dict__)


# --- Available Apps Discovery ---

def _get_zoo_apps_metadata():
    """Helper to scan and parse metadata from all zoo repos."""
    all_zoo_metadata = {}
    for repo_dir in ZOO_ROOT_PATH.iterdir():
        if not repo_dir.is_dir(): continue
        for app_dir in repo_dir.iterdir():
            if not app_dir.is_dir() or app_dir.name.startswith('.'): continue
            yaml_path = app_dir / "description.yaml"
            if not yaml_path.is_file(): continue
            try:
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    metadata = yaml.safe_load(f)
                if metadata and 'name' in metadata:
                    all_zoo_metadata[metadata['name']] = metadata
            except Exception as e:
                print(f"ERROR: Could not process metadata for app in '{app_dir.name}': {e}")
    return all_zoo_metadata

def _scan_app_directory(app_dir: Path, repository_name: str, installed_app_names: set):
    """Scans a single directory for a valid app and returns its info."""
    if not app_dir.is_dir() or app_dir.name.startswith('.'):
        return None
    
    yaml_path = app_dir / "description.yaml"
    if not yaml_path.is_file():
        return None

    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            metadata = yaml.safe_load(f)
        
        if not metadata or 'name' not in metadata:
            return None

        icon_base64 = None
        icon_path = app_dir / "icon.png"
        if icon_path.is_file():
            with open(icon_path, "rb") as image_file:
                icon_base64 = f"data:image/png;base64,{base64.b64encode(image_file.read()).decode('utf-8')}"

        has_readme = (app_dir / "README.md").is_file()
        metadata.pop('repository', None)

        return ZooAppInfo(
            **metadata,
            repository=repository_name,
            folder_name=app_dir.name,
            icon=icon_base64,
            is_installed=(metadata['name'] in installed_app_names),
            has_readme=has_readme
        )
    except Exception as e:
        print(f"ERROR: Could not process app in '{app_dir.name}': {e}")
        return None


@apps_management_router.get("/zoo/available-apps", response_model=list[ZooAppInfo])
def get_available_zoo_apps(db: Session = Depends(get_db)):
    """
    Scans all pulled App Zoo repositories and custom app folders, returning a list of available apps.
    """
    installed_app_names = {app.name for app in db.query(DBApp).filter(DBApp.is_installed == True).all()}
    available_apps = []

    # Scan Zoo Repositories
    for repo_dir in ZOO_ROOT_PATH.iterdir():
        if not repo_dir.is_dir(): continue
        for app_dir in repo_dir.iterdir():
            app_info = _scan_app_directory(app_dir, repo_dir.name, installed_app_names)
            if app_info:
                available_apps.append(app_info)

    # Scan Custom Apps Folder
    for app_dir in CUSTOM_APPS_ROOT_PATH.iterdir():
        app_info = _scan_app_directory(app_dir, "Custom", installed_app_names)
        if app_info:
            available_apps.append(app_info)

    return sorted(available_apps, key=lambda x: x.name.lower())

@apps_management_router.get("/zoo/app-readme", response_class=PlainTextResponse)
def get_app_readme(repository: str = Query(...), folder_name: str = Query(...)):
    if repository == "Custom":
        base_path = CUSTOM_APPS_ROOT_PATH
    else:
        base_path = ZOO_ROOT_PATH / repository

    readme_path = base_path / folder_name / "README.md"
    if not readme_path.is_file():
        raise HTTPException(status_code=404, detail="README.md not found for this app.")
    
    try:
        return readme_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read README file: {e}")


# --- App Installation ---

DEFAULT_SERVER_CODE = """
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI()
app_dir = Path(__file__).parent
static_folder = app_dir / 'dist'
if not static_folder.exists():
    static_folder = app_dir
app.mount("/", StaticFiles(directory=static_folder, html=True), name="static")
"""

def _install_app_task(task: Task, app_info: dict, port: int, autostart: bool):
    repo_name = app_info.get("repository")
    folder_name = app_info.get("folder_name")
    app_name = app_info.get("name")

    if repo_name == "Custom":
        source_path = CUSTOM_APPS_ROOT_PATH / folder_name
    else:
        source_path = ZOO_ROOT_PATH / repo_name / folder_name
        
    dest_path = APPS_ROOT_PATH / folder_name
    
    db_session = next(get_db())
    try:
        task.log(f"Starting installation for '{app_name}'...")
        app_entry = db_session.query(DBApp).filter_by(name=app_name).first()
        if not app_entry:
            app_entry = DBApp(name=app_name, url="#installing", status='installing', is_installed=False)
            db_session.add(app_entry)
        else:
            app_entry.status = 'installing'
        db_session.commit()
        task.set_progress(10)

        if task.cancellation_event.is_set(): raise InterruptedError("Installation cancelled by user.")
        task.log("Copying app files...")
        if dest_path.exists():
            shutil.rmtree(dest_path)
        shutil.copytree(source_path, dest_path)
        task.set_progress(25)
        
        run_command = None
        main_py_path = dest_path / "main.py"
        server_py_path = dest_path / "server.py"

        if main_py_path.exists():
            task.log("Found main.py, configuring for python script execution.")
            run_command = ["{python_executable}", "main.py"]
        elif server_py_path.exists():
            task.log("Found server.py, configuring for uvicorn execution.")
            run_command = ["{python_executable}", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "{port}"]
        else:
            task.log("No main.py or server.py found. Creating a default static server (server.py).")
            with open(server_py_path, "w", encoding="utf-8") as f: f.write(DEFAULT_SERVER_CODE)
            run_command = ["{python_executable}", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "{port}"]

        if task.cancellation_event.is_set(): raise InterruptedError("Installation cancelled by user.")
        task.log("Creating virtual environment...")
        venv_path = dest_path / "venv"
        python_executable = sys.executable
        subprocess.run([python_executable, "-m", "venv", str(venv_path)], check=True, capture_output=True, text=True)
        task.set_progress(50)
        
        pip_executable = venv_path / ("Scripts" if sys.platform == "win32" else "bin") / "pip"
        base_deps = ["fastapi", "uvicorn", "pydantic", "lollms_client"]
        task.log(f"Installing base dependencies: {', '.join(base_deps)}")
        subprocess.run([str(pip_executable), "install"] + base_deps, check=True, capture_output=True, text=True)
        task.set_progress(75)

        if task.cancellation_event.is_set(): raise InterruptedError("Installation cancelled by user.")
        requirements_path = dest_path / "requirements.txt"
        if requirements_path.is_file():
            task.log("Installing app-specific dependencies from requirements.txt...")
            subprocess.run([str(pip_executable), "install", "-r", str(requirements_path)], check=True, capture_output=True, text=True)
        task.set_progress(90)

        task.log("Finalizing installation in database...")
        app_entry.url = f"http://localhost:{port}"
        app_entry.is_installed = True
        app_entry.status = 'stopped'
        app_entry.port = port
        app_entry.autostart = autostart
        app_entry.folder_name = folder_name
        app_entry.icon = app_info.get('icon')
        app_entry.author = app_info.get('author')
        app_entry.description = app_info.get('description')
        app_entry.version = str(app_info.get('version')) if app_info.get('version') is not None else None
        app_entry.category = app_info.get('category')
        app_entry.tags = app_info.get('tags')
        
        other_metadata = app_info.copy()
        keys_to_remove = ['name', 'icon', 'author', 'description', 'version', 'category', 'tags', 'repository', 'folder_name', 'is_installed', 'has_readme']
        for key in keys_to_remove:
            other_metadata.pop(key, None)
        
        if run_command:
            other_metadata['run_command'] = run_command

        app_entry.app_metadata = other_metadata

        db_session.commit()

    except InterruptedError as e:
        task.log(f"Rollback: {e}", level="WARNING")
        db_session.rollback()
        if dest_path.exists():
            shutil.rmtree(dest_path, ignore_errors=True)
        app_to_clean = db_session.query(DBApp).filter_by(name=app_name).first()
        if app_to_clean and not app_to_clean.is_installed:
            db_session.delete(app_to_clean)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        if dest_path.exists():
            shutil.rmtree(dest_path, ignore_errors=True)
        app_to_update = db_session.query(DBApp).filter_by(name=app_name).first()
        if app_to_update:
            if not app_to_update.is_installed:
                db_session.delete(app_to_update)
            else:
                app_to_update.status = 'error'
            db_session.commit()
        raise e
    finally:
        db_session.close()


@apps_management_router.post("/zoo/install-app", response_model=TaskInfo)
def install_app(install_request: AppInstallRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if install_request.repository == "Custom":
        base_path = CUSTOM_APPS_ROOT_PATH
    else:
        base_path = ZOO_ROOT_PATH / install_request.repository
        
    yaml_path = base_path / install_request.folder_name / "description.yaml"
    if not yaml_path.is_file():
        raise HTTPException(status_code=404, detail="App not found in the specified repository.")
    
    with open(yaml_path, 'r', encoding='utf-8') as f: metadata = yaml.safe_load(f)
    app_name = metadata.get('name')
    if not app_name:
        raise HTTPException(status_code=400, detail="App metadata is invalid (missing name).")

    existing_app_by_name = db.query(DBApp).filter(DBApp.name == app_name, DBApp.is_installed == True).first()
    existing_app_by_port = db.query(DBApp).filter(DBApp.port == install_request.port, DBApp.is_installed == True).first()

    if existing_app_by_port and (not existing_app_by_name or existing_app_by_name.id != existing_app_by_port.id):
         raise HTTPException(status_code=409, detail=f"Port {install_request.port} is already in use by another installed app.")

    icon_base64 = None
    icon_path = yaml_path.parent / "icon.png"
    if icon_path.is_file():
        with open(icon_path, "rb") as image_file: icon_base64 = f"data:image/png;base64,{base64.b64encode(image_file.read()).decode('utf-8')}"
    metadata['icon'] = icon_base64
    metadata['repository'] = install_request.repository
    metadata['folder_name'] = install_request.folder_name

    task = task_manager.submit_task(
        name=f"Installing app: {app_name}",
        target=_install_app_task,
        args=(metadata, install_request.port, install_request.autostart)
    )
    background_tasks.add_task(task.run)
    return TaskInfo(**task.__dict__)

# --- Installed App Management ---

@apps_management_router.get("/installed-apps", response_model=list[AppPublic])
def get_installed_apps(db: Session = Depends(get_db)):
    installed_apps = db.query(DBApp).options(joinedload(DBApp.owner)).filter(DBApp.is_installed == True).all()
    zoo_apps_metadata = _get_zoo_apps_metadata()
    
    response_apps = []
    for app in installed_apps:
        app_public = AppPublic.from_orm(app)
        app_public.update_available = False
        zoo_version_info = zoo_apps_metadata.get(app.name)
        if zoo_version_info:
            try:
                if app.version and zoo_version_info.get('version'):
                    if packaging_version.parse(str(zoo_version_info['version'])) > packaging_version.parse(str(app.version)):
                        app_public.update_available = True
                elif 'last_update_date' in zoo_version_info and (app.app_metadata and 'last_update_date' in app.app_metadata):
                    if zoo_version_info['last_update_date'] > app.app_metadata['last_update_date']:
                        app_public.update_available = True
            except Exception as e:
                print(f"Warning: Could not compare version for app '{app.name}'. Error: {e}")
        response_apps.append(app_public)
    return response_apps

@apps_management_router.post("/installed-apps/{app_id}/start", response_model=TaskInfo, status_code=202)
def start_app(app_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app:
        raise HTTPException(status_code=404, detail="Installed app not found.")
    
    if app.status == 'running':
        raise HTTPException(status_code=400, detail="App is already running.")
    
    task = task_manager.submit_task(
        name=f"Start app: {app.name}",
        target=_start_app_task,
        args=(app_id,),
        description=f"Starting the application '{app.name}' on port {app.port}."
    )
    background_tasks.add_task(task.run)
    return TaskInfo(**task.__dict__)

@apps_management_router.post("/installed-apps/{app_id}/stop", response_model=AppActionResponse)
def stop_app(app_id: str, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app:
        raise HTTPException(status_code=404, detail="Installed app not found.")
    
    if app.status != 'running' or not app.pid:
        app.status = 'stopped'
        app.pid = None
        app.active = False
        db.commit()
        return {"success": True, "message": "App was not running."}
    try:
        os.kill(app.pid, signal.SIGTERM)
        app.pid = None
        app.status = 'stopped'
        app.active = False
        db.commit()
        return {"success": True, "message": f"App '{app.name}' stopped successfully."}
    except ProcessLookupError:
        app.pid = None
        app.status = 'stopped'
        app.active = False
        db.commit()
        return {"success": True, "message": "Process not found, app was likely already stopped."}
    except Exception as e:
        app.status = 'error'
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to stop app: {e}")

@apps_management_router.put("/installed-apps/{app_id}", response_model=AppPublic)
def update_installed_app(app_id: str, app_update: AppUpdate, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app:
        raise HTTPException(status_code=404, detail="Installed app not found.")

    if app.status == 'running':
        raise HTTPException(status_code=409, detail="Cannot update settings while the app is running. Please stop it first.")

    update_data = app_update.model_dump(exclude_unset=True)
    
    if 'port' in update_data and update_data['port'] != app.port:
        if db.query(DBApp).filter(DBApp.port == update_data['port'], DBApp.id != app_id).first():
            raise HTTPException(status_code=409, detail=f"Port {update_data['port']} is already in use by another app.")

    unmodifiable_fields = ['name', 'url', 'active', 'type', 'is_installed', 'status', 'pid', 'folder_name']
    for field in unmodifiable_fields:
        if field in update_data:
            del update_data[field]
    
    for key, value in update_data.items():
        setattr(app, key, value)
    
    try:
        db.commit()
        db.refresh(app)
        app_with_owner = db.query(DBApp).options(joinedload(DBApp.owner)).filter(DBApp.id == app_id).first()
        return AppPublic.from_orm(app_with_owner)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error while updating app: {e}")

@apps_management_router.get("/installed-apps/{app_id}/logs", response_model=AppLog)
def get_app_logs(app_id: str, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app:
        raise HTTPException(status_code=404, detail="Installed app not found.")

    app_folder_name = app.folder_name
    if not app_folder_name:
        return AppLog(log_content="App installation is corrupted: missing folder name.")
        
    app_path = APPS_ROOT_PATH / app_folder_name
    log_file_path = app_path / "app.log"

    if not log_file_path.is_file():
        return AppLog(log_content="Log file not found. The app may not have been started yet.")

    try:
        log_content = log_file_path.read_text(encoding="utf-8")
        return AppLog(log_content=log_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read log file: {e}")

@apps_management_router.delete("/installed-apps/{app_id}", response_model=AppActionResponse)
def uninstall_app(app_id: str, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app:
        raise HTTPException(status_code=404, detail="Installed app not found.")
    if app.status == 'running' and app.pid:
        try:
            os.kill(app.pid, signal.SIGTERM)
        except Exception as e:
            print(f"Warning: Could not stop process {app.pid} during uninstall: {e}")

    app_folder_name = app.folder_name
    if app_folder_name:
        app_path = APPS_ROOT_PATH / app_folder_name
        if app_path.exists():
            shutil.rmtree(app_path, ignore_errors=True)
    
    db.delete(app)
    db.commit()
    
    return {"success": True, "message": f"App '{app.name}' has been uninstalled."}