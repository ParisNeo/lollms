import uuid
from sqlalchemy import (
    Column, Integer, String, Text,
    ForeignKey, DateTime, JSON, Boolean
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional, Dict, Any, List
from datetime import datetime
from backend.db.base import Base

class Flow(Base):
    __tablename__ = "flows"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Stores { nodes: [], edges: [], viewport: {} }
    data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=lambda: {"nodes": [], "edges": []})
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    owner: Mapped["User"] = relationship("User")

class FlowNodeDefinition(Base):
    __tablename__ = "flow_node_definitions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Visuals & Organization
    label: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, default="General", index=True) # NEW: Grouping
    color: Mapped[str] = mapped_column(String, default="bg-gray-100 border-gray-500")
    icon: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Schema: List of strings or dicts {name, type}
    inputs: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    outputs: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    
    # Logic & Dependencies
    code: Mapped[str] = mapped_column(Text, nullable=False) # Python code
    class_name: Mapped[str] = mapped_column(String, default="CustomNode") # The class to instantiate
    requirements: Mapped[List[str]] = mapped_column(JSON, default=list) # NEW: Library requirements
    
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
