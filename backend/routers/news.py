from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List

from backend.db import get_db
from backend.db.models.news import NewsArticle
from backend.models.news import NewsArticlePublic

news_router = APIRouter(prefix="/api/news", tags=["News"])

@news_router.get("", response_model=List[NewsArticlePublic])
async def get_news_articles(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    articles = db.query(NewsArticle).order_by(desc(NewsArticle.publication_date)).offset(skip).limit(limit).all()
    return articles