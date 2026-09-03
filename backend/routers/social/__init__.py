# backend/routers/social/__init__.py
import uuid
import shutil
import io
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from PIL import Image
from werkzeug.utils import secure_filename

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, exists, select, insert, delete, func
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from ascii_colors import trace_exception

from backend.settings import settings
from backend.task_manager import task_manager
from backend.tasks.social_tasks import _respond_to_mention_task, _moderate_content_task
from backend.db import get_db
from backend.db.base import PostVisibility, FriendshipStatus, follows_table
from backend.db.models.user import User as DBUser, Friendship as DBFriendship
from backend.db.models.social import Post as DBPost, Comment as DBComment, PostLike as DBPostLike
from backend.models import (
    PostCreate,
    PostUpdate,
    PostPublic,
    UserAuthDetails,
    CommentCreate,
    CommentPublic,
    AuthorPublic
)
from backend.session import (
    get_current_active_user,
    get_current_db_user_from_token,
    get_user_social_assets_path,
    get_user_lollms_client
)
from backend.discussion import get_user_discussion
from backend.routers.social.mentions import mentions_router
from backend.security import sanitize_content, validate_url
from backend.ws_manager import manager

social_router = APIRouter(
    prefix="/api/social",
    tags=["Social"],
    dependencies=[Depends(get_current_active_user)]
)
social_router.include_router(mentions_router, prefix="/mentions")

import datetime

def notify_mentioned_users(db: Session, text_content: str, author_user: Any, item_type: str, item_id: int):
    """Extracts @mentions from content and dispatches WebSocket notifications to tagged users."""
    if not text_content:
        return

    mentions = re.findall(r'(?<!\w)@([a-zA-Z0-9_-]+)\b', text_content)
    if not mentions:
        return

    unique_usernames = set(m.lower() for m in mentions)
    author_username = author_user.username if hasattr(author_user, 'username') else 'Someone'
    author_id = author_user.id if hasattr(author_user, 'id') else None
    author_icon = getattr(author_user, 'icon', None)

    for uname in unique_usernames:
        if uname == 'lollms' or (author_username and uname == author_username.lower()):
            continue

        target_user = db.query(DBUser).filter(func.lower(DBUser.username) == uname, DBUser.is_active == True).first()
        if target_user and target_user.id != author_id:
            msg_text = f"📢 @{author_username} mentioned you in a post." if item_type == 'post' else f"💬 @{author_username} mentioned you in a comment."
            manager.send_personal_message_sync({
                "type": "notification",
                "data": {
                    "message": msg_text,
                    "type": "info",
                    "duration": 6000,
                    "sender_username": author_username,
                    "sender_icon": author_icon
                }
            }, target_user.id)

# --- Helpers ---
def get_post_public(db: Session, post: DBPost, current_user_id: int) -> PostPublic:
    like_count = db.query(DBPostLike).filter(DBPostLike.post_id == post.id).count()
    has_liked = db.query(exists().where(and_(DBPostLike.post_id == post.id, DBPostLike.user_id == current_user_id))).scalar()

    post_public = PostPublic.model_validate(post)
    post_public.like_count = like_count
    post_public.has_liked = bool(has_liked)
    post_public.is_pinned = getattr(post, 'is_pinned', False) or False
    post_public.is_ai_generated = bool(post.author and post.author.username.lower() == 'lollms')

    if post.comments:
        valid_comments = [c for c in post.comments if c.moderation_status != 'flagged']
        comment_objs = []
        for c in valid_comments:
            c_pub = CommentPublic.model_validate(c)
            c_pub.is_ai_generated = bool(c.author and c.author.username.lower() == 'lollms')
            comment_objs.append(c_pub)
        post_public.comments = comment_objs

    return post_public

