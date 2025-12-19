import shutil
import uuid
import datetime
from typing import List, Optional, Dict
from pathlib import Path
import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.db import get_db
from backend.db.models.notebook import Notebook
from backend.models import UserAuthDetails, TaskInfo
from backend.session import get_current_active_user, get_user_notebook_assets_path, get_user_lollms_client
from backend.task_manager import task_manager, Task
from backend.routers.files import extract_text_from_file_bytes

# Import ScrapeMaster for scraping
try:
    from scrapemaster import ScrapeMaster
except ImportError:
    ScrapeMaster = None

router = APIRouter(
    prefix="/api/notebooks",
    tags=["Notebooks"],
    dependencies=[Depends(get_current_active_user)]
)

# --- Pydantic Models ---
class NotebookCreate(BaseModel):
    title: str
    content: Optional[str] = ""

class NotebookUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    artefacts: Optional[List[dict]] = None

class NotebookPublic(BaseModel):
    id: str
    title: str
    content: str
    artefacts: List[dict]
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True

class ScrapeRequest(BaseModel):
    url: str

class ArtefactCreate(BaseModel):
    title: str
    content: str

# --- Tasks ---

def _notebook_process_task(task: Task, username: str, notebook_id: str, prompt: str):
    task.log("Starting notebook processing...")
    
    with task.db_session_factory() as db:
        nb = db.query(Notebook).filter(Notebook.id == notebook_id).first()
        if not nb:
            raise ValueError("Notebook not found")
        
        # Build context from loaded artefacts
        context = ""
        if nb.artefacts:
            for art in nb.artefacts:
                if art.get("is_loaded"):
                    context += f"\n\n--- Source: {art.get('filename')} ---\n{art.get('content','')}\n--- End Source ---\n"
        
        current_content = nb.content or ""
        
        # Prepare LLM client
        lc = get_user_lollms_client(username)
        
        system_prompt = "You are a helpful research assistant. Use the provided sources to answer the request or update the notebook content."
        full_prompt = f"{system_prompt}\n\n[SOURCES]\n{context}\n\n[CURRENT CONTENT]\n{current_content}\n\n[INSTRUCTION]\n{prompt}"
        
        task.set_progress(10)
        task.log("Generating content...")
        
        def callback(chunk, msg_type=None, params=None, **kwargs):
            if task.cancellation_event.is_set(): return False
            return True

        generated = lc.generate_text(full_prompt, streaming_callback=callback)
        
        if generated:
            # Append generated content with a timestamp header
            timestamp = datetime.datetime.now().strftime('%H:%M')
            nb.content = (nb.content or "") + f"\n\n### AI Response ({timestamp})\n{generated}"
            db.commit()
            task.log("Notebook content updated.")
        
    task.set_progress(100)
    return {"notebook_id": notebook_id}

def _notebook_scrape_task(task: Task, username: str, notebook_id: str, url: str):
    if ScrapeMaster is None:
        raise ImportError("ScrapeMaster is not installed.")
        
    task.log(f"Scraping URL: {url}")
    task.set_progress(10)
    
    try:
        scraper = ScrapeMaster(url)
        # Try scrape_markdown if available, else scrape
        if hasattr(scraper, 'scrape_markdown'):
            content = scraper.scrape_markdown()
        else:
            content = scraper.scrape()
        
        if not content:
            raise ValueError("No content extracted from URL.")
            
        task.set_progress(80)
        task.log("Content extracted. Saving to notebook...")
        
        with task.db_session_factory() as db:
            nb = db.query(Notebook).filter(Notebook.id == notebook_id).first()
            if not nb:
                raise ValueError("Notebook not found")
            
            # Use a list copy to ensure SQLAlchemy detects changes
            current_artefacts = list(nb.artefacts) if nb.artefacts else []
            filename = f"Scrape: {url}"
            
            # Remove existing scrape of same URL to update
            current_artefacts = [a for a in current_artefacts if a['filename'] != filename]
            
            current_artefacts.append({
                "filename": filename,
                "content": content,
                "type": "url",
                "is_loaded": True,
                "source": url
            })
            
            nb.artefacts = current_artefacts
            flag_modified(nb, "artefacts")
            db.commit()
            
        task.set_progress(100)
        task.log("Scrape successful.")
        return {"notebook_id": notebook_id, "filename": filename}
        
    except Exception as e:
        task.log(f"Scraping failed: {e}", "ERROR")
        raise e

# --- Endpoints ---

@router.get("", response_model=List[NotebookPublic])
def list_notebooks(db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_active_user)):
    notebooks = db.query(Notebook).filter(Notebook.owner_user_id == current_user.id).order_by(Notebook.updated_at.desc()).all()
    return [
        {
            "id": n.id,
            "title": n.title,
            "content": n.content or "",
            "artefacts": n.artefacts or [],
            "created_at": n.created_at.isoformat(),
            "updated_at": n.updated_at.isoformat() if n.updated_at else n.created_at.isoformat()
        } for n in notebooks
    ]

