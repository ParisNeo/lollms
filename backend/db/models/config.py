from sqlalchemy import (
    Column, Integer, String, Boolean,
    CheckConstraint,
    DateTime, Text, JSON
)
from sqlalchemy.sql import func

from backend.db.base import Base

class LLMBinding(Base):
    __tablename__ = "llm_bindings"
    id = Column(Integer, primary_key=True, index=True)
    alias = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    host_address = Column(String)
    models_path = Column(String)
    service_key = Column(String)
    default_model_name = Column(String)
    verify_ssl_certificate = Column(Boolean, default=True, nullable=False)
    model_aliases = Column(JSON, nullable=True)  # NEW: For model aliases
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class GlobalConfig(Base):
    __tablename__ = "global_configs"
    key = Column(String, primary_key=True, index=True)
    value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=False, default="General", index=True)

class DatabaseVersion(Base):
    __tablename__ = "database_version"
    id = Column(Integer, primary_key=True, default=1) 
    version = Column(String, nullable=False)
    applied_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (CheckConstraint('id = 1', name='ck_single_version_row'),)