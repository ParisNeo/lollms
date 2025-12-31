# backend/routers/notebooks.py
import uuid
import json
import shutil
import re
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
from backend.session import get_current_active_user, get_user_notebook_assets_path, get_user_lollms_client
from backend.task_manager import task_manager
from ascii_colors import trace_exception
from backend.tasks.notebook_tasks import _process_notebook_task, _ingest_notebook_sources_task, _convert_file_with_docling_task

router = APIRouter(
    prefix="/api/notebooks",
    tags=["Notebooks"],
    dependencies=[Depends(get_current_active_user)]
)

# ... (Pydantic Models remain same) ...
class StructureItem(BaseModel):
    title: str
    type: str = "markdown" 
    content: Optional[str] = ""

class NotebookCreate(BaseModel):
    title: str
    content: Optional[str] = ""
    type: Optional[str] = "generic"
    structure: Optional[List[StructureItem]] = None 
    initialPrompt: Optional[str] = None
    urls: Optional[List[str]] = None
    youtube_urls: Optional[List[str]] = None
    raw_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None 

class NotebookUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    artefacts: Optional[List[Dict[str, Any]]] = None
    tabs: Optional[List[Dict[str, Any]]] = None

class NotebookResponse(BaseModel):
    id: str
    title: str
    content: str
    type: str
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

