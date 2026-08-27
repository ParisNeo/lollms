# backend/tasks/artefact_tasks.py
import traceback
import re
from datetime import datetime
from pydantic import BaseModel
from ascii_colors import trace_exception
from pathlib import Path
import tempfile
import shutil

from backend.discussion import get_user_discussion
from backend.session import get_user_lollms_client
from backend.task_manager import Task

try:
    from scrapemaster import ScrapeMaster
except ImportError:
    try:
        import pipmaster as pm
        print("ScrapeMaster not installed. Installing it for you.")
        pm.install("ScrapeMaster")
        from scrapemaster import ScrapeMaster
    except Exception as ex:
        traceback.print_exc()
        print("Couldn't install ScrapeMaster. Please install it manually (`pip install ScrapeMaster`)")
        ScrapeMaster = None

def _map_artefact_for_ui_local(art: dict, discussion_id: str = None) -> dict:
    """
    Standardizes Artefact metadata for the UI without relying on any external imports.
    Maps internal library keys ('type', 'active') to public API keys ('artefact_type', 'is_loaded').
    """
    mapped = {k: v for k, v in art.items() if k not in ['content', 'images']}
    
    # Ensure discussion_id is preserved
    if 'discussion_id' not in mapped and discussion_id:
        mapped['discussion_id'] = discussion_id

    # Map library internal 'type' to UI 'artefact_type'
    mapped['artefact_type'] = art.get('type', 'document')
    
    # Map library 'active' (boolean) to UI 'is_loaded'
    mapped['is_loaded'] = bool(art.get('active', False))
    
    # Handle serialization of dates
    for date_key in ['created_at', 'updated_at']:
        if isinstance(mapped.get(date_key), datetime):
            mapped[date_key] = mapped[date_key].isoformat()
            
    return mapped

def _import_artefact_task(
    task: Task, 
    username: str, 
    discussion_id: str, 
    file_path_str: str, 
    filename: str, 
    pdf_mode: str, 
    auto_load: bool = True,
    on_conflict: str = "suffix"
):
    task.log(f"Importing artefact '{filename}' (Mode: {pdf_mode}, Conflict: {on_conflict})...")
    task.set_progress(10)
    
    file_path = Path(file_path_str)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path_str}")

    try:
        discussion = get_user_discussion(username, discussion_id)
        if not discussion:
            raise ValueError(f"Discussion '{discussion_id}' not found.")

        # Map UI and API modes to native lollms_client import_file modes
        mode_mapping = {
            'as_is': 'as_is',
            'text': 'text',
            'text_images': 'text_images',
            'text_embedded_images': 'text_embedded_images',
            'images_only': 'images_only',
            'ocr': 'ocr',
            'data': 'data',
            'data_bundle': 'data_bundle',
            'audio_stt': 'audio_stt'
        }
        import_mode = mode_mapping.get(pdf_mode, 'as_is' if file_path.suffix.lower() in ['.docx', '.pdf', '.xlsx', '.pptx'] and pdf_mode == 'as_is' else 'text_images')
        
        task.set_progress(30)
        task.log(f"Processing '{filename}' using mode '{import_mode}'...")
        
        # Native library method handles ingestion and artefact creation
        result = discussion.import_file(
            path=str(file_path.resolve()),
            mode=import_mode,
            title=filename,
            auto_load=auto_load,
            on_conflict=on_conflict
        )
        
        task.set_progress(90)
        discussion.commit()
        
        # Fetch updated artefacts list for task result
        artefacts = [
            {
                "title": a["title"],
                "version": a["version"],
                "artefact_type": a.get("type", "document"),
                "is_loaded": a.get("active", False)
            }
            for a in discussion.list_artefacts()
        ]
        
        task.set_progress(100)
        task.log(f"Successfully imported '{filename}'.")
        return {
            "message": f"Successfully imported '{filename}'",
            "artefacts": artefacts,
            "filename": filename,
            "import_mode": import_mode
        }
    except Exception as e:
        task.log(f"Failed to import '{filename}': {e}", "ERROR")
        trace_exception(e)
        raise e
    finally:
        # Clean up temporary upload file
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as ex:
            print(f"Warning: Could not remove temp file {file_path}: {ex}")

