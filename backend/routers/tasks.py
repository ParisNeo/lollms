from typing import List
from fastapi import APIRouter, Depends, HTTPException
from backend.session import get_current_admin_user
from backend.task_manager import task_manager, Task
from backend.models import TaskInfo

tasks_router = APIRouter(
    prefix="/api/tasks",
    tags=["Tasks"],
    dependencies=[Depends(get_current_admin_user)]
)

@tasks_router.get("", response_model=List[TaskInfo])
def get_all_tasks():
    """
    Retrieves a list of all current and past background tasks.
    """
    tasks = task_manager.get_all_tasks()
    return [TaskInfo(**task.__dict__) for task in tasks]

@tasks_router.get("/{task_id}", response_model=TaskInfo)
def get_task_details(task_id: str):
    """
    Retrieves the detailed status and logs for a specific task.
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return TaskInfo(**task.__dict__)

@tasks_router.post("/{task_id}/cancel", response_model=TaskInfo)
def cancel_task(task_id: str):
    """
    Signals a running or pending task to cancel.
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    task.cancel()
    return TaskInfo(**task.__dict__)

@tasks_router.post("/clear-completed", response_model=dict)
def clear_completed_tasks():
    """
    Removes all completed and failed tasks from the manager to clean up the list.
    """
    task_manager.clear_completed_tasks()
    return {"message": "Completed and failed tasks have been cleared."}