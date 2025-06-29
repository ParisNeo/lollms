from typing import List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, exists
from fastapi import APIRouter, Depends, HTTPException, status

from backend.database_setup import (
    User as DBUser,
    Post as DBPost,
    Follow as DBFollow,
    Friendship as DBFriendship,
    FriendshipStatus,
    PostVisibility,
    get_db
)
from backend.models import (
    PostCreate,
    PostUpdate,
    PostPublic,
    UserAuthDetails
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
        return

    if post.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own posts.")

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


@social_router.get("/feed", response_model=List[PostPublic])
def get_main_feed(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    # --- FIX: Conditionally build the query to avoid using 'in_' with empty lists ---

    # 1. Get IDs of users the current user follows
    following_ids = [f.following_id for f in db.query(DBFollow.following_id).filter(DBFollow.follower_id == current_user.id).all()]
    
    # 2. Get IDs of users who are friends with the current user
    friend_ids_q1 = db.query(DBFriendship.user2_id).filter(DBFriendship.user1_id == current_user.id, DBFriendship.status == FriendshipStatus.ACCEPTED)
    friend_ids_q2 = db.query(DBFriendship.user1_id).filter(DBFriendship.user2_id == current_user.id, DBFriendship.status == FriendshipStatus.ACCEPTED)
    friend_ids = [item.user2_id for item in friend_ids_q1.all()] + [item.user1_id for item in friend_ids_q2.all()]

    # 3. Build the list of conditions for the query dynamically
    feed_conditions = [
        # Always include public posts
        DBPost.visibility == PostVisibility.PUBLIC,
        # Always include the user's own posts
        DBPost.author_id == current_user.id,
    ]

    # Only add the 'followers' condition if the user is following people
    if following_ids:
        feed_conditions.append(
            and_(DBPost.author_id.in_(following_ids), DBPost.visibility == PostVisibility.FOLLOWERS)
        )
    
    # Only add the 'friends' condition if the user has friends
    if friend_ids:
        feed_conditions.append(
            and_(DBPost.author_id.in_(friend_ids), DBPost.visibility == PostVisibility.FRIENDS)
        )

    # 4. Construct and execute the final query
    query = (
        db.query(DBPost)
        .options(joinedload(DBPost.author))
        .filter(or_(*feed_conditions))
        .order_by(DBPost.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    posts = query.all()
    return posts