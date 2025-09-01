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
from sqlalchemy.orm import Session
from lollms_client import LollmsClient
from ascii_colors import trace_exception

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.social import Post as DBPost, Comment as DBComment
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.config import LLMBinding as DBLLMBinding
from backend.settings import settings
from backend.task_manager import Task

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



def generate_ai_bot_response_task(task: Task, post_id: int, original_author_username: str, content_to_reply_to: str):
    """
    A background task to generate and post a reply from the @lollms bot.
    """
    db: Session = next(get_db())
    try:
        task.log("Starting AI Bot response task.")
        
        # 1. Check if bot is enabled
        if not settings.get("ai_bot_enabled"):
            task.log("AI Bot is disabled in settings. Aborting.", level="WARNING")
            return {"status": "aborted", "reason": "Bot disabled"}

        # 2. Get necessary bot configuration
        binding_model = settings.get("ai_bot_binding_model")
        personality_id = settings.get("ai_bot_personality_id")
        system_prompt_setting = settings.get("ai_bot_system_prompt")

        if not binding_model:
            task.log("AI Bot model/binding is not configured. Aborting.", level="ERROR")
            raise ValueError("AI Bot model not configured.")
            
        task.set_progress(10)

        # 3. Get the @lollms user for posting
        lollms_user = db.query(DBUser).filter(DBUser.username == "lollms").first()
        if not lollms_user:
            task.log("The special @lollms user was not found. Aborting.", level="CRITICAL")
            raise ValueError("@lollms user not found.")
            
        task.log(f"Found @lollms user with id: {lollms_user.id}")
        task.set_progress(20)

        # 4. Build a LollmsClient instance for the bot
        binding_alias, model_name = (binding_model.split('/', 1) + [None])[:2]
        binding_db = db.query(DBLLMBinding).filter(DBLLMBinding.alias == binding_alias).first()
        if not binding_db:
            task.log(f"Binding with alias '{binding_alias}' not found. Aborting.", level="CRITICAL")
            raise ValueError(f"Binding '{binding_alias}' not found.")
        
        client_config = {**binding_db.config, "model_name": model_name}
        lc = LollmsClient(llm_binding_name=binding_db.name, llm_binding_config=client_config)
        task.log(f"LollmsClient initialized with binding '{binding_db.name}' and model '{model_name}'.")
        task.set_progress(30)
        
        # 5. Determine the system prompt
        system_prompt = ""
        personality = None
        if personality_id:
            personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
        
        if personality:
            system_prompt = personality.prompt_text
            task.log(f"Using personality '{personality.name}'.")
        else:
            system_prompt = system_prompt_setting
            task.log("Using default system prompt from settings.")
        
        # 6. Construct the final prompt
        final_prompt = (
            f"The user '{original_author_username}' created a post/comment that mentions you. "
            f"Here is the content you need to respond to:\n\n"
            f"--- START OF CONTENT ---\n"
            f"{content_to_reply_to}\n"
            f"--- END OF CONTENT ---\n\n"
            f"Please provide a helpful and concise response as a comment."
        )
        
        task.set_progress(50)
        task.log("Generating response...")
        
        # 7. Generate the response
        response_text = lc.generate_text(
            prompt=final_prompt,
            system_prompt=system_prompt,
            stream=False,
            max_new_tokens=512 # Limit response length
        )
        
        task.log("Response received from LLM.")
        task.set_progress(80)

        # 8. Create and save the comment
        new_comment = DBComment(
            post_id=post_id,
            author_id=lollms_user.id,
            content=response_text
        )
        db.add(new_comment)
        db.commit()

        task.log(f"Successfully posted comment to post ID {post_id}.")
        task.set_progress(100)
        
        return {"status": "success", "comment_id": new_comment.id}

    except Exception as e:
        trace_exception(e)
        task.log(f"An error occurred: {str(e)}", level="ERROR")
        db.rollback()
        raise e
    finally:
        db.close()