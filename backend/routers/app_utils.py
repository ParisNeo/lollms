# backend/routers/app_utils.py
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
from typing import Dict, Any, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import func
from ascii_colors import ASCIIColors
from filelock import FileLock, Timeout

from backend.db import get_db
from backend.db.models.service import App as DBApp, MCP as DBMCP, AppZooRepository, MCPZooRepository
from backend.db.models.db_task import DBTask
from backend.models import TaskInfo
from backend.config import APPS_ROOT_PATH, MCPS_ROOT_PATH, MCPS_ZOO_ROOT_PATH, APPS_ZOO_ROOT_PATH, APP_DATA_DIR
from backend.task_manager import task_manager, Task
from backend.zoo_cache import get_all_items
from backend.settings import settings
from backend.utils import get_accessible_host, find_next_available_port
from backend.session import user_sessions, reload_lollms_client_mcp

open_log_files: Dict[str, Any] = {}

# Constants for synchronization lock
SYNC_LOCK_PATH = APP_DATA_DIR / "sync_installations.lock"
SYNC_LOCK_TIMEOUT = 300 # 5 minutes timeout for the lock

# NEW HELPER FUNCTION for finding unique ports during dynamic operations
def _get_next_available_app_port_for_batch(db_session: Session, ports_in_current_batch: set) -> int:
    """
    Finds the next available port for an app, considering ports already in the DB
    and ports assigned within the current synchronization batch.
    """
    # Start checking from a common default port
    current_candidate_port = 9601
    
    # Get all ports currently used by apps in the database
    # This query runs within the ongoing session.
    db_used_ports = {p[0] for p in db_session.query(DBApp.port).filter(DBApp.port.isnot(None)).all()}

    while True:
        # Check against DB-used ports and ports assigned in the current batch
        if current_candidate_port in db_used_ports or current_candidate_port in ports_in_current_batch:
            current_candidate_port += 1
        else:
            # Check if the port is actually free on the system (this is the most reliable check)
            try:
                system_free_port = find_next_available_port(current_candidate_port)
                if system_free_port == current_candidate_port:
                    return current_candidate_port
                else:
                    # If find_next_available_port found a different *higher* free port, jump to it
                    current_candidate_port = system_free_port 
            except Exception as e:
                # If find_next_available_port fails (e.g., no ports available in range), log and increment
                ASCIIColors.warning(f"Could not verify system port {current_candidate_port}: {e}. Trying next port.")
                current_candidate_port += 1
                
def get_installed_app_path(db: Session, app_id: str) -> Path:
    app = db.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
    if not app or not app.folder_name:
        raise HTTPException(status_code=404, detail="Installed app not found or is corrupted.")
    
    if app.app_metadata and app.app_metadata.get('item_type') == 'mcp':
        return MCPS_ROOT_PATH / app.folder_name
    
    # Fallback check for robustness
    if (MCPS_ROOT_PATH / app.folder_name).exists():
        return MCPS_ROOT_PATH / app.folder_name
        
    return APPS_ROOT_PATH / app.folder_name

def generate_unique_client_id(db: Session, model_class, name: str) -> str:
    base_slug = re.sub(r'[^a-z0-9_]+', '', name.lower().replace(' ', '_'))
    client_id = base_slug
    counter = 1
    while db.query(model_class).filter(model_class.client_id == client_id).first():
        client_id = f"{base_slug}_{counter}"
        counter += 1
    return client_id

def to_task_info(db_task: DBTask) -> TaskInfo:
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

def get_all_zoo_metadata():
    all_items_dict = {}
    for item in get_all_items('app') + get_all_items('mcp'):
        all_items_dict[item['name']] = item
    return all_items_dict

