# backend/routers/discussion/artefacts.py
# Standard Library Imports
import base64
import io
import asyncio
import uuid
import requests
import re
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote
from typing import List, Optional, Dict, Any
import pipmaster as pm
import shutil
import tempfile
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Form, status, Body
from sqlalchemy.orm import Session
from ascii_colors import trace_exception

from backend.db import get_db
from backend.models import DiscussionInfo, UserAuthDetails, ArtefactInfo, ArtefactCreateManual, ArtefactUpdate, ExportContextRequest, LoadArtefactRequest, TaskInfo, UnloadArtefactRequest, UrlImportRequest, ArtefactAndDataZoneUpdateResponse
from backend.models.discussion import ArtefactUploadResponse
from backend.session import get_current_active_user, get_user_lollms_client
from backend.discussion import get_user_discussion
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request
from backend.task_manager import task_manager
from backend.tasks.artefact_tasks import _import_artefact_from_url_task
from backend.tasks.utils import _to_task_info
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request
# .msg handling
try:
    import extract_msg  # pip install extract-msg
except ImportError:
    extract_msg = None

# YouTube Transcript handling
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

from backend.db import get_db
from backend.db.models.user import User as DBUser
from pydantic import BaseModel

# --- New Models for Search/Select ---
class WikipediaSearchRequest(BaseModel):
    query: str

class WikipediaImportItem(BaseModel):
    title: str
    url: str

class WikipediaImportSelectedRequest(BaseModel):
    items: List[WikipediaImportItem]
    auto_load: bool = True

class ArxivSearchRequest(BaseModel):
    query: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = None
    max_results: int = 5

class ArxivImportItem(BaseModel):
    id: str
    title: str
    mode: str = "abstract" # "abstract" or "full"

class ArxivImportSelectedRequest(BaseModel):
    items: List[ArxivImportItem]
    auto_load: bool = True

class WebSearchRequest(BaseModel):
    query: str
    provider: str

class WikipediaImportRequest(BaseModel):
    query: str
    auto_load: bool = True

class YoutubeTranscriptImportRequest(BaseModel):
    video_url: str
    language: str = "en"
    auto_load: bool = True

class GithubImportRequest(BaseModel):
    url: str
    auto_load: bool = True

class GithubSearchRequest(BaseModel):
    query: str

class StackOverflowImportRequest(BaseModel):
    url: str
    auto_load: bool = True

class StackOverflowSearchRequest(BaseModel):
    query: str

class ArtefactRenameRequest(BaseModel):
    new_title: str

class ArtefactSquashRequest(BaseModel):
    keep_versions: Optional[List[int]] = None
    keep_last_n: Optional[int] = None
    target_version: Optional[int] = None

class ArtefactCleanupRequest(BaseModel):
    keep_count: int = 5
    min_age_hours: Optional[float] = None

class AudioExportRequest(BaseModel):
    title: str
    content: str

