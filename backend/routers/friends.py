import traceback
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from backend.db import get_db
from backend.db.models.user import User as DBUser, Friendship
from backend.db.models.connections import WebSocketConnection
from backend.db.base import FriendshipStatus
from backend.models import FriendPublic, FriendRequestCreate, FriendshipRequestPublic, FriendshipAction
from backend.session import get_current_db_user_from_token
from backend.ws_manager import manager

friends_router = APIRouter(prefix="/api/friends", tags=["Friends Management"])

class FriendPublicWithStatus(FriendPublic):
    status: str = "disconnected" # 'connected', 'absent', 'disconnected'

@friends_router.get("", response_model=List[FriendPublicWithStatus])
async def get_my_friends(
    current_db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    friendships_db = db.query(Friendship).options(
        joinedload(Friendship.user1), joinedload(Friendship.user2)
    ).filter(
        or_(Friendship.user1_id == current_db_user.id, Friendship.user2_id == current_db_user.id),
        Friendship.status == FriendshipStatus.ACCEPTED
    ).all()

    # Get online users
    online_user_ids = {r[0] for r in db.query(WebSocketConnection.user_id).distinct().all()}
    
    now = datetime.now(timezone.utc)

    friends_list = []
    for fs in friendships_db:
        friend_user = fs.user2 if fs.user1_id == current_db_user.id else fs.user1
        if friend_user:
            # Determine status
            user_status = "disconnected"
            if friend_user.id in online_user_ids:
                user_status = "connected"
                if friend_user.last_activity_at:
                    last_active = friend_user.last_activity_at
                    if last_active.tzinfo is None:
                        last_active = last_active.replace(tzinfo=timezone.utc)
                    
                    # If inactive for more than 5 minutes, mark as absent
                    if (now - last_active) > timedelta(minutes=5):
                        user_status = "absent"

            friends_list.append(FriendPublicWithStatus(
                id=friend_user.id,
                username=friend_user.username,
                icon=friend_user.icon,
                friendship_id=fs.id,
                status_with_current_user=fs.status,
                status=user_status
            ))
    
    # Sort by status (Connected first) then name
    status_order = {"connected": 0, "absent": 1, "disconnected": 2}
    friends_list.sort(key=lambda f: (status_order[f.status], f.username.lower()))
    
    return friends_list


@friends_router.post("/request", response_model=FriendshipRequestPublic, status_code=201)
async def send_friend_request(
    request_data: FriendRequestCreate,
    current_db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> FriendshipRequestPublic:
    if current_db_user.username == request_data.target_username:
        raise HTTPException(status_code=400, detail="You cannot send a friend request to yourself.")

    target_user = db.query(DBUser).filter(DBUser.username == request_data.target_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User '{request_data.target_username}' not found.")

    user1_id, user2_id = sorted((current_db_user.id, target_user.id))
    existing_friendship = db.query(Friendship).filter(Friendship.user1_id == user1_id, Friendship.user2_id == user2_id).first()

    if existing_friendship:
        if existing_friendship.status == FriendshipStatus.ACCEPTED:
            raise HTTPException(status_code=400, detail="You are already friends.")
        elif existing_friendship.status == FriendshipStatus.PENDING:
            if existing_friendship.action_user_id == current_db_user.id:
                raise HTTPException(status_code=400, detail="Request already sent.")
            else:
                raise HTTPException(status_code=400, detail="User already sent you a request.")
        
        existing_friendship.status = FriendshipStatus.PENDING
        existing_friendship.action_user_id = current_db_user.id
        db_item = existing_friendship
    else:
        db_item = Friendship(user1_id=user1_id, user2_id=user2_id, status=FriendshipStatus.PENDING, action_user_id=current_db_user.id)
        db.add(db_item)
    
    db.commit()
    db.refresh(db_item)
    
    resp = FriendshipRequestPublic(friendship_id=db_item.id, requesting_user_id=current_db_user.id, requesting_username=current_db_user.username, requested_at=db_item.updated_at, status=db_item.status)
    manager.send_personal_message_sync({"type": "new_friend_request", "data": resp.model_dump(mode="json")}, target_user.id)
    return resp

@friends_router.get("/requests/pending", response_model=List[FriendshipRequestPublic])
async def get_pending_requests(current_db_user: DBUser = Depends(get_current_db_user_from_token), db: Session = Depends(get_db)):
    reqs = db.query(Friendship).options(joinedload(Friendship.user1), joinedload(Friendship.user2)).filter(
        or_(Friendship.user1_id == current_db_user.id, Friendship.user2_id == current_db_user.id),
        Friendship.action_user_id != current_db_user.id, Friendship.status == FriendshipStatus.PENDING
    ).all()
    res = []
    for r in reqs:
        req_user = r.user1 if r.user2_id == current_db_user.id else r.user2
        res.append(FriendshipRequestPublic(friendship_id=r.id, requesting_user_id=req_user.id, requesting_username=req_user.username, requested_at=r.updated_at, status=r.status))
    return res

@friends_router.put("/requests/{friendship_id}", response_model=FriendPublic)
async def respond_request(friendship_id: int, data: FriendshipAction, current_db_user: DBUser = Depends(get_current_db_user_from_token), db: Session = Depends(get_db)):
    fs = db.query(Friendship).filter(Friendship.id == friendship_id).first()
    if not fs: raise HTTPException(404, "Request not found")
    
    if data.action == 'accept':
        fs.status = FriendshipStatus.ACCEPTED
        fs.action_user_id = current_db_user.id
        db.commit()
        friend = fs.user1 if fs.user2_id == current_db_user.id else fs.user2
        return FriendPublic(id=friend.id, username=friend.username, icon=friend.icon, friendship_id=fs.id, status_with_current_user=fs.status)
    elif data.action == 'reject':
        db.delete(fs)
        db.commit()
        raise HTTPException(200, "Rejected")
    raise HTTPException(400, "Invalid action")

@friends_router.delete("/{friend_id}", status_code=200)
async def remove_friend(friend_id: int, current_db_user: DBUser = Depends(get_current_db_user_from_token), db: Session = Depends(get_db)):
    # logic to remove
    u1, u2 = sorted((current_db_user.id, friend_id))
    fs = db.query(Friendship).filter(Friendship.user1_id==u1, Friendship.user2_id==u2).first()
    if fs:
        db.delete(fs)
        db.commit()
    return {"message": "Removed"}

@friends_router.get("/blocked", response_model=List[FriendPublic])
async def get_blocked(current_db_user: DBUser = Depends(get_current_db_user_from_token), db: Session = Depends(get_db)):
    blocked_records = db.query(Friendship).filter(
        or_(
            (Friendship.user1_id == current_db_user.id) & (Friendship.status == FriendshipStatus.BLOCKED_BY_USER1),
            (Friendship.user2_id == current_db_user.id) & (Friendship.status == FriendshipStatus.BLOCKED_BY_USER2)
        )
    ).all()
    blocked_users = []
    for fs in blocked_records:
        blocked_user = fs.user2 if fs.user1_id == current_db_user.id else fs.user1
        blocked_users.append(FriendPublic(
            id=blocked_user.id,
            username=blocked_user.username,
            icon=blocked_user.icon,
            friendship_id=fs.id,
            status_with_current_user=fs.status
        ))
    return blocked_users

@friends_router.put("/block/{user_id}")
async def block(user_id: int, current_db_user: DBUser = Depends(get_current_db_user_from_token), db: Session = Depends(get_db)):
    u1, u2 = sorted((current_db_user.id, user_id))
    fs = db.query(Friendship).filter(Friendship.user1_id==u1, Friendship.user2_id==u2).first()
    if not fs:
        fs = Friendship(user1_id=u1, user2_id=u2)
        db.add(fs)
    
    if current_db_user.id == u1:
        fs.status = FriendshipStatus.BLOCKED_BY_USER1
    else:
        fs.status = FriendshipStatus.BLOCKED_BY_USER2
    
    fs.action_user_id = current_db_user.id
    db.commit()
    return {"message": "User blocked"}

@friends_router.put("/unblock/{user_id}")
async def unblock(user_id: int, current_db_user: DBUser = Depends(get_current_db_user_from_token), db: Session = Depends(get_db)):
    u1, u2 = sorted((current_db_user.id, user_id))
    fs = db.query(Friendship).filter(Friendship.user1_id==u1, Friendship.user2_id==u2).first()
    if fs:
        db.delete(fs)
        db.commit()
    return {"message": "User unblocked"}
