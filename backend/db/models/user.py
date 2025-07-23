from sqlalchemy import (
    Column, Integer, String, Boolean,
    ForeignKey, UniqueConstraint, CheckConstraint,
    DateTime, Float, Date, Text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SQLAlchemyEnum

from backend.security import pwd_context
from backend.db.base import Base, FriendshipStatus, follows_table

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity_at = Column(DateTime(timezone=True), nullable=True, index=True)
    activation_token = Column(String, nullable=True, index=True, unique=True)
    password_reset_token = Column(String, nullable=True, unique=True, index=True)
    reset_token_expiry = Column(DateTime, nullable=True)
    first_name = Column(String, nullable=True)
    family_name = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True, unique=True)
    birth_date = Column(Date, nullable=True)
    icon = Column(Text, nullable=True)
    receive_notification_emails = Column(Boolean, default=True, nullable=False)
    is_searchable = Column(Boolean, default=True, nullable=False, index=True)
    first_login_done = Column(Boolean, default=False, nullable=False)
    data_zone = Column(Text, nullable=True)
    
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    
    following = relationship(
        'User',
        secondary=follows_table,
        primaryjoin='User.id==follows.c.follower_id',
        secondaryjoin='User.id==follows.c.following_id',
        backref='followers'
    )

    api_keys = relationship("OpenAIAPIKey", back_populates="user", cascade="all, delete-orphan")

    lollms_model_name = Column(String, nullable=True)
    safe_store_vectorizer = Column(String, nullable=True)
    active_personality_id = Column(String, ForeignKey("personalities.id", name="fk_user_active_personality", ondelete="SET NULL"), nullable=True)
    llm_ctx_size = Column(Integer, nullable=True)
    llm_temperature = Column(Float, nullable=True)
    llm_top_k = Column(Integer, nullable=True)
    llm_top_p = Column(Float, nullable=True)
    llm_repeat_penalty = Column(Float, nullable=True)
    llm_repeat_last_n = Column(Integer, nullable=True)
    put_thoughts_in_context = Column(Boolean, default=False, nullable=False)
    rag_top_k = Column(Integer, nullable=True)
    max_rag_len = Column(Integer, nullable=True)
    rag_n_hops = Column(Integer, nullable=True)
    rag_min_sim_percent = Column(Float, nullable=True)
    rag_use_graph = Column(Boolean, default=False, nullable=True)
    rag_graph_response_type = Column(String, default="chunks_summary", nullable=True)
    auto_title = Column(Boolean, default=False, nullable=False)
    user_ui_level = Column(Integer, default=0, nullable=True)
    chat_active = Column(Integer, default=False, nullable=False)
    first_page = Column(String, default="feed", nullable=False)
    ai_response_language = Column(String, default=0, nullable=True)
    fun_mode = Column(Boolean, default=False, nullable=True)
    show_token_counter = Column(Boolean, default=True, nullable=False)
    
    starred_discussions = relationship("UserStarredDiscussion", back_populates="user", cascade="all, delete-orphan")
    message_grades = relationship("UserMessageGrade", back_populates="user", cascade="all, delete-orphan")
    owned_datastores = relationship("DataStore", back_populates="owner", cascade="all, delete-orphan")
    received_shared_datastores_links = relationship("SharedDataStoreLink", foreign_keys="[SharedDataStoreLink.shared_with_user_id]", back_populates="shared_with_user", cascade="all, delete-orphan")
    owned_personalities = relationship("Personality", foreign_keys="[Personality.owner_user_id]", back_populates="owner", cascade="all, delete-orphan")
    active_personality = relationship("Personality", foreign_keys=[active_personality_id])
    personal_mcps = relationship("MCP", back_populates="owner", cascade="all, delete-orphan")
    personal_apps = relationship("App", back_populates="owner", cascade="all, delete-orphan")
    
    __table_args__ = (CheckConstraint(rag_graph_response_type.in_(['graph_only', 'chunks_summary', 'full']), name='ck_rag_graph_response_type_valid'), UniqueConstraint('email', name='uq_user_email'),)
    
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

class Friendship(Base):
    __tablename__ = "friendships"
    id = Column(Integer, primary_key=True, index=True)
    user1_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user2_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(SQLAlchemyEnum(FriendshipStatus), nullable=False, default=FriendshipStatus.PENDING, index=True)
    action_user_id = Column(Integer, ForeignKey("users.id"), nullable=True) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    user1 = relationship("User", foreign_keys=[user1_id], backref="sent_friend_requests_or_friendships")
    user2 = relationship("User", foreign_keys=[user2_id], backref="received_friend_requests_or_friendships")
    action_user = relationship("User", foreign_keys=[action_user_id])
    __table_args__ = (UniqueConstraint('user1_id', 'user2_id', name='uq_friendship_pair'),)