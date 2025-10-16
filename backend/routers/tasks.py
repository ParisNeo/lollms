# backend/routers/tasks.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from backend.session import get_current_active_user
from backend.task_manager import task_manager
from backend.models import TaskInfo, UserAuthDetails
from backend.tasks.utils import _to_task_info

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
    
    return [_to_task_info(task) for task in tasks]

@tasks_router.get("/{task_id}", response_model=TaskInfo)
def get_task_details(task_id: str, current_user: UserAuthDetails = Depends(get_current_active_user)):
    """
    Retrieves details for a specific task. Accessible by admins or the task owner.
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    
    owner_username = task.owner.username if task.owner else "System"
    if not current_user.is_admin and owner_username != current_user.username:
        raise HTTPException(status_code=403, detail="Not authorized to view this task.")
        
    return _to_task_info(task)

@tasks_router.post("/{task_id}/cancel", response_model=TaskInfo)
def cancel_task(task_id: str, current_user: UserAuthDetails = Depends(get_current_active_user)):
    """
    Signals a running or pending task to cancel. Can be done by an admin or the task owner.
    """
    # 1. First, verify the task exists and the user has permission to act on it.
    initial_task = task_manager.get_task(task_id)
    if not initial_task:
        raise HTTPException(status_code=404, detail="Task not found.")

    owner_username = initial_task.owner.username if initial_task.owner else "System"
    if not current_user.is_admin and owner_username != current_user.username:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this task.")

    # 2. Attempt the cancellation. The manager handles both active and zombie tasks.
    task_manager.cancel_task(task_id)

    # 3. Fetch the final, authoritative state from the database and return it.
    final_task_state = task_manager.get_task(task_id)
    if not final_task_state:
         raise HTTPException(status_code=404, detail="Task disappeared after cancellation attempt.")

    return _to_task_info(final_task_state)


@tasks_router.post("/cancel-all", response_model=dict)
def cancel_all_tasks(current_user: UserAuthDetails = Depends(get_current_active_user)):
    """
    Cancels all running or pending tasks for the current user.
    Admins can cancel all tasks in the system.
    """
    tasks_to_cancel = []
    if current_user.is_admin:
        tasks_to_cancel = task_manager.get_all_tasks()
    else:
        tasks_to_cancel = task_manager.get_tasks_for_user(current_user.username)

    cancelled_count = 0
    for task in tasks_to_cancel:
        # Only attempt to cancel if it's still running or pending
        if task.status in ['running', 'pending']:
            task_manager.cancel_task(task.id)
            cancelled_count += 1
            
    message = f"Successfully initiated cancellation for {cancelled_count} active tasks."
    if current_user.is_admin and cancelled_count > 0:
        message = f"Successfully initiated cancellation for {cancelled_count} active tasks across all users."
    elif cancelled_count == 0:
        message = "No active tasks found to cancel."

    return {"message": message, "cancelled_count": cancelled_count}


@tasks_router.post("/clear-completed", response_model=dict)
def clear_completed_tasks(current_user: UserAuthDetails = Depends(get_current_active_user)):
    """
    Removes completed/failed tasks. Admins clear all, users clear only their own.
    """
    username_to_clear = None if current_user.is_admin else current_user.username
    task_manager.clear_completed_tasks(username=username_to_clear)
    
    message = "All completed and failed tasks have been cleared." if current_user.is_admin else "Your completed and failed tasks have been cleared."
    return {"message": message}