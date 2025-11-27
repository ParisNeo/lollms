# [CREATE] backend/db/models/datastore.py
import uuid
from sqlalchemy import (
    Column, Integer, String,
    ForeignKey,
    DateTime, Index, JSON, UniqueConstraint, CheckConstraint
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional, Dict, Any
from datetime import datetime
from backend.db.base import Base

class DataStore(Base):
    __tablename__ = "datastores"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    vectorizer_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    vectorizer_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=lambda: {})
    chunk_size: Mapped[int] = mapped_column(Integer, default=1024)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=256)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    owner: Mapped["User"] = relationship("User", back_populates="owned_datastores")
    
    __table_args__ = (UniqueConstraint('owner_user_id', 'name', name='uq_user_datastore_name'),)

class SharedDataStoreLink(Base):
    __tablename__ = "shared_datastore_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    datastore_id: Mapped[str] = mapped_column(String, ForeignKey("datastores.id", ondelete="CASCADE"), nullable=False, index=True)
    shared_with_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_level: Mapped[str] = mapped_column(String, nullable=False, default="read_query")

    datastore: Mapped["DataStore"] = relationship("DataStore")
    shared_with_user: Mapped["User"] = relationship("User", foreign_keys=[shared_with_user_id])
    
    __table_args__ = (
        UniqueConstraint('datastore_id', 'shared_with_user_id', name='uq_datastore_shared_user'),
        CheckConstraint(permission_level.in_(['read_query', 'read_write', 'revectorize']), name='ck_datastore_permission_level_valid')
    )
