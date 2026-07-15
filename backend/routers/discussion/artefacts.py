# backend/routers/discussion/artefacts.py
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
from lollms_client.lollms_artefact import ArtefactVisibility

try:
    import extract_msg
except ImportError:
    extract_msg = None

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.saved_artefact import SavedArtefact, SharedArtefactLink
from pydantic import BaseModel

class IndividualShareRequest(BaseModel):
    target_username: str
    permission_level: str = "interact"

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
    mode: str = "abstract"

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
    mapped = {k: v for k, v in art.items() if k not in ['content', 'images']}
    if 'discussion_id' not in mapped and discussion_id:
        mapped['discussion_id'] = discussion_id
    mapped['artefact_type'] = art.get('type', 'document')
    mapped['is_loaded'] = bool(art.get('active', False))
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
        "discussion_id": "saved"
    }

def build_artefacts_router(router: APIRouter):
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

    @router.delete("/{discussion_id}/artefacts/{artefact_title:path}/version/{version}")
    async def delete_artefact_version(
        discussion_id: str,
        artefact_title: str,
        version: int,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Deletes a specific version of an artefact.
        If the deleted version was the active one, the system automatically 
        promotes the next highest available version to be the active one.
        """
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        decoded_title = unquote(artefact_title)
        
        # 1. Determine if the version being deleted is currently active
        history = discussion.artefacts.get_version_history(decoded_title)
        target_version_record = next((v for v in history if v["version"] == version), None)
        is_deleting_active = target_version_record and target_version_record.get("is_active", False)

        # 2. Perform the deletion
        removed = discussion.artefacts.remove(decoded_title, version=version)
        if removed == 0:
            raise HTTPException(status_code=404, detail="Version not found.")
            
        # 3. Handle Active Fallback Promotion
        if is_deleting_active:
            # Filter out the deleted version and find the next highest version
            remaining_versions = [v for v in history if v["version"] != version]
            if remaining_versions:
                # Sort descending to get the highest remaining version
                remaining_versions.sort(key=lambda x: x["version"], reverse=True)
                new_active_version = remaining_versions[0]["version"]
                
                # Promote to FULL visibility
                discussion.artefacts.set_visibility(
                    decoded_title, 
                    ArtefactVisibility.FULL, 
                    version=new_active_version
                )
                print(f"INFO: Active version {version} deleted. Automatically promoted version {new_active_version} to active.")
            else:
                print(f"INFO: Deleted last remaining version of '{decoded_title}'.")

        discussion.commit()
        return {"message": f"Version {version} deleted."}

    @router.delete("/{discussion_id}/artefacts/{artefact_title:path}/images/{index}")
    async def delete_binary_image_endpoint(
        discussion_id: str,
        artefact_title: str,
        index: int,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        decoded_title = unquote(artefact_title)

        try:
            for art in discussion.list_artefacts():
                if art.get("title", "").lower() == decoded_title.lower():
                    decoded_title = art["title"]
                    break
        except Exception:
            pass

        try:
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

            images[index] = ""
            latest_art = discussion.get_artefact(title=decoded_title)
            existing_content = latest_art.get('content', '') if latest_art else ''
            existing_type = latest_art.get('artefact_type', 'document') if latest_art else 'document'

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

    @router.get("/artefacts/all", response_model=List[ArtefactInfo])
    async def list_all_user_artefacts(
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
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
        _, owner_username, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')

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

    @router.post("/{discussion_id}/artefacts/sync", response_model=Dict[str, int])
    async def sync_discussion_workspace(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Runs a bidirectional sync scan between disk workspace_data/ and the database.
        Detects new tool-written files and restores accidentally deleted files.
        """
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            report = discussion.sync_workspace_to_artefacts()
            discussion.commit()
            return report
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Workspace sync failed: {e}")

    @router.get("/{discussion_id}/artefacts/{artefact_title:path}/export_archive")
    async def export_standalone_archive(
        discussion_id: str,
        artefact_title: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """Exports a single artefact along with its entire version history into a .laa archive."""
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        decoded_title = unquote(artefact_title)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / f"{unquote(artefact_title)}.laa"
            try:
                discussion.artefacts.export_artefact_to_archive(decoded_title, str(output_path))
                return Response(
                    content=output_path.read_bytes(),
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{decoded_title}.laa"'}
                )
            except Exception as e:
                trace_exception(e)
                raise HTTPException(status_code=500, detail=f"Failed to export standalone archive: {e}")

    @router.post("/{discussion_id}/artefacts/import_archive", response_model=ArtefactInfo)
    async def import_standalone_archive(
        discussion_id: str,
        file: UploadFile = File(...),
        activate: bool = Query(True),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """Imports an artefact with its complete history from a .laa archive."""
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')

        with tempfile.NamedTemporaryFile(delete=False, suffix=".laa") as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = Path(temp_file.name)

        try:
            imported_record = discussion.artefacts.import_artefact_from_archive(str(temp_path), activate=activate)
            discussion.commit()
            return _map_artefact_for_ui(imported_record, discussion_id)
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to import standalone archive: {e}")
        finally:
            temp_path.unlink(missing_ok=True)

    @router.post("/{discussion_id}/artefacts/export_bundle")
    async def export_linked_bundle(
        discussion_id: str,
        paths: List[str] = Body(..., description="Relative paths inside workspace_data to package"),
        include_versions: bool = Body(False),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """Bundles multiple linked artefacts into a unified .lab package preserving folder structures."""
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "bundle.lab"
            try:
                discussion.artefacts.export_artefact_bundle(
                    paths=paths,
                    output_path=str(output_path),
                    include_versions=include_versions
                )
                return Response(
                    content=output_path.read_bytes(),
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": 'attachment; filename="bundle.lab"'}
                )
            except Exception as e:
                trace_exception(e)
                raise HTTPException(status_code=500, detail=f"Failed to package linked bundle: {e}")

    @router.post("/{discussion_id}/artefacts/import_bundle", response_model=List[ArtefactInfo])
    async def import_linked_bundle(
        discussion_id: str,
        file: UploadFile = File(...),
        activate: bool = Query(True),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """Ingests a .lab package, unzipping into workspace_data and auto-registering files."""
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')

        with tempfile.NamedTemporaryFile(delete=False, suffix=".lab") as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = Path(temp_file.name)

        try:
            discussion.artefacts.import_artefact_bundle(str(temp_path), activate=activate)
            discussion.commit()
            return [_map_artefact_for_ui(art, discussion_id) for art in discussion.list_artefacts()]
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to ingest linked bundle: {e}")
        finally:
            temp_path.unlink(missing_ok=True)

    @router.put("/{discussion_id}/artefacts/{artefact_title:path}/visibility", response_model=ArtefactInfo)
    async def update_artefact_visibility(
        discussion_id: str,
        artefact_title: str,
        visibility: str = Query(..., description="FULL, METADATA, TREE_UNLOCKABLE, LOCKED, HIDDEN"),
        version: Optional[int] = Query(None),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """Updates the active visibility tier in the context state machine."""
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        decoded_title = unquote(artefact_title)

        try:
            # Resolves string visibility keys directly to the ArtefactVisibility enum
            from lollms_client.lollms_artefact import ArtefactVisibility
            target_visibility = getattr(ArtefactVisibility, visibility.upper())

            discussion.artefacts.set_visibility(decoded_title, target_visibility, version=version)
            discussion.commit()

            updated_record = discussion.get_artefact(title=decoded_title, version=version)
            return _map_artefact_for_ui(updated_record, discussion_id)
        except AttributeError:
            raise HTTPException(status_code=400, detail=f"Invalid visibility level: {visibility}")
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

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
            artefacts = [
                _map_artefact_for_ui(art, discussion_id)
                for art in discussion.list_artefacts()
            ]
            all_images_info = discussion.get_discussion_images()

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
            artefacts = [
                _map_artefact_for_ui(art, discussion_id)
                for art in discussion.list_artefacts()
            ]
            all_images_info = discussion.get_discussion_images()

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
            artefacts = [
                _map_artefact_for_ui(a, discussion_id)
                for a in discussion.list_artefacts()
            ]
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
            artefacts = [
                _map_artefact_for_ui(a, discussion_id)
                for a in discussion.list_artefacts()
            ]
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
            artefacts = [
                _map_artefact_for_ui(a, discussion_id)
                for a in discussion.list_artefacts()
            ]
            all_images_info = discussion.get_discussion_images()

            return {
                "artefacts": artefacts,
                "discussion_images": [img['data'] for img in all_images_info],
                "active_discussion_images": [img['active'] for img in all_images_info]
            }
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to process YouTube transcript: {str(e)}")

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
            raw_type = (artefact_type or "").lower()
            if "note" in raw_type: final_type = "note"
            elif "skill" in raw_type: final_type = "skill"
            else:
                ext = payload.title.split('.')[-1].lower() if '.' in payload.title else ""
                final_type = "code" if ext in ['py', 'js', 'ts', 'html', 'css', 'sql', 'cpp', 'c', 'sh'] else "document"

            discussion.add_artefact(
                payload.title, 
                payload.content, 
                images=payload.images_b64, 
                author=current_user.username,
                active=False,
                artefact_type=final_type
            )
            
            if auto_load:
                if final_type == "data":
                    discussion.artefacts.set_visibility(payload.title, ArtefactVisibility.TREE_UNLOCKABLE)
                else:
                    discussion.artefacts.set_visibility(payload.title, ArtefactVisibility.FULL)
            else:
                discussion.artefacts.set_visibility(payload.title, ArtefactVisibility.TREE_UNLOCKABLE)
                
            discussion.commit()
            artefacts = [
                _map_artefact_for_ui(art, discussion_id)
                for art in discussion.list_artefacts()
            ]
            all_images_info = discussion.get_discussion_images()

            return {
                "artefacts": artefacts,
                "discussion_images": [img['data'] for img in all_images_info],
                "active_discussion_images": [img['active'] for img in all_images_info]
            }
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to create manual artefact: {e}")

    @router.put("/{discussion_id}/artefacts/{artefact_title}", response_model=ArtefactInfo)
    async def update_manual_artefact(
        discussion_id: str,
        artefact_title: str,
        payload: ArtefactUpdate,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
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
            artefact_info = discussion.artefacts.update(
                title=decoded_title, 
                new_content=payload.new_content, 
                new_type=payload.artefact_type,
                new_images=payload.kept_images_b64 + payload.new_images_b64,
                bump_version=not payload.update_in_place,
                active=True
            )
            discussion.commit()

            if isinstance(artefact_info.get('created_at'), datetime):
                artefact_info['created_at'] = artefact_info['created_at'].isoformat()
            if isinstance(artefact_info.get('updated_at'), datetime):
                artefact_info['updated_at'] = artefact_info['updated_at'].isoformat()
            
            return _map_artefact_for_ui(artefact_info, discussion_id)

        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred while updating the artefact: {e}")

    @router.post("/{discussion_id}/artefacts/load-all-to-context", response_model=ArtefactAndDataZoneUpdateResponse)
    async def load_all_artefacts_to_data_zone(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            all_artefacts_infos = discussion.list_artefacts()
            for art_info in all_artefacts_infos:
                discussion.artefacts.set_visibility(art_info['title'], ArtefactVisibility.FULL, version=art_info['version'])

            discussion.commit()
            artefacts = [
                _map_artefact_for_ui(art, discussion_id) 
                for art in discussion.list_artefacts()
            ]

            all_images_info = discussion.get_discussion_images()
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
            decoded_title = unquote(request.title)
            try:
                if "%" in decoded_title:
                    decoded_title = unquote(decoded_title)
            except Exception:
                pass

            discussion.artefacts.set_visibility(decoded_title, ArtefactVisibility.FULL, version=request.version)
            discussion.commit()
            
            artefacts = [
                _map_artefact_for_ui(art, discussion_id)
                for art in discussion.list_artefacts()
            ]
            all_images_info = discussion.get_discussion_images()

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
            decoded_title = unquote(request.title)
            try:
                if "%" in decoded_title:
                    decoded_title = unquote(decoded_title)
            except Exception:
                pass

            discussion.artefacts.set_visibility(decoded_title, ArtefactVisibility.TREE_UNLOCKABLE, version=request.version)
            discussion.commit()
            
            artefacts = [
                _map_artefact_for_ui(art, discussion_id)
                for art in discussion.list_artefacts()
            ]
            all_images_info = discussion.get_discussion_images()

            return {
                "artefacts": artefacts,
                "discussion_images": [img['data'] for img in all_images_info],
                "active_discussion_images": [img['active'] for img in all_images_info]
            }
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to unload artefact: {e}")

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
        strategy: str = Query("raw"),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        decoded_title = unquote(artefact_title)

        try:
            if "%" in decoded_title:
                decoded_title = unquote(decoded_title)
        except Exception:
            pass

        if "%" in decoded_title:
            raise HTTPException(status_code=400, detail="Malformed artefact title: still URL-encoded.")

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
            from urllib.parse import quote
            encoded_title = quote(decoded_title, safe='')
            return PlainTextResponse(
                content=saved_art.content,
                media_type="text/plain; charset=utf-8",
                headers={"X-Artefact-Title": encoded_title, "X-Artefact-Version": str(saved_art.version)}
            )

        discussion, owner_username, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)

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

        content = artefact.get('content', '')

        from fastapi.responses import PlainTextResponse
        from urllib.parse import quote
        encoded_title = quote(decoded_title, safe='')
        return PlainTextResponse(
            content=content,
            media_type="text/plain; charset=utf-8",
            headers={"X-Artefact-Title": encoded_title, "X-Artefact-Version": str(artefact.get('version', 1))}
        )

    @router.get("/{discussion_id}/artefact", response_model=ArtefactInfo)
    async def get_discussion_artefact_info(
        discussion_id: str,
        artefact_title: str = Query(...),
        version: Optional[int] = Query(None),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
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
            associated_images = discussion.artefacts.get_associated_images(decoded_title)
            if associated_images:
                sorted_images = sorted(associated_images, key=lambda x: x.get('index', 0))
                artefact['images'] = [img['data'] for img in sorted_images]
            else:
                comp_art = discussion.get_artefact(title=f"{decoded_title}::images")
                if comp_art and 'images' in comp_art:
                    artefact['images'] = comp_art['images']
                else:
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
        return _map_artefact_for_ui(artefact, discussion_id)

    @router.delete("/{discussion_id}/artefact", status_code=status.HTTP_200_OK)
    async def delete_discussion_artefact(
        discussion_id: str,
        artefact_title: str = Query(...),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        title = unquote(artefact_title)
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        
        try:
            workspace_data_dir = Path(discussion.workspace_data_path) if hasattr(discussion, "workspace_data_path") and discussion.workspace_data_path else None
            
            if workspace_data_dir and workspace_data_dir.exists():
                possible_extensions = [".md", ".py", ".txt", ".csv", ".db", ".sqlite", ".json", ".yaml", ".yml", ".html", ".css", ".js", ".ts", ""]
                for ext in possible_extensions:
                    file_path = workspace_data_dir / f"{title}{ext}"
                    if file_path.exists():
                        try:
                            os.remove(file_path)
                        except Exception:
                            pass
                
                comp_file_path = workspace_data_dir / f"{title}::images.md"
                if comp_file_path.exists():
                    try:
                        os.remove(comp_file_path)
                    except Exception:
                        pass

            removed_main = discussion.artefacts.remove(title)
            removed_comp = discussion.artefacts.remove(f"{title}::images")
            discussion.commit()
            
            if removed_main > 0 or removed_comp > 0:
                return {"message": f"Artefact '{title}' deleted."}
            else:
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

    @router.post("/{discussion_id}/artefacts/import-from-source", response_model=ArtefactAndDataZoneUpdateResponse)
    async def import_artefact_from_source_discussion(
        discussion_id: str,
        source_discussion_id: str = Query(...),
        artefact_title: str = Query(...),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        target_discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        decoded_title = unquote(artefact_title)

        if source_discussion_id == 'saved':
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

        if target_discussion.get_artefact(title=decoded_title):
            decoded_title = f"{decoded_title} (Copy)"

        target_discussion.add_artefact(
            title=decoded_title,
            content=content_to_import,
            images=images_to_import,
            author=current_user.username,
            active=False,
            artefact_type=type_to_import
        )
        
        if type_to_import == "data":
            target_discussion.artefacts.set_visibility(decoded_title, ArtefactVisibility.TREE_UNLOCKABLE)
        else:
            target_discussion.artefacts.set_visibility(decoded_title, ArtefactVisibility.FULL)
            
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
        decoded_title = unquote(artefact_title)

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

        existing_link = db.query(SharedArtefactLink).filter_by(
            artefact_title=decoded_title,
            owner_user_id=current_user.id,
            shared_with_user_id=target_user.id
        ).first()

        if not existing_link:
            new_link = SharedArtefactLink(
                artefact_title=decoded_title,
                owner_user_id=current_user.id,
                shared_with_user_id=target_user.id,
                permission_level=payload.permission_level
            )
            db.add(new_link)
            db.commit()
        else:
            existing_link.permission_level = payload.permission_level
            db.commit()

        target_discussion_id = str(uuid.uuid4())
        lc_sender = get_user_lollms_client(current_user.username)
        target_discussion = get_user_discussion(target_user.username, target_discussion_id, create_if_missing=True, lollms_client=lc_sender)

        if not target_discussion:
            raise HTTPException(status_code=500, detail="Failed to create target discussion for sharing.")

        target_discussion.add_artefact(
            title=decoded_title,
            content=source_art.content if discussion_id == "saved" else source_art.get('content', ''),
            images=source_art.get('images', []) if hasattr(source_art, 'get') else [],
            author=f"Shared by {current_user.username}",
            active=True,
            artefact_type=source_art.artefact_type if discussion_id == "saved" else source_art.get('artefact_type', 'document')
        )
        target_discussion.set_metadata_item('title', f"Shared: {decoded_title}")

        target_discussion.add_message(
            sender="System",
            content=f"👋 **{current_user.username}** has shared the document **{decoded_title}** with you.\n\nThe file is already loaded into this conversation's context and can be viewed or edited in the Workspace panel on the right.",
            sender_type="system"
        )
        target_discussion.commit()

        from backend.ws_manager import manager
        manager.send_personal_message_sync({
            "type": "notification",
            "data": {"message": f"🎁 {current_user.username} shared an artefact: {decoded_title}", "type": "success", "duration": 5000}
        }, target_user.id)

        manager.send_personal_message_sync({
            "type": "discussion_updated",
            "data": {
                "discussion_id": target_discussion_id,
                "sender_username": current_user.username
            }
        }, target_user.id)

        return {"message": f"Artefact successfully shared with {payload.target_username}."}

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