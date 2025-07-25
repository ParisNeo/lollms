from typing import List
from fastapi import APIRouter, Depends, HTTPException
from backend.session import get_current_active_user
from backend.task_manager import task_manager, Task
from backend.models import TaskInfo, UserAuthDetails

tasks_router = APIRouter(
    prefix="/api/tasks",
    tags=["Tasks"],
    dependencies=[Depends(get_current_active_user)]
)

@tasks_router.get("", response_model=List[TaskInfo])
def get_all_tasks(current_user: UserAuthDetails = Depends(get_current_active_user)):
    """
    Retrieves background tasks. Admins get all tasks, regular users get only their own.
    """
    if current_user.is_admin:
        tasks = task_manager.get_all_tasks()
    else:
        tasks = task_manager.get_tasks_for_user(current_user.username)
    
    return [TaskInfo(**task.__dict__) for task in tasks]

@tasks_router.get("/{task_id}", response_model=TaskInfo)
def get_task_details(task_id: str, current_user: UserAuthDetails = Depends(get_current_active_user)):
    """
    Retrieves details for a specific task. Accessible by admins or the task owner.
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    
    if not current_user.is_admin and task.owner_username != current_user.username:
        raise HTTPException(status_code=403, detail="Not authorized to view this task.")
        
    return TaskInfo(**task.__dict__)

@tasks_router.post("/{task_id}/cancel", response_model=TaskInfo)
def cancel_task(task_id: str, current_user: UserAuthDetails = Depends(get_current_active_user)):
    """
    Signals a running or pending task to cancel. Can be done by an admin or the task owner.
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    if not current_user.is_admin and task.owner_username != current_user.username:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this task.")

    task.cancel()
    return TaskInfo(**task.__dict__)

@tasks_router.post("/clear-completed", response_model=dict)
def clear_completed_tasks(current_user: UserAuthDetails = Depends(get_current_active_user)):
    """
    Removes completed/failed tasks. Admins clear all, users clear only their own.
    """
    username_to_clear = None if current_user.is_admin else current_user.username
    task_manager.clear_completed_tasks(username=username_to_clear)
    
    message = "All completed and failed tasks have been cleared." if current_user.is_admin else "Your completed and failed tasks have been cleared."
    return {"message": message}