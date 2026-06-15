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
from backend.models.personality import PersonalitySendRequest
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
from backend.db.models.saved_artefact import SavedArtefact, SharedArtefactLink
from pydantic import BaseModel

# --- New Models for Search/Select ---
class IndividualShareRequest(BaseModel):
    target_username: str
    permission_level: str = "interact" # "view" or "interact"

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

def _map_saved_artefact_for_ui(saved: SavedArtefact, current_user_id: Optional[int] = None) -> dict:
    author_val = "Me"
    if current_user_id is not None and saved.owner_user_id != current_user_id and saved.owner:
        author_val = f"Shared by {saved.owner.username}"
    elif saved.description:
        if saved.description.startswith("Shared by ") or saved.description == "Shared":
            author_val = saved.description
    return {
        "title": saved.title,
        "version": saved.version,
        "is_loaded": False,
        "author": author_val,
        "artefact_type": saved.artefact_type or "document",
        "created_at": saved.created_at.isoformat() if saved.created_at else datetime.now().isoformat(),
        "updated_at": saved.updated_at.isoformat() if saved.updated_at else datetime.now().isoformat(),
        "content": saved.content,
        "discussion_id": "saved" # Special marker to tell the UI this is from the global saved library
    }

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


    class SaveArtefactRequest(BaseModel):
        title: str
        content: str
        artefact_type: Optional[str] = "document"

    @router.post("/artefacts/save", response_model=ArtefactInfo)
    async def save_artefact_to_library(
        payload: SaveArtefactRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Saves raw content or custom document as a featured artefact in the global library.
        """
        existing_versions = db.query(SavedArtefact).filter(
            SavedArtefact.owner_user_id == current_user.id,
            SavedArtefact.title == payload.title
        ).all()

        if existing_versions:
            max_version = max(v.version for v in existing_versions)
            new_version = max_version + 1
        else:
            new_version = 1

        new_save = SavedArtefact(
            title=payload.title,
            content=payload.content,
            artefact_type=payload.artefact_type,
            owner_user_id=current_user.id,
            version=new_version
        )
        db.add(new_save)
        db.commit()
        db.refresh(new_save)

        return _map_saved_artefact_for_ui(new_save)

    @router.post("/{discussion_id}/artefacts/{artefact_title:path}/save", response_model=ArtefactInfo)
    async def save_discussion_artefact_to_library(
        discussion_id: str,
        artefact_title: str,
        version: Optional[int] = Query(None),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Saves an existing discussion artefact to the user's global library.
        """
        from urllib.parse import unquote
        decoded_title = unquote(artefact_title)

        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        art = discussion.get_artefact(title=decoded_title, version=version)
        if not art:
            raise HTTPException(status_code=404, detail="Artefact not found in discussion.")

        # Find existing versions in the library
        existing_versions = db.query(SavedArtefact).filter(
            SavedArtefact.owner_user_id == current_user.id,
            SavedArtefact.title == decoded_title
        ).all()

        if existing_versions:
            max_version = max(v.version for v in existing_versions)
            new_version = max_version + 1
        else:
            new_version = 1

        new_save = SavedArtefact(
            title=decoded_title,
            content=art.get('content', ''),
            artefact_type=art.get('artefact_type', 'document'),
            owner_user_id=current_user.id,
            version=new_version
        )
        db.add(new_save)
        db.commit()
        db.refresh(new_save)

        return _map_saved_artefact_for_ui(new_save, current_user.id)

    @router.delete("/artefacts/save/{artefact_title:path}", status_code=status.HTTP_200_OK)
    async def delete_saved_artefact(
        artefact_title: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Removes an artefact from the global saved library (or revokes/unsubscribes if shared).
        """
        from urllib.parse import unquote
        decoded_title = unquote(artefact_title)

        owned_art = db.query(SavedArtefact).filter(
            SavedArtefact.owner_user_id == current_user.id,
            SavedArtefact.title == decoded_title
        ).first()

        if owned_art:
            db.query(SavedArtefact).filter(
                SavedArtefact.owner_user_id == current_user.id,
                SavedArtefact.title == decoded_title
            ).delete()
            db.query(SharedArtefactLink).filter(
                SharedArtefactLink.owner_user_id == current_user.id,
                SharedArtefactLink.artefact_title == decoded_title
            ).delete()
        else:
            db.query(SharedArtefactLink).filter(
                SharedArtefactLink.shared_with_user_id == current_user.id,
                SharedArtefactLink.artefact_title == decoded_title
            ).delete()

        db.commit()
        return {"message": "Artefact removed from saved library."}

    class SaveArtefactRequest(BaseModel):
        title: str
        content: str
        artefact_type: Optional[str] = "document"

    @router.post("/artefacts/save", response_model=ArtefactInfo)
    async def save_artefact_to_library(
        payload: SaveArtefactRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Saves raw content or custom document as a featured artefact in the global library.
        """
        existing = db.query(SavedArtefact).filter(
            SavedArtefact.owner_user_id == current_user.id,
            SavedArtefact.title == payload.title
        ).first()

        if existing:
            existing.content = payload.content
            existing.artefact_type = payload.artefact_type
            db.commit()
            db.refresh(existing)
            saved = existing
        else:
            new_save = SavedArtefact(
                title=payload.title,
                content=payload.content,
                artefact_type=payload.artefact_type,
                owner_user_id=current_user.id
            )
            db.add(new_save)
            db.commit()
            db.refresh(new_save)
            saved = new_save

        return _map_saved_artefact_for_ui(saved, current_user.id)

    @router.get("/artefacts/all", response_model=List[ArtefactInfo])
    async def list_all_user_artefacts(
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Retrieves all saved (featured) artefacts for the current user (owned + shared with me).
        """
        from sqlalchemy import or_, and_

        shared_links = db.query(SharedArtefactLink).filter(
            SharedArtefactLink.shared_with_user_id == current_user.id
        ).all()

        shared_conditions = []
        for link in shared_links:
            shared_conditions.append(
                and_(
                    SavedArtefact.owner_user_id == link.owner_user_id,
                    SavedArtefact.title == link.artefact_title
                )
            )

        if shared_conditions:
            query = db.query(SavedArtefact).filter(
                or_(
                    SavedArtefact.owner_user_id == current_user.id,
                    *shared_conditions
                )
            )
        else:
            query = db.query(SavedArtefact).filter(SavedArtefact.owner_user_id == current_user.id)

        saved_list = query.order_by(SavedArtefact.updated_at.desc()).all()

        return [_map_saved_artefact_for_ui(s, current_user.id) for s in saved_list]

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
            last_activity_at=target_discussion.updated_at,
            has_artefacts=len(target_discussion.list_artefacts()) > 0
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
        from urllib.parse import unquote
        decoded_title = unquote(artefact_title)

        if discussion_id == "saved":
            owner_id = current_user.id
            owner_exists = db.query(SavedArtefact).filter(
                SavedArtefact.owner_user_id == current_user.id,
                SavedArtefact.title == decoded_title
            ).first() is not None
            
            if not owner_exists:
                shared_link = db.query(SharedArtefactLink).filter(
                    SharedArtefactLink.shared_with_user_id == current_user.id,
                    SharedArtefactLink.artefact_title == decoded_title
                ).first()
                if shared_link:
                    if shared_link.permission_level != "interact":
                        raise HTTPException(status_code=403, detail="You only have view permission for this shared artefact.")
                    owner_id = shared_link.owner_user_id
                else:
                    raise HTTPException(status_code=404, detail="Saved artefact not found in library.")

            existing_versions = db.query(SavedArtefact).filter(
                SavedArtefact.owner_user_id == owner_id,
                SavedArtefact.title == decoded_title
            ).all()

            if not existing_versions:
                raise HTTPException(status_code=404, detail="Saved artefact not found in library.")

            if payload.update_in_place:
                version_to_update = payload.version if payload.version is not None else max(v.version for v in existing_versions)
                saved_art = db.query(SavedArtefact).filter(
                    SavedArtefact.owner_user_id == owner_id,
                    SavedArtefact.title == decoded_title,
                    SavedArtefact.version == version_to_update
                ).first()
                if not saved_art:
                    raise HTTPException(status_code=404, detail=f"Version {version_to_update} not found.")

                saved_art.content = payload.new_content
                if payload.artefact_type:
                    saved_art.artefact_type = payload.artefact_type
                db.commit()
                db.refresh(saved_art)
                return _map_saved_artefact_for_ui(saved_art, current_user.id)
            else:
                max_version = max(v.version for v in existing_versions)
                new_version = max_version + 1

                new_save = SavedArtefact(
                    title=decoded_title,
                    content=payload.new_content,
                    artefact_type=payload.artefact_type or existing_versions[0].artefact_type,
                    owner_user_id=owner_id,
                    version=new_version
                )
                db.add(new_save)
                db.commit()
                db.refresh(new_save)
                return _map_saved_artefact_for_ui(new_save, current_user.id)

        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')

        try:
            # Use the library's internal manager for correct version bumping and state management.
            # We map UI parameters to the library's ArtefactManager.update signature.
            artefact_info = discussion.artefacts.update(
                title=decoded_title, 
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
        decoded_title = unquote(artefact_title)

        # Decode twice in case of double encoding of path segments
        try:
            if "%" in decoded_title:
                decoded_title = unquote(decoded_title)
        except Exception:
            pass

        if discussion_id == "saved":
            owner_id = current_user.id
            owner_exists = db.query(SavedArtefact).filter(
                SavedArtefact.owner_user_id == current_user.id,
                SavedArtefact.title == decoded_title
            ).first() is not None

            if not owner_exists:
                shared_link = db.query(SharedArtefactLink).filter(
                    SharedArtefactLink.shared_with_user_id == current_user.id,
                    SharedArtefactLink.artefact_title == decoded_title
                ).first()
                if shared_link:
                    owner_id = shared_link.owner_user_id
                else:
                    raise HTTPException(status_code=404, detail=f"Saved artefact '{decoded_title}' not found in library.")

            query = db.query(SavedArtefact).filter(
                SavedArtefact.owner_user_id == owner_id,
                SavedArtefact.title == decoded_title
            )
            if version is not None:
                saved_art = query.filter(SavedArtefact.version == version).first()
            else:
                saved_art = query.order_by(SavedArtefact.version.desc()).first()

            if not saved_art:
                raise HTTPException(status_code=404, detail=f"Saved artefact '{decoded_title}' not found in library.")

            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(
                content=saved_art.content,
                media_type="text/plain; charset=utf-8",
                headers={"X-Artefact-Title": decoded_title, "X-Artefact-Version": str(saved_art.version)}
            )

        discussion, owner_username, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)

        # Performance Optimisation: Attempt to locate version directly in memory-cached list
        artefact = None
        try:
            for art in discussion.list_artefacts():
                if art.get('title') == decoded_title:
                    art_version = art.get('version')
                    if version is None:
                        if artefact is None or (art_version is not None and int(art_version) > int(artefact.get('version', 1))):
                            artefact = art
                    elif art_version is not None and int(art_version) == int(version):
                        artefact = art
                        break
        except Exception:
            pass

        if not artefact:
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
        from urllib.parse import unquote
        decoded_title = unquote(artefact_title)

        if discussion_id == "saved":
            owner_id = current_user.id
            owner_exists = db.query(SavedArtefact).filter(
                SavedArtefact.owner_user_id == current_user.id,
                SavedArtefact.title == decoded_title
            ).first() is not None

            if not owner_exists:
                shared_link = db.query(SharedArtefactLink).filter(
                    SharedArtefactLink.shared_with_user_id == current_user.id,
                    SharedArtefactLink.artefact_title == decoded_title
                ).first()
                if shared_link:
                    owner_id = shared_link.owner_user_id
                else:
                    raise HTTPException(status_code=404, detail=f"Saved artefact '{decoded_title}' not found in library.")

            query = db.query(SavedArtefact).filter(
                SavedArtefact.owner_user_id == owner_id,
                SavedArtefact.title == decoded_title
            )
            if version is not None:
                saved_art = query.filter(SavedArtefact.version == version).first()
            else:
                saved_art = query.order_by(SavedArtefact.version.desc()).first()

            if not saved_art:
                raise HTTPException(status_code=404, detail=f"Saved artefact '{decoded_title}' not found in library.")
            return _map_saved_artefact_for_ui(saved_art, current_user.id)

        discussion, owner_username, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)

        # Performance Optimisation: Attempt to locate version directly in memory-cached list
        artefact = None
        try:
            for art in discussion.list_artefacts():
                if art.get('title') == decoded_title:
                    art_version = art.get('version')
                    if version is None:
                        if artefact is None or (art_version is not None and int(art_version) > int(artefact.get('version', 1))):
                            artefact = art
                    elif art_version is not None and int(art_version) == int(version):
                        artefact = art
                        break
        except Exception:
            pass

        if not artefact:
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
            if discussion.get_artefact(title=title):
                discussion.remove_artefact(title=title)
                discussion.commit()
                return {"message": f"Artefact '{title}' deleted."}
            else:
                # Already removed or not found, but we want to make sure any loose local state is cleared
                try:
                    discussion.remove_artefact(title=title)
                    discussion.commit()
                except Exception:
                    pass
                return {"message": f"Artefact '{title}' was already removed."}
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
        from urllib.parse import unquote
        decoded_title = unquote(artefact_title)

        if discussion_id == "saved":
            owner_id = current_user.id
            owner_exists = db.query(SavedArtefact).filter(
                SavedArtefact.owner_user_id == current_user.id,
                SavedArtefact.title == decoded_title
            ).first() is not None

            if not owner_exists:
                shared_link = db.query(SharedArtefactLink).filter(
                    SharedArtefactLink.shared_with_user_id == current_user.id,
                    SharedArtefactLink.artefact_title == decoded_title
                ).first()
                if shared_link:
                    owner_id = shared_link.owner_user_id
                else:
                    raise HTTPException(status_code=404, detail=f"Saved artefact '{decoded_title}' not found in library.")

            records = db.query(SavedArtefact).filter(
                SavedArtefact.owner_user_id == owner_id,
                SavedArtefact.title == decoded_title
            ).order_by(SavedArtefact.version.desc()).all()

            return [
                {
                    "version": r.version,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                    "content_size": len(r.content),
                    "is_active": False
                }
                for r in records
            ]

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
            from urllib.parse import unquote
            decoded_title = unquote(request.title)
            try:
                if "%" in decoded_title:
                    decoded_title = unquote(decoded_title)
            except Exception:
                pass

            # We only update the library metadata. The library handles 
            # context injection natively during chat() without modifying the data_zone string.
            discussion.artefacts.activate(decoded_title, version=request.version)
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
            from urllib.parse import unquote
            decoded_title = unquote(request.title)
            try:
                if "%" in decoded_title:
                    decoded_title = unquote(decoded_title)
            except Exception:
                pass

            # Deactivate in the library metadata only.
            discussion.artefacts.deactivate(decoded_title, version=request.version)
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

    @router.get("/{discussion_id}/artefacts/{artefact_title:path}/grid-data")
    async def get_data_grid_data(
        discussion_id: str,
        artefact_title: str,
        version: Optional[int] = Query(None),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """Loads a specific versioned data artifact spreadsheet or SQLite DB."""
        from urllib.parse import unquote
        import pandas as pd

        decoded_title = unquote(artefact_title)
        try:
            if "%" in decoded_title:
                decoded_title = unquote(decoded_title)
        except Exception:
            pass

        discussion, owner_username, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        active = discussion.get_artefact(title=decoded_title, version=version)

        path_obj = Path(decoded_title)
        stem = path_obj.stem
        ext = path_obj.suffix.lower()
        is_data_extension = ext in (".csv", ".xlsx", ".xls", ".db", ".sqlite", ".sqlite3")

        if not active:
            raise HTTPException(status_code=404, detail="Artifact not found.")

        # Check both potential type keys, with a safe fallback to file extension check
        art_type = active.get("artefact_type") or active.get("type")
        if art_type != "data" and not is_data_extension:
            raise HTTPException(status_code=404, detail="Data artifact not found.")

        current_version = active.get("version", 1)

        # Use original discussion ID where the file is physically stored on disk
        source_discussion_id = active.get("discussion_id") or discussion_id

        from backend.session import get_user_discussion_assets_path
        assets_dir = get_user_discussion_assets_path(owner_username) / source_discussion_id

        possible_paths = [
            assets_dir / f"{stem}_consolidated.db",
            assets_dir / f"{stem}_v{current_version}{ext}",
            assets_dir / f"{decoded_title}",
        ]

        file_path = None
        for path in possible_paths:
            if path.exists():
                file_path = path
                break

        if not file_path or not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Raw data file missing from workspace. Checked: {possible_paths}")

        try:
            if ext in (".xlsx", ".xls"):
                xl = pd.ExcelFile(str(file_path))
                result = {"type": "excel", "sheets": {}}
                for sheet in xl.sheet_names:
                    df = pd.read_excel(str(file_path), sheet_name=sheet).head(100)
                    df = df.replace({float('nan'): None, float('inf'): None, float('-inf'): None})
                    result["sheets"][sheet] = {
                        "columns": list(df.columns),
                        "rows": df.to_dict(orient="records")
                    }
            elif ext in (".db", ".sqlite", ".sqlite3"):
                import sqlite3
                conn = sqlite3.connect(str(file_path))
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                result = {"type": "sqlite", "sheets": {}}
                for table in tables:
                    df = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 100;", conn)
                    df = df.replace({float('nan'): None, float('inf'): None, float('-inf'): None})
                    result["sheets"][table] = {
                        "columns": list(df.columns),
                        "rows": df.to_dict(orient="records")
                    }
                conn.close()
            else:
                sep = ";" if ext == ".csv" and ";" in file_path.read_text(encoding="utf-8", errors="ignore").splitlines()[0] else ","
                df = pd.read_csv(str(file_path), sep=sep).head(100)
                df = df.replace({float('nan'): None, float('inf'): None, float('-inf'): None})
                result = {
                    "type": "csv",
                    "columns": list(df.columns),
                    "rows": df.to_dict(orient="records")
                }
            return result
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to parse dataset: {e}")

    class RawSQLQueryPayload(BaseModel):
        sql_query: str

    @router.post("/{discussion_id}/artefacts/{artefact_title:path}/raw-query")
    async def execute_raw_sql_query(
        discussion_id: str,
        artefact_title: str,
        payload: RawSQLQueryPayload,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """Executes a raw, user-written SQLite SQL query on the active dataset tables."""
        from urllib.parse import unquote
        import sqlite3
        import pandas as pd
        decoded_title = unquote(artefact_title)

        discussion, owner_username, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        active = discussion.get_artefact(title=decoded_title)

        path_obj = Path(decoded_title)
        stem = path_obj.stem
        ext = path_obj.suffix.lower()
        is_data_extension = ext in (".csv", ".xlsx", ".xls", ".db", ".sqlite", ".sqlite3")

        if not active:
            raise HTTPException(status_code=404, detail="Artifact not found.")

        art_type = active.get("artefact_type") or active.get("type")
        if art_type != "data" and not is_data_extension:
            raise HTTPException(status_code=404, detail="Data artifact not found.")

        current_version = active.get("version", 1)
        source_discussion_id = active.get("discussion_id") or discussion_id

        from backend.session import get_user_discussion_assets_path
        assets_dir = get_user_discussion_assets_path(owner_username) / source_discussion_id
        file_path = assets_dir / f"{stem}_v{current_version}{ext}"
        if not file_path.exists():
            file_path = assets_dir / f"{decoded_title}"

        if not file_path.exists():
            raise FileNotFoundError("Raw data file is missing.")

        try:
            conn = sqlite3.connect(":memory:")
            if ext in (".db", ".sqlite", ".sqlite3"):
                disk_conn = sqlite3.connect(str(file_path))
                disk_conn.backup(conn)
                disk_conn.close()
            elif ext in (".xlsx", ".xls"):
                xl = pd.ExcelFile(str(file_path))
                for sheet_name in xl.sheet_names:
                    t_name = sheet_name.replace(" ", "_")
                    df = pd.read_excel(str(file_path), sheet_name=sheet_name)
                    df.to_sql(t_name, conn, index=False, if_exists="replace")
            else:
                sep = ";" if ext == ".csv" and ";" in file_path.read_text(encoding="utf-8", errors="ignore").splitlines()[0] else ","
                df = pd.read_csv(str(file_path), sep=sep)
                df.to_sql(decoded_title.replace(" ", "_"), conn, index=False, if_exists="replace")

            # Execute
            df_res = pd.read_sql_query(payload.sql_query, conn)
            conn.close()

            df_res = df_res.replace({float('nan'): None, float('inf'): None, float('-inf'): None})

            return {
                "success": True,
                "columns": list(df_res.columns),
                "rows": df_res.to_dict(orient="records")
            }
        except Exception as e:
            trace_exception(e)
            return {"success": False, "error": str(e)}

    class AIDataQueryPayload(BaseModel):
        question: str

    @router.post("/{discussion_id}/artefacts/{artefact_title:path}/ai-query")
    async def execute_ai_data_query(
        discussion_id: str,
        artefact_title: str,
        payload: AIDataQueryPayload,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """Translates a natural language question into an SQL query, executes it, and returns the result."""
        from urllib.parse import unquote
        import sqlite3
        import pandas as pd
        decoded_title = unquote(artefact_title)

        discussion, owner_username, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        active = discussion.get_artefact(title=decoded_title)

        path_obj = Path(decoded_title)
        stem = path_obj.stem
        ext = path_obj.suffix.lower()
        is_data_extension = ext in (".csv", ".xlsx", ".xls", ".db", ".sqlite", ".sqlite3")

        if not active:
            raise HTTPException(status_code=404, detail="Artifact not found.")

        art_type = active.get("artefact_type") or active.get("type")
        if art_type != "data" and not is_data_extension:
            raise HTTPException(status_code=404, detail="Data artifact not found.")

        current_version = active.get("version", 1)
        source_discussion_id = active.get("discussion_id") or discussion_id

        from backend.session import get_user_discussion_assets_path
        assets_dir = get_user_discussion_assets_path(owner_username) / source_discussion_id

        schema_text = active.get("content", "")

        # Ask LLM for the SQL query
        prompt = (
            "You are a Senior SQL Developer and Database Specialist.\n"
            f"Given the database schema for '{decoded_title}' below, translate the user's natural language question into a single, valid, optimized SQLite SQL query.\n\n"
            "=== DATABASE SCHEMA ===\n"
            f"{schema_text}\n"
            "=======================\n\n"
            f"User Question: \"{payload.question}\"\n\n"
            "Requirements:\n"
            "1. Output ONLY the raw SQLite SQL query inside a JSON object.\n"
            "2. Ensure table names match the Sheet/Table names listed in the schema (spaces replaced by underscores, e.g., 'Order_Details').\n"
            "3. Do NOT include markdown formatting, explanations, or code blocks outside the JSON."
        )

        try:
            lc = get_user_lollms_client(current_user.username)
            res_json = lc.generate_structured_content(
                prompt=prompt,
                schema={
                    "sql_query": {
                        "type": "string",
                        "description": "The valid SQLite SQL query to execute."
                    },
                    "explanation": {
                        "type": "string",
                        "description": "A brief explanation of how this query computes the requested answer."
                    }
                },
                temperature=0.1
            )

            if not res_json or not isinstance(res_json, dict):
                raise ValueError("The AI model failed to produce a structured JSON response.")

            sql_query = res_json.get("sql_query", "").strip()
            explanation = res_json.get("explanation", "").strip()

            if not sql_query:
                raise ValueError("LLM failed to generate a valid SQL query.")

            ext = Path(decoded_title).suffix.lower()
            current_version = active.get("version", 1)

            from backend.session import get_user_discussion_assets_path
            assets_dir = get_user_discussion_assets_path(owner_username) / discussion_id
            file_path = assets_dir / f"{decoded_title}_v{current_version}{ext}"
            if not file_path.exists():
                file_path = assets_dir / f"{decoded_title}{ext}"

            conn = sqlite3.connect(":memory:")
            if ext in (".db", ".sqlite", ".sqlite3"):
                disk_conn = sqlite3.connect(str(file_path))
                disk_conn.backup(conn)
                disk_conn.close()
            elif ext in (".xlsx", ".xls"):
                xl = pd.ExcelFile(str(file_path))
                for sheet_name in xl.sheet_names:
                    t_name = sheet_name.replace(" ", "_")
                    df = pd.read_excel(str(file_path), sheet_name=sheet_name)
                    df.to_sql(t_name, conn, index=False, if_exists="replace")
            else:
                sep = ";" if ext == ".csv" and ";" in file_path.read_text(encoding="utf-8", errors="ignore").splitlines()[0] else ","
                df = pd.read_csv(str(file_path), sep=sep)
                df.to_sql(decoded_title.replace(" ", "_"), conn, index=False, if_exists="replace")

            df_res = pd.read_sql_query(sql_query, conn)
            conn.close()

            df_res = df_res.replace({float('nan'): None, float('inf'): None, float('-inf'): None})

            return {
                "success": True,
                "sql_query": sql_query,
                "explanation": explanation,
                "columns": list(df_res.columns),
                "rows": df_res.to_dict(orient="records")
            }
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/{discussion_id}/artefacts/import-from-source", response_model=ArtefactAndDataZoneUpdateResponse)
    async def import_artefact_from_source_discussion(
        discussion_id: str,
        source_discussion_id: str = Query(...),
        artefact_title: str = Query(...),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        from urllib.parse import unquote
        from sqlalchemy import or_, and_

        # 1. Get target and source discussions
        target_discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')

        decoded_title = unquote(artefact_title)

        if source_discussion_id == 'saved':
            # Load from SavedArtefact table
            owner_id = current_user.id
            owner_exists = db.query(SavedArtefact).filter(
                SavedArtefact.owner_user_id == current_user.id,
                SavedArtefact.title == decoded_title
            ).first() is not None

            if not owner_exists:
                shared_link = db.query(SharedArtefactLink).filter(
                    SharedArtefactLink.shared_with_user_id == current_user.id,
                    SharedArtefactLink.artefact_title == decoded_title
                ).first()
                if shared_link:
                    owner_id = shared_link.owner_user_id
                else:
                    raise HTTPException(status_code=404, detail="Saved artefact not found")

            saved_art = db.query(SavedArtefact).filter(
                SavedArtefact.owner_user_id == owner_id,
                SavedArtefact.title == decoded_title
            ).order_by(SavedArtefact.version.desc()).first()

            if not saved_art:
                raise HTTPException(status_code=404, detail="Saved artefact not found")

            content_to_import = saved_art.content
            images_to_import = []
            type_to_import = saved_art.artefact_type or "document"
        else:
            source_discussion, _, _, _ = await get_discussion_and_owner_for_request(source_discussion_id, current_user, db)
            source_art = source_discussion.get_artefact(title=decoded_title)
            if not source_art:
                raise HTTPException(status_code=404, detail="Source artefact not found")
            content_to_import = source_art.get('content', '')
            images_to_import = source_art.get('images', [])
            type_to_import = source_art.get('artefact_type', 'document')

        # Check for name collision in target discussion
        if target_discussion.get_artefact(title=decoded_title):
            decoded_title = f"{decoded_title} (Copy)"

        # 2. Add the copied artefact to the target discussion
        target_discussion.add_artefact(
            title=decoded_title,
            content=content_to_import,
            images=images_to_import,
            author=current_user.username,
            active=True,
            artefact_type=type_to_import
        )
        target_discussion.commit()

        raw_artefacts = target_discussion.list_artefacts()
        all_images_info = target_discussion.get_discussion_images()

        return {
            "artefacts": [_map_artefact_for_ui(art, discussion_id) for art in raw_artefacts],
            "discussion_images": [img['data'] for img in all_images_info],
            "active_discussion_images": [img['active'] for img in all_images_info]
        }

    @router.post("/{discussion_id}/artefacts/{artefact_title:path}/share", status_code=status.HTTP_200_OK)
    async def share_discussion_artefact(
        discussion_id: str,
        artefact_title: str,
        payload: IndividualShareRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        from urllib.parse import unquote
        from backend.db.models.user import User as DBUser
        from backend.discussion import get_user_discussion
        from backend.db.models.saved_artefact import SavedArtefact, SharedArtefactLink

        decoded_title = unquote(artefact_title)

        # Decode twice in case of double encoding of path segments
        try:
            if "%" in decoded_title:
                decoded_title = unquote(decoded_title)
        except Exception:
            pass

        target_user = db.query(DBUser).filter(DBUser.username == payload.target_username).first()
        if not target_user:
            raise HTTPException(status_code=404, detail=f"Target user '{payload.target_username}' not found.")

        if target_user.id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot share with yourself.")

        # Ensure the source artefact exists
        if discussion_id == "saved":
            source_art = db.query(SavedArtefact).filter(
                SavedArtefact.owner_user_id == current_user.id,
                SavedArtefact.title == decoded_title
            ).first()
            if not source_art:
                raise HTTPException(status_code=404, detail=f"Source saved artefact '{decoded_title}' not found.")
        else:
            source_discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
            source_art = source_discussion.get_artefact(title=decoded_title)
            if not source_art:
                raise HTTPException(status_code=404, detail="Source artefact not found.")

            # If it's a local discussion artefact, we should first save it to the owner's global library!
            # Let's save it to the owner's global library (SavedArtefact) if it doesn't exist
            existing = db.query(SavedArtefact).filter(
                SavedArtefact.owner_user_id == current_user.id,
                SavedArtefact.title == decoded_title
            ).first()
            if not existing:
                new_save = SavedArtefact(
                    title=decoded_title,
                    content=source_art.get('content', ''),
                    artefact_type=source_art.get('artefact_type', 'document'),
                    owner_user_id=current_user.id
                )
                db.add(new_save)
                db.commit()

        # Check if sharing link already exists
        existing_link = db.query(SharedArtefactLink).filter_by(
            artefact_title=decoded_title,
            owner_user_id=current_user.id,
            shared_with_user_id=target_user.id
        ).first()

        if not existing_link:
            # Create a SharedArtefactLink with permission_level from payload
            new_link = SharedArtefactLink(
                artefact_title=decoded_title,
                owner_user_id=current_user.id,
                shared_with_user_id=target_user.id,
                permission_level=payload.permission_level
            )
            db.add(new_link)
            db.commit()
        else:
            # Update existing link's permission level
            existing_link.permission_level = payload.permission_level
            db.commit()

        # Create a new discussion for the target user to receive the shared artefact link
        import uuid
        target_discussion_id = str(uuid.uuid4())
        lc_sender = get_user_lollms_client(current_user.username)
        target_discussion = get_user_discussion(target_user.username, target_discussion_id, create_if_missing=True, lollms_client=lc_sender)

        if not target_discussion:
            raise HTTPException(status_code=500, detail="Failed to create target discussion for sharing.")

        # Copy/mount the artefact into the target user's new discussion
        target_discussion.add_artefact(
            title=decoded_title,
            content=source_art.content if discussion_id == "saved" else source_art.get('content', ''),
            images=source_art.get('images', []) if hasattr(source_art, 'get') else [],
            author=f"Shared by {current_user.username}",
            active=True,
            artefact_type=source_art.artefact_type if discussion_id == "saved" else source_art.get('artefact_type', 'document')
        )
        target_discussion.set_metadata_item('title', f"Shared: {decoded_title}")

        # Add an introductory message so the discussion is not empty and appears in the sidebar clearly
        target_discussion.add_message(
            sender="System",
            content=f"👋 **{current_user.username}** has shared the document **{decoded_title}** with you.\n\nThe file is already loaded into this conversation's context and can be viewed or edited in the Workspace panel on the right.",
            sender_type="system"
        )
        target_discussion.commit()

        # 4. Send real-time notifications to the receiver
        from backend.ws_manager import manager
        manager.send_personal_message_sync({
            "type": "notification",
            "data": {"message": f"🎁 {current_user.username} shared an artefact: {decoded_title}", "type": "success", "duration": 5000}
        }, target_user.id)

        # Send a discussion update event to let the receiver's UI auto-refresh their discussions list
        manager.send_personal_message_sync({
            "type": "discussion_updated",
            "data": {
                "discussion_id": target_discussion_id,
                "sender_username": current_user.username
            }
        }, target_user.id)

        return {"message": f"Artefact successfully shared with {payload.target_username}."}

    @router.delete("/{discussion_id}/artefacts/{artefact_title:path}/share/{target_user_id}", status_code=status.HTTP_200_OK)
    async def unshare_discussion_artefact_from_user(
        discussion_id: str,
        artefact_title: str,
        target_user_id: int,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Unshares a global saved library artefact from a specific user.
        """
        from urllib.parse import unquote
        from backend.db.models.saved_artefact import SharedArtefactLink

        decoded_title = unquote(artefact_title)

        # Find and delete the matching link
        link = db.query(SharedArtefactLink).filter_by(
            artefact_title=decoded_title,
            owner_user_id=current_user.id,
            shared_with_user_id=target_user_id
        ).first()

        if not link:
            raise HTTPException(status_code=404, detail="Sharing link not found.")

        db.delete(link)
        db.commit()

        # Notify the unsubscribed participant to refresh their list
        from backend.ws_manager import manager
        manager.send_personal_message_sync({
            "type": "notification",
            "data": {"message": f"ℹ️ {current_user.username} has revoked your access to '{decoded_title}'", "type": "info"}
        }, target_user_id)

        return {"message": "Access revoked successfully."}

    class GroupShareRequest(BaseModel):
        group_id: int
        permission_level: str = "interact"

    @router.post("/{discussion_id}/artefacts/{artefact_title:path}/share-group", status_code=status.HTTP_200_OK)
    async def share_discussion_artefact_with_group(
        discussion_id: str,
        artefact_title: str,
        payload: GroupShareRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Shares a global saved library artefact with all members of a user group.
        """
        from urllib.parse import unquote
        from backend.db.models.group import Group as DBGroup
        from backend.db.models.saved_artefact import SavedArtefact, SharedArtefactLink
        from backend.discussion import get_user_discussion

        decoded_title = unquote(artefact_title)

        # Resolve target group
        group = db.query(DBGroup).options(joinedload(DBGroup.members)).filter(
            DBGroup.id == payload.group_id
        ).first()

        if not group:
            raise HTTPException(status_code=404, detail="Target group not found.")

        # Ensure the source artefact exists and is in global library
        source_art = db.query(SavedArtefact).filter(
            SavedArtefact.owner_user_id == current_user.id,
            SavedArtefact.title == decoded_title
        ).first()

        if not source_art:
            if discussion_id == "saved":
                raise HTTPException(status_code=404, detail="Source saved library artefact not found.")

            # Local discussion import to global library prior to sharing
            source_discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
            local_art = source_discussion.get_artefact(title=decoded_title)
            if not local_art:
                raise HTTPException(status_code=404, detail="Source local artefact not found.")

            source_art = SavedArtefact(
                title=decoded_title,
                content=local_art.get('content', ''),
                artefact_type=local_art.get('artefact_type', 'document'),
                owner_user_id=current_user.id
            )
            db.add(source_art)
            db.commit()

        # Iterate and create shared links for members
        added_count = 0
        from backend.ws_manager import manager
        import uuid

        for member in group.members:
            if member.id == current_user.id:
                continue

            existing_link = db.query(SharedArtefactLink).filter_by(
                artefact_title=decoded_title,
                owner_user_id=current_user.id,
                shared_with_user_id=member.id
            ).first()

            if not existing_link:
                new_link = SharedArtefactLink(
                    artefact_title=decoded_title,
                    owner_user_id=current_user.id,
                    shared_with_user_id=member.id,
                    permission_level=payload.permission_level
                )
                db.add(new_link)
                added_count += 1

                # Spawn active discussion for the new workspace share
                try:
                    target_discussion_id = str(uuid.uuid4())
                    lc_sender = get_user_lollms_client(current_user.username)
                    target_discussion = get_user_discussion(member.username, target_discussion_id, create_if_missing=True, lollms_client=lc_sender)

                    target_discussion.add_artefact(
                        title=decoded_title,
                        content=source_art.content,
                        author=f"Shared by {current_user.username}",
                        active=True,
                        artefact_type=source_art.artefact_type or 'document'
                    )
                    target_discussion.set_metadata_item('title', f"Shared: {decoded_title}")
                    target_discussion.add_message(
                        sender="System",
                        content=f"👋 **{current_user.username}** has shared the group document **{decoded_title}** with you.\n\nThe file is already loaded into your workspace.",
                        sender_type="system"
                    )
                    target_discussion.commit()

                    # Notify
                    manager.send_personal_message_sync({
                        "type": "notification",
                        "data": {"message": f"🎁 Shared with Group: New artefact '{decoded_title}' added.", "type": "success"}
                    }, member.id)

                    manager.send_personal_message_sync({
                        "type": "discussion_updated",
                        "data": {
                            "discussion_id": target_discussion_id,
                            "sender_username": current_user.username
                        }
                    }, member.id)
                except Exception as e:
                    print(f"Warning: Failed to create target workspace mount for {member.username}: {e}")

        db.commit()
        return {"message": f"Artefact successfully shared with {added_count} group member(s)."}

    @router.post("/{discussion_id}/artefacts/{artefact_title:path}/unshare-group", status_code=status.HTTP_200_OK)
    async def unshare_discussion_artefact_from_group(
        discussion_id: str,
        artefact_title: str,
        payload: GroupShareRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Unshares a global saved library artefact from all members of a user group.
        """
        from urllib.parse import unquote
        from backend.db.models.group import Group as DBGroup
        from backend.db.models.saved_artefact import SharedArtefactLink

        decoded_title = unquote(artefact_title)

        group = db.query(DBGroup).options(joinedload(DBGroup.members)).filter(
            DBGroup.id == payload.group_id
        ).first()

        if not group:
            raise HTTPException(status_code=404, detail="Target group not found.")

        revoked_count = 0
        from backend.ws_manager import manager

        for member in group.members:
            if member.id == current_user.id:
                continue

            link = db.query(SharedArtefactLink).filter_by(
                artefact_title=decoded_title,
                owner_user_id=current_user.id,
                shared_with_user_id=member.id
            ).first()

            if link:
                db.delete(link)
                revoked_count += 1

                manager.send_personal_message_sync({
                    "type": "notification",
                    "data": {"message": f"ℹ️ {current_user.username} revoked access to '{decoded_title}'", "type": "info"}
                }, member.id)

        db.commit()
        return {"message": f"Revoked access for {revoked_count} group member(s)."}

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

            # 2. Rename via the LollmsDiscussion sub-manager (updates all versions and internal image anchors)
            discussion.artefacts.rename(
                old_title=old_title, 
                new_title=new_title, 
                new_type=auto_type
            )

            # 3. Update visual references in message content strings across the whole discussion tree
            all_msgs = discussion.get_all_messages_flat()
            old_anchor = f'id="{old_title}::'
            new_anchor = f'id="{new_title}::'
            for m in all_msgs:
                if m.content and old_anchor in m.content:
                    # Modifying m.content automatically modifies the underlying SQLAlchemy ORM object and flags it as dirty
                    m.content = m.content.replace(old_anchor, new_anchor)

            # Persist all dirty states (both renamed artifact versions and updated conversation messages)
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

    @router.get("/shared-with-users", response_model=List[Dict[str, Any]])
    async def get_resource_shared_with(
        resource_type: str,
        resource_name: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        from urllib.parse import unquote
        from sqlalchemy.orm import joinedload
        decoded_name = unquote(resource_name)
        shared_users = []

        if resource_type == "artefact":
            records = db.query(SharedArtefactLink).options(joinedload(SharedArtefactLink.shared_with_user)).filter(
                SharedArtefactLink.artefact_title == decoded_name,
                SharedArtefactLink.owner_user_id == current_user.id
            ).all()
            shared_users = [{"id": r.shared_with_user.id, "username": r.shared_with_user.username, "icon": r.shared_with_user.icon} for r in records if r.shared_with_user]
        elif resource_type == "skill":
            from backend.db.models.skill import Skill
            records = db.query(Skill).options(joinedload(Skill.owner)).filter(
                Skill.name == decoded_name,
                Skill.author == f"Shared by {current_user.username}"
            ).all()
            shared_users = [{"id": r.owner.id, "username": r.owner.username, "icon": r.owner.icon} for r in records if r.owner]
        elif resource_type == "note":
            from backend.db.models.note import Note
            sender_note = db.query(Note).filter(Note.owner_id == current_user.id, Note.title == decoded_name).first()
            if sender_note and sender_note.description:
                found_usernames = re.findall(r'\[Shared with (\w+) on', sender_note.description)
                for uname in found_usernames:
                    user_obj = db.query(DBUser).filter(DBUser.username == uname).first()
                    if user_obj:
                        shared_users.append({"id": user_obj.id, "username": user_obj.username, "icon": user_obj.icon})

        # Deduplicate list of dicts
        seen = set()
        deduped = []
        for u in shared_users:
            if u["id"] not in seen:
                seen.add(u["id"])
                deduped.append(u)
        return deduped
