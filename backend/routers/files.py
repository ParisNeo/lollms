# backend/routers/files.py
import base64
import io
import re
import shutil
import uuid
from pathlib import Path
from typing import List, Dict
import fitz  # PyMuPDF
import io, re, os, tempfile, base64
from typing import Dict
import pipmaster as pm
pm.ensure_packages(["docx2python", "mdtopptx", "markdown_pdf"])

import markdown2  # pip install markdown2
from bs4 import BeautifulSoup  # pip install beautifulsoup4
from docx import Document as DocxDocument  # pip install python-docx
from docx.shared import Pt, Inches
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from pptx import Presentation  # pip install python-pptx
from pptx.util import Inches as PptxInches, Pt as PptxPt
from mdtopptx import parse_markdown as md_to_pptx_parse, create_ppt  # pip install mdtopptx
from markdown_pdf import MarkdownPdf, Section  # pip install markdown-pdf
import fitz  # PyMuPDF (indirectly used by markdown-pdf)
import requests  # pip install requests

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse, Response
from werkzeug.utils import secure_filename

from backend.session import (
    get_current_active_user, get_user_temp_uploads_path
)
from backend.models import UserAuthDetails
from backend.models.files import ContentExportRequest, ExtractionAndEmbeddingResponse
from backend.discussion import get_user_discussion
from ascii_colors import trace_exception
from backend.config import TEMP_UPLOADS_DIR_NAME
from backend.settings import settings

files_router = APIRouter(prefix="/api/files", tags=["Files"])
upload_router = APIRouter(prefix="/api/upload", tags=["Files"])
assets_router = APIRouter(prefix="/assets", tags=["Files"])

@files_router.post("/export-markdown")
async def export_as_markdown(
    content: str = Form(...),
    filename: str = Form("export.md")
):
    """
    Accepts text content and returns it as a downloadable Markdown file.
    """
    safe_filename = secure_filename(filename)
    if not safe_filename.endswith('.md'):
        safe_filename += '.md'
    
    headers = {
        'Content-Disposition': f'attachment; filename="{safe_filename}"'
    }
    return Response(content=content, media_type='text/markdown', headers=headers)

files_router = APIRouter()

# Assume 'settings' and 'ContentExportRequest' and trace_exception exist in your module

def md2_to_html(md_text: str) -> str:
    # Configure markdown2 extras to cover requested features
    extras = [
        "fenced-code-blocks",
        "tables",
        "footnotes",
        "smarty-pants",
        "strike",
        "spoiler",
        "code-friendly",
        "cuddled-lists",
        "header-ids",
        "toc"
    ]
    return markdown2.markdown(md_text, extras=extras)

def _download_image_to_temp(src: str) -> str:
    if src.startswith("data:"):
        head, b64data = src.split(",", 1)
        suffix = ".png"
        if ";base64" in head and "image/" in head:
            mime = head.split(":")[1].split(";")[0]
            ext = "." + mime.split("/")[1]
            suffix = ext
        data = base64.b64decode(b64data)
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tf.write(data)
        tf.flush(); tf.close()
        return tf.name
    r = requests.get(src, timeout=10)
    r.raise_for_status()
    ext = os.path.splitext(src)[1] or ".png"
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    tf.write(r.content)
    tf.flush(); tf.close()
    return tf.name

