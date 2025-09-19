# backend/routers/discussion/message.py
# Standard Library Imports
import base64
import io
import json
import re
import shutil
import uuid
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
import traceback
import threading
import asyncio
import zipfile

# Third-Party Imports
import fitz  # PyMuPDF
from docx import Document as DocxDocument
from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query,
    UploadFile, status)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               PlainTextResponse, StreamingResponse, Response)
from lollms_client import (LollmsClient, LollmsDiscussion, LollmsMessage,
                           LollmsPersonality, MSG_TYPE)
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ascii_colors import ASCIIColors, trace_exception
import markdown2
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from pptx import Presentation
from pptx.util import Inches

# Local Application Imports
from backend.config import APP_VERSION, SERVER_CONFIG
from backend.db import get_db
from backend.db.models.config import TTIBinding as DBTTIBinding
from backend.db.models.db_task import DBTask
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.user import (User as DBUser, UserMessageGrade,
                                     UserStarredDiscussion)
from backend.discussion import get_user_discussion, get_user_discussion_manager
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request
from backend.models import (UserAuthDetails, ArtefactInfo, ContextStatusResponse,
                            DataZones, DiscussionBranchSwitchRequest,
                            DiscussionDataZoneUpdate, DiscussionExportRequest,
                            DiscussionImageUpdateResponse,
                            DiscussionInfo, DiscussionImportRequest,
                            DiscussionRagDatastoreUpdate, DiscussionSendRequest,
                            DiscussionTitleUpdate, ExportContextRequest,
                            ExportData, LoadArtefactRequest, ManualMessageCreate,
                            MessageCodeExportRequest, MessageContentUpdate,
                            MessageGradeUpdate, MessageOutput, MessageExportPayload,
                            MessageUpdateWithImages, TaskInfo,
                            UnloadArtefactRequest, ArtefactCreateManual, ArtefactUpdate)
from backend.session import (get_current_active_user,
                             get_current_db_user_from_token,
                             get_safe_store_instance,
                             get_user_discussion_assets_path,
                             get_user_lollms_client,
                             get_user_temp_uploads_path, user_sessions)
from backend.task_manager import task_manager, Task
from backend.settings import settings
from backend.routers.files import (
    md2_to_html,              # markdown2 renderer with extras
    html_to_docx_bytes,       # HTML → python-docx mapper
    md_to_pdf_bytes,          # Markdown → PDF (images/tables/code/TOC)
    md_to_pptx_bytes,         # Markdown → PPTX (slides via ---)
    html_wrapper              # Wrap HTML body in a shell
)


# safe_store is needed for RAG callbacks
try:
    import safe_store
except ImportError:
    safe_store = None

