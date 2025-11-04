from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from pydantic import BaseModel
import datetime

from backend.db import get_db
from backend.db.models.news import NewsArticle as DBNewsArticle, RSSFeedSource as DBRSSFeedSource

# --- Pydantic Models ---
class NewsArticleAdminPublic(BaseModel):
    id: int
    title: str
    url: str
    content: str
    fun_fact: str
    publication_date: Optional[datetime.datetime]
    source_name: str

    class Config:
        from_attributes = True

class NewsArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    fun_fact: Optional[str] = None

class BatchDeleteRequest(BaseModel):
    article_ids: List[int]

# --- Router ---
news_management_router = APIRouter(tags=["Administration", "News Feed"])

@news_management_router.get("/news-articles", response_model=List[NewsArticleAdminPublic])
async def get_all_news_articles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    articles_query = db.query(DBNewsArticle).options(joinedload(DBNewsArticle.source)).order_by(desc(DBNewsArticle.publication_date))
    articles = articles_query.offset(skip).limit(limit).all()
    
    return [
        NewsArticleAdminPublic(
            id=article.id,
            title=article.title,
            url=article.url,
            content=article.content,
            fun_fact=article.fun_fact,
            publication_date=article.publication_date,
            source_name=article.source.name if article.source else "Unknown"
        ) for article in articles
    ]

@news_management_router.put("/news-articles/{article_id}", response_model=NewsArticleAdminPublic)
async def update_news_article(article_id: int, update_data: NewsArticleUpdate, db: Session = Depends(get_db)):
    article = db.query(DBNewsArticle).options(joinedload(DBNewsArticle.source)).filter(DBNewsArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(article, key, value)
    
    db.commit()
    db.refresh(article)
    
    return NewsArticleAdminPublic(
        id=article.id, title=article.title, url=article.url, content=article.content,
        fun_fact=article.fun_fact, publication_date=article.publication_date,
        source_name=article.source.name if article.source else "Unknown"
    )

@news_management_router.post("/news-articles/batch-delete", status_code=200)
async def delete_news_articles_batch(payload: BatchDeleteRequest, db: Session = Depends(get_db)):
    if not payload.article_ids:
        raise HTTPException(status_code=400, detail="No article IDs provided.")
        
    num_deleted = db.query(DBNewsArticle).filter(DBNewsArticle.id.in_(payload.article_ids)).delete(synchronize_session=False)
    db.commit()
    
    return {"message": f"Successfully deleted {num_deleted} article(s)."}