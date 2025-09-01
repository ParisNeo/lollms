# backend/routers/social.py
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload, contains_eager
from sqlalchemy import or_, and_, desc, func

from backend.db import get_db, session as db_session_module
from backend.db.models.user import User as DBUser, follows_table
from backend.db.models.social import Post as DBPost, PostLike as DBPostLike, Comment as DBComment
from backend.db.base import PostVisibility
from backend.models import UserAuthDetails, PostCreate, PostPublic, CommentCreate, CommentPublic, PostUpdate
from backend.session import get_current_db_user_from_token
from backend.task_manager import task_manager
from backend.tasks.social_tasks import _handle_lollms_mention_task

social_router = APIRouter(prefix="/api/social", tags=["Social"])

def get_post_public(db: Session, db_post: DBPost, current_user_id: int) -> PostPublic:
    like_count = db.query(func.count(DBPostLike.user_id)).filter(DBPostLike.post_id == db_post.id).scalar() or 0
    has_liked = db.query(DBPostLike).filter(DBPostLike.post_id == db_post.id, DBPostLike.user_id == current_user_id).first() is not None
    
    return PostPublic(
        id=db_post.id,
        author_id=db_post.author_id,
        content=db_post.content,
        media=db_post.media,
        visibility=db_post.visibility,
        created_at=db_post.created_at,
        updated_at=db_post.updated_at,
        author=db_post.author,
        comments=[c for c in db_post.comments],
        like_count=like_count,
        has_liked=has_liked
    )

@social_router.get("/feed", response_model=List[PostPublic])
def get_main_feed(
    skip: int = 0, limit: int = 20,
    current_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    following_ids = [u.id for u in current_user.following]
    
    # Base query for posts visible to the current user
    query = db.query(DBPost).options(
        joinedload(DBPost.author),
        joinedload(DBPost.comments).joinedload(DBComment.author)
    ).filter(
        DBPost.author_id != current_user.id,
        or_(
            DBPost.visibility == PostVisibility.public,
            and_(DBPost.visibility == PostVisibility.followers, DBPost.author_id.in_(following_ids))
        )
    ).order_by(desc(DBPost.created_at)).offset(skip).limit(limit)
    
    posts_db = query.all()
    
    return [get_post_public(db, post, current_user.id) for post in posts_db]

@social_router.post("/posts", response_model=PostPublic, status_code=status.HTTP_201_CREATED)
def create_new_post(
    post_data: PostCreate,
    current_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    new_post = DBPost(
        author_id=current_user.id,
        content=post_data.content,
        visibility=post_data.visibility,
        media=post_data.media
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)

    # --- MENTION HANDLING ---
    if '@lollms' in post_data.content.lower():
        task_manager.submit_task(
            name=f"Replying to mention in post {new_post.id}",
            target=_handle_lollms_mention_task,
            args=(new_post.id, current_user.username, post_data.content, db_session_module.SessionLocal),
            owner_username=current_user.username 
        )

    return get_post_public(db, new_post, current_user.id)

@social_router.post("/posts/{post_id}/comments", response_model=CommentPublic, status_code=status.HTTP_201_CREATED)
def add_comment_to_post(
    post_id: int,
    comment_data: CommentCreate,
    current_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    post = db.query(DBPost).filter(DBPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    new_comment = DBComment(
        post_id=post_id,
        author_id=current_user.id,
        content=comment_data.content
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    
    # --- MENTION HANDLING ---
    if '@lollms' in comment_data.content.lower():
        task_manager.submit_task(
            name=f"Replying to mention in comment on post {post_id}",
            target=_handle_lollms_mention_task,
            args=(post_id, current_user.username, comment_data.content, db_session_module.SessionLocal, new_comment.id),
            owner_username=current_user.username
        )

    return new_comment


@social_router.post("/posts/{post_id}/like", response_model=PostPublic)
def like_a_post(
    post_id: int,
    current_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    post = db.query(DBPost).options(joinedload(DBPost.author), joinedload(DBPost.comments)).filter(DBPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    existing_like = db.query(DBPostLike).filter_by(user_id=current_user.id, post_id=post_id).first()
    if not existing_like:
        new_like = DBPostLike(user_id=current_user.id, post_id=post_id)
        db.add(new_like)
        db.commit()
        
    return get_post_public(db, post, current_user.id)


@social_router.delete("/posts/{post_id}/like", response_model=PostPublic)
def unlike_a_post(
    post_id: int,
    current_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    post = db.query(DBPost).options(joinedload(DBPost.author), joinedload(DBPost.comments)).filter(DBPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    like_to_delete = db.query(DBPostLike).filter_by(user_id=current_user.id, post_id=post_id).first()
    if like_to_delete:
        db.delete(like_to_delete)
        db.commit()
        
    return get_post_public(db, post, current_user.id)