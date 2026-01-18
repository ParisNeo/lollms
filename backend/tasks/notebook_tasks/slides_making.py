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

    # --- ACTION: INITIAL PROCESS (The Grounded Pipeline) ---
    if action == 'initial_process':
        task.log("Phase 1: Knowledge Assessment...")
        task.set_progress(5)
        
        context_parts = []
        for art in (notebook.artefacts or []):
            if art.get('is_loaded') and art.get('content'):
                context_parts.append(f"--- Source: {art['filename']} ---\n{art['content']}")
        
        context_text = "\n\n".join(context_parts)
        
        knowledge_core = ""
        
        if context_text.strip():
            task.log("Processing long context from artefacts...")
            research_prompt = f"Extract all key facts, narratives, statistics, and logical steps relevant to producing a slide deck about: '{prompt}'."
            
            try:
                knowledge_core = lc.long_context_processing(
                    text_to_process=context_text,
                    contextual_prompt=research_prompt,
                    context_fill_percentage=0.7,
                    overlap_tokens=200,
                    max_generation_tokens=2048
                )
            except Exception as e:
                task.log(f"Error during context processing: {e}", "ERROR")
                knowledge_core = ""

            # Robust handling for Dict return (Error or Structured)
            if isinstance(knowledge_core, dict):
                if 'error' in knowledge_core:
                    task.log(f"LCP Error: {knowledge_core['error']}", "ERROR")
                    knowledge_core = ""
                else:
                    knowledge_core = knowledge_core.get('content', knowledge_core.get('text', ""))
            
            # Ensure it's a string
            if not isinstance(knowledge_core, str):
                knowledge_core = str(knowledge_core) if knowledge_core else ""
            
            if not knowledge_core.strip():
                task.log("Context extraction returned empty result.", "ERROR")
                tab_data['slides_data'] = [{
                    "id": str(uuid.uuid4()),
                    "title": "Extraction Failed",
                    "layout": "TitleImageBody",
                    "bullets": ["The AI could not extract meaningful information from the source documents.", "Please check if the context files are empty or unreadable."],
                    "notes": "System error during context processing."
                }]
                if target_tab: target_tab['content'] = json.dumps(tab_data)
                return target_tab['id'] if target_tab else None
                
            task.log(f"LCP extracted {len(knowledge_core)} chars of insight.", "INFO")
        else:
            if not prompt or prompt == "Create a detailed presentation structure based on the available research data.":
                task.log("No prompt and no data provided. Cannot build slide show.", "ERROR")
                tab_data['slides_data'] = [{
                    "id": str(uuid.uuid4()),
                    "title": "No Content Provided",
                    "layout": "TitleImageBody",
                    "bullets": ["Please provide a topic prompt or upload documents to generate slides."],
                    "notes": "No input detected."
                }]
                if target_tab: target_tab['content'] = json.dumps(tab_data)
                return target_tab['id'] if target_tab else None
            
            knowledge_core = "No external context provided. Rely on general AI knowledge based on the user prompt."
            task.log("No source text found in notebook artefacts. Using prompt-based general knowledge.", "WARNING")

        task.log("Phase 2: Structured Deck Design...")
        task.set_progress(30)

        # Retrieve Metadata Configurations
        pref_style = metadata.get('style_preset', 'Corporate Vector')
        pref_format = metadata.get('slide_format', 'TitleImageBody')
        num_slides = int(metadata.get('num_slides', 10))
        
        task.log(f"Config: {num_slides} slides, Format: {pref_format}, Style: {pref_style}")

        system_prompt = f"You are a master {pref_style} Presentation Designer."
        
        # Build strict rules based on format
        format_instructions = ""
        if pref_format == 'ImageOnly':
            format_instructions = "STRICT RULE: Every slide MUST have 'layout': 'ImageOnly'. Focus heavily on 'image_prompt' and 'notes'. 'bullets' should be empty. DISCLAIMER: Standard TTI tools (Stable Diffusion/DALL-E 3) struggle with generating legible text inside images. Focus prompts on visual symbolism, not text content."
        elif pref_format == 'TextOnly':
            format_instructions = "STRICT RULE: Every slide MUST have 'layout': 'TextOnly'. 'image_prompt' should be empty."
        elif pref_format == 'HTML_Graph':
            format_instructions = "STRICT RULE: Identify slides that require data visualization. For those slides, include a note in 'bullets' saying '[DATA VIZ REQUIRED]: <description>'."
        else:
            format_instructions = f"Preferred Layout: {pref_format}. You may vary layouts if necessary, but default to {pref_format}."

        design_prompt = f"""
        Based on this Knowledge Core:
        {knowledge_core}
        
        USER OBJECTIVE: {prompt}
        
        CONSTRAINTS:
        - Total Slides: {num_slides}
        - Visual Style: {pref_style}
        - {format_instructions}

        TASK: Generate a complete slide deck structure. 
        Each slide must include:
        1. A compelling Title.
        2. Content bullets (unless layout is ImageOnly).
        3. A highly detailed Visual Prompt ('image_prompt').
        4. A 'negative_image_prompt' (to suppress text, blur, deformation, or low quality).
        5. Detailed Speaker Notes (Notes must be the exact speech/script for the presenter).
        6. The Layout type (use: TitleImageBody, ImageOnly, TextOnly, TitleOnly).
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
                            "bullets": {"type": "array", "items": {"type": "string"}},
                            "image_prompt": {"type": "string", "description": "Detailed prompt for TTI generator"},
                            "negative_image_prompt": {"type": "string", "description": "What to exclude: text, letters, blurry, deformed"},
                            "notes": {"type": "string", "description": "Full speaker script"},
                            "layout": {"type": "string", "enum": ["TitleImageBody", "ImageOnly", "TextOnly", "TitleOnly"]}
                        },
                        "required": ["title", "bullets", "image_prompt", "negative_image_prompt", "notes", "layout"]
                    }
                }
            },
            "required": ["slides"]
        }

        generated_slides = []
        try:
            design_output = lc.generate_structured_content(design_prompt, schema=schema, system_prompt=system_prompt)
            if design_output and isinstance(design_output, dict):
                generated_slides = design_output.get("slides", [])
        except Exception as e:
            task.log(f"Structured generation error: {e}", "WARNING")

        if not generated_slides:
            task.log("Structured generation yielded no slides. Attempting fallback method...", "WARNING")
            fallback_prompt = f"{design_prompt}\n\nIMPORTANT: Return valid JSON only. Structure: {{ \"slides\": [ ... ] }}. Do not output markdown code blocks."
            try:
                raw_json = lc.generate_text(fallback_prompt, system_prompt=system_prompt)
                fallback_data = _extract_json(raw_json, task)
                if fallback_data:
                    if isinstance(fallback_data, dict):
                        generated_slides = fallback_data.get("slides", [])
                    elif isinstance(fallback_data, list):
                        generated_slides = fallback_data
            except Exception as e:
                task.log(f"Fallback generation logic failed: {e}", "ERROR")

        if not generated_slides:
            task.log("Critical failure in slide generation. Creating error slide.", "ERROR")
            generated_slides = [{
                "title": "Generation Failed",
                "bullets": ["Could not generate structure from the LLM.", "Please check the logs for errors."],
                "image_prompt": "Abstract error visual",
                "negative_image_prompt": "text, letters, blurry",
                "notes": "I apologize, but I encountered an issue generating the deck.",
                "layout": "TitleImageBody"
            }]

        if notebook.title == "New Production" and generated_slides and len(generated_slides) > 0:
            first_title = generated_slides[0].get('title', 'Untitled')
            if isinstance(first_title, str):
                clean_title = first_title.split(':')[0].strip()
                if clean_title and len(clean_title) < 50:
                    task.log(f"Updating generic notebook title to: {clean_title}")
                    notebook.title = clean_title

        task.log(f"Phase 3: Visual Production ({len(generated_slides)} visuals)...")
        task.set_progress(50)

        lc_tti = build_lollms_client_from_params(username, load_llm=False, load_tti=True)
        final_slides_data = []
        
        step_inc = 50 / max(1, len(generated_slides))
        
        for i, s in enumerate(generated_slides):
            task.log(f"Processing slide {i+1}: {s.get('title', 'Untitled')}")
            
            html_content = ""
            if pref_format == 'HTML_Graph' and any("DATA VIZ REQUIRED" in b for b in s.get('bullets', [])):
                try:
                    viz_prompt = f"Create an HTML5 widget to visualize: {s.get('title')}. {', '.join(s.get('bullets', []))}"
                    html_sys = "You are a data visualization expert. Output ONLY valid HTML code for a responsive widget."
                    html_out = lc.generate_text(viz_prompt, system_prompt=html_sys)
                    code_match = re.search(r'```html(.*?)```', html_out, re.DOTALL)
                    html_content = code_match.group(1).strip() if code_match else html_out
                    task.log("Generated HTML data viz.")
                except Exception: pass

            img_list = []
            if lc_tti.tti and s.get('layout') != 'TextOnly':
                try:
                    visual_p = f"{s.get('image_prompt', '')}, {pref_style} style, high quality presentation visual."
                    neg_p = s.get('negative_image_prompt', "text, letters, words, watermark, blurry, deformed")
                    img_bytes = lc_tti.tti.generate_image(prompt=visual_p, negative_prompt=neg_p, width=1280, height=720)
                    if img_bytes:
                        fname = f"auto_v_{uuid.uuid4().hex[:8]}.png"
                        (assets_path / fname).write_bytes(img_bytes)
                        img_list.append({
                            "path": f"/api/notebooks/{notebook.id}/assets/{fname}",
                            "prompt": visual_p,
                            "negative_prompt": neg_p,
                            "created_at": str(base64.b64encode(fname.encode()))
                        })
                except Exception as e:
                    task.log(f"Visual failed for slide {i+1}: {str(e)}", "WARNING")

            final_slides_data.append({
                "id": str(uuid.uuid4()),
                "title": s.get('title', 'Untitled'),
                "layout": s.get('layout', 'TitleImageBody'),
                "bullets": s.get('bullets', []),
                "image_prompt": s.get('image_prompt', ''),
                "negative_image_prompt": s.get('negative_image_prompt', ''),
                "images": img_list,
                "selected_image_index": 0,
                "notes": s.get('notes', ''),
                "html_content": html_content,
                "messages": []
            })
            task.set_progress(50 + (i * step_inc))

        tab_data['slides_data'] = final_slides_data
        tab_data['summary'] = f"Grounded {pref_style} deck generated from sources."

        if target_tab:
            target_tab['content'] = json.dumps(tab_data)
        else:
            notebook.tabs.append({
                "id": str(uuid.uuid4()), "title": "AI Presentation", "type": "slides",
                "content": json.dumps(tab_data), "images": []
            })
            
        return target_tab['id'] if target_tab else notebook.tabs[-1]['id']

    # --- ACTION: ADD FULL SLIDE ---
    elif action == 'add_full_slide':
        try:
            slide_config = _extract_json(prompt, task) or {}
            task.log("Generating visual for new slide...")
            deck_summary = tab_data.get('summary', '')
            
            knowledge_summary = ""
            if selected_artefacts:
                knowledge_summary = _extract_knowledge_from_artefacts(task, lc, notebook, selected_artefacts, slide_config.get('topic', 'New Slide'), deck_summary)

            lc_tti = build_lollms_client_from_params(username, load_llm=False, load_tti=True)
            img_list = []
            
            if slide_config.get('image_prompt') and lc_tti.tti:
                style = metadata.get('style_preset', '')
                final_p = slide_config['image_prompt']
                neg_p = slide_config.get('negative_image_prompt', "text, letters, words, blurry, watermark")

                if knowledge_summary:
                    prompt_enhancement = f"Refine this image prompt: '{final_p}'. Incorporate visual details from this context: {knowledge_summary}. Ensure the style '{style}' is respected."
                    final_p = lc.generate_text(prompt_enhancement, max_new_tokens=150).strip()
                else:
                    final_p = f"{final_p}, {style}".strip()

                try:
                    img_bytes = lc_tti.tti.generate_image(prompt=final_p, negative_prompt=neg_p, width=1280, height=720)
                    if img_bytes:
                        fname = f"slide_{uuid.uuid4().hex[:8]}.png"
                        full_path = assets_path / fname
                        full_path.write_bytes(img_bytes)
                        img_list.append({
                            "path": f"/api/notebooks/{notebook.id}/assets/{fname}",
                            "prompt": final_p,
                            "negative_prompt": neg_p,
                            "created_at": str(full_path.stat().st_mtime)
                        })
                except Exception as e:
                    task.log(f"Image generation failed: {e}", "WARNING")

            new_slide = {
                "id": str(uuid.uuid4()),
                "title": slide_config.get('title', 'Untitled'),
                "layout": slide_config.get('layout', 'TitleImageBody'),
                "bullets": slide_config.get('bullets', []),
                "image_prompt": slide_config.get('image_prompt', ''),
                "negative_image_prompt": slide_config.get('negative_image_prompt', ''),
                "images": img_list,
                "selected_image_index": 0,
                "messages": [],
                "notes": slide_config.get('notes', '')
            }
            
            tab_data['slides_data'].append(new_slide)
            if target_tab:
                target_tab['content'] = json.dumps(tab_data)
                return target_tab['id']
            
        except Exception as e:
            task.log(f"Add slide failed: {e}", "ERROR")
            trace_exception(e)

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
        task.log(f"Generating audio for slide in {notebook_language}...")
        match = re.match(r"SLIDE_INDEX:(\d+)", prompt)
        if not match: return target_tab['id']
        slide_idx = int(match.group(1))
        slide = tab_data['slides_data'][slide_idx]
        text_to_speak = slide.get('notes', f"{slide.get('title', '')}. {'. '.join(slide.get('bullets', []))}")
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
            fname = f"audio_slide_{slide['id']}_{uuid.uuid4().hex[:6]}.wav"
            full_path = assets_path / fname
            
            clean_text = _clean_text_for_tts(text_to_speak)
            
            if hasattr(lc_tts.tts, 'generate_audio'):
                audio_bytes = lc_tts.tts.generate_audio(clean_text, voice=voice_to_use, language=notebook_language)
                if audio_bytes: (assets_path / fname).write_bytes(audio_bytes)
            elif hasattr(lc_tts.tts, 'tts_to_file'):
                lc_tts.tts.tts_to_file(clean_text, str(full_path))
                
            if full_path.exists() and full_path.stat().st_size > 0:
                slide['audio_src'] = f"/api/notebooks/{notebook.id}/assets/{fname}"
        except Exception as e:
            trace_exception(e)
        target_tab['content'] = json.dumps(tab_data)
        return target_tab['id']
    
    # --- ACTION: GENERATE HTML GRAPHIC ---
    elif action == 'generate_slide_html':
        if not target_tab: return None
        match = re.match(r"SLIDE_INDEX:(\d+)\|\s*(.*)", prompt, re.DOTALL)
        if not match: return
        slide_idx = int(match.group(1))
        user_instruction = match.group(2)
        if slide_idx >= len(tab_data['slides_data']): return
        
        slide = tab_data['slides_data'][slide_idx]
        task.log(f"Generating HTML graphic for Slide {slide_idx+1}...")
        context = f"Slide Title: {slide.get('title')}\nContent: {', '.join(slide.get('bullets', []))}"
        
        system_prompt = "You are an expert web developer specializing in data visualization. Create self-contained HTML5 widgets."
        user_prompt = f"""
        Context: {context}
        User Request: {user_instruction}
        Task: Create a self-contained HTML file (with CSS/JS embedded) to visualize this. Output ONLY the HTML code block within ```html tags.
        """
        code = lc.generate_text(user_prompt, system_prompt=system_prompt)
        code_match = re.search(r'```html(.*?)```', code, re.DOTALL)
        final_code = code_match.group(1).strip() if code_match else code
        slide['html_content'] = final_code
        target_tab['content'] = json.dumps(tab_data)
        return target_tab['id']

    # --- ACTION: REGENERATE / REFINE ---
    elif action in ['images', 'refine_image']:
        if not target_tab: return None
        # Parsing: SLIDE_INDEX:idx|positive|negative
        match = re.match(r"SLIDE_INDEX:(\d+)\|(.*?)\|(.*)", prompt, re.DOTALL)
        if not match:
            # Fallback for simple prompts
            match = re.match(r"SLIDE_INDEX:(\d+)\|\s*(.*)", prompt, re.DOTALL)
            if not match: return target_tab['id']
            slide_idx = int(match.group(1))
            pos_prompt = match.group(2).strip()
            neg_prompt = "text, letters, words, blurry, deformed, low quality, watermark"
        else:
            slide_idx = int(match.group(1))
            pos_prompt = match.group(2).strip()
            neg_prompt = match.group(3).strip()

        if slide_idx >= len(tab_data['slides_data']): return target_tab['id']

        slide = tab_data['slides_data'][slide_idx]
        deck_summary = tab_data.get('summary', '')
        mini_discussion = "\n".join([f"{m['role']}: {m['content']}" for m in slide.get('messages', [])])
        
        research_data = ""
        if selected_artefacts:
            research_data = _extract_knowledge_from_artefacts(task, lc, notebook, selected_artefacts, slide.get('title', pos_prompt), deck_summary, mini_discussion)
        
        lc_tti = build_lollms_client_from_params(username, load_llm=False, load_tti=True)
        source_img_b64 = None
        
        if action == 'refine_image':
            idx = slide.get('selected_image_index', 0)
            if slide.get('images') and len(slide['images']) > idx:
                image_info = slide['images'][idx]
                path_part = image_info['path'].split('/assets/')[-1]
                local_path = assets_path / path_part
                if local_path.exists():
                    source_img_b64 = base64.b64encode(local_path.read_bytes()).decode('utf-8')

        task.log("Executing visual generation...")
        style = metadata.get('style_preset', 'Corporate Vector')
        final_p = pos_prompt
        
        if research_data:
            fusion_prompt = f"Combine user instruction '{pos_prompt}' with extracted facts: {research_data}. Create a detailed visual prompt for AI generation."
            final_p = lc.generate_text(fusion_prompt, max_new_tokens=256).strip()

        if style and style not in final_p:
            final_p = f"{final_p}, {style}".strip()
        
        try:
            img_bytes = None
            if action == 'refine_image' and source_img_b64:
                if hasattr(lc_tti.tti, 'edit_image'):
                    img_bytes = lc_tti.tti.edit_image(images=source_img_b64, prompt=final_p, negative_prompt=neg_p, width=1280, height=720)
                else:
                    img_bytes = lc_tti.tti.generate_image(prompt=final_p, negative_prompt=neg_p, image=source_img_b64, width=1280, height=720)
            else:
                img_bytes = lc_tti.tti.generate_image(final_p, negative_prompt=neg_p, width=1280, height=720)
                
            if img_bytes:
                fname = f"v_{uuid.uuid4().hex[:8]}.png"
                full_path = assets_path / fname
                full_path.write_bytes(img_bytes)
                
                if 'images' not in slide: slide['images'] = []
                slide['images'].append({
                    "path": f"/api/notebooks/{notebook.id}/assets/{fname}",
                    "prompt": final_p,
                    "negative_prompt": neg_p,
                    "created_at": str(full_path.stat().st_mtime)
                })
                slide['selected_image_index'] = len(slide['images']) - 1
                target_tab['content'] = json.dumps(tab_data)
        except Exception as e:
            task.log(f"Image generation error: {e}", "ERROR")
            trace_exception(e)
        
        return target_tab['id']

    return target_tab_id if target_tab else None

def generate_deck_summary_task(task: Task, username: str, notebook_id: str):
    task.log("Loading notebook...")
    with task.db_session_factory() as db:
        notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
        if not notebook: raise ValueError("Notebook not found")
        target_tab = next((t for t in notebook.tabs if t['type'] == 'slides'), None)
        if not target_tab:
            task.log("No slides tab found.", "ERROR")
            return
        try:
            tab_data = json.loads(target_tab['content'])
        except:
            task.log("Failed to parse slide data.", "ERROR")
            return
        slides_data = tab_data.get('slides_data', [])
        if not slides_data:
            task.log("No slides to summarize.", "WARNING")
            return
        lc = get_user_lollms_client(username)
        context_str = ""
        for i, s in enumerate(slides_data):
            context_str += f"\nSlide {i+1}: {s.get('title', 'Untitled')}\n"
            if s.get('bullets'): context_str += "Points: " + "; ".join(s.get('bullets')) + "\n"
        task.log("Generating summary...", "INFO")
        prompt = f"Summarize the presentation structure and content.\n\nContent:\n{context_str}"
        summary = lc.generate_text(prompt)
        tab_data['summary'] = summary
        target_tab['content'] = json.dumps(tab_data)
        flag_modified(notebook, "tabs")
        db.commit()
        task.log("Summary updated.", "SUCCESS")
        task.set_progress(100)
        return {"summary": summary}

def generate_presentation_video_task(task: Task, username: str, notebook_id: str):
    try:
        from moviepy import ImageClip, concatenate_videoclips, AudioFileClip
    except (ImportError, ModuleNotFoundError) as e:
        task.log(f"Failed to load moviepy. Installing...", "ERROR")
        import pipmaster as pm
        pm.install("moviepy==2.2.1")
        from moviepy import ImageClip, concatenate_videoclips, AudioFileClip

    assets_path = get_user_notebook_assets_path(username, notebook_id)
    output_path = assets_path / "presentation.mp4"
    temp_dir = Path(tempfile.mkdtemp())
    
    lc_tts = build_lollms_client_from_params(username, load_llm=False, load_tts=True)
    if not lc_tts.tts:
        task.log("TTS Binding not configured.", "ERROR")
        raise ValueError("TTS not available")

    voice_to_use = None
    language_to_use = 'en'
    
    with task.db_session_factory() as db:
        notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
        if not notebook: raise ValueError("Notebook not found")
        slides_tab = next((t for t in notebook.tabs if t['type'] == 'slides'), None)
        if not slides_tab: raise ValueError("No slides tab")
        try: tab_data = json.loads(slides_tab['content'])
        except: tab_data = {}
        slides_data = tab_data.get('slides_data', [])
        db_user = db.query(DBUser).filter(DBUser.username == username).first()
        if db_user:
             if db_user.active_voice_id:
                active_voice = db.query(DBUserVoice).filter(DBUserVoice.id == db_user.active_voice_id).first()
                if active_voice:
                    v_path = get_user_data_root(username) / "voices" / active_voice.file_path
                    if v_path.exists(): voice_to_use = str(v_path.resolve())
             if db_user.ai_response_language and db_user.ai_response_language.lower() != "auto":
                language_to_use = db_user.ai_response_language

    if not slides_data: return

    clips = []
    task.set_progress(10)
    total = len(slides_data)
    
    for i, slide in enumerate(slides_data):
        task.log(f"Processing slide {i+1}...")
        img_path = None
        if slide.get('images'):
            idx = slide.get('selected_image_index', 0)
            if idx < len(slide['images']):
                rel_path = slide['images'][idx]['path'].split('/assets/')[-1]
                full_img_path = assets_path / rel_path
                if full_img_path.exists(): img_path = str(full_img_path)
        
        if not img_path: continue
        text = slide.get('notes') or f"{slide.get('title', '')}. {'. '.join(slide.get('bullets', []))}"
        
        try:
            audio_file = temp_dir / f"slide_{i}.wav"
            clean_text = _clean_text_for_tts(text)
            
            if hasattr(lc_tts.tts, 'generate_audio'):
                audio_bytes = lc_tts.tts.generate_audio(clean_text, voice=voice_to_use, language=language_to_use)
                if audio_bytes: 
                    with open(audio_file, "wb") as f: f.write(audio_bytes)

            if not audio_file.exists() or audio_file.stat().st_size == 0:
                clip = ImageClip(img_path).with_duration(5)
            else:
                audio_clip = AudioFileClip(str(audio_file))
                clip = ImageClip(img_path).with_duration(audio_clip.duration).with_audio(audio_clip)
            
            clips.append(clip)
        except Exception as e:
            task.log(f"Error slide {i+1}: {e}", "ERROR")
        
        task.set_progress(10 + int((i+1)/total * 80))

    if clips:
        task.log("Concatenating...")
        final_video = concatenate_videoclips(clips, method="compose")
        final_video.write_videofile(str(output_path), fps=24, codec='libx264', audio_codec='aac')
        
        task.log("Video complete.")
        task.set_progress(100)
        
        try:
            for f in temp_dir.glob("*"): f.unlink()
            temp_dir.rmdir()
        except: pass
        
        with task.db_session_factory() as db:
            notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
            if notebook:
                slides_tab = next((t for t in notebook.tabs if t['type'] == 'slides'), None)
                if slides_tab:
                    tab_data = json.loads(slides_tab['content'])
                    tab_data['video_src'] = f"/api/notebooks/{notebook_id}/assets/presentation.mp4"
                    slides_tab['content'] = json.dumps(tab_data)
                    flag_modified(notebook, "tabs")
                    db.commit()

        return {"file_path": f"/api/notebooks/{notebook_id}/assets/presentation.mp4"}
    return None
