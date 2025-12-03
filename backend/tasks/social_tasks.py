# backend/tasks/social_tasks.py
import re
import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload, contains_eager
from sqlalchemy import or_, and_, desc, func, update

from backend.db import get_db, session as db_session_module
from backend.db.models.user import User as DBUser
from backend.db.models.social import Post as DBPost, PostLike as DBPostLike, Comment as DBComment
from backend.db.models.config import GlobalConfig 
from backend.db.base import PostVisibility
from backend.models.social import PostCreate, PostPublic, CommentCreate, CommentPublic, PostUpdate, AuthorPublic
from backend.models import UserAuthDetails
from backend.session import get_current_db_user_from_token, build_lollms_client_from_params
from backend.task_manager import task_manager
from backend.ws_manager import manager
from sqlalchemy.orm import Session
from lollms_client import LollmsClient
from ascii_colors import trace_exception, ASCIIColors

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
    Supports smart decision making (reply or ignore).
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
             task.log("AI Bot model not explicitly configured. Attempting to use system default.", "INFO")

        # 2. Build Context (Thread History)
        post_id = None
        thread_context = ""
        context_instruction = ""
        
        if mention_type == 'post':
            post = db.query(DBPost).options(joinedload(DBPost.author)).filter(DBPost.id == item_id).first()
            if not post:
                raise Exception(f"Post with ID {item_id} not found.")
            post_id = post.id
            thread_context = f"[Post] {post.author.username}: {post.content}"
            context_instruction = "You were mentioned in this post."
            
        elif mention_type == 'comment':
            triggering_comment = db.query(DBComment).options(joinedload(DBComment.author)).filter(DBComment.id == item_id).first()
            if not triggering_comment:
                raise Exception(f"Comment with ID {item_id} not found.")
            
            post_id = triggering_comment.post_id
            post = db.query(DBPost).options(joinedload(DBPost.author)).filter(DBPost.id == post_id).first()
            
            # Fetch last N comments for context
            comments = db.query(DBComment).options(joinedload(DBComment.author)).filter(DBComment.post_id == post_id).order_by(DBComment.created_at.asc()).all()
            
            thread_context = f"[Post] {post.author.username}: {post.content}\n"
            for c in comments:
                thread_context += f"[Comment] {c.author.username}: {c.content}\n"
            
            context_instruction = f"A new comment was added by {triggering_comment.author.username}."

        task.set_progress(20)

        # 3. Generate the response
        task.log("Generating AI response...")
        
        lc = build_lollms_client_from_params(username=lollms_bot_user.username)
        
        # Determine system prompt
        base_system_prompt = settings.get("ai_bot_system_prompt") or "You are @lollms, a helpful AI assistant residing in this social platform."
        if lollms_bot_user.active_personality_id:
            personality = db.query(DBPersonality).filter(DBPersonality.id == lollms_bot_user.active_personality_id).first()
            if personality:
                base_system_prompt = personality.prompt_text
                task.log(f"Using personality: '{personality.name}'")
        
        # Augmented System Prompt for Thread Awareness and Decision Making
        augmented_prompt = (
            f"{base_system_prompt}\n\n"
            "## Task\n"
            "You are observing a social media thread. "
            "You must decide if a response from you is necessary or helpful.\n\n"
            "## Rules\n"
            "1. Respond if you are explicitly mentioned (@lollms).\n"
            "2. Respond if you are the author of the post and the comment is relevant to you.\n"
            "3. Respond if you are part of the conversation and the user is addressing you.\n"
            "4. **IF NO RESPONSE IS NEEDED** (e.g., users talking amongst themselves, spam, or simple acknowledgement not requiring a bot), you MUST output exactly: [[IGNORE]]\n"
            "5. Keep responses concise (under 2000 chars) and relevant.\n"
            "6. Do not reply to yourself."
        )

        full_user_input = f"{context_instruction}\n\n[THREAD HISTORY]:\n{thread_context}\n\n[INSTRUCTION]: Generate your reply or [[IGNORE]]."
        
        response_text = lc.generate_text(
            full_user_input, 
            system_prompt=augmented_prompt, 
            stream=False,
            max_new_tokens=512
        )
        
        clean_response = response_text.strip()
        
        if "[[IGNORE]]" in clean_response:
            task.log("AI decided to ignore this interaction.", "INFO")
            task.set_progress(100)
            return {"status": "ignored"}

        if not clean_response:
            task.log("AI generated an empty response. Aborting.", "WARNING")
            return {"status": "aborted", "reason": "Empty response from AI."}

        task.log(f"AI Response: {clean_response[:100]}...")
        task.set_progress(80)

        # 4. Create and save the new comment from the bot
        new_comment = DBComment(
            post_id=post_id,
            author_id=lollms_bot_user.id,
            content=clean_response[:2000] # Enforce character limit
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

def _generate_feed_post_task(task: Task, force: bool = False):
    """
    Scheduled task to generate a new post for the bot based on configured material.
    """
    if force:
        task.log("Manual Post Triggered. Bypassing schedule/enabled checks.")
    else:
        task.log("Checking AI Bot Auto-Posting Schedule...")
        
    db = next(get_db())
    try:
        # 1. Check if enabled
        if not force and not settings.get("ai_bot_auto_post", False):
            task.log("Auto-posting is disabled in settings.", "INFO")
            return

        # 2. Check Interval
        if not force:
            last_posted_str = settings.get("ai_bot_last_posted_at")
            interval_hours = float(settings.get("ai_bot_post_interval", 24))
            
            if last_posted_str:
                try:
                    last_posted = datetime.datetime.fromisoformat(last_posted_str)
                    # Ensure UTC awareness if needed, but simple subtraction works if both align
                    time_diff = datetime.datetime.utcnow() - last_posted
                    if time_diff.total_seconds() < interval_hours * 3600:
                        task.log(f"Not enough time elapsed. Last posted: {last_posted_str}. Interval: {interval_hours}h.", "INFO")
                        return
                except ValueError:
                    task.log("Invalid date format for last_posted_at. Proceeding with post.", "WARNING")

        # 3. Get Bot User
        bot_user = db.query(DBUser).filter(DBUser.username == 'lollms').first()
        if not bot_user:
            task.log("@lollms user not found!", "ERROR")
            return

        # 4. Get Content Material
        mode = settings.get("ai_bot_content_mode", "static_text")
        context_material = ""
        
        if mode == "file":
            file_path_str = settings.get("ai_bot_file_path", "")
            if file_path_str:
                path = Path(file_path_str)
                if path.exists() and path.is_file():
                    try:
                        context_material = path.read_text(encoding='utf-8')
                        task.log(f"Loaded {len(context_material)} chars from file: {path}")
                    except Exception as e:
                        task.log(f"Error reading file {path}: {e}", "ERROR")
                else:
                    task.log(f"File not found: {path}", "WARNING")
        else:
            context_material = settings.get("ai_bot_static_content", "")
            
        if not context_material or len(context_material.strip()) < 10:
            task.log("No sufficient context material found to generate post.", "WARNING")
            return

        # 5. Generate Post
        task.log("Generating post content...")
        lc = build_lollms_client_from_params(username=bot_user.username)
        
        system_prompt = settings.get("ai_bot_system_prompt") or "You are a helpful AI assistant."
        if bot_user.active_personality_id:
            p = db.query(DBPersonality).filter(DBPersonality.id == bot_user.active_personality_id).first()
            if p: system_prompt = p.prompt_text

        user_prompt = settings.get("ai_bot_generation_prompt", "Generate an engaging social media post based on this information.")
        
        full_prompt = f"{user_prompt}\n\n[CONTEXT MATERIAL]:\n{context_material[:5000]}" # Limit context to avoid overflow

        generated_content = lc.generate_text(
            full_prompt, 
            system_prompt=system_prompt,
            max_new_tokens=1024
        )

        if not generated_content or len(generated_content.strip()) < 5:
            task.log("Generated content was empty.", "WARNING")
            return

        # 6. Post to Feed
        new_post = DBPost(
            author_id=bot_user.id,
            content=generated_content.strip(),
            visibility=PostVisibility.public
        )
        db.add(new_post)
        
        # 7. Update Last Posted Time
        now_iso = datetime.datetime.utcnow().isoformat()
        
        # We need to update the global config in the DB manually as 'settings' is a read wrapper + load
        # Check if config exists
        config_entry = db.query(GlobalConfig).filter(GlobalConfig.key == "ai_bot_last_posted_at").first()
        if config_entry:
            config_entry.value = now_iso
        else:
            # Create if not exists (though usually settings only read what's there, we can insert)
            db.add(GlobalConfig(key="ai_bot_last_posted_at", value=now_iso, type="string", category="AI Bot"))
        
        db.commit()
        db.refresh(new_post) # refresh post to get ID
        
        # 8. Broadcast
        post_public = get_post_public(db, new_post, bot_user.id) # Use bot ID as viewer, doesn't matter for public
        # Ideally we want the public view
        
        payload = {
            "type": "new_post",
            "data": post_public.model_dump(mode="json")
        }
        manager.broadcast_sync(payload)
        
        # Update cache in memory
        settings._settings_cache["ai_bot_last_posted_at"] = now_iso
        
        task.log(f"Successfully posted new bot content. ID: {new_post.id}", "SUCCESS")

    except Exception as e:
        task.log(f"Error in auto-posting task: {e}", "ERROR")
        trace_exception(e)
    finally:
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
