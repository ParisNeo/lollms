import uuid
import json
import shutil
import re
import base64
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body, Response
from fastapi.responses import FileResponse 
from sqlalchemy.orm import Session
from pydantic import BaseModel
from werkzeug.utils import secure_filename

from backend.db import get_db
from backend.db.models.notebook import Notebook as DBNotebook
from backend.models import UserAuthDetails, TaskInfo
from backend.models.notebook import NotebookCreate, NotebookUpdate, NotebookResponse, StructureItem, GenerateStructureRequest, GenerateTitleResponse, ProcessRequest, ArxivSearchRequest, ArxivResult
from backend.session import get_current_active_user, get_user_notebook_assets_path, get_user_lollms_client
from backend.task_manager import task_manager
from ascii_colors import trace_exception
from backend.tasks.notebook_tasks import _process_notebook_task, _ingest_notebook_sources_task, _convert_file_with_docling_task

router = APIRouter(
    prefix="/api/notebooks",
    tags=["Notebooks"],
    dependencies=[Depends(get_current_active_user)]
)

class StructureItem(BaseModel):
    title: str
    type: str = "markdown" 
    content: Optional[str] = ""

class NotebookCreate(BaseModel):
    title: str
    content: Optional[str] = ""
    type: Optional[str] = "generic"
    language: Optional[str] = "en"
    structure: Optional[List[StructureItem]] = None 
    initialPrompt: Optional[str] = None
    urls: Optional[List[str]] = None
    youtube_urls: Optional[List[str]] = None
    wikipedia_urls: Optional[List[str]] = None
    google_search_queries: Optional[List[str]] = None
    arxiv_queries: Optional[List[str]] = None
    arxiv_selected: Optional[List[Any]] = None
    arxiv_config: Optional[Any] = None
    youtube_configs: Optional[List[Any]] = None
    raw_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None 

class NotebookUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    language: Optional[str] = None
    artefacts: Optional[List[Dict[str, Any]]] = None
    tabs: Optional[List[Dict[str, Any]]] = None

class NotebookResponse(BaseModel):
    id: str
    title: str
    content: str
    type: str
    language: str
    artefacts: List[Dict[str, Any]]
    tabs: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    class Config: from_attributes = True

class GenerateStructureRequest(BaseModel):
    type: str
    prompt: str
    urls: Optional[List[str]] = []
    files: Optional[List[Any]] = [] 

class GenerateTitleResponse(BaseModel):
    title: str

class ProcessRequest(BaseModel):
    prompt: str
    input_tab_ids: List[str]
    output_type: str
    target_tab_id: Optional[str] = None
    skip_llm: bool = False
    generate_speech: bool = False
    selected_artefacts: Optional[List[str]] = []

