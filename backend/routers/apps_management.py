import base64
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
import os
import signal
import datetime
import time
import re
import json
import yaml
import toml
from jsonschema import validate, ValidationError
from packaging import version as packaging_version
import psutil
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session, joinedload
from pydantic import ValidationError as PydanticValidationError

from backend.db import get_db
from backend.db.models.service import AppZooRepository as DBAppZooRepository, App as DBApp, MCPZooRepository as DBMCPZooRepository, MCP as DBMCP
from backend.db.models.db_task import DBTask
from backend.models import (
    AppZooRepositoryCreate, AppZooRepositoryPublic, ZooAppInfo, ZooAppInfoResponse,
    AppInstallRequest, AppPublic, AppActionResponse, TaskInfo,
    AppUpdate, AppLog, MCPZooRepositoryCreate, MCPZooRepositoryPublic, ZooMCPInfo, ZooMCPInfoResponse
)
from backend.session import get_current_admin_user
from backend.config import ZOO_ROOT_PATH, APPS_ROOT_PATH, MCP_ZOO_ROOT_PATH, MCPS_ROOT_PATH
from backend.task_manager import task_manager, Task
from backend.zoo_cache import get_all_items, get_all_categories, build_full_cache, refresh_repo_cache

from backend.settings import settings
from typing import Optional

apps_management_router = APIRouter(
    prefix="/api/apps-management",
    tags=["Apps Management"],
    dependencies=[Depends(get_current_admin_user)]
)

def _get_installed_app_path(db: Session, app_id: str) -> Path:
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app or not app.folder_name:
        raise HTTPException(status_code=404, detail="Installed app not found or is corrupted.")
    
    if app.app_metadata and app.app_metadata.get('item_type') == 'mcp':
        return MCPS_ROOT_PATH / app.folder_name
    
    # Fallback for older installations
    if (MCPS_ROOT_PATH / app.folder_name).exists():
        return MCPS_ROOT_PATH / app.folder_name
        
    return APPS_ROOT_PATH / app.folder_name


def _generate_unique_client_id(db: Session, model_class, name: str) -> str:
    base_slug = re.sub(r'[^a-z0-9_]+', '', name.lower().replace(' ', '_'))
    client_id = base_slug
    counter = 1
    while db.query(model_class).filter(model_class.client_id == client_id).first():
        client_id = f"{base_slug}_{counter}"
        counter += 1
    return client_id

def _to_task_info(db_task: DBTask) -> TaskInfo:
    """Converts a DBTask SQLAlchemy model to a TaskInfo Pydantic model."""
    if not db_task:
        return None
    return TaskInfo(
        id=db_task.id, name=db_task.name, description=db_task.description,
        status=db_task.status, progress=db_task.progress,
        logs=[log for log in (db_task.logs or [])], result=db_task.result, error=db_task.error,
        created_at=db_task.created_at, started_at=db_task.started_at, completed_at=db_task.completed_at,
        file_name=db_task.file_name, total_files=db_task.total_files,
        owner_username=db_task.owner.username if db_task.owner else "System"
    )

open_log_files: Dict[str, Any] = {}


# --- Startup and Task Functions ---
def _cleanup_and_autostart_apps():
    """
    Called on server startup to clean app statuses and autostart designated apps.
    """
    db_session = None
    print("INFO: Performing startup app cleanup and autostart...")
    try:
        db_session = next(get_db())
        
        installed_apps = db_session.query(DBApp).filter(DBApp.is_installed == True).all()
        updated_count = 0
        for app in installed_apps:
            if app.status != 'stopped' or app.pid is not None:
                app.status = 'stopped'
                app.pid = None
                updated_count += 1
        
        if updated_count > 0:
            db_session.commit()
            print(f"INFO: Reset status for {updated_count} apps to 'stopped'.")
        else:
            print("INFO: All app statuses were already clean.")

        apps_to_autostart = db_session.query(DBApp).filter(
            DBApp.is_installed == True,
            DBApp.autostart == True
        ).all()

        if apps_to_autostart:
            print(f"INFO: Found {len(apps_to_autostart)} apps to autostart.")
            for app in apps_to_autostart:
                print(f"INFO: Submitting autostart task for '{app.name}' (ID: {app.id})")
                task_manager.submit_task(
                    name=f"Autostart app: {app.name}",
                    target=_start_app_task,
                    args=(app.id,),
                    description=f"Automatically starting '{app.name}' on server boot.",
                    owner_username=None
                )
        else:
            print("INFO: No apps configured for autostart.")

    except Exception as e:
        print(f"CRITICAL: Failed during app startup management. Error: {e}")
        traceback.print_exc()
        if db_session:
            db_session.rollback()
    finally:
        if db_session:
            db_session.close()

