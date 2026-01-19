# backend/routers/notebooks/__init__.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid
import json

from backend.db import get_db
from backend.db.models.notebook import Notebook as DBNotebook
from backend.models import UserAuthDetails
from backend.models.notebook import NotebookResponse, NotebookCreate, ArxivSearchRequest, ArxivResult
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
    main_tab_id = None

    if payload.type == 'slides_making':
        main_tab_id = str(uuid.uuid4())
        initial_tabs.append({
            "id": main_tab_id, "title": "Presentation", "type": "slides",
            "content": json.dumps({"slides_data": [], "mode": "hybrid", "summary": ""}), "images": []
        })
    elif payload.type == 'youtube_video':
        main_tab_id = str(uuid.uuid4())
        initial_tabs.append({
            "id": main_tab_id, "title": "Script", "type": "youtube_script",
            "content": json.dumps({"scenes": []}), "images": []
        })
    elif payload.type == 'book_building':
        main_tab_id = str(uuid.uuid4())
        initial_tabs.append({
            "id": main_tab_id, "title": "Outline", "type": "book_plan", "content": "[]", "images": []
        })

    if not initial_tabs:
         main_tab_id = str(uuid.uuid4())
         # Don't put the prompt in the main tab - it will be replaced by AI synthesis
         initial_tabs.append({
            "id": main_tab_id, 
            "title": "Research Report", 
            "type": "markdown", 
            "content": "Loading sources..." if payload.delay_processing else "Generating report...",
            "images": []
        })

    content_to_store = payload.content or ""
    if payload.metadata:
        try:
            content_obj = { "text": payload.content or "", "metadata": payload.metadata }
            content_to_store = json.dumps(content_obj)
        except: pass

    new_notebook = DBNotebook(
        title=payload.title or "New Research",
        content=content_to_store,
        type=payload.type or "generic",
        language=payload.language or "en",
        owner_user_id=current_user.id,
        tabs=initial_tabs,
        artefacts=[],
        google_search_queries=payload.google_search_queries or [],
        arxiv_queries=payload.arxiv_queries or []
    )

    if payload.raw_text:
        new_notebook.artefacts = [{
            "filename": "Manual Input",
            "content": payload.raw_text,
            "type": "text",
            "is_loaded": True
        }]

    db.add(new_notebook)
    db.commit()
    db.refresh(new_notebook)

    # Trigger ingestion - it will handle whether to auto-generate or not
    if not payload.delay_processing or (payload.urls or payload.youtube_configs or payload.wikipedia_urls or payload.google_search_queries or payload.arxiv_queries or payload.arxiv_selected):
        from backend.task_manager import task_manager
        from backend.tasks.notebook_tasks import _ingest_notebook_sources_task

        task_manager.submit_task(
            name=f"Building: {new_notebook.title}",
            target=_ingest_notebook_sources_task,
            args=(
                current_user.username,
                new_notebook.id,
                payload.urls or [],
                payload.youtube_configs or [],
                payload.wikipedia_urls or [],
                payload.google_search_queries or [],
                payload.arxiv_queries or [],
                payload.initialPrompt if not payload.delay_processing else None,  # Only pass prompt if auto-generating
                main_tab_id,
                payload.arxiv_config.dict() if payload.arxiv_config else {},
                [a.dict() for a in payload.arxiv_selected] if payload.arxiv_selected else []
            ),
            owner_username=current_user.username,
            description=new_notebook.id
        )

    return new_notebook

# Add Arxiv search endpoint
@router.post("/search/arxiv", response_model=List[ArxivResult])
def search_arxiv_endpoint(
    payload: ArxivSearchRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """Searches Arxiv for papers matching the query."""
    import arxiv
    client = arxiv.Client()
    search = arxiv.Search(
        query=payload.query,
        max_results=payload.max_results,
        sort_by=arxiv.SortCriterion.Relevance
    )
    results = []
    for r in client.results(search):
        results.append(ArxivResult(
            entry_id=r.entry_id,
            title=r.title,
            authors=[a.name for a in r.authors],
            summary=r.summary,
            published=r.published.strftime("%Y-%m-%d"),
            pdf_url=r.pdf_url
        ))
    return results

# --- INCLUDE SUB-ROUTERS ---
router.include_router(core_router)
router.include_router(assets_router)
router.include_router(ai_router)
router.include_router(export_router)

