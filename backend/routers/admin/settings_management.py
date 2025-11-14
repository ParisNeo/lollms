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
        value = config.value
        val_type = 'string'
        
        try:
            # Try to parse the stored value as our expected JSON object
            data = json.loads(value)
            if isinstance(data, dict) and 'value' in data:
                value = data.get('value')
                val_type = data.get('type', 'string')
            else:
                # It's JSON, but not our format. To prevent sending an object,
                # we can either stringify it or, if it's not a dict/list, use it directly.
                if isinstance(data, (dict, list)):
                    print(f"WARNING: Setting '{config.key}' has an unexpected format. Treating as a raw JSON string.")
                    value = json.dumps(data)
                else:
                    value = data
        except (json.JSONDecodeError, TypeError):
            # Not JSON, treat the raw value as a string. `value` is already config.value.
            pass
        
        # Final casting for response model to ensure correct types are sent
        if val_type == 'boolean':
            final_value = str(value).lower() in ('true', '1', 'yes', 'on')
        elif val_type == 'integer':
            try: final_value = int(value) if value is not None else 0
            except (ValueError, TypeError): final_value = 0
        elif val_type == 'float':
            try: final_value = float(value) if value is not None else 0.0
            except (ValueError, TypeError): final_value = 0.0
        else: # string, text, json string, etc.
            final_value = value

        response_models.append(GlobalConfigPublic(
            key=config.key,
            value=final_value,
            type=val_type,
            description=config.description,
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
        all_db_configs = {c.key: c for c in db.query(DBGlobalConfig).all()}

        for key, new_value in update_data.configs.items():
            db_config = all_db_configs.get(key)
            if db_config:
                if key == 'smtp_password' and not new_value:
                    continue

                original_type = 'string'
                try:
                    stored_data = json.loads(db_config.value)
                    if isinstance(stored_data, dict) and 'type' in stored_data:
                        original_type = stored_data.get('type', 'string')
                except (json.JSONDecodeError, TypeError):
                    pass

                final_type = original_type
                coerced_value = new_value

                # Robustly handle booleans - this will fix corrupted data on save
                if final_type == 'boolean' or isinstance(new_value, bool):
                    final_type = 'boolean'
                    coerced_value = str(new_value).lower() in ('true', '1', 'yes', 'on')
                elif isinstance(new_value, str) and new_value.lower() in ('true', 'false'):
                    final_type = 'boolean'
                    coerced_value = new_value.lower() == 'true'
                elif final_type == 'integer':
                    try: coerced_value = int(new_value)
                    except (ValueError, TypeError): coerced_value = 0
                elif final_type == 'float':
                    try: coerced_value = float(new_value)
                    except (ValueError, TypeError): coerced_value = 0.0
                
                new_stored_data = {"type": final_type, "value": coerced_value}
                db_config.value = json.dumps(new_stored_data)
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
        try:
            stored_data = json.loads(db_config.value)
            if not isinstance(stored_data, dict):
                # If the stored value is corrupted (not a dict), create a fresh structure.
                stored_data = {'type': 'string', 'value': ''}
        except (json.JSONDecodeError, TypeError):
            # If it's not valid JSON at all, create a fresh structure.
            stored_data = {'type': 'string', 'value': ''}

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
