import random
from pathlib import Path
from fastapi import FastAPI, Request, APIRouter
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import json
# This router will handle the API endpoint for fun facts.
ui_router = APIRouter()

# --- Fun Facts ---
try:
    ff = Path(__file__).parent.parent/"assets"/"fun_facts.json"
    FUN_FACTS = json.loads(ff.read_text("utf-8"))
except Exception as ex:
    FUN_FACTS = ["No fun facts were loaded"]
@ui_router.get("/api/fun-fact", include_in_schema=True)
async def get_fun_fact():
    """
    Returns a random fun fact about LoLLMs.
    """
    return {"fun_fact": random.choice(FUN_FACTS)}
# --- End Fun Facts ---


# This part remains for serving the static files
STATIC_DIR = Path(__file__).parent.parent.parent / "frontend/dist"

def add_ui_routes(app):
    @app.get("/{full_path:path}", response_class=FileResponse, include_in_schema=False)
    async def serve_vue_app(full_path: str):
        path = STATIC_DIR/ full_path
        if path.exists() and not path.is_dir():
            return FileResponse(path)
        
        index_path = STATIC_DIR/ "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        
        return FileResponse(STATIC_DIR/ "index.html")