@router.get("", response_model=List[NotebookResponse])
def get_notebooks(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return db.query(DBNotebook).filter(DBNotebook.owner_user_id == current_user.id).order_by(DBNotebook.updated_at.desc()).all()


@router.post("", response_model=NotebookResponse)
def create_notebook(
    payload: NotebookCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    initial_tabs = []
    if payload.structure:
        for item in payload.structure:
            initial_tabs.append({
                "id": str(uuid.uuid4()),
                "title": item.title,
                "type": item.type,
                "content": item.content,
                "images": []
            })
    
    # ID for the main tab (used for initial report generation)
    main_tab_id = str(uuid.uuid4())

    if not initial_tabs:
         # Default Tab Setup with Loading State
         initial_tabs.append({
            "id": main_tab_id,
            "title": "Research Report",
            "type": "markdown",
            "content": f"# Research Report\n\n> **Objective:** {payload.initialPrompt or 'General Analysis'}\n\n---\n\n### ⏳ status: Processing Sources...\nThe AI is currently reading the provided materials and will generate a comprehensive analysis shortly.\n\n*Please do not close this tab while the 'Ingesting knowledge sources' task is running.*" if payload.type == 'generic' and (payload.urls or payload.files or payload.raw_text or payload.arxiv_selected) else (payload.initialPrompt or ""),
            "images": []
        })
    else:
        main_tab_id = initial_tabs[0]["id"]

    content_to_store = payload.content or ""
    if payload.metadata:
        try:
            content_obj = { "text": payload.content or "", "metadata": payload.metadata }
            content_to_store = json.dumps(content_obj)
        except: pass

    new_notebook = DBNotebook(
        title=payload.title,
        content=content_to_store,
        type=payload.type,
        language=payload.language or "en",
        owner_user_id=current_user.id,
        tabs=initial_tabs,
        artefacts=[]
    )
    
    if payload.raw_text:
        new_notebook.artefacts = [{
            "filename": "Initial Notes",
            "content": payload.raw_text,
            "type": "text",
            "is_loaded": True
        }]

    db.add(new_notebook)
    db.commit()
    db.refresh(new_notebook)
    
    # Check if we need to trigger ingestion
    has_sources = (
        (payload.urls and len(payload.urls) > 0) or 
        (payload.youtube_urls and len(payload.youtube_urls) > 0) or
        (payload.wikipedia_urls and len(payload.wikipedia_urls) > 0) or
        (payload.google_search_queries and len(payload.google_search_queries) > 0) or
        (payload.arxiv_queries and len(payload.arxiv_queries) > 0) or
        (payload.arxiv_selected and len(payload.arxiv_selected) > 0)
    )

    if has_sources:
        arxiv_conf = payload.arxiv_config.dict() if payload.arxiv_config else {}
        # Convert pydantic models to dicts for the task
        arxiv_selected_dicts = [a.dict() for a in payload.arxiv_selected] if payload.arxiv_selected else []
        
        task_manager.submit_task(
            name=f"Notebook Ingest: {new_notebook.title}",
            target=_ingest_notebook_sources_task,
            args=(
                current_user.username, 
                new_notebook.id, 
                payload.urls or [], 
                payload.youtube_configs or [], # Use config objects if available
                payload.wikipedia_urls or [],
                payload.google_search_queries or [],
                payload.arxiv_queries or [],
                payload.initialPrompt,
                main_tab_id, # Target tab for the generated report
                arxiv_conf,
                arxiv_selected_dicts
            ),
            description="Ingesting knowledge sources...",
            owner_username=current_user.username
        )

    return new_notebook

@router.put("/{notebook_id}", response_model=NotebookResponse)
def update_notebook(
    notebook_id: str,
    payload: NotebookUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
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
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    
    assets_path = get_user_notebook_assets_path(current_user.username, notebook_id)
    if assets_path.exists():
        shutil.rmtree(assets_path, ignore_errors=True)
        
    db.delete(notebook)
    db.commit()
    return {"message": "Notebook deleted."}

@router.post("/structure", response_model=List[StructureItem])
def generate_notebook_structure(
    request: GenerateStructureRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    lc = get_user_lollms_client(current_user.username)
    prompt = f"""Create a structure for a '{request.type}' notebook based on: "{request.prompt}".
    Return a JSON list of objects with "title", "type" (markdown/slides), and "content".
    """
    try:
        response_text = lc.generate_text(prompt, max_new_tokens=1024)
        match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if match:
            return [StructureItem(**item) for item in json.loads(match.group(0))]
        return [StructureItem(title="Chapter 1", content=response_text)]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{notebook_id}/upload")
async def upload_notebook_source_endpoint(
    notebook_id: str,
    file: UploadFile = File(...),
    use_docling: bool = Form(False),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # This was a stub in previous files, ensuring it's correct now
    return await upload_notebook_source(notebook_id, file, use_docling, current_user, db)

async def upload_notebook_source(notebook_id, file, use_docling, current_user, db):
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook: raise HTTPException(status_code=404)
    
    assets_path = get_user_notebook_assets_path(current_user.username, notebook_id)
    assets_path.mkdir(parents=True, exist_ok=True)
    fn = secure_filename(file.filename)
    unique_fn = f"{uuid.uuid4().hex[:8]}_{fn}"
    file_path = assets_path / unique_fn
    with open(file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    
    is_text = file_path.suffix.lower() in ['.txt', '.md', '.py', '.js', '.json', '.html', '.css', '.c', '.cpp']
    if is_text:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        new_art = { "filename": unique_fn, "content": content, "type": "text", "is_loaded": True }
        notebook.artefacts = list(notebook.artefacts) + [new_art]
        db.commit()
    elif use_docling:
        task_manager.submit_task(name=f"Convert: {fn}", target=_convert_file_with_docling_task, args=(current_user.username, notebook_id, str(file_path), unique_fn), owner_username=current_user.username)
    return {"filename": unique_fn}

@router.post("/{notebook_id}/describe_image")
async def describe_notebook_image(
    notebook_id: str,
    file: UploadFile = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    try:
        content = await file.read()
        b64 = base64.b64encode(content).decode('utf-8')
        lc = get_user_lollms_client(current_user.username)
        desc = lc.generate_text("Describe this image for a prompt:", images=[b64])
        return {"description": desc}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{notebook_id}/describe_asset")
async def describe_notebook_asset_endpoint(
    notebook_id: str,
    payload: Dict[str, str],
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    fn = payload.get("filename")
    path = get_user_notebook_assets_path(current_user.username, notebook_id) / secure_filename(fn)
    if not path.exists():
        raise HTTPException(status_code=404)
    b64 = base64.b64encode(path.read_bytes()).decode('utf-8')
    lc = get_user_lollms_client(current_user.username)
    return {"description": lc.generate_text("Describe this image for a prompt:", images=[b64])}

@router.post("/{notebook_id}/artefact")
def create_text_artefact(
    notebook_id: str,
    payload: Dict[str, str], 
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook: raise HTTPException(status_code=404)
    fn = secure_filename(payload.get('title', 'note.txt'))
    path = get_user_notebook_assets_path(current_user.username, notebook_id) / fn
    path.write_text(payload.get('content', ''), encoding='utf-8')
    notebook.artefacts = list(notebook.artefacts) + [{ "filename": fn, "content": payload.get('content', ''), "type": "text", "is_loaded": True }]
    db.commit()
    return {"filename": fn}

@router.post("/{notebook_id}/generate_title", response_model=GenerateTitleResponse)
def generate_notebook_title(
    notebook_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook: raise HTTPException(status_code=404)
    lc = get_user_lollms_client(current_user.username)
    title = lc.generate_text(f"Summarize this notebook content into a short title: {notebook.content[:1000]}").strip().strip('"')
    notebook.title = title
    db.commit()
    return {"title": title}

@router.post("/{notebook_id}/scrape")
def scrape_url_to_notebook(
    notebook_id: str,
    payload: Dict[str, str],
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    return task_manager.submit_task(
        name=f"Scrape: {payload['url']}",
        target=_ingest_notebook_sources_task,
        args=(current_user.username, notebook_id, [payload['url']], [], [], [], [], "", None, {}, []),
        owner_username=current_user.username
    )

@router.post("/{notebook_id}/process", response_model=TaskInfo)
def process_notebook_ai(
    notebook_id: str,
    payload: ProcessRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    return task_manager.submit_task(
        name=f"AI Task: {payload.output_type}",
        target=_process_notebook_task,
        args=(current_user.username, notebook_id, payload.prompt, payload.input_tab_ids, payload.output_type, payload.target_tab_id, payload.skip_llm, payload.generate_speech, payload.selected_artefacts),
        owner_username=current_user.username
    )

@router.get("/{notebook_id}/export")
def export_notebook(
    notebook_id: str,
    format: str = "json",
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from backend.routers.notebooks.export import export_notebook as export_func
    return export_func(notebook_id, format, current_user, db)

@router.get("/{notebook_id}/assets/{filename}")
def get_notebook_asset(
    notebook_id: str,
    filename: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    nb = db.query(DBNotebook.id).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not nb: raise HTTPException(status_code=403)
    path = get_user_notebook_assets_path(current_user.username, notebook_id) / secure_filename(filename)
    if not path.exists(): raise HTTPException(status_code=404)
    return FileResponse(path)


# Stubbing others to keep file valid if user copy-pastes
@router.post("/{notebook_id}/describe_asset")
async def describe_notebook_asset_endpoint(notebook_id: str, payload: Dict[str, str], current_user: UserAuthDetails = Depends(get_current_active_user)):
    fn = payload.get("filename")
    path = get_user_notebook_assets_path(current_user.username, notebook_id) / secure_filename(fn)
    if not path.exists(): raise HTTPException(status_code=404)
    b64 = base64.b64encode(path.read_bytes()).decode('utf-8')
    lc = get_user_lollms_client(current_user.username)
    return {"description": lc.generate_text("Describe this image for a prompt:", images=[b64])}

@router.post("/{notebook_id}/artefact")
def create_text_artefact(notebook_id: str, payload: Dict[str, str], current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook: raise HTTPException(status_code=404)
    fn = secure_filename(payload.get('title', 'note.txt'))
    path = get_user_notebook_assets_path(current_user.username, notebook_id) / fn
    path.write_text(payload.get('content', ''), encoding='utf-8')
    notebook.artefacts = list(notebook.artefacts) + [{ "filename": fn, "content": payload.get('content', ''), "type": "text", "is_loaded": True }]
    db.commit()
    return {"filename": fn}

@router.post("/{notebook_id}/generate_title", response_model=GenerateTitleResponse)
def generate_notebook_title_endpoint(notebook_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook: raise HTTPException(status_code=404)
    lc = get_user_lollms_client(current_user.username)
    title = lc.generate_text(f"Summarize this content into a title: {notebook.content[:1000]}").strip().strip('"')
    notebook.title = title
    db.commit()
    return {"title": title}

@router.post("/{notebook_id}/process", response_model=TaskInfo)
def process_notebook_ai(
    notebook_id: str,
    payload: ProcessRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    return task_manager.submit_task(
        name=f"AI Task: {payload.output_type}",
        target=_process_notebook_task,
        args=(current_user.username, notebook_id, payload.prompt, payload.input_tab_ids, payload.output_type, payload.target_tab_id, payload.skip_llm, payload.generate_speech, payload.selected_artefacts),
        owner_username=current_user.username
    )