def _start_app_task(task: Task, app_id: str):
    db_session = next(get_db())
    app = None
    process = None
    log_file_handle = None
    try:
        app_path = _get_installed_app_path(db_session, app_id)

        app = db_session.query(DBApp).filter(DBApp.id == app_id).first()
        if not app: raise ValueError("Installed app metadata not found.")

        if not app_path.exists():
            app.status = 'error'
            db_session.commit()
            raise FileNotFoundError(f"App directory not found at {app_path}")

        log_file_path = app_path / "app.log"
        if log_file_path.exists():
            try:
                log_file_path.unlink()
            except OSError as e:
                task.log(f"Could not clear old log file: {e}", "WARNING")
        
        log_file_handle = open(log_file_path, "w", encoding="utf-8", buffering=1)

        venv_path = app_path / "venv"
        python_executable = venv_path / ("Scripts" if sys.platform == "win32" else "bin") / "python"
        
        command = None
        if app.app_metadata and 'run_command' in app.app_metadata:
            run_command_template = app.app_metadata['run_command']
            command = [str(arg).replace("{python_executable}", str(python_executable)).replace("{port}", str(app.port)) for arg in run_command_template]
        else:
            item_type = app.app_metadata.get('item_type', 'app') if app.app_metadata else 'app'
            if item_type == 'mcp':
                server_script = app_path / "server.py"
                if not server_script.is_file():
                    raise FileNotFoundError(f"MCP start failed: server.py not found in {app_path}")
                command = [str(python_executable), "server.py", "--port", str(app.port)]
            else: # Default to app
                command = [str(python_executable), "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", str(app.port)]

        task.log(f"Executing start command: {' '.join(command)}")
        task.log(f"Redirecting output to: {log_file_path}")
        task.set_progress(20)

        process = subprocess.Popen(command, cwd=str(app_path), stdout=log_file_handle, stderr=subprocess.STDOUT)
        
        open_log_files[app.id] = log_file_handle
        task.process = process

        task.log("Monitoring application start-up for 5 seconds...")
        time.sleep(5) 
        
        return_code = process.poll()
        if return_code is not None:
            task.log(f"Process exited prematurely with code {return_code}. Start-up failed.", "ERROR")
            app.status = 'error'
            app.pid = None
            db_session.commit()
            raise Exception("Application failed to start. Check task logs and app.log for details.")

        app.pid = process.pid
        app.status = 'running'
        app.url = f"http://localhost:{app.port}"
        app.active = True
        db_session.commit()
        
        task.log(f"App '{app.name}' appears to have started successfully with PID {process.pid} on port {app.port}.")
        task.log("Note: This task is complete, but the app process runs independently.")
        task.set_progress(100)
        return {"success": True, "message": f"App '{app.name}' started successfully."}

    except Exception as e:
        task.log(f"Failed to start app: {e}", level="CRITICAL")
        if log_file_handle: log_file_handle.close()
        if app_id in open_log_files: del open_log_files[app_id]
        if app:
            app.status = 'error'
            db_session.commit()
        if process and process.poll() is None:
            process.terminate()
        raise e
    finally:
        db_session.close()

def _stop_app_task(task: Task, app_id: str):
    db_session = next(get_db())
    app = None
    try:
        task.log("Fetching app details from database...")
        app = db_session.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
        if not app:
            raise ValueError("Installed app not found.")

        if not app.pid:
            task.log("App has no PID. Assuming it is already stopped.", "WARNING")
            app.status = 'stopped'
            db_session.commit()
            task.set_progress(100)
            return {"success": True, "message": "App was already stopped."}

        pid = app.pid
        task.log(f"Attempting to stop process with PID: {pid}")
        task.set_progress(20)

        try:
            process = psutil.Process(pid)
            task.log("Sending SIGTERM signal...")
            process.terminate()
            
            try:
                process.wait(timeout=5)
                task.log("Process terminated gracefully.")
            except psutil.TimeoutExpired:
                task.log("Process did not terminate gracefully. Sending SIGKILL...", "WARNING")
                process.kill()
                process.wait(timeout=2)
                task.log("Process killed.")

            task.set_progress(80)

        except psutil.NoSuchProcess:
            task.log(f"Process with PID {pid} not found. It may have already been stopped.", "WARNING")
        
        except Exception as e:
            task.log(f"An error occurred while stopping the process: {e}", "ERROR")
        
        task.log("Updating app status in database...")
        app.pid = None
        app.status = 'stopped'
        db_session.commit()
        
        if app.id in open_log_files:
            task.log("Closing app log file handle.")
            open_log_files[app.id].close()
            del open_log_files[app.id]

        task.set_progress(100)
        return {"success": True, "message": f"App '{app.name}' stopped successfully."}

    except Exception as e:
        task.log(f"Failed to execute stop task: {e}", level="CRITICAL")
        if app:
            app.status = 'error'
            db_session.commit()
        raise e
    finally:
        db_session.close()

