# backend/routers/memories.py
import json
import re
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Body
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.models import UserAuthDetails
from backend.session import get_current_active_user, get_current_db_user_from_token, get_user_data_root
from lollms_client.lollms_discussion.lollms_memory import LollmsMemoryManager, MemoryConfig

memories_router = APIRouter(prefix="/api/memories", tags=["Cognitive Memories"])


def get_user_memory_manager(username: str) -> LollmsMemoryManager:
    user_data_path = get_user_data_root(username)
    db_path = user_data_path / "memories_v2.db"
    return LollmsMemoryManager(
        db_path=f"sqlite:///{db_path.resolve()}",
        owner_id=f"user_{username}",
        config=MemoryConfig(
            working_token_budget=1024,
            handles_token_budget=512,
            dream_min_interval_hours=0
        )
    )

@memories_router.get("")
async def get_user_memories(
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    mm = get_user_memory_manager(current_user.username)
    # Return all level 1, 2, and 3 records for interactive UI representation
    with mm._session() as s:
        from lollms_client.lollms_discussion.lollms_memory import _MemoryRecord
        records = mm._q(s).order_by(_MemoryRecord.level.asc(), _MemoryRecord.importance.desc()).all()
        return [
            {
                "id": r.id,
                "content": r.content,
                "summary": r.summary or r.content[:60],
                "level": r.level,
                "importance": r.importance,
                "use_count": r.use_count,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
                "tags": r.tags
            }
            for r in records
        ]

@memories_router.post("", status_code=status.HTTP_201_CREATED)
async def create_memory(
    content: str = Body(..., embed=True),
    importance: float = Body(0.9, embed=True),
    tags: Optional[List[str]] = Body(None, embed=True),
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    if not content.strip():
        raise HTTPException(status_code=400, detail="Memory content cannot be empty.")
    mm = get_user_memory_manager(current_user.username)
    record = mm.add(content=content.strip(), importance=importance, tags=tags)
    return {
        "id": record.id,
        "content": record.content,
        "level": record.level,
        "importance": record.importance,
        "use_count": record.use_count
    }

@memories_router.put("/{memory_id}")
async def update_memory(
    memory_id: str,
    content: Optional[str] = Body(None, embed=True),
    importance: Optional[float] = Body(None, embed=True),
    level: Optional[int] = Body(None, embed=True),
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    mm = get_user_memory_manager(current_user.username)
    with mm._session() as s:
        from lollms_client.lollms_discussion.lollms_memory import _MemoryRecord
        record = s.query(_MemoryRecord).filter(_MemoryRecord.id == memory_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Memory record not found.")
        
        if content is not None:
            record.content = content.strip()
            record.summary = content.strip()[:100]
        if importance is not None:
            record.importance = max(0.0, min(1.0, importance))
        if level is not None:
            if level in [1, 2, 3]:
                record.level = level
            else:
                raise HTTPException(status_code=400, detail="Invalid Level. Must be 1 (Working), 2 (Deep), or 3 (Archived).")
                
        record.updated_at = datetime.now(timezone.utc)
        s.commit()
        return {
            "id": record.id,
            "content": record.content,
            "level": record.level,
            "importance": record.importance,
            "use_count": record.use_count
        }

@memories_router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    mm = get_user_memory_manager(current_user.username)
    with mm._session() as s:
        from lollms_client.lollms_discussion.lollms_memory import _MemoryRecord
        record = s.query(_MemoryRecord).filter(_MemoryRecord.id == memory_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Memory record not found.")
        s.delete(record)
        s.commit()

@memories_router.post("/dream", status_code=status.HTTP_200_OK)
async def trigger_dream_consolidation(
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    """Manually triggers the Level 3 Auto-Dreaming Consolidation Process."""
    mm = get_user_memory_manager(current_user.username)
    # Set dreamer parameters through memory_manager.dream()
    report = mm.dream()
    return {"status": "success", "report": report}
@memories_router.get("/export", response_class=StreamingResponse)
async def export_memories(
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    mm = get_user_memory_manager(current_user.username)
    with mm._session() as s:
        from lollms_client.lollms_discussion.lollms_memory import _MemoryRecord
        records = mm._q(s).order_by(_MemoryRecord.created_at.asc()).all()
        memories_to_export = [
            {
                "content": r.content,
                "importance": r.importance,
                "level": r.level,
                "use_count": r.use_count,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in records
        ]
    
    export_data = {"memories": memories_to_export}
    def iter_json():
        yield json.dumps(export_data, indent=2)

    return StreamingResponse(
        iter_json(),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=lollms_cognitive_memories_{current_user.username}.json"}
    )

@memories_router.post("/import", response_model=Dict[str, int])
async def import_memories(
    file: UploadFile = File(...),
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    try:
        contents = await file.read()
        data = json.loads(contents)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON file format.")
    
    mm = get_user_memory_manager(current_user.username)
    imported_count = 0
    
    for mem_data in data.get("memories", []):
        content = mem_data.get("content")
        if content:
            mm.add(
                content=content.strip(),
                importance=mem_data.get("importance", 0.9),
                tags=mem_data.get("tags")
            )
            imported_count += 1
            
    return {"imported_count": imported_count}