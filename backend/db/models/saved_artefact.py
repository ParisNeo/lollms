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
    version = Column(Integer, default=1, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User")

    __table_args__ = (
        Index('ix_saved_artefacts_title', 'title'),
    )

class SharedArtefactLink(Base):
    __tablename__ = "shared_artefact_links"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    artefact_title = Column(String, nullable=False, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    shared_with_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_level = Column(String, nullable=False, default="view") # 'view', 'interact'
    shared_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", foreign_keys=[owner_user_id])
    shared_with_user = relationship("User", foreign_keys=[shared_with_user_id])
