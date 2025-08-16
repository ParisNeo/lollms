# backend/routers/social.py
from typing import List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, exists, select, insert, delete
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func

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
    CommentPublic
)
from backend.session import get_current_active_user

social_router = APIRouter(
    prefix="/api/social",
    tags=["Social"],
    dependencies=[Depends(get_current_active_user)]
)

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

    new_post = DBPost(
        author_id=current_user.id,
        content=post_data.content,
        visibility=post_data.visibility,
        media=post_data.media
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post, ['author'])
    return new_post

@social_router.get("/posts/{post_id}", response_model=PostPublic)
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    post = db.query(DBPost).options(joinedload(DBPost.author)).filter(DBPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    is_author = post.author_id == current_user.id
    if is_author:
        return post

    if post.visibility == PostVisibility.public:
        return post
    
    if post.visibility == PostVisibility.followers:
        is_following = db.query(exists().where(and_(follows_table.c.follower_id == current_user.id, follows_table.c.following_id == post.author_id))).scalar()
        if not is_following:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You must follow this user to see this post.")
        return post

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
        return post

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
    
    db.commit()
    db.refresh(post, ['author'])
    return post

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

    query = db.query(DBPost).options(joinedload(DBPost.author)).filter(DBPost.author_id == target_user.id)

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
    return posts


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
    like_count_subquery = select(func.count(DBPostLike.user_id)).where(DBPostLike.post_id == DBPost.id).scalar_subquery()

    has_liked_subquery = select(
        exists().where(
            and_(
                DBPostLike.post_id == DBPost.id,
                DBPostLike.user_id == current_user.id
            )
        )
    ).correlate(DBPost).scalar_subquery()

    results = db.query(
        DBPost,
        like_count_subquery.label("like_count"),
        has_liked_subquery.label("has_liked")
    ).options(
        joinedload(DBPost.author),
        joinedload(DBPost.comments).joinedload(DBComment.author)
    ).order_by(DBPost.created_at.desc()).limit(50).all()

    response = []
    for post, like_count, has_liked in results:
        post_public = PostPublic.model_validate(post)
        post_public.like_count = like_count
        post_public.has_liked = has_liked
        response.append(post_public)
        
    return response


@social_router.get("/posts/{post_id}/comments", response_model=List[CommentPublic])
def get_comments_for_post(
    post_id: int,
    db: Session = Depends(get_db)
):
    comments = db.query(DBComment).options(
        joinedload(DBComment.author)
    ).filter(DBComment.post_id == post_id).order_by(DBComment.created_at.asc()).all()
    
    return comments

@social_router.post("/posts/{post_id}/comments", response_model=CommentPublic, status_code=status.HTTP_201_CREATED)
def create_comment_for_post(
    post_id: int,
    comment_data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    post = db.query(DBPost).filter(DBPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    new_comment = DBComment(
        post_id=post_id,
        author_id=current_user.id,
        content=comment_data.content
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment, ['author'])
    
    return new_comment


@social_router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    comment = db.query(DBComment).filter(DBComment.id == comment_id).first()
    if not comment:
        return

    if not (comment.author_id == current_user.id or current_user.is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to delete this comment.")
        
    db.delete(comment)
    db.commit()
    return