# [UPDATE] backend/tasks/social_tasks.py
import re
import datetime
import json
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload, contains_eager
from sqlalchemy import or_, and_, desc, func, update, select, exists

from backend.db import get_db, session as db_session_module
from backend.db.models.user import User as DBUser
from backend.db.models.social import Post as DBPost, PostLike as DBPostLike, Comment as DBComment
from backend.db.models.config import GlobalConfig 
from backend.db.models.config import LLMBinding as DBLLMBinding
from backend.db.base import PostVisibility
from backend.db.models.dm import DirectMessage, Conversation, ConversationMember
from backend.models.social import PostCreate, PostPublic, CommentCreate, CommentPublic, PostUpdate, AuthorPublic
from backend.models import UserAuthDetails
from backend.session import get_current_db_user_from_token, build_lollms_client_from_params, get_safe_store_instance
from backend.task_manager import task_manager
from backend.ws_manager import manager
from lollms_client import LollmsClient
from ascii_colors import trace_exception, ASCIIColors

from backend.db.models.personality import Personality as DBPersonality
from backend.settings import settings
from backend.task_manager import Task

# safe_store is needed for RAG
try:
    import safe_store
except ImportError:
    safe_store = None

def _send_moderation_dm(db: Session, bot_user: DBUser, target_user_id: int, content_snippet: str, reason: str):
    try:
        # Find existing 1-on-1 conversation between bot and target
        # We look for a conversation where target is a member, AND bot is a member, AND is_group is False
        conv = db.query(Conversation).join(ConversationMember, Conversation.id == ConversationMember.conversation_id)\
            .filter(ConversationMember.user_id == target_user_id)\
            .filter(exists().where(and_(
                ConversationMember.conversation_id == Conversation.id,
                ConversationMember.user_id == bot_user.id
            )))\
            .filter(Conversation.is_group == False)\
            .first()
            
        if not conv:
            conv = Conversation(is_group=False)
            db.add(conv)
            db.commit()
            db.refresh(conv)
            
            m1 = ConversationMember(conversation_id=conv.id, user_id=bot_user.id)
            m2 = ConversationMember(conversation_id=conv.id, user_id=target_user_id)
            db.add_all([m1, m2])
            db.commit()
    
        msg_content = f"Your content was flagged by the moderation system.\n\nReason: {reason}\n\nContent: \"{content_snippet}...\""
        
        dm = DirectMessage(
            sender_id=bot_user.id,
            conversation_id=conv.id,
            content=msg_content,
            sent_at=datetime.datetime.utcnow()
        )
        db.add(dm)
        db.commit()
        db.refresh(dm)
        
        # Notify via WS
        payload = {
            "type": "new_dm",
            "data": {
                "id": dm.id,
                "sender_id": bot_user.id,
                "receiver_id": target_user_id,
                "conversation_id": conv.id,
                "content": dm.content,
                "sent_at": dm.sent_at.isoformat(),
                "sender_username": bot_user.username,
                "sender_icon": bot_user.icon,
                "is_group": False
            }
        }
        manager.send_personal_message_sync(payload, target_user_id)
        
    except Exception as e:
        print(f"Error sending moderation DM to user {target_user_id}: {e}")
        trace_exception(e)