def synchronize_filesystem_and_db(db: Session):
    """
    Synchronizes installed apps/MCPs on the filesystem with the database.
    - Creates DB entries for "ghost" installations found on disk.
    - Removes DB entries for "orphaned" records with no matching files.
    - Corrects `item_type` for existing records based on folder location.
    
    This function is protected by a FileLock to ensure singleton execution.
    """
    ASCIIColors.info("Attempting to acquire synchronization lock.")
    lock = FileLock(str(SYNC_LOCK_PATH), timeout=SYNC_LOCK_TIMEOUT)
    
    try:
        with lock:
            ASCIIColors.info("Synchronization lock acquired. Starting synchronization of installed items with the database.")
            fixed_ghosts = 0
            removed_orphans = 0
            corrected_types = 0
            
            # Keep track of ports assigned during this single synchronization run
            assigned_ports_in_batch = set() 

            # --- Step 1: Find ghost installations (filesystem folder exists, but no DB record) ---
            ASCIIColors.info("Scanning for ghost installations (files without DB entry)...")
            
            installed_folders = {
                'app': {f.name for f in APPS_ROOT_PATH.iterdir() if f.is_dir()},
                'mcp': {f.name for f in MCPS_ROOT_PATH.iterdir() if f.is_dir()}
            }
            
            db_folder_names = {r[0] for r in db.query(DBApp.folder_name).filter(DBApp.is_installed == True, DBApp.folder_name.isnot(None)).all()}
            
            ghost_folders = {
                'app': installed_folders['app'] - db_folder_names,
                'mcp': installed_folders['mcp'] - db_folder_names
            }

            for item_type, folders in ghost_folders.items():
                if not folders:
                    ASCIIColors.green(f"No ghost installations found for type: {item_type.upper()}")
                    continue
                
                ASCIIColors.yellow(f"Found {len(folders)} ghost installations for type: {item_type.upper()}. Attempting to repair...")
                root_path = APPS_ROOT_PATH if item_type == 'app' else MCPS_ROOT_PATH
                
                for folder_name in folders:
                    item_path = root_path / folder_name
                    desc_path = item_path / "description.yaml"
                    
                    if not desc_path.exists():
                        ASCIIColors.yellow(f"  - SKIPPING '{folder_name}': No description.yaml found. Cannot automatically repair.")
                        continue
                    
                    try:
                        with open(desc_path, 'r', encoding='utf-8') as f:
                            item_info = yaml.safe_load(f) or {}
                        
                        item_name = item_info.get("name", folder_name)
                        
                        if db.query(DBApp).filter(func.lower(DBApp.name) == func.lower(item_name), DBApp.is_installed == True).first():
                            ASCIIColors.yellow(f"  - SKIPPING '{folder_name}': A different installed item with the name '{item_name}' already exists in the database.")
                            continue

                        ASCIIColors.cyan(f"  - REPAIRING '{folder_name}': Creating database entry for '{item_name}'.")
                        
                        icon_path = next((p for p in [item_path / "assets" / "logo.png", item_path / "icon.png"] if p.exists()), None)
                        icon_base64 = f"data:image/png;base64,{base64.b64encode(icon_path.read_bytes()).decode()}" if icon_path else None
                        
                        item_info['item_type'] = item_type
                        item_info['folder_name'] = folder_name
                        
                        client_id = generate_unique_client_id(db, DBApp, item_name)
                        
                        # Use the new helper to find a truly unique port within this batch
                        next_port = _get_next_available_app_port_for_batch(db, assigned_ports_in_batch)
                        assigned_ports_in_batch.add(next_port) # Add to the set for this batch

                        new_app_record = DBApp(
                            name=item_name, client_id=client_id, folder_name=folder_name,
                            icon=icon_base64, is_installed=True, status='stopped', port=next_port,
                            autostart=False, version=str(item_info.get('version', 'N/A')),
                            author=item_info.get('author'), description=item_info.get('description'),
                            category=item_info.get('category'), tags=item_info.get('tags'),
                            app_metadata=item_info
                        )
                        db.add(new_app_record)
                        fixed_ghosts += 1
                    except Exception as e:
                        ASCIIColors.error(f"  - FAILED to repair '{folder_name}': {e}")
                        traceback.print_exc()

            # --- Step 2: Find orphaned DB records (DB record exists, but folder is missing) ---
            ASCIIColors.info("Scanning for orphaned database records (DB entry without files)...")
            
            db_installed_items = db.query(DBApp).filter(DBApp.is_installed == True).all()
            orphaned_items = []
            for item in db_installed_items:
                if not item.folder_name:
                    orphaned_items.append(item)
                    continue
                if isinstance(item.app_metadata , str):
                    try:
                        item.app_metadata = json.loads(item.app_metadata)
                    except:
                        item.app_metadata = {}
                item_type = (item.app_metadata or {}).get('item_type', 'app')
                root_path = APPS_ROOT_PATH if item_type == 'app' else MCPS_ROOT_PATH
                if not (root_path / item.folder_name).exists():
                    orphaned_items.append(item)

            if not orphaned_items:
                ASCIIColors.green("No orphaned database records found.")
            else:
                ASCIIColors.yellow(f"Found {len(orphaned_items)} orphaned records. Removing from database...")
                for item in orphaned_items:
                    ASCIIColors.cyan(f"  - REMOVING orphan record: '{item.name}' (folder: {item.folder_name or 'N/A'})")
                    db.delete(item)
                    removed_orphans += 1

            # --- Step 3: Verify and correct item_type for existing records ---
            ASCIIColors.info("Verifying item types for existing database records...")
            all_installed = db.query(DBApp).filter(DBApp.is_installed == True, DBApp.folder_name.isnot(None)).all()
            
            for item in all_installed:
                expected_type = None
                if (APPS_ROOT_PATH / item.folder_name).exists():
                    expected_type = 'app'
                elif (MCPS_ROOT_PATH / item.folder_name).exists():
                    expected_type = 'mcp'
                
                if expected_type:
                    current_metadata = item.app_metadata or {}
                    current_type = current_metadata.get('item_type')
                    if current_type != expected_type:
                        ASCIIColors.yellow(f"  - CORRECTING type for '{item.name}': was '{current_type}', set to '{expected_type}'.")
                        current_metadata['item_type'] = expected_type
                        item.app_metadata = current_metadata
                        flag_modified(item, "app_metadata")
                        corrected_types += 1
            
            if corrected_types > 0:
                ASCIIColors.green(f"Corrected {corrected_types} item types.")
            else:
                ASCIIColors.green("All existing item types are correct.")

            db.commit()
            ASCIIColors.info("Synchronization complete. Releasing lock.")
            
            return {
                "fixed_ghost_installations": fixed_ghosts,
                "removed_orphaned_records": removed_orphans,
                "corrected_item_types": corrected_types
            }
    except Timeout:
        ASCIIColors.warning(f"Could not acquire synchronization lock within {SYNC_LOCK_TIMEOUT} seconds. Another process is likely performing the sync. Skipping.")
        return {
            "message": "Synchronization skipped: Another process is already running it.",
            "fixed_ghost_installations": 0,
            "removed_orphaned_records": 0,
            "corrected_item_types": 0
        }
    except Exception as e:
        ASCIIColors.error(f"Error during synchronization (lock held): {e}")
        traceback.print_exc()
        db.rollback() # Ensure rollback on error
        raise # Re-raise to ensure task status is set to failed


