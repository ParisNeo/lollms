# [UPDATE] backend/tasks/social_tasks.py
import re
import datetime
import json
import random
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

# Tool Imports
try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

try:
    import arxiv
except ImportError:
    arxiv = None

try:
    from googleapiclient.discovery import build as google_build
except ImportError:
    google_build = None

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    from scrapemaster import ScrapeMaster
except ImportError:
    ScrapeMaster = None

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
    task.log(f"Starting moderation task for {content_type} ID: {content_id}")

    # Ensure settings are refreshed
    with task.db_session_factory() as db:
        settings.refresh(db)
        is_enabled = settings.get("ai_bot_moderation_enabled", False)
    
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
        
        try:
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
        
        try:
            response = lc.generate_text(prompt, max_new_tokens=100, temperature=0.0).strip()
            
            if "[[VIOLATION]]" in response:
                reason = response.replace("[[VIOLATION]]", "").strip()
                if not reason: reason = "Content violates community guidelines."
                
                task.log(f"VIOLATION detected. Reason: {reason}", "WARNING")
                content_obj.moderation_status = "flagged"
                db.commit()
                
                if lollms_bot_user:
                    _send_moderation_dm(db, lollms_bot_user, author_id, content_text[:50], reason)
                    
            elif "[[SAFE]]" in response:
                content_obj.moderation_status = "validated"
                db.commit()
            else:
                # Fallback check for raw response text
                normalized_response = response.lower()
                if "violation" in normalized_response or "unsafe" in normalized_response:
                    content_obj.moderation_status = "flagged"
                    db.commit()
                elif "safe" in normalized_response:
                    content_obj.moderation_status = "validated"
                    db.commit()

        except Exception as e:
            task.log(f"Error during LLM generation: {e}", "ERROR")
            trace_exception(e)

    except Exception as e:
        task.log(f"Moderation task error: {e}", "ERROR")
        trace_exception(e)
    finally:
        db.close()

def _batch_moderate_content_task(task: Task):
    # ... (existing code) ...
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
    # ... (existing code) ...
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
    # ... (existing code) ...
    lollms_bot_user = db.query(DBUser).filter(DBUser.username == 'lollms').first()
    criteria = settings.get("ai_bot_moderation_criteria", "")

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
            response = lc.generate_text(prompt, max_new_tokens=100, temperature=0.0).strip()

            if "[[VIOLATION]]" in response:
                reason = response.replace("[[VIOLATION]]", "").strip()
                if not reason: reason = "Violated community guidelines."
                
                if item.moderation_status != "flagged":
                    item.moderation_status = "flagged"
                    if lollms_bot_user:
                        _send_moderation_dm(db, lollms_bot_user, item.author_id, item.content[:50], reason)

            elif "[[SAFE]]" in response:
                if item.moderation_status != "validated":
                    item.moderation_status = "validated"
            
            processed += 1
            if processed % 10 == 0:
                db.commit()
                if total_count > 0:
                    task.set_progress(int((processed/total_count)*100))
        except Exception as e:
            task.log(f"Error processing item {item.id}: {e}", "ERROR")
    
    db.commit()
    task.set_progress(100)

