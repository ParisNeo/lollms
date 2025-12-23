import shutil
import uuid
import datetime
import json
import base64
from typing import List, Optional, Dict
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.db import get_db
from backend.db.models.notebook import Notebook
from backend.db.models.user import User as DBUser
from backend.db.models.config import TTIBinding as DBTTIBinding
from backend.models import UserAuthDetails, TaskInfo
from backend.session import get_current_active_user, get_user_notebook_assets_path, get_user_lollms_client, build_lollms_client_from_params
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
    tabs: Optional[List[dict]] = None

class NotebookPublic(BaseModel):
    id: str
    title: str
    content: str
    artefacts: List[dict]
    tabs: List[dict]
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True

class ScrapeRequest(BaseModel):
    url: str

class ArtefactCreate(BaseModel):
    title: str
    content: str

class ProcessRequest(BaseModel):
    prompt: str
    input_tab_ids: List[str] = []
    output_type: str = 'text' # 'text', 'images', 'presentation', 'story_structure', 'story_chapter'

# --- Helper: Context Builder ---
def _build_story_context(nb: Notebook, input_tab_ids: List[str], current_step: str):
    """
    Smart context builder for story mode.
    Always includes the first tab (Structure) if it exists.
    """
    context = ""
    tabs = nb.tabs or []
    
    # 1. Always include Structure (Assume Tab 0 is structure/manifest)
    if tabs and len(tabs) > 0:
        # If the user explicitly selected tabs, respect that, but verify structure is there
        structure_tab = tabs[0] 
        context += f"### STORY BIBLE / STRUCTURE\n{structure_tab.get('content', '')}\n\n"

    # 2. Add specifically selected inputs (e.g., previous chapter)
    for tab_id in input_tab_ids:
        # Skip if it's the structure tab we already added
        if tabs and tabs[0]['id'] == tab_id: continue
        
        tab = next((t for t in tabs if t['id'] == tab_id), None)
        if tab:
            context += f"### REFERENCE MATERIAL ({tab.get('title')})\n{tab.get('content', '')}\n\n"
            
    return context

# --- Helper: Agentic Tag Processor ---
def _handle_agentic_tags(text_chunk: str, username: str, db: Session, artefacts: List[dict]) -> str:
    """
    Parses <ScanForInfos> tags, performs RAG/Search, and returns the result to be injected.
    """
    # Regex for case-insensitive tag
    pattern = re.compile(r'<ScanForInfos>(.*?)</ScanForInfos>', re.IGNORECASE | re.DOTALL)
    match = pattern.search(text_chunk)
    
    if match:
        query = match.group(1).strip()
        print(f"Agentic Trigger: Scanning for '{query}'...")
        
        # Perform RAG on Artefacts
        found_info = []
        
        # Simple text search in loaded artefacts for now
        for art in artefacts:
            if art.get('is_loaded') and query.lower() in art.get('content', '').lower():
                # Extract a snippet
                content = art.get('content', '')
                idx = content.lower().find(query.lower())
                start = max(0, idx - 200)
                end = min(len(content), idx + 500)
                snippet = content[start:end]
                found_info.append(f"Source '{art['filename']}': ...{snippet}...")
        
        if not found_info:
            return f"\n[System Agent]: Scanned sources for '{query}' but found no direct text matches. Continue based on general knowledge.\n"
        
        return f"\n[System Agent]: Found info for '{query}':\n" + "\n".join(found_info) + "\n"

    return ""

# --- Tasks ---

