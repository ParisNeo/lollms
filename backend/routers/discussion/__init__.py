# backend/routers/discussion/__init__.py
# Standard Library Imports
import base64
import io
import json
import re
import shutil
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import threading

# Third-Party Imports
import fitz  # PyMuPDF
from fastapi import (
    APIRouter, BackgroundTasks, Depends, HTTPException, Query)
from sqlalchemy.orm import Session, joinedload
from ascii_colors import ASCIIColors, trace_exception

# Local Application Imports
from backend.db import get_db
from backend.db.models.user import (User as DBUser, UserMessageGrade,
                                     UserStarredDiscussion)
from backend.discussion import get_user_discussion, get_user_discussion_manager
from backend.models import (UserAuthDetails, DiscussionBranchSwitchRequest,
                            DiscussionInfo, DiscussionTitleUpdate, MessageOutput
                            )
from backend.session import (get_current_active_user,
                             get_user_discussion_assets_path,
                            )
from backend.routers.discussion.artefacts import build_artefacts_router
from backend.routers.discussion.memories import build_memories_router
from backend.routers.discussion.context import build_context_router
from backend.routers.discussion.data_zone import build_datazone_router
from backend.routers.discussion.message import build_message_router
from backend.routers.discussion.rag import build_rag_router
from backend.routers.discussion.generation.llm import build_llm_generation_router
from backend.routers.discussion.generation.tti import build_tti_generation_router
from backend.routers.discussion.sharing import build_discussion_sharing_router
from backend.routers.discussion.utils import build_utils_router
from backend.db.models.discussion import SharedDiscussionLink
from .helpers import get_discussion_and_owner_for_request

