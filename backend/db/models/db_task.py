import uuid
from sqlalchemy import (
    Column, String, Integer, Text, JSON, DateTime,
    ForeignKey
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
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    file_name = Column(String)
    total_files = Column(Integer)
    
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    owner = relationship("User")