def _notebook_process_task(task: Task, username: str, notebook_id: str, prompt: str, input_tab_ids: List[str], output_type: str):
    task.log(f"Starting notebook processing (Mode: {output_type})...")
    
    with task.db_session_factory() as db:
        nb = db.query(Notebook).filter(Notebook.id == notebook_id).first()
        if not nb:
            raise ValueError("Notebook not found")
        
        # --- Pre-computation Setup ---
        lc = get_user_lollms_client(username)
        current_tabs = list(nb.tabs) if nb.tabs else []
        
        # Auto-Title Check
        if nb.title == "New Research":
            task.log("Auto-generating notebook title...")
            try:
                title_prompt = f"Generate a short, concise, and descriptive title (max 6 words) for a research notebook based on this user instruction: '{prompt}'. Return ONLY the title text, no quotes or explanations."
                raw_title = lc.generate_text(title_prompt, max_new_tokens=50)
                new_title = lc.remove_thinking_blocks(raw_title).strip().strip('"').strip("'")
                
                if new_title and len(new_title) > 2:
                    nb.title = new_title
                    task.log(f"Notebook renamed to: {new_title}")
            except Exception as e:
                task.log(f"Failed to auto-generate title: {e}", "WARNING")

        # --- Create Output Tab Immediately ---
        # This allows the frontend to switch to it and show the spinner
        output_tab_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().strftime('%H:%M')
        
        # Determine tab type and initial title
        tab_type = "markdown"
        tab_title = f"Output {timestamp}"
        
        if output_type == 'images':
            tab_type = "gallery"
            tab_title = "Generated Images"
        elif output_type == 'presentation':
            tab_type = "slides"
            tab_title = "Presentation"
        elif output_type == 'story_structure':
            tab_type = "markdown"
            tab_title = "Story Bible"
        elif output_type == 'story_chapter':
            tab_type = "markdown"
            tab_title = f"Chapter {len(current_tabs)}" # Will fix index later if needed

        new_tab = {
            "id": output_tab_id,
            "title": tab_title,
            "type": tab_type,
            "content": "", # Empty initially
            "images": []
        }
        
        # Insert or Append based on mode
        if output_type == 'story_structure':
             # If structure already exists, we might want to update it, but for now let's prepend/replace
            if current_tabs and current_tabs[0]['title'] in ['Main', 'Structure', 'Story Bible', 'New Research']:
                current_tabs[0] = new_tab # Replace first tab
            else:
                current_tabs.insert(0, new_tab)
        else:
            current_tabs.append(new_tab)
            
        nb.tabs = current_tabs
        flag_modified(nb, "tabs")
        db.commit() # Commit so frontend sees the new tab
        
        task.log(f"Created new tab '{tab_title}'. Processing content...")

        # --- Build Context ---
        context = ""
        # From Artefacts
        if nb.artefacts:
            for art in nb.artefacts:
                if art.get("is_loaded"):
                    context += f"\n\n--- Source: {art.get('filename')} ---\n{art.get('content','')}\n--- End Source ---\n"
        
        # From Tabs
        input_tabs_content = ""
        if output_type != 'story_chapter': 
            for tab_id in input_tab_ids:
                tab = next((t for t in current_tabs if t['id'] == tab_id), None)
                if tab and tab.get('type') == 'markdown':
                    input_tabs_content += f"\n\n--- Input Tab: {tab.get('title')} ---\n{tab.get('content', '')}\n--- End Input Tab ---\n"
            full_context = f"{context}\n{input_tabs_content}"
        else:
            # Story chapter uses special context builder
            full_context = context 

        # --- Generation Logic ---

        if output_type == 'images':
            task.set_progress(10)
            task.log("Generating image prompts...")
            
            prompt_generation_prompt = f"""
[CONTEXT]
{full_context}

[INSTRUCTION]
{prompt}
Based on the context and instruction, generate a list of detailed image prompts to visualize the content.
Return ONLY a valid JSON list of strings. Example: ["A futuristic city", "A robot in a garden"]
"""
            raw_json_prompts = lc.generate_text(prompt_generation_prompt, max_new_tokens=1024)
            json_prompts = lc.remove_thinking_blocks(raw_json_prompts)
            
            prompts_list = []
            try:
                prompts_list = json.loads(json_prompts)
                if not isinstance(prompts_list, list): raise ValueError
            except:
                # Fallback extraction
                start = json_prompts.find('[')
                end = json_prompts.rfind(']') + 1
                if start != -1 and end != -1:
                    try: prompts_list = json.loads(json_prompts[start:end])
                    except: prompts_list = [prompt]
                else:
                    prompts_list = [prompt]
            
            task.log(f"Generated {len(prompts_list)} prompts. Starting image generation...")
            
            # Re-init client with TTI
            user_db = db.query(DBUser).filter(DBUser.username == username).first()
            tti_binding_alias = None
            tti_model_name = None
            if user_db.tti_binding_model_name and '/' in user_db.tti_binding_model_name:
                tti_binding_alias, tti_model_name = user_db.tti_binding_model_name.split('/', 1)
            else:
                def_bind = db.query(DBTTIBinding).filter(DBTTIBinding.is_active==True).first()
                if def_bind: tti_binding_alias = def_bind.alias

            tti_client = build_lollms_client_from_params(username=username, tti_binding_alias=tti_binding_alias, tti_model_name=tti_model_name, load_llm=False, load_tti=True)
            
            if not tti_client.tti:
                 task.log("No TTI binding available.", "ERROR")
                 return

            generated_images = []
            assets_path = get_user_notebook_assets_path(username, notebook_id)
            assets_path.mkdir(parents=True, exist_ok=True)

            for i, p in enumerate(prompts_list):
                if task.cancellation_event.is_set(): break
                task.log(f"Generating image {i+1}/{len(prompts_list)}: {p[:30]}...")
                try:
                    img_bytes = tti_client.tti.generate_image(prompt=p, width=1024, height=1024)
                    if img_bytes:
                        fname = f"gen_{uuid.uuid4().hex}.png"
                        with open(assets_path / fname, "wb") as f:
                            f.write(img_bytes)
                        generated_images.append({
                            "path": f"/user_data/users/{username}/notebook_assets/{notebook_id}/{fname}", 
                            "prompt": p
                        })
                except Exception as e:
                    task.log(f"Failed to generate image for '{p}': {e}", "ERROR")
                
                # Update tab content progressively (images list)
                new_tab["images"] = generated_images
                new_tab["content"] = f"Generating images... ({i+1}/{len(prompts_list)})"
                
                # We need to find the tab in the current object from DB to update it
                # Since we modified the list locally, let's re-assign to be safe or modify object in place if attached
                # Safe approach: locate by ID
                for t in nb.tabs:
                    if t['id'] == output_tab_id:
                        t['images'] = generated_images
                        t['content'] = f"Generated {len(generated_images)} images."
                        break
                flag_modified(nb, "tabs")
                db.commit()
                
                task.set_progress(10 + int(90 * (i + 1) / len(prompts_list)))

        elif output_type == 'presentation':
            task.set_progress(10)
            task.log("Generating presentation outline...")
            
            slide_prompt = f"""
[CONTEXT]
{full_context}

[INSTRUCTION]
{prompt}
Create a presentation based on the context and instruction.
Output the content in Markdown format, where each slide is separated by "---".
Each slide should have a title (## Title) and bullet points.
"""     
            def callback(chunk, msg_type=None, params=None, **kwargs):
                if task.cancellation_event.is_set(): return False
                return True

            slides_md_raw = lc.generate_text(slide_prompt, streaming_callback=callback)
            slides_md = lc.remove_thinking_blocks(slides_md_raw)
            
            # Update Tab
            for t in nb.tabs:
                if t['id'] == output_tab_id:
                    t['content'] = slides_md
                    break
            flag_modified(nb, "tabs")
            db.commit()

        elif output_type == 'story_structure':
            task.set_progress(10)
            task.log("Building Story Structure...")
            
            full_prompt = f"""
[SOURCES]
{full_context}

[USER IDEA]
{prompt}

[TASK]
Create a comprehensive Story Bible and Structure. 
Include:
1. Title & Logline
2. Themes & Tone
3. Character Profiles (Protagonist, Antagonist, Supporting)
4. World Building Rules
5. High-Level Plot Outline (Chapter by Chapter list)

Format as Markdown.
"""
            generated_raw = lc.generate_text(full_prompt)
            generated = lc.remove_thinking_blocks(generated_raw)
            
            for t in nb.tabs:
                if t['id'] == output_tab_id:
                    t['content'] = generated
                    break
            flag_modified(nb, "tabs")
            db.commit()

        elif output_type == 'story_chapter':
            task.set_progress(10)
            task.log("Writing Chapter...")
            
            story_context = _build_story_context(nb, input_tab_ids, "Drafting")
            
            full_prompt = f"""
{story_context}

[TASK]
Write the next chapter or the specific scene described below.
Adhere strictly to the Tone and Character Voices defined in the Story Bible.
Use the Reference Material provided for continuity.

[INSTRUCTION]
{prompt}

[AGENTIC TOOLS]
If you need to check specific details from the source documents, write: <ScanForInfos>search query</ScanForInfos>
"""
            
            final_chapter_text = ""
            
            # Callback to update DB progressively? 
            # Doing DB updates on every token is too heavy. 
            # We will update every chunk or loop.
            
            MAX_LOOPS = 3
            current_prompt = full_prompt
            
            for loop in range(MAX_LOOPS):
                task.log(f"Generation Loop {loop+1}/{MAX_LOOPS}")
                
                segment_raw = lc.generate_text(current_prompt)
                segment = lc.remove_thinking_blocks(segment_raw)
                
                agent_info = _handle_agentic_tags(segment, username, db, nb.artefacts)
                
                final_chapter_text += segment
                
                # Progressive Update
                for t in nb.tabs:
                    if t['id'] == output_tab_id:
                        t['content'] = final_chapter_text
                        break
                flag_modified(nb, "tabs")
                db.commit()

                if agent_info:
                    task.log("Agent info found, injecting and continuing...")
                    final_chapter_text += f"\n\n> *System Info: {agent_info.strip()}*\n\n"
                    current_prompt = f"{story_context}\n\n[PREVIOUSLY WROTE]\n{final_chapter_text}\n\n[NEW INFO]\n{agent_info}\n\n[INSTRUCTION]\nContinue writing based on the new info."
                else:
                    break 
            
        else: # Default Text
            task.set_progress(10)
            task.log("Generating text...")
            
            full_prompt = f"""
[CONTEXT]
{full_context}

[INSTRUCTION]
{prompt}
"""
            def callback(chunk, msg_type=None, params=None, **kwargs):
                if task.cancellation_event.is_set(): return False
                return True

            generated_text_raw = lc.generate_text(full_prompt, streaming_callback=callback)
            generated_text = lc.remove_thinking_blocks(generated_text_raw)
            
            for t in nb.tabs:
                if t['id'] == output_tab_id:
                    t['content'] = generated_text
                    break
            flag_modified(nb, "tabs")
            db.commit()

        task.log("Notebook updated.")
        
    task.set_progress(100)
    return {"notebook_id": notebook_id}