def sync_installs_task(task: Task):
    task.log("Starting synchronization of installed items with the database.")
    task.set_progress(5)
    
    with task.db_session_factory() as db:
        results = synchronize_filesystem_and_db(db)
        
    task.set_progress(100)
    task.log("Synchronization complete.")
    
    return {
        "message": "Sync complete.",
        **results
    }


def _purge_broken_task(task: Task, item_type: str, folder_name: str):
    task.log(f"Starting purge of broken installation: {folder_name} ({item_type})")
    root_path = APPS_ROOT_PATH if item_type == 'app' else MCPS_ROOT_PATH
    folder_path = root_path / folder_name

    if not folder_path.exists():
        task.log(f"Folder '{folder_path}' does not exist. Nothing to purge.", "WARNING")
        task.set_progress(100)
        return {"message": "Folder already gone."}

    try:
        shutil.rmtree(folder_path)
        task.log(f"Successfully deleted folder: {folder_path}", "INFO")
    except Exception as e:
        task.log(f"Failed to delete folder '{folder_path}': {e}", "ERROR")
        raise e
    
    with task.db_session_factory() as db:
        try:
            # IMPORTANT: Delete by folder_name, not just app_id, as a broken app might not have a valid DBApp record ID.
            # Also ensure it's an installed app.
            orphaned_record = db.query(DBApp).filter(DBApp.folder_name == folder_name, DBApp.is_installed == True).first()
            if orphaned_record:
                db.delete(orphaned_record)
                db.commit()
                task.log(f"Also removed an orphaned database record for '{folder_name}'.", "INFO")
            else:
                task.log(f"No corresponding installed DB record found for '{folder_name}'. Folder purged.", "INFO")

        except Exception as e:
            task.log(f"Could not check/remove orphaned DB record for '{folder_name}': {e}", "WARNING")
            db.rollback()

    task.set_progress(100)
    return {"message": f"Purge of '{folder_name}' complete."}

