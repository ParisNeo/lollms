# backend/tasks/artefact_tasks.py
import traceback
from datetime import datetime
from pydantic import BaseModel
from ascii_colors import trace_exception

from backend.discussion import get_user_discussion
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

class UrlImportRequest(BaseModel):
    url: str

def _import_artefact_from_url_task(task: Task, username: str, discussion_id: str, url: str):
    if ScrapeMaster is None:
        raise ImportError("ScrapeMaster library is not installed and could not be installed automatically.")
    
    task.log("Starting URL import task for artefact...")
    task.set_progress(5)
    
    try:
        task.log(f"Scraping URL: {url}")
        scraper = ScrapeMaster(url)
        markdown_content = scraper.scrape_markdown()
        task.set_progress(70)

        if not markdown_content or not markdown_content.strip():
            task.log("No main content could be extracted from the URL.", "WARNING")
            raise ValueError("No main content found at the provided URL.")

        task.log(f"Successfully scraped {len(markdown_content)} characters.")
        discussion = get_user_discussion(username, discussion_id)
        if not discussion:
            raise ValueError("Discussion not found after scraping.")

        artefact_info = discussion.add_artefact(
            title=url,
            content=markdown_content.strip(),
            author=username
        )
        discussion.commit()
        task.set_progress(100)
        
        task.log(f"Artefact '{url}' imported from URL and saved.")
        if isinstance(artefact_info.get('created_at'), datetime):
            artefact_info['created_at'] = artefact_info['created_at'].isoformat()
        if isinstance(artefact_info.get('updated_at'), datetime):
            artefact_info['updated_at'] = artefact_info['updated_at'].isoformat()
        
        return artefact_info
    except Exception as e:
        task.log(f"Failed to import from URL: {e}", "ERROR")
        trace_exception(e)
        raise e