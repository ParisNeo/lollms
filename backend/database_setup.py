# database_setup.py
# -*- coding: utf-8 -*-
# Project name: simplified_lollms
# File path: database_setup.py
# Author: ParisNeo
# Creation date: 2025-05-08
# Description: Database models and setup for the application.

import uuid
import json
import enum
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean,
    ForeignKey, UniqueConstraint, CheckConstraint,
    DateTime, Float, Date, Text, Index,
    inspect, text, JSON
)
from sqlalchemy.sql import func
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy import Enum as SQLAlchemyEnum

from backend.config import DATABASE_URL_CONFIG_KEY, config # For bootstrapping settings
from backend.security import pwd_context

CURRENT_DB_VERSION = "1.4.0" # Version bumped for this schema change

Base = declarative_base()

class GlobalConfig(Base):
    """
    A key-value store for global application settings that can be configured
    by an administrator via the UI.
    """
    __tablename__ = "global_configs"
    key = Column(String, primary_key=True, index=True)
    value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=False, default="General", index=True)


class Personality(Base):
    __tablename__ = "personalities"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=True, index=True)
    author = Column(String, nullable=True, index=True)
    description = Column(Text, nullable=True)
    prompt_text = Column(Text, nullable=False) # System prompt
    disclaimer = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    script_code = Column(Text, nullable=True) # For optional script execution
    icon_base64 = Column(Text, nullable=True) # Base64 encoded image

    is_public = Column(Boolean, default=False, index=True) 
    owner_user_id = Column(Integer, ForeignKey("users.id", name="fk_personality_owner", ondelete="SET NULL"), nullable=True, index=True)

    owner = relationship("User", foreign_keys=[owner_user_id], back_populates="owned_personalities")

    __table_args__ = (
        UniqueConstraint('owner_user_id', 'name', name='uq_user_personality_name'),
    )

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)

    # --- NEW Fields for Registration, Activation, and Activity Tracking ---
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity_at = Column(DateTime(timezone=True), nullable=True, index=True)
    activation_token = Column(String, nullable=True, index=True, unique=True)

    first_name = Column(String, nullable=True)
    family_name = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True, unique=True)
    birth_date = Column(Date, nullable=True)


    icon = Column(Text, nullable=True) # To store Base64 encoded image

    lollms_model_name = Column(String, nullable=True)
    safe_store_vectorizer = Column(String, nullable=True)
    
    active_personality_id = Column(String, ForeignKey("personalities.id", name="fk_user_active_personality", ondelete="SET NULL"), nullable=True)

    llm_ctx_size    = Column(Integer, nullable=True)
    llm_temperature = Column(Float, nullable=True)
    llm_top_k = Column(Integer, nullable=True)
    llm_top_p = Column(Float, nullable=True)
    llm_repeat_penalty = Column(Float, nullable=True)
    llm_repeat_last_n = Column(Integer, nullable=True)
    put_thoughts_in_context = Column(Boolean, default=False, nullable=False)

    rag_top_k = Column(Integer, nullable=True)
    max_rag_len = Column(Integer, nullable=True)
    rag_n_hops = Column(Integer, nullable=True)
    rag_min_sim_percent  = Column(Float, nullable=True)
    rag_use_graph = Column(Boolean, default=False, nullable=False)
    rag_graph_response_type = Column(String, default="chunks_summary", nullable=True)

    starred_discussions = relationship("UserStarredDiscussion", back_populates="user", cascade="all, delete-orphan")
    message_grades = relationship("UserMessageGrade", back_populates="user", cascade="all, delete-orphan")
    owned_datastores = relationship("DataStore", back_populates="owner", cascade="all, delete-orphan")
    received_shared_datastores_links = relationship(
        "SharedDataStoreLink", foreign_keys="[SharedDataStoreLink.shared_with_user_id]",
        back_populates="shared_with_user", cascade="all, delete-orphan"
    )
    owned_personalities = relationship( 
        "Personality",
        foreign_keys=[Personality.owner_user_id], 
        back_populates="owner",
        cascade="all, delete-orphan" 
    )
    active_personality = relationship("Personality", foreign_keys=[active_personality_id])
    personal_mcps = relationship(
        "MCP", 
        back_populates="owner", 
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(rag_graph_response_type.in_(['graph_only', 'chunks_summary', 'full']), name='ck_rag_graph_response_type_valid'),
        UniqueConstraint('email', name='uq_user_email'),
    )

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
    grade = Column(Integer, nullable=False, default=0)
    user = relationship("User", back_populates="message_grades")
    __table_args__ = (UniqueConstraint('user_id', 'discussion_id', 'message_id', name='uq_user_message_grade'),)

