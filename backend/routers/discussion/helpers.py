# backend/routers/discussion/helpers.py
from typing import Tuple, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from lollms_client import LollmsDiscussion

from backend.db.models.user import User as DBUser
from backend.db.models.discussion import SharedDiscussionLink as DBSharedDiscussionLink
from backend.models import UserAuthDetails
from backend.discussion import get_user_discussion

async def get_discussion_and_owner_for_request(
    discussion_id: str,
    current_user: UserAuthDetails,
    db: Session,
    required_permission: str = 'view'
) -> Tuple[LollmsDiscussion, str, str, Optional[DBUser]]:
    """
    Retrieves a discussion object, its owner's username, permission level, and owner's DB object.
    Handles both owned and shared discussions.
    """
    # 1. Check if the current user owns the discussion.
    discussion_obj = get_user_discussion(current_user.username, discussion_id)
    if discussion_obj:
        owner_db = db.query(DBUser).filter(DBUser.id == current_user.id).first()
        return discussion_obj, current_user.username, 'owner', owner_db

    # 2. If not found locally, check if it's shared with the current user.
    shared_link = db.query(DBSharedDiscussionLink).options(
        joinedload(DBSharedDiscussionLink.owner)
    ).filter(
        DBSharedDiscussionLink.discussion_id == discussion_id,
        DBSharedDiscussionLink.shared_with_user_id == current_user.id
    ).first()

    if not shared_link:
        raise HTTPException(status_code=404, detail="Discussion not found or you don't have access.")

    # 3. Check permissions.
    permission_hierarchy = {"view": ["view", "interact"], "interact": ["interact"]}
    user_permission = shared_link.permission_level
    if required_permission != 'owner' and user_permission not in permission_hierarchy.get(required_permission, []):
        raise HTTPException(status_code=403, detail=f"You need '{required_permission}' permission for this discussion.")
    
    owner_username = shared_link.owner.username
    shared_discussion_obj = get_user_discussion(owner_username, discussion_id)
    if not shared_discussion_obj:
        raise HTTPException(status_code=404, detail="The shared discussion seems to have been deleted by its owner.")
    
    return shared_discussion_obj, owner_username, user_permission, shared_link.owner