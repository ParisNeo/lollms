# database_setup.py
# -*- coding: utf-8 -*-
# Project name: simplified_lollms
# File path: database_setup.py
# Author: ParisNeo
# Creation date: 2025-05-08
# Description: Database models and setup for the application.
# Includes User model, UserStarredDiscussion model, UserMessageGrade model,
# DataStore model, and SharedDataStoreLink model.

import uuid # For DataStore ID
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean,
    ForeignKey, UniqueConstraint, CheckConstraint,
    DateTime, Float # Added DateTime and Float
)
from sqlalchemy.sql import func # For default timestamps
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from passlib.context import CryptContext

DATABASE_URL_CONFIG_KEY = "database_url" # Key in config.toml [app_settings]

Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)

    # Per-user settings for LLM
    lollms_model_name = Column(String, nullable=True)
    safe_store_vectorizer = Column(String, nullable=True) # Default vectorizer for new RAG operations

    # New LLM generation parameter defaults per user
    llm_temperature = Column(Float, nullable=True)
    llm_top_k = Column(Integer, nullable=True)
    llm_top_p = Column(Float, nullable=True)
    llm_repeat_penalty = Column(Float, nullable=True)
    llm_repeat_last_n = Column(Integer, nullable=True)


    # Relationships
    starred_discussions = relationship(
        "UserStarredDiscussion",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    message_grades = relationship(
        "UserMessageGrade",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    owned_datastores = relationship( # User is the owner of these datastores
        "DataStore",
        back_populates="owner",
        cascade="all, delete-orphan"
    )
    received_shared_datastores_links = relationship( # Links for datastores shared with this user
        "SharedDataStoreLink",
        foreign_keys="[SharedDataStoreLink.shared_with_user_id]",
        back_populates="shared_with_user",
        cascade="all, delete-orphan"
    )


    def verify_password(self, plain_password):
        """Verifies a plain password against the stored hash."""
        return pwd_context.verify(plain_password, self.hashed_password)

class UserStarredDiscussion(Base):
    __tablename__ = "user_starred_discussions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    discussion_id = Column(String, nullable=False, index=True) # The UUID string of the discussion YAML file

    user = relationship("User", back_populates="starred_discussions")

    __table_args__ = (UniqueConstraint('user_id', 'discussion_id', name='uq_user_discussion_star'),)

class UserMessageGrade(Base):
    __tablename__ = "user_message_grades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    discussion_id = Column(String, nullable=False, index=True) # Identifies the discussion file
    message_id = Column(String, nullable=False, index=True)    # Identifies the message within the discussion
    
    grade = Column(Integer, nullable=False, default=0)

    user = relationship("User", back_populates="message_grades")

    __table_args__ = (
        UniqueConstraint('user_id', 'discussion_id', 'message_id', name='uq_user_message_grade'),
    )

# --- New Table for DataStores (RAG SafeStore instances) ---
class DataStore(Base):
    __tablename__ = "datastores"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True) # UUID as string
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="owned_datastores")
    shared_with_links = relationship( # Links describing who this datastore is shared with
        "SharedDataStoreLink",
        back_populates="datastore",
        cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint('owner_user_id', 'name', name='uq_user_datastore_name'),)

# --- New Table for Shared DataStore Links ---
class SharedDataStoreLink(Base):
    __tablename__ = "shared_datastore_links"

    id = Column(Integer, primary_key=True, index=True)
    datastore_id = Column(String, ForeignKey("datastores.id", ondelete="CASCADE"), nullable=False, index=True)
    shared_with_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # For now, only "read_query" is envisioned. Could be extended.
    permission_level = Column(String, nullable=False, default="read_query") 
    shared_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    datastore = relationship("DataStore", back_populates="shared_with_links")
    shared_with_user = relationship("User", foreign_keys=[shared_with_user_id], back_populates="received_shared_datastores_links")

    __table_args__ = (
        UniqueConstraint('datastore_id', 'shared_with_user_id', name='uq_datastore_shared_user'),
        CheckConstraint(permission_level.in_(['read_query', 'read_write']), name='ck_permission_level_valid') # Example, can expand
    )
# -------------------------------------------------------

# Engine and SessionLocal will be initialized in main.py after config is loaded
engine = None
SessionLocal = None

def init_database(db_url: str):
    """Initializes the database engine and creates tables."""
    global engine, SessionLocal
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, echo=False) # For SQLite
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)
    print(f"INFO: Database tables checked/created using metadata at URL: {db_url}")

def get_db():
    """Dependency generator for getting a database session."""
    if SessionLocal is None:
        print("ERROR: Database SessionLocal not initialized before get_db was called.")
        raise RuntimeError("Database not initialized. Call init_database first.")

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    """Hashes a plain text password."""
    return pwd_context.hash(password)
