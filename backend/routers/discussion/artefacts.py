# backend/routers/discussion/artefacts.py
# Standard Library Imports
import base64
import io
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

try:
    import pipmaster as pm
    pm.ensure_packages(['pandas', 'openpyxl', 'python-docx', 'python-pptx', 'PyMuPDF', 'docx2python'])
    from docx import Document as DocxDocument
    from pptx import Presentation
    import pandas as pd
    import fitz
    from docx2python import docx2python
except ImportError:
    pd = None
    docx2python = None
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Form, status
from sqlalchemy.orm import Session
from ascii_colors import trace_exception

from backend.db import get_db
from backend.models import UserAuthDetails, ArtefactInfo, ArtefactCreateManual, ArtefactUpdate, ExportContextRequest, LoadArtefactRequest, TaskInfo, UnloadArtefactRequest, UrlImportRequest, ArtefactAndDataZoneUpdateResponse
from backend.models.discussion import ArtefactUploadResponse
from backend.session import get_current_active_user, get_user_lollms_client
from backend.discussion import get_user_discussion
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request
from backend.task_manager import task_manager
from ...tasks.discussion_tasks import _import_artefact_from_url_task, _to_task_info
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request
# .msg handling
try:
    pm.ensure_packages("extract-msg")
    import extract_msg  # pip install extract-msg
