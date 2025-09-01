import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from backend.db.base import PostVisibility
from .user import AuthorPublic

class PostBase(BaseModel):
    content: str = Field(..., max_length=10000)
    visibility: PostVisibility = PostVisibility.public

class PostCreate(PostBase):
    media: Optional[List[Dict[str, Any]]] = None

class PostUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=10000)
    visibility: Optional[PostVisibility] = None

class CommentBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class CommentCreate(CommentBase):
    pass

class CommentPublic(CommentBase):
    id: int
    author: AuthorPublic
    created_at: datetime.datetime
    class Config:
        from_attributes = True

class PostPublic(PostBase):
    id: int
    author: AuthorPublic
    media: Optional[List[Dict[str, Any]]] = None
    visibility: PostVisibility
    created_at: datetime.datetime
    updated_at: datetime.datetime
    comments: List[CommentPublic] = []
    
    like_count: int = 0
    has_liked: bool = False
    
    class Config:
        from_attributes = True