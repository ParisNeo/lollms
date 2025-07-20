import traceback
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, and_

from backend.db import get_db
from backend.db.base import FriendshipStatus
from backend.db.utils import get_friendship_record
from backend.db.models.user import User as DBUser, Friendship
from backend.models import (
    UserAuthDetails,
    FriendRequestCreate,
    FriendshipRequestPublic,
    FriendPublic,
    FriendshipAction
)
from backend.session import get_current_db_user_from_token
from backend.ws_manager import manager
from typing import List, Dict

friends_router = APIRouter(prefix="/api/friends", tags=["Friends Management"])

def get_friend_public_from_friendship(friendship: Friendship, current_user_id: int) -> FriendPublic:
    friend_user_obj = None
    if friendship.user1_id == current_user_id:
        friend_user_obj = friendship.user2
    elif friendship.user2_id == current_user_id:
        friend_user_obj = friendship.user1
    
    if not friend_user_obj:
        raise ValueError("Friendship record does not involve the current user.")

    return FriendPublic(
        id=friend_user_obj.id,
        username=friend_user_obj.username,
        friendship_id=friendship.id,
        status_with_current_user=friendship.status
    )

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

    existing_friendship = db.query(Friendship).filter(
        Friendship.user1_id == user1_id,
        Friendship.user2_id == user2_id
    ).first()

    if existing_friendship:
        if existing_friendship.status == FriendshipStatus.ACCEPTED:
            raise HTTPException(status_code=400, detail="You are already friends with this user.")
        elif existing_friendship.status == FriendshipStatus.PENDING:
            if existing_friendship.action_user_id == current_db_user.id:
                raise HTTPException(status_code=400, detail="You have already sent a friend request to this user.")
            else:
                raise HTTPException(status_code=400, detail="This user has already sent you a friend request. Please respond to it.")
        elif existing_friendship.status.name.startswith('BLOCKED'):
            raise HTTPException(status_code=403, detail="A block exists between you and this user.")
        
        existing_friendship.status = FriendshipStatus.PENDING
        existing_friendship.action_user_id = current_db_user.id
        db_friendship_to_return = existing_friendship
    else:
        new_friendship = Friendship(
            user1_id=user1_id,
            user2_id=user2_id,
            status=FriendshipStatus.PENDING,
            action_user_id=current_db_user.id
        )
        db.add(new_friendship)
        db_friendship_to_return = new_friendship
    
    try:
        db.commit()
        db.refresh(db_friendship_to_return)
        
        response_data = FriendshipRequestPublic(
            friendship_id=db_friendship_to_return.id,
            requesting_user_id=current_db_user.id,
            requesting_username=current_db_user.username,
            requested_at=db_friendship_to_return.updated_at,
            status=db_friendship_to_return.status
        )

        notification_payload = {
            "type": "new_friend_request",
            "data": response_data.model_dump(mode="json")
        }
        await manager.send_personal_message(notification_payload, target_user.id)

        return response_data
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Friendship request conflict.")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@friends_router.get("/requests/pending", response_model=List[FriendshipRequestPublic])
async def get_pending_friend_requests(
    current_db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> List[FriendshipRequestPublic]:
    pending_requests_db = db.query(Friendship).options(
        joinedload(Friendship.user1),
        joinedload(Friendship.user2)
    ).filter(
        or_(
            Friendship.user1_id == current_db_user.id,
            Friendship.user2_id == current_db_user.id
        ),
        Friendship.action_user_id != current_db_user.id,
        Friendship.status == FriendshipStatus.PENDING
    ).all()

    response_list = []
    for req in pending_requests_db:
        requester = req.user1 if req.user2_id == current_db_user.id else req.user2
        if requester:
            response_list.append(FriendshipRequestPublic(
                friendship_id=req.id,
                requesting_user_id=requester.id,
                requesting_username=requester.username,
                requested_at=req.updated_at,
                status=req.status
            ))
    return response_list

@friends_router.put("/requests/{friendship_id}", response_model=FriendPublic)
async def respond_to_friend_request(
    friendship_id: int,
    response_data: FriendshipAction,
    current_db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> FriendPublic:
    friendship = db.query(Friendship).filter(Friendship.id == friendship_id).first()

    if not friendship:
        raise HTTPException(status_code=404, detail="Friend request not found.")

    is_recipient = (friendship.user1_id == current_db_user.id and friendship.action_user_id != current_db_user.id) or \
                   (friendship.user2_id == current_db_user.id and friendship.action_user_id != current_db_user.id)

    if not is_recipient or friendship.status != FriendshipStatus.PENDING:
        raise HTTPException(status_code=403, detail="Not a valid pending request for you to respond to.")

    action = response_data.action.lower()
    if action == "accept":
        friendship.status = FriendshipStatus.ACCEPTED
        friendship.action_user_id = current_db_user.id
    elif action == "reject":
        db.delete(friendship)
        db.commit()
        raise HTTPException(status_code=200, detail="Friend request rejected.")
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'accept' or 'reject'.")

    try:
        db.commit()
        db.refresh(friendship)
        db.refresh(friendship, attribute_names=['user1', 'user2'])
        return get_friend_public_from_friendship(friendship, current_db_user.id)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@friends_router.get("", response_model=List[FriendPublic])
async def get_my_friends(
    current_db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> List[FriendPublic]:
    friendships_db = db.query(Friendship).options(
        joinedload(Friendship.user1), joinedload(Friendship.user2)
    ).filter(
        or_(Friendship.user1_id == current_db_user.id, Friendship.user2_id == current_db_user.id),
        Friendship.status == FriendshipStatus.ACCEPTED
    ).order_by(Friendship.updated_at.desc()).all()

    friends_list = []
    for fs in friendships_db:
        try:
            friends_list.append(get_friend_public_from_friendship(fs, current_db_user.id))
        except ValueError:
            pass 
    
    friends_list.sort(key=lambda f: f.username.lower())
    return friends_list

@friends_router.delete("/{friend_user_id}", status_code=200)
async def remove_friend_or_cancel_request(
    friend_user_id: int,
    current_db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    other_user = db.query(DBUser).filter(DBUser.id == friend_user_id).first()

    if not other_user:
        raise HTTPException(status_code=404, detail="Target user not found.")
    if other_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="Cannot perform this action on yourself.")

    friendship = get_friendship_record(db, current_db_user.id, other_user.id)

    if not friendship:
        raise HTTPException(status_code=404, detail="No friendship or request found with this user.")

    action_taken = ""
    if friendship.status == FriendshipStatus.ACCEPTED:
        db.delete(friendship)
        action_taken = "unfriended"
    elif friendship.status == FriendshipStatus.PENDING and friendship.action_user_id == current_db_user.id:
        db.delete(friendship)
        action_taken = "friend request cancelled"
    else:
        raise HTTPException(status_code=400, detail=f"Cannot perform this action on current friendship status: {friendship.status.name}")

    try:
        db.commit()
        return {"message": f"Successfully {action_taken} user '{other_user.username}'."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@friends_router.put("/block/{user_id}", response_model=FriendPublic)
async def block_user(
    user_id: int,
    current_db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> FriendPublic:
    other_user = db.query(DBUser).filter(DBUser.id == user_id).first()

    if not other_user:
        raise HTTPException(status_code=404, detail="Target user not found.")
    if other_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="You cannot block yourself.")

    friendship = get_friendship_record(db, current_db_user.id, other_user.id)
    
    user1_id_ordered, user2_id_ordered = sorted((current_db_user.id, other_user.id))

    if not friendship:
        friendship = Friendship(
            user1_id=user1_id_ordered,
            user2_id=user2_id_ordered,
            action_user_id=current_db_user.id
        )
        db.add(friendship)
    else:
        friendship.action_user_id = current_db_user.id

    if user1_id_ordered == current_db_user.id:
        friendship.status = FriendshipStatus.BLOCKED_BY_USER1
    else:
        friendship.status = FriendshipStatus.BLOCKED_BY_USER2
    
    try:
        db.commit()
        db.refresh(friendship)
        db.refresh(friendship, attribute_names=['user1', 'user2'])
        return get_friend_public_from_friendship(friendship, current_db_user.id)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@friends_router.put("/unblock/{user_id}", status_code=200)
async def unblock_user(
    user_id: int,
    current_db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    other_user = db.query(DBUser).filter(DBUser.id == user_id).first()

    if not other_user:
        raise HTTPException(status_code=404, detail="Target user not found.")

    friendship = get_friendship_record(db, current_db_user.id, other_user.id)
    if not friendship:
        raise HTTPException(status_code=404, detail="No relationship record found with this user to unblock.")

    is_blocker = (friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and friendship.user1_id == current_db_user.id) or \
                 (friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and friendship.user2_id == current_db_user.id)

    if not is_blocker:
        raise HTTPException(status_code=400, detail="You have not blocked this user.")

    db.delete(friendship)
    try:
        db.commit()
        return {"message": f"User '{other_user.username}' unblocked. Any previous friendship status is cleared."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")