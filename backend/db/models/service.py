import uuid
from sqlalchemy import (
    Column, Integer, String, Boolean,
    ForeignKey, UniqueConstraint,
    DateTime, Text, JSON
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from backend.db.base import Base

class MCP(Base):
    __tablename__ = "mcps"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String, nullable=False, index=True)
    client_id = Column(String, unique=True, index=True, nullable=True) # NEW: SSO identifier
    url = Column(String, nullable=False)
    icon = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    type = Column(String, default="system", nullable=False)
    owner_user_id = Column(Integer, ForeignKey("users.id", name="fk_mcp_owner", ondelete="CASCADE"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    authentication_type = Column(String, default="None", nullable=False)
    authentication_key = Column(String, nullable=True)
    sso_redirect_uri = Column(String, nullable=True)
    sso_user_infos_to_share = Column(JSON, nullable=True)
    owner = relationship("User", back_populates="personal_mcps")
    
    __table_args__ = (UniqueConstraint('owner_user_id', 'name', name='uq_user_mcp_name'),)

class AppZooRepository(Base):
    __tablename__ = "app_zoo_repositories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    url = Column(String, unique=True, nullable=False)
    last_pulled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deletable = Column(Boolean, default=True, nullable=False)

class MCPZooRepository(Base):
    __tablename__ = "mcp_zoo_repositories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    url = Column(String, unique=True, nullable=False)
    last_pulled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deletable = Column(Boolean, default=True, nullable=False)

class App(Base):
    __tablename__ = "apps"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String, nullable=False, index=True)
    client_id = Column(String, unique=True, index=True, nullable=True) # NEW: SSO identifier
    folder_name = Column(String, nullable=True)
    url = Column(String, nullable=True)
    icon = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    type = Column(String, default="system", nullable=False)
    owner_user_id = Column(Integer, ForeignKey("users.id", name="fk_app_owner", ondelete="CASCADE"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    authentication_type = Column(String, default="None", nullable=False)
    authentication_key = Column(String, nullable=True)
    sso_redirect_uri = Column(String, nullable=True)
    sso_user_infos_to_share = Column(JSON, nullable=True)
    
    description = Column(Text, nullable=True)
    author = Column(String, nullable=True, index=True)
    version = Column(String, nullable=True)
    category = Column(String, nullable=True, index=True)
    tags = Column(JSON, nullable=True)
    is_installed = Column(Boolean, default=False, nullable=False, index=True)
    status = Column(String, default='stopped', nullable=False, index=True)
    autostart = Column(Boolean, default=False, nullable=False)
    port = Column(Integer, nullable=True, unique=True)
    pid = Column(Integer, nullable=True)
    app_metadata = Column(JSON, nullable=True)

    owner = relationship("User", back_populates="personal_apps")
    __table_args__ = (UniqueConstraint('owner_user_id', 'name', name='uq_user_app_name'),)


class SystemApp(Base):
    __tablename__ = "system_apps"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    url = Column(String, nullable=False)
    icon = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    authentication_type = Column(String, default="None", nullable=False)
    authentication_key = Column(String, nullable=True)
    sso_redirect_uri = Column(String, nullable=True)
    sso_user_infos_to_share = Column(JSON, nullable=True)