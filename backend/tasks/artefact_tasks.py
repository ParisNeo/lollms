# backend/tasks/artefact_tasks.py
import traceback
from datetime import datetime
from pydantic import BaseModel
from ascii_colors import trace_exception

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

def _import_artefact_from_url_task(task: Task, username: str, discussion_id: str, url: str, depth: int = 0, process_with_ai: bool = False):
    if ScrapeMaster is None:
        raise ImportError("ScrapeMaster library is not installed and could not be installed automatically.")
    
    task.log(f"Starting URL import task. URL: {url}, Depth: {depth}, AI Processing: {process_with_ai}")
    task.set_progress(5)
    
    try:
        task.log(f"Scraping URL hierarchy...")
        scraper = ScrapeMaster(url)
        # ScrapeMaster supports depth for crawling
        markdown_content = scraper.scrape_markdown(max_depth = depth) # TODO add depth when scrapemaster is updated 
        task.set_progress(50)

        if not markdown_content or not markdown_content.strip():
            task.log("No main content could be extracted from the URL.", "WARNING")
            raise ValueError("No main content found at the provided URL.")

        final_content = markdown_content.strip()

        if process_with_ai:
            task.log("AI Processing enabled. Cleaning and structuring content...")
            task.set_description("AI is processing the scraped content...")
            lc = get_user_lollms_client(username)
            
            prompt = f"Scraped content from {url}:\n\n{final_content}\n\n"
            prompt += "--- Task ---\n"
            prompt += "Analyze the scraped markdown above. Clean up boilerplate, navigation menus, and footers. "
            prompt += "Structure the core information clearly. Ensure all relevant knowledge is preserved. "
            prompt += "Format the result as clean markdown."
            
            def ai_callback(chunk, msg_type, params=None):
                if task.cancellation_event.is_set(): return False
                return True

            final_content = lc.generate_text(prompt, streaming_callback=ai_callback)
            task.log("AI processing finished.")

        task.set_progress(90)
        discussion = get_user_discussion(username, discussion_id)
        if not discussion:
            raise ValueError("Discussion not found after scraping.")

        # Use positional arguments for required fields (title, content)
        artefact_info = discussion.add_artefact(
            url,
            final_content,
            author=username
        )
        discussion.commit()
        task.set_progress(100)
        
        task.log(f"Artefact '{url}' imported successfully.")
        
        # Clean up timestamps for JSON serialization
        if isinstance(artefact_info.get('created_at'), datetime):
            artefact_info['created_at'] = artefact_info['created_at'].isoformat()
        if isinstance(artefact_info.get('updated_at'), datetime):
            artefact_info['updated_at'] = artefact_info['updated_at'].isoformat()
        
        return artefact_info
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
