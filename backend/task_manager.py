# backend/task_manager.py
import uuid
import datetime
import threading
import traceback
from typing import List, Dict, Any, Callable, Optional
from sqlalchemy.orm import Session, joinedload
from backend.db.models.db_task import DBTask
from backend.db.base import TaskStatus
from backend.ws_manager import manager
from backend.models.task import TaskInfo
from backend.db.models.user import User as DBUser

def _serialize_task(db_task: DBTask) -> Optional[dict]:
    """
    Serializes a SQLAlchemy DBTask object into a dictionary suitable for JSON transport.
    Ensures that the owner relationship is loaded.
    """
    if not db_task:
        return None
    
    task_info = {
        "id": db_task.id,
        "name": db_task.name,
        "description": db_task.description,
        "status": db_task.status,
        "progress": db_task.progress,
        "logs": db_task.logs or [],
        "result": db_task.result,
        "error": db_task.error,
        "created_at": db_task.created_at,
        "started_at": db_task.started_at,
        "completed_at": db_task.completed_at,
        "file_name": db_task.file_name,
        "total_files": db_task.total_files,
        "owner_username": db_task.owner.username if db_task.owner else "System"
    }
    for key in ['created_at', 'started_at', 'completed_at']:
        if task_info[key] and isinstance(task_info[key], datetime.datetime):
            task_info[key] = task_info[key].isoformat()

    return task_info


class Task:
    """
    Represents a runnable task that updates its state in the database.
    This object is managed by the TaskManager and executed in a separate thread.
    """
    def __init__(self, id: str, name: str, description: Optional[str], target: Callable, args: tuple, kwargs: dict, owner_username: Optional[str], db_session_factory: Callable[[], Session]):
        self.id = id
        self.name = name
        self.description = description
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.owner_username = owner_username
        self.db_session_factory = db_session_factory
        self.cancellation_event = threading.Event()
        self.process = None

    def _broadcast_update(self, db_task: DBTask):
        """Sends a WebSocket update for the task."""
        if not db_task:
            return
            
        task_data = _serialize_task(db_task)
        payload = {"type": "task_update", "data": task_data}
        
        # Always send to the specific user if they are the owner
        if db_task.owner_user_id:
            manager.send_personal_message_sync(payload, db_task.owner_user_id)
        
        # Only broadcast to all admins if there's an owner OR if any admins are actually connected.
        # This prevents spamming logs on startup for system tasks.
        if db_task.owner_user_id or len(manager.admin_user_ids) > 0:
            manager.broadcast_to_admins_sync(payload)

        # --- NEW: Send specific event for data zone tasks on completion ---
        if db_task.status == TaskStatus.COMPLETED and db_task.result:
            if isinstance(db_task.result, dict):
                # Handle Data Zone updates
                zone_info = db_task.result
                if "zone" in zone_info and "discussion_id" in zone_info:
                    if zone_info.get("zone") in ["discussion", "memory"]:
                        custom_payload = {
                            "type": "data_zone_processed",
                            "data": {
                                "discussion_id": zone_info.get("discussion_id"),
                                "zone": zone_info.get("zone"),
                                "new_content": zone_info.get("new_content")
                            }
                        }
                        if db_task.owner_user_id:
                            manager.send_personal_message_sync(custom_payload, db_task.owner_user_id)
                        manager.broadcast_to_admins_sync(custom_payload)
                
                # NEW: Handle App Status updates
                app_data = zone_info.get("updated_app")
                if "updated_app" in zone_info and (app_data):
                    app_payload = {"type": "app_status_changed", "data": app_data}
                    # Broadcast to everyone as multiple users (admins, owner) might need the update
                    manager.broadcast_sync(app_payload)


    def _update_db(self, **kwargs):
        """Safely updates the task's record in the database."""
        with self.db_session_factory() as db:
            task_record = db.query(DBTask).options(joinedload(DBTask.owner)).filter(DBTask.id == self.id).first()
            if not task_record:
                return
            
            for key, value in kwargs.items():
                setattr(task_record, key, value)
            
            db.commit()
            db.refresh(task_record, ['owner'])
            self._broadcast_update(task_record)

    def log(self, message: str, level: str = "INFO"):
        """Adds a log entry to the task's record."""
        log_entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "message": message,
            "level": level
        }
        with self.db_session_factory() as db:
            task_record = db.query(DBTask).options(joinedload(DBTask.owner)).filter(DBTask.id == self.id).first()
            if task_record:
                task_record.logs = (task_record.logs or []) + [log_entry]
                db.commit()
                db.refresh(task_record, ['owner'])
                self._broadcast_update(task_record)


    def set_progress(self, value: int):
        """Sets the task's progress percentage."""
        self._update_db(progress=max(0, min(100, value)))

    def set_description(self, description: str):
        """Updates the task's description."""
        self._update_db(description=description)
    
    def set_file_info(self, file_name: str, total_files: int):
        """Sets file-related information for the task."""
        self._update_db(file_name=file_name, total_files=total_files)

    def cancel(self):
        """Signals the task to cancel."""
        self.cancellation_event.set()
        if self.process and self.process.poll() is None:
            self.log("Terminating associated subprocess...", "WARNING")
            try:
                self.process.terminate()
            except ProcessLookupError:
                self.log("Process already terminated or does not exist.", "INFO")
        self.log("Cancellation signal received.", level="WARNING")

    def run(self):
        """The main execution method for the task thread."""
        self._update_db(status=TaskStatus.RUNNING, started_at=datetime.datetime.now(datetime.timezone.utc))
        self.log(f"Task '{self.name}' started.")
        try:
            result = self.target(self, *self.args, **self.kwargs)
            
            if self.cancellation_event.is_set():
                self._update_db(status=TaskStatus.CANCELLED)
                self.log(f"Task '{self.name}' was cancelled.", level="WARNING")
            else:
                self._update_db(status=TaskStatus.COMPLETED, progress=100, result=result)
                self.log(f"Task '{self.name}' completed successfully.")

        except Exception as e:
            tb_str = traceback.format_exc()
            self._update_db(status=TaskStatus.FAILED, error=str(e))
            self.log(f"Task '{self.name}' failed: {e}\n{tb_str}", level="CRITICAL")
        finally:
            self._update_db(completed_at=datetime.datetime.now(datetime.timezone.utc))

