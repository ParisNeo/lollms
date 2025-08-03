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
from packaging import version as packaging_version
import psutil
from typing import Dict, Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session, joinedload

from backend.db import get_db
from backend.db.models.service import AppZooRepository as DBAppZooRepository, App as DBApp, MCPZooRepository as DBMCPZooRepository
from backend.db.models.db_task import DBTask
from backend.models import (
    AppZooRepositoryCreate, AppZooRepositoryPublic, ZooAppInfo, 
    AppInstallRequest, AppPublic, AppActionResponse, TaskInfo,
    AppUpdate, AppLog, MCPZooRepositoryCreate, MCPZooRepositoryPublic, ZooMCPInfo
)
from backend.session import get_current_admin_user
from backend.config import APP_DATA_DIR, ZOO_DIR_NAME, APPS_DIR_NAME, CUSTOM_APPS_DIR_NAME, MCP_ZOO_DIR_NAME
from backend.task_manager import task_manager, Task

from backend.settings import settings
from typing import Optional

apps_management_router = APIRouter(
    prefix="/api/apps-management",
    tags=["Apps Management"],
    dependencies=[Depends(get_current_admin_user)]
)

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

ZOO_ROOT_PATH = APP_DATA_DIR / ZOO_DIR_NAME
ZOO_ROOT_PATH.mkdir(parents=True, exist_ok=True)
MCP_ZOO_ROOT_PATH = APP_DATA_DIR / MCP_ZOO_DIR_NAME
MCP_ZOO_ROOT_PATH.mkdir(parents=True, exist_ok=True)
APPS_ROOT_PATH = APP_DATA_DIR / APPS_DIR_NAME
APPS_ROOT_PATH.mkdir(parents=True, exist_ok=True)
CUSTOM_APPS_ROOT_PATH = APP_DATA_DIR / CUSTOM_APPS_DIR_NAME
CUSTOM_APPS_ROOT_PATH.mkdir(parents=True, exist_ok=True)

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

# --- REFACTORED INSTALLATION TASK ---
def _install_item_task(task: Task, repository: str, folder_name: str, port: int, autostart: bool, source_root_path: Path):
    db_session = next(get_db())
    item_info = {}
    try:
        source_item_path = source_root_path / repository / folder_name
        if not source_item_path.exists():
            raise FileNotFoundError(f"Source directory not found at {source_item_path}")
        
        # Determine info file name based on source path
        info_file_name = "description.yaml" if source_root_path == MCP_ZOO_ROOT_PATH else "app_info.yaml"
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
        
        dest_app_path = APPS_ROOT_PATH / folder_name
        if dest_app_path.exists():
            task.log(f"Removing existing destination directory: {dest_app_path}")
            shutil.rmtree(dest_app_path, ignore_errors=True)

        task.log(f"Copying files from {source_item_path} to {dest_app_path}")
        task.set_progress(10)
        shutil.copytree(source_item_path, dest_app_path)
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

        client_id = _generate_unique_client_id(db_session, DBApp, item_name)
        new_app = DBApp(
            name=item_name, client_id=client_id, folder_name=folder_name,
            icon=icon_base64, is_installed=True, status='stopped',
            port=port, autostart=autostart,
            version=item_info.get('version'), author=item_info.get('author'),
            description=item_info.get('description'), category=item_info.get('category'),
            tags=item_info.get('tags'), app_metadata=item_info,
        )
        db_session.add(new_app)
        db_session.commit()
        
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


@apps_management_router.get("/zoo/repositories", response_model=list[AppZooRepositoryPublic])
def get_zoo_repositories(db: Session = Depends(get_db)):
    return db.query(DBAppZooRepository).all()

@apps_management_router.post("/zoo/repositories", response_model=AppZooRepositoryPublic, status_code=201)
def add_zoo_repository(repo: AppZooRepositoryCreate, db: Session = Depends(get_db)):
    if db.query(DBAppZooRepository).filter(DBAppZooRepository.name == repo.name).first():
        raise HTTPException(status_code=409, detail="A repository with this name already exists.")
    if db.query(DBAppZooRepository).filter(DBAppZooRepository.url == repo.url).first():
        raise HTTPException(status_code=409, detail="A repository with this URL already exists.")
    
    new_repo = DBAppZooRepository(**repo.model_dump())
    db.add(new_repo)
    db.commit()
    db.refresh(new_repo)
    return new_repo

@apps_management_router.delete("/zoo/repositories/{repo_id}", status_code=204)
def delete_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
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
    return None

def _pull_repo_task(task: Task, repo_id: int, repo_model, root_path: Path):
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
        task.log("Updated repository pull time.")
        task.set_progress(100)
        return {"message": "Repository pulled successfully."}

    except Exception as e:
        if repo:
            repo.last_pulled_at = None
            db_session.commit()
        raise e
    finally:
        db_session.close()


