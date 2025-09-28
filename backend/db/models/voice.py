# backend/db/models/voice.py
import uuid
from sqlalchemy import (
    Column, Integer, String, Float,
    ForeignKey,
    DateTime
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from backend.db.base import Base

class UserVoice(Base):
    __tablename__ = "user_voices"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    alias = Column(String, nullable=False)
    language = Column(String, nullable=False, default="en") # Default to english
    file_path = Column(String, nullable=False) # Relative to a user's voices folder
    pitch = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    owner = relationship("User", back_populates="voices", foreign_keys=[owner_user_id])