except ImportError:
    extract_msg = None

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

    @router.post("/{discussion_id}/artefacts", response_model=ArtefactUploadResponse)
    async def add_discussion_artefact(
        discussion_id: str,
        file: UploadFile = File(...),
        extract_images: bool = Form(True),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db) 
    ):
        print(f"extract_images: {extract_images}")
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        if not discussion:
            raise HTTPException(status_code=404, detail="Discussion not found")
        
        try:
            content_bytes = await file.read()
            title = file.filename
            extension = Path(title).suffix.lower()
            
            content = ""
            images: List[str] = []
            
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
                        if extract_images:
                            img_list = page.get_images(full=True)
                            for img_info in img_list:
                                xref = img_info[0]
                                base_image = pdf_doc.extract_image(xref)
                                image_bytes = base_image["image"]
                                images.append(base64.b64encode(image_bytes).decode('utf-8'))
                    content = "\n".join(text_parts)
                    pdf_doc.close()

                elif extension == ".docx":
                    if docx2python is None:
                        content = "Error: docx2python library is not installed, so tables cannot be extracted."
                    else:
                        with io.BytesIO(content_bytes) as docx_io:
                            result = docx2python(docx_io)
                            content = result.text
                            if extract_images and result.images:
                                for image_bytes in result.images.values():
                                    images.append(base64.b64encode(image_bytes).decode("utf-8"))

                elif extension == ".xlsx" or "spreadsheetml" in file.content_type:
                    try:
                        xls = pd.read_excel(io.BytesIO(content_bytes), sheet_name=None)
                        md_parts = []
                        for sheet_name, df in xls.items():
                            md_parts.append(f"### {sheet_name}\n\n{df.to_markdown(index=False)}")
                        content = "\n\n".join(md_parts)
                    except Exception as e:
                        trace_exception(e)
                        content = f"Error processing XLSX file: {e}"

                elif extension == ".pptx":
                    try:
                        with io.BytesIO(content_bytes) as pptx_io:
                            prs = Presentation(pptx_io)
                            slide_texts: List[str] = []
                            for idx, slide in enumerate(prs.slides, start=1):
                                slide_parts: List[str] = []
                                for shape in slide.shapes:
                                    if hasattr(shape, "text"):
                                        txt = (shape.text or "").strip()
                                        if txt:
                                            slide_parts.append(txt)
                                if slide_parts:
                                    slide_texts.append(f"--- Slide {idx} ---\n" + "\n".join(slide_parts))
                            content = "\n\n".join(slide_texts)
                            if extract_images:                            
                                from pptx.enum.shapes import MSO_SHAPE_TYPE
                                for slide in prs.slides:
                                    for shape in slide.shapes:
                                        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                                            image_blob = shape.image.blob
                                            images.append(base64.b64encode(image_blob).decode("utf-8"))
                    except Exception as e:
                        trace_exception(e)
                        content = f"Error processing PPTX file: {e}"

                elif extension == ".msg":
                    if extract_msg is None:
                        content = "Error: extract-msg library is not installed."
                    else:
                        try:
                            with io.BytesIO(content_bytes) as bio:
                                import tempfile, os
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".msg") as tf:
                                    tf.write(bio.getvalue())
                                    temp_path = tf.name
                            try:
                                msg = extract_msg.Message(temp_path)
                                msg_sender = getattr(msg, "sender", None) or getattr(msg, "from_", None) or ""
                                msg_to = getattr(msg, "to", "") or ""
                                msg_cc = getattr(msg, "cc", "") or ""
                                msg_date = getattr(msg, "date", "")
                                msg_subject = getattr(msg, "subject", "") or title
                                msg_body = (getattr(msg, "body", "") or "").strip()

                                # Prefer body (plain) over HTML to avoid markup; if body empty, fallback to htmlBody text
                                html_body = getattr(msg, "htmlBody", None)
                                if not msg_body and html_body:
                                    try:
                                        from bs4 import BeautifulSoup
                                        msg_body = BeautifulSoup(html_body, "html.parser").get_text()
                                    except Exception:
                                        pass

                                header_lines = []
                                if msg_subject: header_lines.append(f"# {msg_subject}")
                                meta = []
                                if msg_sender: meta.append(f"From: {msg_sender}")
                                if msg_to: meta.append(f"To: {msg_to}")
                                if msg_cc: meta.append(f"CC: {msg_cc}")
                                if msg_date: meta.append(f"Date: {msg_date}")
                                if meta: header_lines.append("\n".join(meta))
                                header = "\n\n".join(header_lines)

                                # Attachments
                                attachment_text_parts: List[str] = []
                                for att in msg.attachments:
                                    # att has .longFilename, .data (bytes), possibly .mimetype
                                    att_name = getattr(att, "longFilename", None) or getattr(att, "shortFilename", None) or "attachment"
                                    att_bytes = att.data or b""
                                    att_ext = Path(att_name).suffix.lower()

                                    if extract_images:
                                        # Handle images directly
                                        if att_ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"]:
                                            images.append(base64.b64encode(att_bytes).decode("utf-8"))
                                            continue

                                    # Text-like attachments
                                    try:
                                        text_guess = att_bytes.decode("utf-8")
                                    except UnicodeDecodeError:
                                        try:
                                            text_guess = att_bytes.decode("latin-1", errors="replace")
                                        except Exception:
                                            text_guess = ""

                                    # If looks like Markdown or plain text/code, include as fenced block
                                    if att_ext in [".txt", ".md", ".py", ".json", ".csv", ".log", ".yaml", ".yml", ".xml", ".html", ".js", ".ts", ".css"]:
                                        lang = {
                                            ".md": "markdown", ".py": "python", ".json": "json", ".csv": "csv",
                                            ".yaml": "yaml", ".yml": "yaml", ".xml": "xml", ".html": "html",
                                            ".js": "javascript", ".ts": "typescript", ".css": "css"
                                        }.get(att_ext, "")
                                        fence = f"````{lang}\n{text_guess}\n````"
                                        attachment_text_parts.append(f"### Attachment: {att_name}\n\n{fence}")
                                    else:
                                        # Other binaries: just list the name
                                        attachment_text_parts.append(f"- Attachment: {att_name} ({len(att_bytes)} bytes)")

                                attachments_md = "\n\n".join(attachment_text_parts)
                                content = "\n\n".join([p for p in [header, msg_body, attachments_md] if p])

                            finally:
                                os.unlink(temp_path)
                        except Exception as e:
                            trace_exception(e)
                            content = f"Error processing MSG file: {e}"

                elif extension in CODE_EXTENSIONS:
                    lang = CODE_EXTENSIONS[extension]
                    text_content = content_bytes.decode('utf-8', errors='replace')
                    content = f"````{lang}\n{text_content}\n````"
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

            all_images_info = discussion.get_discussion_images()
            
            if isinstance(artefact_info.get('created_at'), datetime):
                artefact_info['created_at'] = artefact_info['created_at'].isoformat()
            if isinstance(artefact_info.get('updated_at'), datetime):
                artefact_info['updated_at'] = artefact_info['updated_at'].isoformat()

            return {
                "new_artefact_info": artefact_info,
                "discussion_images": [img['data'] for img in all_images_info],
                "active_discussion_images": [img['active'] for img in all_images_info]
            }
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
        
        try:
            artefact_info = discussion.update_artefact(
                title=artefact_title, 
                new_content=payload.new_content, 
                new_images=payload.kept_images_b64 + payload.new_images_b64,
                version=payload.version,
                update_in_place=payload.update_in_place
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

    @router.get("/{discussion_id}/artefact", response_model=ArtefactInfo)
    async def get_discussion_artefact_content(
        discussion_id: str,
        artefact_title: str = Query(...),
        version: Optional[int] = Query(None),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, owner_username, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        artefact = discussion.get_artefact(title=artefact_title, version=version)

        if not artefact:
            raise HTTPException(status_code=404, detail="Artefact not found")

        if isinstance(artefact.get('created_at'), datetime):
            artefact['created_at'] = artefact['created_at'].isoformat()
        if isinstance(artefact.get('updated_at'), datetime):
            artefact['updated_at'] = artefact['updated_at'].isoformat()
        return artefact

    @router.delete("/{discussion_id}/artefact", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_discussion_artefact(
        discussion_id: str,
        artefact_title: str = Query(...),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            discussion.remove_artefact(title=artefact_title)
            discussion.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete artefact: {e}")

    @router.post("/{discussion_id}/artefacts/load-all-to-context", response_model=ArtefactAndDataZoneUpdateResponse)
    async def load_all_artefacts_to_data_zone(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            discussion.discussion_data_zone = ""
            discussion.loaded_artefacts = []
            
            all_artefacts_infos = discussion.list_artefacts()
            
            latest_artefacts = {}
            for art_info in all_artefacts_infos:
                if art_info['title'] not in latest_artefacts or art_info['version'] > latest_artefacts[art_info['title']]['version']:
                    latest_artefacts[art_info['title']] = art_info
            
            for title, art_info in latest_artefacts.items():
                discussion.load_artefact_into_data_zone(title=title, version=art_info['version'])

            discussion.commit()
            
            artefacts = discussion.list_artefacts()
            for artefact in artefacts:
                if isinstance(artefact.get('created_at'), datetime):
                    artefact['created_at'] = artefact['created_at'].isoformat()
                if isinstance(artefact.get('updated_at'), datetime):
                    artefact['updated_at'] = artefact['updated_at'].isoformat()

            lc = get_user_lollms_client(current_user.username)
            token_count = len(lc.tokenize(discussion.discussion_data_zone))
            
            all_images_info = discussion.get_discussion_images()
            return {
                "discussion_data_zone": discussion.discussion_data_zone,
                "artefacts": artefacts,
                "discussion_data_zone_tokens": token_count,
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
            discussion.load_artefact_into_data_zone(title=request.title, version=request.version)
            discussion.commit()
            
            artefacts = discussion.list_artefacts()
            for artefact in artefacts:
                if isinstance(artefact.get('created_at'), datetime):
                    artefact['created_at'] = artefact['created_at'].isoformat()
                if isinstance(artefact.get('updated_at'), datetime):
                    artefact['updated_at'] = artefact['updated_at'].isoformat()
            
            lc = get_user_lollms_client(current_user.username)
            token_count = len(lc.tokenize(discussion.discussion_data_zone))

            all_images_info = discussion.get_discussion_images()
            return {
                "discussion_data_zone": discussion.discussion_data_zone,
                "artefacts": artefacts,
                "discussion_data_zone_tokens": token_count,
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
            discussion.unload_artefact_from_data_zone(title=request.title, version=request.version)
            discussion.commit()
            
            artefacts = discussion.list_artefacts()
            for artefact in artefacts:
                if isinstance(artefact.get('created_at'), datetime):
                    artefact['created_at'] = artefact['created_at'].isoformat()
                if isinstance(artefact.get('updated_at'), datetime):
                    artefact['updated_at'] = artefact['updated_at'].isoformat()

            lc = get_user_lollms_client(current_user.username)
            token_count = len(lc.tokenize(discussion.discussion_data_zone))

            all_images_info = discussion.get_discussion_images()
            return {
                "discussion_data_zone": discussion.discussion_data_zone,
                "artefacts": artefacts,
                "discussion_data_zone_tokens": token_count,
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
            args=(owner_username, discussion_id, request.url),
            description=f"Scraping content from URL and saving as artefact.",
            owner_username=current_user.username
        )
        return _to_task_info(task)