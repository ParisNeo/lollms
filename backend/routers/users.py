from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, exists
from typing import List

from backend.database_setup import (
    get_db, 
    User as DBUser, 
    Follow as DBFollow, 
    Friendship as DBFriendship,
    FriendshipStatus,
    get_friendship_record # Using the helper from your database_setup
)
from backend.models import UserAuthDetails, UserProfileResponse, UserPublic
from backend.session import get_current_active_user

users_router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
    dependencies=[Depends(get_current_active_user)]
)

@users_router.get("/search", response_model=List[UserPublic])
def search_for_users(
    q: str = Query(..., min_length=2, max_length=50),
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Searches for users by username, excluding the current user.
    """
    search_term = f"%{q}%"
    users = db.query(DBUser).filter(
        DBUser.username.ilike(search_term),
        DBUser.id != current_user.id
    ).limit(10).all()
    return users


@users_router.get("/{username}", response_model=UserProfileResponse)
def get_user_profile(
    username: str,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Fetches a user's public profile along with the relationship
    status relative to the current authenticated user.
    """
    target_user = db.query(DBUser).filter(DBUser.username == username).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Check follow status
    is_following = db.query(exists().where(and_(
        DBFollow.follower_id == current_user.id,
        DBFollow.following_id == target_user.id
    ))).scalar()

    # Check friendship status using the helper function from your database_setup
    friendship = get_friendship_record(db, current_user.id, target_user.id)
    friendship_status = friendship.status if friendship else None

    # Construct the response using the Pydantic models
    return UserProfileResponse(
        user=UserPublic.from_orm(target_user),
        relationship={
            "is_following": is_following,
            "friendship_status": friendship_status
        }
    )