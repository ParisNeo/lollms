# backend/db/models/connections.py
import os
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.db.base import Base

class WebSocketConnection(Base):
    __tablename__ = "websocket_connections"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True) # A unique ID for each WebSocket connection
    worker_pid = Column(Integer, default=lambda: os.getpid())
    connected_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="connections")