def _fix_broken_task(task: Task, item_type: str, folder_name: str):
    task.log(f"Attempting to fix broken installation: {folder_name} ({item_type})")
    root_path = APPS_ROOT_PATH if item_type == 'app' else MCPS_ROOT_PATH
    item_path = root_path / folder_name
    
    desc_path = item_path / "description.yaml"
    if not desc_path.exists():
        raise FileNotFoundError(f"Cannot fix '{folder_name}': description.yaml is missing.")

    with task.db_session_factory() as db:
        try:
            with open(desc_path, 'r', encoding='utf-8') as f:
                item_info = yaml.safe_load(f) or {}
            
            item_name = item_info.get("name", folder_name)
            
            # Check for existing installed item with this name (case-insensitive)
            existing_db_app = db.query(DBApp).filter(func.lower(DBApp.name) == func.lower(item_name), DBApp.is_installed == True).first()
            if existing_db_app:
                # If a record exists, update it rather than creating a new one
                # This scenario might happen if the folder was purged but the DB record was not.
                task.log(f"  - Found existing DB record for '{item_name}'. Updating it instead of creating new.", "INFO")
                new_app_record = existing_db_app
            else:
                new_app_record = DBApp()
                db.add(new_app_record)

            task.log(f"Read metadata for '{item_name}'. Updating/Creating database entry.")
            
            icon_path = next((p for p in [item_path / "assets" / "logo.png", item_path / "icon.png"] if p.exists()), None)
            icon_base64 = f"data:image/png;base64,{base64.b64encode(icon_path.read_bytes()).decode()}" if icon_path else None
            
            item_info['item_type'] = item_type
            item_info['folder_name'] = folder_name
            
            # Only assign a new port if it doesn't have one or it's null, and ensure it's unique
            if new_app_record.port is None or new_app_record.port not in _get_next_available_app_port_for_batch(db, set()): # Using the batch function with empty set to just check overall uniqueness
                next_port = find_next_available_port(9601) # Use the simpler utility for single installs
                new_app_record.port = next_port
                task.log(f"  - Assigned new port {next_port} to '{item_name}'.", "INFO")
            
            # Generate client_id if missing
            if not new_app_record.client_id:
                new_app_record.client_id = generate_unique_client_id(db, DBApp, item_name)
                task.log(f"  - Assigned new client_id '{new_app_record.client_id}' to '{item_name}'.", "INFO")


            new_app_record.name = item_name
            new_app_record.folder_name = folder_name
            new_app_record.icon = icon_base64
            new_app_record.is_installed = True
            new_app_record.status = 'stopped' # Always stopped after fix/install
            new_app_record.autostart = False # Default to False, user can enable later
            new_app_record.version = str(item_info.get('version', 'N/A'))
            new_app_record.author = item_info.get('author')
            new_app_record.description = item_info.get('description')
            new_app_record.category = item_info.get('category')
            new_app_record.tags = item_info.get('tags')
            new_app_record.app_metadata = item_info

            db.commit()
            task.set_progress(100)
            task.log(f"Successfully fixed installation for '{item_name}'.")
            return {"message": "Fix successful."}
        except Exception as e:
            db.rollback()
            task.log(f"Failed to fix '{folder_name}': {e}", "ERROR")
            raise e


