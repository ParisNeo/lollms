import uuid
from sqlalchemy import (
    Column, String, Text, ForeignKey, Integer, Index
)
from sqlalchemy.orm import relationship

from backend.db.base import Base

class SavedPrompt(Base):
    __tablename__ = "saved_prompts"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # NEW: Fields for Zoo integration
    category = Column(String, nullable=True, index=True)
    author = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    icon = Column(Text, nullable=True) # Base64 icon

    owner = relationship("User")
    
    __table_args__ = (
        Index('ix_saved_prompts_name', 'name'),
    )