def _install_item_task(task: Task, repository: str, folder_name: str, port: int, autostart: bool, source_root_path: Path):
    db_session = next(get_db())
    item_info = {}
    try:
        is_mcp = source_root_path == MCP_ZOO_ROOT_PATH
        source_item_path = source_root_path / repository / folder_name
        if not source_item_path.exists():
            raise FileNotFoundError(f"Source directory not found at {source_item_path}")
        
        info_file_name = "app_info.yaml"
        if not (source_item_path / info_file_name).exists():
            info_file_name = "description.yaml"

        with open(source_item_path / info_file_name, "r", encoding='utf-8') as f:
            item_info = yaml.safe_load(f)
        
        item_name = item_info.get("name", folder_name)

        if db_session.query(DBApp).filter(DBApp.name == item_name, DBApp.is_installed == True).first():
            task.log(f"Item '{item_name}' is already installed. Reinstalling...", "WARNING")
            existing_app = db_session.query(DBApp).filter(DBApp.name == item_name).first()
            if existing_app:
                if existing_app.pid:
                    try: os.kill(existing_app.pid, signal.SIGTERM)
                    except Exception: pass
                db_session.delete(existing_app)
                db_session.commit()
        
        dest_app_path = (MCPS_ROOT_PATH if is_mcp else APPS_ROOT_PATH) / folder_name
        
        task.log(f"Copying files from {source_item_path} to {dest_app_path}")
        task.set_progress(10)
        shutil.copytree(source_item_path, dest_app_path, dirs_exist_ok=True)
        task.set_progress(30)
        
        task.log("Creating virtual environment...")
        venv_path = dest_app_path / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True, capture_output=True, text=True)
        task.set_progress(50)

        task.log("Installing dependencies from requirements.txt...")
        pip_executable = venv_path / ("Scripts" if sys.platform == "win32" else "bin") / "pip"
        requirements_path = dest_app_path / "requirements.txt"
        
        if requirements_path.exists():
            install_process = subprocess.run([str(pip_executable), "install", "-r", str(requirements_path)], check=True, capture_output=True, text=True)
            task.log(install_process.stdout)
        else:
            task.log("No requirements.txt found, skipping dependency installation.", "WARNING")
        
        task.set_progress(80)

        icon_path = dest_app_path / "assets" / "logo.png"
        if not icon_path.exists():
            icon_path = dest_app_path / "icon.png"

        icon_base64 = None
        if icon_path.exists():
            icon_base64 = f"data:image/png;base64,{base64.b64encode(icon_path.read_bytes()).decode()}"

        item_info['item_type'] = 'mcp' if is_mcp else 'app'
        
        client_id = _generate_unique_client_id(db_session, DBApp, item_name)
        new_app = DBApp(
            name=item_name, client_id=client_id, folder_name=folder_name,
            icon=icon_base64, is_installed=True, status='stopped',
            port=port, autostart=autostart,
            version=str(item_info.get('version', 'N/A')), author=item_info.get('author'),
            description=item_info.get('description'), category=item_info.get('category'),
            tags=item_info.get('tags'), app_metadata=item_info,
        )
        db_session.add(new_app)
        db_session.commit()
        db_session.refresh(new_app)

        if is_mcp:
            task.log(f"Registering '{item_name}' as a system MCP server.")
            existing_mcp = db_session.query(DBMCP).filter(DBMCP.name == item_name, DBMCP.type == 'system').first()
            
            if existing_mcp:
                task.log(f"System MCP '{item_name}' already exists. Updating its URL and icon.", "WARNING")
                existing_mcp.url = f"http://localhost:{port}"
                existing_mcp.icon = icon_base64
                existing_mcp.active = True
            else:
                mcp_client_id = _generate_unique_client_id(db_session, DBMCP, item_name)
                new_mcp = DBMCP(
                    name=item_name,
                    client_id=mcp_client_id,
                    url=f"http://localhost:{port}",
                    icon=icon_base64,
                    active=True,
                    type='system',
                    owner_user_id=None
                )
                db_session.add(new_mcp)
            db_session.commit()
            task.log("Successfully registered system MCP.")
        else: # This is a regular app
            task.log(f"Registering '{item_name}' as a system App.")
            existing_system_app = db_session.query(DBApp).filter(
                DBApp.name == item_name,
                DBApp.type == 'system',
                DBApp.is_installed == False
            ).first()

            if existing_system_app:
                task.log(f"System App '{item_name}' already exists. Updating its URL and icon.", "WARNING")
                existing_system_app.url = f"http://localhost:{port}"
                existing_system_app.icon = icon_base64
                existing_system_app.active = True
            else:
                app_client_id = _generate_unique_client_id(db_session, DBApp, item_name)
                new_system_app = DBApp(
                    name=item_name,
                    client_id=app_client_id,
                    url=f"http://localhost:{port}",
                    icon=icon_base64,
                    active=True,
                    type='system',
                    is_installed=False, # This is a pointer to the installed service
                    owner_user_id=None,
                    description=item_info.get('description'),
                    author=item_info.get('author'),
                    version=str(item_info.get('version', 'N/A')),
                    category=item_info.get('category'),
                    tags=item_info.get('tags')
                )
                db_session.add(new_system_app)
            db_session.commit()
            task.log("Successfully registered system App.")

        task.set_progress(100)
        task.log(f"Item '{item_name}' installed successfully.")
        
        if autostart:
            task.log("Autostart is enabled. Initiating start...")
            _start_app_task(task, new_app.id)

        return {"success": True, "message": "Installation successful."}

    except Exception as e:
        traceback.print_exc()
        if isinstance(e, subprocess.CalledProcessError):
            task.log("Subprocess failed.", "CRITICAL")
            task.log(f"STDOUT: {e.stdout}", "ERROR")
            task.log(f"STDERR: {e.stderr}", "ERROR")
        raise e
    finally:
        db_session.close()


