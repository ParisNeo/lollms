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

        # Broadcast live sync event over WebSocket so all UI components update immediately
        try:
            from backend.ws_manager import manager
            with task.db_session_factory() as db:
                from backend.db.models.user import User as DBUser
                user_rec = db.query(DBUser).filter(DBUser.username == username).first()
                if user_rec:
                    manager.send_personal_message_sync({
                        "type": "discussion_updated",
                        "data": {
                            "discussion_id": discussion_id,
                            "sender_username": username
                        }
                    }, user_rec.id)
        except Exception as ws_err:
            print(f"Warning: Failed to broadcast discussion_updated from artefact task: {ws_err}")

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
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
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

    # Normalize protocol
    clean_url = url.strip()
    if not clean_url.startswith(('http://', 'https://')):
        clean_url = f"https://{clean_url}"

    # SSRF protection
    from backend.security import validate_url, safe_requests_get
    try:
        validate_url(clean_url)
    except ValueError as ve:
        task.log(f"Security error: {ve}", "ERROR")
        raise ve

    try:
        discussion = get_user_discussion(username, discussion_id)
        if not discussion:
            raise ValueError(f"Discussion '{discussion_id}' not found.")

        task.set_progress(25)
        task.log(f"Scraping content from '{clean_url}'...")

        clean_title = _clean_url_to_title(clean_url)

        imported = False
        if hasattr(discussion, 'import_url'):
            try:
                task.log("Attempting native discussion.import_url...")
                discussion.import_url(
                    url=clean_url,
                    depth=depth,
                    process_with_ai=process_with_ai,
                    title=clean_title,
                    auto_load=True
                )
                imported = True
            except TypeError:
                try:
                    discussion.import_url(
                        url=clean_url,
                        depth=depth,
                        process_with_ai=process_with_ai,
                        auto_load=True
                    )
                    imported = True
                except Exception as ex_type:
                    task.log(f"Native import_url failed with fallback: {ex_type}", "WARNING")
            except Exception as ex_import:
                task.log(f"Native import_url failed: {ex_import}. Falling back to resilient web scraper...", "WARNING")

        # Multi-strategy scraping fallback
        if not imported:
            scraped_content = ""

            # Strategy 1: ScrapeMaster
            if ScrapeMaster:
                try:
                    task.log("Attempting ScrapeMaster extraction...")
                    scraper = ScrapeMaster(clean_url, strategy=["beautifulsoup", "selenium"], headless=True)
                    if hasattr(scraper, "scrape_markdown"):
                        scraped_content = scraper.scrape_markdown()
                    elif hasattr(scraper, "scrape_all"):
                        results = scraper.scrape_all(max_depth=depth, convert_to_markdown=True)
                        scraped_content = results.get('markdown') or "\n\n".join(results.get('texts', []))
                    elif hasattr(scraper, "scrape"):
                        scraped_content = scraper.scrape(clean_url)
                except Exception as sm_err:
                    task.log(f"ScrapeMaster failed: {sm_err}", "WARNING")

            # Strategy 2: Safe HTTP + BeautifulSoup fallback
            if not scraped_content or len(scraped_content.strip()) < 20:
                task.log("Attempting resilient HTTP extraction with BeautifulSoup...")
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                }
                from bs4 import BeautifulSoup
                resp = safe_requests_get(clean_url, headers=headers, timeout=15, max_response_size=2097152)
                resp.raise_for_status()

                soup = BeautifulSoup(resp.content, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "iframe"]):
                    tag.decompose()

                page_title = soup.title.string.strip() if soup.title and soup.title.string else clean_title
                main_el = soup.find("article") or soup.find("main") or soup.find("div", {"id": "content"}) or soup.body or soup
                scraped_text = main_el.get_text(separator="\n\n", strip=True) if main_el else ""

                scraped_content = f"# {page_title}\nSource: {clean_url}\n\n{scraped_text}"

            if not scraped_content or len(scraped_content.strip()) < 10:
                raise ValueError(f"No readable content could be extracted from {clean_url}")

            task.set_progress(70)

            # Strategy 3: Optional AI summary / refinement
            if process_with_ai:
                task.log("Refining content with AI summarization...")
                try:
                    lc = get_user_lollms_client(username)
                    if lc:
                        prompt = f"Convert the following scraped web content into clean, structured Markdown. Preserve all factual details, links, and code snippets:\n\n{scraped_content[:12000]}"
                        ai_text = lc.generate_text(prompt, max_new_tokens=2048)
                        if ai_text and len(ai_text.strip()) > 50:
                            scraped_content = ai_text.strip()
                except Exception as ai_err:
                    task.log(f"AI refinement note: {ai_err}. Preserving raw scraped content.", "INFO")

            task.log(f"Adding '{clean_title}' to discussion workspace...")
            discussion.add_artefact(
                title=clean_title,
                content=scraped_content,
                author="Web Scraper",
                active=True,
                artefact_type="document"
            )
            from lollms_client.lollms_artefact import ArtefactVisibility
            discussion.artefacts.set_visibility(clean_title, ArtefactVisibility.FULL)

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

        # Broadcast live sync event over WebSocket
        try:
            from backend.ws_manager import manager
            with task.db_session_factory() as db:
                from backend.db.models.user import User as DBUser
                user_rec = db.query(DBUser).filter(DBUser.username == username).first()
                if user_rec:
                    manager.send_personal_message_sync({
                        "type": "discussion_updated",
                        "data": {
                            "discussion_id": discussion_id,
                            "sender_username": username
                        }
                    }, user_rec.id)
        except Exception as ws_err:
            print(f"Warning: Failed to broadcast discussion_updated from url task: {ws_err}")

        task.set_progress(100)
        task.log(f"Successfully imported from '{clean_url}'.")
        return {
            "message": f"Successfully imported content from {clean_url}", 
            "url": clean_url,
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
