# backend/routers/static.py
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.services.auth_service import get_current_active_user, get_current_admin_user, UserAuthDetails
from backend.utils.path_helpers import get_user_discussion_assets_path, secure_filename
from backend.config import STATIC_FILES_PATH, LOCALES_PATH # project_root

static_router = APIRouter()

# Serve index.html from project root
@static_router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index_html(request: Request) -> FileResponse:
    index_path = STATIC_FILES_PATH / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="index.html not found.")
    return FileResponse(index_path)

# Serve admin.html from project root (requires admin login)
@static_router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def serve_admin_panel_page(admin_user: UserAuthDetails = Depends(get_current_admin_user)) -> FileResponse:
    admin_html_path = STATIC_FILES_PATH / "admin.html"
    if not admin_html_path.is_file():
        raise HTTPException(status_code=404, detail="admin.html not found.")
    return FileResponse(admin_html_path)

# Serve favicon.ico from project root
@static_router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    favicon_path = STATIC_FILES_PATH / "favicon.ico"
    return FileResponse(favicon_path, media_type="image/x-icon") if favicon_path.is_file() else Response(status_code=204)

# Serve logo.png from project root
@static_router.get("/logo.png", include_in_schema=False)
async def logo() -> Response:
    logo_path = STATIC_FILES_PATH / "logo.png"
    return FileResponse(logo_path, media_type="image/png") if logo_path.is_file() else Response(status_code=404)

# User assets (requires authentication)
@static_router.get("/user_assets/{username}/{discussion_id}/{filename}", include_in_schema=False)
async def get_discussion_asset(
    username: str, 
    discussion_id: str, 
    filename: str, 
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> FileResponse:
    if current_user.username != username: # Only allow access to own assets
        raise HTTPException(status_code=403, detail="Forbidden to access assets of another user.")
    
    # Use secure_filename on the filename part
    s_filename = secure_filename(filename)
    asset_path = get_user_discussion_assets_path(username) / discussion_id / s_filename
    
    if not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found.")
    return FileResponse(asset_path)

# Function to mount static directories (like locales)
# This will be called in main.py's app setup
def mount_static_directories(app):
    if LOCALES_PATH.is_dir():
        app.mount("/locales", StaticFiles(directory=LOCALES_PATH, html=False), name="locales")
        print(f"INFO: Mounted /locales from {LOCALES_PATH}")
    else:
        print(f"WARNING: 'locales' directory not found at {LOCALES_PATH}.")