def _moderate_content_task(task: Task, content_type: str, content_id: int):
    """
    Task to check a post or comment against moderation criteria.
    """
    task.log(f"Starting moderation task for {content_type} ID: {content_id}")

    # Ensure settings are refreshed
    with task.db_session_factory() as db:
        settings.refresh(db)
        is_enabled = settings.get("ai_bot_moderation_enabled", False)
        task.log(f"Moderation Enabled Status: {is_enabled}")
    
    if not is_enabled:
        task.log("Moderation disabled. Skipping.", "INFO")
        return

    db = next(get_db())
    try:
        # 1. Fetch content
        content_text = ""
        author_id = None
        content_obj = None
        
        if content_type == 'post':
            content_obj = db.query(DBPost).filter(DBPost.id == content_id).first()
        elif content_type == 'comment':
            content_obj = db.query(DBComment).filter(DBComment.id == content_id).first()
            
        if not content_obj:
            task.log(f"{content_type} {content_id} not found.", "WARNING")
            return

        content_text = content_obj.content
        author_id = content_obj.author_id
        
        # Don't moderate the bot itself
        lollms_bot_user = db.query(DBUser).filter(DBUser.username == 'lollms').first()
        if lollms_bot_user and author_id == lollms_bot_user.id:
            task.log("Author is bot. Validating immediately.")
            content_obj.moderation_status = "validated"
            db.commit()
            return

        # 2. Check Criteria
        criteria = settings.get("ai_bot_moderation_criteria", "Be polite and respectful. No hate speech, spam, or explicit content.")
        task.log(f"Moderation Criteria: {criteria}")
        
        try:
            task.log("Initializing LLM client for moderation...")
            lc = build_lollms_client_from_params(username='lollms')
        except Exception as e:
             task.log(f"Failed to initialize LLM client for moderation: {e}", "ERROR")
             trace_exception(e)
             return

        prompt = f"""You are a strict content moderator AI.
[MODERATION CRITERIA]
{criteria}

[TEXT TO ANALYZE]
"{content_text}"

[INSTRUCTION]
Analyze the text carefully against the criteria.
1. If the text violates ANY of the criteria, output: [[VIOLATION]] followed by a short, polite explanation for the user.
2. If the text is compliant, output: [[SAFE]]
"""
        task.log(f"Sending prompt to LLM (Length: {len(content_text)} chars)...")
        
        try:
            response = lc.generate_text(prompt, max_new_tokens=100, temperature=0.0).strip()
            task.log(f"LLM Response: '{response}'")
            
            if "[[VIOLATION]]" in response:
                reason = response.replace("[[VIOLATION]]", "").strip()
                if not reason: reason = "Content violates community guidelines."
                
                task.log(f"VIOLATION detected for {content_type} {content_id}. Reason: {reason}", "WARNING")
                content_obj.moderation_status = "flagged"
                db.commit()
                
                if lollms_bot_user:
                    _send_moderation_dm(db, lollms_bot_user, author_id, content_text[:50], reason)
                    task.log("Sent DM notification to user.")
                    
            elif "[[SAFE]]" in response:
                content_obj.moderation_status = "validated"
                db.commit()
                task.log("Content validated as SAFE.", "INFO")
            else:
                # Fallback check for raw response text
                normalized_response = response.lower()
                if "violation" in normalized_response or "unsafe" in normalized_response:
                    task.log(f"Heuristic violation detected. Response: {response}", "WARNING")
                    content_obj.moderation_status = "flagged"
                    db.commit()
                elif "safe" in normalized_response:
                    task.log(f"Heuristic safe detected. Response: {response}", "INFO")
                    content_obj.moderation_status = "validated"
                    db.commit()
                else:
                    task.log(f"Ambiguous response from LLM. Leaving as pending. Response: {response}", "WARNING")

        except Exception as e:
            task.log(f"Error during LLM generation: {e}", "ERROR")
            trace_exception(e)

    except Exception as e:
        task.log(f"Moderation task error: {e}", "ERROR")
        trace_exception(e)
    finally:
        db.close()

def _batch_moderate_content_task(task: Task):
    """
    Task to moderate all old posts/comments that are pending moderation.
    """
    with task.db_session_factory() as db:
        settings.refresh(db)
        if not settings.get("ai_bot_moderation_enabled", False):
            task.log("Moderation disabled. Aborting batch.", "WARNING")
            return
        
    task.log("Starting batch moderation...")
    db = next(get_db())
    
    try:
        pending_posts = db.query(DBPost).filter(or_(DBPost.moderation_status == "pending", DBPost.moderation_status == None)).all()
        pending_comments = db.query(DBComment).filter(or_(DBComment.moderation_status == "pending", DBComment.moderation_status == None)).all()
        
        total = len(pending_posts) + len(pending_comments)
        task.log(f"Found {total} items to moderate.")
        
        _run_moderation_loop(task, db, pending_posts + pending_comments, total)
        
    except Exception as e:
        task.log(f"Batch moderation error: {e}", "ERROR")
        trace_exception(e)
    finally:
        db.close()

