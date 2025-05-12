# database_setup.py
# -*- coding: utf-8 -*-
# Project name: simplified_lollms
# File path: database_setup.py
# Author: ParisNeo
# Creation date: 2025-05-08
# Description: Database models and setup for the application.
# Includes User model, UserStarredDiscussion model, and UserMessageGrade model.

from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean,
    ForeignKey, UniqueConstraint, CheckConstraint
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

# --- New Table for User Message Grades ---
class UserMessageGrade(Base):
    __tablename__ = "user_message_grades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    discussion_id = Column(String, nullable=False, index=True) # Identifies the discussion file
    message_id = Column(String, nullable=False, index=True)    # Identifies the message within the discussion
    
    # Cumulative grade given by this user for this specific message.
    # Can be positive (upvotes) or negative (downvotes).
    grade = Column(Integer, nullable=False, default=0)

    user = relationship("User", back_populates="message_grades")

    # Ensure a user can only have one grade entry per message
    __table_args__ = (
        UniqueConstraint('user_id', 'discussion_id', 'message_id', name='uq_user_message_grade'),
        # Optional: CheckConstraint(grade >= -N AND grade <= M, name='ck_grade_range') if you want to limit total grade
    )
# ---------------------------------------

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