def cleanup_and_autostart_apps():
    lock_path = APP_DATA_DIR / "startup.lock"
    lock = FileLock(str(lock_path), timeout=10)

    db_session = None
    try:
        with lock:
            print("INFO: Acquired startup lock. Performing app cleanup and autostart...")
            db_session = next(get_db())
            
            # This logic will now run only once per server startup, by the first worker that gets the lock.
            
            # 1. Cleanup: Reset status of all installed apps to 'stopped'
            # Also clear any lingering PIDs and force stop if process exists.
            installed_apps = db_session.query(DBApp).filter(DBApp.is_installed == True).all()
            updated_count = 0
            
            # Before cleaning, check for duplicate ports in the DB that might have survived previous migrations
            # and fix them proactively. This handles cases where a unique constraint might have been added later.
            ports_in_db = {} # port -> [app_id1, app_id2]
            for app in installed_apps:
                if app.port is not None:
                    ports_in_db.setdefault(app.port, []).append(app.id)

            ports_to_reassign_app_ids = set() # Use a better name for clarity
            for port, app_ids in ports_in_db.items():
                if len(app_ids) > 1:
                    print(f"WARNING: Detected port conflict for port {port} on startup (apps: {[db_session.query(DBApp).filter_by(id=aid).first().name for aid in app_ids if db_session.query(DBApp).filter_by(id=aid).first()]}). Reassigning additional apps.")
                    # Keep the first app by its original port, reassign others.
                    # Or for simplicity during cleanup, reassign all except the first one found by query order.
                    for i in range(1, len(app_ids)): # Iterate from the second app onwards
                        ports_to_reassign_app_ids.add(app_ids[i])
            
            # Track ports assigned during this cleanup batch to prevent new internal conflicts
            reassigned_ports_current_batch = set()

            # Iterate again to apply changes
            for app in installed_apps:
                original_status = app.status
                original_pid = app.pid

                if app.pid:
                    try:
                        p = psutil.Process(app.pid)
                        # Check if process is still running and is the expected process
                        # This avoids killing a new process that might have reused the PID
                        if p.status() != psutil.STATUS_ZOMBIE and p.pid == original_pid:
                            p.terminate() # or p.kill() if terminate is not enough
                            p.wait(timeout=5)
                            print(f"INFO: Terminated lingering process with PID {app.pid} for app '{app.name}'.")
                    except psutil.NoSuchProcess:
                        pass # Process already gone
                    except Exception as e:
                        print(f"WARNING: Could not kill lingering process {app.pid} for app '{app.name}': {e}")
                
                app.status = 'stopped'
                app.pid = None
                
                # Reassign port if it was part of a conflict, or if it's currently None (should have one)
                # or if its current port is already taken by another app in this same transaction.
                if app.id in ports_to_reassign_app_ids or app.port is None:
                    # Find a new unique port for this app.
                    new_port = _get_next_available_app_port_for_batch(db_session, reassigned_ports_current_batch)
                    if app.port != new_port: # Only update if different to avoid unnecessary commits
                        print(f"INFO: Reassigned port for '{app.name}' from {app.port} to {new_port}.")
                        app.port = new_port
                    reassigned_ports_current_batch.add(new_port)
                elif app.port is not None and app.port in reassigned_ports_current_batch:
                    # This case means this app's existing port was assigned to a previous app in this batch.
                    # This app also needs a new port.
                    new_port = _get_next_available_app_port_for_batch(db_session, reassigned_ports_current_batch)
                    print(f"INFO: Reassigned port for '{app.name}' from {app.port} to {new_port} due to batch conflict.")
                    app.port = new_port
                    reassigned_ports_current_batch.add(new_port)
                elif app.port is not None:
                    # If the app's port is valid and not conflicting in this batch, reserve it.
                    reassigned_ports_current_batch.add(app.port)
                    
                
                # Check if an update occurred
                if original_status != 'stopped' or original_pid is not None or app.id in ports_to_reassign_app_ids:
                    updated_count += 1
            
            if updated_count > 0:
                db_session.commit()
                print(f"INFO: Cleaned up status and fixed {updated_count} app records.")

            # 2. Autostart
            apps_to_autostart = db_session.query(DBApp).filter(DBApp.is_installed == True, DBApp.autostart == True).all()

            if apps_to_autostart:
                print(f"INFO: Found {len(apps_to_autostart)} apps to autostart.")
                for app in apps_to_autostart:
                    task_manager.submit_task(
                        name=f"Start app: {app.name} ({app.id})",
                        target=start_app_task,
                        args=(app.id,),
                        description=f"Automatically starting '{app.name}' on server boot.",
                        owner_username=None
                    )
            print("INFO: App cleanup and autostart complete. Releasing lock.")

    except Timeout:
        print("INFO: Could not acquire startup lock. Another worker is performing startup. Skipping.")
        return
    except Exception as e:
        print(f"CRITICAL: Failed during app startup management. Error: {e}")
        traceback.print_exc()
        if db_session: db_session.rollback()
    finally:
        if db_session: db_session.close()

