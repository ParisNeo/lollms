import json
import uuid
from backend.task_manager import Task
from backend.db.models.notebook import Notebook as DBNotebook
from backend.session import build_lollms_client_from_params, get_user_notebook_assets_path
from sqlalchemy.orm.attributes import flag_modified

def _regenerate_slide_image_task(task: Task, username: str, notebook_id: str, tab_id: str, slide_id: str, prompt: str = None, negative_prompt: str = ""):
    task.log("Starting slide image regeneration...")
    task.set_progress(10)
    
    with task.db_session_factory() as db:
        notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
        if not notebook: raise Exception("Notebook not found")
        
        target_tab = next((t for t in notebook.tabs if t['id'] == tab_id), None)
        if not target_tab: raise Exception("Tab not found")
        
        try:
            tab_data = json.loads(target_tab['content'])
        except:
            raise Exception("Invalid tab content")
            
        slide = next((s for s in tab_data.get('slides_data', []) if s['id'] == slide_id), None)
        if not slide: raise Exception("Slide not found")

        # Determine prompt
        if not prompt:
            if slide.get('images') and len(slide['images']) > 0:
                # Use last used prompt
                last_img = slide['images'][-1]
                prompt = last_img.get('prompt') if isinstance(last_img, dict) else slide.get('visual_description', '')
            else:
                prompt = slide.get('visual_description', '')
        
        if not prompt:
             raise Exception("No prompt available for regeneration")

        task.log(f"Generating image for: {prompt[:50]}...")
        task.set_progress(30)
        
        # Init Lollms Client
        lc = build_lollms_client_from_params(username=username, load_llm=False, load_tti=True)
        if not lc.tti: raise Exception("No TTI binding active")
        
        image_bytes = lc.tti.generate_image(prompt=prompt, negative_prompt=negative_prompt, width=1024, height=1024)
        if not image_bytes: raise Exception("Generation failed")
        
        task.set_progress(80)
        
        # Save image
        assets_path = get_user_notebook_assets_path(username, notebook_id)
        assets_path.mkdir(parents=True, exist_ok=True)
        
        filename = f"slide_gen_{uuid.uuid4().hex[:8]}.png"
        (assets_path / filename).write_bytes(image_bytes)
        
        # Update Slide Data
        new_entry = {
            "path": f"/api/notebooks/{notebook_id}/assets/{filename}",
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "generated_at": str(uuid.uuid1()) 
        }
        
        if 'images' not in slide: slide['images'] = []
        slide['images'].append(new_entry)
        slide['selected_image_index'] = len(slide['images']) - 1
        
        # Save back to DB
        target_tab['content'] = json.dumps(tab_data)
        flag_modified(notebook, "tabs")
        db.commit()
        
        task.set_progress(100)
        return {"notebook_id": notebook_id, "tab_id": tab_id, "slide_id": slide_id, "new_image": new_entry}