message_grade_lock = threading.Lock()
def build_message_router(router: APIRouter):
    @router.put("/{discussion_id}/messages/{message_id}/grade", response_model=MessageOutput)
    async def grade_discussion_message(discussion_id: str, message_id: str, grade_update: MessageGradeUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
        username = current_user.username
        db_user = db.query(DBUser).filter(DBUser.username == username).one()
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        if not discussion_obj: raise HTTPException(status_code=404, detail="Discussion not found.")
        with message_grade_lock:
            grade = db.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id, message_id=message_id).first()
            if grade: grade.grade += grade_update.change
            else:
                grade = UserMessageGrade(user_id=db_user.id, discussion_id=discussion_id, message_id=message_id, grade=grade_update.change)
                db.add(grade)
            db.commit()
            db.refresh(grade)
            current_grade = grade.grade
        branch = discussion_obj.get_branch(discussion_obj.active_branch_id)
        target_message = next((msg for msg in branch if msg.id == message_id), None)
        if not target_message: raise HTTPException(status_code=404, detail="Message not found in active branch.")
        full_image_refs = [ f"data:image/png;base64,{img}" for img in target_message.images or []]

        msg_metadata = target_message.metadata or {}
        return MessageOutput(
            id=target_message.id, sender=target_message.sender, sender_type=target_message.sender_type, content=target_message.content,
            parent_message_id=target_message.parent_id, binding_name=target_message.binding_name, model_name=target_message.model_name,
            token_count=target_message.tokens, sources=msg_metadata.get('sources'), events=msg_metadata.get('events'),
            image_references=full_image_refs, user_grade=current_grade, created_at=target_message.created_at,
            branch_id=discussion_obj.active_branch_id, branches=None
        )

    @router.put("/{discussion_id}/messages/{message_id}", response_model=MessageOutput)
    async def update_discussion_message(
        discussion_id: str,
        message_id: str,
        payload: MessageUpdateWithImages,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        username = current_user.username
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        if not discussion_obj:
            raise HTTPException(status_code=404, detail="Discussion not found.")
        
        target_message = discussion_obj.get_message(message_id)
        if not target_message:
            raise HTTPException(status_code=404, detail="Message not found in discussion.")

        target_message.content = payload.content

        final_images_b64 = []
        final_images_b64.extend(payload.kept_images_b64)

        for b64_data_uri in payload.new_images_b64:
            try:
                _, encoded = b64_data_uri.split(",", 1)
                final_images_b64.append(encoded)
            except ValueError:
                final_images_b64.append(b64_data_uri)
        
        target_message.images = final_images_b64
        discussion_obj.commit()

        db_user = db.query(DBUser).filter(DBUser.username == username).one()
        grade = db.query(UserMessageGrade.grade).filter_by(user_id=db_user.id, discussion_id=discussion_id, message_id=message_id).scalar() or 0
        
        full_image_refs = [f"data:image/png;base64,{img}" for img in target_message.images or []]
        active_images = [True] * len(full_image_refs)

        msg_metadata = target_message.metadata or {}
        return MessageOutput(
            id=target_message.id, sender=target_message.sender, sender_type=target_message.sender_type,
            content=target_message.content, parent_message_id=target_message.parent_id,
            binding_name=target_message.binding_name, model_name=target_message.model_name,
            token_count=target_message.tokens, sources=msg_metadata.get('sources'),
            events=msg_metadata.get('events'), image_references=full_image_refs,
            active_images=active_images, user_grade=grade,
            created_at=target_message.created_at, branch_id=discussion_obj.active_branch_id
        )

    @router.post("/{discussion_id}/messages", response_model=MessageOutput)
    async def add_manual_message(
        discussion_id: str,
        payload: ManualMessageCreate,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        username = current_user.username
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, "interact")
        if not discussion_obj:
            raise HTTPException(status_code=404, detail="Discussion not found.")

        if payload.sender_type not in ['user', 'assistant']:
            raise HTTPException(status_code=400, detail="Invalid sender_type.")

        sender_name = username
        if payload.sender_type == 'assistant':
            db_pers = db.query(DBPersonality).filter(DBPersonality.id == current_user.active_personality_id).first()
            sender_name = db_pers.name if db_pers else "assistant"

        try:
            new_message = discussion_obj.add_message(
                sender=sender_name,
                content=payload.content,
                parent_id=payload.parent_message_id,
                sender_type=payload.sender_type
            )
            discussion_obj.commit()
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to add message to discussion: {e}")

        return MessageOutput(
            id=new_message.id,
            sender=new_message.sender,
            sender_type=new_message.sender_type,
            content=new_message.content,
            parent_message_id=new_message.parent_id,
            binding_name=new_message.binding_name,
            model_name=new_message.model_name,
            token_count=new_message.tokens,
            sources=[],
            events=[],
            image_references=[],
            user_grade=0,
            created_at=new_message.created_at,
            branch_id=discussion_obj.active_branch_id
        )

    @router.delete("/{discussion_id}/messages/{message_id}", status_code=200)
    async def delete_discussion_message(discussion_id: str, message_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
        username = current_user.username
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        if not discussion_obj:
            raise HTTPException(status_code=404, detail="Discussion not found.")
        
        try:
            message_to_delete = discussion_obj.get_message(message_id)
            if not message_to_delete:
                raise ValueError("Message to be deleted not found in discussion.")
            
            parent_id = message_to_delete.parent_id
            
            discussion_obj.delete_branch(message_id)
            
            # After deleting, set the active branch to the parent of the deleted branch
            discussion_obj.switch_to_branch(parent_id)

            discussion_obj.commit()
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        
        db_user = db.query(DBUser).filter(DBUser.username == username).one()
        db.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id, message_id=message_id).delete(synchronize_session=False)
        db.commit()
        return {"message": "Message and its branch deleted successfully."}


    @router.post("/{discussion_id}/messages/{message_id}/export")
    async def export_message(
        discussion_id: str,
        message_id: str,
        payload: MessageExportPayload,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        message = discussion.get_message(message_id)

        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        export_format = payload.format.lower()

        # Normalize format name for setting key
        setting_key_format = 'markdown' if export_format == 'md' else export_format
        setting_key = f"export_to_{setting_key_format}_enabled"

        if not settings.get(setting_key, False):
            raise HTTPException(status_code=403, detail=f"Export to '{export_format}' is disabled by the administrator.")

        content = message.content
        filename = f"message_{message_id[:8]}.{export_format}"
        media_type = "application/octet-stream"
        file_content = b''

        try:
            if export_format == 'txt':
                media_type = "text/plain"
                file_content = content.encode('utf-8')

            elif export_format in ['md', 'markdown']:
                media_type = "text/markdown"
                file_content = content.encode('utf-8')

            elif export_format == 'html':
                media_type = "text/html"
                html_content = md2_to_html(content)  # markdown2 with extras
                file_content = html_wrapper(html_content, title="Message Export")

            elif export_format == 'pdf':
                media_type = "application/pdf"
                file_content = md_to_pdf_bytes(content)  # preserves headings/lists/code/images/tables

            elif export_format == 'docx':
                media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                html_content = md2_to_html(content)
                file_content = html_to_docx_bytes(html_content)

            elif export_format == 'pptx':
                media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                file_content = md_to_pptx_bytes(content)  # Markdown slides delimited by ---

            elif export_format == 'xlsx':
                media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                wb = Workbook()

                # Regex to find markdown tables
                table_regex = re.compile(r'(\|.*\|(?:\r?\n|\r)?\|[-| :]*\|(?:\r?\n|\r)?(?:\|.*\|(?:\r?\n|\r)?)+)')
                tables = table_regex.findall(content)

                if tables:
                    for i, table_md in enumerate(tables):
                        ws = wb.create_sheet(title=f"Table {i+1}")
                        lines = [line.strip() for line in table_md.strip().split('\n')]
                        # Skip header separator line
                        data_rows = [line for line in lines if not re.match(r'^\|[-| :]*\|$', line)]
                        for row_idx, line in enumerate(data_rows):
                            cells = [cell.strip() for cell in line.strip('|').split('|')]
                            for col_idx, cell_text in enumerate(cells):
                                ws.cell(row=row_idx + 1, column=col_idx + 1, value=cell_text)
                        # Auto-adjust column widths
                        for col in ws.columns:
                            max_length = 0
                            column = get_column_letter(col[0].column)
                            for cell in col:
                                try:
                                    if cell.value and len(str(cell.value)) > max_length:
                                        max_length = len(str(cell.value))
                                except Exception:
                                    pass
                            ws.column_dimensions[column].width = (max_length + 2)
                    if wb.sheetnames[0] == 'Sheet':
                        wb.remove(wb['Sheet'])  # Remove default sheet if we added new ones
                else:
                    # Fallback for content without tables
                    ws = wb.active
                    ws.title = "Message"
                    ws['A1'] = content
                    ws.column_dimensions['A'].width = 100
                    ws['A1'].alignment = ws['A1'].alignment.copy(wrapText=True)

                bio = io.BytesIO()
                wb.save(bio)
                file_content = bio.getvalue()

            elif export_format == 'epub':
                media_type = "application/epub+zip"
                html_content = md2_to_html(content)
                file_content = html_wrapper(html_content, title="Message Export")  # placeholder XHTML

            elif export_format == 'odt':
                media_type = "application/vnd.oasis.opendocument.text"
                html_content = md2_to_html(content)
                file_content = html_wrapper(html_content, title="Message Export")  # placeholder

            elif export_format == 'rtf':
                media_type = "application/rtf"
                text_only = BeautifulSoup(md2_to_html(content), "html.parser").get_text()
                rtf = r"{\rtf1\ansi " + text_only.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}") \
                    .replace("\n", r"\par ") + "}"
                file_content = rtf.encode("utf-8", errors="ignore")

            elif export_format in ['tex', 'latex']:
                media_type = "application/x-tex"
                text_only = BeautifulSoup(md2_to_html(content), "html.parser").get_text()
                def esc(t: str) -> str:
                    rep = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
                    for k, v in rep.items():
                        t = t.replace(k, v)
                    return t
                tex = "\\documentclass{article}\n\\usepackage[utf8]{inputenc}\n\\begin{document}\n" + esc(text_only) + "\n\\end{document}\n"
                file_content = tex.encode("utf-8")

            else:
                raise HTTPException(status_code=400, detail="Unsupported export format")

        except ImportError as e:
            raise HTTPException(status_code=501, detail=f"A required library for '{export_format}' export is missing: {e.name}")
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to generate export file: {e}")

        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
        return Response(content=file_content, media_type=media_type, headers=headers)