# [UPDATE] backend/routers/admin/settings_management.py
import json
import base64
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.db.models.config import GlobalConfig as DBGlobalConfig
from backend.models import UserAuthDetails, GlobalConfigPublic, GlobalConfigUpdate
from backend.ws_manager import manager
from backend.settings import settings
from ascii_colors import trace_exception

settings_management_router = APIRouter()

@settings_management_router.get("/settings", response_model=List[GlobalConfigPublic])
async def admin_get_global_settings(db: Session = Depends(get_db)):
    db_configs = db.query(DBGlobalConfig).order_by(DBGlobalConfig.category, DBGlobalConfig.key).all()
    response_models = []
    for config in db_configs:
        try:
            stored_data = json.loads(config.value)
            if isinstance(stored_data, str):
                stored_data = json.loads(stored_data)
            response_models.append(GlobalConfigPublic(
                key=config.key,
                value=stored_data.get('value'),
                type=stored_data.get('type', 'unknown'),
                description=config.description,
                category=config.category,
            ))
        except (json.JSONDecodeError, TypeError):
            response_models.append(GlobalConfigPublic(
                key=config.key, value=None, type='error',
                description=f"Error parsing value: {config.value}",
                category=config.category,
            ))
    return response_models

@settings_management_router.put("/settings", response_model=Dict[str, str])
async def admin_update_global_settings(
    update_data: GlobalConfigUpdate,
    db: Session = Depends(get_db)
):
    updated_keys = []
    try:
        for key, new_value in update_data.configs.items():
            db_config = db.query(DBGlobalConfig).filter(DBGlobalConfig.key == key).first()
            if db_config:
                if key == 'smtp_password' and not new_value:
                    continue
                
                try:
                    stored_data = json.loads(db_config.value)
                    if not isinstance(stored_data, dict) or 'type' not in stored_data:
                        stored_data = {'type': 'string', 'value': stored_data}
                except (json.JSONDecodeError, TypeError):
                    stored_data = {'type': 'string', 'value': db_config.value}
                
                stored_data['value'] = new_value
                db_config.value = json.dumps(stored_data)
                updated_keys.append(key)

        if updated_keys:
            db.commit()
            settings.refresh(db)
            manager.broadcast_sync({"type": "settings_updated"})
        
        return {"message": f"Successfully updated {len(updated_keys)} settings."}
    except Exception as e:
        db.rollback()
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@settings_management_router.post("/upload-logo", response_model=Dict[str, str])
async def upload_custom_logo(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type.")

    db = next(get_db())
    try:
        image_bytes = await file.read()
        encoded_logo = base64.b64encode(image_bytes).decode("utf-8")
        logo_url = f"data:{file.content_type};base64,{encoded_logo}"
        
        db_config = db.query(DBGlobalConfig).filter(DBGlobalConfig.key == "welcome_logo_url").first()
        if db_config:
            stored_data = json.loads(db_config.value)
            stored_data['value'] = logo_url
            db_config.value = json.dumps(stored_data)
            db.commit()
            settings.refresh(db)
            manager.broadcast_sync({"type": "settings_updated"})
        
        return {"message": "Logo uploaded successfully.", "logo_url": logo_url}
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to upload logo: {e}")
    finally:
        await file.close()
        db.close()

@settings_management_router.delete("/remove-logo", response_model=Dict[str, str])
async def remove_custom_logo(db: Session = Depends(get_db)):
    db_config = db.query(DBGlobalConfig).filter(DBGlobalConfig.key == "welcome_logo_url").first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Logo setting not found.")
    
    try:
        stored_data = json.loads(db_config.value)
        stored_data['value'] = ""
        db_config.value = json.dumps(stored_data)
        db.commit()
        settings.refresh(db)
        manager.broadcast_sync({"type": "settings_updated"})
        return {"message": "Custom logo removed successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")