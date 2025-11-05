
import datetime
from pydantic import BaseModel
from typing import Optional

class NewsArticlePublic(BaseModel):
    id: int
    title: str
    url: str
    content: str
    fun_fact: str
    publication_date: Optional[datetime.datetime]
    source_id: int

    class Config:
        from_attributes = True

class RSSFeedSourceBase(BaseModel):
    name: str
    url: str
    is_active: bool = True

class RSSFeedSourceCreate(RSSFeedSourceBase):
    pass

class RSSFeedSourcePublic(RSSFeedSourceBase):
    id: int
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime]

    class Config:
        from_attributes = True