def _notebook_scrape_task(task: Task, username: str, notebook_id: str, url: str):
    if ScrapeMaster is None:
        raise ImportError("ScrapeMaster is not installed.")
        
    task.log(f"Scraping URL: {url}")
    task.set_progress(10)
    
    try:
        scraper = ScrapeMaster(url)
        content = scraper.scrape()
        
        if not content:
            raise ValueError("No content extracted from URL.")
            
        task.set_progress(80)
        task.log("Content extracted. Saving to notebook...")
        
        with task.db_session_factory() as db:
            nb = db.query(Notebook).filter(Notebook.id == notebook_id).first()
            if not nb:
                raise ValueError("Notebook not found")
            
            current_artefacts = list(nb.artefacts) if nb.artefacts else []
            filename = f"Scrape: {url}"
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
            "tabs": n.tabs or [],
            "created_at": n.created_at.isoformat(),
            "updated_at": n.updated_at.isoformat() if n.updated_at else n.created_at.isoformat()
        } for n in notebooks
    ]

@router.post("", response_model=NotebookPublic)
def create_notebook(data: NotebookCreate, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_active_user)):
    initial_tab = {
        "id": str(uuid.uuid4()),
        "title": "Main",
        "type": "markdown",
        "content": data.content or "",
        "images": []
    }
    
    nb = Notebook(
        title=data.title,
        content=data.content,
        owner_user_id=current_user.id,
        artefacts=[],
        tabs=[initial_tab]
    )
    db.add(nb)
    db.commit()
    db.refresh(nb)
    return {
            "id": nb.id,
            "title": nb.title,
            "content": nb.content or "",
            "artefacts": nb.artefacts or [],
            "tabs": nb.tabs or [],
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
    if data.tabs is not None:
        nb.tabs = data.tabs
        flag_modified(nb, "tabs")
    
    db.commit()
    db.refresh(nb)
    return {
            "id": nb.id,
            "title": nb.title,
            "content": nb.content or "",
            "artefacts": nb.artefacts or [],
            "tabs": nb.tabs or [],
            "created_at": nb.created_at.isoformat(),
            "updated_at": nb.updated_at.isoformat() if nb.updated_at else nb.created_at.isoformat()
        }

@router.delete("/{notebook_id}")
def delete_notebook(notebook_id: str, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_active_user)):
    nb = db.query(Notebook).filter(Notebook.id == notebook_id, Notebook.owner_user_id == current_user.id).first()
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")
    
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
        
    text_content, _ = extract_text_from_file_bytes(content_bytes, file.filename)
    
    current_artefacts = list(nb.artefacts) if nb.artefacts else []
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

    current_artefacts = list(nb.artefacts) if nb.artefacts else []
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
    request: ProcessRequest,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    nb = db.query(Notebook).filter(Notebook.id == notebook_id, Notebook.owner_user_id == current_user.id).first()
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")

    task = task_manager.submit_task(
        name=f"Process Notebook: {nb.title}",
        target=_notebook_process_task,
        args=(current_user.username, notebook_id, request.prompt, request.input_tab_ids, request.output_type),
        description=f"AI processing notebook ({request.output_type})",
        owner_username=current_user.username
    )
    return task

@router.post("/{notebook_id}/generate_title")
async def generate_notebook_title(
    notebook_id: str,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    nb = db.query(Notebook).filter(Notebook.id == notebook_id, Notebook.owner_user_id == current_user.id).first()
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")
    
    content_snippet = (nb.content or "")[:500]
    tabs_snippet = ""
    if nb.tabs:
        for tab in nb.tabs[:3]: 
            tabs_snippet += f"Tab: {tab.get('title','')}\n{tab.get('content','v')[:200]}\n"
            
    prompt = f"""Generate a short, concise, and descriptive title (max 6 words) for this research notebook based on these snippets:
    
    {content_snippet}
    
    {tabs_snippet}
    
    Return ONLY the title text, no quotes."""
    
    lc = get_user_lollms_client(current_user.username)
    raw_title = lc.generate_text(prompt, max_new_tokens=50)
    new_title = lc.remove_thinking_blocks(raw_title).strip().strip('"').strip("'")
    
    if new_title:
        nb.title = new_title
        db.commit()
        return {"title": new_title}
    else:
        raise HTTPException(status_code=500, detail="Failed to generate title")
