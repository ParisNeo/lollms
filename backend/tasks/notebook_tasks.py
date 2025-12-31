import uuid
import json
import traceback
import base64
import os
from datetime import datetime
from typing import List, Optional, Any
from sqlalchemy.orm.attributes import flag_modified

from backend.db.models.notebook import Notebook as DBNotebook
from backend.session import get_user_lollms_client, build_lollms_client_from_params, get_user_notebook_assets_path
from backend.task_manager import Task
from ascii_colors import trace_exception

def _process_notebook_task(task: Task, username: str, notebook_id: str, prompt: str, input_tab_ids: List[str], action: str, target_tab_id: Optional[str] = None):
    task.log(f"Starting notebook processing: {action}")
    task.set_progress(5)
    
    try:
        with task.db_session_factory() as db:
            notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
            if not notebook:
                raise Exception("Notebook not found.")
            
            # Find Target Tab
            target_tab = None
            if target_tab_id:
                for t in notebook.tabs:
                    if t['id'] == target_tab_id:
                        target_tab = t
                        break
            
            if not target_tab and action != 'generate_slides_text':
                 # If no target and not generating new, try finding first slide tab or markdown
                 if notebook.tabs: target_tab = notebook.tabs[0]

            # Load Metadata
            nb_metadata = {}
            try:
                loaded_content = json.loads(notebook.content)
                if isinstance(loaded_content, dict) and 'metadata' in loaded_content:
                    nb_metadata = loaded_content['metadata']
            except: pass
            
            slide_format = nb_metadata.get('format', { "width": 1920, "height": 1080 })
            global_style_prompt = nb_metadata.get('style_prompt', "")
            slide_mode = nb_metadata.get('slide_mode', 'image_only')

            # 1. Gather Context (Sources) into text_to_process
            text_to_process = ""
            for tab in notebook.tabs:
                if tab['id'] in input_tab_ids:
                    text_to_process += f"\n\n--- Source: {tab['title']} ---\n{tab.get('content', '')}\n"
            
            for art in notebook.artefacts:
                if art.get('is_loaded') and art.get('content'):
                    text_to_process += f"\n\n--- File: {art['filename']} ---\n{art['content']}\n"

            # 2. Build Scratchpad (Presentation Overview) if editing
            scratchpad = ""
            if target_tab and target_tab.get('type') == 'slides':
                try:
                    current_content = json.loads(target_tab['content'])
                    slides = current_content.get('slides_data', [])
                    scratchpad = "## Current Presentation Structure:\n"
                    for i, s in enumerate(slides):
                        scratchpad += f"Slide {i+1}: {s.get('title', 'Untitled')} (Layout: {s.get('layout')})\n"
                except:
                    scratchpad = "Presentation structure unavailable."

            task.set_progress(20)
            lc = get_user_lollms_client(username)
            
            system_prompt = "You are a helpful AI assistant."
            contextual_prompt = ""
            is_slide_generation = False
            
            # --- ACTION HANDLING ---
            
            if action == 'generate_slides_text':
                is_slide_generation = True
                
                # Strict Structure Enforcement
                structure_instruction = (
                    "STRUCTURE REQUIREMENTS:\n"
                    "1. **Slide 1 MUST be a Title Slide** (Title of presentation, Subtitle).\n"
                    "2. Subsequent slides should cover the topic in a logical narrative flow.\n"
                    "3. **The Final Slide MUST be a Conclusion or Thank You slide**.\n"
                )

                if slide_mode == 'image_only':
                    system_prompt = "You are an AI Art Director creating a full-visual presentation."
                    contextual_prompt = (
                        f"{structure_instruction}\n"
                        "Generate a JSON list of detailed image prompts for each slide. "
                        "The image prompt MUST describe the textual content to appear in the image itself (e.g. 'A futuristic billboard displaying the text \"Welcome\"', or 'A diagram of X with labels'). "
                        "Since this is an image-only presentation, do NOT provide separate bullet points. The text must be integrated into the visual description.\n"
                        "Format: `[ { \"title\": \"Slide Title\", \"image_prompt\": \"...\" }, ... ]`"
                    )
                elif slide_mode == 'hybrid':
                    system_prompt = "You are a Presentation Designer."
                    contextual_prompt = (
                        f"{structure_instruction}\n"
                        "Generate a structured JSON for a slide deck. "
                        "Layouts: 'TitleBody', 'TitleImageBody'. "
                        "Format: `[ { \"layout\": \"TitleImageBody\", \"title\": \"...\", \"bullets\": [\"...\"], \"image_prompt\": \"...\" } ]`"
                    )
                else: 
                    system_prompt = "You are a Presentation Copywriter."
                    contextual_prompt = (
                        f"{structure_instruction}\n"
                        "Generate JSON: `[ { \"title\": \"...\", \"bullets\": [\"...\"] } ]`"
                    )

                if global_style_prompt:
                    contextual_prompt += f"\n\nVISUAL STYLE: {global_style_prompt}"
                
                contextual_prompt += f"\n\n[INSTRUCTION]\n{prompt}"

            elif action == 'update_slide_text' and target_tab:
                # Handle specific slide update
                try:
                    parts = prompt.split('|', 1)
                    slide_idx = int(parts[0].split(':')[1])
                    instruction = parts[1].strip()
                    
                    current_content = json.loads(target_tab['content'])
                    target_slide = current_content['slides_data'][slide_idx]
                    
                    system_prompt = "You are a Presentation Editor."
                    contextual_prompt = (
                        f"Here is a summary of the slide deck for context:\n{scratchpad}\n\n"
                        f"CURRENT SLIDE JSON:\n{json.dumps(target_slide)}\n\n"
                        f"Update the content of this specific slide JSON based on the instruction below. "
                        f"Return ONLY the updated JSON object for this single slide.\n"
                        f"[INSTRUCTION]\n{instruction}"
                    )
                except Exception as e:
                    raise ValueError(f"Invalid update instruction format: {e}")

            elif action == 'images' and target_tab:
                system_prompt = "You are an AI Art Director."
                
                # Check for SLIDE_INDEX in prompt to get context
                slide_content_context = ""
                slide_instruction = prompt
                
                if "SLIDE_INDEX:" in prompt:
                    try:
                        parts = prompt.split('|', 1)
                        slide_idx = int(parts[0].split(':')[1])
                        slide_instruction = parts[1].strip()
                        
                        current_content = json.loads(target_tab['content'])
                        if 0 <= slide_idx < len(current_content.get('slides_data', [])):
                            target_slide = current_content['slides_data'][slide_idx]
                            slide_content_context = (
                                f"SLIDE TITLE: {target_slide.get('title', '')}\n"
                                f"SLIDE TEXT: {json.dumps(target_slide.get('bullets', []))}\n"
                            )
                    except: pass

                contextual_prompt = (
                    f"Here is the context of the presentation:\n{scratchpad}\n\n"
                    f"{slide_content_context}"
                    f"Based on the request, generate a highly detailed image prompt suitable for a text-to-image model. "
                    f"The prompt should describe a visual that complements the slide content."
                    f"\nVISUAL STYLE: {global_style_prompt}\n"
                    f"Return ONLY a JSON list containing 1 image prompt string.\n"
                    f"[INSTRUCTION]\n{slide_instruction}"
                )

            else:
                contextual_prompt = f"{prompt}\n\nAnswer in Markdown."
            
            def stream_cb(chunk, msg_type=None, **kwargs):
                if task.cancellation_event.is_set(): return False
                return True

            task.log("Sending request to AI (Long Context Processing)...")
            
            # Use long_context_processing
            response_text = lc.long_context_processing(
                text_to_process=text_to_process,
                contextual_prompt=contextual_prompt,
                system_prompt=system_prompt,
                streaming_callback=stream_cb
            )
            
            task.set_progress(60)

            # 5. Handle Results
            result_data = None
            
            if is_slide_generation:
                import re
                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                
                if json_match:
                    try:
                        slides_struct = json.loads(json_match.group(0))
                        enhanced_slides = []
                        lc_tti = None
                        
                        needs_tti = (slide_mode == 'image_only') or (slide_mode == 'hybrid')
                        if needs_tti:
                            lc_tti = build_lollms_client_from_params(username, load_llm=False, load_tti=True)
                        
                        assets_path = get_user_notebook_assets_path(username, notebook_id)
                        assets_path.mkdir(parents=True, exist_ok=True)
                        
                        width = int(slide_format.get('width', 1920))
                        height = int(slide_format.get('height', 1080))

                        total = len(slides_struct)
                        for i, slide in enumerate(slides_struct):
                            if task.cancellation_event.is_set(): break
                            
                            img_list = []
                            should_gen = (slide_mode == 'image_only') or (slide_mode == 'hybrid' and slide.get('image_prompt') and 'Image' in slide.get('layout', ''))
                            
                            if should_gen and lc_tti and lc_tti.tti:
                                img_p = slide.get('image_prompt', '')
                                if img_p:
                                    final_p = f"{img_p}, {global_style_prompt}".strip()
                                    task.log(f"Generating visual {i+1}/{total}...")
                                    try:
                                        img_bytes = lc_tti.tti.generate_image(final_p, width=width, height=height)
                                        if img_bytes:
                                            img_filename = f"slide_{uuid.uuid4().hex[:8]}.png"
                                            with open(assets_path / img_filename, 'wb') as f:
                                                f.write(img_bytes)
                                            # Use relative API path
                                            img_url = f"/api/notebooks/{notebook_id}/assets/{img_filename}"
                                            img_list.append({ "path": img_url, "prompt": final_p })
                                    except Exception as ex:
                                        task.log(f"Image gen failed: {ex}", "ERROR")

                            enhanced_slides.append({
                                "id": str(uuid.uuid4()),
                                "layout": slide.get('layout', 'TitleBody'),
                                "title": slide.get('title', 'Untitled'),
                                "bullets": slide.get('bullets', []),
                                "images": img_list,
                                "selected_image_index": 0,
                                "image_prompt": slide.get('image_prompt', '')
                            })
                            task.set_progress(60 + int((i+1)/total*35))

                        result_data = {
                            "type": "slides",
                            "mode": slide_mode,
                            "slides_data": enhanced_slides,
                            "format": slide_format
                        }
                    except Exception as e:
                        task.log(f"JSON Error: {e}", "ERROR")
                        result_data = response_text
                else:
                    result_data = response_text

            elif action == 'update_slide_text' and target_tab:
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    updated_slide = json.loads(json_match.group(0))
                    # Merge update
                    current_content = json.loads(target_tab['content'])
                    # Ensure ID and images are preserved if AI missed them
                    original_slide = current_content['slides_data'][slide_idx]
                    
                    if 'images' not in updated_slide: updated_slide['images'] = original_slide.get('images', [])
                    if 'id' not in updated_slide: updated_slide['id'] = original_slide.get('id', str(uuid.uuid4()))
                    
                    current_content['slides_data'][slide_idx] = updated_slide
                    target_tab['content'] = json.dumps(current_content)
                    flag_modified(notebook, "tabs")
                    result_data = {"status": "updated", "slide_index": slide_idx}
                else:
                    task.log("Failed to parse AI response for slide update.", "ERROR")

            elif action == 'images' and target_tab:
                # Regenerate image
                lc_tti = build_lollms_client_from_params(username, load_llm=False, load_tti=True)
                if lc_tti.tti:
                    width = int(slide_format.get('width', 1024))
                    height = int(slide_format.get('height', 768))
                    try:
                        # Parse regex from LLM response if it returned JSON
                        import re
                        image_prompt = response_text.strip() # Default to raw text if no JSON found
                        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                        if json_match:
                            try:
                                prompt_list = json.loads(json_match.group(0))
                                if prompt_list and len(prompt_list) > 0:
                                    image_prompt = prompt_list[0]
                            except: pass
                        
                        # Clean up prompt if it captured the instruction by mistake (unlikely with improved prompt)
                        
                        final_prompt = f"{image_prompt}, {global_style_prompt}".strip()
                        img_bytes = lc_tti.tti.generate_image(final_prompt, width=width, height=height)
                        if img_bytes:
                            assets_path = get_user_notebook_assets_path(username, notebook_id)
                            img_filename = f"regen_{uuid.uuid4().hex[:8]}.png"
                            with open(assets_path / img_filename, 'wb') as f:
                                f.write(img_bytes)
                            img_url = f"/api/notebooks/{notebook_id}/assets/{img_filename}"
                            result_data = {
                                "new_image": { "path": img_url, "prompt": final_prompt }
                            }
                    except Exception as e:
                        task.log(f"Regen failed: {e}", "ERROR")

            # 6. Update Notebook (General cases)
            if target_tab and action != 'update_slide_text': # Update slide text already handled the tab modification
                if action == 'images' and result_data and 'new_image' in result_data:
                    # Update specific slide if prompted
                    if "SLIDE_INDEX:" in prompt:
                        try:
                            parts = prompt.split('|', 1)
                            idx = int(parts[0].split(':')[1])
                            tab_content = json.loads(target_tab['content'])
                            if 0 <= idx < len(tab_content['slides_data']):
                                tab_content['slides_data'][idx]['images'].append(result_data['new_image'])
                                tab_content['slides_data'][idx]['selected_image_index'] = len(tab_content['slides_data'][idx]['images']) - 1
                                target_tab['content'] = json.dumps(tab_content)
                                flag_modified(notebook, "tabs")
                        except: pass
                elif isinstance(result_data, dict) and 'type' in result_data:
                     target_tab['content'] = json.dumps(result_data)
                     target_tab['type'] = 'slides'
                     flag_modified(notebook, "tabs")
                elif not isinstance(result_data, dict):
                     target_tab['content'] = result_data if result_data else response_text
                     flag_modified(notebook, "tabs")
            elif not target_tab:
                new_tab_title = f"Result: {action}"
                content_str = json.dumps(result_data) if isinstance(result_data, dict) else (result_data or response_text)
                new_tab = {
                    "id": str(uuid.uuid4()),
                    "title": new_tab_title,
                    "type": "slides" if is_slide_generation else "markdown",
                    "content": content_str,
                    "images": []
                }
                current_tabs = list(notebook.tabs)
                current_tabs.append(new_tab)
                notebook.tabs = current_tabs
                flag_modified(notebook, "tabs")
                target_tab_id = new_tab['id']

            db.commit()
            task.set_progress(100)
            return {
                "notebook_id": notebook_id,
                "new_tab_id": target_tab_id,
                "status": "success"
            }

    except Exception as e:
        task.log(f"Processing failed: {e}", "ERROR")
        trace_exception(e)
        raise e