def start_app_task(task: Task, app_id: str):
    db_session = next(get_db())
    app = None
    process = None
    log_file_handle = None
    try:
        app_path = get_installed_app_path(db_session, app_id)
        app = db_session.query(DBApp).filter(DBApp.id == app_id).first()
        if not app: raise ValueError("Installed app metadata not found.")

        # Ensure the app has a port before trying to start
        if app.port is None:
            new_port = _get_next_available_app_port_for_batch(db_session, set())
            app.port = new_port
            db_session.commit() # Commit this change so it's persisted immediately
            task.log(f"App '{app.name}' had no port, assigned new port {new_port}.", "INFO")


        log_file_path = app_path / "app.log"
        log_file_handle = open(log_file_path, "w", encoding="utf-8", buffering=1)

        venv_path = app_path / "venv"
        python_executable = venv_path / ("Scripts" if sys.platform == "win32" else "bin") / "python"
        
        main_server_host = settings.get("host", "0.0.0.0")
        host_to_bind = "0.0.0.0" if main_server_host in ["0.0.0.0", "::"] else "127.0.0.1"

        command_template = (app.app_metadata or {}).get('run_command')
        if command_template:
            command = [str(arg).replace("{python_executable}", str(python_executable)).replace("{port}", str(app.port)).replace("{host}", host_to_bind) for arg in command_template]
        else:
            item_type = (app.app_metadata or {}).get('item_type', 'app')
            if item_type == 'mcp':
                command = [str(python_executable), "server.py", "--host", host_to_bind, "--port", str(app.port)]
            else:
                command = [str(python_executable), "-m", "uvicorn", "server:app", "--host", host_to_bind, "--port", str(app.port)]

        task.log(f"Executing start command: {' '.join(command)}")
        process = subprocess.Popen(command, cwd=str(app_path), stdout=log_file_handle, stderr=subprocess.STDOUT)
        
        open_log_files[app.id] = log_file_handle
        task.process = process
        time.sleep(5) 
        
        if process.poll() is not None:
            raise Exception(f"Application failed to start. Process exited with code {process.poll()}. Check task logs and app.log.")

        app_host = get_accessible_host()
        app.pid = process.pid
        app.status = 'running'
        
        item_type = (app.app_metadata or {}).get('item_type', 'app')
        app_url = f"http://{app_host}:{app.port}"
        if item_type == 'mcp' and not app_url.endswith('/mcp'):
            app_url += "/mcp"
        app.url = app_url
        
        app.active = True
        db_session.commit()
        
        if item_type == 'mcp':
            task.log(f"MCP '{app.name}' has started. Reloading MCPs for all active users.")
            active_users = list(user_sessions.keys())
            total_users = len(active_users)
            reloaded_count = 0
            for i, username in enumerate(active_users):
                try:
                    reload_lollms_client_mcp(username)
                    task.log(f"Reloaded MCPs for user: {username}")
                    reloaded_count += 1
                except Exception as e:
                    task.log(f"Failed to reload MCPs for user {username}: {e}", level="ERROR")
                    traceback.print_exc()
                
                if total_users > 0:
                    task.set_progress(90 + int(10 * (i + 1) / total_users))

            task.log(f"MCP reload triggered for {reloaded_count} of {total_users} active sessions.")

        task.log(f"App '{app.name}' started with PID {process.pid} on port {app.port}.")
        task.set_progress(100)
        return {"success": True, "message": f"App '{app.name}' started successfully.", "item_type": item_type}
    except Exception as e:
        task.log(f"Failed to start app: {e}", level="CRITICAL")
        if app:
            app.status = 'error'
            db_session.commit()
        if process and process.poll() is None:
            process.terminate()
        raise e
    finally:
        if log_file_handle: log_file_handle.close()
        if app and app.id in open_log_files: del open_log_files[app.id]
        db_session.close()


def stop_app_task(task: Task, app_id: str):
    db_session = next(get_db())
    app = None
    try:
        app = db_session.query(DBApp).filter(DBApp.id == app_id, DBApp.is_installed == True).first()
        if not app: raise ValueError("Installed app not found.")
        if not app.pid:
            app.status = 'stopped'
            db_session.commit()
            return {"success": True, "message": "App was already stopped."}

        try:
            process = psutil.Process(app.pid)
            process.terminate()
            process.wait(timeout=5)
        except psutil.TimeoutExpired:
            process.kill()
        except psutil.NoSuchProcess:
            pass
        
        app.pid = None
        app.status = 'stopped'
        db_session.commit()
        
        if app.id in open_log_files:
            open_log_files[app.id].close()
            del open_log_files[app.id]

        task.set_progress(100)
        return {"success": True, "message": f"App '{app.name}' stopped successfully."}
    except Exception as e:
        if app:
            app.status = 'error'
            db_session.commit()
        raise e
    finally:
        db_session.close()

