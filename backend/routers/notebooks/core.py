# backend/routers/notebooks/core.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from backend.db import get_db
from backend.db.models.notebook import Notebook as DBNotebook
from backend.models import UserAuthDetails
from backend.models.notebook import NotebookResponse, NotebookUpdate
from backend.session import get_current_active_user

router = APIRouter()

@router.get("/{notebook_id}", response_model=NotebookResponse)
def get_notebook(
    notebook_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Retrieves a single notebook by ID (Requires ownership)."""
    notebook = db.query(DBNotebook).filter(
        DBNotebook.id == notebook_id, 
        DBNotebook.owner_user_id == current_user.id
    ).first()
    
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    return notebook

@router.put("/{notebook_id}", response_model=NotebookResponse)
def update_notebook(
    notebook_id: str,
    payload: NotebookUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Updates notebook properties (title, language, tabs, etc)."""
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    
    if payload.title is not None: notebook.title = payload.title
    if payload.content is not None: notebook.content = payload.content
    if payload.language is not None: notebook.language = payload.language
    if payload.artefacts is not None: notebook.artefacts = payload.artefacts
    if payload.tabs is not None: notebook.tabs = payload.tabs
    
    notebook.updated_at = datetime.now()
    db.commit()
    db.refresh(notebook)
    return notebook

@router.delete("/{notebook_id}")
def delete_notebook(
    notebook_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Deletes a notebook and its associated assets."""
    import shutil
    from backend.session import get_user_notebook_assets_path
    
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    
    assets_path = get_user_notebook_assets_path(current_user.username, notebook_id)
    if assets_path.exists():
        shutil.rmtree(assets_path, ignore_errors=True)
        
    db.delete(notebook)
    db.commit()
    return {"message": "Notebook deleted."}
