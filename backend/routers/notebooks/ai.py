# backend/routers/notebooks/ai.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
import json
import re
from typing import List, Optional
from pydantic import BaseModel

from backend.db import get_db
from backend.db.models.notebook import Notebook as DBNotebook
from backend.models import UserAuthDetails, TaskInfo
from backend.models.notebook import GenerateStructureRequest, ProcessRequest, GenerateTitleResponse
from backend.session import get_current_active_user, get_user_lollms_client

router = APIRouter()

class SlideChatRequest(BaseModel):
    prompt: str
    tab_id: str
    slide_id: str
    selected_artefacts: Optional[List[str]] = []

class BrainstormRequest(BaseModel):
    topic: str
    layout: str
    selected_artefacts: List[str]
    author: Optional[str] = None

class EnhanceRequest(BaseModel):
    prompt: str
    context: Optional[str] = ""

class RegenerateImageRequest(BaseModel):
    tab_id: str
    slide_id: str
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = ""

@router.post("/{notebook_id}/slide_chat")
async def chat_with_slide(
    notebook_id: str,
    request: SlideChatRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Mini-discussion system localized to a specific slide item."""
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")

    target_tab = next((t for t in notebook.tabs if t['id'] == request.tab_id), None)
    if not target_tab:
        raise HTTPException(status_code=404, detail="Tab not found")
    
    tab_data = json.loads(target_tab['content'])
    slide = next((s for s in tab_data['slides_data'] if s['id'] == request.slide_id), None)
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")

    if 'messages' not in slide:
        slide['messages'] = []

    lc = get_user_lollms_client(current_user.username)
    
    # 1. Build Research Context if artefacts are selected
    research_context = ""
    if request.selected_artefacts:
        knowledge_base = ""
        for art in notebook.artefacts:
            if art['filename'] in request.selected_artefacts:
                knowledge_base += f"\nSource: {art['filename']}\n{art['content']}\n"
        
        if knowledge_base:
            research_context = lc.long_context_processing(
                text_to_process=knowledge_base,
                contextual_prompt=f"Extract facts needed to answer the user query regarding the slide '{slide.get('title')}'.",
                system_prompt="You are a research assistant. Extract only facts from the sources."
            )

    # 2. Build history-aware prompt
    history = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in slide['messages'][-6:]])
    
    full_prompt = f"""Slide Title: {slide.get('title')}
    Slide Content: {', '.join(slide.get('bullets', []))}
    Notes: {slide.get('notes', '')}
    Research Data: {research_context}
    
    Recent History:
    {history}
    
    USER: {request.prompt}
    ASSISTANT:"""

    response_text = lc.generate_text(full_prompt, max_new_tokens=1024)

    # 3. Persist history
    slide['messages'].append({"role": "user", "content": request.prompt})
    slide['messages'].append({"role": "assistant", "content": response_text})

    target_tab['content'] = json.dumps(tab_data)
    flag_modified(notebook, "tabs")
    db.commit()

    return {"response": response_text, "history": slide['messages']}

@router.post("/{notebook_id}/brainstorm")
async def brainstorm_slide_content(
    notebook_id: str,
    request: BrainstormRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Performs LCP research on artefacts to suggest slide structure."""
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook:
        raise HTTPException(status_code=404)

    lc = get_user_lollms_client(current_user.username)
    
    research_data = ""
    if request.selected_artefacts:
        knowledge_base = ""
        for art in notebook.artefacts:
            if art['filename'] in request.selected_artefacts:
                knowledge_base += f"\nSource: {art['filename']}\n{art['content']}\n"
        
        research_data = lc.long_context_processing(
            text_to_process=knowledge_base,
            contextual_prompt=f"Perform deep research into the topic: '{request.topic}'. Extract key facts and visual themes.",
            system_prompt="Research Assistant"
        )

    author_info = f"Author: {request.author}\n" if request.author else ""

    # Use structured generation
    prompt = f"""{author_info}Based on research: {research_data}
    Topic: {request.topic}
    Layout: {request.layout}
    
    Suggest a slide title, 3-5 bullet points, a detailed visual prompt for image generation, AND detailed speaker notes (script).
    The notes must be PURE SPOKEN TEXT. Do not include stage directions, voice descriptions, quotes or markdown formatting in the notes.
    """
    
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "bullets": {"type": "array", "items": {"type": "string"}},
            "image_prompt": {"type": "string"},
            "notes": {"type": "string", "description": "Detailed speaker notes/speech script for this slide. Pure spoken words only."}
        },
        "required": ["title", "bullets", "image_prompt", "notes"]
    }
    
    data = lc.generate_structured_content(prompt, schema=schema)
    return data

