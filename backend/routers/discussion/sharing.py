# backend/routers/discussion/sharing.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.discussion import SharedDiscussionLink as DBSharedDiscussionLink
from backend.models import UserAuthDetails, DiscussionShareRequest, SharedDiscussionInfo, DiscussionInfo
from backend.session import get_current_active_user
from backend.discussion import get_user_discussion
from backend.ws_manager import manager


def build_discussion_sharing_router(router: APIRouter):
    @router.get("/shared", response_model=List[DiscussionInfo])
    async def list_discussions_shared_with_me(
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        shared_links = db.query(DBSharedDiscussionLink).options(
            joinedload(DBSharedDiscussionLink.owner)
        ).filter(
            DBSharedDiscussionLink.shared_with_user_id == current_user.id
        ).order_by(DBSharedDiscussionLink.shared_at.desc()).all()

        return [
            DiscussionInfo(
                id=link.discussion_id,
                title=link.discussion_title,
                is_starred=False,
                last_activity_at=link.shared_at,
                owner_username=link.owner.username,
                permission_level=link.permission_level,
                share_id=link.id
            ) for link in shared_links
        ]

    @router.post("/{discussion_id}/share", status_code=status.HTTP_201_CREATED)
    async def share_discussion(
        discussion_id: str,
        share_request: DiscussionShareRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        owner_user_db = db.query(DBUser).filter(DBUser.id == current_user.id).first()
        discussion_obj = get_user_discussion(current_user.username, discussion_id)
        if not discussion_obj:
            raise HTTPException(status_code=404, detail="Discussion not found.")

        target_user_db = db.query(DBUser).filter(DBUser.username == share_request.target_username).first()
        if not target_user_db:
            raise HTTPException(status_code=404, detail=f"Target user '{share_request.target_username}' not found.")
        
        if owner_user_db.id == target_user_db.id:
            raise HTTPException(status_code=400, detail="You cannot share a discussion with yourself.")

        existing_link = db.query(DBSharedDiscussionLink).filter_by(
            discussion_id=discussion_id,
            owner_user_id=owner_user_db.id,
            shared_with_user_id=target_user_db.id
        ).first()

        if existing_link:
            if existing_link.permission_level != share_request.permission_level:
                existing_link.permission_level = share_request.permission_level
                db.commit()
                return {"message": f"Permission updated for {target_user_db.username}."}
            raise HTTPException(status_code=409, detail="Discussion already shared with this user with the same permission.")

        new_link = DBSharedDiscussionLink(
            discussion_id=discussion_id,
            discussion_title=discussion_obj.metadata.get('title', 'Untitled Discussion'),
            owner_user_id=owner_user_db.id,
            shared_with_user_id=target_user_db.id,
            permission_level=share_request.permission_level
        )
        try:
            db.add(new_link)
            db.commit()
            await manager.send_personal_message(
                {"type": "new_shared_discussion", "data": {"from_user": current_user.username, "discussion_title": new_link.discussion_title}},
                target_user_db.id
            )
            return {"message": f"Discussion shared with {target_user_db.username}."}
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="A sharing conflict occurred.")
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {e}")

    @router.delete("/{discussion_id}/share/{share_id}", status_code=status.HTTP_200_OK)
    async def unshare_discussion(
        discussion_id: str,
        share_id: int,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        link_to_delete = db.query(DBSharedDiscussionLink).filter_by(
            id=share_id,
            discussion_id=discussion_id,
            owner_user_id=current_user.id
        ).first()

        if not link_to_delete:
            raise HTTPException(status_code=404, detail="Share link not found or you are not the owner.")
        
        target_user_id = link_to_delete.shared_with_user_id
        db.delete(link_to_delete)
        db.commit()
        await manager.send_personal_message(
            {"type": "discussion_unshared", "data": {"discussion_id": discussion_id, "from_user": current_user.username}},
            target_user_id
        )
        return {"message": "Sharing revoked successfully."}

    @router.get("/{discussion_id}/shared-with", response_model=List[SharedDiscussionInfo])
    async def get_who_discussion_is_shared_with(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion_obj = get_user_discussion(current_user.username, discussion_id)
        if not discussion_obj:
            raise HTTPException(status_code=404, detail="Discussion not found.")

        links = db.query(DBSharedDiscussionLink).options(
            joinedload(DBSharedDiscussionLink.shared_with_user)
        ).filter_by(
            discussion_id=discussion_id,
            owner_user_id=current_user.id
        ).all()
        
        response = []
        for link in links:
            shared_user = link.shared_with_user
            if shared_user:
                response.append(
                    SharedDiscussionInfo(
                        share_id=link.id,
                        discussion_id=link.discussion_id,
                        discussion_title=link.discussion_title,
                        permission_level=link.permission_level,
                        shared_at=link.shared_at,
                        owner_id=current_user.id,
                        owner_username=current_user.username,
                        owner_icon=current_user.icon
                    )
                )
        return response