def html_to_docx_bytes(html: str) -> bytes:
    soup = BeautifulSoup(html, "html.parser")
    doc = DocxDocument()

    def add_inline_runs(p, node):
        for child in node.children:
            if isinstance(child, str):
                p.add_run(child)
                continue
            tag = getattr(child, "name", "").lower()
            if tag in ("strong", "b"):
                run = p.add_run(child.get_text()); run.bold = True
            elif tag in ("em", "i"):
                run = p.add_run(child.get_text()); run.italic = True
            elif tag == "code":
                run = p.add_run(child.get_text()); run.font.name = "Consolas"; run.font.size = Pt(10)
            elif tag == "a":
                text = child.get_text(); href = child.get("href") or ""
                run = p.add_run(text + f" ({href})"); run.underline = True
            else:
                add_inline_runs(p, child)

    def handle_block(el):
        if not getattr(el, "name", None):
            return
        name = el.name.lower()

        if name in [f"h{i}" for i in range(1, 7)]:
            lvl = int(name[1]); doc.add_heading(el.get_text(), level=min(9, lvl)); return

        if name == "p":
            p = doc.add_paragraph(); add_inline_runs(p, el); return

        if name in ("ul", "ol"):
            style = "List Bullet" if name == "ul" else "List Number"
            for li in el.find_all("li", recursive=False):
                p = doc.add_paragraph(style=style); add_inline_runs(p, li)
            return

        if name == "blockquote":
            p = doc.add_paragraph(style="Intense Quote"); add_inline_runs(p, el); return

        if name == "pre":
            code_text = el.get_text()
            p = doc.add_paragraph(); run = p.add_run(code_text)
            run.font.name = "Consolas"; run.font.size = Pt(10); return

        if name == "table":
            rows = el.find_all("tr")
            if not rows: return
            cols = rows[0].find_all(["th", "td"])
            table = doc.add_table(rows=len(rows), cols=len(cols))
            for i, row in enumerate(rows):
                cells = row.find_all(["th", "td"])
                for j, cell in enumerate(cells):
                    table.cell(i, j).text = cell.get_text()
            return

        if name == "img":
            src = el.get("src"); alt = el.get("alt") or "[image]"
            tmp = None
            try:
                tmp = _download_image_to_temp(src)
                doc.add_picture(tmp, width=Inches(5.5))
            except Exception:
                doc.add_paragraph(alt)
            finally:
                try:
                    if tmp and os.path.exists(tmp): os.unlink(tmp)
                except Exception:
                    pass
            return

        # Recurse into generic containers
        for child in el.children:
            handle_block(child)

    body = soup.body or soup
    for child in body.children:
        handle_block(child)

    bio = io.BytesIO(); doc.save(bio); return bio.getvalue()

def md_to_pdf_bytes(md_text: str, toc_level: int = 3) -> bytes:
    pdf = MarkdownPdf(toc_level=toc_level)
    pdf.add_section(Section(md_text))
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
        out_path = tf.name
    pdf.save(out_path)
    with open(out_path, "rb") as f:
        data = f.read()
    try: os.unlink(out_path)
    except Exception: pass
    return data

def md_to_pptx_bytes(md_text: str) -> bytes:
    slides = md_to_pptx_parse(md_text)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tf:
        out_path = tf.name
    create_ppt(slides, out_path)
    with open(out_path, "rb") as f:
        data = f.read()
    try: os.unlink(out_path)
    except Exception: pass
    return data

def html_wrapper(html_body: str, title: str = "Export") -> bytes:
    return f"<html><head><meta charset='utf-8'><title>{title}</title></head><body>{html_body}</body></html>".encode("utf-8")