@router.post("", response_model=NotebookPublic)
def create_notebook(data: NotebookCreate, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_active_user)):
    nb = Notebook(
        title=data.title,
        content=data.content,
        owner_user_id=current_user.id,
        artefacts=[]
    )
    db.add(nb)
    db.commit()
    db.refresh(nb)
    return {
            "id": nb.id,
            "title": nb.title,
            "content": nb.content or "",
            "artefacts": nb.artefacts or [],
            "created_at": nb.created_at.isoformat(),
            "updated_at": nb.updated_at.isoformat() if nb.updated_at else nb.created_at.isoformat()
        }

@router.put("/{notebook_id}", response_model=NotebookPublic)
def update_notebook(notebook_id: str, data: NotebookUpdate, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_active_user)):
    nb = db.query(Notebook).filter(Notebook.id == notebook_id, Notebook.owner_user_id == current_user.id).first()
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")
    
    if data.title is not None: nb.title = data.title
    if data.content is not None: nb.content = data.content
    if data.artefacts is not None: 
        nb.artefacts = data.artefacts
        flag_modified(nb, "artefacts")
    
    db.commit()
    db.refresh(nb)
    return {
            "id": nb.id,
            "title": nb.title,
            "content": nb.content or "",
            "artefacts": nb.artefacts or [],
            "created_at": nb.created_at.isoformat(),
            "updated_at": nb.updated_at.isoformat() if nb.updated_at else nb.created_at.isoformat()
        }

@router.delete("/{notebook_id}")
def delete_notebook(notebook_id: str, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_active_user)):
    nb = db.query(Notebook).filter(Notebook.id == notebook_id, Notebook.owner_user_id == current_user.id).first()
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")
    
    # Clean up assets
    assets_path = get_user_notebook_assets_path(current_user.username, notebook_id)
    if assets_path.exists():
        shutil.rmtree(assets_path)

    db.delete(nb)
    db.commit()
    return {"message": "Deleted"}

@router.post("/{notebook_id}/upload")
async def upload_to_notebook(
    notebook_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    nb = db.query(Notebook).filter(Notebook.id == notebook_id, Notebook.owner_user_id == current_user.id).first()
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")

    assets_path = get_user_notebook_assets_path(current_user.username, notebook_id)
    assets_path.mkdir(parents=True, exist_ok=True)
    
    file_path = assets_path / file.filename
    content_bytes = await file.read()
    
    with open(file_path, "wb") as f:
        f.write(content_bytes)
        
    # Extract text content
    text_content, _ = extract_text_from_file_bytes(content_bytes, file.filename)
    
    # Update artefacts safely
    current_artefacts = list(nb.artefacts) if nb.artefacts else []
    
    # Remove existing artefact with same name to update content
    current_artefacts = [a for a in current_artefacts if a['filename'] != file.filename]
    
    current_artefacts.append({
        "filename": file.filename,
        "content": text_content,
        "type": "file",
        "is_loaded": True
    })
    
    nb.artefacts = current_artefacts
    flag_modified(nb, "artefacts")
    db.commit()
    
    return {"message": "Uploaded", "filename": file.filename}

@router.post("/{notebook_id}/artefact")
async def create_notebook_artefact(
    notebook_id: str,
    artefact: ArtefactCreate,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    nb = db.query(Notebook).filter(Notebook.id == notebook_id, Notebook.owner_user_id == current_user.id).first()
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")

    # Update artefacts safely
    current_artefacts = list(nb.artefacts) if nb.artefacts else []
    
    # Remove existing artefact with same name/title to update content
    current_artefacts = [a for a in current_artefacts if a['filename'] != artefact.title]
    
    current_artefacts.append({
        "filename": artefact.title,
        "content": artefact.content,
        "type": "text",
        "is_loaded": True
    })
    
    nb.artefacts = current_artefacts
    flag_modified(nb, "artefacts")
    db.commit()
    
    return {"message": "Artefact created", "filename": artefact.title}

@router.post("/{notebook_id}/scrape", response_model=TaskInfo)
async def scrape_url_to_notebook(
    notebook_id: str,
    request: ScrapeRequest,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    nb = db.query(Notebook).filter(Notebook.id == notebook_id, Notebook.owner_user_id == current_user.id).first()
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")

    task = task_manager.submit_task(
        name=f"Scrape URL: {request.url}",
        target=_notebook_scrape_task,
        args=(current_user.username, notebook_id, request.url),
        description=f"Scraping content for notebook: {nb.title}",
        owner_username=current_user.username
    )
    return task

@router.post("/{notebook_id}/process")
async def process_notebook(
    notebook_id: str,
    prompt: str = Form(...),
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    nb = db.query(Notebook).filter(Notebook.id == notebook_id, Notebook.owner_user_id == current_user.id).first()
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")

    task = task_manager.submit_task(
        name=f"Process Notebook: {nb.title}",
        target=_notebook_process_task,
        args=(current_user.username, notebook_id, prompt),
        description="AI processing notebook content",
        owner_username=current_user.username
    )
    return task
