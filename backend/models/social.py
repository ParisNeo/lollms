import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.db.base import PostVisibility
from .user import AuthorPublic

class PostBase(BaseModel):
    content: str
    visibility: PostVisibility = PostVisibility.public
    is_pinned: bool = False

class PostCreate(PostBase):
    content: str = Field(..., max_length=50000)
    media: Optional[List[Dict[str, Any]]] = None
    is_pinned: Optional[bool] = False

class PostUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=50000)
    visibility: Optional[PostVisibility] = None
    is_pinned: Optional[bool] = None

class CommentBase(BaseModel):
    content: str

class CommentCreate(CommentBase):
    content: str = Field(..., min_length=1, max_length=10000)

class CommentPublic(CommentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    author: AuthorPublic
    created_at: datetime.datetime
    is_ai_generated: bool = False

class PostPublic(PostBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    author: AuthorPublic
    media: Optional[List[Dict[str, Any]]] = None
    visibility: PostVisibility
    is_pinned: bool = False
    is_ai_generated: bool = False
    created_at: datetime.datetime
    updated_at: datetime.datetime
    comments: List[CommentPublic] = []
    like_count: int = 0
    has_liked: bool = False

class GeneratePostDraftRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=2000, description="The topic, brief, or request for the post.")
    use_websearch: bool = Field(default=False, description="Whether to fetch real-time web search information to back the post.")
    search_provider: Optional[str] = Field(default="ddg", description="Search provider: 'ddg', 'google', or 'arxiv'")
    tone: Optional[str] = Field(default="engaging", description="Tone of the post: 'engaging', 'informative', 'humorous', 'technical', or 'concise'")
    include_hashtags: bool = Field(default=True, description="Whether to include relevant hashtags.")

class GeneratePostDraftResponse(BaseModel):
    content: str
    sources: Optional[List[str]] = Field(default_factory=list)
    tools_used: Optional[List[str]] = Field(default_factory=list)