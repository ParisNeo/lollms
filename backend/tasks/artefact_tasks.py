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
        markdown_content = scraper.scrape_markdown() # TODO add depth when scrapemaster is updated 
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

        artefact_info = discussion.add_artefact(
            title=url,
            content=final_content,
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
