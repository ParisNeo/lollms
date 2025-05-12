# database_setup.py
# -*- coding: utf-8 -*-
# Project name: simplified_lollms
# File path: database_setup.py
# Author: ParisNeo
# Creation date: 2025-05-08
# Description: Database models and setup for the application.
# Includes User model and UserStarredDiscussion model.

from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, 
    ForeignKey, UniqueConstraint
)
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
    
    # Per-user settings
    lollms_model_name = Column(String, nullable=True)
    safe_store_vectorizer = Column(String, nullable=True)
    # Add more user-specific settings here as needed

    # Relationship to starred discussions (optional, but can be useful)
    starred_discussions = relationship("UserStarredDiscussion", back_populates="user", cascade="all, delete-orphan")

    def verify_password(self, plain_password):
        """Verifies a plain password against the stored hash."""
        return pwd_context.verify(plain_password, self.hashed_password)

# --- New Table for Starred Discussions ---
class UserStarredDiscussion(Base):
    __tablename__ = "user_starred_discussions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    discussion_id = Column(String, nullable=False, index=True) # The UUID string of the discussion YAML file

    # Relationship back to the user (optional, but good practice)
    user = relationship("User", back_populates="starred_discussions")

    # Ensure a user can only star a specific discussion once
    __table_args__ = (UniqueConstraint('user_id', 'discussion_id', name='uq_user_discussion_star'),)

# ---------------------------------------


# Engine and SessionLocal will be initialized in main.py after config is loaded
engine = None
SessionLocal = None

def init_database(db_url: str):
    """Initializes the database engine and creates tables."""
    global engine, SessionLocal
    # Added echo=False for production, can be True for debugging SQL
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, echo=False) # For SQLite
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # create_all checks for table existence before creating, making it safe
    # to run on existing databases. It will add the new table if it's missing.
    Base.metadata.create_all(bind=engine) 
    print(f"INFO: Database tables checked/created using metadata at URL: {db_url}")

def get_db():
    """Dependency generator for getting a database session."""
    if SessionLocal is None:
        # This should ideally not happen if init_database is called correctly at startup
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
