# backend/database/setup.py
# (Content of your original database_setup.py)
# Make sure DATABASE_URL_CONFIG_KEY is used correctly or adjust if APP_DB_URL from config.py is directly used.
# For this refactor, we'll assume init_database gets APP_DB_URL passed directly.

import uuid
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, Text,
    ForeignKey, UniqueConstraint, CheckConstraint,
    DateTime, Float
)
from sqlalchemy.sql import func
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from passlib.context import CryptContext

Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Model Definitions (User, UserStarredDiscussion, etc.) ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)

    lollms_model_name = Column(String, nullable=True)
    safe_store_vectorizer = Column(String, nullable=True) 

    llm_temperature = Column(Float, nullable=True)
    llm_top_k = Column(Integer, nullable=True)
    llm_top_p = Column(Float, nullable=True)
    llm_repeat_penalty = Column(Float, nullable=True)
    llm_repeat_last_n = Column(Integer, nullable=True)

    theme_preference = Column(String, nullable=True, default='system')
    rag_top_k = Column(Integer, nullable=True)

    starred_discussions = relationship("UserStarredDiscussion", back_populates="user", cascade="all, delete-orphan")
    message_grades = relationship("UserMessageGrade", back_populates="user", cascade="all, delete-orphan")
    owned_datastores = relationship("DataStore", back_populates="owner", cascade="all, delete-orphan")
    received_shared_datastores_links = relationship("SharedDataStoreLink", foreign_keys="[SharedDataStoreLink.shared_with_user_id]", back_populates="shared_with_user", cascade="all, delete-orphan")
    prompts = relationship("Prompt", back_populates="owner", cascade="all, delete-orphan")
    sent_friend_requests = relationship("Friendship", foreign_keys="[Friendship.requester_id]", back_populates="requester", cascade="all, delete-orphan")
    received_friend_requests = relationship("Friendship", foreign_keys="[Friendship.addressee_id]", back_populates="addressee", cascade="all, delete-orphan")

    def verify_password(self, plain_password):
        return pwd_context.verify(plain_password, self.hashed_password)

class UserStarredDiscussion(Base):
    __tablename__ = "user_starred_discussions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    discussion_id = Column(String, nullable=False, index=True) 
    user = relationship("User", back_populates="starred_discussions")
    __table_args__ = (UniqueConstraint('user_id', 'discussion_id', name='uq_user_discussion_star'),)

class UserMessageGrade(Base):
    __tablename__ = "user_message_grades"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    discussion_id = Column(String, nullable=False, index=True) 
    message_id = Column(String, nullable=False, index=True)    
    grade = Column(Integer, nullable=False, default=0) # -1, 0, 1
    user = relationship("User", back_populates="message_grades")
    __table_args__ = (UniqueConstraint('user_id', 'discussion_id', 'message_id', name='uq_user_message_grade'),)

class DataStore(Base):
    __tablename__ = "datastores"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True) 
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_public_in_store = Column(Boolean, default=False, nullable=False)
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
    __table_args__ = (
        UniqueConstraint('datastore_id', 'shared_with_user_id', name='uq_datastore_shared_user'),
        CheckConstraint(permission_level.in_(['read_query']), name='ck_permission_level_valid') # Adjusted, original had 'read_write'
    )

class Prompt(Base):
    __tablename__ = "prompts"
    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    description = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    owner = relationship("User", back_populates="prompts")
    __table_args__ = (UniqueConstraint('owner_user_id', 'name', name='uq_user_prompt_name'),)

class Friendship(Base):
    __tablename__ = "friendships"
    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    addressee_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False, default='pending')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    requester = relationship("User", foreign_keys=[requester_id], back_populates="sent_friend_requests")
    addressee = relationship("User", foreign_keys=[addressee_id], back_populates="received_friend_requests")

    __table_args__ = (
        UniqueConstraint('requester_id', 'addressee_id', name='uq_friendship_pair'),
        CheckConstraint("requester_id != addressee_id", name="ck_friendship_not_self"),
        CheckConstraint(status.in_(['pending', 'accepted', 'declined', 'blocked_by_requester', 'blocked_by_addressee']), name='ck_friendship_status_valid')
    )

engine = None
SessionLocal = None

def init_database(db_url: str):
    global engine, SessionLocal
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, echo=False) 
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    print(f"INFO: Database tables checked/created using metadata at URL: {db_url}")

def get_db():
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database first.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)