@files_router.post("/export-content")
async def export_content(payload: ContentExportRequest):
    export_format = payload.format.lower()
    setting_key_format = 'markdown' if export_format == 'md' else export_format
    setting_key = f"export_to_{setting_key_format}_enabled"

    if not settings.get(setting_key, False):
        raise HTTPException(status_code=403, detail=f"Export to '{export_format}' is disabled by the administrator.")

    content = payload.content
    filename = f"export.{export_format}"
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
            html_content = md2_to_html(content)  # markdown2
            media_type = "text/html"
            file_content = html_wrapper(html_content, title="Export")  # consistent HTML shell

        elif export_format == 'pdf':
            media_type = "application/pdf"
            file_content = md_to_pdf_bytes(content)  # preserves headings/lists/code/images/tables

        elif export_format == 'docx':
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            html_content = md2_to_html(content)  # markdown2
            file_content = html_to_docx_bytes(html_content)  # map HTML → Word

        elif export_format == 'pptx':
            media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            file_content = md_to_pptx_bytes(content)  # Markdown slides via mdtopptx

        elif export_format == 'xlsx':
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            wb = Workbook()
            table_regex = re.compile(r'(\|.*\|(?:\r?\n|\r)?\|[-| :]*\|(?:\r?\n|\r)?(?:\|.*\|(?:\r?\n|\r)?)+)')
            tables = table_regex.findall(content)

            if tables:
                for i, table_md in enumerate(tables):
                    ws = wb.create_sheet(title=f"Table {i+1}")
                    lines = [line.strip() for line in table_md.strip().split('\n')]
                    data_rows = [line for line in lines if not re.match(r'^\|[-| :]*\|$', line)]
                    for row_idx, line in enumerate(data_rows):
                        cells = [cell.strip() for cell in line.strip('|').split('|')]
                        for col_idx, cell_text in enumerate(cells):
                            ws.cell(row=row_idx + 1, column=col_idx + 1, value=cell_text)
                    for col in ws.columns:
                        max_length = 0
                        column = get_column_letter(col[0].column)
                        for cell in col:
                            if cell.value and len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        ws.column_dimensions[column].width = (max_length + 2)
                if wb.sheetnames[0] == 'Sheet':
                    wb.remove(wb['Sheet'])
            else:
                ws = wb.active
                ws.title = "Content"
                ws['A1'] = content
                ws.column_dimensions['A'].width = 100
                ws['A1'].alignment = ws['A1'].alignment.copy(wrapText=True)

            bio = io.BytesIO(); wb.save(bio); file_content = bio.getvalue()

        elif export_format == 'epub':
            media_type = "application/epub+zip"
            html_content = md2_to_html(content)
            file_content = html_wrapper(html_content, title="Export")  # placeholder xhtml; replace with proper EPUB packaging

        elif export_format == 'odt':
            media_type = "application/vnd.oasis.opendocument.text"
            html_content = md2_to_html(content)
            file_content = html_wrapper(html_content, title="Export")  # placeholder

        elif export_format == 'rtf':
            media_type = "application/rtf"
            text = BeautifulSoup(md2_to_html(content), "html.parser").get_text()
            rtf = r"{\rtf1\ansi " + text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\par ") + "}"
            file_content = rtf.encode("utf-8", errors="ignore")

        elif export_format in ['tex', 'latex']:
            media_type = "application/x-tex"
            text = BeautifulSoup(md2_to_html(content), "html.parser").get_text()
            def esc(t: str) -> str:
                rep = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
                for k, v in rep.items(): t = t.replace(k, v)
                return t
            tex = "\\documentclass{article}\n\\usepackage[utf8]{inputenc}\n\\begin{document}\n" + esc(text) + "\n\\end{document}\n"
            file_content = tex.encode("utf-8")

        else:
            raise HTTPException(status_code=400, detail="Unsupported export format")

    except ImportError as e:
        raise HTTPException(status_code=501, detail=f"A required library for '{export_format}' export is missing: {e.name}")
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to generate export file: {e}")

    headers = {'Content-Disposition': f'attachment; filename=\"{filename}\"'}
    return Response(content=file_content, media_type=media_type, headers=headers)