def build_discussions_router():
    # safe_store is needed for RAG callbacks
    router = APIRouter(prefix="/api/discussions", tags=["Discussions"])

    # import 
    build_artefacts_router(router)
    build_memories_router(router)
    build_context_router(router)
    build_datazone_router(router)
    build_rag_router(router)
    build_message_router(router)
    build_llm_generation_router(router)
    build_tti_generation_router(router)
    build_discussion_sharing_router(router)
    build_utils_router(router)



    @router.get("", response_model=List[DiscussionInfo])
    async def list_all_discussions(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[DiscussionInfo]:
        username = current_user.username
        db_user = db.query(DBUser).filter(DBUser.username == username).one()
        dm = get_user_discussion_manager(username)

        discussions_from_db = dm.list_discussions()
        starred_ids = {star.discussion_id for star in db.query(UserStarredDiscussion.discussion_id).filter(UserStarredDiscussion.user_id == db_user.id).all()}

        infos = []
        for disc_data in discussions_from_db:
            try:
                disc_id = disc_data['id']
                metadata = disc_data.get('discussion_metadata', {})
                
                image_data = metadata.get("discussion_images", [])
                discussion_images_b64 = []
                active_discussion_images = []

                if isinstance(image_data, dict) and 'data' in image_data:
                    discussion_images_b64 = image_data.get('data', [])
                    active_discussion_images = image_data.get('active', [])
                elif isinstance(image_data, list):
                    for item in image_data:
                        if isinstance(item, dict) and 'data' in item:
                            discussion_images_b64.append(item['data'])
                            active_discussion_images.append(item.get('active', True))
                        elif isinstance(item, str):
                            discussion_images_b64.append(item)
                            active_discussion_images.append(True)

                info = DiscussionInfo(
                    id=disc_id,
                    title=metadata.get('title', f"Discussion {disc_id[:8]}"),
                    is_starred=(disc_id in starred_ids),
                    rag_datastore_ids=metadata.get('rag_datastore_ids'),
                    active_tools=metadata.get('active_tools', []),
                    active_branch_id=disc_data.get('active_branch_id'),
                    created_at=disc_data.get('created_at'),
                    last_activity_at=disc_data.get('updated_at'),
                    discussion_images=discussion_images_b64,
                    active_discussion_images=active_discussion_images
                )
                infos.append(info)
            except Exception as e:
                trace_exception(e)
        return sorted(infos, key=lambda d: d.last_activity_at or datetime.min, reverse=True)

    @router.get("/{discussion_id}", response_model=List[MessageOutput])
    async def get_messages_for_discussion(discussion_id: str, branch_id: Optional[str] = Query(None), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[MessageOutput]:
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)

        branch_tip_to_load = branch_id or discussion_obj.active_branch_id
        messages_in_branch = discussion_obj.get_branch(branch_tip_to_load)

        db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
        user_grades = {g.message_id: g.grade for g in db.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id).all()}

        all_messages_in_discussion = discussion_obj.get_all_messages_flat()
        children_map = {}
        for msg_obj in all_messages_in_discussion:
            if msg_obj.parent_id:
                if msg_obj.parent_id not in children_map:
                    children_map[msg_obj.parent_id] = []
                children_map[msg_obj.parent_id].append(msg_obj.id)


        messages_output = []
        for msg in messages_in_branch:
            images_list_raw = msg.images or []
            images_list = []
            if isinstance(images_list_raw, str):
                try: images_list = json.loads(images_list_raw)
                except json.JSONDecodeError: images_list = []
            elif isinstance(images_list_raw, list):
                images_list = images_list_raw
            
            full_image_refs = []
            active_images_bools = []
            for img_data in images_list:
                if isinstance(img_data, dict) and 'image' in img_data:
                    full_image_refs.append(f"data:image/png;base64,{img_data['image']}")
                    active_images_bools.append(img_data.get('active', True))
                elif isinstance(img_data, str):
                    full_image_refs.append(f"data:image/png;base64,{img_data}")
                    active_images_bools.append(True)

            msg_metadata_raw = msg.metadata
            if isinstance(msg_metadata_raw, str):
                try: msg_metadata = json.loads(msg_metadata_raw) if msg_metadata_raw else {}
                except json.JSONDecodeError: msg_metadata = {}
            else:
                msg_metadata = msg_metadata_raw or {}

            msg_branches = None
            if msg.id in children_map and len(children_map[msg.id]) > 1:
                msg_branches = children_map[msg.id]

            messages_output.append(
                MessageOutput(
                    id=msg.id, sender=msg.sender, sender_type=msg.sender_type, content=msg.content,
                    parent_message_id=msg.parent_id, binding_name=msg.binding_name, model_name=msg.model_name,
                    token_count=msg.tokens, sources=msg_metadata.get('sources'), events=msg_metadata.get('events'),
                    image_references=full_image_refs,
                    active_images=active_images_bools,
                    user_grade=user_grades.get(msg.id, 0),
                    created_at=msg.created_at, branch_id=branch_tip_to_load, branches=msg_branches
                )
            )
        return messages_output

    @router.post("", response_model=DiscussionInfo, status_code=201)
    async def create_new_discussion(current_user: UserAuthDetails = Depends(get_current_active_user)) -> DiscussionInfo:
        username = current_user.username
        discussion_id = str(uuid.uuid4())
        discussion_obj = get_user_discussion(username, discussion_id, create_if_missing=True)
        if not discussion_obj:
            raise HTTPException(status_code=500, detail="Failed to create new discussion.")

        metadata = discussion_obj.metadata or {}
        return DiscussionInfo(
            id=discussion_obj.id,
            title=metadata.get('title', f"New Discussion {discussion_id[:8]}"),
            is_starred=False,
            rag_datastore_ids=None,
            active_tools=[],
            active_branch_id=None,
            created_at=discussion_obj.created_at,
            last_activity_at=discussion_obj.updated_at
        )

    @router.post("/{discussion_id}/clone", response_model=DiscussionInfo, status_code=201)
    async def clone_discussion(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ) -> DiscussionInfo:
        original_discussion, _, permission_level, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        
        if permission_level not in ['owner', 'interact']:
             raise HTTPException(status_code=403, detail="You need at least 'interact' permission to clone a discussion.")

        try:
            cloned_discussion = original_discussion.clone_without_messages()
            
            original_title = original_discussion.metadata.get('title', f"Discussion {discussion_id[:8]}")
            cloned_discussion.set_metadata_item('title', f"Clone of {original_title}")
            cloned_discussion.commit()

            return DiscussionInfo(
                id=cloned_discussion.id,
                title=cloned_discussion.metadata.get('title'),
                is_starred=False,
                rag_datastore_ids=cloned_discussion.metadata.get('rag_datastore_ids'),
                active_tools=cloned_discussion.metadata.get('active_tools', []),
                active_branch_id=cloned_discussion.active_branch_id,
                created_at=cloned_discussion.created_at,
                last_activity_at=cloned_discussion.updated_at,
                discussion_images=cloned_discussion.images or [],
                active_discussion_images= [img_info['active'] for img_info in cloned_discussion.images] if cloned_discussion.images else []
            )
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to clone discussion: {e}")

    @router.post("/{discussion_id}/auto-title", response_model=DiscussionInfo)
    async def generate_discussion_auto_title(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')

        try:
            new_title = discussion_obj.auto_title()
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to generate title: {e}")

        db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
        is_starred = db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).first() is not None
        metadata = discussion_obj.metadata or {}
        
        return DiscussionInfo(
            id=discussion_id,
            title=new_title,
            is_starred=is_starred,
            rag_datastore_ids=metadata.get('rag_datastore_ids'),
            active_tools=metadata.get('active_tools', []),
            active_branch_id=discussion_obj.active_branch_id,
            created_at=discussion_obj.created_at,
            last_activity_at=discussion_obj.updated_at
        )


    @router.get("/{discussion_id}/full_tree", response_model=List[MessageOutput])
    async def get_full_discussion_tree(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[MessageOutput]:
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        all_messages_in_discussion = discussion_obj.get_all_messages_flat()
        
        children_map: Dict[Optional[str], List[str]] = {}
        for msg_obj in all_messages_in_discussion:
            parent_id = msg_obj.parent_id
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(msg_obj.id)

        messages_output = []
        db_session_for_grades = next(get_db())
        try:
            db_user = db_session_for_grades.query(DBUser).filter(DBUser.username == current_user.username).one()
            user_grades = {g.message_id: g.grade for g in db_session_for_grades.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id).all()}
        finally:
            db_session_for_grades.close()


        for msg_obj in all_messages_in_discussion:
            msg_branches = None
            if msg_obj.id in children_map and len(children_map[msg_obj.id]) > 1:
                msg_branches = children_map[msg_obj.id]
                
            images_list_raw = msg_obj.images or []
            images_list = []
            if isinstance(images_list_raw, str):
                try: images_list = json.loads(images_list_raw)
                except json.JSONDecodeError: images_list = []
            elif isinstance(images_list_raw, list):
                images_list = images_list_raw
            
            full_image_refs = []
            active_images_bools = []
            for img_data in images_list:
                if isinstance(img_data, dict) and 'image' in img_data:
                    full_image_refs.append(f"data:image/png;base64,{img_data['image']}")
                    active_images_bools.append(img_data.get('active', True))
                elif isinstance(img_data, str):
                    full_image_refs.append(f"data:image/png;base64,{img_data}")
                    active_images_bools.append(True)
                    
            msg_metadata_raw = msg_obj.metadata
            if isinstance(msg_metadata_raw, str):
                try: msg_metadata = json.loads(msg_metadata_raw) if msg_metadata_raw else {}
                except json.JSONDecodeError: msg_metadata = {}
            else:
                msg_metadata = msg_metadata_raw or {}


            messages_output.append(
                MessageOutput(
                    id=msg_obj.id,
                    sender=msg_obj.sender,
                    sender_type=msg_obj.sender_type,
                    content=msg_obj.content,
                    parent_message_id=msg_obj.parent_id,
                    binding_name=msg_obj.binding_name,
                    model_name=msg_obj.model_name,
                    token_count=msg_obj.tokens,
                    sources=msg_metadata.get('sources'),
                    events=msg_metadata.get('events'),
                    image_references=full_image_refs,
                    active_images=active_images_bools,
                    user_grade=user_grades.get(msg_obj.id, 0),
                    created_at=msg_obj.created_at,
                    branch_id=discussion_obj.active_branch_id,
                    branches=msg_branches,
                    vision_support=True
                )
            )
        return messages_output

    @router.put("/{discussion_id}/active_branch", response_model=DiscussionInfo)
    async def update_discussion_active_branch(discussion_id: str, branch_request: DiscussionBranchSwitchRequest, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DiscussionInfo:
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')

        try:
            discussion_obj.switch_to_branch(branch_request.active_branch_id)
            discussion_obj.commit()
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
        is_starred = db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).first() is not None
        metadata = discussion_obj.metadata or {}
        return DiscussionInfo(
            id=discussion_id,
            title=metadata.get('title', "Untitled"),
            is_starred=is_starred,
            rag_datastore_ids=metadata.get('rag_datastore_ids'),
            active_tools=metadata.get('active_tools', []),
            active_branch_id=discussion_obj.active_branch_id,
            created_at=discussion_obj.created_at,
            last_activity_at=discussion_obj.updated_at
        )

    @router.put("/{discussion_id}/title", response_model=DiscussionInfo)
    async def update_discussion_title(discussion_id: str, title_update: DiscussionTitleUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        discussion_obj.set_metadata_item('title',title_update.title)

        db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
        is_starred = db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).first() is not None
        return DiscussionInfo(
            id=discussion_id,
            title=title_update.title,
            is_starred=is_starred,
            rag_datastore_ids=discussion_obj.metadata.get('rag_datastore_ids'),
            active_tools=discussion_obj.metadata.get('active_tools', []),
            active_branch_id=discussion_obj.active_branch_id,
            created_at=discussion_obj.created_at,
            last_activity_at=discussion_obj.updated_at
        )

    @router.delete("/{discussion_id}", status_code=200)
    async def delete_specific_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()):
        username = current_user.username
        dm = get_user_discussion_manager(username)
        
        if not dm.discussion_exists(discussion_id):
            raise HTTPException(status_code=404, detail="Discussion not found or you are not the owner.")
            
        dm.delete_discussion(discussion_id)

        assets_path = get_user_discussion_assets_path(username) / discussion_id
        if assets_path.exists() and assets_path.is_dir():
            background_tasks.add_task(shutil.rmtree, assets_path, ignore_errors=True)

        try:
            db_user = db.query(DBUser).filter(DBUser.username == username).one()
            db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).delete(synchronize_session=False)
            db.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id).delete(synchronize_session=False)
            db.query(SharedDiscussionLink).filter_by(discussion_id=discussion_id, owner_user_id=db_user.id).delete(synchronize_session=False)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"ERROR: Failed to delete main DB entries for discussion {discussion_id}: {e}")

        return {"message": f"Discussion '{discussion_id}' deleted successfully."}

    @router.post("/{discussion_id}/star", status_code=201, response_model=DiscussionInfo)
    async def star_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DiscussionInfo:
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
        
        if not db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).first():
            db.add(UserStarredDiscussion(user_id=db_user.id, discussion_id=discussion_id))
            db.commit()

        metadata = discussion_obj.metadata or {}
        return DiscussionInfo(
            id=discussion_id,
            title=metadata.get('title', "Untitled"),
            is_starred=True,
            rag_datastore_ids=metadata.get('rag_datastore_ids'),
            active_tools=metadata.get('active_tools', []),
            active_branch_id=discussion_obj.active_branch_id,
            created_at=discussion_obj.created_at,
            last_activity_at=discussion_obj.updated_at
        )

    @router.delete("/{discussion_id}/star", status_code=200, response_model=DiscussionInfo)
    async def unstar_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DiscussionInfo:
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()

        star = db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).first()
        if star:
            db.delete(star)
            db.commit()

        metadata = discussion_obj.metadata or {}
        return DiscussionInfo(
            id=discussion_id,
            title=metadata.get('title', "Untitled"),
            is_starred=False,
            rag_datastore_ids=metadata.get('rag_datastore_ids'),
            active_tools=metadata.get('active_tools', []),
            active_branch_id=discussion_obj.active_branch_id,
            created_at=discussion_obj.created_at,
            last_activity_at=discussion_obj.updated_at
        )

    return router