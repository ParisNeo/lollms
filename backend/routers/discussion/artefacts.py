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
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Form, status, Body, Response
from sqlalchemy.orm import Session
from ascii_colors import trace_exception

from backend.db import get_db
from backend.models import DiscussionInfo, UserAuthDetails, ArtefactInfo, ArtefactCreateManual, ArtefactUpdate, ExportContextRequest, LoadArtefactRequest, TaskInfo, UnloadArtefactRequest, UrlImportRequest, ArtefactAndDataZoneUpdateResponse
from backend.models.discussion import ArtefactUploadResponse
from backend.session import get_current_active_user, get_user_lollms_client
from backend.discussion import get_user_discussion
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request
from backend.task_manager import task_manager
from backend.tasks.artefact_tasks import _import_artefact_from_url_task, _import_artefact_task
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
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        try:
            results = discussion.search_web(request.query, request.provider)
            return results
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Search failed: {e}")

    @router.delete("/{discussion_id}/artefacts/{artefact_title:path}/images/{index}")
    async def delete_binary_image_endpoint(
        discussion_id: str,
        artefact_title: str,
        index: int,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """Removes a specific sub-image of an artefact by index and updates text content."""
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')

        from urllib.parse import unquote
        decoded_title = unquote(artefact_title)

        # Resolve title case-insensitively
        try:
            for art in discussion.list_artefacts():
                if art.get("title", "").lower() == decoded_title.lower():
                    decoded_title = art["title"]
                    break
        except Exception:
            pass

        try:
            # 1. Retrieve the existing image list
            associated_images = discussion.artefacts.get_associated_images(decoded_title)
            if associated_images:
                sorted_images = sorted(associated_images, key=lambda x: x.get('index', 0))
                images = [img['data'] for img in sorted_images]
            else:
                comp_art = discussion.get_artefact(title=f"{decoded_title}::images")
                if comp_art and 'images' in comp_art:
                    images = comp_art['images']
                else:
                    images = []

            if not images or index < 0 or index >= len(images):
                raise HTTPException(status_code=404, detail="Image index out of range")

            # 2. Re-assign the targeted index to an empty string to prevent index shifting
            images[index] = ""

            # 3. Update the artefact's images list in place
            latest_art = discussion.get_artefact(title=decoded_title)
            existing_content = latest_art.get('content', '') if latest_art else ''
            existing_type = latest_art.get('artefact_type', 'document') if latest_art else 'document'

            # 4. Remove the specific tag from the content to prevent rendering broken frames
            escaped_title = re.escape(decoded_title)
            tag_pattern = re.compile(rf'<artefact_image\s+id=["\']{escaped_title}::{index}["\']\s*/?>', re.IGNORECASE)
            updated_content = tag_pattern.sub("", existing_content)

            discussion.artefacts.update(
                title=decoded_title,
                new_content=updated_content,
                new_type=existing_type,
                new_images=images,
                bump_version=False,
                active=True
            )

            # 5. Synchronize the companion ::images artefact if it exists
            comp_title = f"{decoded_title}::images"
            if discussion.get_artefact(title=comp_title):
                discussion.update_artefact(
                    title=comp_title,
                    content="",
                    images=images,
                    author=current_user.username
                )

            discussion.commit()
            return {"message": "Image deleted successfully", "remaining_count": len([img for img in images if img])}

        except HTTPException as he:
            raise he
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=str(e))


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

    @router.post("/{discussion_id}/artefacts", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
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
        Launches a background task to import a file into the discussion's artefact system
        using the library's integrated import mechanism with real-time progress updates.
        """
        _, owner_username, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')

        # Save to a temporary file under user's upload folder so the background worker can read it
        from backend.session import get_user_temp_uploads_path
        temp_dir = get_user_temp_uploads_path(current_user.username)
        temp_id = str(uuid.uuid4())
        suffix = Path(file.filename).suffix if file.filename else '.tmp'
        temp_file_path = temp_dir / f"{temp_id}_import{suffix}"

        try:
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to write uploaded file to temp disk: {e}")

        # Submit background task
        task = task_manager.submit_task(
            name=f"Importing document: {file.filename or 'unnamed'}",
            target=_import_artefact_task,
            args=(owner_username, discussion_id, str(temp_file_path.resolve()), file.filename or 'unnamed', pdf_mode, auto_load),
            description=f"AI is ingesting '{file.filename or 'unnamed'}' (mode: {pdf_mode}) and building workspace context...",
            owner_username=current_user.username
        )
        return task

    @router.post("/{discussion_id}/artefacts/wikipedia/search", response_model=List[Dict[str, str]])
    async def search_wikipedia(
        discussion_id: str,
        request: WikipediaSearchRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        try:
            results = discussion.search_wikipedia(request.query)
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
                discussion.import_wikipedia(item.title, item.url, request.auto_load)

            discussion.commit()

            artefacts = discussion.list_artefacts()
            for artefact in artefacts:
                if isinstance(artefact.get('created_at'), datetime): artefact['created_at'] = artefact['created_at'].isoformat()
                if isinstance(artefact.get('updated_at'), datetime): artefact['updated_at'] = artefact['updated_at'].isoformat()

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
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        try:
            results = discussion.search_arxiv(request.query, request.author, request.year, request.max_results)
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
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')

        try:
            for item in request.items:
                discussion.import_arxiv(item.id, item.mode, request.auto_load)

            discussion.commit()

            artefacts = discussion.list_artefacts()
            for artefact in artefacts:
                if isinstance(artefact.get('created_at'), datetime): artefact['created_at'] = artefact['created_at'].isoformat()
                if isinstance(artefact.get('updated_at'), datetime): artefact['updated_at'] = artefact['updated_at'].isoformat()

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
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        try:
            results = discussion.search_github(request.query)
            return results
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
        try:
            art = discussion.import_github(request.url, request.auto_load)
            if not art:
                raise HTTPException(status_code=400, detail="Failed to import GitHub content.")

            discussion.commit()

            artefacts = discussion.list_artefacts()
            for artefact in artefacts:
                if isinstance(artefact.get('created_at'), datetime): artefact['created_at'] = artefact['created_at'].isoformat()
                if isinstance(artefact.get('updated_at'), datetime): artefact['updated_at'] = artefact['updated_at'].isoformat()

            all_images_info = discussion.get_discussion_images()

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
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        try:
            results = discussion.search_stackoverflow(request.query)
            return results
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
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            art = discussion.import_stackoverflow(request.url, request.auto_load)
            if not art:
                raise HTTPException(status_code=400, detail="Failed to import StackOverflow content.")

            discussion.commit()

            artefacts = discussion.list_artefacts()
            for artefact in artefacts:
                if isinstance(artefact.get('created_at'), datetime): artefact['created_at'] = artefact['created_at'].isoformat()
                if isinstance(artefact.get('updated_at'), datetime): artefact['updated_at'] = artefact['updated_at'].isoformat()

            all_images_info = discussion.get_discussion_images()

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
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            art = discussion.import_youtube_transcript(request.video_url, request.language, request.auto_load)
            if not art:
                raise HTTPException(status_code=400, detail="Failed to import YouTube video transcript.")

            discussion.commit()

            artefacts = discussion.list_artefacts()
            for artefact in artefacts:
                if isinstance(artefact.get('created_at'), datetime): artefact['created_at'] = artefact['created_at'].isoformat()
                if isinstance(artefact.get('updated_at'), datetime): artefact['updated_at'] = artefact['updated_at'].isoformat()

            all_images_info = discussion.get_discussion_images()

            return {
                "artefacts": artefacts,
                "discussion_images": [img['data'] for img in all_images_info],
                "active_discussion_images": [img['active'] for img in all_images_info]
            }
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to process YouTube transcript: {str(e)}")

    class RenameArtefactRequest(BaseModel):
        old_title: str
        new_title: str
        new_type: Optional[str] = None

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

        from urllib.parse import unquote
        decoded_title = unquote(artefact_title)

        artefact = discussion.get_artefact(title=decoded_title, version=version)

        if not artefact:
            raise HTTPException(status_code=404, detail="Artefact not found")

        try:
            # 1. Try to query the integrated associated images lists from the discussion manager
            associated_images = discussion.artefacts.get_associated_images(decoded_title)
            if associated_images:
                sorted_images = sorted(associated_images, key=lambda x: x.get('index', 0))
                artefact['images'] = [img['data'] for img in sorted_images]
            else:
                # 2. Fallback: Fetch companion images artefact directly
                comp_art = discussion.get_artefact(title=f"{decoded_title}::images")
                if comp_art and 'images' in comp_art:
                    artefact['images'] = comp_art['images']
                else:
                    # 3. Fallback: Check if the main-title or metadata itself has the images
                    if 'images' in artefact:
                        pass
                    else:
                        artefact['images'] = []
        except Exception as e:
            print(f"Warning: Failed to fetch companion images for artefact '{decoded_title}': {e}")
            artefact['images'] = []

        if isinstance(artefact.get('created_at'), datetime):
            artefact['created_at'] = artefact['created_at'].isoformat()
        if isinstance(artefact.get('updated_at'), datetime):
            artefact['updated_at'] = artefact['updated_at'].isoformat()
        return artefact

    @router.get("/{discussion_id}/artefacts/{artefact_title:path}/images/{index}")
    async def get_binary_image(
        discussion_id: str,
        artefact_title: str,
        index: int,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """Locates and serves decoded base64 sub-images as a binary stream."""
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)

        from urllib.parse import unquote
        decoded_title = unquote(artefact_title)

        # Resolve title case-insensitively against active artefacts
        try:
            for art in discussion.list_artefacts():
                if art.get("title", "").lower() == decoded_title.lower():
                    decoded_title = art["title"]
                    break
        except Exception:
            pass

        try:
            associated_images = discussion.artefacts.get_associated_images(decoded_title)
            for img in associated_images:
                img_idx = img.get("index")
                if img_idx is not None and str(img_idx) == str(index):
                    import base64
                    binary_data = base64.b64decode(img["data"])
                    return Response(content=binary_data, media_type=img.get("media_type", "image/png"))

            # Fallback to direct companion direct read
            comp_art = discussion.get_artefact(title=f"{decoded_title}::images")
            if comp_art and 'images' in comp_art:
                images = comp_art['images']
                if 0 <= index < len(images):
                    import base64
                    img_b64 = images[index]
                    if "," in img_b64:
                        img_b64 = img_b64.split(",")[1]
                    binary_data = base64.b64decode(img_b64)
                    return Response(content=binary_data, media_type="image/png")
            
            # If no image matches, raise 404 explicitly instead of returning None
            raise HTTPException(status_code=404, detail="Image not found")
        except HTTPException as he:
            raise he
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to load image: {e}")

        raise HTTPException(status_code=404, detail="Requested sub-image not found in bundle.")

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

        # Check if original exists first
        if not discussion.get_artefact(title=old_title):
            raise HTTPException(status_code=404, detail="Original artefact not found.")

        # Prevent collisions
        if old_title != new_title and discussion.get_artefact(title=new_title):
             raise HTTPException(status_code=400, detail=f"An artefact named '{new_title}' already exists.")

        try:
            # 1. Auto-detect type based on extension
            ext = Path(new_title).suffix.lower()
            auto_type = None
            CODE_EXTS = {".py", ".js", ".ts", ".html", ".css", ".c", ".cpp", ".h", ".cs", ".java", ".sh", ".sql", ".vhd", ".v", ".rb", ".php", ".go", ".rs", ".swift", ".kt"}
            if ext in CODE_EXTS:
                auto_type = "code"
            elif ext in {".md", ".txt", ".pdf", ".docx", ".xlsx", ".pptx"}:
                auto_type = "document"

            # 2. Rename via the LollmsDiscussion sub-manager
            discussion.artefacts.rename(
                old_title=old_title, 
                new_title=new_title, 
                new_type=auto_type
            )

            # 3. Update visual references in message content strings
            all_msgs = discussion.db_manager.get_all_messages(discussion_id)
            old_anchor = f'id="{old_title}::'
            new_anchor = f'id="{new_title}::'
            for m in all_msgs:
                if old_anchor in m.content:
                    m.content = m.content.replace(old_anchor, new_anchor)
                    discussion.db_manager.update_message(m)

            # Persist changes
            discussion.commit()
            return {"message": "Artefact renamed successfully.", "new_title": new_title}
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/{discussion_id}/artefacts/{artefact_title:path}/log")
    async def get_artefact_log(
        discussion_id: str,
        artefact_title: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        try:
            log = discussion.artefacts.get_log(unquote(artefact_title))
            return log
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/{discussion_id}/artefacts/{artefact_title:path}/resolve-tag")
    async def resolve_artefact_tag(
        discussion_id: str,
        artefact_title: str,
        tag: str = Query(...),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        try:
            version = discussion.artefacts.resolve_tag(unquote(artefact_title), tag)
            return {"version": version}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    class RevertToTagRequest(BaseModel):
        tag: str

    @router.post("/{discussion_id}/artefacts/{artefact_title:path}/revert-to-tag")
    async def revert_artefact_to_tag(
        discussion_id: str,
        artefact_title: str,
        payload: RevertToTagRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            reverted_art = discussion.artefacts.revert_to_tag(unquote(artefact_title), payload.tag)
            discussion.commit()
            return _map_artefact_for_ui(reverted_art, discussion_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/{discussion_id}/artefacts/{artefact_title:path}/bundle")
    async def export_artefact_bundle(
        discussion_id: str,
        artefact_title: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        try:
            bundle = discussion.artefacts.export_artefact_bundle(unquote(artefact_title))
            return bundle
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    class ImportBundleRequest(BaseModel):
        bundle: Dict[str, Any]
        activate: bool = True

    @router.post("/{discussion_id}/artefacts/bundle")
    async def import_artefact_bundle(
        discussion_id: str,
        payload: ImportBundleRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            restored_art = discussion.artefacts.import_artefact_bundle(payload.bundle, activate=payload.activate)
            discussion.commit()
            return _map_artefact_for_ui(restored_art, discussion_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