@files_router.post("/extract_and_embed/{discussion_id}", response_model=ExtractionAndEmbeddingResponse)
async def extract_and_embed_files(
    discussion_id: str,
    files: List[UploadFile] = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    discussion = get_user_discussion(current_user.username, discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    all_extracted_text = ""
    initial_image_count = len(discussion.images)
    new_image_count = 0

    temp_img_root = get_user_temp_uploads_path(current_user.username)

    for file in files:
        filename = secure_filename(file.filename)
        content_type = file.content_type
        content = await file.read()
        
        file_text = f"\n\n--- Document: {filename} ---\n"
        
        try:
            if content_type == "application/pdf":
                with fitz.open(stream=content, filetype="pdf") as doc:
                    for page_num, page in enumerate(doc):
                        file_text += f"\n--- Page {page_num + 1} ---\n"
                        images = page.get_images(full=True)
                        for img_index, img in enumerate(images):
                            xref = img[0]
                            base_image = doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            b64_image = base64.b64encode(image_bytes).decode('utf-8')
                            discussion.add_discussion_image(b64_image)
                            new_image_count += 1
                            file_text += f"![Image from {filename}, page {page_num + 1} | Image {initial_image_count + new_image_count}]\n"
                        file_text += page.get_text("text")

            elif "wordprocessingml" in str(content_type):
                with io.BytesIO(content) as docx_file:
                    temp_img_dir = temp_img_root / f"extract_{uuid.uuid4().hex}"
                    temp_img_dir.mkdir(parents=True, exist_ok=True)
                    try:
                        docx_result = docx2python(docx_file, image_folder=str(temp_img_dir))
                        text_with_placeholders = docx_result.text
                        for img_name in docx_result.images:
                            img_path = temp_img_dir / img_name
                            if img_path.exists():
                                with open(img_path, "rb") as f:
                                    b64_image = base64.b64encode(f.read()).decode('utf-8')
                                discussion.add_discussion_image(b64_image)
                                new_image_count += 1
                                placeholder = f"----{img_name}----"
                                reference = f"\n![Image from {filename} | Image {initial_image_count + new_image_count}]\n"
                                text_with_placeholders = text_with_placeholders.replace(placeholder, reference)
                        file_text += text_with_placeholders
                    finally:
                        shutil.rmtree(temp_img_dir)

            elif "presentationml" in str(content_type):
                with io.BytesIO(content) as pptx_file:
                    prs = Presentation(pptx_file)
                    for i, slide in enumerate(prs.slides):
                        file_text += f"\n--- Slide {i + 1} ---\n"
                        for shape in slide.shapes:
                            if hasattr(shape, "text") and shape.text.strip():
                                file_text += shape.text + "\n"
                            if hasattr(shape, "image"): # shape.shape_type == 13 (Picture)
                                image = shape.image
                                image_bytes = image.blob
                                b64_image = base64.b64encode(image_bytes).decode('utf-8')
                                discussion.add_discussion_image(b64_image)
                                new_image_count += 1
                                file_text += f"![Image from {filename}, slide {i+1} | Image {initial_image_count + new_image_count}]\n"
            else:
                try:
                    file_text += content.decode('utf-8')
                except UnicodeDecodeError:
                    file_text += "[Could not decode file as text]"

            file_text += f"\n--- End Document: {filename} ---\n"
            all_extracted_text += file_text

        except Exception as e:
            trace_exception(e)
            all_extracted_text += f"\n\n--- Error processing {filename}: {str(e)} ---\n\n"

    discussion.discussion_data_zone = all_extracted_text + (discussion.discussion_data_zone or "")
    discussion.commit()
    all_images_info = discussion.get_discussion_images()

    return ExtractionAndEmbeddingResponse(
        text_content=discussion.discussion_data_zone,
        discussion_images=[img_info['data'] for img_info in all_images_info],
        active_discussion_images=[img_info['active'] for img_info in all_images_info]
    )

@upload_router.post("/chat_image", response_model=List[Dict[str, str]])
async def upload_chat_image(
    files: List[UploadFile] = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """Handles image uploads specifically for attaching to a chat message before sending."""
    temp_path = get_user_temp_uploads_path(current_user.username)
    uploaded_files = []
    for file in files:
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Only image files are allowed.")
        
        s_filename = secure_filename(file.filename)
        # Use a more unique name to avoid collisions
        unique_filename = f"{uuid.uuid4().hex[:8]}_{s_filename}"
        file_path = temp_path / unique_filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        uploaded_files.append({"filename": s_filename, "server_path": unique_filename})
        
    return uploaded_files