def _pull_repo_task(task: Task, repo_id: int, repo_model, root_path: Path, item_type: str):
    db_session = next(get_db())
    repo = None
    try:
        repo = db_session.query(repo_model).filter(repo_model.id == repo_id).first()
        if not repo: raise ValueError("Repository not found.")

        repo_path = root_path / repo.name
        task.log(f"Repository path: {repo_path}")
        task.set_progress(10)
        
        command = ["git", "clone", repo.url, repo.name] if not repo_path.exists() else ["git", "pull"]
        cwd = str(root_path) if not repo_path.exists() else str(repo_path)
        
        task.log(f"Executing command: {' '.join(command)} in {cwd}")
        process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        task.process = process
        
        for line in iter(process.stdout.readline, ''):
            if task.cancellation_event.is_set():
                task.log("Cancellation requested, terminating git process.", "WARNING")
                process.terminate()
                break
            task.log(line.strip(), "GIT_STDOUT")

        process.wait()

        if process.returncode != 0:
            stderr_output = process.stderr.read()
            raise Exception(f"Git operation failed. Stderr: {stderr_output.strip()}")
        
        task.log("Git operation completed successfully.")
        task.set_progress(90)
        
        repo.last_pulled_at = datetime.datetime.now(datetime.timezone.utc)
        db_session.commit()
        
        refresh_repo_cache(repo.name, item_type)
        
        task.log("Updated repository pull time and refreshed cache.")
        task.set_progress(100)
        return {"message": "Repository pulled successfully."}

    except Exception as e:
        if repo:
            repo.last_pulled_at = None
            db_session.commit()
        raise e
    finally:
        db_session.close()

# --- New Cache Management Endpoints ---
@apps_management_router.post("/zoo/rescan", response_model=Dict[str, str])
def rescan_all_zoos():
    try:
        build_full_cache()
        return {"message": "Full Zoo cache rebuild initiated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start cache rebuild: {e}")

@apps_management_router.get("/app-zoo/categories", response_model=List[str])
def get_app_zoo_categories():
    return get_all_categories('app')

@apps_management_router.get("/mcp-zoo/categories", response_model=List[str])
def get_mcp_zoo_categories():
    return get_all_categories('mcp')


# --- App Zoo Endpoints ---
@apps_management_router.get("/app-zoo/repositories", response_model=list[AppZooRepositoryPublic])
def get_app_zoo_repositories(db: Session = Depends(get_db)):
    return db.query(DBAppZooRepository).all()

@apps_management_router.post("/app-zoo/repositories", response_model=AppZooRepositoryPublic, status_code=201)
def add_app_zoo_repository(repo: AppZooRepositoryCreate, db: Session = Depends(get_db)):
    if db.query(DBAppZooRepository).filter(DBAppZooRepository.name == repo.name).first():
        raise HTTPException(status_code=409, detail="A repository with this name already exists.")
    if db.query(DBAppZooRepository).filter(DBAppZooRepository.url == repo.url).first():
        raise HTTPException(status_code=409, detail="A repository with this URL already exists.")
    
    new_repo = DBAppZooRepository(**repo.model_dump())
    db.add(new_repo)
    db.commit()
    db.refresh(new_repo)
    build_full_cache()
    return new_repo

