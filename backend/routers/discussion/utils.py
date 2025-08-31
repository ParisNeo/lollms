# backend/routers/discussion/utils.py
import io
import re
import zipfile
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.db.models.user import UserStarredDiscussion
from backend.models import (DiscussionInfo, MessageCodeExportRequest,
                            TaskInfo, UserAuthDetails)
from backend.discussion import get_user_discussion  
from backend.tasks.discussion_tasks import (_prune_empty_discussions_task,
                                             _to_task_info)
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request
from backend.session import get_current_active_user, get_user_lollms_client
from backend.task_manager import task_manager
from ascii_colors import trace_exception


class TokenizeRequest(BaseModel):
    text: str

def build_utils_router(router: APIRouter):
    @router.post("/tokenize", response_model=Dict[str, int])
    async def tokenize_text(
        request: TokenizeRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user)
    ):
        """Tokenizes text using the user's current LLM client."""
        try:
            lc = get_user_lollms_client(current_user.username)
            tokens = lc.tokenize(request.text)
            return {"tokens": len(tokens)}
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to tokenize text: {e}")
        
    @router.post("/prune", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
    async def prune_empty_discussions(current_user: UserAuthDetails = Depends(get_current_active_user)):
        db_task = task_manager.submit_task(
            name=f"Prune empty discussions for {current_user.username}",
            target=_prune_empty_discussions_task,
            args=(current_user.username,),
            description="Scans and deletes discussions with 0 or 1 message.",
            owner_username=current_user.username
        )
        return _to_task_info(db_task)

    @router.post("/{discussion_id}/auto-title", response_model=DiscussionInfo)
    async def generate_discussion_auto_title(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion_obj, _, permission, owner = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            new_title = discussion_obj.auto_title()
            discussion_obj.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate title: {e}")
        
        is_starred = db.query(UserStarredDiscussion).filter_by(user_id=current_user.id, discussion_id=discussion_id).first() is not None
        metadata = discussion_obj.metadata or {}
        
        return DiscussionInfo(
            id=discussion_id,
            title=new_title,
            is_starred=is_starred,
            rag_datastore_ids=metadata.get('rag_datastore_ids'),
            active_tools=metadata.get('active_tools', []),
            active_branch_id=discussion_obj.active_branch_id,
            created_at=discussion_obj.created_at,
            last_activity_at=discussion_obj.updated_at,
            owner_username=owner.username,
            permission_level=permission
        )

    def _extract_code_files(content: str):
        code_files = []
        code_block_counter = 1
        
        code_block_pattern = re.compile(r"```(\w*)\n([\s\S]*?)\n```")
        filename_pattern = re.compile(r"^(?:----?\s*)?(?:\[(?:CREATE|UPDATE)\]\s*)?([a-zA-Z0-9_./\\-]+?\.\w+)(?:\s*----?)?$", re.MULTILINE)
        lang_ext_map = {'python': 'py', 'javascript': 'js', 'typescript': 'ts', 'html': 'html', 'css': 'css', 'json': 'json', 'xml': 'xml', 'sql': 'sql', 'bash': 'sh', 'shell': 'sh', 'text': 'txt', 'markdown': 'md', 'java': 'java', 'c++': 'cpp', 'cpp': 'cpp', 'c': 'c', 'csharp': 'cs', 'go': 'go', 'rust': 'rs', 'php': 'php', 'ruby': 'rb', 'swift': 'swift', 'kotlin': 'kt', 'yaml': 'yaml', 'yml': 'yaml'}

        parts = code_block_pattern.split(content)
        if len(parts) < 3:
            return []

        preceding_texts = parts[0::3]
        languages = parts[1::3]
        codes = parts[2::3]

        for i in range(len(codes)):
            preceding_text = preceding_texts[i]
            lang = languages[i].lower()
            code_content = codes[i]
            filename = ""

            lines_before = preceding_text.strip().split('\n')
            if lines_before:
                for line in reversed(lines_before[-5:]):
                    match = filename_pattern.match(line.strip())
                    if match:
                        filename = match.group(1).replace("\\", "/")
                        break
            
            if not filename:
                ext = lang_ext_map.get(lang, 'txt')
                filename = f"script_{code_block_counter}.{ext}"
                code_block_counter += 1
            
            code_files.append((filename, code_content))
        return code_files

    @router.get("/{discussion_id}/export-code", response_class=StreamingResponse)
    async def export_discussion_code(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user)
    ):
        username = current_user.username
        discussion_obj = get_user_discussion(username, discussion_id)
        if not discussion_obj:
            raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

        code_files = []
        code_block_counter = 1
        
        code_block_pattern = re.compile(r"```(\w*)\n([\s\S]*?)\n```")
        filename_pattern = re.compile(
            r"^(?:----?\s*)?(?:\[(?:CREATE|UPDATE)\]\s*)?([a-zA-Z0-9_./\\-]+?\.\w+)(?:\s*----?)?$",
            re.MULTILINE
        )
        lang_ext_map = {
            'python': 'py', 'javascript': 'js', 'typescript': 'ts', 'html': 'html',
            'css': 'css', 'json': 'json', 'xml': 'xml', 'sql': 'sql', 'bash': 'sh',
            'shell': 'sh', 'text': 'txt', 'markdown': 'md', 'java': 'java',
            'c++': 'cpp', 'cpp': 'cpp', 'c': 'c', 'csharp': 'cs', 'go': 'go',
            'rust': 'rs', 'php': 'php', 'ruby': 'rb', 'swift': 'swift',
            'kotlin': 'kt', 'yaml': 'yaml', 'yml': 'yaml'
        }

        all_messages_orm = discussion_obj.db_manager.get_all_messages(discussion_id)
        if not all_messages_orm:
            raise HTTPException(status_code=404, detail="No messages in discussion to export from.")

        for msg in all_messages_orm:
            if not msg.content or '```' not in msg.content:
                continue
            
            parts = code_block_pattern.split(msg.content)
            if len(parts) < 3:
                continue

            preceding_texts = parts[0::3]
            languages = parts[1::3]
            codes = parts[2::3]

            for i in range(len(codes)):
                preceding_text = preceding_texts[i]
                lang = languages[i].lower()
                code_content = codes[i]
                filename = ""

                lines_before = preceding_text.strip().split('\n')
                if lines_before:
                    for line in reversed(lines_before[-5:]):
                        match = filename_pattern.match(line.strip())
                        if match:
                            filename = match.group(1)
                            break
                
                if filename:
                    if ".." in filename or Path(filename).is_absolute():
                        filename = ""
                    else:
                        filename = filename.replace("\\", "/")

                if not filename:
                    ext = lang_ext_map.get(lang, 'txt')
                    filename = f"script_{code_block_counter}.{ext}"
                    code_block_counter += 1
                
                code_files.append((filename, code_content))

        if not code_files:
            raise HTTPException(status_code=404, detail="No valid code blocks found to export.")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filepath, content in code_files:
                zf.writestr(filepath, content)
        
        zip_buffer.seek(0)
        
        safe_title = re.sub(r'[^a-zA-Z0-9_-]', '', discussion_obj.metadata.get('title', 'discussion').replace(' ', '_'))
        zip_filename = f"code_export_{safe_title}_{discussion_id[:8]}.zip"
        
        headers = {'Content-Disposition': f'attachment; filename="{zip_filename}"'}
        return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)


    @router.post("/export-message-code", response_class=StreamingResponse)
    async def export_message_code(
        payload: MessageCodeExportRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user)
    ):
        code_files = []
        code_block_counter = 1
        
        code_block_pattern = re.compile(r"```(\w*)\n([\s\S]*?)\n```")
        filename_pattern = re.compile(
            r"^(?:----?\s*)?(?:\[(?:CREATE|UPDATE)\]\s*)?([a-zA-Z0-9_./\\-]+?\.\w+)(?:\s*----?)?$",
            re.MULTILINE
        )
        lang_ext_map = {
            'python': 'py', 'javascript': 'js', 'typescript': 'ts', 'html': 'html',
            'css': 'css', 'json': 'json', 'xml': 'xml', 'sql': 'sql', 'bash': 'sh',
            'shell': 'sh', 'text': 'txt', 'markdown': 'md', 'java': 'java',
            'c++': 'cpp', 'cpp': 'cpp', 'c': 'c', 'csharp': 'cs', 'go': 'go',
            'rust': 'rs', 'php': 'php', 'ruby': 'rb', 'swift': 'swift',
            'kotlin': 'kt', 'yaml': 'yaml', 'yml': 'yaml'
        }

        content = payload.content
        if not content or '```' not in content:
            raise HTTPException(status_code=404, detail="No code blocks found in the provided content.")

        parts = code_block_pattern.split(content)
        if len(parts) < 3:
            raise HTTPException(status_code=404, detail="No valid code blocks found in the provided content.")

        preceding_texts = parts[0::3]
        languages = parts[1::3]
        codes = parts[2::3]

        for i in range(len(codes)):
            preceding_text = preceding_texts[i]
            lang = languages[i].lower()
            code_content = codes[i]
            filename = ""

            lines_before = preceding_text.strip().split('\n')
            if lines_before:
                for line in reversed(lines_before[-5:]):
                    match = filename_pattern.match(line.strip())
                    if match:
                        filename = match.group(1)
                        break
            
            if filename:
                if ".." in filename or Path(filename).is_absolute():
                    filename = ""
                else:
                    filename = filename.replace("\\", "/")

            if not filename:
                ext = lang_ext_map.get(lang, 'txt')
                filename = f"script_{code_block_counter}.{ext}"
                code_block_counter += 1
            
            code_files.append((filename, code_content))

        if not code_files:
            raise HTTPException(status_code=404, detail="No valid code blocks found to export.")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filepath, content in code_files:
                zf.writestr(filepath, content)
        
        zip_buffer.seek(0)
        
        safe_title = re.sub(r'[^a-zA-Z0-9_-]', '', payload.discussion_title.replace(' ', '_'))
        zip_filename = f"code_export_{safe_title}.zip"
        
        headers = {'Content-Disposition': f'attachment; filename="{zip_filename}"'}
        return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)
