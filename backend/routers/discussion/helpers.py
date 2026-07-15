from typing import Tuple, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from lollms_client import LollmsDiscussion

from backend.db.models.user import User as DBUser
from backend.db.models.discussion import SharedDiscussionLink as DBSharedDiscussionLink
from backend.models.user import UserAuthDetails
from backend.discussion import get_user_discussion
from backend.session import get_user_lollms_client

async def get_discussion_and_owner_for_request(
    discussion_id: str,
    current_user: UserAuthDetails,
    db: Session,
    required_permission: str = 'view'
) -> Tuple[LollmsDiscussion, str, str, Optional[DBUser]]:
    """
    Retrieves a discussion object. Handles owned chats, notebooks, and shared discussions.
    Ensures correct LollmsDiscussion instance is constructed with full context capability.
    """
    from backend.discussion_manager import get_user_discussion_manager
    dm_local = get_user_discussion_manager(current_user.username)

    # 1. Active Owner Session check
    if dm_local.discussion_exists(discussion_id):
        discussion_obj = get_user_discussion(current_user.username, discussion_id)
        owner_db = db.query(DBUser).filter(DBUser.id == current_user.id).first()
        return discussion_obj, current_user.username, 'owner', owner_db

    # 2. Check Shared Discussion Links
    shared_link = db.query(DBSharedDiscussionLink).options(
        joinedload(DBSharedDiscussionLink.owner)
    ).filter(
        DBSharedDiscussionLink.discussion_id == discussion_id,
        DBSharedDiscussionLink.shared_with_user_id == current_user.id
    ).first()

    if shared_link:
        permission_hierarchy = {"view": ["view", "interact"], "interact": ["interact"]}
        user_permission = shared_link.permission_level
        if required_permission != 'owner' and user_permission not in permission_hierarchy.get(required_permission, []):
            raise HTTPException(status_code=403, detail=f"You need '{required_permission}' permission for this discussion.")

        owner_username = shared_link.owner.username
        # Shared sessions utilize the viewer's LollmsClient for token counting & model constraints
        lc = get_user_lollms_client(current_user.username)
        shared_discussion_obj = get_user_discussion(owner_username, discussion_id, lollms_client=lc)

        if not shared_discussion_obj:
            raise HTTPException(status_code=404, detail="The shared discussion source was not found.")

        return shared_discussion_obj, owner_username, user_permission, shared_link.owner

    # 3. Dynamic Creation Gate for New Conversations
    if required_permission in ['owner', 'interact']:
        discussion_obj = get_user_discussion(current_user.username, discussion_id, create_if_missing=True)
        if discussion_obj:
            owner_db = db.query(DBUser).filter(DBUser.id == current_user.id).first()
            return discussion_obj, current_user.username, 'owner', owner_db

    raise HTTPException(status_code=404, detail="Discussion not found or access denied.")
