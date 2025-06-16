# database_setup.py
# -*- coding: utf-8 -*-
# Project name: simplified_lollms
# File path: database_setup.py
# Author: ParisNeo
# Creation date: 2025-05-08
# Description: Database models and setup for the application.

import uuid
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean,
    ForeignKey, UniqueConstraint, CheckConstraint,
    DateTime, Float, Date, Text, Index,
    inspect, text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.exc import OperationalError

from sqlalchemy import Enum as SQLAlchemyEnum # For status
import enum # For Python enum
from backend.config import DATABASE_URL_CONFIG_KEY
from backend.security import pwd_context

CURRENT_DB_VERSION = "1.3.0"

Base = declarative_base()


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

    # Corrected relationship: Specify foreign_keys
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

    first_name = Column(String, nullable=True)
    family_name = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    birth_date = Column(Date, nullable=True)

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
    name = Column(String, nullable=False, index=True) # Alias
    url = Column(String, nullable=False)

    # If owner_user_id is NULL, it's a default/global MCP defined by an admin.
    owner_user_id = Column(Integer, ForeignKey("users.id", name="fk_mcp_owner", ondelete="CASCADE"), nullable=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="personal_mcps")

    __table_args__ = (
        # A user cannot have two MCPs with the same name.
        # This constraint works for user-owned MCPs. Uniqueness for default (NULL owner_id)
        # MCPs should be handled at the application level.
        UniqueConstraint('owner_user_id', 'name', name='uq_user_mcp_name'),
    )


class DatabaseVersion(Base):
    __tablename__ = "database_version"
    id = Column(Integer, primary_key=True, default=1) 
    version = Column(String, nullable=False)
    applied_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (CheckConstraint('id = 1', name='ck_single_version_row'),)

class FriendshipStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED_BY_USER1 = "blocked_by_user1" # User1 blocked User2
    BLOCKED_BY_USER2 = "blocked_by_user2" # User2 blocked User1
    # Could also have DECLINED if you want to store that state explicitly

class Friendship(Base):
    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True, index=True)
    # User who initiated the request or the user with the lower ID if mutual
    user1_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # User who received the request or the user with the higher ID
    user2_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    status = Column(SQLAlchemyEnum(FriendshipStatus), nullable=False, default=FriendshipStatus.PENDING)
    
    # User ID of the one who performed the last action (e.g., sent request, accepted, blocked)
    # This helps determine who to notify or who initiated a block.
    action_user_id = Column(Integer, ForeignKey("users.id"), nullable=True) 

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user1 = relationship("User", foreign_keys=[user1_id], backref="sent_friend_requests_or_friendships")
    user2 = relationship("User", foreign_keys=[user2_id], backref="received_friend_requests_or_friendships")
    action_user = relationship("User", foreign_keys=[action_user_id])


    __table_args__ = (
        UniqueConstraint('user1_id', 'user2_id', name='uq_friendship_pair'),
        # Ensure user1_id < user2_id to make the pair canonical and simplify queries,
        # or handle this ordering in application logic when creating/querying.
        # For simplicity here, we'll rely on application logic to order user IDs before insert
        # or ensure queries check both (user1_id=A, user2_id=B) OR (user1_id=B, user2_id=A).
        # A CheckConstraint like CheckConstraint('user1_id < user2_id') could enforce canonical storage.
    )


