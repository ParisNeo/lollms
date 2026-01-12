from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.utils import secure_filename
import uuid
import os
import json
import base64
import shutil
from typing import Dict, Optional, Any

from backend.db import get_db
from backend.db.models.notebook import Notebook as DBNotebook
from backend.models import UserAuthDetails
from backend.session import get_current_active_user, get_user_notebook_assets_path
from backend.tasks.notebook_tasks import _ingest_notebook_sources_task

router = APIRouter()

@router.post("/{notebook_id}/upload")
async def upload_notebook_source(
    notebook_id: str,
    file: UploadFile = File(...),
    use_docling: bool = Form(False),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Uploads a file to the notebook's asset directory."""
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook: raise HTTPException(status_code=404)

    assets_path = get_user_notebook_assets_path(current_user.username, notebook_id)
    assets_path.mkdir(parents=True, exist_ok=True)
    
    fn = secure_filename(file.filename)
    unique_fn = f"{uuid.uuid4().hex[:8]}_{fn}"
    file_path = assets_path / unique_fn
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    is_text = file_path.suffix.lower() in ['.txt', '.md', '.py', '.js', '.json', '.html', '.css', '.c', '.cpp']
    if is_text:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        new_art = { "filename": unique_fn, "content": content, "type": "text", "is_loaded": True }
        notebook.artefacts = list(notebook.artefacts) + [new_art]
        db.commit()
    elif use_docling:
        from backend.task_manager import task_manager
        from backend.tasks.notebook_tasks import _convert_file_with_docling_task
        task_manager.submit_task(
            name=f"Convert: {fn}",
            target=_convert_file_with_docling_task,
            args=(current_user.username, notebook_id, str(file_path), unique_fn),
            owner_username=current_user.username
        )
    
    return {"filename": unique_fn}

@router.get("/{notebook_id}/assets/{filename}")
def get_notebook_asset(
    notebook_id: str,
    filename: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Retrieves a specific file asset for a notebook (Requires ownership)."""
    nb = db.query(DBNotebook.id).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not nb: raise HTTPException(status_code=403)
    path = get_user_notebook_assets_path(current_user.username, notebook_id) / secure_filename(filename)
    if not path.exists(): raise HTTPException(status_code=404)
    return FileResponse(path)

@router.delete("/{notebook_id}/generated_asset")
def delete_generated_asset(
    notebook_id: str,
    type: str, # 'video', 'audio', 'image'
    tab_id: str,
    slide_id: Optional[str] = None,
    image_index: Optional[int] = Query(None),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Deletes a generated asset (video, audio, or image version) and updates references."""
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook: raise HTTPException(status_code=404, detail="Notebook not found")

    target_tab = next((t for t in notebook.tabs if t['id'] == tab_id), None)
    if not target_tab: raise HTTPException(status_code=404, detail="Tab not found")

    try:
        tab_data = json.loads(target_tab['content'])
    except:
        raise HTTPException(status_code=500, detail="Invalid tab content")

    assets_path = get_user_notebook_assets_path(current_user.username, notebook_id)
    file_to_remove = None

    if type == 'video':
        if 'video_src' in tab_data:
            url = tab_data['video_src']
            filename = url.split('/')[-1]
            file_to_remove = assets_path / filename
            del tab_data['video_src']
    
    elif type == 'audio' and slide_id:
        if 'slides_data' in tab_data:
            slide = next((s for s in tab_data['slides_data'] if s['id'] == slide_id), None)
            if slide and 'audio_src' in slide:
                url = slide['audio_src']
                filename = url.split('/')[-1]
                file_to_remove = assets_path / filename
                del slide['audio_src']

    elif type == 'image' and slide_id and image_index is not None:
        if 'slides_data' in tab_data:
            slide = next((s for s in tab_data['slides_data'] if s['id'] == slide_id), None)
            if slide and 'images' in slide and 0 <= image_index < len(slide['images']):
                img_entry = slide['images'][image_index]
                if isinstance(img_entry, dict) and 'path' in img_entry:
                     filename = img_entry['path'].split('/')[-1]
                     file_to_remove = assets_path / filename
                
                # Remove from list
                slide['images'].pop(image_index)
                
                # Adjust selected index if needed
                current_sel = slide.get('selected_image_index', 0)
                if current_sel == image_index:
                    slide['selected_image_index'] = max(0, len(slide['images']) - 1) if slide['images'] else 0
                elif current_sel > image_index:
                    slide['selected_image_index'] = current_sel - 1

    if file_to_remove and file_to_remove.exists():
        try:
            os.remove(file_to_remove)
        except Exception as e:
            print(f"Error deleting file {file_to_remove}: {e}")

    target_tab['content'] = json.dumps(tab_data)
    flag_modified(notebook, "tabs")
    db.commit()
    
    return {"status": "success"}

@router.put("/{notebook_id}/tabs/{tab_id}/slides/{slide_id}/select_image")
def select_slide_image(
    notebook_id: str,
    tab_id: str,
    slide_id: str,
    payload: Dict[str, int], # { "index": 1 }
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Sets the active image index for a specific slide."""
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook: raise HTTPException(status_code=404)

    target_tab = next((t for t in notebook.tabs if t['id'] == tab_id), None)
    if not target_tab: raise HTTPException(status_code=404)

    try:
        tab_data = json.loads(target_tab['content'])
        slide = next((s for s in tab_data.get('slides_data', []) if s['id'] == slide_id), None)
        if slide:
            slide['selected_image_index'] = payload.get('index', 0)
            target_tab['content'] = json.dumps(tab_data)
            flag_modified(notebook, "tabs")
            db.commit()
            return {"status": "success"}
    except:
        pass
    
    raise HTTPException(status_code=400, detail="Failed to update selection")


@router.post("/{notebook_id}/describe_image")
async def describe_notebook_image(
    notebook_id: str,
    file: UploadFile = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """Asks the AI to describe an uploaded image."""
    from backend.session import get_user_lollms_client
    content = await file.read()
    b64 = base64.b64encode(content).decode('utf-8')
    lc = get_user_lollms_client(current_user.username)
    desc = lc.generate_text("Describe this image in detail for a prompt:", images=[b64])
    return {"description": desc}

@router.post("/{notebook_id}/describe_asset")
async def describe_notebook_asset(
    notebook_id: str,
    payload: Dict[str, str],
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """Asks the AI to describe an image already stored in the assets."""
    from backend.session import get_user_lollms_client
    fn = payload.get("filename")
    path = get_user_notebook_assets_path(current_user.username, notebook_id) / secure_filename(fn)
    if not path.exists(): raise HTTPException(status_code=404)
    b64 = base64.b64encode(path.read_bytes()).decode('utf-8')
    lc = get_user_lollms_client(current_user.username)
    return {"description": lc.generate_text("Describe this image for a text-to-image prompt:", images=[b64])}

@router.post("/{notebook_id}/scrape")
def scrape_url_to_notebook(
    notebook_id: str,
    payload: Dict[str, str],
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """Triggers a background task to scrape a URL and add it as a source."""
    from backend.task_manager import task_manager
    from backend.tasks.notebook_tasks import _ingest_notebook_sources_task
    return task_manager.submit_task(
        name=f"Scrape: {payload['url']}",
        target=_ingest_notebook_sources_task,
        args=(current_user.username, notebook_id, [payload['url']], [], [], [], [], "", None, {}, []),
        owner_username=current_user.username
    )

@router.post("/{notebook_id}/artefact")
def create_text_artefact(
    notebook_id: str,
    payload: Dict[str, str], 
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Manually adds a text block as a research source (artefact)."""
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook: raise HTTPException(status_code=404)
    fn = secure_filename(payload.get('title', 'note.txt'))
    path = get_user_notebook_assets_path(current_user.username, notebook_id) / fn
    path.write_text(payload.get('content', ''), encoding='utf-8')
    notebook.artefacts = list(notebook.artefacts) + [{ "filename": fn, "content": payload.get('content', ''), "type": "text", "is_loaded": True }]
    db.commit()
    return {"filename": fn}

@router.post("/{notebook_id}/import_sources")
def import_sources_to_notebook(
    notebook_id: str,
    payload: Dict[str, Any], # expects urls, wikipedia_urls, youtube_configs, arxiv_selected, initialPrompt, target_tab_id
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """Triggers a background ingestion task for an existing notebook."""
    from backend.task_manager import task_manager
    from backend.tasks.notebook_tasks import _ingest_notebook_sources_task
    
    prompt = payload.get('initialPrompt')
    # Use a generic name if no prompt is provided (Scrape only mode)
    task_name = f"Building: {prompt[:30]}..." if prompt else "Ingesting Sources (No Generation)"

    return task_manager.submit_task(
        name=task_name,
        target=_ingest_notebook_sources_task,
        args=(
            current_user.username,
            notebook_id,
            payload.get('urls', []),
            payload.get('youtube_configs', []),
            payload.get('wikipedia_urls', []),
            payload.get('google_search_queries', []),
            payload.get('arxiv_queries', []),
            prompt, 
            payload.get('target_tab_id', None),
            payload.get('arxiv_config', {}),
            payload.get('arxiv_selected', [])
        ),
        owner_username=current_user.username,
        description=notebook_id 
    )