def get_posts_public_batched(db: Session, posts: List[DBPost], current_user_id: int) -> List[PostPublic]:
    """
    Optimized helper to convert a list of DBPosts to PostPublic objects,
    fetching like counts and user like status in bulk to avoid N+1 queries.
    """
    if not posts:
        return []

    post_ids = [p.id for p in posts]

    like_counts_rows = db.query(
        DBPostLike.post_id,
        func.count(DBPostLike.user_id)
    ).filter(DBPostLike.post_id.in_(post_ids)).group_by(DBPostLike.post_id).all()

    like_counts = {r[0]: r[1] for r in like_counts_rows}

    user_likes_rows = db.query(DBPostLike.post_id).filter(
        DBPostLike.post_id.in_(post_ids),
        DBPostLike.user_id == current_user_id
    ).all()
    user_likes = set(r[0] for r in user_likes_rows)

    results = []
    for post in posts:
        post_public = PostPublic.model_validate(post)
        post_public.like_count = like_counts.get(post.id, 0)
        post_public.has_liked = post.id in user_likes
        post_public.is_pinned = getattr(post, 'is_pinned', False) or False
        post_public.is_ai_generated = bool(post.author and post.author.username.lower() == 'lollms')

        if post.comments:
            valid_comments = [c for c in post.comments if c.moderation_status != 'flagged']
            comment_objs = []
            for c in valid_comments:
                c_pub = CommentPublic.model_validate(c)
                c_pub.is_ai_generated = bool(c.author and c.author.username.lower() == 'lollms')
                comment_objs.append(c_pub)
            post_public.comments = comment_objs

        results.append(post_public)

    return results

# --- Follow/Unfollow Endpoints ---

