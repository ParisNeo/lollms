# backend/db/models/social.py
from sqlalchemy import (
    Column, Integer, String,
    ForeignKey, UniqueConstraint,
    DateTime, Text, JSON
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SQLAlchemyEnum

from backend.db.base import Base, PostVisibility
from backend.db.models.group import Group

class PostLike(Base):
    __tablename__ = 'post_likes'
    user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True)
    post_id = Column(Integer, ForeignKey('posts.id', ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (UniqueConstraint('user_id', 'post_id', name='uq_user_post_like'),)

class Post(Base):
    __tablename__ = 'posts'
    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey('user_groups.id', ondelete="CASCADE"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    media = Column(JSON, nullable=True) 
    visibility = Column(SQLAlchemyEnum(PostVisibility), nullable=False, default=PostVisibility.public, index=True)
    moderation_status = Column(String, default="pending", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    author = relationship("User", back_populates="posts")
    group = relationship("Group")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("PostLike", cascade="all, delete-orphan")

class Comment(Base):
    __tablename__ = 'comments'
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey('posts.id', ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    moderation_status = Column(String, default="pending", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    post = relationship("Post", back_populates="comments")
    author = relationship("User")
