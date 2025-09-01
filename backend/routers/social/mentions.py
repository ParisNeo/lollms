# backend/routers/social/mentions.py
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from backend.db import get_db
from backend.db.models.user import User as DBUser, Friendship as DBFriendship
from backend.db.base import FriendshipStatus
from backend.models import UserAuthDetails, UserPublic
from backend.session import get_current_active_user
from backend.settings import settings

mentions_router = APIRouter()

@mentions_router.get("/search", response_model=List[UserPublic])
def search_users_for_mention(
    q: str = Query(..., min_length=1, max_length=50),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    search_term = f"%{q}%"
    
    # Get IDs of friends
    friend_ids = db.query(DBFriendship.user1_id, DBFriendship.user2_id)\
        .filter(or_(DBFriendship.user1_id == current_user.id, DBFriendship.user2_id == current_user.id))\
        .filter(DBFriendship.status == FriendshipStatus.ACCEPTED).all()
    
    friend_ids_flat = {uid for pair in friend_ids for uid in pair if uid != current_user.id}

    # Get IDs of people the user follows
    db_user = db.query(DBUser).options(joinedload(DBUser.following)).filter(DBUser.id == current_user.id).one()
    following_ids = {u.id for u in db_user.following}
    
    mentionable_user_ids = friend_ids_flat.union(following_ids)

    query = db.query(DBUser).filter(
        DBUser.id.in_(mentionable_user_ids),
        DBUser.username.ilike(search_term)
    ).limit(10)
    
    users = query.all()
    
    # Add the @lollms bot if it's enabled and matches the search
    if settings.get("ai_bot_enabled", False) and 'lollms'.startswith(q.lower()):
        lollms_bot = db.query(DBUser).filter(DBUser.username == 'lollms').first()
        if lollms_bot and not any(u.id == lollms_bot.id for u in users):
            users.insert(0, lollms_bot)
            
    return users