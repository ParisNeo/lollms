from sqlalchemy import (
    Column, Integer, String,
    ForeignKey, UniqueConstraint,
    DateTime
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from backend.db.base import Base

class OpenAIAPIKey(Base):
    __tablename__ = "openai_api_keys"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    alias = Column(String(100), nullable=False)
    key_prefix = Column(String(8), nullable=False, unique=True, index=True)
    key_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    user = relationship("User", back_populates="api_keys")
    __table_args__ = (UniqueConstraint('user_id', 'alias', name='uq_user_api_key_alias'),)