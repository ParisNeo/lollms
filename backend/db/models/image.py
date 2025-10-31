# backend/db/models/image.py
import uuid
from sqlalchemy import (
    Column, Integer, String, Text,
    ForeignKey,
    DateTime, JSON
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from backend.db.base import Base

class UserImage(Base):
    __tablename__ = "user_images"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    discussion_id = Column(String, nullable=True, index=True) # To link image back to a discussion if it's moved
    
    filename = Column(String, nullable=False)
    prompt = Column(Text, nullable=True)
    negative_prompt = Column(Text, nullable=True)
    model = Column(String, nullable=True)
    seed = Column(Integer, nullable=True)
    generation_params = Column(JSON, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    owner = relationship("User", back_populates="images")