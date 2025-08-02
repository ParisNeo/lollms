# backend/db/models/dm.py
from sqlalchemy import (
    Column, Integer, Text, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.db.base import Base

class DirectMessage(Base):
    __tablename__ = "direct_messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    read_at = Column(DateTime(timezone=True), nullable=True)
    image_references = Column(JSON, nullable=True)

    sender = relationship("User", foreign_keys=[sender_id], backref="sent_dms")
    receiver = relationship("User", foreign_keys=[receiver_id], backref="received_dms")