def pull_repo_task(task: Task, repo_id: int, repo_model, root_path: Path, item_type: str):
    db_session = next(get_db())
    repo = db_session.query(repo_model).filter(repo_model.id == repo_id).first()
    if not repo: raise ValueError("Repository not found.")

    try:
        if repo.type == 'local':
            task.log(f"'{repo.name}' is a local folder. Rescanning for items...", "INFO")
            repo.last_pulled_at = datetime.datetime.now(datetime.timezone.utc)
            db_session.commit()
            from backend.zoo_cache import refresh_repo_cache
            refresh_repo_cache(repo.name, item_type)
            task.set_progress(100)
            return {"message": "Local folder rescanned successfully."}
        
        repo_path = root_path / repo.name
        command = ["git", "clone", repo.url, str(repo_path)] if not repo_path.exists() else ["git", "pull"]
        cwd = str(root_path) if not repo_path.exists() else str(repo_path)
        
        process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        task.process = process
        
        for line in iter(process.stdout.readline, ''):
            if task.cancellation_event.is_set():
                process.terminate()
                break
            task.log(line.strip(), "GIT_STDOUT")
        process.wait()
        if process.returncode != 0:
            raise Exception(f"Git operation failed. Stderr: {process.stderr.read().strip()}")
        
        repo.last_pulled_at = datetime.datetime.now(datetime.timezone.utc)
        db_session.commit()
        
        from backend.zoo_cache import refresh_repo_cache
        refresh_repo_cache(repo.name, item_type)
        task.set_progress(100)
        return {"message": "Repository pulled successfully."}
    except Exception as e:
        repo.last_pulled_at = None
        db_session.commit()
        raise e
    finally:
        db_session.close()

