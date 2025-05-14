# backend/routers/friendships.py
import datetime
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.models.api_models import (
    FriendshipRequestCreate, FriendshipPublic, UserAuthDetails
)
from backend.database.setup import (
    User as DBUser, Friendship as DBFriendship, get_db
)
from backend.services.auth_service import get_current_db_user # get_current_db_user for direct DBUser object

friendships_router = APIRouter(prefix="/api/friendships", tags=["Friendships"])

def _get_friendship_response(friendship_db: DBFriendship, current_user_id: int) -> FriendshipPublic:
    """Helper to format DBFriendship object into FriendshipPublic response model."""
    # Determine who the 'friend' is in this relationship from current user's perspective
    if friendship_db.requester_id == current_user_id:
        friend_user = friendship_db.addressee
    else:
        friend_user = friendship_db.requester
    
    return FriendshipPublic(
        id=friendship_db.id,
        friend_username=friend_user.username, # Username of the other person in the friendship
        status=friendship_db.status,
        initiated_by_me=(friendship_db.requester_id == current_user_id), # True if current user sent the request
        created_at=friendship_db.created_at,
        updated_at=friendship_db.updated_at
    )


@friendships_router.post("/request", response_model=FriendshipPublic)
async def send_friend_request(
    request_data: FriendshipRequestCreate,
    current_user_db: DBUser = Depends(get_current_db_user), # Gets the DBUser model
    db: Session = Depends(get_db)
) -> FriendshipPublic:
    if current_user_db.username == request_data.target_username:
        raise HTTPException(status_code=400, detail="You cannot send a friend request to yourself.")

    addressee_db = db.query(DBUser).filter(DBUser.username == request_data.target_username).first()
    if not addressee_db:
        raise HTTPException(status_code=404, detail=f"User '{request_data.target_username}' not found.")

    # Check for existing friendship (pending, accepted, declined, blocked)
    existing_friendship = db.query(DBFriendship).filter(
        ((DBFriendship.requester_id == current_user_db.id) & (DBFriendship.addressee_id == addressee_db.id)) |
        ((DBFriendship.requester_id == addressee_db.id) & (DBFriendship.addressee_id == current_user_db.id))
    ).first()

    if existing_friendship:
        if existing_friendship.status == 'pending':
            # Check who initiated the pending request
            if existing_friendship.requester_id == current_user_db.id:
                raise HTTPException(status_code=400, detail="You already have a pending friend request sent to this user.")
            else:
                raise HTTPException(status_code=400, detail="This user already has a pending friend request sent to you. Please check your incoming requests.")
        elif existing_friendship.status == 'accepted':
            raise HTTPException(status_code=400, detail="You are already friends with this user.")
        elif existing_friendship.status == 'declined':
            # If previous request was declined, allow a new one by deleting old record.
            # This policy might need adjustment (e.g., cooldown period).
            db.delete(existing_friendship)
            # db.commit() # Commit deletion before adding new one, or let it be part of the same transaction
        # Handle 'blocked' status if you want specific behavior (e.g., prevent re-request if blocked)
        # For now, if status is 'blocked_...', this logic will delete and create a new 'pending'.

    new_friend_request = DBFriendship(
        requester_id=current_user_db.id,
        addressee_id=addressee_db.id,
        status='pending'
    )
    try:
        db.add(new_friend_request)
        db.commit()
        db.refresh(new_friend_request)
        # Need to load relationships for _get_friendship_response if they are not automatically loaded by refresh
        db.refresh(new_friend_request.requester) # Ensure requester is loaded
        db.refresh(new_friend_request.addressee) # Ensure addressee is loaded
        return _get_friendship_response(new_friend_request, current_user_db.id)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error sending friend request: {e}")


