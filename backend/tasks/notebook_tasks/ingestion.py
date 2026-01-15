
import uuid
import json
import traceback
from typing import List, Dict, Any, Optional
from sqlalchemy.orm.attributes import flag_modified
from backend.db.models.notebook import Notebook as DBNotebook
from backend.db.models.user import User as DBUser
from backend.task_manager import Task
from ascii_colors import trace_exception

def handle_partial_notebook(db, notebook_id, username):
    """
    Ensures a partially created notebook is properly saved and accessible.
    """
    notebook = db.query(DBNotebook).filter(
        DBNotebook.id == notebook_id,
        DBNotebook.owner_user_id == db.query(DBUser).filter(DBUser.username == username).first().id
    ).first()

    if notebook:
        # Ensure the notebook has at least one tab if it doesn't have any
        if not notebook.tabs:
            notebook.tabs = [{
                "id": str(uuid.uuid4()),
                "title": "Main",
                "type": "markdown",
                "content": "This notebook was partially created. Some content may be missing.",
                "images": []
            }]

        # Commit any changes
        db.commit()
        db.refresh(notebook)

    return notebook


def _add_artefact(notebook, title, content):
    """Helper to add a text artefact to a notebook."""
    current = list(notebook.artefacts) if notebook.artefacts else []
    # Avoid duplicates
    if any(a['filename'] == title for a in current):
        return
    current.append({
        "filename": title,
        "content": content,
        "type": "text",
        "is_loaded": True
    })
    notebook.artefacts = current

