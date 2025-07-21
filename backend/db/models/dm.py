from sqlalchemy import (
    Column, Integer,
    ForeignKey,
    DateTime, Text, Index
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from backend.db.base import Base

class DirectMessage(Base):
    __tablename__ = "direct_messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    sender = relationship("User", foreign_keys=[sender_id], backref="sent_direct_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], backref="received_direct_messages")
    __table_args__ = (Index('ix_dm_conversation', 'sender_id', 'receiver_id', 'sent_at'), Index('ix_dm_conversation_alt', 'receiver_id', 'sender_id', 'sent_at'))