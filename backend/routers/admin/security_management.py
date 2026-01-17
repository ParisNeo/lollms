from fastapi import APIRouter, Depends, HTTPException
from backend.models import TaskInfo, UserAuthDetails
from backend.session import get_current_admin_user
from backend.task_manager import task_manager
from backend.tasks.security_tasks import _sanitize_database_task

router = APIRouter(
    prefix="/security",
    tags=["Admin", "Security"],
    dependencies=[Depends(get_current_admin_user)]
)

@router.post("/sanitize-content", response_model=TaskInfo, status_code=202)
async def trigger_content_sanitization(
    current_user: UserAuthDetails = Depends(get_current_admin_user)
):
    """
    Triggers a background task to scan and sanitize all existing database content
    (Posts, Comments, DMs) to remove potential XSS scripts.
    """
    task = task_manager.submit_task(
        name="Database Content Sanitization",
        target=_sanitize_database_task,
        description="Scanning and cleaning existing content for XSS vulnerabilities.",
        owner_username=current_user.username
    )
    return task
