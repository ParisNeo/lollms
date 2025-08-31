# backend/db/models/discussion.py
from sqlalchemy import (
    Column, Integer, String,
    ForeignKey, UniqueConstraint, CheckConstraint,
    DateTime
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.db.base import Base

class SharedDiscussionLink(Base):
    __tablename__ = "shared_discussion_links"
    id = Column(Integer, primary_key=True, index=True)
    discussion_id = Column(String, nullable=False, index=True)
    discussion_title = Column(String, nullable=False)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    shared_with_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_level = Column(String, nullable=False, default="view") 
    shared_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", foreign_keys=[owner_user_id], back_populates="owned_shared_discussions")
    shared_with_user = relationship("User", foreign_keys=[shared_with_user_id], back_populates="received_shared_discussions")

    __table_args__ = (
        UniqueConstraint('discussion_id', 'owner_user_id', 'shared_with_user_id', name='uq_discussion_share'),
        CheckConstraint(permission_level.in_(['view', 'interact']), name='ck_share_permission_level_valid')
    )