def _research_and_post_task(task: Task, topic: str, user_instructions: str):
    task.log(f"Starting research task for query: {topic}")
    task.set_progress(5)
    db = next(get_db())
    try:
        settings.refresh(db)
        lollms_bot_user = db.query(DBUser).filter(DBUser.username == 'lollms').first()
        if not lollms_bot_user: return

        # 1. Gather Tools
        enabled_tools = []
        if settings.get("ai_bot_tool_ddg_enabled", False): enabled_tools.append("DuckDuckGo")
        if settings.get("ai_bot_tool_google_enabled", False): enabled_tools.append("Google")
        if settings.get("ai_bot_tool_arxiv_enabled", False): enabled_tools.append("ArXiv")
        if settings.get("ai_bot_tool_scraper_enabled", False): enabled_tools.append("Scraper")
        
        task.log(f"Enabled Tools: {enabled_tools}")
        task.set_progress(10)
        
        # 2. Research
        research_data = []
        lc = build_lollms_client_from_params(username='lollms')
        
        # Calculate progress step for tools
        # 10% to 70% is allocated for tools (60% total)
        total_tools = len(enabled_tools)
        progress_per_tool = 60 / total_tools if total_tools > 0 else 0
        current_progress = 10

        # --- DuckDuckGo ---
        if "DuckDuckGo" in enabled_tools:
            if DDGS:
                try:
                    task.log("Tool: DuckDuckGo - Searching...")
                    with DDGS() as ddgs:
                        results = [r for r in ddgs.text(topic, max_results=5)]
                        if results:
                            formatted_results = [f"Title: {r.get('title')}\nLink: {r.get('href')}\nSnippet: {r.get('body')}" for r in results]
                            research_data.append(f"### DuckDuckGo Search Results for '{topic}':\n" + "\n---\n".join(formatted_results))
                            task.log(f"Tool: DuckDuckGo - Found {len(results)} results.")
                        else:
                            task.log("Tool: DuckDuckGo - No results found.", "WARNING")
                except Exception as e:
                    task.log(f"Tool: DuckDuckGo - Error: {e}", "ERROR")
            else:
                task.log("Tool: DuckDuckGo - Library not available.", "WARNING")
            
            current_progress += progress_per_tool
            task.set_progress(int(current_progress))

        # --- Google ---
        if "Google" in enabled_tools:
            if google_build:
                api_key = settings.get("ai_bot_tool_google_api_key")
                cse_id = settings.get("ai_bot_tool_google_cse_id")
                if api_key and cse_id:
                    try:
                        task.log("Tool: Google Search - Searching...")
                        service = google_build("customsearch", "v1", developerKey=api_key)
                        res = service.cse().list(q=topic, cx=cse_id, num=5).execute()
                        items = res.get('items', [])
                        if items:
                            formatted_items = [f"Title: {item['title']}\nSnippet: {item.get('snippet', '')}\nLink: {item['link']}" for item in items]
                            research_data.append(f"### Google Search Results for '{topic}':\n" + "\n---\n".join(formatted_items))
                            task.log(f"Tool: Google Search - Found {len(items)} results.")
                        else:
                            task.log("Tool: Google Search - No results found.", "WARNING")
                    except Exception as e:
                        task.log(f"Tool: Google Search - Error: {e}", "ERROR")
                else:
                    task.log("Tool: Google Search - Missing API Key or CSE ID.", "WARNING")
            else:
                task.log("Tool: Google Search - Library not available.", "WARNING")

            current_progress += progress_per_tool
            task.set_progress(int(current_progress))

        # --- ArXiv ---
        if "ArXiv" in enabled_tools:
            if arxiv:
                try:
                    task.log("Tool: ArXiv - Searching...")
                    # Construct client to be safe with 2.x API
                    client = arxiv.Client()
                    search = arxiv.Search(query=topic, max_results=5, sort_by=arxiv.SortCriterion.Relevance)
                    results = []
                    for result in client.results(search):
                        results.append(f"Title: {result.title}\nSummary: {result.summary}\nURL: {result.entry_id}")
                    
                    if results:
                        research_data.append(f"### ArXiv Papers for '{topic}':\n" + "\n---\n".join(results))
                        task.log(f"Tool: ArXiv - Found {len(results)} papers.")
                    else:
                        task.log("Tool: ArXiv - No results found.", "WARNING")
                except Exception as e:
                    task.log(f"Tool: ArXiv - Error: {e}", "ERROR")
            else:
                task.log("Tool: ArXiv - Library not available.", "WARNING")

            current_progress += progress_per_tool
            task.set_progress(int(current_progress))

        # --- Scraper ---
        if "Scraper" in enabled_tools:
            if ScrapeMaster:
                urls = re.findall(r'(https?://[^\s]+)', topic + " " + user_instructions)
                if urls:
                    task.log(f"Tool: Scraper - Found {len(urls)} URLs to scrape.")
                    try:
                        scraper = ScrapeMaster()
                        for url in urls[:2]: # Limit scraping
                            task.log(f"Tool: Scraper - Scraping {url}...")
                            try:
                                content = scraper.scrape(url)
                                if content:
                                    research_data.append(f"### Scraped Content from {url}:\n{content[:2000]}...")
                                    task.log(f"Tool: Scraper - Successfully scraped {url}")
                                else:
                                    task.log(f"Tool: Scraper - Empty content from {url}", "WARNING")
                            except Exception as scrape_err:
                                task.log(f"Tool: Scraper - Failed to scrape {url}: {scrape_err}", "WARNING")
                    except Exception as e:
                        task.log(f"Tool: Scraper - Error: {e}", "ERROR")
                else:
                    task.log("Tool: Scraper - No URLs found in prompt to scrape.")
            else:
                task.log("Tool: Scraper - Library not available.", "WARNING")
            
            current_progress += progress_per_tool
            task.set_progress(int(current_progress))

        full_context = "\n\n".join(research_data)
        
        has_real_data = len(research_data) > 0
        
        if not has_real_data:
            task.log("No external data found from enabled tools.", "WARNING")
            full_context = "No external data found."

        # 4. Generate Post
        task.set_progress(70)
        task.log("Generating post content with LLM...")
        prompt = f"""You are @lollms, an AI assistant.
[USER INSTRUCTIONS]: {user_instructions}
[RESEARCH TOPIC]: {topic}

[RESEARCH DATA]:
{full_context}

[INSTRUCTION]:
Write a comprehensive and engaging social media post based on the topic and the research data provided above.
Use markdown formatting. Cite sources if available in the research data.
If NO research data was found, acknowledge that you searched but found nothing specific, and provide a general informative response about the topic based on your internal knowledge instead.
"""
        post_content = lc.generate_text(prompt, max_new_tokens=2048)
        task.set_progress(90)
        
        if post_content:
            new_post = DBPost(
                author_id=lollms_bot_user.id,
                content=post_content,
                visibility=PostVisibility.public
            )
            db.add(new_post)
            db.commit()
            db.refresh(new_post)
            
            from backend.routers.social import get_post_public
            post_public = get_post_public(db, new_post, lollms_bot_user.id)
            manager.broadcast_sync({"type": "new_post", "data": post_public.model_dump(mode="json")})
            task.log(f"Post created successfully. ID: {new_post.id}", "SUCCESS")
            task.set_progress(100)
        else:
            task.log("Failed to generate post content.", "ERROR")
            task.set_progress(100)

    except Exception as e:
        task.log(f"Research task failed: {e}", "CRITICAL")
        trace_exception(e)
    finally:
        db.close()

