from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.db.models.news import RSSFeedSource as DBRSSFeedSource
from backend.models.news import RSSFeedSourceCreate, RSSFeedSourcePublic
from backend.models.task import TaskInfo
from backend.session import get_current_admin_user
from backend.task_manager import task_manager
from backend.tasks.news_tasks import _scrape_rss_feeds_task
from backend.tasks.utils import _to_task_info

rss_management_router = APIRouter(
    tags=["Administration", "News Feed"],
)

@rss_management_router.post("/rss-feeds/scrape", response_model=TaskInfo, status_code=202)
async def trigger_rss_feed_scraping(current_user=Depends(get_current_admin_user)):
    """
    Manually triggers the RSS feed scraping and processing task.
    """
    db_task = task_manager.submit_task(
        name="Manual RSS Feed Scraping",
        target=_scrape_rss_feeds_task,
        description="Fetching and processing all active RSS feeds for new articles.",
        owner_username=current_user.username
    )
    return _to_task_info(db_task)

@rss_management_router.get("/rss-feeds", response_model=List[RSSFeedSourcePublic])
async def get_rss_feeds(db: Session = Depends(get_db)):
    return db.query(DBRSSFeedSource).all()

@rss_management_router.post("/rss-feeds", response_model=RSSFeedSourcePublic, status_code=201)
async def create_rss_feed(feed_data: RSSFeedSourceCreate, db: Session = Depends(get_db)):
    new_feed = DBRSSFeedSource(**feed_data.model_dump())
    db.add(new_feed)
    db.commit()
    db.refresh(new_feed)
    return new_feed

@rss_management_router.put("/rss-feeds/{feed_id}", response_model=RSSFeedSourcePublic)
async def update_rss_feed(feed_id: int, feed_data: RSSFeedSourceCreate, db: Session = Depends(get_db)):
    feed = db.query(DBRSSFeedSource).filter(DBRSSFeedSource.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    
    update_data = feed_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(feed, key, value)
    
    db.commit()
    db.refresh(feed)
    return feed

@rss_management_router.delete("/rss-feeds/{feed_id}", status_code=204)
async def delete_rss_feed(feed_id: int, db: Session = Depends(get_db)):
    feed = db.query(DBRSSFeedSource).filter(DBRSSFeedSource.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    db.delete(feed)
    db.commit()