def _ingest_notebook_sources_task(
    task: Task, 
    username: str, 
    notebook_id: str, 
    urls: List[str], 
    youtube_configs: List[Dict[str, str]] = None, 
    wikipedia_urls: List[str] = None,
    google_search_queries: List[str] = None,
    arxiv_queries: List[str] = None,
    initial_prompt: Optional[str] = None,
    target_tab_id: Optional[str] = None,
    arxiv_config: Optional[Dict[str, Any]] = None,
    arxiv_selected_list: Optional[List[Dict[str, Any]]] = None
):
    task.log("Starting production ingestion...")
    task.set_progress(5)
    
    yt_list = youtube_configs or []
    wiki_list = wikipedia_urls or []
    google_list = google_search_queries or []
    arxiv_list = arxiv_queries or []
    
    total_ops = len(urls) + len(yt_list) + len(wiki_list) + len(google_list) + len(arxiv_list) + (len(arxiv_selected_list) if arxiv_selected_list else 0)
    current_op = 0

    with task.db_session_factory() as db:
        notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
        if not notebook:
            task.log("Notebook not found", "ERROR")
            return

        # 1. Wikipedia Ingestion
        if wiki_list:
            try:
                import pipmaster as pm
                if not pm.is_installed("wikipedia"):
                    pm.install("wikipedia")
                import wikipedia
                
                for query in wiki_list:
                    if task.cancellation_event.is_set(): break
                    task.log(f"Fetching Wikipedia: {query}")
                    try:
                        page_title = query.split('/')[-1].replace('_', ' ') if 'wikipedia.org' in query else query
                        # Try exact match first
                        try:
                            page = wikipedia.page(page_title, auto_suggest=False)
                        except wikipedia.exceptions.PageError:
                            # If exact failed, try auto-suggest
                            task.log(f"Exact match failed for {page_title}, trying suggestion...", "INFO")
                            page = wikipedia.page(page_title, auto_suggest=True)
                            
                        _add_artefact(notebook, f"Wikipedia: {page.title}", page.content)
                        flag_modified(notebook, "artefacts")
                        db.commit()
                    except Exception as e:
                        task.log(f"Wikipedia error for {query}: {str(e)}", "WARNING")
                    current_op += 1
                    if total_ops > 0: task.set_progress(int(current_op / total_ops * 90))
            except Exception as e:
                task.log(f"Wikipedia system error: {e}", "ERROR")

        # 2. Web URLs Ingestion
        if urls:
            try:
                from scrapemaster import ScrapeMaster
                for url in urls:
                    if task.cancellation_event.is_set(): break
                    task.log(f"Scraping Web: {url}")
                    try:
                        scraper = ScrapeMaster(url)
                        content = scraper.scrape_markdown()
                        if content:
                            _add_artefact(notebook, f"Web: {url}", content)
                            flag_modified(notebook, "artefacts")
                            db.commit()
                    except Exception as e:
                        task.log(f"Scrape failed for {url}: {e}", "WARNING")
                    current_op += 1
                    if total_ops > 0: task.set_progress(int(current_op / total_ops * 90))
            except Exception as e:
                task.log(f"Scrape system error: {e}", "ERROR")

        # 3. YouTube Ingestion
        if yt_list:
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
                for yt in yt_list:
                    if task.cancellation_event.is_set(): break
                    url = yt.get('url')
                    lang = yt.get('lang', 'en')
                    task.log(f"Fetching YouTube [{lang}]: {url}")
                    try:
                        vid = None
                        if "v=" in url: vid = url.split("v=")[1].split("&")[0]
                        elif "youtu.be/" in url: vid = url.split("youtu.be/")[1]
                        
                        if vid:
                            try:
                                vtapi = YouTubeTranscriptApi()
                                ts = vtapi.fetch(vid, languages=[lang])
                            except:
                                ytt = YouTubeTranscriptApi()
                                try:
                                    ts = ytt.fetch(vid, languages=[lang])
                                except:
                                    ts = ytt.fetch(vid)
                            
                            def extract_text(item):
                                if isinstance(item, dict):
                                    return item.get('text', '')
                                return getattr(item, 'text', '')

                            txt = " ".join([extract_text(t) for t in ts])
                            _add_artefact(notebook, f"YouTube: {url}", txt)
                            flag_modified(notebook, "artefacts")
                            db.commit()
                    except Exception as e:
                        error_trace = traceback.format_exc()
                        task.log(f"YouTube failed for {url}: {e}\nTraceback:\n{error_trace}", "WARNING")
                    current_op += 1
                    if total_ops > 0: task.set_progress(int(current_op / total_ops * 90))
            except Exception as e:
                error_trace = traceback.format_exc()
                task.log(f"YouTube system error: {e}\nTraceback:\n{error_trace}", "ERROR")

        # 4. Google Search Ingestion
        if google_list:
            user = db.query(DBUser).filter(DBUser.username == username).first()
            if not user or not user.google_api_key or not user.google_cse_id:
                task.log("Google Search skipped: User API Key or CSE ID missing.", "WARNING")
            else:
                try:
                    from googleapiclient.discovery import build as google_build
                    from scrapemaster import ScrapeMaster
                    
                    service = google_build("customsearch", "v1", developerKey=user.google_api_key)
                    
                    for query in google_list:
                        if task.cancellation_event.is_set(): break
                        task.log(f"Google Search: {query}")
                        try:
                            res = service.cse().list(q=query, cx=user.google_cse_id, num=5).execute()
                            items = res.get('items', [])
                            
                            if items:
                                summary_text = f"Search Results for '{query}':\n\n" + "\n".join([f"## {item.get('title')}\nLink: {item.get('link')}\n{item.get('snippet')}\n" for item in items])
                                _add_artefact(notebook, f"Search Summary: {query}", summary_text)
                                
                                for i, item in enumerate(items[:3]):
                                    if task.cancellation_event.is_set(): break
                                    link = item.get('link')
                                    task.log(f"Scraping result {i+1}: {link}")
                                    try:
                                        scraper = ScrapeMaster(link)
                                        content = scraper.scrape_markdown()
                                        if content:
                                            _add_artefact(notebook, f"Web: {item.get('title')}", content)
                                    except Exception as e:
                                        task.log(f"Failed to scrape {link}: {e}", "WARNING")
                                        
                                flag_modified(notebook, "artefacts")
                                db.commit()
                            else:
                                task.log(f"No results for query: {query}", "INFO")
                                
                        except Exception as e:
                            task.log(f"Error searching '{query}': {e}", "ERROR")
                        
                        current_op += 1
                        if total_ops > 0: task.set_progress(int(current_op / total_ops * 90))
                except ImportError:
                    task.log("Google API Client library not installed.", "ERROR")
                except Exception as e:
                    task.log(f"Google Search system error: {e}", "ERROR")

        # 5. Arxiv Queries (Legacy/Manual list)
        if arxiv_list:
            try:
                import pipmaster as pm
                if not pm.is_installed("arxiv"):
                    pm.install("arxiv")
                import arxiv
                
                client = arxiv.Client()
                
                for query in arxiv_list:
                    if task.cancellation_event.is_set(): break
                    task.log(f"Arxiv Search: {query}")
                    try:
                        search = arxiv.Search(
                            query = query,
                            max_results = 3,
                            sort_by = arxiv.SortCriterion.Relevance
                        )
                        results = client.results(search)
                        found_any = False
                        
                        for r in results:
                            found_any = True
                            content = f"# {r.title}\n\n"
                            content += f"**Authors:** {', '.join([a.name for a in r.authors])}\n"
                            content += f"**Published:** {r.published.strftime('%Y-%m-%d')}\n"
                            content += f"**PDF:** {r.pdf_url}\n\n"
                            content += "## Abstract\n"
                            content += r.summary
                            _add_artefact(notebook, f"Arxiv: {r.title}", content)
                        
                        if found_any:
                            flag_modified(notebook, "artefacts")
                            db.commit()
                        else:
                            task.log(f"No Arxiv results for: {query}", "INFO")
                    except Exception as e:
                        task.log(f"Error searching Arxiv for '{query}': {e}", "ERROR")
                    
                    current_op += 1
                    if total_ops > 0: task.set_progress(int(current_op / total_ops * 90))
            except Exception as e:
                task.log(f"Arxiv system error: {e}", "ERROR")

        # 6. Selected Arxiv Ingestion (Specific user selection)
        if arxiv_selected_list:
            try:
                import pipmaster as pm
                if not pm.is_installed("arxiv"):
                    pm.install("arxiv")
                import requests
                
                for item in arxiv_selected_list:
                    if task.cancellation_event.is_set(): break
                    title = item.get('title')
                    pdf_url = item.get('pdf_url')
                    summary = item.get('summary')
                    ingest_full = item.get('ingest_full', False)
                    task.log(f"Processing Arxiv Selection: {title}")
                    
                    if not ingest_full:
                        content = f"# {title}\n\n**Authors:** {', '.join(item.get('authors',[]))}\n**PDF:** {pdf_url}\n\n## Abstract\n{summary}"
                        _add_artefact(notebook, f"Arxiv Abstract: {title}", content)
                    else:
                        task.log(f"Downloading PDF: {pdf_url}")
                        try:
                            response = requests.get(pdf_url, stream=True)
                            if response.status_code == 200:
                                import tempfile
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        tf.write(chunk)
                                    tf_path = tf.name
                                
                                try:
                                    from docling.document_converter import DocumentConverter
                                    converter = DocumentConverter()
                                    res = converter.convert(tf_path)
                                    md = res.document.export_to_markdown()
                                    _add_artefact(notebook, f"Arxiv Paper: {title}", md)
                                except ImportError:
                                    task.log("Docling not available, cannot convert PDF.", "WARNING")
                                except Exception as e:
                                    task.log(f"Conversion failed: {e}", "ERROR")
                                finally:
                                    import os
                                    if os.path.exists(tf_path): os.unlink(tf_path)
                            else:
                                task.log(f"Failed to download PDF {pdf_url}", "WARNING")
                        except Exception as e:
                            task.log(f"Error processing PDF {pdf_url}: {e}", "ERROR")
                    
                    flag_modified(notebook, "artefacts")
                    db.commit()
                    current_op += 1
                    if total_ops > 0: task.set_progress(int(current_op / total_ops * 90))
            except Exception as e:
                task.log(f"Arxiv selected error: {e}", "ERROR")
        # Check for cancellation at key points
        if task.cancellation_event.is_set():
            task.log("Task cancelled by user. Saving partial notebook state.", "WARNING")
            with task.db_session_factory() as db:
                handle_partial_notebook(db, notebook_id, username)
            return
        # --- TASK CHAINING: Trigger Production Phase ---
        if not task.cancellation_event.is_set():
            db.refresh(notebook)
            has_artefacts = len(notebook.artefacts) > 0
            
            effective_prompt = initial_prompt
            if not effective_prompt:
                if has_artefacts:
                    task.log("No specific prompt provided. Auto-generating based on ingested data.", "INFO")
                    effective_prompt = "Create a detailed presentation structure based on the available research data."
                else:
                    task.log("No prompt and no source data provided. Skipping generation phase.", "WARNING")
                    task.set_progress(100)
                    return

            task.log(f"Transitioning to Production Phase: {notebook.type}")
            task.set_progress(95)
            
            from backend.tasks.notebook_tasks import _process_notebook_task
            
            action = 'initial_process' 
            if notebook.type == 'youtube_video':
                action = 'generate_script'
            elif notebook.type == 'book_building':
                action = 'generate_book_plan'
            
            try:
                _process_notebook_task(
                    task=task,
                    username=username,
                    notebook_id=notebook_id,
                    prompt=effective_prompt,
                    input_tab_ids=[],
                    action=action,
                    target_tab_id=target_tab_id,
                    selected_artefacts=[]
                )
            except Exception as e:
                task.log(f"Chained Production Task Failed: {str(e)}", "ERROR")
                trace_exception(e)

    task.set_progress(100)
    task.log("Pipeline processing completed.")

def _convert_file_with_docling_task(task: Task, username: str, notebook_id: str, file_path: str, original_filename: str):
    task.log(f"Converting document: {original_filename}...")
    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result = converter.convert(file_path)
        md = result.document.export_to_markdown()
        
        with task.db_session_factory() as db:
            notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
            if notebook:
                _add_artefact(notebook, f"File: {original_filename}", md)
                flag_modified(notebook, "artefacts")
                db.commit()
        task.set_progress(100)
        task.log(f"File {original_filename} ingested.")
    except Exception as e:
        task.log(f"File conversion error: {e}", "ERROR")
        trace_exception(e)