@friendships_router.get("/requests/incoming", response_model=List[FriendshipPublic])
async def list_incoming_friend_requests(
    current_user_db: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> List[FriendshipPublic]:
    # Eager load the 'requester' user object to get their username
    incoming_requests_db = db.query(DBFriendship).options(
        joinedload(DBFriendship.requester) # Loads the User object related via requester_id
    ).filter(
        DBFriendship.addressee_id == current_user_db.id,
        DBFriendship.status == 'pending'
    ).all()
    
    return [_get_friendship_response(req, current_user_db.id) for req in incoming_requests_db]


@friendships_router.get("/requests/outgoing", response_model=List[FriendshipPublic])
async def list_outgoing_friend_requests(
    current_user_db: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> List[FriendshipPublic]:
    # Eager load the 'addressee' user object
    outgoing_requests_db = db.query(DBFriendship).options(
        joinedload(DBFriendship.addressee) # Loads the User object related via addressee_id
    ).filter(
        DBFriendship.requester_id == current_user_db.id,
        DBFriendship.status == 'pending'
    ).all()
    
    return [_get_friendship_response(req, current_user_db.id) for req in outgoing_requests_db]


@friendships_router.put("/requests/{friendship_id}/accept", response_model=FriendshipPublic)
async def accept_friend_request(
    friendship_id: int,
    current_user_db: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> FriendshipPublic:
    # Find the request where current user is the addressee and status is pending
    request_to_accept = db.query(DBFriendship).options(
        joinedload(DBFriendship.requester), joinedload(DBFriendship.addressee) # Load both for response
    ).filter(
        DBFriendship.id == friendship_id,
        DBFriendship.addressee_id == current_user_db.id,
        DBFriendship.status == 'pending'
    ).first()

    if not request_to_accept:
        raise HTTPException(status_code=404, detail="Incoming friend request not found, already actioned, or invalid ID.")

    request_to_accept.status = 'accepted'
    request_to_accept.updated_at = datetime.datetime.now(datetime.timezone.utc)
    try:
        db.commit()
        db.refresh(request_to_accept)
        return _get_friendship_response(request_to_accept, current_user_db.id)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error accepting friend request: {e}")


@friendships_router.put("/requests/{friendship_id}/decline", response_model=FriendshipPublic)
async def decline_friend_request(
    friendship_id: int,
    current_user_db: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> FriendshipPublic:
    request_to_decline = db.query(DBFriendship).options(
        joinedload(DBFriendship.requester), joinedload(DBFriendship.addressee)
    ).filter(
        DBFriendship.id == friendship_id,
        DBFriendship.addressee_id == current_user_db.id,
        DBFriendship.status == 'pending'
    ).first()

    if not request_to_decline:
        raise HTTPException(status_code=404, detail="Incoming friend request not found, already actioned, or invalid ID.")

    request_to_decline.status = 'declined'
    request_to_decline.updated_at = datetime.datetime.now(datetime.timezone.utc)
    try:
        db.commit()
        db.refresh(request_to_decline)
        # Client might not need the full FriendshipPublic object back for a decline.
        # A simple success message might suffice, but returning object for consistency.
        return _get_friendship_response(request_to_decline, current_user_db.id)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error declining friend request: {e}")


@friendships_router.delete("/requests/{friendship_id}/cancel", status_code=200)
async def cancel_outgoing_friend_request(
    friendship_id: int, # ID of the friendship record
    current_user_db: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    # Find the request where current user is the requester and status is pending
    request_to_cancel = db.query(DBFriendship).filter(
        DBFriendship.id == friendship_id,
        DBFriendship.requester_id == current_user_db.id,
        DBFriendship.status == 'pending'
    ).first()

    if not request_to_cancel:
        raise HTTPException(status_code=404, detail="Outgoing friend request not found, already actioned, or invalid ID.")

    try:
        db.delete(request_to_cancel)
        db.commit()
        return {"message": "Friend request cancelled successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error cancelling friend request: {e}")


@friendships_router.get("", response_model=List[FriendshipPublic]) # List all accepted friends
async def list_friends(
    current_user_db: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> List[FriendshipPublic]:
    # Find all 'accepted' friendships where current user is either requester or addressee
    # Eager load both requester and addressee to determine the friend's username
    accepted_friendships_db = db.query(DBFriendship).options(
        joinedload(DBFriendship.requester),
        joinedload(DBFriendship.addressee)
    ).filter(
        ((DBFriendship.requester_id == current_user_db.id) | (DBFriendship.addressee_id == current_user_db.id)),
        DBFriendship.status == 'accepted'
    ).all()
    
    return [_get_friendship_response(f, current_user_db.id) for f in accepted_friendships_db]


@friendships_router.delete("/{friend_username}", status_code=200) # Unfriend by friend's username
async def unfriend_user(
    friend_username: str,
    current_user_db: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    if current_user_db.username == friend_username:
        raise HTTPException(status_code=400, detail="You cannot unfriend yourself.")

    friend_user_db = db.query(DBUser).filter(DBUser.username == friend_username).first()
    if not friend_user_db:
        raise HTTPException(status_code=404, detail=f"User '{friend_username}' not found.")

    # Find the accepted friendship between current user and the friend_user
    friendship_to_delete = db.query(DBFriendship).filter(
        (
            (DBFriendship.requester_id == current_user_db.id) & (DBFriendship.addressee_id == friend_user_db.id) |
            (DBFriendship.requester_id == friend_user_db.id) & (DBFriendship.addressee_id == current_user_db.id)
        ),
        DBFriendship.status == 'accepted'
    ).first()

    if not friendship_to_delete:
        raise HTTPException(status_code=404, detail=f"You are not friends with '{friend_username}', or no accepted friendship found.")

    try:
        db.delete(friendship_to_delete)
        db.commit()
        return {"message": f"You have unfriended '{friend_username}'."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error unfriending user: {e}")
