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
    from backend.db.models.user import User as DBUser
    
    user = db.query(DBUser).filter(DBUser.username == username).first()
    if not user:
        return None
        
    notebook = db.query(DBNotebook).filter(
        DBNotebook.id == notebook_id,
        DBNotebook.owner_user_id == user.id
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

        # Initialize artefacts if None
        if notebook.artefacts is None:
            notebook.artefacts = []

        # Commit any changes
        db.commit()
        db.refresh(notebook)

    return notebook


def _add_artefact(notebook, title, content):
    """Helper to add a text artefact to a notebook."""
    # Initialize artefacts if None
    if notebook.artefacts is None:
        notebook.artefacts = []
    
    current = list(notebook.artefacts) if notebook.artefacts else []
    # Avoid duplicates
    if any(a.get('filename') == title for a in current):
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
    arxiv_selected = arxiv_selected_list or []
    
    total_ops = len(urls) + len(yt_list) + len(wiki_list) + len(google_list) + len(arxiv_list) + len(arxiv_selected)
    current_op = 0

    with task.db_session_factory() as db:
        # Fetch and lock the notebook row to ensure we have the latest state
        notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
        if not notebook:
            task.log("Notebook not found", "ERROR")
            return

        # CRITICAL FIX: Initialize artefacts if None and refresh to ensure SQLAlchemy tracks it
        if notebook.artefacts is None:
            notebook.artefacts = []
        
        # Force a refresh to ensure SQLAlchemy knows about all columns
        db.refresh(notebook)
        
        # Ensure artefacts is a list (not None) in the object state
        # This is necessary for flag_modified to work later
        current_artefacts = notebook.artefacts if notebook.artefacts is not None else []
        if notebook.artefacts is None:
            notebook.artefacts = []
            db.flush()  # Flush to get SQLAlchemy to track the change

        # 1. Wikipedia Ingestion
        if wiki_list:
            try:
                import pipmaster as pm
                if not pm.is_installed("wikipedia"):
                    pm.install("wikipedia")
                import wikipedia
                
                for query in wiki_list:
                    if task.cancellation_event.is_set():
                        break
                    task.log(f"Fetching Wikipedia: {query}")
                    try:
                        page_title = query.split('/')[-1].replace('_', ' ') if 'wikipedia.org' in query else query
                        # Try exact match first
                        try:
                            page = wikipedia.page(page_title, auto_suggest=False)
                        except Exception:
                            # If exact failed, try auto-suggest
                            task.log(f"Exact match failed for {page_title}, trying suggestion...", "INFO")
                            page = wikipedia.page(page_title, auto_suggest=True)
                            
                        _add_artefact(notebook, f"Wikipedia: {page.title}", page.content)
                        db.flush()  # Flush after each artefact to ensure state is tracked
                    except Exception as e:
                        task.log(f"Wikipedia error for {query}: {str(e)}", "WARNING")
                    current_op += 1
                    if total_ops > 0:
                        task.set_progress(int(current_op / total_ops * 90))
            except Exception as e:
                task.log(f"Wikipedia system error: {e}", "ERROR")

        # 2. Web URLs Ingestion
        if urls:
            try:
                from scrapemaster import ScrapeMaster
                for url in urls:
                    if task.cancellation_event.is_set():
                        break
                    task.log(f"Scraping Web: {url}")
                    try:
                        scraper = ScrapeMaster(url)
                        content = scraper.scrape_markdown()
                        if content:
                            _add_artefact(notebook, f"Web: {url}", content)
                            db.flush()
                    except Exception as e:
                        task.log(f"Scrape failed for {url}: {e}", "WARNING")
                    current_op += 1
                    if total_ops > 0:
                        task.set_progress(int(current_op / total_ops * 90))
            except Exception as e:
                task.log(f"Scrape system error: {e}", "ERROR")

        # 3. YouTube Ingestion
        if yt_list:
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
                for yt in yt_list:
                    if task.cancellation_event.is_set():
                        break
                    url = yt.get('url') if isinstance(yt, dict) else yt
                    lang = yt.get('lang', 'en') if isinstance(yt, dict) else 'en'
                    task.log(f"Fetching YouTube [{lang}]: {url}")
                    try:
                        vid = None
                        if "v=" in url:
                            vid = url.split("v=")[1].split("&")[0]
                        elif "youtu.be/" in url:
                            vid = url.split("youtu.be/")[1]
                        
                        if vid:
                            try:
                                vtapi = YouTubeTranscriptApi()
                                ts = vtapi.fetch(vid, languages=[lang])
                            except Exception:
                                ytt = YouTubeTranscriptApi()
                                try:
                                    ts = ytt.fetch(vid, languages=[lang])
                                except Exception:
                                    ts = ytt.fetch(vid)
                            
                            def extract_text(item):
                                if isinstance(item, dict):
                                    return item.get('text', '')
                                return getattr(item, 'text', '')

                            txt = " ".join([extract_text(t) for t in ts])
                            _add_artefact(notebook, f"YouTube: {url}", txt)
                            db.flush()
                    except Exception as e:
                        error_trace = traceback.format_exc()
                        task.log(f"YouTube failed for {url}: {e}\nTraceback:\n{error_trace}", "WARNING")
                    current_op += 1
                    if total_ops > 0:
                        task.set_progress(int(current_op / total_ops * 90))
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
                        if task.cancellation_event.is_set():
                            break
                        task.log(f"Google Search: {query}")
                        try:
                            res = service.cse().list(q=query, cx=user.google_cse_id, num=5).execute()
                            items = res.get('items', [])
                            
                            if items:
                                summary_text = f"Search Results for '{query}':\n\n" + "\n".join([f"## {item.get('title')}\nLink: {item.get('link')}\n{item.get('snippet')}\n" for item in items])
                                _add_artefact(notebook, f"Search Summary: {query}", summary_text)
                                
                                for i, item in enumerate(items[:3]):
                                    if task.cancellation_event.is_set():
                                        break
                                    link = item.get('link')
                                    task.log(f"Scraping result {i+1}: {link}")
                                    try:
                                        scraper = ScrapeMaster(link)
                                        content = scraper.scrape_markdown()
                                        if content:
                                            _add_artefact(notebook, f"Web: {item.get('title')}", content)
                                            db.flush()
                                    except Exception as e:
                                        task.log(f"Failed to scrape {link}: {e}", "WARNING")
                                        
                                db.flush()
                            else:
                                task.log(f"No results for query: {query}", "INFO")
                                
                        except Exception as e:
                            task.log(f"Error searching '{query}': {e}", "ERROR")
                        
                        current_op += 1
                        if total_ops > 0:
                            task.set_progress(int(current_op / total_ops * 90))
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
                    if task.cancellation_event.is_set():
                        break
                    task.log(f"Arxiv Search: {query}")
                    try:
                        search = arxiv.Search(
                            query=query,
                            max_results=3,
                            sort_by=arxiv.SortCriterion.Relevance
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
                            db.flush()
                        
                        if not found_any:
                            task.log(f"No Arxiv results for: {query}", "INFO")
                    except Exception as e:
                        task.log(f"Error searching Arxiv for '{query}': {e}", "ERROR")
                    
                    current_op += 1
                    if total_ops > 0:
                        task.set_progress(int(current_op / total_ops * 90))
            except Exception as e:
                task.log(f"Arxiv system error: {e}", "ERROR")

        # 6. Selected Arxiv Ingestion (Specific user selection)
        if arxiv_selected:
            try:
                import pipmaster as pm
                if not pm.is_installed("arxiv"):
                    pm.install("arxiv")
                import requests
                
                for item in arxiv_selected:
                    if task.cancellation_event.is_set():
                        break
                    title = item.get('title', 'Unknown')
                    pdf_url = item.get('pdf_url', '')
                    summary = item.get('summary', '')
                    ingest_full = item.get('ingest_full', False)
                    task.log(f"Processing Arxiv Selection: {title}")
                    
                    if not ingest_full:
                        content = f"# {title}\n\n"
                        authors = item.get('authors', [])
                        content += f"**Authors:** {', '.join(authors) if isinstance(authors, list) else authors}\n"
                        content += f"**PDF:** {pdf_url}\n\n## Abstract\n{summary}"
                        _add_artefact(notebook, f"Arxiv Abstract: {title}", content)
                        db.flush()
                    else:
                        task.log(f"Downloading PDF: {pdf_url}")
                        try:
                            response = requests.get(pdf_url, stream=True, timeout=30)
                            if response.status_code == 200:
                                import tempfile
                                import os
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        if chunk:
                                            tf.write(chunk)
                                    tf_path = tf.name
                                
                                try:
                                    from docling.document_converter import DocumentConverter
                                    converter = DocumentConverter()
                                    res = converter.convert(tf_path)
                                    md = res.document.export_to_markdown()
                                    _add_artefact(notebook, f"Arxiv Paper: {title}", md)
                                    db.flush()
                                except ImportError:
                                    task.log("Docling not available, cannot convert PDF.", "WARNING")
                                except Exception as e:
                                    task.log(f"Conversion failed: {e}", "ERROR")
                                finally:
                                    try:
                                        if os.path.exists(tf_path):
                                            os.unlink(tf_path)
                                    except Exception:
                                        pass
                            else:
                                task.log(f"Failed to download PDF {pdf_url}", "WARNING")
                        except Exception as e:
                            task.log(f"Error processing PDF {pdf_url}: {e}", "ERROR")
                    
                    current_op += 1
                    if total_ops > 0:
                        task.set_progress(int(current_op / total_ops * 90))
            except Exception as e:
                task.log(f"Arxiv selected error: {e}", "ERROR")
        
        # CRITICAL FIX: Only call flag_modified if artefacts has been modified and exists in state
        # First, ensure we have a list (not None)
        if notebook.artefacts is None:
            notebook.artefacts = []
        
        # Flush to ensure SQLAlchemy tracks the state
        db.flush()
        
        # Now safely mark as modified if we have artefacts
        if notebook.artefacts:
            try:
                # Refresh to ensure the attribute is in the object state
                db.refresh(notebook, ['artefacts'])
                flag_modified(notebook, "artefacts")
            except Exception as e:
                # If flag_modified fails, just commit anyway - the data is there
                task.log(f"Note: Could not flag artefacts modified (non-critical): {e}", "INFO")
        
        db.commit()
        db.refresh(notebook)
        
        # Check for cancellation at key points
        if task.cancellation_event.is_set():
            task.log("Task cancelled by user. Saving partial notebook state.", "WARNING")
            with task.db_session_factory() as db2:
                handle_partial_notebook(db2, notebook_id, username)
            return
        
        # --- TASK CHAINING: Trigger Production Phase (ONLY if initial_prompt exists) ---
        if not task.cancellation_event.is_set() and initial_prompt and initial_prompt.strip():
            db.refresh(notebook)
            has_artefacts = len(notebook.artefacts) > 0 if notebook.artefacts else False
            
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
                    prompt=initial_prompt,
                    input_tab_ids=[],
                    action=action,
                    target_tab_id=target_tab_id,
                    selected_artefacts=[]
                )
            except Exception as e:
                task.log(f"Chained Production Task Failed: {str(e)}", "ERROR")
                trace_exception(e)
        else:
            task.log("No synthesis prompt provided. Notebook ready for manual interaction.", "INFO")

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
                # Initialize artefacts if None
                if notebook.artefacts is None:
                    notebook.artefacts = []
                    db.flush()
                    db.refresh(notebook, ['artefacts'])
                
                _add_artefact(notebook, f"File: {original_filename}", md)
                db.flush()
                
                # Safely flag modified
                try:
                    flag_modified(notebook, "artefacts")
                except Exception as e:
                    task.log(f"Note: Could not flag modified (non-critical): {e}", "INFO")
                
                db.commit()
        task.set_progress(100)
        task.log(f"File {original_filename} ingested.")
    except Exception as e:
        task.log(f"File conversion error: {e}", "ERROR")
        trace_exception(e)
