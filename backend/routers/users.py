# backend/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, exists

from backend.db import get_db
from backend.db.base import FriendshipStatus
from backend.db.utils import get_friendship_record
from backend.db.base import follows_table
from backend.db.models.user import User as DBUser, Friendship as DBFriendship
from backend.models import UserAuthDetails, UserProfileResponse, UserPublic
from backend.session import get_current_active_user
from typing import List
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
    Searches for users.
    - If the query is a partial match, it returns only users who have enabled searchability.
    - If the query is an exact username match, it returns that user regardless of their searchability setting.
    - Excludes the current user from results.
    """
    search_term = f"%{q}%"
    
    users = db.query(DBUser).filter(
        DBUser.id != current_user.id,
        or_(
            DBUser.username == q,
            and_(
                DBUser.is_searchable == True,
                DBUser.username.ilike(search_term)
            )
        )
    ).limit(10).all()
    
    return users


@users_router.get("/mention_search", response_model=List[UserPublic])
def search_for_mentions(
    q: str = Query(..., min_length=1, max_length=50),
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Searches for users to mention.
    Returns users whose username starts with the query and are searchable.
    Excludes the current user.
    """
    search_term = f"{q}%"
    users = db.query(DBUser).filter(
        DBUser.id != current_user.id,
        DBUser.is_searchable == True,
        DBUser.username.ilike(search_term)
    ).limit(5).all()
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

    is_following = db.query(exists().where(and_(
        follows_table.c.follower_id == current_user.id,
        follows_table.c.following_id == target_user.id
    ))).scalar()

    friendship = get_friendship_record(db, current_user.id, target_user.id)
    friendship_status = friendship.status if friendship else None

    return UserProfileResponse(
        user=UserPublic.from_orm(target_user),
        relationship={
            "is_following": is_following,
            "friendship_status": friendship_status
        }
    )
