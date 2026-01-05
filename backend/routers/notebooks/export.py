# backend/routers/notebooks/export.py
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
import json
import os
import io
import zipfile
import traceback
from pathlib import Path
from werkzeug.utils import secure_filename
from backend.db import get_db
from backend.db.models.notebook import Notebook as DBNotebook
from backend.models import UserAuthDetails, TaskInfo
from backend.session import get_current_active_user, get_user_notebook_assets_path

# Try imports for PDF generation and auto-install if missing
try:
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    import textwrap
except ImportError:
    try:
        import pipmaster as pm
        pm.install("reportlab")
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        import textwrap
    except:
        canvas = None

router = APIRouter()

def _get_image_path(assets_path: Path, slide: dict) -> str:
    """Helper to resolve local image path from slide data"""
    if not slide.get('images'):
        return None
    
    try:
        # Get selected image or default to first
        idx = slide.get('selected_image_index', 0)
        if idx >= len(slide['images']):
            idx = 0
            
        img_data = slide['images'][idx]
        img_url = img_data.get('path', '')
        
        # Extract filename from /api/notebooks/{id}/assets/{filename}
        if '/assets/' in img_url:
            filename = img_url.split('/assets/')[-1]
        else:
            filename = os.path.basename(img_url)
            
        local_path = assets_path / filename
        
        if local_path.exists():
            return str(local_path)
    except Exception:
        pass
    return None

