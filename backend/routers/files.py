import os
import shutil
import uuid
from pathlib import Path
from typing import List, Dict

from fastapi import (
    APIRouter, Depends, File, UploadFile, HTTPException
)
from fastapi.responses import FileResponse
from werkzeug.utils import secure_filename
import pipmaster
pipmaster.ensure_packages(['pypdf','python-docx', 'python-pptx', 'openpyxl'])
try:
    from pypdf import PdfReader
    import docx
    import pptx
    import openpyxl
except ImportError:
    PdfReader = None
    docx = None
    pptx = None
    openpyxl = None

from backend.session import (
    get_current_active_user, get_user_temp_uploads_path, get_user_discussion_assets_path
)
from backend.models import UserAuthDetails
from backend.config import TEMP_UPLOADS_DIR_NAME

upload_router = APIRouter(prefix="/api/upload", tags=["Uploads"])
assets_router = APIRouter()
files_router = APIRouter(prefix="/api/files", tags=["Files"])


MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_UPLOADS_PER_MESSAGE = 5

@files_router.post("/extract-text")
async def extract_text_from_files(files: List[UploadFile] = File(...), current_user: UserAuthDetails = Depends(get_current_active_user)):
    """
    Accepts multiple files, extracts text content from supported types,
    and returns the concatenated text. Code files are automatically wrapped
    in Markdown code blocks.
    """
    if not all([PdfReader, docx, pptx, openpyxl]):
        raise HTTPException(status_code=501, detail="Text extraction libraries (pypdf, python-docx, python-pptx, openpyxl) are not fully installed.")

    concatenated_text = []
    
    # Define sets of extensions for different handling
    known_code_extensions = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.java': 'java', 
        '.c': 'c', '.cpp': 'cpp', '.h': 'c', '.hpp': 'cpp', '.cs': 'csharp', 
        '.go': 'go', '.rs': 'rust', '.php': 'php', '.rb': 'ruby', '.swift': 'swift', 
        '.kt': 'kotlin', '.html': 'html', '.css': 'css', '.scss': 'scss', 
        '.json': 'json', '.xml': 'xml', '.yaml': 'yaml', '.yml': 'yaml', 
        '.ini': 'ini', '.toml': 'toml', '.cfg': 'ini', '.sh': 'bash', 
        '.bat': 'batch', '.ps1': 'powershell', '.sql': 'sql', '.dockerfile': 'dockerfile'
    }
    known_text_extensions = {'.txt', '.md', '.markdown', '.rst', '.log'}
    
    for file in files:
        temp_file_path = None
        try:
            temp_dir = get_user_temp_uploads_path(current_user.username)
            temp_file_path = temp_dir / f"{uuid.uuid4()}_{secure_filename(file.filename)}"
            
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            text = ""
            suffix = temp_file_path.suffix.lower()

            if suffix == '.pdf':
                reader = PdfReader(str(temp_file_path))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            elif suffix == '.docx':
                doc = docx.Document(str(temp_file_path))
                text = "\n".join(para.text for para in doc.paragraphs)
            elif suffix == '.pptx':
                prs = pptx.Presentation(str(temp_file_path))
                slide_texts = []
                for slide in prs.slides:
                    for shape in slide.shapes:
                        if hasattr(shape, "text"):
                            slide_texts.append(shape.text)
                text = "\n".join(slide_texts)
            elif suffix in ['.xlsx', '.xls']:
                workbook = openpyxl.load_workbook(str(temp_file_path))
                sheet_texts = []
                for sheet in workbook.worksheets:
                    for row in sheet.iter_rows():
                        cell_texts = [str(cell.value) for cell in row if cell.value is not None]
                        if cell_texts:
                            sheet_texts.append(" | ".join(cell_texts))
                text = "\n".join(sheet_texts)
            elif suffix in known_text_extensions or suffix in known_code_extensions:
                text = temp_file_path.read_text(encoding='utf-8', errors='ignore')
            else:
                try:
                    text = temp_file_path.read_text(encoding='utf-8', errors='strict')
                except (UnicodeDecodeError, Exception):
                    print(f"Skipping file with unsupported extension or non-text content: {file.filename}")
                    continue

            # --- NEW: Code Wrapping Logic ---
            if suffix in known_code_extensions:
                lang_identifier = known_code_extensions[suffix]
                formatted_text = f"--- Document: {file.filename} ---\n```{lang_identifier}\n{text}\n```"
            else:
                formatted_text = f"--- Document: {file.filename} ---\n{text}"
            
            concatenated_text.append(formatted_text)

        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Failed to process file {file.filename}: {str(e)}")
        finally:
            await file.close()
            if temp_file_path and temp_file_path.exists():
                os.remove(temp_file_path)
            
    return {"text": "\n\n".join(concatenated_text)}


@upload_router.post("/chat_image", response_model=List[Dict[str,str]])
async def upload_chat_images(files: List[UploadFile] = File(...), current_user: UserAuthDetails = Depends(get_current_active_user)):
    if len(files) > MAX_IMAGE_UPLOADS_PER_MESSAGE:
        raise HTTPException(status_code=400, detail=f"Cannot upload more than {MAX_IMAGE_UPLOADS_PER_MESSAGE} images at once.")
    
    username = current_user.username
    temp_uploads_path = get_user_temp_uploads_path(username)
    temp_uploads_path.mkdir(parents=True, exist_ok=True)
    
    uploaded_file_infos = []
    for file_upload in files:
        if not file_upload.content_type or not file_upload.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"File '{file_upload.filename}' is not a valid image type.")
        
        file_upload.file.seek(0, os.SEEK_END)
        if file_upload.file.tell() > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"Image '{file_upload.filename}' exceeds max size of {MAX_IMAGE_SIZE_MB}MB.")
        file_upload.file.seek(0)
        
        s_filename_base, s_filename_ext = os.path.splitext(secure_filename(file_upload.filename or "image"))
        if not s_filename_ext:
            s_filename_ext = ".png"
            
        final_filename = f"{s_filename_base}_{uuid.uuid4().hex[:8]}{s_filename_ext}"
        target_file_path = temp_uploads_path / final_filename
        
        try:
            with open(target_file_path, "wb") as buffer:
                shutil.copyfileobj(file_upload.file, buffer)
            uploaded_file_infos.append({"filename": file_upload.filename, "server_path": f"{TEMP_UPLOADS_DIR_NAME}/{final_filename}"})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not save uploaded image '{file_upload.filename}': {str(e)}")
        finally:
            await file_upload.close()
            
    return uploaded_file_infos

@assets_router.get("/user_assets/{username}/{discussion_id}/{filename}", include_in_schema=False)
async def get_discussion_asset(
    username: str, discussion_id: str, filename: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> FileResponse:
    if current_user.username != username:
        raise HTTPException(status_code=403, detail="Forbidden to access assets of another user.")

    asset_path = get_user_discussion_assets_path(username) / discussion_id / secure_filename(filename)
    if not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found.")
    return FileResponse(asset_path)