from typing import Tuple, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from lollms_client import LollmsDiscussion

from backend.db.models.user import User as DBUser
from backend.db.models.discussion import SharedDiscussionLink as DBSharedDiscussionLink
from backend.db.models.notebook import Notebook as DBNotebook
from backend.models.user import UserAuthDetails
from backend.discussion import get_user_discussion

async def get_discussion_and_owner_for_request(
    discussion_id: str,
    current_user: UserAuthDetails,
    db: Session,
    required_permission: str = 'view'
) -> Tuple[LollmsDiscussion, str, str, Optional[DBUser]]:
    """
    Retrieves a discussion object. Handles owned chats, notebooks, and shared discussions.
    """
    # 1. Check owned chat
    discussion_obj = get_user_discussion(current_user.username, discussion_id)
    if discussion_obj:
        owner_db = db.query(DBUser).filter(DBUser.id == current_user.id).first()
        return discussion_obj, current_user.username, 'owner', owner_db

    # 2. Check if it's a Notebook (Allow access to its shadow discussion)
    notebook = db.query(DBNotebook).filter(DBNotebook.id == discussion_id, DBNotebook.owner_user_id == current_user.id).first()
    if notebook:
        discussion_obj = get_user_discussion(current_user.username, discussion_id, create_if_missing=True)
        owner_db = db.query(DBUser).filter(DBUser.id == current_user.id).first()
        return discussion_obj, current_user.username, 'owner', owner_db

    # 3. Check shared discussions
    shared_link = db.query(DBSharedDiscussionLink).options(
        joinedload(DBSharedDiscussionLink.owner)
    ).filter(
        DBSharedDiscussionLink.discussion_id == discussion_id,
        DBSharedDiscussionLink.shared_with_user_id == current_user.id
    ).first()

    if not shared_link:
        raise HTTPException(status_code=404, detail="Discussion not found or you don't have access.")

    permission_hierarchy = {"view": ["view", "interact"], "interact": ["interact"]}
    user_permission = shared_link.permission_level
    if required_permission != 'owner' and user_permission not in permission_hierarchy.get(required_permission, []):
        raise HTTPException(status_code=403, detail=f"You need '{required_permission}' permission for this discussion.")
    
    owner_username = shared_link.owner.username
    shared_discussion_obj = get_user_discussion(owner_username, discussion_id)
    if not shared_discussion_obj:
        raise HTTPException(status_code=404, detail="The shared discussion was deleted.")
    
    return shared_discussion_obj, owner_username, user_permission, shared_link.owner