def install_item_task(task: Task, repository: str, folder_name: str, port: int, autostart: bool, source_root_path: Path):
    with task.db_session_factory() as db_session:
        try:
            repo_model = None
            if source_root_path == APPS_ZOO_ROOT_PATH:
                repo_model = AppZooRepository
            elif source_root_path == MCPS_ZOO_ROOT_PATH:
                repo_model = MCPZooRepository

            source_item_path = None
            if repo_model:
                repo = db_session.query(repo_model).filter_by(name=repository).first()
                if repo and repo.type == 'local':
                    source_item_path = Path(repo.url) / folder_name
                else:
                    source_item_path = source_root_path / repository / folder_name
            else:
                source_item_path = source_root_path / repository / folder_name

            if not source_item_path.exists():
                raise FileNotFoundError(f"Source directory not found at {source_item_path}")
            
            info_file = next((p for p in [source_item_path / "description.yaml"] if p.exists()), None)
            if not info_file: raise FileNotFoundError("Metadata file (description.yaml) not found.")
            with open(info_file, "r", encoding='utf-8') as f:
                item_info = yaml.safe_load(f)
            
            item_name = item_info.get("name", folder_name)
            is_mcp = source_root_path == MCPS_ZOO_ROOT_PATH
            dest_app_path = (MCPS_ROOT_PATH if is_mcp else APPS_ROOT_PATH) / folder_name
            
            shutil.copytree(source_item_path, dest_app_path, dirs_exist_ok=True)
            task.set_progress(20)

            server_py_path = dest_app_path / "server.py"
            if not server_py_path.exists() and 'run_command' not in item_info:
                static_dir = next((d for d in ["dist", "static", "."] if (dest_app_path / d / "index.html").exists()), None)
                if static_dir:
                    server_py_path.write_text(f"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
app = FastAPI()
app.mount("/", StaticFiles(directory=str(Path(__file__).parent / '{static_dir}'), html=True), name="static")
                    """.strip())
            
            venv_path = dest_app_path / "venv"
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True, capture_output=True)
            task.set_progress(40)

            pip_executable = venv_path / ("Scripts" if sys.platform == "win32" else "bin") / "pip"
            requirements_path = dest_app_path / "requirements.txt"
            if requirements_path.exists():
                subprocess.run([str(pip_executable), "install", "-r", str(requirements_path)], check=True, capture_output=True)

            if 'run_command' not in item_info:
                subprocess.run([str(pip_executable), "install", "fastapi", "uvicorn[standard]"], check=True, capture_output=True)
            task.set_progress(80)

            icon_path = next((p for p in [dest_app_path / "assets" / "logo.png", dest_app_path / "icon.png"] if p.exists()), None)
            icon_base64 = f"data:image/png;base64,{base64.b64encode(icon_path.read_bytes()).decode()}" if icon_path else None
            
            item_info['item_type'] = 'mcp' if is_mcp else 'app'
            item_info['repository'] = repository
            item_info['folder_name'] = folder_name
            client_id = generate_unique_client_id(db_session, DBApp, item_name)
            new_app = DBApp(name=item_name, client_id=client_id, folder_name=folder_name, icon=icon_base64, is_installed=True, status='stopped', port=port, autostart=autostart, version=str(item_info.get('version', 'N/A')), author=item_info.get('author'), description=item_info.get('description'), category=item_info.get('category'), tags=item_info.get('tags'), app_metadata=item_info)
            db_session.add(new_app)
            db_session.commit()
            db_session.refresh(new_app)
            
            if autostart: start_app_task(task, new_app.id)
            return {"success": True, "message": "Installation successful."}
        except Exception as e:
            if isinstance(e, subprocess.CalledProcessError): task.log(f"STDERR: {e.stderr}", "ERROR")
            raise e

def update_item_task(task: Task, app_id: str):
    db = next(get_db())
    app = db.query(DBApp).filter(DBApp.id == app_id).first()
    if not app:
        raise ValueError("App to update not found in database.")

    try:
        task.log("Starting update process...")
        if app.status == 'running':
            task.log("App is running, attempting to stop it first...")
            stop_app_task(task, app.id)

            for _ in range(30):
                db.refresh(app)
                if app.status == 'stopped':
                    task.log("App confirmed stopped.")
                    break
                time.sleep(1)
            else:
                raise Exception("Failed to stop running app before update (timeout).")
        
        task.set_progress(10)
        
        installed_path = get_installed_app_path(db, app.id)
        config_path = installed_path / 'config.yaml'
        log_path = installed_path / 'app.log'
        
        config_data = config_path.read_text() if config_path.exists() else None
        log_data = log_path.read_text() if log_path.exists() else None
        
        task.log("Backing up configuration and logs...")
        
        zoo_meta = (app.app_metadata or {})
        repo_name = zoo_meta.get('repository')
        folder_name = zoo_meta.get('folder_name')
        item_type = zoo_meta.get('item_type', 'app')
        source_root_path = APPS_ZOO_ROOT_PATH if item_type == 'app' else MCPS_ZOO_ROOT_PATH
        
        if not repo_name or not folder_name:
            raise ValueError("App metadata is missing repository/folder information needed for update.")

        source_path = source_root_path / repo_name / folder_name
        if not source_path.is_dir():
            raise FileNotFoundError(f"Source directory not found in zoo: {source_path}")

        task.log(f"Updating files from {source_path} to {installed_path}")
        task.set_progress(25)
        
        shutil.rmtree(installed_path)
        shutil.copytree(source_path, installed_path)

        if config_data:
            config_path.write_text(config_data)
            task.log("Restored user configuration.")
        if log_data:
            log_path.write_text(log_data)
            task.log("Restored previous logs.")

        task.set_progress(50)
        task.log("Re-installing dependencies...")
        
        venv_path = installed_path / "venv"
        pip_executable = venv_path / ("Scripts" if sys.platform == "win32" else "bin") / "pip"
        requirements_path = installed_path / "requirements.txt"
        
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True, capture_output=True)
        if requirements_path.exists():
            subprocess.run([str(pip_executable), "install", "-r", str(requirements_path)], check=True, capture_output=True)

        task.set_progress(80)
        task.log("Updating database record...")
        
        info_file = installed_path / "description.yaml"
        new_info = {}
        if info_file.exists():
            with open(info_file, "r", encoding='utf-8') as f:
                new_info = yaml.safe_load(f)

        app.version = str(new_info.get('version', app.version))
        app.app_metadata = {**zoo_meta, **new_info}
        db.commit()

        if app.autostart:
            task.log("Autostart is enabled, restarting app...")
            start_app_task(task, app.id)
        
        task.set_progress(100)
        task.log("Update completed successfully.")
        return {"success": True, "message": "Update successful."}

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise e
    finally:
        db.close()