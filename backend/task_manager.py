import uuid
import datetime
import threading
from enum import Enum
from typing import List, Dict, Any, Callable, Optional

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task:
    def __init__(self, name: str, target: Callable, args: tuple = (), kwargs: dict = None, description: Optional[str] = None):
        self.id: str = str(uuid.uuid4())
        self.name: str = name
        self.description: Optional[str] = description or name
        self.target: Callable = target
        self.args: tuple = args
        self.kwargs: dict = kwargs or {}
        self.status: TaskStatus = TaskStatus.PENDING
        self.progress: int = 0
        self.logs: List[Dict[str, Any]] = []
        self.result: Any = None
        self.error: Optional[str] = None
        self.created_at: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)
        self.started_at: Optional[datetime.datetime] = None
        self.completed_at: Optional[datetime.datetime] = None
        self.cancellation_event = threading.Event()
        self.file_name: Optional[str] = None
        self.total_files: Optional[int] = None

    def log(self, message: str, level: str = "INFO"):
        self.logs.append({
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "message": message,
            "level": level
        })

    def set_progress(self, value: int):
        self.progress = max(0, min(100, value))

    def set_description(self, description: str):
        self.description = description
    
    def set_file_info(self, file_name: str, total_files: int):
        self.file_name = file_name
        self.total_files = total_files

    def cancel(self):
        if self.status in [TaskStatus.RUNNING, TaskStatus.PENDING]:
            self.cancellation_event.set()
            self.log("Cancellation signal received.", level="WARNING")

    def run(self):
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.datetime.now(datetime.timezone.utc)
        self.log(f"Task '{self.name}' started.")
        try:
            # Pass the task instance itself to the target function
            self.result = self.target(self, *self.args, **self.kwargs)
            
            if self.cancellation_event.is_set():
                self.status = TaskStatus.CANCELLED
                self.log(f"Task '{self.name}' was cancelled.", level="WARNING")
            else:
                self.status = TaskStatus.COMPLETED
                self.progress = 100
                self.log(f"Task '{self.name}' completed successfully.")

        except Exception as e:
            self.status = TaskStatus.FAILED
            self.error = str(e)
            self.log(f"Task '{self.name}' failed: {e}", level="CRITICAL")
            import traceback
            traceback.print_exc()
        finally:
            self.completed_at = datetime.datetime.now(datetime.timezone.utc)

class TaskManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskManager, cls).__new__(cls)
            cls._instance.tasks: Dict[str, Task] = {}
        return cls._instance

    def submit_task(self, name: str, target: Callable, args: tuple = (), kwargs: dict = None, description: Optional[str] = None) -> Task:
        task = Task(name=name, target=target, args=args, kwargs=kwargs, description=description)
        self.tasks[task.id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        return sorted(list(self.tasks.values()), key=lambda t: t.created_at, reverse=True)

    def clear_completed_tasks(self):
        tasks_to_keep = {
            task_id: task for task_id, task in self.tasks.items()
            if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
        }
        self.tasks = tasks_to_keep

task_manager = TaskManager()