@social_router.post("/users/{target_user_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
def follow_user(
    target_user_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    if current_user.id == target_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot follow yourself.")

    target_user = db.query(DBUser).filter(DBUser.id == target_user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    follow_exists = db.query(exists().where(
        and_(
            follows_table.c.follower_id == current_user.id,
            follows_table.c.following_id == target_user_id
        )
    )).scalar()

    if follow_exists:
        return

    stmt = insert(follows_table).values(follower_id=current_user.id, following_id=target_user_id)
    db.execute(stmt)
    db.commit()
    return

@social_router.delete("/users/{target_user_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
def unfollow_user(
    target_user_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    stmt = delete(follows_table).where(
        and_(
            follows_table.c.follower_id == current_user.id,
            follows_table.c.following_id == target_user_id
        )
    )
    db.execute(stmt)
    db.commit()
    return

# --- Post Media & Link Verification Models ---

class LinkPreviewRequest(BaseModel):
    url: str

class LinkPreviewResponse(BaseModel):
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    domain: str

# Allowed Media Configurations
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/ogg": ".ogv", "video/quicktime": ".mov"}
ALLOWED_AUDIO_TYPES = {"audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/wav": ".wav", "audio/ogg": ".ogg", "audio/webm": ".webm", "audio/aac": ".aac"}

MAX_IMAGE_SIZE = 15 * 1024 * 1024  # 15 MB
MAX_VIDEO_SIZE = 60 * 1024 * 1024  # 60 MB
MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25 MB

def _sanitize_media_items(media_list: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not media_list or not isinstance(media_list, list):
        return []

    clean_media = []
    for item in media_list[:10]:  # Cap at 10 items max per post
        if not isinstance(item, dict):
            continue

        m_type = item.get("type", "").lower()
        if m_type in ["image", "video", "audio"]:
            url_val = item.get("url", "")
            if url_val.startswith("/api/social/media/"):
                clean_media.append({
                    "type": m_type,
                    "url": sanitize_content(url_val),
                    "filename": sanitize_content(item.get("filename", "media")),
                    "size": int(item.get("size", 0)) if isinstance(item.get("size"), (int, float)) else 0
                })
        elif m_type == "link":
            raw_url = item.get("url", "").strip()
            if raw_url:
                try:
                    validate_url(raw_url)
                    clean_media.append({
                        "type": "link",
                        "url": raw_url,
                        "title": sanitize_content(item.get("title", "")[:200]) if item.get("title") else None,
                        "description": sanitize_content(item.get("description", "")[:500]) if item.get("description") else None,
                        "image": item.get("image") if item.get("image") and (item.get("image").startswith("http://") or item.get("image").startswith("https://")) else None,
                        "domain": sanitize_content(item.get("domain", "")[:100])
                    })
                except ValueError:
                    continue

    return clean_media

# --- Media Upload & Link Verification Endpoints ---

@social_router.post("/upload-media", response_model=List[Dict[str, Any]], status_code=status.HTTP_201_CREATED)
async def upload_post_media(
    files: List[UploadFile] = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Safely ingests and verifies image/video/audio attachments for social posts.
    Enforces MIME verification, deep magic-byte inspection, and size restrictions.
    """
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files allowed per post.")

    saved_media = []
    user_social_path = get_user_social_assets_path(current_user.username)

    for file in files:
        if not file.filename:
            continue

        s_filename = secure_filename(file.filename or "media_upload")
        content_type = (file.content_type or "").lower()

        # 1. Determine media category and validate size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        media_type = None
        ext = Path(s_filename).suffix.lower()

        if content_type in ALLOWED_IMAGE_TYPES:
            if file_size > MAX_IMAGE_SIZE:
                raise HTTPException(status_code=413, detail=f"Image '{s_filename}' exceeds 15MB limit.")
            # Deep PIL Image Verification (Blocks polyglots/scripts)
            try:
                img = Image.open(file.file)
                img.verify()
                file.file.seek(0)
            except Exception:
                raise HTTPException(status_code=400, detail=f"Corrupted or invalid image content: '{s_filename}'")
            media_type = "image"
            if not ext or ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                ext = ALLOWED_IMAGE_TYPES.get(content_type, ".png")

        elif content_type in ALLOWED_VIDEO_TYPES:
            if file_size > MAX_VIDEO_SIZE:
                raise HTTPException(status_code=413, detail=f"Video '{s_filename}' exceeds 60MB limit.")
            if ext not in [".mp4", ".webm", ".ogv", ".mov"]:
                ext = ALLOWED_VIDEO_TYPES.get(content_type, ".mp4")
            media_type = "video"

        elif content_type in ALLOWED_AUDIO_TYPES:
            if file_size > MAX_AUDIO_SIZE:
                raise HTTPException(status_code=413, detail=f"Audio '{s_filename}' exceeds 25MB limit.")
            if ext not in [".mp3", ".wav", ".ogg", ".webm", ".m4a", ".aac"]:
                ext = ALLOWED_AUDIO_TYPES.get(content_type, ".mp3")
            media_type = "audio"

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported media format: '{content_type}'")

        # 2. Persist with secure random name
        unique_name = f"{uuid.uuid4().hex}{ext}"
        target_path = user_social_path / unique_name

        try:
            with open(target_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        finally:
            file.file.close()

        saved_media.append({
            "type": media_type,
            "url": f"/api/social/media/{current_user.username}/{unique_name}",
            "filename": s_filename,
            "size": file_size
        })

    return saved_media

@social_router.get("/media/{username}/{filename}")
async def get_social_media_file(
    username: str,
    filename: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Serves stored social post media with path containment checks and nosniff protections.
    """
    s_username = secure_filename(username)
    s_filename = secure_filename(filename)

    user_social_path = get_user_social_assets_path(s_username).resolve()
    target_file = (user_social_path / s_filename).resolve()

    if not target_file.is_relative_to(user_social_path) or not target_file.is_file():
        raise HTTPException(status_code=404, detail="Media asset not found.")

    return FileResponse(
        str(target_file),
        headers={"X-Content-Type-Options": "nosniff"}
    )

@social_router.post("/link-preview", response_model=LinkPreviewResponse)
async def extract_link_preview(
    payload: LinkPreviewRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Fetches OpenGraph title, description, and preview image for an external URL.
    Enforces SSRF prevention via validate_url, tight timeouts, and response size guards.
    """
    raw_url = payload.url.strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="URL cannot be empty.")

    try:
        validate_url(raw_url)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=f"Access to URL is forbidden: {str(val_err)}")

    parsed = urlparse(raw_url)
    domain = parsed.netloc

    title = None
    description = None
    image_url = None

    try:
        headers = {
            "User-Agent": "LoLLMs-Platform-Bot/2.1 (+https://github.com/ParisNeo/lollms)"
        }
        resp = requests.get(raw_url, headers=headers, timeout=4, stream=True)
        resp.raise_for_status()

        # Read only up to 512KB to prevent memory exhaustion from massive files
        content_chunk = b""
        for chunk in resp.iter_content(chunk_size=16384):
            content_chunk += chunk
            if len(content_chunk) > 524288:
                break

        soup = BeautifulSoup(content_chunk.decode("utf-8", errors="ignore"), "html.parser")

        # OpenGraph extraction
        og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()

        og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "twitter:description"}) or soup.find("meta", attrs={"name": "description"})
        if og_desc and og_desc.get("content"):
            description = og_desc["content"].strip()

        og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
        if og_img and og_img.get("content"):
            cand_img = og_img["content"].strip()
            try:
                validate_url(cand_img)
                image_url = cand_img
            except ValueError:
                image_url = None

    except Exception:
        # Fallback to domain name if scraping is blocked or fails
        title = title or domain

    return LinkPreviewResponse(
        url=raw_url,
        title=sanitize_content(title[:200]) if title else domain,
        description=sanitize_content(description[:400]) if description else None,
        image=image_url,
        domain=domain
    )

# --- Post Management Endpoints ---

@social_router.post("/posts", response_model=PostPublic, status_code=status.HTTP_201_CREATED)
def create_post(
    post_data: PostCreate,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    if not post_data.content or not post_data.content.strip():
        raise HTTPException(status_code=400, detail="Post content cannot be empty.")
    
    moderation_enabled = settings.get("ai_bot_moderation_enabled", False)
    initial_status = "pending" if moderation_enabled else "validated"

    # Sanitize content to prevent Stored XSS
    clean_content = sanitize_content(post_data.content)
    is_pinned = bool(post_data.is_pinned and getattr(current_user, 'is_admin', False))
    clean_media = _sanitize_media_items(post_data.media)

    new_post = DBPost(
        author_id=current_user.id,
        content=clean_content,
        visibility=post_data.visibility,
        is_pinned=is_pinned,
        media=clean_media if clean_media else None,
        moderation_status=initial_status
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post, ['author'])
    
    # Notify human users mentioned in the post
    notify_mentioned_users(db, clean_content, current_user, "post", new_post.id)

    # --- Check for @lollms mention ---
    if settings.get("ai_bot_enabled", False):
        if re.search(r'(?<!\w)@lollms\b', clean_content, re.IGNORECASE):
            task_manager.submit_task(
                name=f"AI Bot responding to post by {current_user.username}",
                target=_respond_to_mention_task,
                args=('post', new_post.id),
                description=f"Generating AI reply for post ID: {new_post.id}",
                owner_username='lollms' 
            )

    # --- MODERATION ---
    if moderation_enabled:
        task_manager.submit_task(
            name=f"Moderating post {new_post.id}",
            target=_moderate_content_task,
            args=('post', new_post.id),
            owner_username='lollms' # System/Bot owns this task
        )

    post_public_obj = get_post_public(db, new_post, current_user.id)
    manager.broadcast_sync({"type": "new_post", "data": post_public_obj.model_dump(mode="json")})
    return post_public_obj

@social_router.get("/posts/{post_id}", response_model=PostPublic)
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    post = db.query(DBPost).options(joinedload(DBPost.author)).filter(
        DBPost.id == post_id,
        DBPost.moderation_status != 'flagged'
    ).first()
    
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    is_author = post.author_id == current_user.id
    if is_author:
        return get_post_public(db, post, current_user.id)

    if post.visibility == PostVisibility.public:
        return get_post_public(db, post, current_user.id)
    
    if post.visibility == PostVisibility.followers:
        is_following = db.query(exists().where(and_(follows_table.c.follower_id == current_user.id, follows_table.c.following_id == post.author_id))).scalar()
        if not is_following:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You must follow this user to see this post.")
        return get_post_public(db, post, current_user.id)

    if post.visibility == PostVisibility.friends:
        are_friends = db.query(exists().where(
            and_(
                or_(
                    and_(DBFriendship.user1_id == current_user.id, DBFriendship.user2_id == post.author_id),
                    and_(DBFriendship.user1_id == post.author_id, DBFriendship.user2_id == current_user.id)
                ),
                DBFriendship.status == FriendshipStatus.ACCEPTED
            )
        )).scalar()
        if not are_friends:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You must be friends with this user to see this post.")
        return get_post_public(db, post, current_user.id)

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to view this post.")


@social_router.put("/posts/{post_id}", response_model=PostPublic)
def update_post(
    post_id: int,
    post_data: PostUpdate,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    post = db.query(DBPost).filter(DBPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    is_author = post.author_id == current_user.id
    is_admin = getattr(current_user, 'is_admin', False)

    if not is_author and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own posts.")

    update_data = post_data.model_dump(exclude_unset=True)

    # Sanitize content update
    if 'content' in update_data and update_data['content'] is not None:
        if not update_data['content'].strip():
            raise HTTPException(status_code=400, detail="Post content cannot be empty.")
        post.content = sanitize_content(update_data['content'])

    if 'visibility' in update_data and update_data['visibility'] is not None:
        post.visibility = update_data['visibility']

    if 'media' in update_data and update_data['media'] is not None:
        post.media = _sanitize_media_items(update_data['media'])

    if 'is_pinned' in update_data and update_data['is_pinned'] is not None:
        if is_admin:
            post.is_pinned = bool(update_data['is_pinned'])
        else:
            raise HTTPException(status_code=403, detail="Only administrators can feature or pin posts.")

    # Reset moderation status on edit if moderation is enabled
    moderation_enabled = settings.get("ai_bot_moderation_enabled", False)
    if moderation_enabled and 'content' in update_data:
        post.moderation_status = 'pending'
    else:
        post.moderation_status = 'validated'

    db.commit()
    db.refresh(post, ['author'])

    if moderation_enabled and 'content' in update_data:
        task_manager.submit_task(
            name=f"Moderating post {post.id}",
            target=_moderate_content_task,
            args=('post', post.id),
            owner_username='lollms'
        )

    return get_post_public(db, post, current_user.id)

class PostExplainActionRequest(BaseModel):
    action: Optional[str] = "explain" # "explain", "fact_check", "expand", "summarize", "discuss"

class PostExplanationResponse(BaseModel):
    discussion_id: str
    prompt: str
    post_id: int
    title: str
    action: str

@social_router.post("/posts/{post_id}/explain", response_model=PostExplanationResponse)
def explain_post_with_lollms(
    post_id: int,
    action: Optional[str] = Query("explain"),
    payload: Optional[PostExplainActionRequest] = None,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Creates a private, personal explanation discussion for the current user anchored to a specific post.
    Supports actions: 'explain', 'fact_check', 'expand', 'summarize', 'discuss'.
    """
    selected_action = (payload.action if payload and payload.action else action or "explain").lower().strip()
    """
    Creates a private, personal explanation discussion for the current user anchored to a specific post.
    The resulting discussion is private and visible only to the requesting user.
    """
    try:
        post = db.query(DBPost).options(joinedload(DBPost.author)).filter(
            DBPost.id == post_id,
            DBPost.moderation_status != 'flagged'
        ).first()

        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

        # Validate post visibility for the current user
        if post.author_id != current_user.id and post.visibility != PostVisibility.public:
            if post.visibility == PostVisibility.followers:
                is_following = db.query(exists().where(and_(follows_table.c.follower_id == current_user.id, follows_table.c.following_id == post.author_id))).scalar()
                if not is_following and not current_user.is_admin:
                    raise HTTPException(status_code=403, detail="Forbidden.")
            elif post.visibility == PostVisibility.friends:
                are_friends = db.query(exists().where(
                    and_(
                        or_(
                            and_(DBFriendship.user1_id == current_user.id, DBFriendship.user2_id == post.author_id),
                            and_(DBFriendship.user1_id == post.author_id, DBFriendship.user2_id == current_user.id)
                        ),
                        DBFriendship.status == FriendshipStatus.ACCEPTED
                    )
                )).scalar()
                if not are_friends and not current_user.is_admin:
                    raise HTTPException(status_code=403, detail="Forbidden.")

        # Create a private discussion for the requesting user
        author_name = post.author.username if post.author else "Community User"
        discussion_id = str(uuid.uuid4())

        lc = get_user_lollms_client(current_user.username)
        discussion_obj = get_user_discussion(current_user.username, discussion_id, create_if_missing=True, lollms_client=lc)

        # Collect media references or links from post if available
        media_links = []
        if post.media and isinstance(post.media, list):
            for m in post.media:
                if isinstance(m, dict) and m.get("url"):
                    media_links.append(f"- {m.get('type', 'media').capitalize()}: {m.get('url')}")

        media_context = ("\n\nAttached Media / Links:\n" + "\n".join(media_links)) if media_links else ""

        # Construct customized prompts & titles based on requested cognitive action
        if selected_action in ["fact_check", "verify"]:
            clean_title = f"Fact-Check: @{author_name}'s Post"
            prompt = (
                f"Please fact-check and critically verify the claims made in this post by @{author_name}:\n\n"
                f"\"{post.content}\"{media_context}\n\n"
                "Instructions:\n"
                "1. Cross-examine all facts, statistics, historical claims, and technical assertions.\n"
                "2. Search the web or analyze external references if necessary to find verifying or contradicting evidence.\n"
                "3. Provide a clear, objective assessment with verifiable sources and conclusions."
            )
        elif selected_action in ["expand", "research"]:
            clean_title = f"Research: @{author_name}'s Post"
            prompt = (
                f"Please expand and deep-dive into the concepts presented in this post by @{author_name}:\n\n"
                f"\"{post.content}\"{media_context}\n\n"
                "Instructions:\n"
                "1. Provide in-depth technical context, history, and broader implications of the topic.\n"
                "2. Feel free to use web search or research tools to bring in external papers, documentation, or related case studies.\n"
                "3. Structure your response clearly with detailed explanations and actionable insights."
            )
        elif selected_action in ["summarize", "summary"]:
            clean_title = f"Summary: @{author_name}'s Post"
            prompt = (
                f"Please summarize the following post by @{author_name}:\n\n"
                f"\"{post.content}\"{media_context}\n\n"
                "Extract the core arguments, main takeaways, and key conclusions into concise, structured bullet points."
            )
        elif selected_action in ["discuss", "chat"]:
            clean_title = f"Chat: @{author_name}'s Post"
            prompt = (
                f"Let's discuss this post by @{author_name}:\n\n"
                f"\"{post.content}\"{media_context}\n\n"
                "Share your initial perspective and key thoughts on this post to start our discussion."
            )
        else:
            clean_title = f"Explain: @{author_name}'s Post"
            prompt = (
                f"Please explain and analyze the following post by @{author_name}:\n\n"
                f"\"{post.content}\"{media_context}\n\n"
                "Break down the key concepts in plain, accessible language, explain any technical terms or jargon, and provide intuitive background context."
            )

        discussion_obj.set_metadata_item('title', clean_title)
        discussion_obj.set_metadata_item('linked_post_id', post_id)
        discussion_obj.set_metadata_item('cognitive_action', selected_action)
        discussion_obj.commit()

        return PostExplanationResponse(
            discussion_id=discussion_id,
            prompt=prompt,
            post_id=post_id,
            title=clean_title,
            action=selected_action
        )
    except HTTPException:
        raise
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to generate explanation discussion: {e}")

@social_router.post("/posts/{post_id}/pin", response_model=PostPublic)
def toggle_pin_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(status_code=403, detail="Only administrators can feature or pin posts.")

    post = db.query(DBPost).filter(DBPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")

    post.is_pinned = not bool(getattr(post, 'is_pinned', False))
    db.commit()
    db.refresh(post, ['author'])
    return get_post_public(db, post, current_user.id)

@social_router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    post = db.query(DBPost).filter(DBPost.id == post_id).first()
    if not post:
        return

    is_author = post.author_id == current_user.id
    is_admin = hasattr(current_user, 'is_admin') and current_user.is_admin

    if not is_author and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this post."
        )

    db.delete(post)
    db.commit()
    return

# --- Feed Generation Endpoints ---

@social_router.get("/users/{username}/posts", response_model=List[PostPublic])
def get_user_posts(
    username: str,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    target_user = db.query(DBUser).filter(DBUser.username == username).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    query = db.query(DBPost).options(joinedload(DBPost.author)).filter(
        DBPost.author_id == target_user.id,
        DBPost.moderation_status != 'flagged'
    )

    if target_user.id != current_user.id:
        visibility_conditions = [DBPost.visibility == PostVisibility.public]
        is_following = db.query(exists().where(and_(follows_table.c.follower_id == current_user.id, follows_table.c.following_id == target_user.id))).scalar()
        if is_following:
            visibility_conditions.append(DBPost.visibility == PostVisibility.followers)
        
        are_friends = db.query(exists().where(
            and_(
                or_(
                    and_(DBFriendship.user1_id == current_user.id, DBFriendship.user2_id == target_user.id),
                    and_(DBFriendship.user1_id == target_user.id, DBFriendship.user2_id == current_user.id)
                ),
                DBFriendship.status == FriendshipStatus.ACCEPTED
            )
        )).scalar()
        if are_friends:
             visibility_conditions.append(DBPost.visibility == PostVisibility.friends)
        
        query = query.filter(or_(*visibility_conditions))

    posts = query.order_by(DBPost.created_at.desc()).all()
    # Optimized batch fetching
    return get_posts_public_batched(db, posts, current_user.id)


@social_router.post("/posts/{post_id}/like", status_code=201)
def like_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    post = db.query(DBPost).filter(DBPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    existing_like = db.query(DBPostLike).filter_by(user_id=current_user.id, post_id=post_id).first()
    if not existing_like:
        new_like = DBPostLike(user_id=current_user.id, post_id=post_id)
        db.add(new_like)
        db.commit()
    return {"message": "Post liked successfully."}

@social_router.delete("/posts/{post_id}/like", status_code=204)
def unlike_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    like_to_delete = db.query(DBPostLike).filter_by(user_id=current_user.id, post_id=post_id).first()
    if like_to_delete:
        db.delete(like_to_delete)
        db.commit()
    return

@social_router.get("/feed", response_model=List[PostPublic])
def get_main_feed(
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    try:
        following_ids_query = select(follows_table.c.following_id).where(follows_table.c.follower_id == current_user.id)
        following_ids_res = db.execute(following_ids_query).scalars().all()
        following_ids = set(uid for uid in following_ids_res if uid is not None)

        friend_ids_q1 = select(DBFriendship.user2_id).where(
            DBFriendship.user1_id == current_user.id,
            DBFriendship.status == FriendshipStatus.ACCEPTED
        )
        friend_ids_q2 = select(DBFriendship.user1_id).where(
            DBFriendship.user2_id == current_user.id,
            DBFriendship.status == FriendshipStatus.ACCEPTED
        )
        friend_ids = set(list(db.execute(friend_ids_q1).scalars().all()) + list(db.execute(friend_ids_q2).scalars().all()))

        conditions = [
            DBPost.visibility == PostVisibility.public,
            DBPost.author_id == current_user.id
        ]

        if following_ids:
            conditions.append(and_(
                DBPost.visibility == PostVisibility.followers,
                DBPost.author_id.in_(list(following_ids))
            ))

        if friend_ids:
            conditions.append(and_(
                DBPost.visibility == PostVisibility.friends,
                DBPost.author_id.in_(list(friend_ids))
            ))

        visibility_conditions = or_(*conditions)

        candidates = db.query(DBPost).options(
            joinedload(DBPost.author),
            joinedload(DBPost.comments).joinedload(DBComment.author),
            joinedload(DBPost.likes)
        ).filter(
            visibility_conditions,
            DBPost.moderation_status != 'flagged'
        ).order_by(DBPost.created_at.desc()).limit(200).all()

        now = datetime.datetime.now(datetime.timezone.utc)

        def calculate_post_score(post: DBPost) -> float:
            is_pinned = getattr(post, 'is_pinned', False) or False
            created_at = post.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=datetime.timezone.utc)

            age_hours = max(0.05, (now - created_at).total_seconds() / 3600.0)

            # Pinned admin announcements maintain highest priority tier
            if is_pinned:
                return 1000000.0 + (1000.0 / (1.0 + age_hours / 24.0))

            # 1. Social Relationship Affinity
            author_id = post.author_id
            is_self = (author_id == current_user.id)
            is_friend = (author_id in friend_ids)
            is_following = (author_id in following_ids)
            is_bot = bool(post.author and post.author.username.lower() == 'lollms')

            affinity = 15.0
            if is_self:
                affinity += 30.0
            if is_friend:
                affinity += 75.0
            if is_following:
                affinity += 40.0
            if is_bot:
                affinity += 30.0

            # 2. Engagement Factor
            like_count = len(post.likes) if post.likes else 0
            comment_count = len([c for c in (post.comments or []) if c.moderation_status != 'flagged'])
            engagement = (like_count * 5.0) + (comment_count * 8.0)

            # 3. 48-hour half-life exponential time decay
            decay = 1.0 / (1.0 + (age_hours / 48.0) ** 1.35)

            return (affinity + engagement) * decay

        sorted_candidates = sorted(candidates, key=calculate_post_score, reverse=True)[:50]
        return get_posts_public_batched(db, sorted_candidates, current_user.id)

    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail="An error occurred while fetching the feed.")


@social_router.get("/posts/{post_id}/comments", response_model=List[CommentPublic])
def get_comments_for_post(
    post_id: int,
    db: Session = Depends(get_db)
):
    comments = db.query(DBComment).options(
        joinedload(DBComment.author)
    ).filter(
        DBComment.post_id == post_id,
        DBComment.moderation_status != 'flagged'
    ).order_by(DBComment.created_at.asc()).all()
    
    return [CommentPublic.model_validate(c) for c in comments]

@social_router.post("/posts/{post_id}/comments", response_model=CommentPublic, status_code=status.HTTP_201_CREATED)
def add_comment_to_post(
    post_id: int,
    comment_data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    post = db.query(DBPost).filter(DBPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")

    moderation_enabled = settings.get("ai_bot_moderation_enabled", False)
    initial_status = "pending" if moderation_enabled else "validated"

    # Sanitize comment content
    clean_content = sanitize_content(comment_data.content)

    new_comment = DBComment(
        post_id=post_id,
        author_id=current_user.id,
        content=clean_content,
        moderation_status=initial_status
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment, ['author'])
    
    # Notify human users mentioned in the comment
    notify_mentioned_users(db, clean_content, current_user, "comment", new_comment.id)

    # Also notify post author if someone commented on their post and they weren't explicitly tagged
    if post.author_id != current_user.id and (post.author and post.author.username.lower() != 'lollms'):
        post_author_name = post.author.username.lower()
        mentioned_names = [m.lower() for m in re.findall(r'(?<!\w)@([a-zA-Z0-9_-]+)\b', clean_content)]
        if post_author_name not in mentioned_names:
            manager.send_personal_message_sync({
                "type": "notification",
                "data": {
                    "message": f"💬 @{current_user.username} commented on your post.",
                    "type": "info",
                    "duration": 6000,
                    "sender_username": current_user.username,
                    "sender_icon": current_user.icon
                }
            }, post.author_id)

    # Mention Response for Bot
    if settings.get("ai_bot_enabled", False):
        if current_user.username != 'lollms':
            is_explicit_mention = re.search(r'(?<!\w)@lollms\b', clean_content, re.IGNORECASE)
            post_author_username = post.author.username if post.author else db.query(DBUser.username).filter(DBUser.id == post.author_id).scalar()
            is_bot_post = (post_author_username == 'lollms')
            was_mentioned_in_post = re.search(r'(?<!\w)@lollms\b', post.content, re.IGNORECASE)

            lollms_user = db.query(DBUser).filter(DBUser.username == 'lollms').first()
            is_active_participant = False
            if lollms_user:
                is_active_participant = db.query(exists().where(
                    and_(
                        DBComment.post_id == post_id,
                        DBComment.author_id == lollms_user.id
                    )
                )).scalar()

            if is_explicit_mention or is_bot_post or was_mentioned_in_post or is_active_participant:
                task_manager.submit_task(
                    name=f"AI Bot responding to comment by {current_user.username}",
                    target=_respond_to_mention_task,
                    args=('comment', new_comment.id),
                    description=f"Generating AI reply for comment ID: {new_comment.id} (Thread monitoring)",
                    owner_username='lollms'
                )

    # Moderation
    if moderation_enabled:
        task_manager.submit_task(
            name=f"Moderating comment {new_comment.id}",
            target=_moderate_content_task,
            args=('comment', new_comment.id),
            owner_username='lollms'
        )

    return CommentPublic.model_validate(new_comment)

@social_router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    comment = db.query(DBComment).filter(DBComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    post = db.query(DBPost).filter(DBPost.id == comment.post_id).first()
    is_post_author = post.author_id == current_user.id if post else False
    is_comment_author = comment.author_id == current_user.id
    is_admin_or_moderator = current_user.is_admin or current_user.is_moderator

    if not (is_comment_author or is_admin_or_moderator or is_post_author):
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")

    db.delete(comment)
    db.commit()
    return
