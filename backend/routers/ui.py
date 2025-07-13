from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

VUE_APP_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

def add_ui_routes(app: FastAPI):
    """
    Mounts the static files and adds the catch-all route for the Vue.js UI.
    This should be called *after* all other API routers have been included.
    """
    if VUE_APP_DIR.exists() and (VUE_APP_DIR / "index.html").exists():
        app.mount(
            "/assets",
            StaticFiles(directory=VUE_APP_DIR / "assets"),
            name="vue-assets"
        )
        
        @app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
        async def serve_vue_app(request: Request, full_path: str):
            return FileResponse(VUE_APP_DIR / "index.html")
    else:
        print("WARNING: Frontend 'dist' directory not found. The web UI will not be served.")