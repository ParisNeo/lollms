# [UPDATE] backend/db/models/db_task.py
import uuid
from sqlalchemy import (
    Column, String, Integer, Text, JSON, DateTime,
    ForeignKey, Boolean
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from backend.db.base import Base, TaskStatus

class DBTask(Base):
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, nullable=False, default=TaskStatus.PENDING, index=True)
    progress = Column(Integer, default=0)
    logs = Column(JSON, default=list)
    result = Column(JSON)
    error = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    file_name = Column(String)
    total_files = Column(Integer)
    
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    owner = relationship("User")

class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    cron_expression = Column(String, nullable=False) # e.g., "0 8 * * *"
    prompt = Column(Text, nullable=False) # The prompt to run
    is_active = Column(Boolean, default=True)
    
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    owner = relationship("User", backref="scheduled_tasks")
