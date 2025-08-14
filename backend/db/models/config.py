# backend/db/models/config.py
from sqlalchemy import (
    Column, Integer, String, Boolean, JSON,
    DateTime, Text
)
from sqlalchemy.sql import func

from backend.db.base import Base

class GlobalConfig(Base):
    __tablename__ = "global_configs"
    key = Column(String, primary_key=True, index=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=False, default="General", index=True)

class LLMBinding(Base):
    __tablename__ = "llm_bindings"
    id = Column(Integer, primary_key=True, index=True)
    alias = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)  # This is the binding_name from lollms-client
    config = Column(JSON, nullable=False, default=lambda: {})
    default_model_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    model_aliases = Column(JSON, nullable=True)

class DatabaseVersion(Base):
    __tablename__ = "database_version"
    id = Column(Integer, primary_key=True)
    # Changed from Integer to String to correctly store version like "1.7.1"
    version = Column(String, nullable=False)