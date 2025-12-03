import json
import base64
import socket
import ipaddress
import datetime
from typing import List, Dict, Any
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.db.models.config import GlobalConfig as DBGlobalConfig
from backend.models import UserAuthDetails, GlobalConfigPublic, GlobalConfigUpdate, TaskInfo
from backend.ws_manager import manager
from backend.settings import settings
from ascii_colors import trace_exception
from backend.config import APP_DATA_DIR
from backend.session import get_current_admin_user
from backend.task_manager import task_manager
from backend.tasks.system_tasks import _generate_self_signed_cert_task


settings_management_router = APIRouter()

def _parse_setting_value(value_str):
    try:
        # Try to parse the stored value as our expected JSON object
        data = json.loads(value_str)
        if isinstance(data, dict) and 'value' in data:
            return data.get('value'), data.get('type', 'string')
        else:
            if isinstance(data, (dict, list)):
                return json.dumps(data), 'json'
            return data, 'string'
    except (json.JSONDecodeError, TypeError):
        return value_str, 'string'

@settings_management_router.get("/settings", response_model=List[GlobalConfigPublic])
async def admin_get_global_settings(db: Session = Depends(get_db)):
    db_configs = db.query(DBGlobalConfig).order_by(DBGlobalConfig.category, DBGlobalConfig.key).all()
    response_models = []
    for config in db_configs:
        value = config.value
        val_type = 'string'
        
        if isinstance(value, dict):
            if 'value' in value:
                val_type = value.get('type', 'string')
                value = value.get('value')
        else:
            value, val_type = _parse_setting_value(value)
        
        # Final casting for response model
        if val_type == 'boolean':
            if isinstance(value, bool):
                final_value = value
            else:
                final_value = str(value).lower() in ('true', '1', 'yes', 'on')
        elif val_type == 'integer':
            try: final_value = int(value) if value is not None else 0
            except (ValueError, TypeError): final_value = 0
        elif val_type == 'float':
            try: final_value = float(value) if value is not None else 0.0
            except (ValueError, TypeError): final_value = 0.0
        else:
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
                current_val_in_db = db_config.value
                
                if isinstance(current_val_in_db, dict) and 'type' in current_val_in_db:
                    original_type = current_val_in_db.get('type', 'string')
                else:
                    try:
                        stored_data = json.loads(current_val_in_db)
                        if isinstance(stored_data, dict) and 'type' in stored_data:
                            original_type = stored_data.get('type', 'string')
                    except (json.JSONDecodeError, TypeError):
                        pass

                final_type = original_type
                coerced_value = new_value

                if final_type == 'boolean' or isinstance(new_value, bool):
                    final_type = 'boolean'
                    if isinstance(new_value, bool):
                        coerced_value = new_value
                    else:
                        coerced_value = str(new_value).lower() in ('true', '1', 'yes', 'on')
                elif isinstance(new_value, str) and new_value.lower() in ('true', 'false') and final_type == 'boolean':
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
            try:
                if isinstance(db_config.value, dict):
                    stored_data = db_config.value
                else:
                    stored_data = json.loads(db_config.value)
            except (json.JSONDecodeError, TypeError):
                stored_data = {'type': 'string', 'value': ''}
                
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
            if isinstance(db_config.value, dict):
                stored_data = db_config.value
            else:
                stored_data = json.loads(db_config.value)
            if not isinstance(stored_data, dict):
                stored_data = {'type': 'string', 'value': ''}
        except (json.JSONDecodeError, TypeError):
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

    certs_dir = APP_DATA_DIR / "certificates"
    certs_dir.mkdir(exist_ok=True, parents=True)
    
    if not file.filename:
        filename = f"uploaded_{file_type}.pem"
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
            if isinstance(db_config.value, dict):
                stored_data = db_config.value
            else:
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

@settings_management_router.post("/generate-cert", response_model=TaskInfo, status_code=202)
async def generate_self_signed_cert(current_user: UserAuthDetails = Depends(get_current_admin_user)):
    """Starts a background task to generate a self-signed certificate."""
    db_task = task_manager.submit_task(
        name="Generate Self-Signed Certificate",
        target=_generate_self_signed_cert_task,
        description="Generating SSL certificate and private key.",
        owner_username=current_user.username
    )
    return db_task

@settings_management_router.get("/download-cert")
async def download_cert(db: Session = Depends(get_db)):
    config = db.query(DBGlobalConfig).filter(DBGlobalConfig.key == "ssl_certfile").first()
    if not config:
        raise HTTPException(status_code=404, detail="Certificate path setting not found.")
    
    val, _ = _parse_setting_value(config.value)
    if not val:
        raise HTTPException(status_code=404, detail="Certificate path is empty.")
    
    path = Path(val)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Certificate file not found on server.")
        
    return FileResponse(path, media_type='application/x-pem-file', filename="lollms_cert.pem")

@settings_management_router.get("/download-trust-script")
async def download_trust_script(script_type: str, db: Session = Depends(get_db)):
    """
    Generates and downloads a script to install the current certificate into the system trust store.
    """
    config = db.query(DBGlobalConfig).filter(DBGlobalConfig.key == "ssl_certfile").first()
    if not config:
        raise HTTPException(status_code=404, detail="Certificate not configured.")
    
    cert_path_str, _ = _parse_setting_value(config.value)
    if not cert_path_str or not Path(cert_path_str).exists():
        raise HTTPException(status_code=404, detail="Certificate file missing on server.")
        
    try:
        with open(cert_path_str, 'r') as f:
            cert_content = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read certificate: {e}")

    if script_type == 'windows':
        # Batch script for Windows using certutil
        # We use a temporary filename to avoid conflicts, then delete it.
        content = f"""@echo off
echo Installing LoLLMs Certificate to Current User Trusted Root Store...
echo Please accept the prompt if requested.
(
echo {cert_content}
) > lollms_cert_temp.crt
certutil -user -addstore "Root" lollms_cert_temp.crt
del lollms_cert_temp.crt
echo.
echo Certificate installed. You may need to restart your browser.
pause
"""
        filename = "install_lollms_cert.bat"
        media_type = "application/x-bat"
    
    elif script_type == 'linux':
        # Bash script for Linux (Debian/Ubuntu style)
        content = f"""#!/bin/bash
if [ "$EUID" -ne 0 ]
  then echo "Please run as root (e.g. sudo ./install_lollms_cert.sh)"
  exit
fi
echo "Installing Certificate..."
cat <<EOF > /usr/local/share/ca-certificates/lollms_local.crt
{cert_content}
EOF
update-ca-certificates
echo "Done. You may need to restart your browser."
"""
        filename = "install_lollms_cert.sh"
        media_type = "application/x-sh"
    else:
        raise HTTPException(status_code=400, detail="Invalid script type. Use 'windows' or 'linux'.")

    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})
