# backend/tasks/utils.py
from backend.models import TaskInfo
from backend.db.models.db_task import DBTask

def _to_task_info(db_task: DBTask) -> TaskInfo:
    """Converts a DBTask SQLAlchemy model to a TaskInfo Pydantic model."""
    if not db_task:
        return None
    return TaskInfo(
        id=db_task.id, name=db_task.name, description=db_task.description,
        status=db_task.status, progress=db_task.progress,
        logs=[log for log in (db_task.logs or [])], result=db_task.result, error=db_task.error,
        created_at=db_task.created_at, started_at=db_task.started_at, updated_at=db_task.updated_at, completed_at=db_task.completed_at,
        file_name=db_task.file_name, total_files=db_task.total_files,
        owner_username=db_task.owner.username if db_task.owner else "System"
    )