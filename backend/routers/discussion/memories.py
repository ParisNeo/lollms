from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ascii_colors import trace_exception

from backend.db import get_db
from backend.models import UserAuthDetails
from backend.models.discussion import MemoryInfo, LoadMemoryRequest, UnloadMemoryRequest, MemoryCreateManual
from backend.session import get_current_active_user
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request

def build_memories_router(router: APIRouter):
    @router.get("/{discussion_id}/memories", response_model=List[MemoryInfo])
    async def list_discussion_memories(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        memories = discussion.list_memories()
        for memory in memories:
            if isinstance(memory.get('created_at'), datetime):
                memory['created_at'] = memory['created_at'].isoformat()
        return memories

    @router.post("/{discussion_id}/memories", response_model=MemoryInfo, status_code=status.HTTP_201_CREATED)
    async def create_or_update_manual_memory(
        discussion_id: str,
        payload: MemoryCreateManual,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            memory_info = discussion.add_memory(
                title=payload.title,
                content=payload.content
            )
            discussion.commit()
            if isinstance(memory_info.get('created_at'), datetime):
                memory_info['created_at'] = memory_info['created_at'].isoformat()
            return memory_info
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to create or update memory: {e}")

    @router.get("/{discussion_id}/memories/{memory_title}", response_model=MemoryInfo)
    async def get_discussion_memory(
        discussion_id: str,
        memory_title: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        memory = discussion.get_memory(title=memory_title)
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")
        if isinstance(memory.get('created_at'), datetime):
            memory['created_at'] = memory['created_at'].isoformat()
        return memory

    @router.delete("/{discussion_id}/memories/{memory_title}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_discussion_memory(
        discussion_id: str,
        memory_title: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        removed_count = discussion.remove_memory(title=memory_title)
        if removed_count == 0:
            raise HTTPException(status_code=404, detail="Memory not found to delete")
        discussion.commit()

    @router.post("/{discussion_id}/memories/load-to-context", response_model=dict)
    async def load_memory_to_context(
        discussion_id: str,
        request: LoadMemoryRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            discussion.load_memory_into_context(title=request.title)
            return {"content": discussion.memory or ""}
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load memory: {e}")

    @router.post("/{discussion_id}/memories/unload-from-context", response_model=dict)
    async def unload_memory_from_context(
        discussion_id: str,
        request: UnloadMemoryRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            discussion.unload_memory_from_context(title=request.title)
            return {"content": discussion.memory or ""}
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to unload memory: {e}")