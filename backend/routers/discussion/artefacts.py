# backend/routers/discussion/artefacts.py
import base64
import io
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

import fitz
from docx import Document as DocxDocument
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Form, status
from sqlalchemy.orm import Session
from ascii_colors import trace_exception

from backend.db import get_db
from backend.models import UserAuthDetails, ArtefactInfo, ArtefactCreateManual, ArtefactUpdate, ExportContextRequest, LoadArtefactRequest, TaskInfo, UnloadArtefactRequest, UrlImportRequest
from backend.session import get_current_active_user
from backend.discussion import get_user_discussion
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request
from backend.task_manager import task_manager
from ...tasks.discussion_tasks import _import_artefact_from_url_task, _to_task_info
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request

from backend.db import get_db

def build_artefacts_router(router: APIRouter):
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
        artefacts = discussion.list_artefacts()
        for artefact in artefacts:
            if isinstance(artefact.get('created_at'), datetime):
                artefact['created_at'] = artefact['created_at'].isoformat()
            if isinstance(artefact.get('updated_at'), datetime):
                artefact['updated_at'] = artefact['updated_at'].isoformat()
        return artefacts

    @router.post("/{discussion_id}/artefacts", response_model=ArtefactInfo)
    async def add_discussion_artefact(
        discussion_id: str,
        file: UploadFile = File(...),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)  
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        if not discussion:
            raise HTTPException(status_code=404, detail="Discussion not found")
        
        try:
            content_bytes = await file.read()
            title = file.filename
            extension = Path(title).suffix.lower()
            
            content = ""
            images = []
            
            image_mimetypes = ["image/jpeg", "image/png", "image/gif", "image/webp"]
            if file.content_type in image_mimetypes:
                images.append(base64.b64encode(content_bytes).decode('utf-8'))
                content = ""
            else:
                CODE_EXTENSIONS = {
                    ".py": "python", ".js": "javascript", ".ts": "typescript", ".html": "html", ".css": "css",
                    ".c": "c", ".cpp": "cpp", ".h": "cpp", ".hpp": "cpp", ".cs": "csharp", ".java": "java",
                    ".json": "json", ".xml": "xml", ".sh": "bash", ".md": "markdown", ".vhd": "vhdl", ".v": "verilog",
                    ".rb": "ruby", ".php": "php", ".go": "go", ".rs": "rust", ".swift": "swift", ".kt": "kotlin"
                }

                if extension == ".pdf":
                    pdf_doc = fitz.open(stream=content_bytes, filetype="pdf")
                    text_parts = []
                    for page in pdf_doc:
                        text_parts.append(page.get_text())
                        img_list = page.get_images(full=True)
                        for img_info in img_list:
                            xref = img_info[0]
                            base_image = pdf_doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            images.append(base64.b64encode(image_bytes).decode('utf-8'))
                    content = "\n".join(text_parts)
                    pdf_doc.close()
                elif extension == ".docx":
                    with io.BytesIO(content_bytes) as docx_io:
                        doc = DocxDocument(docx_io)
                        # Extract text
                        content = "\n".join([p.text for p in doc.paragraphs])
                
                        # Extract images
                        for rel in doc.part._rels.values():
                            if "image" in rel.target_ref:  # detect images
                                image_part = rel.target_part
                                image_bytes = image_part.blob
                                images.append(base64.b64encode(image_bytes).decode("utf-8"))
                elif extension in CODE_EXTENSIONS:
                    lang = CODE_EXTENSIONS[extension]
                    text_content = content_bytes.decode('utf-8', errors='replace')
                    content = f"```{lang}\n{text_content}\n```"
                else:
                    try:
                        content = content_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        content = content_bytes.decode('latin-1', errors='replace')

            artefact_info = discussion.add_artefact(
                title=title,
                content=content,
                images=images,
                author=current_user.username
            )
            discussion.commit()
            if isinstance(artefact_info.get('created_at'), datetime):
                artefact_info['created_at'] = artefact_info['created_at'].isoformat()
            if isinstance(artefact_info.get('updated_at'), datetime):
                artefact_info['updated_at'] = artefact_info['updated_at'].isoformat()
            return artefact_info
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to add artefact: {e}")

    @router.post("/{discussion_id}/artefacts/manual", response_model=ArtefactInfo, status_code=status.HTTP_201_CREATED)
    async def create_manual_artefact(
        discussion_id: str,
        payload: ArtefactCreateManual,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        if discussion.get_artefact(title=payload.title):
            raise HTTPException(status_code=409, detail="An artefact with this title already exists.")
        try:
            artefact_info = discussion.add_artefact(
                title=payload.title, content=payload.content, images=payload.images_b64, author=current_user.username
            )
            discussion.commit()
            if isinstance(artefact_info.get('created_at'), datetime):
                artefact_info['created_at'] = artefact_info['created_at'].isoformat()
            if isinstance(artefact_info.get('updated_at'), datetime):
                artefact_info['updated_at'] = artefact_info['updated_at'].isoformat()
            return artefact_info
        except Exception as e:
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
        if not discussion.get_artefact(title=artefact_title):
            raise HTTPException(status_code=404, detail="Artefact not found to update.")
        try:
            artefact_info = discussion.update_artefact(
                title=artefact_title, new_content=payload.new_content, new_images=payload.kept_images_b64 + payload.new_images_b64
            )
            discussion.commit()
            if isinstance(artefact_info.get('created_at'), datetime):
                artefact_info['created_at'] = artefact_info['created_at'].isoformat()
            if isinstance(artefact_info.get('updated_at'), datetime):
                artefact_info['updated_at'] = artefact_info['updated_at'].isoformat()
            return artefact_info
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update artefact: {e}")

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
            if discussion.get_artefact(title=request.title):
                artefact_info = discussion.update_artefact(title=request.title, new_content=content, author=current_user.username)
            else:
                artefact_info = discussion.add_artefact(title=request.title, content=content, author=current_user.username)
            discussion.commit()
            if isinstance(artefact_info.get('created_at'), datetime):
                artefact_info['created_at'] = artefact_info['created_at'].isoformat()
            if isinstance(artefact_info.get('updated_at'), datetime):
                artefact_info['updated_at'] = artefact_info['updated_at'].isoformat()
            return artefact_info
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create artefact from context: {e}")

    @router.get("/{discussion_id}/artefacts/{artefact_title}", response_model=ArtefactInfo)
    async def get_discussion_artefact_content(
        discussion_id: str,
        artefact_title: str,
        version: Optional[int] = Query(None),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        artefact = discussion.get_artefact(title=artefact_title, version=version)
        if not artefact:
            raise HTTPException(status_code=404, detail="Artefact not found")
        if isinstance(artefact.get('created_at'), datetime):
            artefact['created_at'] = artefact['created_at'].isoformat()
        if isinstance(artefact.get('updated_at'), datetime):
            artefact['updated_at'] = artefact['updated_at'].isoformat()
        return artefact

    @router.delete("/{discussion_id}/artefacts/{artefact_title}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_discussion_artefact(
        discussion_id: str,
        artefact_title: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            discussion.remove_artefact(title=artefact_title)
            discussion.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete artefact: {e}")

    @router.post("/{discussion_id}/artefacts/load-to-context", response_model=Dict[str, str])
    async def load_artefact_to_data_zone(
        discussion_id: str,
        request: LoadArtefactRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            discussion.load_artefact_into_data_zone(title=request.title, version=request.version)
            discussion.commit()
            return {"content": discussion.discussion_data_zone}
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load artefact: {e}")

    @router.post("/{discussion_id}/artefacts/unload-from-context", response_model=Dict[str, str])
    async def unload_artefact_from_data_zone(
        discussion_id: str,
        request: UnloadArtefactRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            discussion.unload_artefact_from_data_zone(title=request.title, version=getattr(request, 'version', None))
            discussion.commit()
            return {"content": discussion.discussion_data_zone}
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
            args=(owner_username, discussion_id, request.url),
            description=f"Scraping content from URL and saving as artefact.",
            owner_username=current_user.username
        )
        return _to_task_info(task)
