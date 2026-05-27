import uuid
from sqlalchemy import (
    Column, String, Text, ForeignKey, Integer, Index, DateTime
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from backend.db.base import Base

class SavedArtefact(Base):
    __tablename__ = "saved_artefacts"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    artefact_type = Column(String, nullable=True, default="document") # 'document', 'code', 'note', 'skill', etc.
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User")
    
    __table_args__ = (
        Index('ix_saved_artefacts_title', 'title'),
    )
