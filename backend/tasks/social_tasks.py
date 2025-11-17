# backend/tasks/social_tasks.py
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload, contains_eager
from sqlalchemy import or_, and_, desc, func

from backend.db import get_db, session as db_session_module
from backend.db.models.user import User as DBUser
from backend.db.models.social import Post as DBPost, PostLike as DBPostLike, Comment as DBComment
from backend.db.base import PostVisibility
from backend.models.social import PostCreate, PostPublic, CommentCreate, CommentPublic, PostUpdate, AuthorPublic
from backend.models import UserAuthDetails
from backend.session import get_current_db_user_from_token, build_lollms_client_from_params
from backend.task_manager import task_manager
from backend.ws_manager import manager
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

def _respond_to_mention_task(task: Task, mention_type: str, item_id: int):
    """
    A background task to generate and post a reply from the @lollms bot.
    """
    task.log(f"Starting AI response task for {mention_type} ID: {item_id}")
    db = next(get_db())
    try:
        # 1. Fetch the @lollms bot user and its configuration
        lollms_bot_user = db.query(DBUser).filter(DBUser.username == 'lollms').first()
        if not lollms_bot_user:
            task.log("CRITICAL: @lollms user not found in the database.", "ERROR")
            raise Exception("@lollms user does not exist.")

        ai_bot_enabled = settings.get("ai_bot_enabled", False)
        if not ai_bot_enabled:
            task.log("AI Bot is disabled in settings. Aborting.", "WARNING")
            return {"status": "aborted", "reason": "AI Bot is disabled."}
            
        if not lollms_bot_user.lollms_model_name:
            task.log("CRITICAL: No model is configured for the AI Bot in the admin panel.", "ERROR")
            raise Exception("AI Bot model not configured.")

        task.log(f"Bot enabled, using model: {lollms_bot_user.lollms_model_name}")

        # 2. Fetch the content that triggered the mention
        post_id = None
        context_text = ""
        if mention_type == 'post':
            post = db.query(DBPost).options(joinedload(DBPost.author)).filter(DBPost.id == item_id).first()
            if not post:
                raise Exception(f"Post with ID {item_id} not found.")
            post_id = post.id
            context_text = f"User '{post.author.username}' wrote a post: {post.content}"
        elif mention_type == 'comment':
            comment = db.query(DBComment).options(joinedload(DBComment.author)).filter(DBComment.id == item_id).first()
            if not comment:
                raise Exception(f"Comment with ID {item_id} not found.")
            post_id = comment.post_id
            context_text = f"In response to a post, user '{comment.author.username}' commented: {comment.content}"
        else:
            raise ValueError(f"Invalid mention type: {mention_type}")

        task.set_progress(20)

        # 3. Generate the response
        task.log("Generating AI response...")
        
        lc = build_lollms_client_from_params(username=lollms_bot_user.username)
        
        # Determine system prompt: personality first, then global setting
        system_prompt = ""
        if lollms_bot_user.active_personality_id:
            personality = db.query(DBPersonality).filter(DBPersonality.id == lollms_bot_user.active_personality_id).first()
            if personality:
                system_prompt = personality.prompt_text
                task.log(f"Using personality: '{personality.name}'")
        
        if not system_prompt:
            system_prompt = settings.get("ai_bot_system_prompt")
            task.log("Using global default system prompt.")
        
        response_text = lc.generate_text(
            context_text, 
            system_prompt=system_prompt + "\n**Important:** You are commenting on the user's post. Your response must not exceed 2000 characters.", 
            stream=False,
            max_new_tokens=512
        )
        
        if not response_text or not response_text.strip():
            task.log("AI generated an empty response. Aborting.", "WARNING")
            return {"status": "aborted", "reason": "Empty response from AI."}

        task.log(f"AI Response: {response_text[:100]}...")
        task.set_progress(80)

        # 4. Create and save the new comment from the bot
        new_comment = DBComment(
            post_id=post_id,
            author_id=lollms_bot_user.id,
            content=response_text.strip()[:2000] # Enforce character limit
        )
        db.add(new_comment)
        db.commit()
        db.refresh(new_comment, ['author'])
        task.log(f"Bot comment created with ID: {new_comment.id}")

        # 5. Broadcast the new comment to all clients
        comment_public = CommentPublic(
            id=new_comment.id,
            content=new_comment.content,
            created_at=new_comment.created_at,
            author=AuthorPublic.from_orm(new_comment.author)
        )

        payload = {
            "type": "new_comment",
            "data": {
                "post_id": post_id,
                "comment": comment_public.model_dump(mode="json")
            }
        }
        
        manager.broadcast_sync(payload)
        task.log("Broadcasted new comment to clients.")
        task.set_progress(100)
        
        return {"status": "success", "comment_id": new_comment.id}

    except Exception as e:
        task.log(f"An error occurred in the AI response task: {e}", "CRITICAL")
        trace_exception(e)
        if db:
            db.rollback()
        raise e
    finally:
        if db:
            db.close()
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
    group_ids = [g.id for g in current_user.groups]
    
    # Base query for posts visible to the current user
    query = db.query(DBPost).options(
        joinedload(DBPost.author),
        joinedload(DBPost.comments).joinedload(DBComment.author)
    ).filter(
        DBPost.author_id != current_user.id,
        or_(
            DBPost.visibility == PostVisibility.public,
            and_(DBPost.visibility == PostVisibility.followers, DBPost.author_id.in_(following_ids)),
            and_(DBPost.visibility == PostVisibility.group, DBPost.group_id.in_(group_ids))
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
    if post_data.visibility == PostVisibility.group:
        if not post_data.group_id:
            raise HTTPException(status_code=400, detail="A group ID is required for group posts.")
        # Verify user is a member of the group
        if not any(g.id == post_data.group_id for g in current_user.groups):
            raise HTTPException(status_code=403, detail="You are not a member of this group.")

    new_post = DBPost(
        author_id=current_user.id,
        content=post_data.content,
        visibility=post_data.visibility,
        media=post_data.media,
        group_id=post_data.group_id if post_data.visibility == PostVisibility.group else None
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)

    # --- MENTION HANDLING ---
    if '@lollms' in post_data.content.lower():
        task_manager.submit_task(
            name=f"Replying to mention in post {new_post.id}",
            target=_respond_to_mention_task,
            args=('post', new_post.id),
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
            target=_respond_to_mention_task,
            args=('comment', new_comment.id),
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
