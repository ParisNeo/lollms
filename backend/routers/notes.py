# backend/routers/notes.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, Field

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.note import Note as DBNote, NoteGroup as DBNoteGroup
from backend.session import get_current_active_user
from backend.models import UserAuthDetails

notes_router = APIRouter(
    prefix="/api/notes",
    tags=["Notes"],
    dependencies=[Depends(get_current_active_user)]
)

# --- Pydantic Models ---
class NoteGroupCreate(BaseModel):
    name: str = Field(..., min_length=1)
    parent_id: Optional[str] = None

class NoteGroupUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[str] = None

class NoteGroupPublic(BaseModel):
    id: str
    name: str
    parent_id: Optional[str]
    created_at: str
    updated_at: str
    class Config:
        from_attributes = True

class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = ""
    group_id: Optional[str] = None

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    group_id: Optional[str] = None

class NotePublic(BaseModel):
    id: str
    title: str
    content: str
    group_id: Optional[str]
    created_at: str
    updated_at: str
    class Config:
        from_attributes = True

# --- Group Endpoints ---

@notes_router.get("/groups", response_model=List[NoteGroupPublic])
def get_note_groups(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    groups = db.query(DBNoteGroup).filter(DBNoteGroup.owner_user_id == current_user.id).all()
    return [
        NoteGroupPublic(
            id=g.id, name=g.name, parent_id=g.parent_id,
            created_at=g.created_at.isoformat(), updated_at=g.updated_at.isoformat()
        ) for g in groups
    ]

@notes_router.post("/groups", response_model=NoteGroupPublic, status_code=status.HTTP_201_CREATED)
def create_note_group(
    group_data: NoteGroupCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    new_group = DBNoteGroup(
        name=group_data.name,
        parent_id=group_data.parent_id,
        owner_user_id=current_user.id
    )
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    return NoteGroupPublic(
        id=new_group.id, name=new_group.name, parent_id=new_group.parent_id,
        created_at=new_group.created_at.isoformat(), updated_at=new_group.updated_at.isoformat()
    )

@notes_router.put("/groups/{group_id}", response_model=NoteGroupPublic)
def update_note_group(
    group_id: str,
    group_data: NoteGroupUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    group = db.query(DBNoteGroup).filter(DBNoteGroup.id == group_id, DBNoteGroup.owner_user_id == current_user.id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")
    
    if group_data.name is not None:
        group.name = group_data.name
    if group_data.parent_id is not None:
        if group_data.parent_id == group.id:
             raise HTTPException(status_code=400, detail="Cannot set parent to self.")
        group.parent_id = group_data.parent_id
        
    db.commit()
    db.refresh(group)
    return NoteGroupPublic(
        id=group.id, name=group.name, parent_id=group.parent_id,
        created_at=group.created_at.isoformat(), updated_at=group.updated_at.isoformat()
    )

@notes_router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note_group(
    group_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    group = db.query(DBNoteGroup).filter(DBNoteGroup.id == group_id, DBNoteGroup.owner_user_id == current_user.id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")
    
    # Logic for orphans: if group is deleted, children groups become top-level, notes become ungrouped
    # SQLAlchemy cascade might handle notes if configured, but re-parenting groups is manual
    children = db.query(DBNoteGroup).filter(DBNoteGroup.parent_id == group_id).all()
    for child in children:
        child.parent_id = group.parent_id # Move up one level
    
    notes = db.query(DBNote).filter(DBNote.group_id == group_id).all()
    for note in notes:
        note.group_id = None # Ungroup notes
        
    db.delete(group)
    db.commit()

# --- Note Endpoints ---

@notes_router.get("", response_model=List[NotePublic])
def get_notes(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    notes = db.query(DBNote).filter(DBNote.owner_user_id == current_user.id).order_by(DBNote.updated_at.desc()).all()
    return [
        NotePublic(
            id=n.id, title=n.title, content=n.content, group_id=n.group_id,
            created_at=n.created_at.isoformat(), updated_at=n.updated_at.isoformat()
        ) for n in notes
    ]

@notes_router.post("", response_model=NotePublic, status_code=status.HTTP_201_CREATED)
def create_note(
    note_data: NoteCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    new_note = DBNote(
        title=note_data.title,
        content=note_data.content,
        group_id=note_data.group_id,
        owner_user_id=current_user.id
    )
    db.add(new_note)
    db.commit()
    db.refresh(new_note)
    return NotePublic(
        id=new_note.id, title=new_note.title, content=new_note.content, group_id=new_note.group_id,
        created_at=new_note.created_at.isoformat(), updated_at=new_note.updated_at.isoformat()
    )

@notes_router.put("/{note_id}", response_model=NotePublic)
def update_note(
    note_id: str,
    note_data: NoteUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    note = db.query(DBNote).filter(DBNote.id == note_id, DBNote.owner_user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")

    if note_data.title is not None: note.title = note_data.title
    if note_data.content is not None: note.content = note_data.content
    if note_data.group_id is not None: note.group_id = note_data.group_id
    
    db.commit()
    db.refresh(note)
    return NotePublic(
        id=note.id, title=note.title, content=note.content, group_id=note.group_id,
        created_at=note.created_at.isoformat(), updated_at=note.updated_at.isoformat()
    )

@notes_router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    note = db.query(DBNote).filter(DBNote.id == note_id, DBNote.owner_user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    
    db.delete(note)
    db.commit()
