# backend/routers/groups.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from typing import List

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.group import Group as DBGroup
from backend.db.models.social import Post as DBPost, Comment as DBComment
from backend.db.base import FriendshipStatus
from backend.db.utils import get_friendship_record
from backend.models import UserAuthDetails
from backend.models.social import PostPublic
from backend.models.group import GroupCreate, GroupUpdate, GroupPublic, MemberUpdate
from backend.session import get_current_db_user_from_token

groups_router = APIRouter(
    prefix="/api/groups",
    tags=["Groups"],
    dependencies=[Depends(get_current_db_user_from_token)]
)

@groups_router.get("", response_model=List[GroupPublic])
def get_my_groups(
    current_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    return current_user.groups

@groups_router.post("", response_model=GroupPublic, status_code=status.HTTP_201_CREATED)
def create_group(
    group_data: GroupCreate,
    current_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    new_group = DBGroup(
        display_name=group_data.display_name,
        description=group_data.description,
        owner_id=current_user.id
    )
    new_group.members.append(current_user)
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    return new_group

@groups_router.get("/{group_id}", response_model=GroupPublic)
def get_group_details(
    group_id: int,
    current_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    group = db.query(DBGroup).options(joinedload(DBGroup.owner), joinedload(DBGroup.members)).filter(DBGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if current_user not in group.members and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not a member of this group")
    return group

@groups_router.put("/{group_id}", response_model=GroupPublic)
def update_group(
    group_id: int,
    group_data: GroupUpdate,
    current_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    group = db.query(DBGroup).filter(DBGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only the group owner can edit it")

    update_data = group_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(group, key, value)
    
    db.commit()
    db.refresh(group)
    return group

@groups_router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int,
    current_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    group = db.query(DBGroup).filter(DBGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only the group owner can delete it")
    
    db.delete(group)
    db.commit()

@groups_router.post("/{group_id}/members", response_model=GroupPublic)
def add_member_to_group(
    group_id: int,
    member_data: MemberUpdate,
    current_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    group = db.query(DBGroup).filter(DBGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only the group owner can add members")
    
    user_to_add = db.query(DBUser).filter(DBUser.id == member_data.user_id).first()
    if not user_to_add:
        raise HTTPException(status_code=404, detail="User to add not found")
    
    friendship = get_friendship_record(db, current_user.id, user_to_add.id)
    if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
        raise HTTPException(status_code=400, detail="You can only add friends to a group")

    if user_to_add in group.members:
        raise HTTPException(status_code=400, detail="User is already a member of this group")

    group.members.append(user_to_add)
    db.commit()
    db.refresh(group)
    return group

@groups_router.delete("/{group_id}/members/{user_id}", response_model=GroupPublic)
def remove_member_from_group(
    group_id: int,
    user_id: int,
    current_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    group = db.query(DBGroup).filter(DBGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    user_to_remove = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_remove or user_to_remove not in group.members:
        raise HTTPException(status_code=404, detail="User is not a member of this group")

    is_owner = group.owner_id == current_user.id
    is_self = user_id == current_user.id

    if not is_owner and not is_self:
        raise HTTPException(status_code=403, detail="You can only remove yourself or be removed by the owner")

    if is_owner and user_id == group.owner_id:
        raise HTTPException(status_code=400, detail="Owner cannot be removed. Transfer ownership or delete the group.")
    
    group.members.remove(user_to_remove)
    db.commit()
    db.refresh(group)
    return group

@groups_router.get("/{group_id}/feed", response_model=List[PostPublic])
def get_group_feed(
    group_id: int,
    current_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    from backend.routers.social import get_post_public
    
    group = db.query(DBGroup).filter(DBGroup.id == group_id).first()
    if not group or current_user not in group.members:
        raise HTTPException(status_code=403, detail="You are not a member of this group")

    # Filter flagged posts
    posts_db = db.query(DBPost).options(
        joinedload(DBPost.author),
        joinedload(DBPost.comments).joinedload(DBComment.author)
    ).filter(
        DBPost.group_id == group_id,
        DBPost.moderation_status != 'flagged'
    ).order_by(DBPost.created_at.desc()).all()

    return [get_post_public(db, post, current_user.id) for post in posts_db]