def _clean_url_to_title(url: str) -> str:
    """Generates a clean, deterministic title from a URL without ugly slashes or duplicate schemas."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    netloc = parsed.netloc.replace('www.', '')
    path_clean = parsed.path.strip('/').replace('/', '_')

    if 'github.com' in netloc:
        parts = [p for p in parsed.path.strip('/').split('/') if p]
        if len(parts) >= 2:
            return f"GitHub_{parts[0]}_{parts[1]}.md"
        elif len(parts) == 1:
            return f"GitHub_{parts[0]}.md"

    if path_clean:
        return f"{netloc}_{path_clean[:40]}.md"
    return f"{netloc}.md"

def _import_artefact_from_url_task(task: Task, username: str, discussion_id: str, url: str, depth: int = 0, process_with_ai: bool = False):
    task.log(f"Importing from URL: {url} (Depth: {depth})...")
    task.set_progress(10)

    try:
        discussion = get_user_discussion(username, discussion_id)
        if not discussion:
            raise ValueError(f"Discussion '{discussion_id}' not found.")

        task.set_progress(30)
        task.log(f"Scraping content from '{url}'...")

        clean_title = _clean_url_to_title(url)

        # Native lollms_client method handles scraping and artefact creation
        try:
            result = discussion.import_url(
                url=url,
                depth=depth,
                process_with_ai=process_with_ai,
                title=clean_title,
                auto_load=True
            )
        except TypeError:
            result = discussion.import_url(
                url=url,
                depth=depth,
                process_with_ai=process_with_ai,
                auto_load=True
            )

        task.set_progress(90)
        discussion.commit()

        # Fetch updated artefacts list for task result
        artefacts = [
            {
                "title": a["title"],
                "version": a["version"],
                "artefact_type": a.get("type", "document"),
                "is_loaded": a.get("active", False)
            }
            for a in discussion.list_artefacts()
        ]
        
        task.set_progress(100)
        task.log(f"Successfully imported from '{url}'.")
        return {
            "message": f"Successfully imported content from {url}", 
            "url": url,
            "artefacts": artefacts
        }
    except Exception as e:
        task.log(f"Failed to import from URL: {e}", "ERROR")
        trace_exception(e)
        raise e

def _export_audio_task(task: Task, username: str, title: str, text: str):
    task.log(f"Starting background audio generation for: {title}")
    task.set_progress(10)

    try:
        from backend.session import get_user_data_root, build_lollms_client_from_params

        # Clean text
        clean_text = text.replace('#', '').replace('*', '').strip()
        if not clean_text:
            raise ValueError("Document content is empty after cleaning.")

        # Init Client
        lc = build_lollms_client_from_params(username=username, load_llm=False, load_tts=True)
        if not lc.tts:
            raise Exception("TTS Service is not configured or available.")

        task.set_progress(30)
        task.log("Communicating with TTS Engine... (This may take several minutes for large files)")

        audio_bytes = lc.tts.generate_audio(clean_text)

        task.set_progress(90)
        task.log("Generation complete. Saving file...")

        # Save to user's generated media folder
        output_dir = get_user_data_root(username) / "generated_audio"
        output_dir.mkdir(parents=True, exist_ok=True)

        safe_title = "".join([c if c.isalnum() else "_" for c in title])
        filename = f"{safe_title}_{datetime.now().strftime('%H%M%S')}.wav"
        file_path = output_dir / filename

        file_path.write_bytes(audio_bytes)

        task.set_progress(100)
        task.log(f"Success. Ready for download.")

        # Return the download path relative to the api/files/generated endpoint
        return {
            "status": "ready",
            "filename": filename,
            "download_url": f"/api/files/generated_audio/{filename}"
        }

    except Exception as e:
        task.log(f"Audio export failed: {str(e)}", "ERROR")
        trace_exception(e)
        raise e
