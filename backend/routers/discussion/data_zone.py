# backend/routers/discussion/data_zone.py
import base64
import io
from typing import Optional, List, Dict, Any
from datetime import datetime

import fitz # PyMuPDF
from PIL import Image
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from ascii_colors import trace_exception

from backend.db import get_db
from backend.models import UserAuthDetails, DataZones, DiscussionDataZoneUpdate, TaskInfo, DiscussionImageUpdateResponse
from backend.session import get_current_active_user
from backend.task_manager import task_manager
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request
from backend.tasks.discussion_tasks import _generate_image_task, _process_data_zone_task, _memorize_ltm_task, _to_task_info

from backend.db.models.user import (User as DBUser)


def build_datazone_router(router: APIRouter):
    @router.get("/{discussion_id}/data_zones", response_model=DataZones)
    async def get_all_data_zones(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, owner_username, _, owner_db_user = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        
        discussion.memory = "\n".join(["---"+m.title+"---\n"+m.content+"\n------" for m in owner_db_user.memories]) if owner_db_user and owner_db_user.memories else ""
        
        images_info = discussion.get_discussion_images()
        
        return DataZones(
            user_data_zone=owner_db_user.data_zone if owner_db_user else "",
            discussion_data_zone=discussion.discussion_data_zone,
            personality_data_zone=discussion.personality_data_zone,
            memory=discussion.memory,
            discussion_images=[img['data'] for img in images_info],
            active_discussion_images=[img['active'] for img in images_info]
        )

    @router.get("/{discussion_id}/data_zone", response_model=Dict[str, str])
    async def get_discussion_data_zone(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        return {"content": discussion.discussion_data_zone or ""}

    @router.put("/{discussion_id}/data_zone", status_code=200)
    async def update_discussion_data_zone(
        discussion_id: str,
        payload: DiscussionDataZoneUpdate,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        
        try:
            discussion.discussion_data_zone = payload.content
            discussion.commit()
            return {"message": "Data Zone updated successfully."}
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to update Data Zone: {e}")

    @router.post("/{discussion_id}/process_data_zone", response_model=TaskInfo, status_code=202)
    async def summarize_discussion_data_zone(
        discussion_id: str,
        prompt: Optional[str] = Form(None),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, owner_username, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        
        db_task = task_manager.submit_task(
            name=f"Processing Data Zone for: {discussion.metadata.get('title', 'Untitled')}",
            target=_process_data_zone_task,
            args=(owner_username, discussion_id, prompt),
            description=f"AI is processing the discussion data zone content.",
            owner_username=current_user.username
        )
        return _to_task_info(db_task)

    @router.post("/{discussion_id}/memorize", response_model=TaskInfo, status_code=202)
    async def memorize_ltm(
        discussion_id: str,
        db: Session = Depends(get_db),
        current_user: UserAuthDetails = Depends(get_current_active_user)    
    ):
        
        discussion, owner_username, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')

        db_task = task_manager.submit_task(
            name=f"Memorize LTM for: {discussion.metadata.get('title', 'Untitled')}",
            target=_memorize_ltm_task,
            args=(owner_username, discussion_id),
            description="AI is analyzing the conversation to extract key facts for long-term memory.",
            owner_username=current_user.username
        )
        return _to_task_info(db_task)

    @router.post("/{discussion_id}/images", response_model=DiscussionImageUpdateResponse)
    async def add_discussion_image(
        discussion_id: str,
        file: UploadFile = File(...),
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')

        try:
            content_type = file.content_type
            images_b64 = []

            if content_type.startswith("image/"):
                image_bytes = await file.read()
                try:
                    img = Image.open(io.BytesIO(image_bytes))
                    if img.format == 'GIF':
                        img.seek(0)
                    if img.mode not in ('RGB', 'RGBA'):
                        img = img.convert('RGBA')
                    with io.BytesIO() as buffer:
                        img.save(buffer, format="PNG")
                        png_image_bytes = buffer.getvalue()
                    images_b64.append(base64.b64encode(png_image_bytes).decode('utf-8'))
                except Exception as e:
                    ASCIIColors.warning(f"Pillow conversion failed: {e}. Falling back to original bytes for content type {content_type}")
                    images_b64.append(base64.b64encode(image_bytes).decode('utf-8'))
            elif content_type == "application/pdf":
                pdf_bytes = await file.read()
                pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                for page_num in range(len(pdf_doc)):
                    page = pdf_doc.load_page(page_num)
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")
                    images_b64.append(base64.b64encode(img_bytes).decode('utf-8'))
                pdf_doc.close()
            else:
                raise HTTPException(status_code=400, detail="Unsupported file type. Please upload an image or a PDF.")

            for b64_data in images_b64:
                discussion.add_discussion_image(b64_data, source="user")
            
            discussion.commit()
            all_images_info = discussion.get_discussion_images()
            
            return {
                "discussion_id": discussion_id,
                "zone": "discussion_images",
                "discussion_images": [img_info['data'] for img_info in all_images_info],
                "active_discussion_images": [img_info['active'] for img_info in all_images_info]
            }
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to add file to discussion: {str(e)}")
        finally:
            await file.close()

    @router.put("/{discussion_id}/images/{image_index}/toggle", response_model=DiscussionImageUpdateResponse)
    async def toggle_discussion_image(
        discussion_id: str,
        image_index: int,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            discussion.toggle_discussion_image_activation(image_index)
            discussion.commit()

            all_images_info = discussion.get_discussion_images()
            return {
                "discussion_id": discussion_id,
                "zone": "discussion_images",
                "discussion_images": [img_info['data'] for img_info in all_images_info],
                "active_discussion_images": [img_info['active'] for img_info in all_images_info]
            }
        except IndexError:
            raise HTTPException(status_code=404, detail="Image index out of bounds.")
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to toggle image activation: {str(e)}")

    @router.delete("/{discussion_id}/images/{image_index}", response_model=Dict[str, List[Any]])
    async def delete_discussion_image_from_discussion(
        discussion_id: str,
        image_index: int,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            discussion.remove_discussion_image(image_index)
            discussion.commit()

            all_images_info = discussion.get_discussion_images()
            discussion_images_b64 = [img_info['data'] for img_info in all_images_info]
            active_discussion_images = [img_info['active'] for img_info in all_images_info]
            
            return {
                "discussion_images": discussion_images_b64,
                "active_discussion_images": active_discussion_images
            }
        except IndexError:
            raise HTTPException(status_code=404, detail="Image index out of bounds.")
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to delete image from discussion: {str(e)}")

    @router.delete("/{discussion_id}/images", response_model=Dict[str, List[Any]])
    async def delete_all_discussion_images(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        try:
            if discussion.images:
                discussion.images.clear()
            else:
                discussion.images = []
            discussion.commit()
            
            return {
                "discussion_images": [],
                "active_discussion_images": []
            }
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to delete all images from discussion: {str(e)}")