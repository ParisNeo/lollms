import datetime
from typing import List, Optional, Any
from pydantic import BaseModel
from backend.task_manager import TaskStatus

class TaskLogMessage(BaseModel):
    timestamp: str
    message: str
    level: str

class TaskInfo(BaseModel):
    id: str
    name: str
    status: TaskStatus
    progress: int
    logs: List[TaskLogMessage]
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime.datetime
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None