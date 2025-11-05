import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Boolean, ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.db.base import Base

class RSSFeedSource(Base):
    __tablename__ = 'rss_feed_sources'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    url = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    articles = relationship("NewsArticle", back_populates="source", cascade="all, delete-orphan")


class NewsArticle(Base):
    __tablename__ = 'news_articles'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("rss_feed_sources.id"), nullable=False)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True, index=True)
    content = Column(Text, nullable=False)
    fun_fact = Column(Text, nullable=False)
    publication_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    source = relationship("RSSFeedSource", back_populates="articles")