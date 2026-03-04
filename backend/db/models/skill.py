import uuid
from sqlalchemy import (
    Column, String, Text, ForeignKey, Integer, Index, DateTime
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from backend.db.base import Base

class Skill(Base):
    __tablename__ = "skills"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    language = Column(String, nullable=True, default="markdown")
    content = Column(Text, nullable=False)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="skills")
    
    __table_args__ = (
        Index('ix_skills_name', 'name'),
    )