def _full_remoderation_task(task: Task):
    """
    Task to force re-moderation on ALL posts and comments in the system.
    """
    with task.db_session_factory() as db:
        settings.refresh(db)
        if not settings.get("ai_bot_moderation_enabled", False):
            task.log("Moderation disabled. Aborting full revision.", "WARNING")
            return
            
    task.log("Starting FULL CONTENT REVISION...")
    db = next(get_db())
    try:
        all_posts = db.query(DBPost).all()
        all_comments = db.query(DBComment).all()
        
        total = len(all_posts) + len(all_comments)
        task.log(f"Found {total} total items (posts + comments) to re-evaluate.")
        
        _run_moderation_loop(task, db, all_posts + all_comments, total)
        
    except Exception as e:
        task.log(f"Full revision error: {e}", "ERROR")
        trace_exception(e)
    finally:
        db.close()

def _run_moderation_loop(task, db, items, total_count):
    """
    Shared logic for iterating over a list of content items and moderating them.
    """
    lollms_bot_user = db.query(DBUser).filter(DBUser.username == 'lollms').first()
    criteria = settings.get("ai_bot_moderation_criteria", "")
    task.log(f"Criteria: {criteria}")

    try:
        lc = build_lollms_client_from_params(username='lollms')
    except Exception as e:
            task.log(f"Failed to init LLM: {e}", "ERROR")
            return

    processed = 0
    
    for item in items:
        if task.cancellation_event.is_set(): 
            task.log("Moderation task cancelled.")
            break
        
        # Skip bot's own content
        if lollms_bot_user and item.author_id == lollms_bot_user.id:
            if item.moderation_status != "validated":
                item.moderation_status = "validated"
                processed += 1
            continue

        prompt = f"""You are a strict content moderator AI.
[MODERATION CRITERIA]
{criteria}

[CONTENT]
"{item.content}"

[INSTRUCTION]
1. If content violates criteria, output: [[VIOLATION]] followed by a short explanation.
2. If content is compliant, output: [[SAFE]]
"""
        try:
            # task.log(f"Checking item {item.id}...")
            response = lc.generate_text(prompt, max_new_tokens=100, temperature=0.0).strip()
            # task.log(f"Response: {response}")

            if "[[VIOLATION]]" in response:
                reason = response.replace("[[VIOLATION]]", "").strip()
                if not reason: reason = "Violated community guidelines."
                
                if item.moderation_status != "flagged":
                    item.moderation_status = "flagged"
                    task.log(f"Flagged item {item.id}. Reason: {reason}", "WARNING")
                    if lollms_bot_user:
                        _send_moderation_dm(db, lollms_bot_user, item.author_id, item.content[:50], reason)

            elif "[[SAFE]]" in response:
                if item.moderation_status != "validated":
                    item.moderation_status = "validated"
            else:
                # Fallback
                if "violation" in response.lower():
                    item.moderation_status = "flagged"
                elif "safe" in response.lower():
                    item.moderation_status = "validated"
                else:
                    task.log(f"Ambiguous: {response}")
            
            processed += 1
            if processed % 10 == 0:
                db.commit()
                if total_count > 0:
                    task.set_progress(int((processed/total_count)*100))
        except Exception as e:
            task.log(f"Error processing item {item.id}: {e}", "ERROR")
    
    db.commit()
    task.log(f"Moderation run complete. Processed {processed}/{total_count}.", "SUCCESS")
    task.set_progress(100)