def _map_artefact_for_ui(art: dict, discussion_id: str = None) -> dict:
    """
    Standardizes Artefact metadata for the UI.
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

def build_artefacts_router(router: APIRouter):
    # Ensure Arxiv is available
    try:
        import arxiv
    except ImportError:
        pm.ensure_packages("arxiv")
        import arxiv

    @router.post("/{discussion_id}/artefacts/web/search", response_model=List[Dict[str, Any]])
    async def search_web(
        discussion_id: str,
        request: WebSearchRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        results =[]
        try:
            if request.provider == "duckduckgo":
                pm.ensure_packages("duckduckgo-search") # using duckduckgo-search to avoid ddgs rename warning if possible or handle it
                try:
                    from duckduckgo_search import DDGS
                except ImportError:
                    from ddgs import DDGS
                with DDGS() as ddgs:
                    raw_results =[r for r in ddgs.text(request.query, max_results=10)]
                    results =[{'title': r.get('title'), 'url': r.get('href'), 'snippet': r.get('body')} for r in raw_results]
            elif request.provider == "google":
                pm.ensure_packages("google-api-python-client")
                from googleapiclient.discovery import build as google_build
                
                db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
                if not db_user or not db_user.google_api_key or not db_user.google_cse_id:
                    raise HTTPException(status_code=400, detail="Google Search API is not configured in settings.")
                    
                service = google_build("customsearch", "v1", developerKey=db_user.google_api_key)
                res = service.cse().list(q=request.query, cx=db_user.google_cse_id, num=10).execute()
                items = res.get('items', [])
                results =[{'title': item.get('title'), 'url': item.get('link'), 'snippet': item.get('snippet')} for item in items]
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Search failed: {e}")
        
        return results

    # safe_store is needed for RAG callbacks
    @router.get("/{discussion_id}/artefacts", response_model=List[ArtefactInfo])
    async def list_discussion_artefacts(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)  
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        if not discussion:
            raise HTTPException(status_code=404, detail="Discussion not found")
        
        # Fetch raw artefacts from the manager and use centralized mapper
        raw_artefacts = discussion.list_artefacts()
        return [_map_artefact_for_ui(art, discussion_id) for art in raw_artefacts]

    @router.post("/{discussion_id}/artefacts", response_model=ArtefactUploadResponse)
    async def add_discussion_artefact(
        discussion_id: str,
        file: UploadFile = File(...),
        extract_images: bool = Form(True),
        pdf_mode: str = Form("text_images"),
        auto_load: bool = Form(True),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db) 
    ):
        """
        Imports a file into the discussion's artefact system using the library's unified import mechanism.
        """
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        if not discussion:
            raise HTTPException(status_code=404, detail="Discussion not found")

        # Map frontend modes to library modes
        # UI: text_and_embedded_images, text_only, embedded_images, render_pages, ocr
        mode_map = {
            "text_and_embedded_images": "text_images",
            "render_pages": "text_images",
            "text_only": "text",
            "embedded_images": "images_only",
            "ocr": "ocr"
        }

        import_mode = mode_map.get(pdf_mode, pdf_mode) # Default to literal if not in map

        # Save to temporary file so the library can read it via path
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = Path(tmp.name)

        try:
            # Delegate to library
            result = discussion.import_file(
                path=tmp_path,
                mode=import_mode,
                title=file.filename,
                activate=auto_load
            )

            discussion.commit()

            text_art = result.get("text_artefact")
            img_art = result.get("image_artefact")

            # Identify the primary artefact info to return
            primary_art = text_art or img_art

            if not primary_art:
                 raise RuntimeError("Library failed to create any artefacts from the provided file.")

            # Map for UI compatibility
            mapped_info = _map_artefact_for_ui(primary_art, discussion_id)

            all_images_info = discussion.get_discussion_images()

            return {
                "new_artefact_info": mapped_info,
                "discussion_images": [img['data'] for img in all_images_info],
                "active_discussion_images": [img['active'] for img in all_images_info]
            }
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to add artefact: {e}")

    @router.post("/{discussion_id}/artefacts/wikipedia/search", response_model=List[Dict[str, str]])
    async def search_wikipedia(
        discussion_id: str,
        request: WikipediaSearchRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        try:
            query = request.query.strip()
            lang = "en"
            
            # Check if it's a URL to just return that specific one
            if query.startswith("http://") or query.startswith("https://"):
                parsed = urlparse(query)
                if "wikipedia.org" in parsed.netloc:
                    title = unquote(parsed.path.split('/')[-1]).replace('_', ' ')
                    return [{"title": title, "url": query, "snippet": "Direct URL import."}]

            api_url = f"https://{lang}.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 10
            }
            headers = {
                "User-Agent": "LoLLMs/1.0 (https://github.com/ParisNeo/lollms; parisneo@gmail.com)"
            }
            resp = requests.get(api_url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            
            results = []
            for item in data.get("query", {}).get("search", []):
                results.append({
                    "title": item["title"],
                    "url": f"https://{lang}.wikipedia.org/wiki/{item['title'].replace(' ', '_')}",
                    "snippet": item["snippet"].replace('<span class="searchmatch">', '').replace('</span>', '')
                })
            return results
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Wikipedia search failed: {e}")

    @router.post("/{discussion_id}/artefacts/wikipedia/import", response_model=ArtefactAndDataZoneUpdateResponse)
    async def import_wikipedia_selected(
        discussion_id: str,
        request: WikipediaImportSelectedRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        
        try:
            for item in request.items:
                api_url = "https://en.wikipedia.org/w/api.php"
                params = {
                    "action": "query",
                    "prop": "extracts",
                    "titles": item.title,
                    "explaintext": 1,
                    "format": "json"
                }
                headers = {
                    "User-Agent": "LoLLMs/1.0 (https://github.com/ParisNeo/lollms; parisneo_ai@gmail.com)"
                }
                resp = requests.get(api_url, params=params, headers=headers)
                data = resp.json()
                pages = data.get("query", {}).get("pages", {})
                page_id = list(pages.keys())[0]
                if page_id != "-1":
                    content = pages[page_id].get("extract", "")
                    full_md = f"# {item.title}\nSource: {item.url}\n\n{content}"
                    # Use update_artefact to handle creation/versioning and activation in one go
                    discussion.update_artefact(
                        f"{item.title}.md", 
                        full_md, 
                        author=current_user.username,
                        active=request.auto_load
                    )
            
            discussion.commit()
            
            artefacts = discussion.list_artefacts()
            for artefact in artefacts:
                if isinstance(artefact.get('created_at'), datetime): artefact['created_at'] = artefact['created_at'].isoformat()
                if isinstance(artefact.get('updated_at'), datetime): artefact['updated_at'] = artefact['updated_at'].isoformat()

            lc = get_user_lollms_client(current_user.username)
            token_count = len(lc.tokenize(discussion.discussion_data_zone))
            all_images_info = discussion.get_discussion_images()

            # Pure Artefact Response: We no longer return or touch the discussion_data_zone text
            return {
                "artefacts": artefacts,
                "discussion_images": [img['data'] for img in all_images_info],
                "active_discussion_images": [img['active'] for img in all_images_info]
            }
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Wikipedia import failed: {e}")

    @router.post("/{discussion_id}/artefacts/arxiv/search", response_model=List[Dict[str, Any]])
    async def search_arxiv(
        discussion_id: str,
        request: ArxivSearchRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        import arxiv
        try:
            query_parts = []
            if request.query: query_parts.append(request.query)
            if request.author: query_parts.append(f"au:{request.author}")
            
            # Construct final query string
            query_str = " AND ".join(query_parts) if query_parts else "all:*"
            
            search = arxiv.Search(
                query=query_str,
                max_results=request.max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            results = []
            for r in search.results():
                # Filter by year client-side if requested
                if request.year and r.published.year != request.year:
                    continue
                    
                results.append({
                    "id": r.entry_id.split('/')[-1],
                    "title": r.title,
                    "authors": [a.name for a in r.authors],
                    "year": r.published.year,
                    "abstract": r.summary,
                    "pdf_url": r.pdf_url
                })
            return results
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Arxiv search failed: {e}")

    @router.post("/{discussion_id}/artefacts/arxiv/import", response_model=ArtefactAndDataZoneUpdateResponse)
    async def import_arxiv_selected(
        discussion_id: str,
        request: ArxivImportSelectedRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        import arxiv
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        
        try:
            for item in request.items:
                search = arxiv.Search(id_list=[item.id])
                paper = next(search.results())
                
                if item.mode == "full":
                    # Download PDF and extract
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
                        paper.download_pdf(filename=tf.name)
                        pdf_path = tf.name
                    
                    pdf_doc = fitz.open(pdf_path)
                    text = "\n".join([page.get_text() for page in pdf_doc])
                    pdf_doc.close()
                    os.unlink(pdf_path)
                    
                    content = f"# {paper.title}\nAuthors: {', '.join([a.name for a in paper.authors])}\nSource: {paper.entry_id}\n\n{text}"
                else:
                    content = f"# {paper.title} (Abstract)\nAuthors: {', '.join([a.name for a in paper.authors])}\nSource: {paper.entry_id}\n\n{paper.summary}"
                
                # Use update_artefact for unified management
                    discussion.update_artefact(
                    f"Arxiv_{item.id}.md", 
                    content, 
                    author=current_user.username, 
                    active=request.auto_load
                )
            
            discussion.commit()
            
            artefacts = discussion.list_artefacts()
            for artefact in artefacts:
                if isinstance(artefact.get('created_at'), datetime): artefact['created_at'] = artefact['created_at'].isoformat()
                if isinstance(artefact.get('updated_at'), datetime): artefact['updated_at'] = artefact['updated_at'].isoformat()

            lc = get_user_lollms_client(current_user.username)
            token_count = len(lc.tokenize(discussion.discussion_data_zone))
            all_images_info = discussion.get_discussion_images()

            # Pure Artefact Response: We no longer return or touch the discussion_data_zone text
            return {
                "artefacts": artefacts,
                "discussion_images": [img['data'] for img in all_images_info],
                "active_discussion_images": [img['active'] for img in all_images_info]
            }
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Arxiv import failed: {e}")

    @router.post("/{discussion_id}/artefacts/github/search", response_model=List[Dict[str, str]])
    async def search_github(
        discussion_id: str,
        request: GithubSearchRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        try:
            query = request.query.strip()
            if query.startswith("http://") or query.startswith("https://"):
                return[{"title": "Direct GitHub URL", "url": query, "snippet": "Direct import."}]
                
            api_url = f"https://api.github.com/search/issues?q={query}&per_page=10"
            r = requests.get(api_url, headers={"Accept": "application/vnd.github.v3+json"})
            r.raise_for_status()
            items = r.json().get('items', [])
            return[{
                "title": i.get('title', 'Unknown'), 
                "url": i.get('html_url', ''), 
                "snippet": f"[{i.get('state', 'unknown').upper()}] {i.get('repository_url', '').split('/')[-1]} | Comments: {i.get('comments', 0)}"
            } for i in items]
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"GitHub search failed: {e}")

    @router.post("/{discussion_id}/artefacts/github", response_model=ArtefactAndDataZoneUpdateResponse)
    async def import_github(
        discussion_id: str,
        request: GithubImportRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        
        url = request.url.strip()
        content = ""
        title = "Github_Import"
        
        try:
            if "github.com" in url:
                blob_match = re.match(r'https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)', url)
                issue_match = re.match(r'https?://github\.com/([^/]+)/([^/]+)/(issues|pull)/(\d+)', url)
                
                if blob_match:
                    user, repo, branch, filepath = blob_match.groups()
                    raw_url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{filepath}"
                    r = requests.get(raw_url)
                    r.raise_for_status()
                    
                    # Guess language for markdown fence
                    ext = filepath.split('.')[-1] if '.' in filepath else 'txt'
                    content = f"# File: {filepath}\nSource: {url}\n\n```{ext}\n{r.text}\n```"
                    title = f"GH_{filepath.split('/')[-1]}"
                    
                elif issue_match:
                    user, repo, type_, num = issue_match.groups()
                    api_url = f"https://api.github.com/repos/{user}/{repo}/issues/{num}"
                    r = requests.get(api_url, headers={"Accept": "application/vnd.github.v3+json"})
                    r.raise_for_status()
                    data = r.json()
                    
                    title_str = data.get('title', f'{type_.capitalize()} #{num}')
                    body = data.get('body', '')
                    state = data.get('state', 'unknown')
                    content = f"# [{state.upper()}] {title_str}\nSource: {url}\n\n{body}"
                    
                    comments_url = data.get('comments_url')
                    if comments_url:
                        rc = requests.get(comments_url, headers={"Accept": "application/vnd.github.v3+json"})
                        if rc.status_code == 200:
                            comments = rc.json()
                            for c in comments:
                                content += f"\n\n---\n**{c.get('user',{}).get('login','User')}** commented:\n{c.get('body','')}"
                    title = f"GH_{type_}_{num}"
                    
                else:
                    raise HTTPException(status_code=400, detail="Only GitHub file blobs, issues, or pull requests are currently supported.")
                    
            elif "raw.githubusercontent.com" in url:
                r = requests.get(url)
                r.raise_for_status()
                filepath = url.split('/')[-1]
                ext = filepath.split('.')[-1] if '.' in filepath else 'txt'
                content = f"# File: {filepath}\nSource: {url}\n\n```{ext}\n{r.text}\n```"
                title = f"GH_Raw_{filepath}"
            else:
                 raise HTTPException(status_code=400, detail="Not a valid GitHub URL.")

            # Ensure safe filename
            safe_title = re.sub(r'[^A-Za-z0-9_.-]', '_', title) + ".md"
            
            # Use update_artefact for unified management
            discussion.update_artefact(
                safe_title, 
                content, 
                author=current_user.username, 
                active=request.auto_load
            )
            
            discussion.commit()
            
            artefacts = discussion.list_artefacts()
            for artefact in artefacts:
                if isinstance(artefact.get('created_at'), datetime): artefact['created_at'] = artefact['created_at'].isoformat()
                if isinstance(artefact.get('updated_at'), datetime): artefact['updated_at'] = artefact['updated_at'].isoformat()

            lc = get_user_lollms_client(current_user.username)
            token_count = len(lc.tokenize(discussion.discussion_data_zone))
            all_images_info = discussion.get_discussion_images()

            # Pure Artefact Response: We no longer return or touch the discussion_data_zone text
            return {
                "artefacts": artefacts,
                "discussion_images": [img['data'] for img in all_images_info],
                "active_discussion_images": [img['active'] for img in all_images_info]
            }
            
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"GitHub import failed: {e}")

    @router.post("/{discussion_id}/artefacts/stackoverflow/search", response_model=List[Dict[str, str]])
    async def search_stackoverflow(
        discussion_id: str,
        request: StackOverflowSearchRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        try:
            query = request.query.strip()
            if query.startswith("http://") or query.startswith("https://"):
                return[{"title": "Direct StackOverflow URL", "url": query, "snippet": "Direct import."}]

            api_url = f"https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=relevance&q={query}&site=stackoverflow&pagesize=10"
            r = requests.get(api_url)
            r.raise_for_status()
            items = r.json().get('items', [])
            return[{
                "title": i.get('title', 'Unknown'), 
                "url": i.get('link', ''), 
                "snippet": f"Score: {i.get('score', 0)} | Answers: {i.get('answer_count', 0)} | Tags: {', '.join(i.get('tags', []))}"
            } for i in items]
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"StackOverflow search failed: {e}")

    @router.post("/{discussion_id}/artefacts/stackoverflow", response_model=ArtefactAndDataZoneUpdateResponse)
    async def import_stackoverflow(
        discussion_id: str,
        request: StackOverflowImportRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        pm.ensure_packages("markdownify")
        from markdownify import markdownify as md
        
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        url = request.url.strip()
        
        q_match = re.search(r'stackoverflow\.com/questions/(\d+)', url)
        if not q_match:
             raise HTTPException(status_code=400, detail="Invalid StackOverflow question URL. Must contain /questions/ID")
        
        q_id = q_match.group(1)
        
        try:
            # Fetch question
            api_q = f"https://api.stackexchange.com/2.3/questions/{q_id}?site=stackoverflow&filter=withbody"
            r_q = requests.get(api_q)
            r_q.raise_for_status()
            q_data = r_q.json().get('items',[])
            if not q_data:
                raise HTTPException(status_code=404, detail="Question not found on StackOverflow.")
            
            question = q_data[0]
            q_title = question.get('title', 'StackOverflow Question')
            q_body_html = question.get('body', '')
            q_body_md = md(q_body_html).strip()

            content = f"# {q_title}\nSource: {url}\n\n**Question (Score: {question.get('score', 0)}):**\n\n{q_body_md}\n\n---\n"

            # Fetch top 3 answers
            api_a = f"https://api.stackexchange.com/2.3/questions/{q_id}/answers?site=stackoverflow&order=desc&sort=votes&filter=withbody"
            r_a = requests.get(api_a)
            if r_a.status_code == 200:
                a_data = r_a.json().get('items',[])
                for i, ans in enumerate(a_data[:3]):
                    is_accepted = "✅ ACCEPTED " if ans.get('is_accepted') else ""
                    a_body_md = md(ans.get('body', '')).strip()
                    content += f"\n### {is_accepted}Answer {i+1} (Score: {ans.get('score', 0)})\n\n{a_body_md}\n\n---\n"
                
            title = f"SO_{q_id}.md"
            
            # Use update_artefact for unified management
            discussion.update_artefact(
                title, 
                content, 
                author=current_user.username, 
                active=request.auto_load
            )
            
            discussion.commit()
            
            artefacts = discussion.list_artefacts()
            for artefact in artefacts:
                if isinstance(artefact.get('created_at'), datetime): artefact['created_at'] = artefact['created_at'].isoformat()
                if isinstance(artefact.get('updated_at'), datetime): artefact['updated_at'] = artefact['updated_at'].isoformat()

            lc = get_user_lollms_client(current_user.username)
            token_count = len(lc.tokenize(discussion.discussion_data_zone))
            all_images_info = discussion.get_discussion_images()

            # Pure Artefact Response: We no longer return or touch the discussion_data_zone text
            return {
                "artefacts": artefacts,
                "discussion_images": [img['data'] for img in all_images_info],
                "active_discussion_images": [img['active'] for img in all_images_info]
            }

        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"StackOverflow import failed: {e}")

    @router.post("/{discussion_id}/artefacts/youtube", response_model=ArtefactAndDataZoneUpdateResponse)
    async def import_youtube_transcript(
        discussion_id: str,
        request: YoutubeTranscriptImportRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        if YouTubeTranscriptApi is None:
            raise HTTPException(status_code=501, detail="youtube_transcript_api is not installed on the server.")

        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        
        # 1. Improved Video ID Extraction
        video_id = None
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', # v=... or /...
            r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})', # youtu.be/ID
            r'(?:embed\/)([0-9A-Za-z_-]{11})' # embed/ID
        ]
        
        for p in patterns:
             match = re.search(p, request.video_url)
             if match:
                 video_id = match.group(1)
                 break
        
        # Fallback: check if the whole string is an ID
        if not video_id:
             if len(request.video_url) == 11 and re.match(r'^[0-9A-Za-z_-]{11}$', request.video_url):
                 video_id = request.video_url
        
        if not video_id:
            raise HTTPException(status_code=400, detail="Could not extract a valid YouTube Video ID from the provided URL.")

        try:
            # 2. Retrieve Transcript List
            try:
                yvt = YouTubeTranscriptApi()
                transcript_list_obj = yvt.list(video_id)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to retrieve transcript list. Video may not have captions or is restricted. Error: {e}")

            target_transcript = None
            requested_lang = request.language.lower().strip() if request.language else None

            # 3. Smart Selection Logic
            if requested_lang:
                # Try finding exact match
                try:
                    target_transcript = transcript_list_obj.find_transcript([requested_lang])
                except:
                    # Try finding a translation
                    try:
                        # Translate the first available transcript
                        first_available = next(iter(transcript_list_obj))
                        if first_available.is_translatable:
                            target_transcript = first_available.translate(requested_lang)
                    except:
                        pass # Translation failed or not available
            
            # If no specific language requested OR specific lookup failed
            if not target_transcript:
                # Priority: English -> First Available
                try:
                    target_transcript = transcript_list_obj.find_generated_transcript(['en'])
                except:
                    pass
                
                if not target_transcript:
                    try:
                        target_transcript = transcript_list_obj.find_manually_created_transcript(['en'])
                    except:
                        pass
                
                if not target_transcript:
                    try:
                        target_transcript = next(iter(transcript_list_obj))
                    except:
                        pass

            if not target_transcript:
                raise HTTPException(status_code=400, detail="No suitable transcript found.")

            # 4. Fetch
            transcript_data = target_transcript.fetch()

            # 5. Format
            lines = []
            for entry in transcript_data.snippets:
                start = int(entry.start)
                minutes = start // 60
                seconds = start % 60
                text = entry.text
                lines.append(f"[{minutes:02d}:{seconds:02d}] {text}")
            
            lang_label = target_transcript.language if hasattr(target_transcript, 'language') else (requested_lang or 'unknown')
            full_content = f"# YouTube Transcript ({lang_label})\nSource: {request.video_url}\n\n" + "\n".join(lines)
            
            # 6. Save using the internal manager
            artefact_name = f"Youtube_Transcript_{video_id}.md"
            latest = discussion.artefacts.get(artefact_name)
            if latest:
                discussion.update_artefact(
                    artefact_name,
                    full_content,
                    author=current_user.username,
                    active=request.auto_load
                )
            else:
                discussion.add_artefact(
                    artefact_name,
                    full_content,
                    author=current_user.username,
                    active=request.auto_load
                )

            # Activation is already handled by the 'active' parameter logic (default is True in add_artefact)
            
            discussion.commit()
            
            artefacts = discussion.list_artefacts()
            for artefact in artefacts:
                if isinstance(artefact.get('created_at'), datetime): artefact['created_at'] = artefact['created_at'].isoformat()
                if isinstance(artefact.get('updated_at'), datetime): artefact['updated_at'] = artefact['updated_at'].isoformat()

            lc = get_user_lollms_client(current_user.username)
            token_count = len(lc.tokenize(discussion.discussion_data_zone))
            all_images_info = discussion.get_discussion_images()

            # Pure Artefact Response: We no longer return or touch the discussion_data_zone text
            return {
                "artefacts": artefacts,
                "discussion_images": [img['data'] for img in all_images_info],
                "active_discussion_images": [img['active'] for img in all_images_info]
            }

        except HTTPException as he:
            raise he
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to process YouTube transcript: {str(e)}")

    class RenameArtefactRequest(BaseModel):
        old_title: str
        new_title: str
        new_type: Optional[str] = None

    @router.put("/{discussion_id}/artefacts/rename", status_code=status.HTTP_200_OK)
    async def rename_discussion_artefact(
        discussion_id: str,
        payload: RenameArtefactRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        
        # 1. Type Auto-Detection from extension
        ext = Path(payload.new_title).suffix.lower()
        auto_type = payload.new_type
        
        if not auto_type:
            CODE_EXTS = {".py", ".js", ".ts", ".html", ".css", ".c", ".cpp", ".h", ".cs", ".java", ".sh", ".sql", ".vhd", ".v", ".rb", ".php", ".go", ".rs", ".swift", ".kt"}
            if ext in CODE_EXTS:
                auto_type = "code"
            elif ext in {".md", ".txt", ".pdf", ".docx", ".xlsx", ".pptx"}:
                auto_type = "document"

        try:
            # We use the library's internal artefacts manager to perform the rename
            # This ensures all versions associated with the old title are migrated.
            discussion.artefacts.rename(
                old_title=payload.old_title, 
                new_title=payload.new_title, 
                new_type=auto_type
            )
            discussion.commit()
            return {"message": f"Artefact renamed to '{payload.new_title}'", "detected_type": auto_type}
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/{discussion_id}/artefacts/{artefact_title}/create_discussion_with_version", response_model=DiscussionInfo)
    async def create_discussion_from_artefact_version(
        discussion_id: str,
        artefact_title: str,
        version: int = Query(...),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Creates a brand new discussion and pre-loads it with a specific version 
        of an artefact from an existing discussion.
        """
        from urllib.parse import unquote
        title = unquote(artefact_title)

        # 1. Get the source discussion and artefact
        source_discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        source_art = source_discussion.get_artefact(title=title, version=version)

        if not source_art:
            raise HTTPException(status_code=404, detail="Source artefact version not found.")

        # 2. Create the target discussion
        new_discussion_id = str(uuid.uuid4())
        target_discussion = get_user_discussion(current_user.username, new_discussion_id, create_if_missing=True)

        # 3. Copy the artefact content and metadata
        # We use add_artefact to create Version 1 in the new discussion using source data
        target_discussion.add_artefact(
            title=title,
            content=source_art.get('content', ''),
            images=source_art.get('images', []),
            author=current_user.username,
            active=True, # Auto-load it into context
            artefact_type=source_art.get('artefact_type', 'document')
        )

        target_discussion.set_metadata_item('title', f"Chat about {title}")
        target_discussion.commit()

        metadata = target_discussion.metadata or {}
        return DiscussionInfo(
            id=new_discussion_id,
            title=metadata.get('title'),
            is_starred=False,
            active_tools=[],
            created_at=target_discussion.created_at,
            last_activity_at=target_discussion.updated_at
        )

    @router.post("/{discussion_id}/artefacts/manual", response_model=ArtefactAndDataZoneUpdateResponse, status_code=status.HTTP_201_CREATED)
    async def create_manual_artefact(
        discussion_id: str,
        payload: ArtefactCreateManual,
        artefact_type: str = Query(None),
        auto_load: bool = Query(True),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        
        try:
            # Type resolution logic
            raw_type = (artefact_type or "").lower()
            if "note" in raw_type: final_type = "note"
            elif "skill" in raw_type: final_type = "skill"
            else:
                ext = payload.title.split('.')[-1].lower() if '.' in payload.title else ""
                final_type = "code" if ext in ['py', 'js', 'ts', 'html', 'css', 'sql', 'cpp', 'c', 'sh'] else "document"

            # Use add_artefact for initial manual creation
            artefact_info = discussion.add_artefact(
                payload.title, 
                payload.content, 
                images=payload.images_b64, 
                author=current_user.username,
                active=auto_load,
                artefact_type=final_type
            )
            
            discussion.commit()
            
            # Fetch latest synchronized state
            raw_artefacts = discussion.list_artefacts()
            all_images_info = discussion.get_discussion_images()

            return {
                "artefacts": [_map_artefact_for_ui(art, discussion_id) for art in raw_artefacts],
                "discussion_images": [img['data'] for img in all_images_info],
                "active_discussion_images": [img['active'] for img in all_images_info]
            }
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to create artefact: {e}")

    @router.put("/{discussion_id}/artefacts/{artefact_title}", response_model=ArtefactInfo)
    async def update_manual_artefact(
        discussion_id: str,
        artefact_title: str,
        payload: ArtefactUpdate,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')

        try:
            # Use the library's internal manager for correct version bumping and state management.
            # We map UI parameters to the library's ArtefactManager.update signature.
            artefact_info = discussion.artefacts.update(
                title=artefact_title, 
                new_content=payload.new_content, 
                new_type=payload.artefact_type,
                new_images=payload.kept_images_b64 + payload.new_images_b64,
                bump_version=not payload.update_in_place,
                active=True # UI updates generally imply an active document
            )
            discussion.commit()

            if isinstance(artefact_info.get('created_at'), datetime):
                artefact_info['created_at'] = artefact_info['created_at'].isoformat()
            if isinstance(artefact_info.get('updated_at'), datetime):
                artefact_info['updated_at'] = artefact_info['updated_at'].isoformat()
            
            return artefact_info

        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred while updating the artefact: {e}")

    @router.post("/{discussion_id}/artefacts/export-context", response_model=ArtefactInfo)
    async def export_context_as_artefact(
        discussion_id: str,
        request: ExportContextRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        content = discussion.discussion_data_zone
        if not content or not content.strip():
            raise HTTPException(status_code=400, detail="Data zone is empty.")
        try:
            # Use update_artefact for consistent versioned storage of the context snapshot
            artefact_info = discussion.update_artefact(
                request.title, 
                content, 
                author=current_user.username,
                active=True,
                artefact_type="document"
            )
            discussion.commit()
            return _map_artefact_for_ui(artefact_info, discussion_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create artefact from context: {e}")

    @router.get("/{discussion_id}/artefacts/{artefact_title:path}/content")
    async def get_discussion_artefact_content(
        discussion_id: str,
        artefact_title: str,
        version: Optional[int] = Query(None),
        strategy: str = Query("raw"),  # 'raw' or 'formatted'
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Get the raw content of a specific artefact version.
        Path-style route to avoid conflicts with SPA catch-all.
        """
        from urllib.parse import unquote
        
        discussion, owner_username, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        
        # URL decode the title (handles spaces and special chars)
        decoded_title = unquote(artefact_title)
        
        artefact = discussion.get_artefact(title=decoded_title, version=version)
        if not artefact:
            raise HTTPException(status_code=404, detail=f"Artefact '{decoded_title}' not found")

        # Return raw content as plain text for the workspace editor
        content = artefact.get('content', '')
        
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=content,
            media_type="text/plain; charset=utf-8",
            headers={"X-Artefact-Title": decoded_title, "X-Artefact-Version": str(artefact.get('version', 1))}
        )

    # Keep the old endpoint for backward compatibility (returns JSON with metadata)
    @router.get("/{discussion_id}/artefact", response_model=ArtefactInfo)
    async def get_discussion_artefact_info(
        discussion_id: str,
        artefact_title: str = Query(...),
        version: Optional[int] = Query(None),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Get artefact metadata (JSON). Use /content endpoint for raw content.
        """
        discussion, owner_username, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        artefact = discussion.get_artefact(title=artefact_title, version=version)

        if not artefact:
            raise HTTPException(status_code=404, detail="Artefact not found")

        if isinstance(artefact.get('created_at'), datetime):
            artefact['created_at'] = artefact['created_at'].isoformat()
        if isinstance(artefact.get('updated_at'), datetime):
            artefact['updated_at'] = artefact['updated_at'].isoformat()
        return artefact

    @router.delete("/{discussion_id}/artefact", status_code=status.HTTP_200_OK)
    async def delete_discussion_artefact(
        discussion_id: str,
        artefact_title: str = Query(...),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        from urllib.parse import unquote
        title = unquote(artefact_title) # Ensure URL encoded titles match correctly
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            # Check if it exists first
            if not discussion.get_artefact(title=title):
                raise HTTPException(status_code=404, detail="Artefact not found.")
                
            discussion.remove_artefact(title=title)
            discussion.commit()
            return {"message": f"Artefact '{title}' deleted."}
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/{discussion_id}/artefacts/revert", status_code=status.HTTP_200_OK)
    async def revert_discussion_artefact(
        discussion_id: str,
        title: str = Body(..., embed=True),
        version: int = Body(..., embed=True),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            discussion.artefacts.revert(title, target_version=version)
            discussion.commit()
            return {"message": f"Reverted to version {version}"}
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Revert failed: {e}")

    @router.get("/{discussion_id}/artefacts/{artefact_title:path}/history")
    async def get_artefact_history(
        discussion_id: str,
        artefact_title: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        history = discussion.artefacts.get_version_history(unquote(artefact_title))
        return history

    @router.post("/{discussion_id}/artefacts/{artefact_title:path}/squash")
    async def squash_artefact_versions(
        discussion_id: str,
        artefact_title: str,
        payload: ArtefactSquashRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            result = discussion.artefacts.squash_versions(
                unquote(artefact_title),
                keep_versions=payload.keep_versions,
                keep_last_n=payload.keep_last_n,
                target_version=payload.target_version
            )
            discussion.commit()
            return result
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/{discussion_id}/artefacts/{artefact_title:path}/cleanup")
    async def cleanup_artefact_versions(
        discussion_id: str,
        artefact_title: str,
        payload: ArtefactCleanupRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        result = discussion.artefacts.cleanup_old_versions(
            unquote(artefact_title),
            keep_count=payload.keep_count,
            min_age_hours=payload.min_age_hours
        )
        discussion.commit()
        return result

    @router.delete("/{discussion_id}/artefacts/{artefact_title:path}/version/{version}")
    async def delete_artefact_version(
        discussion_id: str,
        artefact_title: str,
        version: int,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        removed = discussion.artefacts.remove(unquote(artefact_title), version=version)
        if removed == 0:
            raise HTTPException(status_code=404, detail="Version not found.")
        discussion.commit()
        return {"message": f"Version {version} deleted."}

    @router.post("/{discussion_id}/artefacts/load-all-to-context", response_model=ArtefactAndDataZoneUpdateResponse)
    async def load_all_artefacts_to_data_zone(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            # The library manages the context layer. We just activate everything.
            all_artefacts_infos = discussion.list_artefacts()
            
            for art_info in all_artefacts_infos:
                discussion.artefacts.activate(art_info['title'], version=art_info['version'])

            discussion.commit()
            
            raw_artefacts = discussion.list_artefacts()
            artefacts = [_map_artefact_for_ui(art) for art in raw_artefacts]

            lc = get_user_lollms_client(current_user.username)
            token_count = len(lc.tokenize(discussion.discussion_data_zone))
            
            all_images_info = discussion.get_discussion_images()
            # Pure Artefact Response: We no longer return or touch the discussion_data_zone text
            return {
                "artefacts": artefacts,
                "discussion_images": [img['data'] for img in all_images_info],
                "active_discussion_images": [img['active'] for img in all_images_info]
            }
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load all artefacts: {e}")        

    @router.post("/{discussion_id}/artefacts/load-to-context", response_model=ArtefactAndDataZoneUpdateResponse)
    async def load_artefact_to_data_zone(
        discussion_id: str,
        request: LoadArtefactRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            # We only update the library metadata. The library handles 
            # context injection natively during chat() without modifying the data_zone string.
            discussion.artefacts.activate(request.title, version=request.version)
            discussion.commit()
            
            raw_artefacts = discussion.list_artefacts()
            artefacts = [_map_artefact_for_ui(art) for art in raw_artefacts]
            
            lc = get_user_lollms_client(current_user.username)
            token_count = len(lc.tokenize(discussion.discussion_data_zone))

            all_images_info = discussion.get_discussion_images()
            # Pure Artefact Response: We no longer return or touch the discussion_data_zone text
            return {
                "artefacts": artefacts,
                "discussion_images": [img['data'] for img in all_images_info],
                "active_discussion_images": [img['active'] for img in all_images_info]
            }
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to load artefact: {e}")

    @router.post("/{discussion_id}/artefacts/unload-from-context", response_model=ArtefactAndDataZoneUpdateResponse)
    async def unload_artefact_from_data_zone(
        discussion_id: str,
        request: UnloadArtefactRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            # Deactivate in the library metadata only.
            discussion.artefacts.deactivate(request.title, version=request.version)
            discussion.commit()
            
            raw_artefacts = discussion.list_artefacts()
            artefacts = [_map_artefact_for_ui(art) for art in raw_artefacts]

            lc = get_user_lollms_client(current_user.username)
            token_count = len(lc.tokenize(discussion.discussion_data_zone))

            all_images_info = discussion.get_discussion_images()
            # Pure Artefact Response: We no longer return or touch the discussion_data_zone text
            return {
                "artefacts": artefacts,
                "discussion_images": [img['data'] for img in all_images_info],
                "active_discussion_images": [img['active'] for img in all_images_info]
            }
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to unload artefact: {e}")

    @router.post("/{discussion_id}/artefacts/import_url", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
    async def import_artefact_from_url(
        discussion_id: str,
        request: UrlImportRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        _, owner_username, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        task = task_manager.submit_task(
            name=f"Importing artefact from URL: {request.url}",
            target=_import_artefact_from_url_task,
            args=(owner_username, discussion_id, request.url, request.depth, request.process_with_ai),
            description=f"Scraping content (depth {request.depth}) and saving as artefact.",
            owner_username=current_user.username
        )
        return task

    @router.post("/{discussion_id}/artefacts/export_audio", response_model=TaskInfo, status_code=202)
    async def export_artefact_as_audio(
        discussion_id: str,
        payload: AudioExportRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user)
    ):
        from backend.tasks.artefact_tasks import _export_audio_task
        task = task_manager.submit_task(
            name=f"Audio Export: {payload.title}",
            target=_export_audio_task,
            args=(current_user.username, payload.title, payload.content),
            description="Generating high-fidelity audio from document text.",
            owner_username=current_user.username
        )
        return task

    @router.put("/{discussion_id}/artefacts/{artefact_title}/rename")
    async def rename_discussion_artefact(
        discussion_id: str,
        artefact_title: str,
        payload: ArtefactRenameRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        from urllib.parse import unquote
        old_title = unquote(artefact_title)
        new_title = payload.new_title.strip()
        
        if not new_title:
            raise HTTPException(status_code=400, detail="New title cannot be empty.")
            
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        
        # Prevent collisions
        if discussion.get_artefact(title=new_title):
             raise HTTPException(status_code=400, detail=f"An artefact named '{new_title}' already exists.")

        try:
            if 'artefacts' in discussion.metadata:
                # 1. Update versioned artefacts metadata
                found = False
                for art in discussion.metadata['artefacts']:
                    if art['title'] == old_title:
                        art['title'] = new_title
                        found = True
                
                if not found:
                    raise HTTPException(status_code=404, detail="Artefact not found.")
                
                # 2. Update source field in global discussion images (for vision anchors)
                if hasattr(discussion, 'images') and discussion.images:
                    for img in discussion.images:
                        if img.get('source') == old_title:
                            img['source'] = new_title

                # 3. Update visual references in message content strings
                all_msgs = discussion.db_manager.get_all_messages(discussion_id)
                old_anchor = f'id="{old_title}::'
                new_anchor = f'id="{new_title}::'
                for m in all_msgs:
                    if old_anchor in m.content:
                        m.content = m.content.replace(old_anchor, new_anchor)
                        discussion.db_manager.update_message(m)

                # Persist changes
                discussion.set_metadata_item('artefacts', discussion.metadata['artefacts'])
                discussion.commit()
                return {"message": "Artefact renamed successfully.", "new_title": new_title}
            else:
                raise HTTPException(status_code=404, detail="No artefacts found.")
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=str(e))
