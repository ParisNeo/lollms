# backend/routers/social/__init__.py
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, exists, select, insert, delete, func
from fastapi import APIRouter, Depends, HTTPException, status
from ascii_colors import trace_exception
import re
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
from backend.session import get_current_active_user, get_current_db_user_from_token
from backend.routers.social.mentions import mentions_router

social_router = APIRouter(
    prefix="/api/social",
    tags=["Social"],
    dependencies=[Depends(get_current_active_user)]
)
social_router.include_router(mentions_router, prefix="/mentions")

# --- Helpers ---
def get_post_public(db: Session, post: DBPost, current_user_id: int) -> PostPublic:
    # Logic to convert DBPost to PostPublic, including like counts and status
    like_count = db.query(DBPostLike).filter(DBPostLike.post_id == post.id).count()
    has_liked = db.query(exists().where(and_(DBPostLike.post_id == post.id, DBPostLike.user_id == current_user_id))).scalar()
    
    post_public = PostPublic.model_validate(post)
    post_public.like_count = like_count
    post_public.has_liked = has_liked
    
    # Filter comments based on moderation status
    if post.comments:
        valid_comments = [c for c in post.comments if c.moderation_status != 'flagged']
        post_public.comments = [CommentPublic.model_validate(c) for c in valid_comments]
        
    return post_public

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

    new_post = DBPost(
        author_id=current_user.id,
        content=post_data.content,
        visibility=post_data.visibility,
        media=post_data.media,
        moderation_status=initial_status
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post, ['author'])
    
    # --- NEW: Check for @lollms mention ---
    if settings.get("ai_bot_enabled", False):
        if re.search(r'\B@lollms\b', post_data.content, re.IGNORECASE):
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
    
    return get_post_public(db, new_post, current_user.id)

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

    if post.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own posts.")

    update_data = post_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(post, key, value)
    
    # Reset moderation status on edit if moderation is enabled
    moderation_enabled = settings.get("ai_bot_moderation_enabled", False)
    post.moderation_status = 'pending' if moderation_enabled else 'validated'
    
    db.commit()
    db.refresh(post, ['author'])
    
    if moderation_enabled:
         task_manager.submit_task(
            name=f"Moderating post {post.id}",
            target=_moderate_content_task,
            args=('post', post.id),
            owner_username='lollms'
        )

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
    return [get_post_public(db, p, current_user.id) for p in posts]


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
        following_ids = [uid for uid in following_ids_res if uid is not None]

        friend_ids_q1 = select(DBFriendship.user2_id).where(
            DBFriendship.user1_id == current_user.id,
            DBFriendship.status == FriendshipStatus.ACCEPTED
        )
        friend_ids_q2 = select(DBFriendship.user1_id).where(
            DBFriendship.user2_id == current_user.id,
            DBFriendship.status == FriendshipStatus.ACCEPTED
        )
        friend_ids = list(db.execute(friend_ids_q1).scalars().all()) + list(db.execute(friend_ids_q2).scalars().all())
        friend_ids = [uid for uid in friend_ids if uid is not None]

        conditions = [
            DBPost.visibility == PostVisibility.public,
            DBPost.author_id == current_user.id
        ]
        
        if following_ids:
            conditions.append(and_(
                DBPost.visibility == PostVisibility.followers,
                DBPost.author_id.in_(following_ids)
            ))
            
        if friend_ids:
            conditions.append(and_(
                DBPost.visibility == PostVisibility.friends,
                DBPost.author_id.in_(friend_ids)
            ))

        visibility_conditions = or_(*conditions)

        results = db.query(DBPost).options(
            joinedload(DBPost.author),
            joinedload(DBPost.comments).joinedload(DBComment.author)
        ).filter(
            visibility_conditions,
            DBPost.moderation_status != 'flagged'
        ).order_by(DBPost.created_at.desc()).limit(50).all()
        
        response = []
        for post in results:
            response.append(get_post_public(db, post, current_user.id))
        
        return response
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

    new_comment = DBComment(
        post_id=post_id,
        author_id=current_user.id,
        content=comment_data.content,
        moderation_status=initial_status
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment, ['author'])
    
    # Mention Response
    if settings.get("ai_bot_enabled", False):
        if current_user.username != 'lollms':
            is_explicit_mention = re.search(r'\B@lollms\b', comment_data.content, re.IGNORECASE)
            post_author_username = post.author.username if post.author else db.query(DBUser.username).filter(DBUser.id == post.author_id).scalar()
            is_bot_post = (post_author_username == 'lollms')
            was_mentioned_in_post = re.search(r'\B@lollms\b', post.content, re.IGNORECASE)
            
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
