import uuid
from sqlalchemy import (
    Column, Integer, String,
    ForeignKey, UniqueConstraint, CheckConstraint,
    DateTime
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from backend.db.base import Base

class DataStore(Base):
    __tablename__ = "datastores"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    owner = relationship("User", back_populates="owned_datastores")
    shared_with_links = relationship("SharedDataStoreLink", back_populates="datastore", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint('owner_user_id', 'name', name='uq_user_datastore_name'),)

class SharedDataStoreLink(Base):
    __tablename__ = "shared_datastore_links"
    id = Column(Integer, primary_key=True, index=True)
    datastore_id = Column(String, ForeignKey("datastores.id", ondelete="CASCADE"), nullable=False, index=True)
    shared_with_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_level = Column(String, nullable=False, default="read_query") 
    shared_at = Column(DateTime(timezone=True), server_default=func.now())
    datastore = relationship("DataStore", back_populates="shared_with_links")
    shared_with_user = relationship("User", foreign_keys=[shared_with_user_id], back_populates="received_shared_datastores_links")
    __table_args__ = (UniqueConstraint('datastore_id', 'shared_with_user_id', name='uq_datastore_shared_user'), CheckConstraint(permission_level.in_(['read_query', 'read_write', 'revectorize']), name='ck_permission_level_valid'))