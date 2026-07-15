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

def _project_user_public(user: DBUser) -> UserPublic:
    """
    Transforms a DBUser ORM object into a completely decoupled, flat UserPublic model.
    This guarantees that the JSON serializer never accesses lazy-loaded ORM relationships
    (discussions, notes, memories) that cause huge payload warning loops.
    """
    return UserPublic(
        id=user.id,
        username=user.username,
        email=user.email,
        icon=user.icon,
        is_active=user.is_active,
        is_admin=getattr(user, "is_admin", False) or False,
        is_moderator=getattr(user, "is_moderator", False) or False,
        status=user.status,
        created_at=user.created_at,
        last_activity_at=user.last_activity_at
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

    return [_project_user_public(u) for u in users]


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
    return [_project_user_public(u) for u in users]


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
    # Resolve 'me' keyword to current user's username
    target_username = current_user.username if username == "me" else username

    target_user = db.query(DBUser).filter(DBUser.username == target_username).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    is_following = db.query(exists().where(and_(
        follows_table.c.follower_id == current_user.id,
        follows_table.c.following_id == target_user.id
    ))).scalar()

    friendship = get_friendship_record(db, current_user.id, target_user.id)
    friendship_status = friendship.status if friendship else None

    return UserProfileResponse(
        user=_project_user_public(target_user),
        relationship={
            "is_following": is_following,
            "friendship_status": friendship_status
        }
    )