def _respond_to_mention_task(task: Task, mention_type: str, item_id: int):
    # ... (existing code for respond to mention) ...
    task.log(f"Starting AI response task for {mention_type} ID: {item_id}")
    db = next(get_db())
    try:
        lollms_bot_user = db.query(DBUser).filter(DBUser.username == 'lollms').first()
        if not lollms_bot_user: return

        settings.refresh(db)
        if not settings.get("ai_bot_enabled", False):
            task.log("AI Bot disabled.", "INFO")
            return

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
            "You have been summoned by a user. Analyze their request and the thread context.\n"
            "1. **Direct Reply**: If the request is simple, conversational, or can be answered directly, reply to the thread.\n"
            "2. **Research & Post**: If the request requires detailed research, web browsing, ArXiv search, website analysis, or is a request for a full article/post, you must:\n"
            "   a. Reply to the user acknowledging the request and stating that you will research and create a dedicated post about it.\n"
            "   b. Define the topic and instructions for the research task.\n"
            "3. **Ignore**: If the mention is trivial or requires no response.\n\n"
            "## Output Format\n"
            "Start your response with ONE of these tags:\n"
            "- `[[REPLY]] <your direct answer here>`\n"
            "- `[[RESEARCH_AND_POST]] <acknowledgment comment to user> || <EXACT KEYWORD SEARCH QUERY>`\n"
            "- `[[IGNORE]]`\n"
            "For RESEARCH_AND_POST, the part after || must be a concise search string (e.g., 'quantum computing advances 2024' or 'https://example.com/article')."
        )

        full_user_input = f"{context_instruction}\n\n[THREAD HISTORY]:\n{thread_context}\n\n[INSTRUCTION]: Generate your response starting with [[REPLY]], [[RESEARCH_AND_POST]], or [[IGNORE]]."
        
        response_text = lc.generate_text(full_user_input, system_prompt=augmented_prompt, stream=False, max_new_tokens=512)
        clean_response = response_text.strip()
        
        if "[[IGNORE]]" in clean_response:
            task.log("AI decided to ignore.", "INFO")
            task.set_progress(100)
            return {"status": "ignored"}

        if "[[RESEARCH_AND_POST]]" in clean_response:
            # Parse split
            content_part = clean_response.replace("[[RESEARCH_AND_POST]]", "").strip()
            parts = content_part.split("||")
            
            ack_comment = parts[0].strip()
            research_instructions = parts[1].strip() if len(parts) > 1 else ack_comment
            
            if not ack_comment: ack_comment = "I'm on it! I'll research this and create a post shortly."

            # 1. Post acknowledgment comment
            new_comment = DBComment(
                post_id=post_id,
                author_id=lollms_bot_user.id,
                content=ack_comment
            )
            db.add(new_comment)
            db.commit()
            db.refresh(new_comment, ['author'])
            
            # Broadcast comment
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
            task.log(f"Bot acknowledged request on post ID: {post_id}")

            # 2. Trigger Research Task
            task_manager.submit_task(
                name=f"Research & Post: {research_instructions[:30]}...",
                target=_research_and_post_task,
                args=(research_instructions, thread_context), # passing instruction as topic, and thread context as user_instructions for context
                description=f"Researching topic requested by user.",
                owner_username='lollms'
            )
            return {"status": "research_triggered"}

        # Handle simple reply (or fallback if tag missing but content exists)
        final_content = clean_response.replace("[[REPLY]]", "").strip()
        
        if not final_content:
            task.log("AI generated empty reply.", "WARNING")
            return {"status": "aborted"}

        new_comment = DBComment(
            post_id=post_id,
            author_id=lollms_bot_user.id,
            content=final_content
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
        return {"status": "replied"}

    except Exception as e:
        task.log(f"Error in AI response task: {e}", "CRITICAL")
        trace_exception(e)
        if db: db.rollback()
    finally:
        if db: db.close()

def _generate_feed_post_task(task: Task, force: bool = False):
    """
    Scheduled task to generate a new post for the bot.
    Supports: Static Text, File, RAG, and Auto-Discovery modes.
    """
    if force: task.log("Manual Post Triggered.")
    else: task.log("Running Auto-Posting Job...")
        
    db = next(get_db())
    try:
        settings.refresh(db)
        if not force and not settings.get("ai_bot_auto_post", False):
            task.log("Auto-posting is disabled.", "INFO")
            return

        bot_user = db.query(DBUser).filter(DBUser.username == 'lollms').first()
        if not bot_user:
            task.log("@lollms user not found!", "ERROR")
            return

        mode = settings.get("ai_bot_content_mode", "static_text")
        task.log(f"Posting Mode: {mode}")
        
        context_material = ""
        user_prompt = settings.get("ai_bot_generation_prompt", "Generate an engaging social media post.")
        
        # --- MODE: AUTO DISCOVERY ---
        if mode == "auto_discovery":
            task.log("Auto Discovery: Mining feed for topics...")
            
            # 1. Fetch recent posts to analyze
            recent_posts = db.query(DBPost).filter(
                DBPost.visibility == 'public',
                DBPost.author_id != bot_user.id
            ).order_by(desc(DBPost.created_at)).limit(30).all()
            
            if len(recent_posts) < 3:
                task.log("Not enough recent public posts for auto-discovery.", "WARNING")
                if not force: return
                posts_text = "No recent activity."
            else:
                # Sample random posts to diversify
                sampled_posts = random.sample(recent_posts, min(len(recent_posts), 5))
                posts_text = "\n".join([f"- {p.content[:200]}..." for p in sampled_posts])

            # 2. Get Topic History
            topic_history = settings.get("ai_bot_topic_history", [])
            history_text = ", ".join(topic_history[-10:]) # Send last 10 topics
            
            discovery_prompt = f"""Analyze these recent posts from the community feed:
{posts_text}

[HISTORY]: The bot has recently posted about: {history_text}.

[INSTRUCTION]:
Identify a trending topic or a fun, engaging subject based on the community activity.
It MUST be different from the history.
If the feed is quiet or boring, pick a general interesting topic related to technology, science, or AI.
Return ONLY the topic name/summary.
"""
            lc = build_lollms_client_from_params(username=bot_user.username)
            topic = lc.generate_text(discovery_prompt, max_new_tokens=100).strip()
            task.log(f"Discovered Topic: {topic}")
            
            # Update Context for generation
            context_material = f"The community is talking about or interested in: {topic}."
            user_prompt = f"Create a post about {topic}. Make it engaging and ask a question to spark discussion."
            
            # Save to history
            if topic:
                topic_history.append(topic)
                # Keep history manageable (last 50 topics)
                if len(topic_history) > 50: topic_history = topic_history[-50:]
                
                # Update GlobalConfig for history
                config_entry = db.query(GlobalConfig).filter(GlobalConfig.key == "ai_bot_topic_history").first()
                val_str = json.dumps({"value": topic_history, "type": "json"})
                if config_entry: config_entry.value = val_str
                else: db.add(GlobalConfig(key="ai_bot_topic_history", value=val_str, type="json", category="AI Bot"))
                db.commit()

        # --- MODE: STATIC / FILE / RAG ---
        elif mode == "static_text":
             context_material = settings.get("ai_bot_static_content", "")
        elif mode == "file":
             path = settings.get("ai_bot_file_path", "")
             if path and Path(path).exists():
                 try: context_material = Path(path).read_text(encoding='utf-8')
                 except Exception as e: task.log(f"Error reading file: {e}", "ERROR")
        elif mode == "rag":
             # Basic implementation: just pass the prompt, let the binding handle it if configured, 
             # or here we could query the vector store if we wanted specific context injection.
             # For simplicity, we assume the LLM binding might have RAG enabled or we rely on the prompt.
             # A full RAG query here would require querying the SafeStore with the prompt first.
             datastore_ids = settings.get("ai_bot_rag_datastore_ids", [])
             if datastore_ids and safe_store:
                 try:
                     docs = []
                     for ds_id in datastore_ids:
                         ss = get_safe_store_instance(bot_user.username, ds_id, db)
                         results = ss.query(user_prompt, top_k=3)
                         docs.extend([r['chunk_text'] for r in results])
                     context_material = "\n\n".join(docs)
                 except Exception as e:
                     task.log(f"RAG query failed: {e}", "ERROR")

        # --- GENERATION ---
        task.log("Generating post content...")
        if 'lc' not in locals(): lc = build_lollms_client_from_params(username=bot_user.username)
        
        system_prompt = settings.get("ai_bot_system_prompt") or "You are a helpful AI assistant."
        full_prompt = f"{user_prompt}\n\n[CONTEXT MATERIAL]:\n{context_material[:5000]}"
        
        generated_content = lc.generate_text(full_prompt, system_prompt=system_prompt, max_new_tokens=1024)

        if not generated_content or len(generated_content.strip()) < 5:
            task.log("Generated content was empty.", "WARNING")
            return

        # --- POSTING ---
        new_post = DBPost(
            author_id=bot_user.id,
            content=generated_content.strip(),
            visibility=PostVisibility.public
        )
        db.add(new_post)
        
        # Update last posted time
        now_iso = datetime.datetime.utcnow().isoformat()
        config_entry = db.query(GlobalConfig).filter(GlobalConfig.key == "ai_bot_last_posted_at").first()
        val_str = json.dumps({"value": now_iso, "type": "string"})
        if config_entry: config_entry.value = val_str
        else: db.add(GlobalConfig(key="ai_bot_last_posted_at", value=val_str, type="string", category="AI Bot"))
        
        db.commit()
        db.refresh(new_post)
        
        from backend.routers.social import get_post_public
        post_public = get_post_public(db, new_post, bot_user.id)
        manager.broadcast_sync({"type": "new_post", "data": post_public.model_dump(mode="json")})
        
        task.log(f"Successfully posted. ID: {new_post.id}", "SUCCESS")

    except Exception as e:
        task.log(f"Error in auto-posting task: {e}", "ERROR")
        trace_exception(e)
    finally:
        db.close()
