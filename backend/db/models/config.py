# [UPDATE] backend/db/models/config.py
import datetime
from sqlalchemy import (
    Column, Integer, String, JSON, Boolean, DateTime, Float
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import UniqueConstraint

from backend.db.base import Base

class DatabaseVersion(Base):
    __tablename__ = 'database_version'
    id = Column(Integer, primary_key=True)
    version = Column(String, nullable=False)

class GlobalConfig(Base):
    __tablename__ = 'global_configs'
    key = Column(String, primary_key=True, index=True)
    value = Column(JSON, nullable=False)
    description = Column(String, nullable=True)
    category = Column(String, nullable=True, index=True)
    
class LLMBinding(Base):
    __tablename__ = 'llm_bindings'
    id = Column(Integer, primary_key=True, index=True)
    alias = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    config = Column(JSON)
    default_model_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    model_aliases = Column(JSON)

class TTIBinding(Base):
    __tablename__ = 'tti_bindings'
    id = Column(Integer, primary_key=True, index=True)
    alias = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    config = Column(JSON)
    default_model_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    model_aliases = Column(JSON)

class TTSBinding(Base):
    __tablename__ = 'tts_bindings'
    id = Column(Integer, primary_key=True, index=True)
    alias = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    config = Column(JSON)
    default_model_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    model_aliases = Column(JSON)

class RAGBinding(Base):
    __tablename__ = 'rag_bindings'
    id = Column(Integer, primary_key=True, index=True)
    alias = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    config = Column(JSON)
    default_model_name = Column(String, nullable=True) # NEW
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    model_aliases = Column(JSON)