class DirectMessage(Base):
    __tablename__ = "direct_messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    content = Column(Text, nullable=False)
    # Optional: image_references, similar to AppLollmsMessage if you want DMs to support images
    # image_references_json = Column(Text, nullable=True) # Store as JSON string list

    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    read_at = Column(DateTime(timezone=True), nullable=True) # Timestamp when receiver read the message

    sender = relationship("User", foreign_keys=[sender_id], backref="sent_direct_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], backref="received_direct_messages")

    # To easily query conversations between two users
    __table_args__ = (
        Index('ix_dm_conversation', 'sender_id', 'receiver_id', 'sent_at'),
        Index('ix_dm_conversation_alt', 'receiver_id', 'sender_id', 'sent_at'),
    )

engine = None
SessionLocal = None

# init_database function remains the same as the previous version you provided
# (with the migration logic for user_saved_system_prompts and column alterations)
def init_database(db_url: str):
    global engine, SessionLocal
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # This call creates all tables defined in Base's metadata that do not yet exist,
    # including the new `mcps` table. It's the standard way to upgrade the schema.
    Base.metadata.create_all(bind=engine)
    print(f"INFO: Database tables checked/created using metadata at URL: {db_url}")

    inspector = inspect(engine)

    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            if inspector.has_table("user_saved_system_prompts"):
                print("INFO: Found 'user_saved_system_prompts' table. Migrating to 'personalities'.")
                if not inspector.has_table("personalities"):
                    Personality.__table__.create(connection, checkfirst=True)
                    print("INFO: 'personalities' table explicitly created for migration.")

                old_prompts_cursor = connection.execute(text("SELECT id, user_id, title, prompt_text, created_at, updated_at FROM user_saved_system_prompts"))
                old_prompts = old_prompts_cursor.fetchall()
                
                migrated_count = 0
                for old_prompt in old_prompts:
                    new_id = str(uuid.uuid4())
                    stmt = Personality.__table__.insert().values(
                        id=new_id,
                        owner_user_id=old_prompt.user_id,
                        name=old_prompt.title,
                        prompt_text=old_prompt.prompt_text,
                        created_at=old_prompt.created_at,
                        updated_at=old_prompt.updated_at,
                        is_public=False, # Old prompts are user-specific
                        category="Migrated", author="System Migration", description="Migrated from old system prompt.", disclaimer=None,
                        script_code=None, icon_base64=None
                    )
                    connection.execute(stmt)
                    migrated_count += 1
                print(f"INFO: Migrated {migrated_count} prompts from 'user_saved_system_prompts' to 'personalities'.")
                
                connection.execute(text("DROP TABLE user_saved_system_prompts"))
                print("INFO: Dropped 'user_saved_system_prompts' table.")

            if inspector.has_table("users"):
                user_columns_db = [col['name'] for col in inspector.get_columns('users')]
                
                if 'current_system_prompt' in user_columns_db:
                    try:
                        connection.execute(text("ALTER TABLE users RENAME COLUMN current_system_prompt TO _old_current_system_prompt"))
                        connection.execute(text("ALTER TABLE users DROP COLUMN _old_current_system_prompt"))
                        print("INFO: Dropped column 'current_system_prompt' from 'users' table (via rename and drop).")
                        user_columns_db.remove('current_system_prompt') # Update local list
                    except Exception as e_drop_csp_rename:
                        try:
                            connection.execute(text("ALTER TABLE users DROP COLUMN current_system_prompt"))
                            print("INFO: Dropped column 'current_system_prompt' from 'users' table (direct drop).")
                            user_columns_db.remove('current_system_prompt') # Update local list
                        except Exception as e_drop_csp_direct:
                             print(f"WARNING: Could not drop 'current_system_prompt' from 'users': {e_drop_csp_direct}. Manual cleanup might be needed.")


                if 'active_personality_id' not in user_columns_db:
                    connection.execute(text("ALTER TABLE users ADD COLUMN active_personality_id VARCHAR"))
                    print("INFO: Added column 'active_personality_id' (VARCHAR) to 'users' table.")
                    user_columns_db.append('active_personality_id') # Update local list

                new_user_cols_defs = {
                    "first_name": "VARCHAR", "family_name": "VARCHAR", "email": "VARCHAR",
                    "birth_date": "DATE", 
                    "llm_ctx_size": "INTEGER",
                    "rag_top_k": "INTEGER",
                    "max_rag_len": "INTEGER",
                    "rag_n_hops": "INTEGER",
                    "rag_min_sim_percent": "FLOAT",
                    "rag_use_graph": "BOOLEAN DEFAULT 0",
                    "rag_graph_response_type": "VARCHAR DEFAULT 'chunks_summary'",
                    "put_thoughts_in_context": "BOOLEAN DEFAULT 0 NOT NULL",
                }
                for col_name, col_sql_def in new_user_cols_defs.items():
                    if col_name not in user_columns_db:
                        connection.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_sql_def}"))
                        print(f"INFO: Added missing column '{col_name}' to 'users' table.")
                
                current_user_cols_after_add = [col['name'] for col in inspector.get_columns('users')]
                if 'email' in current_user_cols_after_add:
                    user_indexes = inspector.get_indexes('users')
                    email_idx_name = 'ix_users_email'
                    if not any(idx['name'] == email_idx_name for idx in user_indexes):
                        connection.execute(text(f"CREATE INDEX IF NOT EXISTS {email_idx_name} ON users (email)"))
                        print(f"INFO: Created missing index '{email_idx_name}' on 'users.email'.")
            
            if inspector.has_table("personalities"):
                personality_cols_db = [col['name'] for col in inspector.get_columns('personalities')]
                expected_personality_cols_defs = {
                    "id": "VARCHAR NOT NULL", "name": "VARCHAR NOT NULL", "category": "VARCHAR", "author": "VARCHAR",
                    "description": "TEXT", "prompt_text": "TEXT NOT NULL", "disclaimer": "TEXT",
                    "created_at": "DATETIME", "updated_at": "DATETIME",
                    "script_code": "TEXT", "icon_base64": "TEXT",
                    "is_public": "BOOLEAN DEFAULT 0",
                    "owner_user_id": "INTEGER",
                }
                for col_name, col_sql_type_and_constraints in expected_personality_cols_defs.items():
                    if col_name not in personality_cols_db:
                        connection.execute(text(f"ALTER TABLE personalities ADD COLUMN {col_name} {col_sql_type_and_constraints}"))
                        print(f"INFO: Added missing column '{col_name}' to 'personalities' table.")
                
                pers_indexes_db = inspector.get_indexes('personalities')
                pers_req_indexes = {
                    "ix_personalities_name": "name", "ix_personalities_category": "category",
                    "ix_personalities_author": "author", "ix_personalities_is_public": "is_public",
                    "ix_personalities_owner_user_id": "owner_user_id",
                }
                current_pers_cols_after_add = [col['name'] for col in inspector.get_columns('personalities')]
                for idx_name, col_to_idx in pers_req_indexes.items():
                    if col_to_idx in current_pers_cols_after_add:
                        if not any(idx['name'] == idx_name for idx in pers_indexes_db):
                            connection.execute(text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON personalities ({col_to_idx})"))
                            print(f"INFO: Created missing index '{idx_name}' on 'personalities.{col_to_idx}'.")

            transaction.commit()
            print("INFO: Database schema migration/check completed successfully.")
        except Exception as e_migrate:
            transaction.rollback()
            print(f"CRITICAL: Database migration failed: {e_migrate}. Changes rolled back.")
            raise

    session = SessionLocal()
    try:
        if not inspector.has_table("database_version"):
            DatabaseVersion.__table__.create(bind=engine, checkfirst=True)
            if not inspector.has_table("database_version"):
                 raise RuntimeError("'database_version' table could not be created.")

        version_record = session.query(DatabaseVersion).filter_by(id=1).first()
        if version_record:
            if version_record.version != CURRENT_DB_VERSION:
                print(f"INFO: DB version is {version_record.version}. Code expects {CURRENT_DB_VERSION}. Updating.")
                version_record.version = CURRENT_DB_VERSION
                session.commit()
                print(f"INFO: DB version updated to {CURRENT_DB_VERSION}.")
            else:
                print(f"INFO: DB version {CURRENT_DB_VERSION} already set.")
        else:
            print(f"INFO: No DB version record. Setting initial version to {CURRENT_DB_VERSION}.")
            new_version_record = DatabaseVersion(id=1, version=CURRENT_DB_VERSION)
            session.add(new_version_record)
            session.commit()
            print(f"INFO: DB version set to {CURRENT_DB_VERSION}.")
    except OperationalError as e_ver_op:
        print(f"ERROR: OperationalError during DB version management: {e_ver_op}.")
        session.rollback()
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
    # Query for the friendship where user_id < other_user_id
    record = db.query(Friendship).filter(
        ((Friendship.user1_id == user_id) & (Friendship.user2_id == other_user_id)) |
        ((Friendship.user1_id == other_user_id) & (Friendship.user2_id == user_id))
    ).first()

    return record