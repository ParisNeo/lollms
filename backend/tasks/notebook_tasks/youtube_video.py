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
from typing import List, Dict, Any, Union
from .common import gather_context, get_notebook_metadata
from sqlalchemy.orm.attributes import flag_modified

def _try_parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        text_clean = re.sub(r',\s*([\]}])', r'\1', text)
        try:
            return json.loads(text_clean)
        except json.JSONDecodeError:
            return None

def _extract_json(text: str, task: Task = None) -> Any:
    if not text: return None
    if task: task.log(f"Attempting to extract JSON from {len(text)} chars...", "INFO")
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
        if task: task.log(f"Extraction failed: {e}", "WARNING")
    clean_text = re.sub(r'//.*$', '', text, flags=re.MULTILINE)
    res = _try_parse_json(clean_text)
    if res: return res
    if task: task.log(f"Failed to parse JSON. Content start: {text[:100]}...", "ERROR")
    return None

def _clean_text_for_tts(text: str) -> str:
    """Removes special characters and emojis that confuse TTS engines."""
    if not text: return ""
    # Remove markdown bold/italic (*) and headers (#)
    text = re.sub(r'[*#]', '', text)
    # Remove unicode emojis (Supplementary Multilingual Plane)
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    return text.strip()

def _generate_video_plan(task: Task, lc, context: str, metadata: Dict[str, Any], prompt: str, config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    task.log("Designing video structure...")
    cfg = config or {}
    style = cfg.get('style') or metadata.get('style', 'Engaging and informative')
    intro = metadata.get('intro_script', '')
    outro = metadata.get('outro_script', '')
    num_scenes_hint = cfg.get('num_scenes')
    duration_hint = cfg.get('target_duration')
    platform = cfg.get('platform', 'YouTube (Landscape 16:9)')
    
    constraints = []
    if num_scenes_hint: constraints.append(f"- Target Number of Scenes: {num_scenes_hint}")
    if duration_hint: constraints.append(f"- Target Video Duration: {duration_hint}")
    if platform: constraints.append(f"- Platform Format: {platform}")
    constraints_str = "\n".join(constraints)

    system_prompt = "You are an expert YouTube Scriptwriter and Director. Create a JSON video script."
    user_prompt = f"""
    [Context]
    {context[:15000]}... [truncated]

    [User Request]
    Topic: {prompt}
    Video Style: {style}
    {f"Standard Intro: {intro}" if intro else ""}
    {f"Standard Outro: {outro}" if outro else ""}

    [Constraints]
    {constraints_str}

    [Task]
    Create a detailed scene-by-scene storyboard.
    Output MUST be a valid JSON object with a key "scenes" containing a list of objects.
    
    Each scene object must have:
    - "title": Short title (e.g. "Introduction", "The Problem")
    - "visual_description": Detailed description of what is seen (camera angle, action, lighting). Important for image generation.
    - "audio_script": The exact spoken words (narration or dialogue).
    - "duration_estimate": Estimated seconds (number)
    - "type": "intro", "segment", "animation", or "outro"
    """
    
    raw_response = lc.generate_text(user_prompt, system_prompt=system_prompt)
    response_data = _extract_json(raw_response, task)
    if not response_data or 'scenes' not in response_data:
        task.log("Failed to generate valid JSON structure. Attempting fallback...", "WARNING")
        return []
    return response_data.get("scenes", [])

def _extract_personalities(task: Task, lc, scenes: List[Dict]) -> List[Dict]:
    task.log("Analyzing script for characters...")
    script_text = "\n".join([f"Scene {i}: {s.get('visual_description')} {s.get('audio_script')}" for i, s in enumerate(scenes)])
    if not script_text.strip(): return []
    system_prompt = "You are a Casting Director. Extract main characters."
    user_prompt = f"""
    Analyze the script below. Identify recurrent characters that appear visually.
    Ignore generic crowds.
    Script:
    {script_text[:5000]}
    Output JSON:
    {{ "characters": [{{"name": "Name", "visual_prompt": "Detailed visual description (face, clothes, style)"}}] }}
    """
    raw = lc.generate_text(user_prompt, system_prompt=system_prompt)
    data = _extract_json(raw, task)
    return data.get("characters", []) if data else []

def process_youtube_video(task: Task, notebook: DBNotebook, username: str, prompt: str, input_tab_ids: List[str], action: str, target_tab_id: str = None, selected_artefacts: List[str] = None):
    lc = get_user_lollms_client(username)
    context = gather_context(notebook, input_tab_ids)
    if selected_artefacts:
        for art in notebook.artefacts:
            if art['filename'] in selected_artefacts:
                context += f"\n\n--- Artefact: {art['filename']} ---\n{art['content']}\n"
    metadata = get_notebook_metadata(notebook)
    assets_path = get_user_notebook_assets_path(username, notebook.id)
    target_tab = None
    if target_tab_id:
        target_tab = next((t for t in notebook.tabs if t['id'] == target_tab_id), None)
    
    config = {}
    real_prompt = prompt
    try:
        if prompt.strip().startswith('{'):
            parsed = json.loads(prompt)
            if isinstance(parsed, dict):
                config = parsed
                real_prompt = config.get('topic') or config.get('prompt') or prompt
    except: pass

    # 1. GENERATE FULL SCRIPT / STORYBOARD
    if action == 'generate_script' or (action == 'initial_process' and not target_tab):
        task.log("Generating YouTube video script...")
        scenes = _generate_video_plan(task, lc, context, metadata, real_prompt, config)
        if not scenes:
            task.log("No scenes generated. Creating default structure.", "WARNING")
            scenes = [{"title": "Introduction", "visual_description": "Title card with topic text", "audio_script": f"Welcome to this video about {real_prompt}.", "type": "intro"}]
        content_data = { "scenes": scenes, "metadata": {**metadata, **config}, "personalities": [] }
        if target_tab:
            target_tab['content'] = json.dumps(content_data)
            return target_tab['id']
        else:
            new_tab = { "id": str(uuid.uuid4()), "title": "Storyboard", "type": "youtube_storyboard", "content": json.dumps(content_data), "images": [] }
            notebook.tabs.append(new_tab)
            return new_tab['id']

    # 2. GENERATE PERSONALITIES
    elif action == 'generate_personalities':
        if not target_tab: raise ValueError("No script tab found")
        try: tab_data = json.loads(target_tab['content'])
        except: tab_data = {"scenes": [], "personalities": []}
        chars = _extract_personalities(task, lc, tab_data.get('scenes', []))
        lc_tti = build_lollms_client_from_params(username, load_llm=False, load_tti=True)
        personalities = tab_data.get('personalities', [])
        for c in chars:
            if any(p['name'] == c['name'] for p in personalities): continue
            p_data = { "id": str(uuid.uuid4()), "name": c['name'], "visual_prompt": c['visual_prompt'], "image_path": None }
            if lc_tti.tti:
                task.log(f"Generating image for {c['name']}...")
                try:
                    img_bytes = lc_tti.tti.generate_image(c['visual_prompt'], width=512, height=768) 
                    if img_bytes:
                        fname = f"char_{p_data['id']}.png"
                        (assets_path / fname).write_bytes(img_bytes)
                        p_data['image_path'] = f"/api/notebooks/{notebook.id}/assets/{fname}"
                except Exception as e: task.log(f"Failed to generate {c['name']}: {e}", "ERROR")
            personalities.append(p_data)
        tab_data['personalities'] = personalities
        target_tab['content'] = json.dumps(tab_data)
        return target_tab['id']

    # 3. REGENERATE SINGLE PERSONALITY IMAGE
    elif action == 'regenerate_personality':
        if not target_tab: return
        tab_data = json.loads(target_tab['content'])
        p_id = prompt.strip()
        person = next((p for p in tab_data.get('personalities', []) if p['id'] == p_id), None)
        if person:
            lc_tti = build_lollms_client_from_params(username, load_llm=False, load_tti=True)
            if lc_tti.tti:
                task.log(f"Regenerating {person['name']}...")
                try:
                    img_bytes = lc_tti.tti.generate_image(person['visual_prompt'], width=512, height=768)
                    if img_bytes:
                        fname = f"char_{person['id']}_{uuid.uuid4().hex[:4]}.png"
                        (assets_path / fname).write_bytes(img_bytes)
                        person['image_path'] = f"/api/notebooks/{notebook.id}/assets/{fname}"
                        target_tab['content'] = json.dumps(tab_data)
                except Exception as e: task.log(f"Error regenerating: {e}", "ERROR")
        return target_tab['id']

    # 4. GENERATE SCENE VISUAL (IMAGE)
    elif action == 'generate_scene_image':
        if not target_tab: return
        tab_data = json.loads(target_tab['content'])
        match = re.match(r"SCENE_INDEX:(\d+)", prompt)
        if not match: return
        scene_idx = int(match.group(1))
        if scene_idx >= len(tab_data['scenes']): return
        scene = tab_data['scenes'][scene_idx]
        task.log(f"Generating visual for Scene {scene_idx+1}...")
        
        lc_tti = build_lollms_client_from_params(username, load_llm=False, load_tti=True)
        if not lc_tti.tti:
            task.log("TTI not configured.", "ERROR")
            return

        selected_p_ids = scene.get('selected_personalities', [])
        source_images_b64 = []
        prompt_prefix = ""
        if selected_p_ids:
            all_personalities = tab_data.get('personalities', [])
            for i, pid in enumerate(selected_p_ids):
                p = next((x for x in all_personalities if x['id'] == pid), None)
                if p and p.get('image_path'):
                    fname = p['image_path'].split('/')[-1]
                    local_path = assets_path / fname
                    if local_path.exists():
                        b64 = base64.b64encode(local_path.read_bytes()).decode('utf-8')
                        source_images_b64.append(b64)
                        prompt_prefix += f"Image {i+1} is {p['name']}. "
        
        visual_prompt = scene.get('visual_description', '')
        final_prompt = f"{prompt_prefix}{visual_prompt}"
        if not final_prompt: final_prompt = "A cinematic shot for a video."

        platform = tab_data.get('metadata', {}).get('platform', '')
        width, height = 1280, 720
        if "Shorts" in platform or "TikTok" in platform or "Portrait" in platform:
            width, height = 720, 1280

        try:
            img_bytes = None
            if source_images_b64 and hasattr(lc_tti.tti, 'edit_image'):
                 img_bytes = lc_tti.tti.edit_image(prompt=final_prompt, images=source_images_b64, width=width, height=height)
            else:
                img_bytes = lc_tti.tti.generate_image(prompt=final_prompt, width=width, height=height)

            if img_bytes:
                fname = f"scene_{scene_idx}_{uuid.uuid4().hex[:6]}.png"
                (assets_path / fname).write_bytes(img_bytes)
                scene['image_path'] = f"/api/notebooks/{notebook.id}/assets/{fname}"
                target_tab['content'] = json.dumps(tab_data)
                task.log("Visual generated.")
            else:
                task.log("No image data returned.", "WARNING")
        except Exception as e:
            task.log(f"Generation failed: {e}", "ERROR")
        return target_tab['id']

    # 5. GENERATE ANIMATION (HTML)
    elif action == 'generate_animation':
        # ... logic as before ...
        pass
    
    # 6. GENERATE AUDIO FOR VIDEO SCENES
    elif action == 'generate_audio':
        # Handled in generate_presentation_video_task mostly, but if user wants to gen audio for one scene?
        # TODO: Implement granular audio generation if needed. For now the video task does batch.
        pass

    return target_tab_id

def generate_presentation_video_task(task: Task, username: str, notebook_id: str):
    try:
        from moviepy import ImageClip, concatenate_videoclips, AudioFileClip
    except (ImportError, ModuleNotFoundError) as e:
        task.log(f"Failed to load moviepy: {e}. Installing...", "ERROR")
        import pipmaster as pm
        pm.install("moviepy==2.2.1")
        from moviepy import ImageClip, concatenate_videoclips, AudioFileClip

    assets_path = get_user_notebook_assets_path(username, notebook_id)
    output_path = assets_path / "presentation.mp4"
    temp_dir = Path(tempfile.mkdtemp())
    
    task.log("Initializing TTS and Video components...")
    lc_tts = build_lollms_client_from_params(username, load_llm=False, load_tts=True)
    if not lc_tts.tts:
        task.log("TTS Binding not configured.", "ERROR")
        raise ValueError("TTS not available")

    voice_to_use = None
    language_to_use = 'en'
    
    with task.db_session_factory() as db:
        notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
        if not notebook: raise ValueError("Notebook not found")
        # For youtube video, the tab is 'youtube_storyboard' or 'youtube_script'
        script_tab = next((t for t in notebook.tabs if t['type'] in ['youtube_script', 'youtube_storyboard']), None)
        if not script_tab: raise ValueError("No script tab")
        try: tab_data = json.loads(script_tab['content'])
        except: tab_data = {}
        scenes = tab_data.get('scenes', [])
        
        db_user = db.query(DBUser).filter(DBUser.username == username).first()
        if db_user:
             if db_user.active_voice_id:
                active_voice = db.query(DBUserVoice).filter(DBUserVoice.id == db_user.active_voice_id).first()
                if active_voice:
                    v_path = get_user_data_root(username) / "voices" / active_voice.file_path
                    if v_path.exists(): voice_to_use = str(v_path.resolve())
             if db_user.ai_response_language and db_user.ai_response_language.lower() != "auto":
                language_to_use = db_user.ai_response_language

    if not scenes:
        task.log("No scenes found.", "WARNING")
        return

    clips = []
    task.set_progress(10)
    total = len(scenes)
    
    for i, scene in enumerate(scenes):
        task.log(f"Processing scene {i+1}...")
        img_path = None
        if scene.get('image_path'):
            fname = scene['image_path'].split('/')[-1]
            full_img_path = assets_path / fname
            if full_img_path.exists(): img_path = str(full_img_path)
        
        # If no image, maybe create a text clip? For now skip visual or use placeholder?
        # Assuming we need visual.
        if not img_path: 
            task.log(f"Scene {i+1} has no visual. Skipping.", "WARNING")
            continue

        text = scene.get('audio_script', '')
        
        try:
            audio_file = temp_dir / f"scene_{i}.wav"
            clean_text = _clean_text_for_tts(text)
            
            if clean_text:
                if hasattr(lc_tts.tts, 'generate_audio'):
                    audio_bytes = lc_tts.tts.generate_audio(clean_text, voice=voice_to_use, language=language_to_use)
                    if audio_bytes: 
                        with open(audio_file, "wb") as f: f.write(audio_bytes)
                elif hasattr(lc_tts.tts, 'tts_to_file'):
                    lc_tts.tts.tts_to_file(clean_text, str(audio_file))

            if not audio_file.exists() or audio_file.stat().st_size == 0:
                # Default duration if no audio
                clip = ImageClip(img_path).with_duration(5)
            else:
                audio_clip = AudioFileClip(str(audio_file))
                clip = ImageClip(img_path).with_duration(audio_clip.duration).with_audio(audio_clip)
            
            clips.append(clip)
        except Exception as e:
            task.log(f"Error processing scene {i+1}: {e}", "ERROR")
        
        task.set_progress(10 + int((i+1)/total * 80))

    if clips:
        task.log("Concatenating video clips...")
        final_video = concatenate_videoclips(clips, method="compose")
        final_video.write_videofile(str(output_path), fps=24, codec='libx264', audio_codec='aac')
        
        task.log("Video render complete.")
        task.set_progress(100)
        
        try:
            for f in temp_dir.glob("*"): f.unlink()
            temp_dir.rmdir()
        except: pass
        
        with task.db_session_factory() as db:
            notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
            if notebook:
                # Refresh tab data to ensure we don't overwrite if changed? 
                # Ideally we lock or re-fetch. Here we just update the video link.
                script_tab = next((t for t in notebook.tabs if t['type'] in ['youtube_script', 'youtube_storyboard']), None)
                if script_tab:
                    tab_data = json.loads(script_tab['content'])
                    tab_data['video_src'] = f"/api/notebooks/{notebook_id}/assets/presentation.mp4"
                    script_tab['content'] = json.dumps(tab_data)
                    flag_modified(notebook, "tabs")
                    db.commit()

        return {"file_path": f"/api/notebooks/{notebook_id}/assets/presentation.mp4"}
    
    return None