# --- Endpoints ---

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
    
    if not initial_tabs:
         initial_tabs.append({
            "id": str(uuid.uuid4()),
            "title": "Main",
            "type": "markdown",
            "content": payload.initialPrompt or "",
            "images": []
        })

    content_to_store = payload.content
    if payload.metadata:
        try:
            content_obj = { "text": payload.content, "metadata": payload.metadata }
            content_to_store = json.dumps(content_obj)
        except: pass

    initial_artefacts = []
    if payload.raw_text:
        initial_artefacts.append({
            "filename": "Initial Notes",
            "content": payload.raw_text,
            "type": "text",
            "is_loaded": True
        })

    new_notebook = DBNotebook(
        title=payload.title,
        content=content_to_store,
        type=payload.type,
        owner_user_id=current_user.id,
        tabs=initial_tabs,
        artefacts=initial_artefacts
    )
    db.add(new_notebook)
    db.commit()
    db.refresh(new_notebook)
    
    # Trigger background ingestion for URLs
    if (payload.urls and len(payload.urls) > 0) or (payload.youtube_urls and len(payload.youtube_urls) > 0):
        task_manager.submit_task(
            name=f"Notebook {new_notebook.id}: Ingest Sources",
            target=_ingest_notebook_sources_task,
            args=(current_user.username, new_notebook.id, payload.urls or [], payload.youtube_urls or []),
            description="Scraping web and YouTube sources...",
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
    system_prompt = "You are a helpful AI assistant that structures documents and projects."
    prompt = f"""Create a structure for a '{request.type}' notebook based on this request: "{request.prompt}".
    Return a JSON list of objects. Each object must have:
    - "title": string
    - "type": string (one of: 'markdown', 'gallery', 'slides')
    - "content": string (Optional initial content)
    Example output: [{{"title": "Intro", "type": "markdown", "content": "# Intro"}}]
    """
    try:
        response_text = lc.generate_text(prompt, system_prompt=system_prompt, max_new_tokens=1024, temperature=0.7)
        try:
            import re
            match = re.search(r'\[.*\]', response_text, re.DOTALL)
            json_str = match.group(0) if match else response_text
            structure_data = json.loads(json_str)
            return [StructureItem(**item) for item in structure_data]
        except json.JSONDecodeError:
            return [StructureItem(title="Generated Plan", content=response_text)]
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")

@router.post("/{notebook_id}/upload")
async def upload_notebook_source(
    notebook_id: str,
    file: UploadFile = File(...),
    use_docling: bool = Form(False),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found.")

    assets_path = get_user_notebook_assets_path(current_user.username, notebook_id)
    assets_path.mkdir(parents=True, exist_ok=True)
    
    safe_filename = secure_filename(file.filename)
    file_path = assets_path / safe_filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    content = ""
    is_text = False
    try:
        if file_path.suffix.lower() in ['.txt', '.md', '.py', '.js', '.json', '.html', '.css', '.c', '.cpp', '.h', '.hpp']:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            is_text = True
    except: pass
        
    if is_text:
        new_artefact = {
            "filename": safe_filename,
            "content": content,
            "type": "text",
            "is_loaded": True
        }
        current_artefacts = list(notebook.artefacts)
        current_artefacts = [a for a in current_artefacts if a['filename'] != safe_filename]
        current_artefacts.append(new_artefact)
        notebook.artefacts = current_artefacts
        db.commit()
    elif use_docling:
        # Trigger Docling conversion task
        task_manager.submit_task(
            name=f"Notebook {notebook_id}: Convert {safe_filename}",
            target=_convert_file_with_docling_task,
            args=(current_user.username, notebook_id, str(file_path), safe_filename),
            description=f"Converting {safe_filename} to markdown...",
            owner_username=current_user.username
        )
    
    return {"filename": safe_filename}


@router.post("/{notebook_id}/artefact")
def create_text_artefact(
    notebook_id: str,
    payload: Dict[str, str], 
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found.")
        
    title = secure_filename(payload.get('title', 'untitled.txt'))
    content = payload.get('content', '')
    
    assets_path = get_user_notebook_assets_path(current_user.username, notebook_id)
    assets_path.mkdir(parents=True, exist_ok=True)
    (assets_path / title).write_text(content, encoding='utf-8')
    
    new_artefact = {
        "filename": title,
        "content": content,
        "type": "text",
        "is_loaded": True
    }
    
    current_artefacts = list(notebook.artefacts)
    current_artefacts = [a for a in current_artefacts if a['filename'] != title]
    current_artefacts.append(new_artefact)
    notebook.artefacts = current_artefacts
    db.commit()
    return {"filename": title}

@router.post("/{notebook_id}/generate_title", response_model=GenerateTitleResponse)
def generate_notebook_title(
    notebook_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    
    context = ""
    for tab in notebook.tabs:
        context += f"Tab: {tab.get('title')}\n{tab.get('content', '')[:500]}\n\n"
    
    if not context.strip():
        return {"title": "Untitled Notebook"}

    lc = get_user_lollms_client(current_user.username)
    prompt = f"Generate a short, descriptive title (max 5 words) for a notebook containing the following content:\n\n{context}"
    try:
        title = lc.generate_text(prompt, max_new_tokens=20).strip().strip('"')
        notebook.title = title
        db.commit()
        return {"title": title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Title generation failed: {e}")

@router.post("/{notebook_id}/process", response_model=TaskInfo)
def process_notebook_ai(
    notebook_id: str,
    payload: ProcessRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found.")

    task_name = f"Notebook {notebook_id} Process: {payload.output_type}"
    
    task = task_manager.submit_task(
        name=task_name,
        target=_process_notebook_task,
        args=(current_user.username, notebook_id, payload.prompt, payload.input_tab_ids, payload.output_type, payload.target_tab_id),
        description=f"Processing notebook with action: {payload.output_type}",
        owner_username=current_user.username
    )
    return task

@router.post("/{notebook_id}/scrape")
def scrape_url_to_notebook(
    notebook_id: str,
    payload: Dict[str, str],
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    from backend.tasks.notebook_tasks import _ingest_notebook_sources_task
    task = task_manager.submit_task(
        name=f"Notebook {notebook_id}: Scrape URL",
        target=_ingest_notebook_sources_task,
        args=(current_user.username, notebook_id, [payload['url']], []),
        owner_username=current_user.username
    )
    return task

@router.get("/{notebook_id}/export")
def export_notebook(
    notebook_id: str,
    format: str = "json",
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found.")

    if format == "json":
        data = {
            "title": notebook.title,
            "type": notebook.type,
            "content": notebook.content,
            "tabs": notebook.tabs,
            "artefacts": notebook.artefacts
        }
        return Response(content=json.dumps(data, indent=2), media_type="application/json", headers={"Content-Disposition": f"attachment; filename={secure_filename(notebook.title)}.json"})
    
    elif format == "pptx":
        try:
            from pptx import Presentation
            from pptx.util import Inches as PptxInches
            import io
            
            prs = Presentation()
            assets_path = get_user_notebook_assets_path(current_user.username, notebook_id)
            
            # --- Check Metadata for Slide Mode ---
            nb_metadata = {}
            try:
                loaded_content = json.loads(notebook.content)
                if isinstance(loaded_content, dict) and 'metadata' in loaded_content:
                    nb_metadata = loaded_content['metadata']
            except: pass
            
            slide_mode = nb_metadata.get('slide_mode', 'hybrid')

            for tab in notebook.tabs:
                if tab['type'] == 'slides':
                    try:
                        content_obj = json.loads(tab['content'])
                        slides_data = content_obj.get('slides_data', [])
                        
                        for s in slides_data:
                            # Resolve Image
                            img_path_local = None
                            selected_img = None
                            if s.get('images') and len(s.get('images')) > 0:
                                idx = s.get('selected_image_index', 0)
                                if idx < len(s['images']):
                                    selected_img = s['images'][idx]
                                    if selected_img and selected_img.get('path'):
                                        # Convert /api/notebooks/{id}/assets/{filename} -> local path
                                        filename = Path(selected_img['path']).name
                                        local_file = assets_path / filename
                                        if local_file.exists():
                                            img_path_local = str(local_file)

                            # Layout Selection
                            if slide_mode == 'image_only':
                                # Blank slide filled with image
                                slide_layout = prs.slide_layouts[6] # Blank
                                slide = prs.slides.add_slide(slide_layout)
                                
                                if img_path_local:
                                    # Add picture covering entire slide
                                    slide_width = prs.slide_width
                                    slide_height = prs.slide_height
                                    # Insert image
                                    pic = slide.shapes.add_picture(img_path_local, 0, 0, width=slide_width, height=slide_height)
                                    
                                    # Crop if needed to fill aspect ratio
                                    # python-pptx doesn't auto-crop easily, but resizing to fill is mostly what we want for "image only"
                                else:
                                    # Fallback text if no image found
                                    txBox = slide.shapes.add_textbox(PptxInches(1), PptxInches(1), PptxInches(8), PptxInches(5))
                                    tf = txBox.text_frame
                                    tf.text = s.get('title', 'Untitled') + "\n(Image missing)"

                            else:
                                # Standard Hybrid/Text
                                layout_type = s.get('layout', 'TitleBody')
                                slide_layout = prs.slide_layouts[1] # Title and Content
                                slide = prs.slides.add_slide(slide_layout)
                                
                                if slide.shapes.title: slide.shapes.title.text = s.get('title', '')
                                if len(slide.placeholders) > 1:
                                    if img_path_local:
                                        # If there's an image, use it in the placeholder if possible, or add separately
                                        # Simple logic: add image to right side, text to left? 
                                        # Or just use placeholder for text and add image floating.
                                        slide.placeholders[1].text = "\n".join(s.get('bullets', []))
                                        
                                        # Add image smaller
                                        slide.shapes.add_picture(img_path_local, PptxInches(5), PptxInches(2), width=PptxInches(4))
                                    else:
                                        slide.placeholders[1].text_frame.text = "\n".join(s.get('bullets', []))

                    except Exception as e:
                        print(f"Slide export error: {e}")
                        trace_exception(e)
            
            ppt_io = io.BytesIO()
            prs.save(ppt_io)
            ppt_io.seek(0)
            return Response(content=ppt_io.getvalue(), media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", headers={"Content-Disposition": f"attachment; filename={secure_filename(notebook.title)}.pptx"})
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"PPTX export failed: {e}")

    raise HTTPException(status_code=400, detail="Unsupported format.")

@router.get("/{notebook_id}/assets/{filename}")
def get_notebook_asset(
    notebook_id: str,
    filename: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Serves a specific asset (image/file) from a notebook's storage.
    """
    assets_path = get_user_notebook_assets_path(current_user.username, notebook_id)
    file_path = assets_path / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Asset not found.")
        
    return FileResponse(file_path)