class TaskManager:
    """
    Manages the lifecycle of background tasks in a persistent, thread-safe manner.
    """
    def __init__(self, db_session_factory: Optional[Callable[[], Session]] = None):
        self.db_session_factory = db_session_factory
        self.active_tasks: Dict[str, Task] = {}
        self.lock = threading.Lock()

    def init_app(self, db_session_factory: Callable[[], Session]):
        """Initializes the TaskManager with a database session factory."""
        self.db_session_factory = db_session_factory

    def _run_and_cleanup(self, task: Task):
        """Wrapper to run a task and ensure it's removed from the active list upon completion."""
        try:
            task.run()
        finally:
            with self.lock:
                if task.id in self.active_tasks:
                    del self.active_tasks[task.id]

    def submit_task(self, name: str, target: Callable, args: tuple = (), kwargs: dict = None, description: Optional[str] = None, owner_username: Optional[str] = None) -> DBTask:
        """
        Creates a task record in the DB, and starts its execution in a new thread.
        """
        if not self.db_session_factory:
            raise RuntimeError("TaskManager not initialized. Call init_app first.")
            
        with self.db_session_factory() as db:
            owner_id = None
            if owner_username:
                user = db.query(DBUser).filter_by(username=owner_username).first()
                if user:
                    owner_id = user.id

            new_db_task = DBTask(
                name=name,
                description=description or name,
                owner_user_id=owner_id
            )
            db.add(new_db_task)
            db.commit()
            db.refresh(new_db_task, ['owner'])
            
            task_data = _serialize_task(new_db_task)
            payload = {"type": "task_update", "data": task_data}
            
            if new_db_task.owner_user_id:
                manager.send_personal_message_sync(payload, new_db_task.owner_user_id)
            
            if new_db_task.owner_user_id or len(manager.admin_user_ids) > 0:
                manager.broadcast_to_admins_sync(payload)

            db.expunge(new_db_task)


        task_instance = Task(id=new_db_task.id, name=name, description=description, target=target, args=args, kwargs=kwargs, owner_username=owner_username, db_session_factory=self.db_session_factory)
        
        with self.lock:
            self.active_tasks[task_instance.id] = task_instance

        thread = threading.Thread(target=self._run_and_cleanup, args=(task_instance,), daemon=True)
        thread.start()
        
        return new_db_task

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancels a task. If the task is actively running, it signals the thread.
        If the task is a "zombie" (in DB but not running), it updates the DB directly.
        """
        with self.lock:
            task_instance = self.active_tasks.get(task_id)
        
        if task_instance and not task_instance.cancellation_event.is_set():
            task_instance.cancel()
            return True

        with self.db_session_factory() as db:
            db_task = db.query(DBTask).options(joinedload(DBTask.owner)).filter(DBTask.id == task_id).first()
            if db_task and db_task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                db_task.status = TaskStatus.CANCELLED
                db_task.completed_at = datetime.datetime.now(datetime.timezone.utc)
                
                log_entry = {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "message": "Task was cancelled manually while in a pending or orphaned state.",
                    "level": "WARNING"
                }
                current_logs = db_task.logs or []
                current_logs.append(log_entry)
                db_task.logs = current_logs
                
                db.commit()
                db.refresh(db_task, ['owner'])

                task_data = _serialize_task(db_task)
                payload = {"type": "task_update", "data": task_data}
                if db_task.owner_user_id:
                    manager.send_personal_message_sync(payload, db_task.owner_user_id)
                manager.broadcast_to_admins_sync(payload)
                
                return True

        return False

    def get_task(self, task_id: str) -> Optional[DBTask]:
        """Retrieves a task from the database by its ID."""
        with self.db_session_factory() as db:
            return db.query(DBTask).options(joinedload(DBTask.owner)).filter(DBTask.id == task_id).first()

    def get_all_tasks(self) -> List[DBTask]:
        """Retrieves all tasks from the database for an admin."""
        with self.db_session_factory() as db:
            return db.query(DBTask).options(joinedload(DBTask.owner)).order_by(DBTask.created_at.desc()).all()
    
    def get_tasks_for_user(self, username: str) -> List[DBTask]:
        """Retrieves all tasks for a specific user."""
        with self.db_session_factory() as db:
            return db.query(DBTask).options(joinedload(DBTask.owner)).join(DBUser, DBTask.owner_user_id == DBUser.id).filter(DBUser.username == username).order_by(DBTask.created_at.desc()).all()

    def clear_completed_tasks(self, username: Optional[str] = None):
        """Deletes finished (completed, failed, cancelled) tasks from the database."""
        with self.db_session_factory() as db:
            query = db.query(DBTask).filter(DBTask.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]))
            if username:
                query = query.join(DBUser, DBTask.owner_user_id == DBUser.id).filter(DBUser.username == username)
            
            query.delete(synchronize_session=False)
            db.commit()
            
            payload = {"type": "tasks_cleared", "data": {"username": username}}
            if username:
                 user = db.query(DBUser).filter(DBUser.username == username).first()
                 if user:
                    manager.send_personal_message_sync(payload, user.id)
            else:
                 manager.broadcast_sync(payload)

task_manager = TaskManager()