def _respond_to_mention_task(task: Task, mention_type: str, item_id: int):
    """
    A background task to generate and post a reply from the @lollms bot.
    """
    task.log(f"Starting AI response task for {mention_type} ID: {item_id}")
    db = next(get_db())
    try:
        lollms_bot_user = db.query(DBUser).filter(DBUser.username == 'lollms').first()
        if not lollms_bot_user:
            task.log("CRITICAL: @lollms user not found.", "ERROR")
            return

        settings.refresh(db)
        if not settings.get("ai_bot_enabled", False):
            task.log("AI Bot disabled.", "INFO")
            return

        # 2. Build Context
        post_id = None
        thread_context = ""
        context_instruction = ""
        
        post = None
        if mention_type == 'post':
            post = db.query(DBPost).options(joinedload(DBPost.author)).filter(DBPost.id == item_id).first()
            if not post: return
            post_id = post.id
            thread_context = f"[Post] {post.author.username}: {post.content}"
            context_instruction = "You were mentioned in this post."
        elif mention_type == 'comment':
            triggering_comment = db.query(DBComment).options(joinedload(DBComment.author)).filter(DBComment.id == item_id).first()
            if not triggering_comment: return
            post_id = triggering_comment.post_id
            post = db.query(DBPost).options(joinedload(DBPost.author)).filter(DBPost.id == post_id).first()
            comments = db.query(DBComment).options(joinedload(DBComment.author)).filter(DBComment.post_id == post_id).order_by(DBComment.created_at.asc()).all()
            thread_context = f"[Post] {post.author.username}: {post.content}\n"
            for c in comments:
                thread_context += f"[Comment] {c.author.username}: {c.content}\n"
            context_instruction = f"A new comment was added by {triggering_comment.author.username}."

        task.set_progress(20)
        task.log("Generating response...")
        lc = build_lollms_client_from_params(username=lollms_bot_user.username)
        
        base_system_prompt = settings.get("ai_bot_system_prompt") or "You are @lollms, a helpful AI assistant."
        if lollms_bot_user.active_personality_id:
            personality = db.query(DBPersonality).filter(DBPersonality.id == lollms_bot_user.active_personality_id).first()
            if personality: base_system_prompt = personality.prompt_text
        
        augmented_prompt = (
            f"{base_system_prompt}\n\n"
            "## Task\n"
            "Decide on the best action:\n"
            "1. **Reply** to the thread.\n"
            "2. **Create a new post** if topic warrants it.\n"
            "3. **Ignore** if no response needed.\n\n"
            "## Output Format\n"
            "Start with:\n"
            "- [[REPLY]] <content>\n"
            "- [[POST]] <content>\n"
            "- [[IGNORE]]\n"
        )

        full_user_input = f"{context_instruction}\n\n[THREAD HISTORY]:\n{thread_context}\n\n[INSTRUCTION]: Generate your response starting with [[REPLY]], [[POST]], or [[IGNORE]]."
        
        response_text = lc.generate_text(full_user_input, system_prompt=augmented_prompt, stream=False, max_new_tokens=512)
        clean_response = response_text.strip()
        
        if "[[IGNORE]]" in clean_response:
            task.log("AI decided to ignore.", "INFO")
            task.set_progress(100)
            return {"status": "ignored"}

        is_new_post = "[[POST]]" in clean_response
        final_content = clean_response.replace("[[POST]]", "").replace("[[REPLY]]", "").strip()

        if not final_content:
            task.log("AI generated empty content.", "WARNING")
            return {"status": "aborted"}

        task.log(f"AI Response ({'New Post' if is_new_post else 'Reply'}): {final_content[:100]}...")
        task.set_progress(80)

        if is_new_post:
            new_db_post = DBPost(
                author_id=lollms_bot_user.id,
                content=final_content[:5000],
                visibility=PostVisibility.public,
                group_id=post.group_id if post and post.group_id else None
            )
            db.add(new_db_post)
            db.commit()
            db.refresh(new_db_post)
            
            from backend.routers.social import get_post_public
            post_public = get_post_public(db, new_db_post, lollms_bot_user.id)
            manager.broadcast_sync({"type": "new_post", "data": post_public.model_dump(mode="json")})
            task.log(f"Created new post ID: {new_db_post.id}")
        else:
            new_comment = DBComment(
                post_id=post_id,
                author_id=lollms_bot_user.id,
                content=final_content[:2000]
            )
            db.add(new_comment)
            db.commit()
            db.refresh(new_comment, ['author'])
            
            comment_public = CommentPublic(
                id=new_comment.id,
                content=new_comment.content,
                created_at=new_comment.created_at,
                author=AuthorPublic.from_orm(new_comment.author)
            )
            manager.broadcast_sync({
                "type": "new_comment",
                "data": {"post_id": post_id, "comment": comment_public.model_dump(mode="json")}
            })
            task.log(f"Bot commented on post ID: {post_id}")

    except Exception as e:
        task.log(f"Error in AI response task: {e}", "CRITICAL")
        trace_exception(e)
        if db: db.rollback()
    finally:
        if db: db.close()

