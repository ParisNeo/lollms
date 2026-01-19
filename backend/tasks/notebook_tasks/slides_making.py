import uuid
import json
import re
import base64
import os
import tempfile
from pathlib import Path
from backend.task_manager import Task
from backend.db.models.notebook import Notebook as DBNotebook
from backend.db.models.user import User as DBUser
from backend.db.models.voice import UserVoice as DBUserVoice
from ascii_colors import trace_exception
from backend.session import get_user_lollms_client, build_lollms_client_from_params, get_user_notebook_assets_path, get_user_data_root
from typing import List, Dict, Any
from .common import gather_context, get_notebook_metadata
from sqlalchemy.orm.attributes import flag_modified

def _try_parse_json(text: str) -> Any:
    """Attempts to parse JSON, handling common LLM formatting errors."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        text_clean = re.sub(r',\s*([\]}])', r'\1', text)
        try:
            return json.loads(text_clean)
        except json.JSONDecodeError:
            return None

def _extract_json(text: str, task: Task = None) -> Any:
    """Robust JSON extraction from LLM output."""
    if not text: return None
    
    if task:
        task.log(f"Attempting to extract JSON from {len(text)} chars...", "INFO")

    code_block_pattern = re.compile(r'```(?:json)?\s*(\{.*?\})\s*```', re.DOTALL)
    match = code_block_pattern.search(text)
    if match:
        clean_text = match.group(1)
        res = _try_parse_json(clean_text)
        if res: return res

    try:
        start_idx = -1
        end_idx = -1
        for i, char in enumerate(text):
            if char in ['{', '[']:
                start_idx = i
                break
        for i in range(len(text) - 1, -1, -1):
            if text[i] in ['}', ']']:
                end_idx = i
                break
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidate = text[start_idx : end_idx + 1]
            res = _try_parse_json(candidate)
            if res: return res
    except Exception as e:
        if task: task.log(f"Regex extraction failed: {e}", "WARNING")

    clean_text = re.sub(r'//.*$', '', text, flags=re.MULTILINE)
    res = _try_parse_json(clean_text)
    if res: return res

    if task:
        task.log(f"Failed to parse JSON. Raw start: {text[:200]}...", "ERROR")
        
    return None

def _clean_text_for_tts(text: str) -> str:
    """Removes special characters and emojis that confuse TTS engines."""
    if not text: return ""
    text = re.sub(r'[*#]', '', text)
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    return text.strip()

def _extract_knowledge_from_artefacts(task: Task, lc, notebook: DBNotebook, selected_artefacts: List[str], focus_topic: str, presentation_context: str = "", mini_discussion: str = "") -> str:
    if not selected_artefacts:
        return ""
        
    task.log(f"Researching topic: {focus_topic}")
    
    knowledge_base = ""
    for art in (notebook.artefacts or []):
        if art['filename'] in selected_artefacts:
            knowledge_base += f"\n--- Source: {art['filename']} ---\n{art.get('content', '')}\n"
    
    if not knowledge_base.strip():
        return ""

    research_prompt = f"""
    [Presentation Context]
    {presentation_context}

    [Discussion History]
    {mini_discussion}

    [Task]
    The user is adding/editing a slide about: "{focus_topic}".
    Scan the sources and extract specific factual points and visual cues that align with the requirements.
    Return a summary of relevant information to support image generation and content creation.
    """
    
    research_results = lc.long_context_processing(
        text_to_process=knowledge_base,
        contextual_prompt=research_prompt,
        system_prompt="Research Specialist"
    )
    
    if isinstance(research_results, dict):
        if 'error' in research_results:
            task.log(f"Context Error: {research_results['error']}", "WARNING")
            return ""
        research_results = research_results.get('content', research_results.get('text', str(research_results)))
    
    if not isinstance(research_results, str):
        research_results = str(research_results)

    task.log("Research step complete.")
    return research_results


def process_slides_making(task: Task, notebook: DBNotebook, username: str, prompt: str, input_tab_ids: List[str], action: str, target_tab_id: str = None, selected_artefacts: List[str] = None):
    lc = get_user_lollms_client(username)
    metadata = get_notebook_metadata(notebook)
    assets_path = get_user_notebook_assets_path(username, notebook.id)
    notebook_language = getattr(notebook, 'language', 'en')
    
    target_tab = None
    if target_tab_id:
        target_tab = next((t for t in notebook.tabs if t['id'] == target_tab_id), None)
    if not target_tab:
        target_tab = next((t for t in notebook.tabs if t['type'] == 'slides'), None)

    try:
        if target_tab:
            tab_data = json.loads(target_tab['content'])
        else:
            tab_data = {"slides_data": [], "mode": "hybrid", "summary": ""}
    except:
        tab_data = {"slides_data": [], "mode": "hybrid", "summary": ""}

    # --- ACTION: INITIAL PROCESS (Full Atomic Build Pipeline) ---
    if action == 'initial_process':
        task.log("Phase 1: Deep Knowledge Extraction...")
        task.set_progress(5)
        
        context_parts = []
        for art in (notebook.artefacts or []):
            if art.get('is_loaded') and art.get('content'):
                context_parts.append(f"--- Source: {art['filename']} ---\n{art['content']}")
        
        context_text = "\n\n".join(context_parts)
        knowledge_core = ""
        
        if context_text.strip():
            task.log("Analyzing sources for narrative and data...")
            research_prompt = f"Extract all key facts, narratives, statistics, and logical steps relevant to producing a slide deck about: '{prompt}'."
            knowledge_core = lc.long_context_processing(text_to_process=context_text, contextual_prompt=research_prompt)
            if isinstance(knowledge_core, dict):
                knowledge_core = knowledge_core.get('content', knowledge_core.get('text', ""))
        else:
            knowledge_core = f"Rely on general AI knowledge for: {prompt}"

        task.log("Phase 2: Architectural Deck Design...")
        task.set_progress(20)

        pref_style = metadata.get('style_preset', 'Modern Corporate')
        num_slides = int(metadata.get('num_slides', 8))

        design_prompt = f"""
        Objective: {prompt}
        Research: {knowledge_core}
        Slides Requested: {num_slides}
        Visual Style: {pref_style}

        TASK: Generate a complete presentation structure. For each slide, select the most appropriate layout:
        - 'TitleImageBody': Standard text bullets next to a visual.
        - 'ImageOnly': Full-screen high impact visual with title overlay.
        - 'HtmlGraphic': A data-driven visualization using HTML/CSS/JS.
        - 'TextOnly': Centered quote or key takeaway.
        - 'TitleOnly': Major section introduction.

        Output JSON structure: {{ "slides": [ {{ "title", "layout", "bullets", "image_prompt", "negative_prompt", "notes", "html_request" }} ] }}
        """

        schema = {
            "type": "object",
            "properties": {
                "slides": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "layout": {"type": "string", "enum": ["TitleImageBody", "ImageOnly", "HtmlGraphic", "TextOnly", "TitleOnly"]},
                            "bullets": {"type": "array", "items": {"type": "string"}},
                            "image_prompt": {"type": "string"},
                            "negative_prompt": {"type": "string"},
                            "notes": {"type": "string", "description": "Speech script for the presenter"},
                            "html_request": {"type": "string", "description": "Specific visual goal for HtmlGraphic layout"}
                        },
                        "required": ["title", "layout", "bullets", "image_prompt", "notes"]
                    }
                }
            },
            "required": ["slides"]
        }

        design_output = lc.generate_structured_content(design_prompt, schema=schema)
        generated_slides = design_output.get("slides", []) if design_output else []

        if not generated_slides:
            task.log("Design phase failed to return slides.", "ERROR")
            return None

        task.log(f"Phase 3: Production of {len(generated_slides)} slides...")
        lc_tti = build_lollms_client_from_params(username, load_llm=False, load_tti=True)
        final_slides_data = []

        for i, s in enumerate(generated_slides):
            task.log(f"Processing Slide {i+1}: {s.get('title')}")
            
            # 1. Handle HTML Graphics
            html_code = ""
            if s.get('layout') == 'HtmlGraphic':
                task.log("Generating visualization code...")
                html_sys = "You are a web visualization expert. Output ONLY self-contained, responsive HTML/CSS/JS code."
                html_code = lc.generate_text(f"Create a visualization for: {s.get('html_request', s.get('title'))}", system_prompt=html_sys)
                code_match = re.search(r'```html(.*?)```', html_code, re.DOTALL)
                html_code = code_match.group(1).strip() if code_match else html_code

            # 2. Handle TTI Production
            img_list = []
            if lc_tti.tti and s.get('layout') not in ['TextOnly', 'TitleOnly']:
                try:
                    visual_p = f"{s.get('image_prompt')}, {pref_style} style, high quality presentation asset."
                    neg_p = s.get('negative_prompt', "text, letters, words, blurry, watermark, low quality")
                    img_bytes = lc_tti.tti.generate_image(prompt=visual_p, negative_prompt=neg_p)
                    if img_bytes:
                        fname = f"auto_v_{uuid.uuid4().hex[:8]}.png"
                        (assets_path / fname).write_bytes(img_bytes)
                        img_list.append({
                            "path": f"/api/notebooks/{notebook.id}/assets/{fname}",
                            "prompt": visual_p,
                            "created_at": str(base64.b64encode(fname.encode()))
                        })
                except Exception as e:
                    task.log(f"Visual failed for slide {i+1}: {e}", "WARNING")

            # 3. Assemble atomic slide object
            new_slide = {
                "id": str(uuid.uuid4()),
                "title": s.get('title'),
                "layout": s.get('layout'),
                "bullets": s.get('bullets', []),
                "images": img_list,
                "notes": s.get('notes', ''),
                "html_content": html_code,
                "selected_image_index": 0,
                "messages": []
            }
            final_slides_data.append(new_slide)

            # ATOMIC DB UPDATE: Commit progress after every single slide is produced
            with task.db_session_factory() as db:
                db_notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook.id).first()
                if db_notebook:
                    current_tab = next((t for t in db_notebook.tabs if t['id'] == (target_tab_id or target_tab['id'])), None)
                    if current_target:
                        current_target['content'] = json.dumps({
                            "slides_data": final_slides_data, 
                            "mode": "hybrid", 
                            "summary": f"Built {i+1} slides..."
                        })
                        flag_modified(db_notebook, "tabs")
                        db.commit()

            task.set_progress(20 + int((i+1)/len(generated_slides) * 80))

        return target_tab_id or target_tab['id']

    # --- ACTION: ADD FULL SLIDE ---
    elif action == 'add_full_slide':
        try:
            slide_config = _extract_json(prompt, task) or {}
            task.log("Generating visual for single slide...")
            lc_tti = build_lollms_client_from_params(username, load_llm=False, load_tti=True)
            img_list = []
            
            if slide_config.get('image_prompt') and lc_tti.tti:
                visual_p = f"{slide_config['image_prompt']}, {metadata.get('style_preset', '')}"
                img_bytes = lc_tti.tti.generate_image(prompt=visual_p)
                if img_bytes:
                    fname = f"slide_{uuid.uuid4().hex[:8]}.png"
                    (assets_path / fname).write_bytes(img_bytes)
                    img_list.append({"path": f"/api/notebooks/{notebook.id}/assets/{fname}", "prompt": visual_p})

            new_slide = {
                "id": str(uuid.uuid4()),
                "title": slide_config.get('title', 'Untitled'),
                "layout": slide_config.get('layout', 'TitleImageBody'),
                "bullets": slide_config.get('bullets', []),
                "images": img_list,
                "selected_image_index": 0,
                "messages": [],
                "notes": slide_config.get('notes', ''),
                "html_content": slide_config.get('html_code', '')
            }
            tab_data['slides_data'].append(new_slide)
            if target_tab:
                target_tab['content'] = json.dumps(tab_data)
                return target_tab['id']
        except Exception as e:
            task.log(f"Add slide failed: {e}", "ERROR")

    # --- ACTION: GENERATE TITLE ---
    elif action == 'generate_slide_title':
        task.log("Generating slide title...")
        if not target_tab: return None
        
        match = re.match(r"SLIDE_INDEX:(\d+)\|\s*(.*)", prompt, re.DOTALL)
        if not match: return target_tab['id']
            
        slide_idx = int(match.group(1))
        user_steer = match.group(2).strip()
        
        if slide_idx >= len(tab_data['slides_data']): return target_tab['id']

        slide = tab_data['slides_data'][slide_idx]
        context_str = f"Slide Content: {', '.join(slide.get('bullets', []))}\nNotes: {slide.get('notes', '')}\nImage Description: {slide.get('image_prompt', '')}"
        
        sys_prompt = "You are a professional presentation expert. Create a short, engaging, and relevant title. Return ONLY the title text."
        user_p = f"{context_str}\n\nTask: Generate a title for this slide."
        if user_steer: user_p += f"\nInstruction: {user_steer}"
        
        title = lc.generate_text(user_p, system_prompt=sys_prompt).strip().strip('"')
        slide['title'] = title
        target_tab['content'] = json.dumps(tab_data)
        return target_tab['id']

    # --- ACTION: GENERATE NOTES ---
    elif action == 'generate_notes':
        task.log("Generating speaker notes...")
        if not target_tab: return None

        match = re.match(r"SLIDE_INDEX:(\d+)\|\s*(.*)", prompt, re.DOTALL)
        if not match: return target_tab['id']
            
        slide_idx = int(match.group(1))
        user_steer = match.group(2).strip()
        
        if slide_idx >= len(tab_data['slides_data']): return target_tab['id']

        slide = tab_data['slides_data'][slide_idx]
        context_str = f"""
        Deck Summary: {tab_data.get('summary', 'No summary available.')}
        Current Slide: {slide.get('title')}
        Bullets: {', '.join(slide.get('bullets', []))}
        """
        
        system_prompt = "You are a speech writer generating text for a Text-To-Speech engine. Write ONLY the verbal content the speaker will say."
        user_instruction = f"{context_str}\n\nTask: Write the spoken script for this slide."
        if user_steer: user_instruction += f"\nStyle/Content Instructions: {user_steer}"
            
        notes = lc.generate_text(user_instruction, system_prompt=system_prompt)
        cleaned_notes = re.sub(r'\[.*?\]', '', notes)
        cleaned_notes = re.sub(r'\*.*?\*', '', cleaned_notes).strip().strip('"')
        
        slide['notes'] = cleaned_notes
        target_tab['content'] = json.dumps(tab_data)
        return target_tab['id']

    # --- ACTION: GENERATE AUDIO FOR SLIDE ---
    elif action == 'generate_audio':
        task.log(f"Generating audio for slide...")
        match = re.match(r"SLIDE_INDEX:(\d+)", prompt)
        if not match: return target_tab['id']
        slide_idx = int(match.group(1))
        slide = tab_data['slides_data'][slide_idx]
        text_to_speak = slide.get('notes', slide.get('title', ''))
        if not text_to_speak.strip(): return target_tab['id']

        voice_to_use = None
        with task.db_session_factory() as db:
            db_user = db.query(DBUser).filter(DBUser.username == username).first()
            if db_user and db_user.active_voice_id:
                active_voice = db.query(DBUserVoice).filter(DBUserVoice.id == db_user.active_voice_id).first()
                if active_voice:
                    v_path = get_user_data_root(username) / "voices" / active_voice.file_path
                    if v_path.exists(): voice_to_use = str(v_path.resolve())

        lc_tts = build_lollms_client_from_params(username, load_llm=False, load_tts=True)
        if not lc_tts.tts: return target_tab['id']
        try:
            fname = f"audio_slide_{slide['id']}.wav"
            clean_text = _clean_text_for_tts(text_to_speak)
            audio_bytes = lc_tts.tts.generate_audio(clean_text, voice=voice_to_use, language=notebook_language)
            if audio_bytes:
                (assets_path / fname).write_bytes(audio_bytes)
                slide['audio_src'] = f"/api/notebooks/{notebook.id}/assets/{fname}"
        except Exception as e:
            trace_exception(e)
        target_tab['content'] = json.dumps(tab_data)
        return target_tab['id']
    
    # --- ACTION: GENERATE HTML GRAPHIC ---
    elif action == 'generate_slide_html':
        if not target_tab: return None
        match = re.match(r"SLIDE_INDEX:(\d+)\|\s*(.*)", prompt, re.DOTALL)
        if not match: return target_tab['id']
        slide_idx = int(match.group(1))
        user_instruction = match.group(2)
        if slide_idx >= len(tab_data['slides_data']): return target_tab['id']
        
        slide = tab_data['slides_data'][slide_idx]
        task.log(f"Generating HTML graphic for Slide {slide_idx+1}...")
        
        system_prompt = "You are an expert web developer specializing in data visualization. Create responsive, self-contained HTML5 widgets."
        user_prompt = f"""
        Context: Slide "{slide.get('title')}" containing "{', '.join(slide.get('bullets', []))}".
        User Request: {user_instruction}
        Task: Output valid HTML code block for a visualization widget.
        """
        code = lc.generate_text(user_prompt, system_prompt=system_prompt)
        code_match = re.search(r'```html(.*?)```', code, re.DOTALL)
        slide['html_content'] = code_match.group(1).strip() if code_match else code
        target_tab['content'] = json.dumps(tab_data)
        return target_tab['id']

    # --- ACTION: REGENERATE / REFINE IMAGE ---
    elif action in ['images', 'refine_image']:
        if not target_tab: return None
        match = re.match(r"SLIDE_INDEX:(\d+)\|(.*?)\|(.*)", prompt, re.DOTALL)
        if not match: return target_tab['id']
        
        idx = int(match.group(1))
        pos_prompt = match.group(2).strip()
        neg_prompt = match.group(3).strip()
        if idx >= len(tab_data['slides_data']): return target_tab['id']

        slide = tab_data['slides_data'][idx]
        task.log("Executing visual generation...")
        lc_tti = build_lollms_client_from_params(username, load_llm=False, load_tti=True)
        
        try:
            img_bytes = lc_tti.tti.generate_image(pos_prompt, negative_prompt=neg_prompt)
            if img_bytes:
                fname = f"v_{uuid.uuid4().hex[:8]}.png"
                (assets_path / fname).write_bytes(img_bytes)
                if 'images' not in slide: slide['images'] = []
                slide['images'].append({"path": f"/api/notebooks/{notebook.id}/assets/{fname}", "prompt": pos_prompt})
                slide['selected_image_index'] = len(slide['images']) - 1
                target_tab['content'] = json.dumps(tab_data)
        except Exception as e:
            task.log(f"Image generation error: {e}", "ERROR")
        return target_tab['id']

    return target_tab_id if target_tab else None

def generate_deck_summary_task(task: Task, username: str, notebook_id: str):
    task.log("Generating deck summary...")
    with task.db_session_factory() as db:
        notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
        if not notebook: return
        slides_tab = next((t for t in notebook.tabs if t['type'] == 'slides'), None)
        if not slides_tab: return
        data = json.loads(slides_tab['content'])
        lc = get_user_lollms_client(username)
        summary = lc.generate_text(f"Summarize this presentation structure: {slides_tab['content'][:2000]}")
        data['summary'] = summary
        slides_tab['content'] = json.dumps(data)
        flag_modified(notebook, "tabs")
        db.commit()
        return {"summary": summary}

def generate_presentation_video_task(task: Task, username: str, notebook_id: str):
    try:
        from moviepy import ImageClip, concatenate_videoclips, AudioFileClip
    except:
        import pipmaster as pm
        pm.install("moviepy==2.2.1")
        from moviepy import ImageClip, concatenate_videoclips, AudioFileClip

    assets_path = get_user_notebook_assets_path(username, notebook_id)
    output_path = assets_path / "presentation.mp4"
    
    with task.db_session_factory() as db:
        notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
        tab = next((t for t in notebook.tabs if t['type'] == 'slides'), None)
        data = json.loads(tab['content'])
        slides = data.get('slides_data', [])
        
    clips = []
    for i, slide in enumerate(slides):
        img_path = None
        if slide.get('images'):
            rel = slide['images'][slide.get('selected_image_index', 0)]['path'].split('/assets/')[-1]
            if (assets_path / rel).exists(): img_path = str(assets_path / rel)
        if img_path:
            clip = ImageClip(img_path).with_duration(5)
            clips.append(clip)
            
    if clips:
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(str(output_path), fps=24, codec='libx264')
        
    return {"file_path": str(output_path)}