@router.post("/{notebook_id}/generate_video", response_model=TaskInfo)
def generate_video_endpoint(
    notebook_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Starts a background task to generate a video presentation from the slides."""
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    
    from backend.task_manager import task_manager
    from backend.tasks.notebook_tasks.slides_making import generate_presentation_video_task
    
    return task_manager.submit_task(
        name=f"Generate Video: {notebook.title}",
        target=generate_presentation_video_task,
        args=(current_user.username, notebook_id),
        description="Rendering video with TTS...",
        owner_username=current_user.username
    )

@router.get("/{notebook_id}/export")
def export_notebook(
    notebook_id: str,
    format: str = "json",
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Exports the entire notebook to JSON, PDF, PPTX, or ZIP (images)."""
    notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id, DBNotebook.owner_user_id == current_user.id).first()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found.")

    assets_path = get_user_notebook_assets_path(current_user.username, notebook_id)

    if format == "json":
        data = { 
            "title": notebook.title, 
            "type": notebook.type, 
            "language": notebook.language,
            "content": notebook.content, 
            "tabs": notebook.tabs, 
            "artefacts": notebook.artefacts 
        }
        return Response(content=json.dumps(data, indent=2), media_type="application/json", headers={"Content-Disposition": f"attachment; filename={secure_filename(notebook.title)}.json"})
    
    elif format == "zip":
        try:
            mem_zip = io.BytesIO()
            with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                for tab in notebook.tabs:
                    if tab['type'] == 'slides' and tab.get('content'):
                        try:
                            slides_data = json.loads(tab['content']).get('slides_data', [])
                            for i, s in enumerate(slides_data):
                                img_path = _get_image_path(assets_path, s)
                                if img_path:
                                    safe_title = secure_filename(s.get('title', 'Untitled'))[:30]
                                    ext = os.path.splitext(img_path)[1] or ".png"
                                    arcname = f"Slide_{i+1:02d}_{safe_title}{ext}"
                                    zf.write(img_path, arcname)
                        except Exception as e:
                            print(f"Error zipping slide image: {e}")
            
            mem_zip.seek(0)
            return Response(content=mem_zip.getvalue(), media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={secure_filename(notebook.title)}_images.zip"})
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Failed to generate ZIP: {str(e)}")

    elif format == "pdf":
        if not canvas:
            raise HTTPException(status_code=501, detail="ReportLab library not installed and auto-installation failed. Cannot generate PDF.")
        
        try:
            bio = io.BytesIO()
            # Use Landscape Letter size for slide feel
            page_w, page_h = landscape(letter)
            c = canvas.Canvas(bio, pagesize=(page_w, page_h))
            
            # Draw Content
            has_content = False
            for tab in notebook.tabs:
                # Handle Slides
                if tab['type'] == 'slides' and tab.get('content'):
                    try:
                        slides_data = json.loads(tab['content']).get('slides_data', [])
                        for s in slides_data:
                            has_content = True
                            c.setFillColorRGB(1, 1, 1)
                            c.rect(0, 0, page_w, page_h, fill=1)
                            
                            img_path = _get_image_path(assets_path, s)
                            layout = s.get('layout', 'TitleImageBody')
                            title = s.get('title', '')
                            bullets = s.get('bullets', [])
                            
                            # -- Image Only Mode --
                            if layout == 'ImageOnly' and img_path:
                                try:
                                    img = ImageReader(img_path)
                                    iw, ih = img.getSize()
                                    aspect = iw / ih
                                    draw_w = page_w
                                    draw_h = page_w / aspect
                                    if draw_h > page_h:
                                        draw_h = page_h
                                        draw_w = page_h * aspect
                                    x = (page_w - draw_w) / 2
                                    y = (page_h - draw_h) / 2
                                    c.drawImage(img, x, y, width=draw_w, height=draw_h)
                                except Exception as e:
                                    print(f"PDF Image Error: {e}")
                            
                            # -- Standard / Hybrid Layout --
                            else:
                                c.setFillColorRGB(0, 0, 0)
                                c.setFont("Helvetica-Bold", 24)
                                c.drawString(40, page_h - 50, title)
                                
                                if img_path:
                                    try:
                                        img = ImageReader(img_path)
                                        box_x = page_w / 2 + 10
                                        box_y = 50
                                        box_w = page_w / 2 - 50
                                        box_h = page_h - 120
                                        c.drawImage(img, box_x, box_y, width=box_w, height=box_h, preserveAspectRatio=True, mask='auto')
                                    except Exception as e:
                                        print(f"PDF Image Error: {e}")

                                text_x = 40
                                text_y = page_h - 100
                                text_w = (page_w / 2 - 50) if img_path else (page_w - 80)
                                
                                c.setFont("Helvetica", 16)
                                for b in bullets:
                                    if not b: continue
                                    max_chars = int(text_w / 7)
                                    lines = textwrap.wrap(b, width=max_chars)
                                    c.drawString(text_x, text_y, "•")
                                    for line in lines:
                                        c.drawString(text_x + 15, text_y, line)
                                        text_y -= 24
                                        if text_y < 40: break
                                    text_y -= 12
                                    if text_y < 40: break

                            c.showPage()
                    except Exception as e:
                        print(f"Slide processing error: {e}")
                
                # Handle standard Markdown tabs
                elif tab['type'] == 'markdown' and tab.get('content'):
                    has_content = True
                    c.setFont("Helvetica-Bold", 20)
                    c.drawString(40, page_h - 50, tab.get('title', 'Draft'))
                    c.setFont("Helvetica", 12)
                    text_y = page_h - 80
                    lines = tab['content'].split('\n')
                    for line in lines:
                        wrapped = textwrap.wrap(line, width=100)
                        for w_line in wrapped:
                            c.drawString(40, text_y, w_line)
                            text_y -= 15
                            if text_y < 40:
                                c.showPage()
                                text_y = page_h - 50
                    c.showPage()
            
            if not has_content:
                c.drawString(100, 100, "No content found to export.")
                c.showPage()
                
            c.save()
            bio.seek(0)
            return Response(content=bio.getvalue(), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={secure_filename(notebook.title)}.pdf"})
            
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

    elif format == "pptx":
        try:
            from pptx import Presentation
            from pptx.util import Inches, Pt
            
            prs = Presentation()
            prs.slide_width = Inches(13.3333)
            prs.slide_height = Inches(7.5)
            
            for tab in notebook.tabs:
                if tab['type'] == 'slides' and tab.get('content'):
                    try:
                        slides_data = json.loads(tab['content']).get('slides_data', [])
                        for s in slides_data:
                            img_path = _get_image_path(assets_path, s)
                            layout_mode = s.get('layout', 'TitleImageBody')
                            slide = None
                            
                            if layout_mode == 'ImageOnly' and img_path:
                                slide = prs.slides.add_slide(prs.slide_layouts[6])
                                slide.shapes.add_picture(img_path, 0, 0, width=prs.slide_width, height=prs.slide_height)
                            elif layout_mode == 'TitleOnly':
                                slide = prs.slides.add_slide(prs.slide_layouts[5])
                                slide.shapes.title.text = s.get('title', '')
                            else:
                                slide = prs.slides.add_slide(prs.slide_layouts[1])
                                if slide.shapes.title: 
                                    slide.shapes.title.text = s.get('title', '')
                                if len(slide.placeholders) > 1:
                                    tf = slide.placeholders[1].text_frame
                                    tf.text = ""
                                    for bullet in s.get('bullets', []):
                                        p = tf.add_paragraph()
                                        p.text = bullet
                                if img_path:
                                    if len(slide.placeholders) > 1:
                                        slide.placeholders[1].width = Inches(6)
                                    slide.shapes.add_picture(img_path, Inches(6.5), Inches(1.5), height=Inches(5))

                            if s.get('notes') and slide:
                                slide.notes_slide.notes_text_frame.text = s['notes']
                                
                    except Exception as e:
                        print(f"Error adding slide to PPTX: {e}")
            
            bio = io.BytesIO()
            prs.save(bio)
            return Response(content=bio.getvalue(), media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", headers={"Content-Disposition": f"attachment; filename={secure_filename(notebook.title)}.pptx"})
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=400, detail="Invalid format")