@apps_management_router.post("/zoo/repositories/{repo_id}/pull", response_model=TaskInfo, status_code=202)
def pull_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBAppZooRepository).filter(DBAppZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    db_task = task_manager.submit_task(
        name=f"Pulling App repository: {repo.name}",
        target=_pull_repo_task,
        args=(repo_id, DBAppZooRepository, ZOO_ROOT_PATH),
        description=f"Updating local copy of '{repo.name}' from '{repo.url}'."
    )
    return _to_task_info(db_task)


def _get_zoo_apps_metadata():
    apps_metadata = {}
    if not ZOO_ROOT_PATH.exists(): return {}
    for repo_dir in ZOO_ROOT_PATH.iterdir():
        if repo_dir.is_dir():
            for app_dir in repo_dir.iterdir():
                if app_dir.is_dir() and (app_dir / "app_info.yaml").exists():
                    try:
                        with open(app_dir / "app_info.yaml", "r", encoding='utf-8') as f:
                            info = yaml.safe_load(f)
                            apps_metadata[info['name']] = info
                    except Exception as e:
                        print(f"Warning: Could not parse app_info.yaml for {app_dir.name}. Error: {e}")
    return apps_metadata

@apps_management_router.get("/zoo/available-apps", response_model=list[ZooAppInfo])
def get_available_zoo_apps(db: Session = Depends(get_db)):
    if not ZOO_ROOT_PATH.exists(): return []
    installed_apps = {app.name for app in db.query(DBApp.name).filter(DBApp.is_installed == True).all()}
    apps_list = []
    for repo_dir in ZOO_ROOT_PATH.iterdir():
        if repo_dir.is_dir():
            for app_dir in repo_dir.iterdir():
                if app_dir.is_dir() and (app_dir / "app_info.yaml").exists():
                    try:
                        with open(app_dir / "app_info.yaml", "r", encoding='utf-8') as f: info = yaml.safe_load(f)
                        icon_path = app_dir / "assets" / "logo.png"
                        icon_base64 = f"data:image/png;base64,{base64.b64encode(icon_path.read_bytes()).decode()}" if icon_path.exists() else None
                        apps_list.append(ZooAppInfo(
                            name=info.get('name', app_dir.name), repository=repo_dir.name, folder_name=app_dir.name,
                            icon=icon_base64, is_installed=(info.get('name', app_dir.name) in installed_apps),
                            has_readme=(app_dir / "README.md").exists(), **info
                        ))
                    except Exception as e:
                        print(f"Warning: Could not process app at {app_dir}. Error: {e}")
    return apps_list

@apps_management_router.get("/zoo/app-readme", response_class=PlainTextResponse)
def get_app_readme(repository: str, folder_name: str):
    readme_path = ZOO_ROOT_PATH / repository / folder_name / "README.md"
    if not readme_path.exists():
        raise HTTPException(status_code=404, detail="README.md not found for this app.")
    return readme_path.read_text(encoding="utf-8")

@apps_management_router.post("/zoo/install-app", response_model=TaskInfo, status_code=202)
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
    return None

@apps_management_router.post("/mcp-zoo/repositories/{repo_id}/pull", response_model=TaskInfo, status_code=202)
def pull_mcp_zoo_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(DBMCPZooRepository).filter(DBMCPZooRepository.id == repo_id).first()
    if not repo: raise HTTPException(status_code=404, detail="Repository not found.")
    db_task = task_manager.submit_task(
        name=f"Pulling MCP repository: {repo.name}",
        target=_pull_repo_task,
        args=(repo_id, DBMCPZooRepository, MCP_ZOO_ROOT_PATH),
        description=f"Updating local copy of '{repo.name}' from '{repo.url}'."
    )
    return _to_task_info(db_task)

@apps_management_router.get("/mcp-zoo/available-mcps", response_model=list[ZooMCPInfo])
def get_available_zoo_mcps(db: Session = Depends(get_db)):
    if not MCP_ZOO_ROOT_PATH.exists(): return []
    installed_items = {app.name for app in db.query(DBApp.name).filter(DBApp.is_installed == True).all()}
    mcps_list = []
    for repo_dir in MCP_ZOO_ROOT_PATH.iterdir():
        if repo_dir.is_dir():
            for mcp_dir in repo_dir.iterdir():
                if mcp_dir.is_dir() and (mcp_dir / "description.yaml").exists():
                    try:
                        with open(mcp_dir / "description.yaml", "r", encoding='utf-8') as f: info = yaml.safe_load(f)
                        icon_path = mcp_dir / "icon.png"
                        icon_base64 = f"data:image/png;base64,{base64.b64encode(icon_path.read_bytes()).decode()}" if icon_path.exists() else None
                        mcps_list.append(ZooMCPInfo(
                            name=info.get('name', mcp_dir.name), repository=repo_dir.name, folder_name=mcp_dir.name,
                            icon=icon_base64, is_installed=(info.get('name', mcp_dir.name) in installed_items),
                            has_readme=(mcp_dir / "README.md").exists(), **info
                        ))
                    except Exception as e:
                        print(f"Warning: Could not process mcp at {mcp_dir}. Error: {e}")
    return mcps_list

@apps_management_router.get("/mcp-zoo/mcp-readme", response_class=PlainTextResponse)
def get_mcp_readme(repository: str, folder_name: str):
    readme_path = MCP_ZOO_ROOT_PATH / repository / folder_name / "README.md"
    if not readme_path.exists():
        raise HTTPException(status_code=404, detail="README.md not found for this mcp.")
    return readme_path.read_text(encoding="utf-8")

@apps_management_router.post("/mcp-zoo/install-mcp", response_model=TaskInfo, status_code=202)
def install_zoo_mcp(request: AppInstallRequest):
    db_task = task_manager.submit_task(
        name=f"Installing app: {request.folder_name}", # Keep 'app' for consistency in task names
        target=_install_item_task,
        args=(request.repository, request.folder_name, request.port, request.autostart, MCP_ZOO_ROOT_PATH),
        description=f"Installing MCP from repository '{request.repository}'."
    )
    return _to_task_info(db_task)


# --- Installed App Management (Shared by Apps and MCPs) ---
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
def start_app(app_id: str, db: Session = Depends(get_db)):
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app:
        raise HTTPException(status_code=404, detail="Installed app not found.")
    
    if app.status == 'running':
        raise HTTPException(status_code=400, detail="App is already running.")
    
    db_task = task_manager.submit_task(
        name=f"Start app: {app.name}",
        target=_start_app_task,
        args=(app_id,),
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
        args=(app_id,),
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
        if db.query(DBApp).filter(DBApp.port == update_data['port'], DBApp.id != app_id).first():
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