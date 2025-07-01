from typing import List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, exists, select
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from backend.database_setup import PostLike as DBPostLike # <-- Import PostLike

from backend.database_setup import (
    User as DBUser,
    Post as DBPost,
    Follow as DBFollow,
    Friendship as DBFriendship,
    Comment as DBComment,
    FriendshipStatus,
    PostVisibility,
    get_db
)
from backend.models import (
    PostCreate,
    PostUpdate,
    PostPublic,
    UserAuthDetails,
    CommentCreate, # <-- Import CommentCreate
    CommentPublic  # <-- Import CommentPublic
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

    follow_exists = db.query(DBFollow).filter(
        DBFollow.follower_id == current_user.id,
        DBFollow.following_id == target_user_id
    ).first()

    if follow_exists:
        return

    new_follow = DBFollow(follower_id=current_user.id, following_id=target_user_id)
    db.add(new_follow)
    db.commit()
    return

@social_router.delete("/users/{target_user_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
def unfollow_user(
    target_user_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    follow_record = db.query(DBFollow).filter(
        DBFollow.follower_id == current_user.id,
        DBFollow.following_id == target_user_id
    ).first()

    if follow_record:
        db.delete(follow_record)
        db.commit()
    return

# --- Post Management Endpoints ---

@social_router.post("/posts", response_model=PostPublic, status_code=status.HTTP_201_CREATED)
def create_post(
    post_data: PostCreate,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    # --- FIX: Add explicit validation for content ---
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

    if post.visibility == PostVisibility.PUBLIC:
        return post
    
    if post.visibility == PostVisibility.FOLLOWERS:
        is_following = db.query(exists().where(and_(DBFollow.follower_id == current_user.id, DBFollow.following_id == post.author_id))).scalar()
        if not is_following:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You must follow this user to see this post.")
        return post

    if post.visibility == PostVisibility.FRIENDS:
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
        # Post doesn't exist, so the desired state is already met.
        return

    # Check for authorization. User must be the author OR an admin.
    is_author = post.author_id == current_user.id
    # Use the 'is_admin' boolean property for the check.
    is_admin = hasattr(current_user, 'is_admin') and current_user.is_admin

    if not is_author and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this post."
        )

    # If authorized, delete the post
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
        visibility_conditions = [DBPost.visibility == PostVisibility.PUBLIC]
        is_following = db.query(exists().where(and_(DBFollow.follower_id == current_user.id, DBFollow.following_id == target_user.id))).scalar()
        if is_following:
            visibility_conditions.append(DBPost.visibility == PostVisibility.FOLLOWERS)
        
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
             visibility_conditions.append(DBPost.visibility == PostVisibility.FRIENDS)
        
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

# --- MODIFIED: Update post-fetching endpoints ---
# You must update ALL endpoints that return posts (e.g., /feed, /posts/{id}, etc.)
# Here is an example for the /feed endpoint.

@social_router.get("/feed", response_model=List[PostPublic])
def get_main_feed(
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    # This query is more complex to calculate like_count and has_liked
    like_count_subquery = select(func.count(DBPostLike.user_id)).where(DBPostLike.post_id == DBPost.id).scalar_subquery()
    has_liked_subquery = exists().where(and_(DBPostLike.post_id == DBPost.id, DBPostLike.user_id == current_user.id)).correlate(DBPost).as_scalar()

    # The main query
    results = db.query(
        DBPost,
        like_count_subquery.label("like_count"),
        has_liked_subquery.label("has_liked")
    ).options(joinedload(DBPost.author), joinedload(DBPost.comments).joinedload(DBComment.author)).order_by(DBPost.created_at.desc()).limit(50).all()

    # Manually construct the response to include the calculated fields
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
    """
    Retrieves all comments for a specific post.
    """
    comments = db.query(DBComment).options(
        joinedload(DBComment.author) # Eagerly load author data
    ).filter(DBComment.post_id == post_id).order_by(DBComment.created_at.asc()).all()
    
    return comments

@social_router.post("/posts/{post_id}/comments", response_model=CommentPublic, status_code=status.HTTP_201_CREATED)
def create_comment_for_post(
    post_id: int,
    comment_data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Creates a new comment on a post.
    """
    post = db.query(DBPost).filter(DBPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    
    # TODO: Add logic here to check if the current user has permission to view/comment on the post.

    new_comment = DBComment(
        post_id=post_id,
        author_id=current_user.id,
        content=comment_data.content
    )
    db.add(new_comment)
    db.commit()
    
    # CRITICAL: Refresh the object to load the 'author' relationship after commit.
    db.refresh(new_comment, ['author'])
    
    return new_comment


@social_router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Deletes a comment. Only the author of the comment or an admin can delete it.
    """
    comment = db.query(DBComment).filter(DBComment.id == comment_id).first()
    if not comment:
        return # Idempotent: If it doesn't exist, the desired state is met.

    if not (comment.author_id == current_user.id or current_user.is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to delete this comment.")
        
    db.delete(comment)
    db.commit()
    return