@apps_management_router.delete("/app-zoo/repositories/{repo_id}", status_code=204)
def delete_app_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBAppZooRepository).filter(DBAppZooRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")
    if not repo.is_deletable:
        raise HTTPException(status_code=403, detail="This is a default repository and cannot be deleted.")
    
    repo_path = ZOO_ROOT_PATH / repo.name
    if repo_path.exists():
        shutil.rmtree(repo_path, ignore_errors=True)
    
    db.delete(repo)
    db.commit()
    build_full_cache()
    return None

@apps_management_router.post("/app-zoo/repositories/{repo_id}/pull", response_model=TaskInfo, status_code=202)
def pull_app_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBAppZooRepository).filter(DBAppZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    db_task = task_manager.submit_task(
        name=f"Pulling App repository: {repo.name}",
        target=_pull_repo_task,
        args=(repo_id, DBAppZooRepository, ZOO_ROOT_PATH, 'app'),
        description=f"Updating local copy of '{repo.name}' from '{repo.url}'."
    )
    return _to_task_info(db_task)

@apps_management_router.get("/app-zoo/available-apps", response_model=ZooAppInfoResponse)
def get_available_zoo_apps(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    sort_by: str = Query('last_update_date'),
    sort_order: str = Query('desc'),
    category: Optional[str] = Query(None),
    search_query: Optional[str] = Query(None),
    installation_status: Optional[str] = Query(None)
):
    all_items_raw = get_all_items('app')
    installed_apps = {app.name for app in db.query(DBApp.name).filter(DBApp.is_installed == True).all()}
    
    all_items = []
    for info in all_items_raw:
        try:
            model_data = {
                "name": info.get('name'), "repository": info.get('repository'), "folder_name": info.get('folder_name'),
                "icon": info.get('icon'),
                "is_installed": info.get('name') in installed_apps, "has_readme": (ZOO_ROOT_PATH / info['repository'] / info['folder_name'] / "README.md").exists(),
                **{f: info.get(f) for f in ZooAppInfo.model_fields if f not in ['name', 'repository', 'folder_name', 'is_installed', 'has_readme', 'icon']}
            }
            all_items.append(ZooAppInfo(**model_data))
        except (PydanticValidationError, Exception) as e:
            print(f"ERROR: Could not process cached app data for {info.get('name')}. Error: {e}")

    # Filtering
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

    # Sorting
    def sort_key_func(item):
        val = getattr(item, sort_by, None)
        if 'date' in sort_by:
            if val:
                try: return datetime.datetime.fromisoformat(val).timestamp()
                except (ValueError, TypeError): return 0.0
            else: return 0.0
        return str(val or '').lower()
    
    all_items.sort(key=sort_key_func, reverse=(sort_order == 'desc'))

    # Pagination
    total_items = len(all_items)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_items = all_items[start:end]

    return ZooAppInfoResponse(
        items=paginated_items, total=total_items, page=page,
        pages=(total_items + page_size - 1) // page_size if page_size > 0 else 0
    )


@apps_management_router.get("/app-zoo/app-readme", response_class=PlainTextResponse)
def get_app_readme(repository: str, folder_name: str):
    readme_path = ZOO_ROOT_PATH / repository / folder_name / "README.md"
    if not readme_path.exists():
        raise HTTPException(status_code=404, detail="README.md not found for this app.")
    return readme_path.read_text(encoding="utf-8")

@apps_management_router.post("/app-zoo/install-app", response_model=TaskInfo, status_code=202)
def install_zoo_app(request: AppInstallRequest):
    db_task = task_manager.submit_task(
        name=f"Installing app: {request.folder_name}",
        target=_install_item_task,
        args=(request.repository, request.folder_name, request.port, request.autostart, ZOO_ROOT_PATH),
        description=f"Installing from repository '{request.repository}'."
    )
    return _to_task_info(db_task)

# --- MCP ZOO ENDPOINTS ---

@apps_management_router.get("/mcp-zoo/repositories", response_model=list[MCPZooRepositoryPublic])
def get_mcp_zoo_repositories(db: Session = Depends(get_db)):
    return db.query(DBMCPZooRepository).all()

@apps_management_router.post("/mcp-zoo/repositories", response_model=MCPZooRepositoryPublic, status_code=201)
def add_mcp_zoo_repository(repo: MCPZooRepositoryCreate, db: Session = Depends(get_db)):
    if db.query(DBMCPZooRepository).filter(DBMCPZooRepository.name == repo.name).first():
        raise HTTPException(status_code=409, detail="A repository with this name already exists.")
    if db.query(DBMCPZooRepository).filter(DBMCPZooRepository.url == repo.url).first():
        raise HTTPException(status_code=409, detail="A repository with this URL already exists.")
    
    new_repo = DBMCPZooRepository(**repo.model_dump(), is_deletable=True)
    db.add(new_repo)
    db.commit()
    db.refresh(new_repo)
    build_full_cache()
    return new_repo

@apps_management_router.delete("/mcp-zoo/repositories/{repo_id}", status_code=204)
def delete_mcp_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBMCPZooRepository).filter(DBMCPZooRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")
    if not repo.is_deletable:
        raise HTTPException(status_code=403, detail="This is a default repository and cannot be deleted.")
    
    repo_path = MCP_ZOO_ROOT_PATH / repo.name
    if repo_path.exists():
        shutil.rmtree(repo_path, ignore_errors=True)
    
    db.delete(repo)
    db.commit()
    build_full_cache()
    return None

@apps_management_router.post("/mcp-zoo/repositories/{repo_id}/pull", response_model=TaskInfo, status_code=202)
def pull_mcp_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBMCPZooRepository).filter(DBMCPZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    db_task = task_manager.submit_task(
        name=f"Pulling MCP repository: {repo.name}",
        target=_pull_repo_task,
        args=(repo_id, DBMCPZooRepository, MCP_ZOO_ROOT_PATH, 'mcp'),
        description=f"Updating local copy of '{repo.name}' from '{repo.url}'."
    )
    return _to_task_info(db_task)

@apps_management_router.get("/mcp-zoo/available-mcps", response_model=ZooMCPInfoResponse)
def get_available_zoo_mcps(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    sort_by: str = Query('last_update_date'),
    sort_order: str = Query('desc'),
    category: Optional[str] = Query(None),
    search_query: Optional[str] = Query(None),
    installation_status: Optional[str] = Query(None)
):
    all_items_raw = get_all_items('mcp')
    installed_items_query = db.query(DBApp.name).filter(
        DBApp.is_installed == True, 
        DBApp.app_metadata['item_type'].as_string() == 'mcp'
    ).all()
    installed_items = {item.name for item in installed_items_query}
    all_items = []

    for info in all_items_raw:
        try:
            model_data = {
                "name": info.get('name'), "repository": info.get('repository'), "folder_name": info.get('folder_name'),
                "icon": info.get('icon'),
                "is_installed": info.get('name') in installed_items, "has_readme": (MCP_ZOO_ROOT_PATH / info['repository'] / info['folder_name'] / "README.md").exists(),
                **{f: info.get(f) for f in ZooMCPInfo.model_fields if f not in ['name', 'repository', 'folder_name', 'is_installed', 'has_readme', 'icon']}
            }
            all_items.append(ZooMCPInfo(**model_data))
        except (PydanticValidationError, Exception) as e:
            print(f"ERROR: Could not process cached mcp data for {info.get('name')}. Error: {e}")

    # Filtering
    if installation_status:
        if installation_status == 'Installed': all_items = [item for item in all_items if item.is_installed]
        elif installation_status == 'Uninstalled': all_items = [item for item in all_items if not item.is_installed]
    if category and category != 'All': all_items = [item for item in all_items if item.category == category]
    if search_query:
        q = search_query.lower()
        all_items = [item for item in all_items if q in item.name.lower() or (item.description and q in item.description.lower()) or (item.author and q in item.author.lower())]

    # Sorting
    def sort_key_func(item):
        val = getattr(item, sort_by, None)
        if 'date' in sort_by:
            if val:
                try: return datetime.datetime.fromisoformat(val).timestamp()
                except (ValueError, TypeError): return 0.0
            else: return 0.0
        return str(val or '').lower()
    
    all_items.sort(key=sort_key_func, reverse=(sort_order == 'desc'))

    # Pagination
    total_items = len(all_items)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_items = all_items[start:end]

    return ZooMCPInfoResponse(
        items=paginated_items, total=total_items, page=page,
        pages=(total_items + page_size - 1) // page_size if page_size > 0 else 0
    )


@apps_management_router.get("/mcp-zoo/mcp-readme", response_class=PlainTextResponse)
def get_mcp_readme(repository: str, folder_name: str):
    readme_path = MCP_ZOO_ROOT_PATH / repository / folder_name / "README.md"
    if not readme_path.exists():
        raise HTTPException(status_code=404, detail="README.md not found for this mcp.")
    return readme_path.read_text(encoding="utf-8")

@apps_management_router.post("/mcp-zoo/install-mcp", response_model=TaskInfo, status_code=202)
def install_zoo_mcp(request: AppInstallRequest):
    db_task = task_manager.submit_task(
        name=f"Installing MCP: {request.folder_name}",
        target=_install_item_task,
        args=(request.repository, request.folder_name, request.port, request.autostart, MCP_ZOO_ROOT_PATH),
        description=f"Installing MCP from repository '{request.repository}'."
    )
    return _to_task_info(db_task)


# --- Installed App Management (Shared by Apps and MCPs) ---
def _get_all_zoo_metadata():
    all_items_dict = {}
    for item in get_all_items('app') + get_all_items('mcp'):
        all_items_dict[item['name']] = item
    return all_items_dict

@apps_management_router.get("/installed-apps", response_model=list[AppPublic])
def get_installed_apps(db: Session = Depends(get_db)):
    installed_apps = db.query(DBApp).options(joinedload(DBApp.owner)).filter(DBApp.is_installed == True).all()
    zoo_metadata = _get_all_zoo_metadata()
    
    response_apps = []
    for app in installed_apps:
        app_public = AppPublic.from_orm(app)
        app_public.update_available = False

        # Determine item_type with fallback for older installations
        if app.app_metadata and 'item_type' in app.app_metadata:
            app_public.item_type = app.app_metadata.get('item_type')
        else:
            if (MCPS_ROOT_PATH / app.folder_name).exists():
                app_public.item_type = 'mcp'
            else:
                app_public.item_type = 'app'

        app_path = _get_installed_app_path(db, app.id)
        if (app_path / 'schema.config.json').is_file():
            app_public.has_config_schema = True

        zoo_version_info = zoo_metadata.get(app.name)
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

@apps_management_router.get("/installed-apps/{app_id}/config-schema", response_model=Dict[str, Any])
def get_app_config_schema(app_id: str, db: Session = Depends(get_db)):
    app_path = _get_installed_app_path(db, app_id)
    schema_path = app_path / 'schema.config.json'
    if not schema_path.is_file():
        return {}
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read or parse schema.config.json: {e}")

@apps_management_router.get("/installed-apps/{app_id}/config", response_model=Dict[str, Any])
def get_app_config(app_id: str, db: Session = Depends(get_db)):
    app_path = _get_installed_app_path(db, app_id)
    schema_path = app_path / 'schema.config.json'
    if not schema_path.is_file():
        # Fallback for installed items without a schema
        app_record = db.query(DBApp).filter(DBApp.id == app_id).first()
        if app_record:
            return {"config": {"port": app_record.port, "autostart": app_record.autostart}, "metadata": {}}
        return {"config": {}, "metadata": {}}

    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not load config schema.")

    config = {key: prop.get('default') for key, prop in schema.get('properties', {}).items()}
    
    config_yaml_path = app_path / 'config.yaml'
    config_toml_path = app_path / 'config.toml'
    file_config = {}
    if config_yaml_path.is_file():
        with open(config_yaml_path, 'r', encoding='utf-8') as f:
            file_config = yaml.safe_load(f) or {}
    elif config_toml_path.is_file():
        with open(config_toml_path, 'r', encoding='utf-8') as f:
            file_config = toml.load(f) or {}
    config.update(file_config)
    
    metadata = {"env_overrides": [], "sensitive_keys": []}
    for key, prop in schema.get('properties', {}).items():
        env_var = prop.get('envVar')
        if env_var and env_var in os.environ:
            env_value = os.environ[env_var]
            prop_type = prop.get('type')
            try:
                if prop_type == 'integer':
                    config[key] = int(env_value)
                elif prop_type == 'number':
                    config[key] = float(env_value)
                elif prop_type == 'boolean':
                    config[key] = env_value.lower() in ['true', '1', 'yes']
                else:
                    config[key] = env_value
            except ValueError:
                config[key] = env_value
            
            metadata["env_overrides"].append(key)
        
        if prop.get('sensitive'):
            metadata["sensitive_keys"].append(key)
            if key not in metadata["env_overrides"]:
                config[key] = "********"
                
    return {"config": config, "metadata": metadata}


@apps_management_router.put("/installed-apps/{app_id}/config", response_model=AppActionResponse)
def set_app_config(app_id: str, config_data: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    app_path = _get_installed_app_path(db, app_id)
    schema_path = app_path / 'schema.config.json'
    if not schema_path.is_file():
        raise HTTPException(status_code=404, detail="No configuration schema found for this app.")

    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        validate(instance=config_data, schema=schema)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Schema file disappeared.")
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration data: {e.message}")

    config_yaml_path = app_path / 'config.yaml'
    final_config = {}
    if config_yaml_path.is_file():
        with open(config_yaml_path, 'r', encoding='utf-8') as f:
            final_config = yaml.safe_load(f) or {}

    for key, prop in schema.get('properties', {}).items():
        if key in config_data and not prop.get('envVar'):
            final_config[key] = config_data[key]
    
    try:
        with open(config_yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(final_config, f, sort_keys=False)
        return AppActionResponse(success=True, message="Configuration saved successfully.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write configuration file: {e}")

@apps_management_router.post("/installed-apps/{app_id}/start", response_model=TaskInfo, status_code=202)
def start_app(app_id: str, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app:
        raise HTTPException(status_code=404, detail="Installed app not found.")
    
    if app.status == 'running':
        raise HTTPException(status_code=400, detail="App is already running.")
    
    db_task = task_manager.submit_task(
        name=f"Start app: {app.name}",
        target=_start_app_task,
        args=(app.id,),
        description=f"Starting the application '{app.name}' on port {app.port}."
    )
    return _to_task_info(db_task)

@apps_management_router.post("/installed-apps/{app_id}/stop", response_model=TaskInfo, status_code=202)
def stop_app(app_id: str, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app:
        raise HTTPException(status_code=404, detail="Installed app not found.")
    
    if app.status == 'stopped' and not app.pid:
        raise HTTPException(status_code=400, detail="App is already stopped.")

    db_task = task_manager.submit_task(
        name=f"Stop app: {app.name}",
        target=_stop_app_task,
        args=(app.id,),
        description=f"Stopping the application '{app.name}'."
    )
    return _to_task_info(db_task)


@apps_management_router.put("/installed-apps/{app_id}", response_model=AppPublic)
def update_installed_app(app_id: str, app_update: AppUpdate, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app:
        raise HTTPException(status_code=404, detail="Installed app not found.")

    if app.status == 'running':
        raise HTTPException(status_code=409, detail="Cannot update settings while the app is running. Please stop it first.")

    update_data = app_update.model_dump(exclude_unset=True)
    
    if 'port' in update_data and update_data['port'] != app.port:
        if db.query(DBApp).filter(DBApp.port == update_data['port'], DBApp.id != app.id).first():
            raise HTTPException(status_code=409, detail=f"Port {update_data['port']} is already in use by another app.")

    unmodifiable_fields = ['name', 'url', 'active', 'type', 'is_installed', 'status', 'pid', 'folder_name', 'client_id']
    for field in unmodifiable_fields:
        if field in update_data:
            del update_data[field]
    
    for key, value in update_data.items():
        setattr(app, key, value)
    
    try:
        db.commit()
        db.refresh(app)
        app_with_owner = db.query(DBApp).options(joinedload(DBApp.owner)).filter(DBApp.id == app_id).first()
        return app_with_owner
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error while updating app: {e}")

@apps_management_router.get("/installed-apps/{app_id}/logs", response_model=AppLog)
def get_app_logs(app_id: str, db: Session = Depends(get_db)):
    app_path = _get_installed_app_path(db, app_id)
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

    if app.id in open_log_files:
        try:
            open_log_files[app.id].close()
            del open_log_files[app.id]
            print(f"INFO: Closed dangling log file handle for uninstalled app '{app.name}'.")
        except Exception as e:
            print(f"Warning: Could not close log file for app '{app.name}' during uninstall: {e}")

    app_name = app.name 
    app_path = _get_installed_app_path(db, app.id)
    
    if app_path.exists():
        shutil.rmtree(app_path, ignore_errors=True)
    
    corresponding_mcp = db.query(DBMCP).filter(DBMCP.name == app_name, DBMCP.type == 'system').first()
    if corresponding_mcp:
        print(f"INFO: Deleting corresponding system MCP entry for uninstalled app '{app_name}'.")
        db.delete(corresponding_mcp)

    corresponding_app = db.query(DBApp).filter(
        DBApp.name == app_name,
        DBApp.type == 'system',
        DBApp.is_installed == False
    ).first()
    if corresponding_app:
        print(f"INFO: Deleting corresponding system App entry for uninstalled app '{app_name}'.")
        db.delete(corresponding_app)

    db.delete(app)
    db.commit()
    
    return {"success": True, "message": f"App '{app.name}' has been uninstalled."}


@apps_management_router.get("/apps/get-next-available-port", response_model=Dict[str, int])
def get_next_available_port(port: Optional[int] = Query(None), db: Session = Depends(get_db)):
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