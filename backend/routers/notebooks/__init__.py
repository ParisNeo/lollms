# backend/routers/notebooks/__init__.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid
import json

from backend.db import get_db
from backend.db.models.notebook import Notebook as DBNotebook
from backend.models import UserAuthDetails
from backend.models.notebook import NotebookResponse, NotebookCreate
from backend.session import get_current_active_user

# Sub-router imports
from .core import router as core_router
from .assets import router as assets_router
from .ai import router as ai_router
from .export import router as export_router

router = APIRouter(
    prefix="/api/notebooks",
    tags=["Notebooks"]
)

# --- BASE ROUTES ---

@router.get("", response_model=List[NotebookResponse])
@router.get("/", response_model=List[NotebookResponse], include_in_schema=False)
def get_notebooks(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Lists all notebooks owned by the current user."""
    return db.query(DBNotebook).filter(DBNotebook.owner_user_id == current_user.id).order_by(DBNotebook.updated_at.desc()).all()

@router.post("", response_model=NotebookResponse)
@router.post("/", response_model=NotebookResponse, include_in_schema=False)
def create_notebook(
    payload: NotebookCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Creates a new notebook and initializes its tabs/content."""
    initial_tabs = []
    if payload.type == 'slides_making':
        initial_tabs.append({
            "id": str(uuid.uuid4()), "title": "Presentation", "type": "slides", 
            "content": json.dumps({"slides_data": [], "mode": "hybrid", "summary": ""}), "images": []
        })
    elif payload.type == 'youtube_video':
        initial_tabs.append({
            "id": str(uuid.uuid4()), "title": "Script", "type": "youtube_script", 
            "content": json.dumps({"scenes": []}), "images": []
        })
    elif payload.type == 'book_building':
        initial_tabs.append({
            "id": str(uuid.uuid4()), "title": "Outline", "type": "book_plan", "content": "[]", "images": []
        })
    
    if not initial_tabs:
         initial_tabs.append({
            "id": str(uuid.uuid4()), "title": "Main", "type": "markdown", "content": payload.initialPrompt or "", "images": []
        })

    content_to_store = payload.content or ""
    if payload.metadata:
        try:
            content_obj = { "text": payload.content or "", "metadata": payload.metadata }
            content_to_store = json.dumps(content_obj)
        except: pass

    new_notebook = DBNotebook(
        title=payload.title or "New Production",
        content=content_to_store,
        type=payload.type or "generic",
        language=payload.language or "en",
        owner_user_id=current_user.id,
        tabs=initial_tabs,
        artefacts=[]
    )
    
    if payload.raw_text:
        new_notebook.artefacts = [{
            "filename": "Initial Research Notes",
            "content": payload.raw_text,
            "type": "text",
            "is_loaded": True
        }]

    db.add(new_notebook)
    db.commit()
    db.refresh(new_notebook)
    
    # Trigger ingestion WITH chaining support
    from backend.task_manager import task_manager
    from backend.tasks.notebook_tasks import _ingest_notebook_sources_task
    
    task_manager.submit_task(
        name=f"Ingesting Production Context: {new_notebook.title}",
        target=_ingest_notebook_sources_task,
        args=(
            current_user.username, 
            new_notebook.id, 
            payload.urls or [], 
            payload.youtube_configs or [], 
            payload.wikipedia_urls or [],
            payload.initialPrompt # Passed to enable auto-generation after ingestion
        ),
        owner_username=current_user.username,
        description=new_notebook.id # Ensure overlay finds it
    )

    return new_notebook

# --- INCLUDE SUB-ROUTERS ---
router.include_router(core_router)
router.include_router(assets_router)
router.include_router(ai_router)
router.include_router(export_router)
