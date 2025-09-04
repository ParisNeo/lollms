# backend/routers/memories.py
import json
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.memory import UserMemory as DBUserMemory
from backend.models import UserAuthDetails
from backend.models.memory import MemoryCreate, MemoryPublic, MemoryUpdate, MemoriesImport
from backend.session import get_current_active_user, get_current_db_user_from_token

memories_router = APIRouter(prefix="/api/memories", tags=["Memories"])

@memories_router.get("", response_model=List[MemoryPublic])
async def get_user_memories(
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    return current_user.memories

@memories_router.post("", response_model=MemoryPublic, status_code=status.HTTP_201_CREATED)
async def create_memory(
    memory_data: MemoryCreate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    if not memory_data.title.strip() or not memory_data.content.strip():
        raise HTTPException(status_code=400, detail="Title and content cannot be empty.")
        
    new_memory = DBUserMemory(
        user_id=current_user.id,
        title=memory_data.title,
        content=memory_data.content
    )
    db.add(new_memory)
    db.commit()
    db.refresh(new_memory)
    return new_memory

@memories_router.put("/{memory_id}", response_model=MemoryPublic)
async def update_memory(
    memory_id: str,
    memory_data: MemoryUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    memory = db.query(DBUserMemory).filter(DBUserMemory.id == memory_id, DBUserMemory.user_id == current_user.id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found.")
    
    update_data = memory_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(memory, key, value)
    
    db.commit()
    db.refresh(memory)
    return memory

@memories_router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    memory = db.query(DBUserMemory).filter(DBUserMemory.id == memory_id, DBUserMemory.user_id == current_user.id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found.")
    db.delete(memory)
    db.commit()

@memories_router.get("/export", response_class=StreamingResponse)
async def export_memories(
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    memories_to_export = [
        {
            "title": mem.title,
            "content": mem.content,
            "created_at": mem.created_at.isoformat()
        }
        for mem in current_user.memories
    ]
    
    export_data = {"memories": memories_to_export}
    
    def iter_json():
        yield json.dumps(export_data, indent=2)

    return StreamingResponse(
        iter_json(),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=lollms_memories_export_{current_user.username}.json"}
    )

@memories_router.post("/import", response_model=Dict[str, int])
async def import_memories(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_db_user_from_token)
):
    try:
        contents = await file.read()
        data = json.loads(contents)
        import_data = MemoriesImport(**data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON file format.")
    
    imported_count = 0
    for mem_data in import_data.memories:
        new_memory = DBUserMemory(
            user_id=current_user.id,
            title=mem_data.title,
            content=mem_data.content
        )
        db.add(new_memory)
        imported_count += 1
    
    db.commit()
    return {"imported_count": imported_count}