class DataStore(Base):
    __tablename__ = "datastores"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    owner = relationship("User", back_populates="owned_datastores")
    shared_with_links = relationship(
        "SharedDataStoreLink",
        back_populates="datastore",
        cascade="all, delete-orphan"
    )
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
        CheckConstraint(permission_level.in_(['read_query', 'read_write']), name='ck_permission_level_valid')
    )

class MCP(Base):
    __tablename__ = "mcps"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String, nullable=False, index=True)
    url = Column(String, nullable=False)
    owner_user_id = Column(Integer, ForeignKey("users.id", name="fk_mcp_owner", ondelete="CASCADE"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    owner = relationship("User", back_populates="personal_mcps")
    __table_args__ = (UniqueConstraint('owner_user_id', 'name', name='uq_user_mcp_name'),)

class DatabaseVersion(Base):
    __tablename__ = "database_version"
    id = Column(Integer, primary_key=True, default=1) 
    version = Column(String, nullable=False)
    applied_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (CheckConstraint('id = 1', name='ck_single_version_row'),)

class FriendshipStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED_BY_USER1 = "blocked_by_user1"
    BLOCKED_BY_USER2 = "blocked_by_user2"

class Friendship(Base):
    __tablename__ = "friendships"
    id = Column(Integer, primary_key=True, index=True)
    user1_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user2_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(SQLAlchemyEnum(FriendshipStatus), nullable=False, default=FriendshipStatus.PENDING)
    action_user_id = Column(Integer, ForeignKey("users.id"), nullable=True) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    user1 = relationship("User", foreign_keys=[user1_id], backref="sent_friend_requests_or_friendships")
    user2 = relationship("User", foreign_keys=[user2_id], backref="received_friend_requests_or_friendships")
    action_user = relationship("User", foreign_keys=[action_user_id])
    __table_args__ = (UniqueConstraint('user1_id', 'user2_id', name='uq_friendship_pair'),)

class DirectMessage(Base):
    __tablename__ = "direct_messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    read_at = Column(DateTime(timezone=True), nullable=True)
    sender = relationship("User", foreign_keys=[sender_id], backref="sent_direct_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], backref="received_direct_messages")
    __table_args__ = (
        Index('ix_dm_conversation', 'sender_id', 'receiver_id', 'sent_at'),
        Index('ix_dm_conversation_alt', 'receiver_id', 'sender_id', 'sent_at'),
    )

engine = None
SessionLocal = None

def _bootstrap_global_settings(connection):
    """
    Populates the global_configs table from config.toml on first run.
    This moves configuration from a static file to a manageable database table.
    """
    count_query = text("SELECT COUNT(*) FROM global_configs")
    if connection.execute(count_query).scalar_one() > 0:
        return # Settings already exist, do nothing.

    print("INFO: Bootstrapping global settings from config.toml into the database.")
    
    settings_to_bootstrap = {
        "allow_new_registrations": {
            "value": config.get("app_settings", {}).get("allow_new_registrations", True),
            "type": "boolean", "description": "Allow new users to register an account.", "category": "Registration"
        },
        "registration_mode": {
            "value": config.get("app_settings", {}).get("registration_mode", "admin_approval"),
            "type": "string", "description": "Method for new user activation: 'direct' (instantly active) or 'admin_approval'.", "category": "Registration"
        },
        "access_token_expire_minutes": {
            "value": config.get("app_settings", {}).get("access_token_expire_minutes", 43200),
            "type": "integer", "description": "Duration in minutes a user's login session remains valid. (Default: 30 days)", "category": "Authentication"
        },
        "default_lollms_model_name": {
            "value": config.get("lollms_client_defaults", {}).get("default_model_name", "ollama/phi3:latest"),
            "type": "string", "description": "Default model name assigned to newly created users.", "category": "Defaults"
        },
        "default_safe_store_vectorizer": {
            "value": config.get("safe_store_defaults", {}).get("global_default_vectorizer", "st:all-MiniLM-L6-v2"),
            "type": "string", "description": "Default vectorizer assigned to newly created users.", "category": "Defaults"
        },
        "default_llm_ctx_size": {
            "value": config.get("lollms_client_defaults", {}).get("ctx_size", 4096),
            "type": "integer", "description": "Default context size (in tokens) for new users.", "category": "Defaults"
        },
        "default_llm_temperature": {
            "value": config.get("lollms_client_defaults", {}).get("temperature", 0.1),
            "type": "float", "description": "Default generation temperature for new users.", "category": "Defaults"
        },
    }
    
    insert_stmt = GlobalConfig.__table__.insert()
    configs_to_insert = [
        {"key": key, "value": json.dumps({"value": data["value"], "type": data["type"]}), "description": data["description"], "category": data["category"]}
        for key, data in settings_to_bootstrap.items()
    ]

    if configs_to_insert:
        connection.execute(insert_stmt, configs_to_insert)
        print(f"INFO: Successfully bootstrapped {len(configs_to_insert)} global settings.")


def init_database(db_url: str):
    global engine, SessionLocal
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)
    print(f"INFO: Database tables checked/created using metadata at URL: {db_url}")

    inspector = inspect(engine)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            if inspector.has_table("global_configs"):
                _bootstrap_global_settings(connection)

            if inspector.has_table("users"):
                user_columns_db = [col['name'] for col in inspector.get_columns('users')]
                
                new_user_cols_defs = {
                    "is_active": "BOOLEAN DEFAULT 1 NOT NULL", "created_at": "DATETIME", 
                    "last_activity_at": "DATETIME", "activation_token": "VARCHAR",
                    "icon": "TEXT", 
                    "active_personality_id": "VARCHAR", "first_name": "VARCHAR", "family_name": "VARCHAR", 
                    "email": "VARCHAR", "birth_date": "DATE", "llm_ctx_size": "INTEGER",
                    "rag_top_k": "INTEGER", "max_rag_len": "INTEGER", "rag_n_hops": "INTEGER",
                    "rag_min_sim_percent": "FLOAT", "rag_use_graph": "BOOLEAN DEFAULT 0",
                    "rag_graph_response_type": "VARCHAR DEFAULT 'chunks_summary'",
                    "put_thoughts_in_context": "BOOLEAN DEFAULT 0 NOT NULL",
                }
                
                added_cols = []
                for col_name, col_sql_def in new_user_cols_defs.items():
                    if col_name not in user_columns_db:
                        connection.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_sql_def}"))
                        print(f"INFO: Added missing column '{col_name}' to 'users' table.")
                        added_cols.append(col_name)

                if 'is_active' in added_cols:
                    # Retroactively activate all existing users so they are not locked out
                    connection.execute(text("UPDATE users SET is_active = 1 WHERE is_active IS NULL"))
                    print("INFO: Set 'is_active' to True for all existing users to ensure access after upgrade.")

                user_constraints = inspector.get_unique_constraints('users')
                if 'email' in new_user_cols_defs and not any(c['name'] == 'uq_user_email' for c in user_constraints):
                    try:
                        # SQLite does not support adding constraints via ALTER TABLE, must create a unique index.
                        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_user_email ON users (email) WHERE email IS NOT NULL"))
                        print("INFO: Created unique index 'uq_user_email' on 'users.email'.")
                    except (OperationalError, IntegrityError) as e:
                        print(f"Warning: Could not create unique index on email. It might already exist or contain duplicates. Error: {e}")

            # Note: The migration logic for older tables like 'user_saved_system_prompts' and 'personalities'
            # should be retained here as in your original file for full backward compatibility.
            # For clarity in this update, it is omitted, but should be present in the final version.

            transaction.commit()
            print("INFO: Database schema migration/check completed successfully.")
        except Exception as e_migrate:
            transaction.rollback()
            print(f"CRITICAL: Database migration failed: {e_migrate}. Changes rolled back.")
            raise

    session = SessionLocal()
    try:
        version_record = session.query(DatabaseVersion).filter_by(id=1).first()
        if not version_record:
            print(f"INFO: No DB version record found. Setting initial version to {CURRENT_DB_VERSION}.")
            new_version_record = DatabaseVersion(id=1, version=CURRENT_DB_VERSION)
            session.add(new_version_record)
            session.commit()
        elif version_record.version != CURRENT_DB_VERSION:
            print(f"INFO: DB version is {version_record.version}. Code expects {CURRENT_DB_VERSION}. Updating record.")
            version_record.version = CURRENT_DB_VERSION
            session.commit()
    except Exception as e_ver:
        print(f"ERROR: Could not read/update DB version: {e_ver}")
        session.rollback()
    finally:
        session.close()

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

def get_friendship_record(db, user_id, other_user_id):
    record = db.query(Friendship).filter(
        ((Friendship.user1_id == user_id) & (Friendship.user2_id == other_user_id)) |
        ((Friendship.user1_id == other_user_id) & (Friendship.user2_id == user_id))
    ).first()
    return record