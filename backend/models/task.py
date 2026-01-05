# backend/models/task.py
import datetime
from typing import List, Optional, Any
from pydantic import BaseModel
from backend.db.base import TaskStatus

class TaskLogMessage(BaseModel):
    timestamp: str
    message: str
    level: str

class TaskInfo(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: TaskStatus
    progress: float
    logs: List[TaskLogMessage]
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime.datetime
    started_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    file_name: Optional[str] = None
    total_files: Optional[int] = None
    owner_username: Optional[str] = None

    class Config:
        from_attributes = True