# ... (rest of file remains unchanged)
def _ingest_notebook_sources_task(task: Task, username: str, notebook_id: str, urls: List[str], youtube_urls: List[str]):
    task.log("Starting source ingestion...")
    task.set_progress(5)
    total_ops = len(urls) + len(youtube_urls)
    current_op = 0

    with task.db_session_factory() as db:
        notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
        if not notebook: return

        # Web URLs
        if urls:
            try:
                import pipmaster as pm
                if not pm.is_installed("scrapemaster"): pm.install("ScrapeMaster")
                from scrapemaster import ScrapeMaster
                for url in urls:
                    if task.cancellation_event.is_set(): break
                    task.log(f"Scraping: {url}")
                    try:
                        scraper = ScrapeMaster(url)
                        content = scraper.scrape_markdown()
                        if content:
                            _add_artefact(notebook, f"Web: {url}", content)
                            flag_modified(notebook, "artefacts")
                            db.commit()
                    except Exception as e: task.log(f"Failed {url}: {e}", "WARNING")
                    current_op += 1
                    task.set_progress(int(current_op / total_ops * 100))
            except Exception as e: task.log(f"Scrape error: {e}", "ERROR")

        # YouTube
        if youtube_urls:
            try:
                import pipmaster as pm
                if not pm.is_installed("youtube_transcript_api"): pm.install("youtube-transcript-api")
                from youtube_transcript_api import YouTubeTranscriptApi
                for yt in youtube_urls:
                    if task.cancellation_event.is_set(): break
                    task.log(f"Transcript: {yt}")
                    try:
                        vid = None
                        if "v=" in yt: vid = yt.split("v=")[1].split("&")[0]
                        elif "youtu.be/" in yt: vid = yt.split("youtu.be/")[1]
                        if vid:
                            ts = YouTubeTranscriptApi.get_transcript(vid)
                            txt = " ".join([t['text'] for t in ts])
                            _add_artefact(notebook, f"YouTube: {yt}", txt)
                            flag_modified(notebook, "artefacts")
                            db.commit()
                    except Exception as e: task.log(f"Failed {yt}: {e}", "WARNING")
                    current_op += 1
                    task.set_progress(int(current_op / total_ops * 100))
            except Exception as e: task.log(f"YouTube error: {e}", "ERROR")
            
    task.set_progress(100)

def _convert_file_with_docling_task(task: Task, username: str, notebook_id: str, file_path: str, original_filename: str):
    task.log(f"Converting {original_filename}...")
    try:
        import pipmaster as pm
        if not pm.is_installed("docling"): pm.install("docling")
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result = converter.convert(file_path)
        md = result.document.export_to_markdown()
        with task.db_session_factory() as db:
            notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
            if notebook:
                _add_artefact(notebook, f"Doc: {original_filename}", md)
                flag_modified(notebook, "artefacts")
                db.commit()
        task.set_progress(100)
    except Exception as e:
        task.log(f"Docling error: {e}", "ERROR")

def _add_artefact(notebook, title, content):
    current = list(notebook.artefacts)
    current.append({ "filename": title, "content": content, "type": "text", "is_loaded": True })
    notebook.artefacts = current
