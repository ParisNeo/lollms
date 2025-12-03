# backend/routers/public.py
from pathlib import Path
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from backend.db import get_db
from backend.db.models.config import GlobalConfig
from backend.settings import settings
from backend.config import APP_VERSION

public_router = APIRouter(tags=["Public"])

@public_router.get("/api/public/ssl-status")
def get_ssl_status(db: Session = Depends(get_db)):
    https_enabled = settings.get("https_enabled", False)
    return {"is_https_enabled": https_enabled}

@public_router.get("/api/public/version")
def get_app_version():
    return {"version": APP_VERSION}

@public_router.get("/api/public/cert/download")
def download_cert(db: Session = Depends(get_db)):
    config = db.query(GlobalConfig).filter(GlobalConfig.key == "ssl_certfile").first()
    if not config:
        raise HTTPException(status_code=404, detail="Certificate path setting not found.")
    
    val_str = config.value
    # Parse potential JSON wrapper
    try:
        data = json.loads(val_str)
        if isinstance(data, dict) and 'value' in data:
            val_str = data['value']
    except:
        pass

    if not val_str:
        raise HTTPException(status_code=404, detail="Certificate path is empty.")
    
    path = Path(val_str)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Certificate file not found on server.")
        
    return FileResponse(path, media_type='application/x-pem-file', filename="lollms_cert.pem")

@public_router.get("/api/public/cert/install-script")
def download_trust_script(script_type: str, db: Session = Depends(get_db)):
    config = db.query(GlobalConfig).filter(GlobalConfig.key == "ssl_certfile").first()
    if not config:
        raise HTTPException(status_code=404, detail="Certificate not configured.")
    
    val_str = config.value
    try:
        data = json.loads(val_str)
        if isinstance(data, dict) and 'value' in data:
            val_str = data['value']
    except:
        pass

    if not val_str or not Path(val_str).exists():
        raise HTTPException(status_code=404, detail="Certificate file missing on server.")
        
    try:
        with open(val_str, 'r') as f:
            cert_content = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read certificate: {e}")

    if script_type == 'windows':
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