def _generate_feed_post_task(task: Task, force: bool = False):
    """
    Scheduled task to generate a new post for the bot.
    """
    if force: task.log("Manual Post Triggered.")
    else: task.log("Checking AI Bot Auto-Posting Schedule...")
        
    db = next(get_db())
    try:
        settings.refresh(db)
        if not force and not settings.get("ai_bot_auto_post", False):
            task.log("Auto-posting is disabled.", "INFO")
            return

        if not force:
            last_posted_str = settings.get("ai_bot_last_posted_at")
            interval_hours = float(settings.get("ai_bot_post_interval", 24))
            if last_posted_str:
                try:
                    last_posted = datetime.datetime.fromisoformat(last_posted_str)
                    time_diff = datetime.datetime.utcnow() - last_posted
                    if time_diff.total_seconds() < interval_hours * 3600:
                        task.log(f"Not enough time elapsed.", "INFO")
                        return
                except ValueError: pass

        bot_user = db.query(DBUser).filter(DBUser.username == 'lollms').first()
        if not bot_user:
            task.log("@lollms user not found!", "ERROR")
            return

        mode = settings.get("ai_bot_content_mode", "static_text")
        context_material = ""
        user_prompt = settings.get("ai_bot_generation_prompt", "Generate an engaging social media post.")
        
        if mode == "static_text":
             context_material = settings.get("ai_bot_static_content", "")
        # ... (other modes omitted for brevity) ...

        task.log("Generating post content...")
        lc = build_lollms_client_from_params(username=bot_user.username)
        system_prompt = settings.get("ai_bot_system_prompt") or "You are a helpful AI assistant."
        
        full_prompt = f"{user_prompt}\n\n[CONTEXT MATERIAL]:\n{context_material[:10000]}"
        generated_content = lc.generate_text(full_prompt, system_prompt=system_prompt, max_new_tokens=1024)

        if not generated_content or len(generated_content.strip()) < 5:
            task.log("Generated content was empty.", "WARNING")
            return

        new_post = DBPost(
            author_id=bot_user.id,
            content=generated_content.strip(),
            visibility=PostVisibility.public
        )
        db.add(new_post)
        
        now_iso = datetime.datetime.utcnow().isoformat()
        # Update last posted time in DB
        config_entry = db.query(GlobalConfig).filter(GlobalConfig.key == "ai_bot_last_posted_at").first()
        if config_entry: config_entry.value = now_iso
        else: db.add(GlobalConfig(key="ai_bot_last_posted_at", value=now_iso, type="string", category="AI Bot"))
        
        db.commit()
        db.refresh(new_post)
        
        from backend.routers.social import get_post_public
        post_public = get_post_public(db, new_post, bot_user.id)
        manager.broadcast_sync({"type": "new_post", "data": post_public.model_dump(mode="json")})
        
        settings._settings_cache["ai_bot_last_posted_at"] = now_iso
        task.log(f"Successfully posted. ID: {new_post.id}", "SUCCESS")

    except Exception as e:
        task.log(f"Error in auto-posting task: {e}", "ERROR")
        trace_exception(e)
    finally:
        db.close()
