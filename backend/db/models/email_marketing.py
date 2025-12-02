from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum
from sqlalchemy.sql import func
import enum
from backend.db.base import Base

class EmailStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    SENT = "sent"
    REJECTED = "rejected"
    ARCHIVED = "archived"

class EmailProposal(Base):
    __tablename__ = "email_proposals"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    source_topic = Column(String, nullable=True) # The topic that triggered this
    research_notes = Column(Text, nullable=True) # Context used/found during search
    
    status = Column(Enum(EmailStatus), default=EmailStatus.DRAFT, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    sent_at = Column(DateTime(timezone=True), nullable=True)
    
    admin_feedback = Column(Text, nullable=True) # Reason for rejection or notes
    generated_by = Column(String, default="lollms_bot") 

class EmailTopic(Base):
    """Topics suggested by admin or learned from successful emails"""
    __tablename__ = "email_topics"
    id = Column(Integer, primary_key=True)
    topic = Column(String, nullable=False)
    source = Column(String, default="admin") # admin, learned
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
