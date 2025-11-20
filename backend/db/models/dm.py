from sqlalchemy import (
    Column, Integer, Text, DateTime, ForeignKey, JSON, String
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.db.base import Base

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True) # Optional, mostly for group chats
    is_group = Column(Integer, default=0) # 0 for DM (migrated or new), 1 for Group
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    members = relationship("ConversationMember", back_populates="conversation", cascade="all, delete-orphan")
    messages = relationship("DirectMessage", back_populates="conversation", cascade="all, delete-orphan")

class ConversationMember(Base):
    __tablename__ = "conversation_members"
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    last_read_at = Column(DateTime(timezone=True), nullable=True)
    
    conversation = relationship("Conversation", back_populates="members")
    user = relationship("User")

class DirectMessage(Base):
    __tablename__ = "direct_messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Receiver ID is kept for legacy 1-on-1 DMs compatibility. 
    # For group chats, this will be NULL.
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # New field for grouping messages
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    
    content = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    read_at = Column(DateTime(timezone=True), nullable=True) # Legacy read receipt
    image_references = Column(JSON, nullable=True)

    sender = relationship("User", foreign_keys=[sender_id], backref="sent_dms")
    receiver = relationship("User", foreign_keys=[receiver_id], backref="received_dms")
    conversation = relationship("Conversation", back_populates="messages")
