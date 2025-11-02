import json
import base64
from typing import List, Dict
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.db.models.config import GlobalConfig as DBGlobalConfig
from backend.models import UserAuthDetails, GlobalConfigPublic, GlobalConfigUpdate
from backend.ws_manager import manager
from backend.settings import settings
from ascii_colors import trace_exception
from backend.config import APP_DATA_DIR


settings_management_router = APIRouter()

@settings_management_router.get("/settings", response_model=List[GlobalConfigPublic])
async def admin_get_global_settings(db: Session = Depends(get_db)):
    db_configs = db.query(DBGlobalConfig).order_by(DBGlobalConfig.category, DBGlobalConfig.key).all()
    response_models = []
    for config in db_configs:
        value_to_send = None
        type_to_send = 'unknown'
        description_to_send = config.description
        
        try:
            if isinstance(config.value, str):
                stored_data = json.loads(config.value)
            elif isinstance(config.value, dict):
                stored_data = config.value
            else:
                stored_data = {'type': 'string', 'value': config.value}   
            # Defensive unpacking loop to handle corrupted, nested value objects
            while isinstance(stored_data, dict) and 'value' in stored_data and isinstance(stored_data.get('value'), dict):
                stored_data = stored_data['value']

            if isinstance(stored_data, dict) and 'value' in stored_data:
                value_to_send = stored_data.get('value')
                type_to_send = stored_data.get('type', 'string')
            else:
                value_to_send = stored_data
                if isinstance(value_to_send, bool): type_to_send = 'boolean'
                elif isinstance(value_to_send, int): type_to_send = 'integer'
                elif isinstance(value_to_send, float): type_to_send = 'float'
                else: type_to_send = 'string'

        except (json.JSONDecodeError, TypeError, AttributeError):
            value_to_send = config.value 
            type_to_send = 'string'

        response_models.append(GlobalConfigPublic(
            key=config.key,
            value=value_to_send,
            type=type_to_send,
            description=description_to_send,
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
                
                # FIX: Update ONLY the 'value' field within the stored JSON object.
                stored_data['value'] = new_value
                
                # Save the entire structured object back as a JSON string.
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

@settings_management_router.post("/upload-ssl-file", response_model=Dict[str, str])
async def upload_ssl_file(
    file: UploadFile = File(...),
    file_type: str = Form(...), # 'cert' or 'key'
    db: Session = Depends(get_db)
):
    if file_type not in ['cert', 'key']:
        raise HTTPException(status_code=400, detail="Invalid file_type. Must be 'cert' or 'key'.")

    certs_dir = APP_DATA_DIR / "certs"
    certs_dir.mkdir(exist_ok=True, parents=True)
    
    if not file.filename:
        filename = f"{file_type}.pem"
    else:
        filename = Path(file.filename).name

    file_path = certs_dir / filename

    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        file.file.close()

    setting_key = "ssl_certfile" if file_type == 'cert' else "ssl_keyfile"
    
    db_config = db.query(DBGlobalConfig).filter(DBGlobalConfig.key == setting_key).first()
    if db_config:
        try:
            stored_data = json.loads(db_config.value)
            if not isinstance(stored_data, dict) or 'type' not in stored_data:
                stored_data = {'type': 'string', 'value': stored_data}
        except (json.JSONDecodeError, TypeError):
            stored_data = {'type': 'string', 'value': db_config.value}
        
        absolute_path = str(file_path.resolve())
        stored_data['value'] = absolute_path
        db_config.value = json.dumps(stored_data)
        db.commit()
        settings.refresh(db)
        manager.broadcast_sync({"type": "settings_updated"})
        
        return {"message": f"{file_type.capitalize()} file uploaded and path updated.", "path": absolute_path}
    else:
        raise HTTPException(status_code=404, detail=f"Setting key '{setting_key}' not found.")