@router.post("/structure")
def generate_notebook_structure(
    request: GenerateStructureRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    lc = get_user_lollms_client(current_user.username)
    prompt = f"Create a structure for a '{request.type}' notebook based on: \"{request.prompt}\". Return a JSON list of objects with 'title', 'type', and 'content'."
    try:
        response_text = lc.generate_text(prompt, max_new_tokens=1024)
        match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return [{"title": "Chapter 1", "content": response_text, "type": "markdown"}]
    except:
        return []

@router.post("/{notebook_id}/generate_title", response_model=GenerateTitleResponse)
def generate_notebook_title(
    notebook_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook: raise HTTPException(status_code=404)
    lc = get_user_lollms_client(current_user.username)
    title = lc.generate_text(f"Summarize this notebook content into a short title (max 5 words): {notebook.content[:1000]}").strip().strip('"')
    notebook.title = title
    db.commit()
    return GenerateTitleResponse(title=title)

@router.post("/{notebook_id}/process", response_model=TaskInfo)
def process_notebook_ai(
    notebook_id: str,
    payload: ProcessRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from backend.task_manager import task_manager
    from backend.tasks.notebook_tasks import _process_notebook_task
    
    # Verify notebook exists and user owns it
    exists = db.query(DBNotebook.id).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not exists: 
        raise HTTPException(status_code=404, detail="Notebook not found")

    # CRITICAL: We pass notebook_id as the description so the UI can reliably filter tasks
    return task_manager.submit_task(
        name=f"AI Task: {payload.output_type}",
        target=_process_notebook_task,
        args=(
            current_user.username, 
            notebook_id, 
            payload.prompt, 
            payload.input_tab_ids, 
            payload.output_type, 
            payload.target_tab_id, 
            payload.skip_llm, 
            payload.generate_speech, 
            payload.selected_artefacts,
            payload.use_rlm
        ),
        description=notebook_id, # Linked to current UI view
        owner_username=current_user.username
    )


@router.post("/enhance_prompt")
def enhance_prompt_endpoint(
    request: EnhanceRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    lc = get_user_lollms_client(current_user.username)
    system = "You are an expert prompt engineer for Image Generation models (Stable Diffusion, Midjourney, etc)."
    user_p = f"Improve this prompt for better visual aesthetics and detail: '{request.prompt}'. Keep it concise but descriptive."
    if request.context:
        user_p += f"\nContext: {request.context}"
    
    return {"enhanced_prompt": lc.generate_text(user_p, system_prompt=system).strip()}

@router.post("/{notebook_id}/generate_summary", response_model=TaskInfo)
def generate_summary_endpoint(
    notebook_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from backend.task_manager import task_manager
    from backend.tasks.notebook_tasks.slides_making import generate_deck_summary_task
    
    exists = db.query(DBNotebook.id).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not exists: raise HTTPException(status_code=404)

    return task_manager.submit_task(
        name="Generate Deck Summary",
        target=generate_deck_summary_task,
        args=(current_user.username, notebook_id),
        description="Analyzing slides to generate a coherent summary...",
        owner_username=current_user.username
    )

@router.post("/{notebook_id}/regenerate_slide_image", response_model=TaskInfo)
def regenerate_slide_image_endpoint(
    notebook_id: str,
    payload: RegenerateImageRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from backend.task_manager import task_manager
    from backend.tasks.notebook_tasks.image_gen import _regenerate_slide_image_task
    
    exists = db.query(DBNotebook.id).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not exists: raise HTTPException(status_code=404)

    return task_manager.submit_task(
        name=f"Regenerate Slide Image",
        target=_regenerate_slide_image_task,
        args=(current_user.username, notebook_id, payload.tab_id, payload.slide_id, payload.prompt, payload.negative_prompt),
        owner_username=current_user.username
    )
