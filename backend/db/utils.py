from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.db.models.user import Friendship

def get_friendship_record(db: Session, user_id: int, other_user_id: int):
    # The filter logic needs to handle cases where the user pair is stored in either order
    user1_id_ordered, user2_id_ordered = sorted((user_id, other_user_id))
    
    record = db.query(Friendship).filter(
        Friendship.user1_id == user1_id_ordered,
        Friendship.user2_id == user2_id_ordered
    ).first()
    return record