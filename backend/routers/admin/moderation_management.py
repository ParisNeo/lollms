# [UPDATE] backend/routers/admin/moderation_management.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc
from pydantic import BaseModel
import datetime

from backend.db import get_db
from backend.db.models.social import Post as DBPost, Comment as DBComment
from backend.session import get_current_admin_user
from ascii_colors import ASCIIColors

# FIX: Changed prefix from "/api/admin/moderation" to "/moderation"
# The admin_router in __init__.py already provides "/api/admin"
router = APIRouter(
    prefix="/moderation",
    tags=["Admin", "Moderation"],
    dependencies=[Depends(get_current_admin_user)]
)

class AuthorInfo(BaseModel):
    id: int
    username: str
    icon: Optional[str] = None
    class Config:
        from_attributes = True

class ModerationItem(BaseModel):
    id: int
    type: str # 'post' or 'comment'
    content: str
    author: Optional[AuthorInfo] = None
    created_at: Optional[datetime.datetime] = None
    moderation_status: str = "pending"
    flagged_reason: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("/queue", response_model=List[ModerationItem])
async def get_moderation_queue(
    status_filter: Optional[str] = Query(None, regex="^(pending|flagged)$"),
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of posts and comments that require moderation.
    """
    items = []
    
    # --- Fetch Posts ---
    post_query = db.query(DBPost).options(joinedload(DBPost.author))
    if status_filter:
        post_query = post_query.filter(DBPost.moderation_status == status_filter)
    else:
        post_query = post_query.filter(or_(DBPost.moderation_status == 'pending', DBPost.moderation_status == 'flagged'))
    
    posts = post_query.order_by(desc(DBPost.created_at)).limit(limit).all()
    
    for p in posts:
        if not p.id: continue 
        
        author_info = None
        if p.author:
            author_info = AuthorInfo.model_validate(p.author)
        else:
            author_info = AuthorInfo(id=0, username="Unknown User", icon=None)

        items.append(ModerationItem(
            id=p.id,
            type='post',
            content=p.content or "[Empty Content]",
            author=author_info,
            created_at=p.created_at,
            moderation_status=p.moderation_status or "pending"
        ))

    # --- Fetch Comments ---
    comment_query = db.query(DBComment).options(joinedload(DBComment.author))
    if status_filter:
        comment_query = comment_query.filter(DBComment.moderation_status == status_filter)
    else:
        comment_query = comment_query.filter(or_(DBComment.moderation_status == 'pending', DBComment.moderation_status == 'flagged'))
        
    comments = comment_query.order_by(desc(DBComment.created_at)).limit(limit).all()

    for c in comments:
        if not c.id: continue

        author_info = None
        if c.author:
            author_info = AuthorInfo.model_validate(c.author)
        else:
            author_info = AuthorInfo(id=0, username="Unknown User", icon=None)

        items.append(ModerationItem(
            id=c.id,
            type='comment',
            content=c.content or "[Empty Content]",
            author=author_info,
            created_at=c.created_at,
            moderation_status=c.moderation_status or "pending"
        ))

    # Sort combined list by date desc
    items.sort(key=lambda x: x.created_at or datetime.datetime.min, reverse=True)
    
    ASCIIColors.info(f"Moderation Queue: Found {len(items)} items.")
    return items[:limit]

@router.post("/{type}/{id}/approve")
async def approve_content(type: str, id: int, db: Session = Depends(get_db)):
    item = None
    if type == 'post':
        item = db.query(DBPost).filter(DBPost.id == id).first()
    elif type == 'comment':
        item = db.query(DBComment).filter(DBComment.id == id).first()
    else:
        raise HTTPException(status_code=400, detail=f"Invalid content type: {type}")
        
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
        
    item.moderation_status = 'validated'
    db.commit()
    return {"message": "Content approved successfully."}

@router.delete("/{type}/{id}")
async def delete_content(type: str, id: int, db: Session = Depends(get_db)):
    item = None
    if type == 'post':
        item = db.query(DBPost).filter(DBPost.id == id).first()
    elif type == 'comment':
        item = db.query(DBComment).filter(DBComment.id == id).first()
    else:
        raise HTTPException(status_code=400, detail=f"Invalid content type: {type}")
        
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
        
    db.delete(item)
    db.commit()
    return {"message": "Content deleted successfully."}
