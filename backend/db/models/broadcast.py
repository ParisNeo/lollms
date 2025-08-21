# backend/db/models/broadcast.py
from sqlalchemy import (
    Column, Integer, JSON, DateTime
)
from sqlalchemy.sql import func
from backend.db.base import Base

class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())