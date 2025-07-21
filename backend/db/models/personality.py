import uuid
from sqlalchemy import (
    Column, Integer, String, Boolean,
    ForeignKey, UniqueConstraint,
    DateTime, Text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from backend.db.base import Base

class Personality(Base):
    __tablename__ = "personalities"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=True, index=True)
    author = Column(String, nullable=True, index=True)
    description = Column(Text, nullable=True)
    prompt_text = Column(Text, nullable=False)
    disclaimer = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    script_code = Column(Text, nullable=True)
    icon_base64 = Column(Text, nullable=True)
    is_public = Column(Boolean, default=False, index=True) 
    owner_user_id = Column(Integer, ForeignKey("users.id", name="fk_personality_owner", ondelete="SET NULL"), nullable=True, index=True)
    owner = relationship("User", foreign_keys=[owner_user_id], back_populates="owned_personalities")
    __table_args__ = (UniqueConstraint('owner_user_id', 'name', name='uq_user_personality_name'),)