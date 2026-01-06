import uuid
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.db.base import Base

class Notebook(Base):
    __tablename__ = "notebooks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    content = Column(Text, default="") 
    type = Column(String, default="generic") 
    language = Column(String, default="en") # New global language setting
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Stores references to files/sources processed for this notebook
    # Each entry is a dict: { "filename": str, "content": str, "type": str, "is_loaded": bool }
    artefacts = Column(JSON, default=list) 
    
    # Stores tabs. List of dicts: { id, title, type, content, ... }
    tabs = Column(JSON, default=list)
    
    # Stores source queries
    google_search_queries = Column(JSON, default=list)
    arxiv_queries = Column(JSON, default=list)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    owner = relationship("User")
