from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.discussion_group import DiscussionGroup as DBDiscussionGroup
from backend.models import UserAuthDetails
from backend.models.discussion import (
    DiscussionGroupCreate,
    DiscussionGroupPublic,
    DiscussionGroupUpdate,
)
from backend.session import get_current_active_user, get_current_db_user_from_token

discussion_groups_router = APIRouter(
    prefix="/api/discussion-groups",
    tags=["Discussion Groups"],
    dependencies=[Depends(get_current_active_user)]
)

@discussion_groups_router.get("", response_model=List[DiscussionGroupPublic])
def get_user_discussion_groups(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    return db.query(DBDiscussionGroup).filter(DBDiscussionGroup.owner_user_id == current_user.id).order_by(DBDiscussionGroup.name).all()

@discussion_groups_router.post("", response_model=DiscussionGroupPublic, status_code=status.HTTP_201_CREATED)
def create_discussion_group(
    group_data: DiscussionGroupCreate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    new_group = DBDiscussionGroup(
        name=group_data.name,
        owner_user_id=current_user.id
    )
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    return new_group

@discussion_groups_router.put("/{group_id}", response_model=DiscussionGroupPublic)
def update_discussion_group(
    group_id: str,
    group_data: DiscussionGroupUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    group = db.query(DBDiscussionGroup).filter(
        DBDiscussionGroup.id == group_id,
        DBDiscussionGroup.owner_user_id == current_user.id
    ).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found or you don't have permission to edit it.")
    
    group.name = group_data.name
    db.commit()
    db.refresh(group)
    return group

@discussion_groups_router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_discussion_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    group = db.query(DBDiscussionGroup).filter(
        DBDiscussionGroup.id == group_id,
        DBDiscussionGroup.owner_user_id == current_user.id
    ).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found or you don't have permission to delete it.")
    
    db.delete(group)
    db.commit()