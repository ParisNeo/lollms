# backend/db/models/memory.py
import uuid
from sqlalchemy import (
    Column, Integer, String,
    ForeignKey,
    DateTime, Text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from backend.db.base import Base

class UserMemory(Base):
    __tablename__ = "user_memories"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    owner = relationship("User", back_populates="memories")