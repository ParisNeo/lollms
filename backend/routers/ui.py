# backend/routers/ui.py
import random
from pathlib import Path
from fastapi import FastAPI, Request, APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session, joinedload
import json

from backend.db import get_db
from backend.db.models.fun_fact import FunFact, FunFactCategory
from backend.settings import settings
from backend.config import APP_DATA_DIR

# This router will handle the API endpoint for fun facts.
ui_router = APIRouter()

# --- Welcome Info & Fun Facts ---
@ui_router.get("/api/welcome-info", include_in_schema=True)
async def get_welcome_info(db: Session = Depends(get_db)):
    """
    Returns welcome text, logo, slogan, and a random fun fact for the welcome page.
    """
    welcome_text = settings.get("welcome_text", "lollms")
    welcome_slogan = settings.get("welcome_slogan", "One tool to rule them all")
    welcome_logo_url = settings.get("welcome_logo_url", None)

    # Fetch a random fun fact from an active category
    fun_fact_content = "Welcome to lollms!" # Default fallback
    fun_fact_color = "#3B82F6" # Default blue
    fun_fact_category = None
    try:
        active_facts = db.query(FunFact).options(joinedload(FunFact.category)).join(FunFactCategory).filter(FunFactCategory.is_active == True).all()
        if active_facts:
            selected_fact = random.choice(active_facts)
            fun_fact_content = selected_fact.content
            fun_fact_color = selected_fact.category.color
            fun_fact_category = selected_fact.category.name
    except Exception as e:
        print(f"Warning: Could not fetch a fun fact from the database. Error: {e}")

    return {
        "welcome_text": welcome_text,
        "welcome_slogan": welcome_slogan,
        "welcome_logo_url": welcome_logo_url,
        "fun_fact": fun_fact_content,
        "fun_fact_color": fun_fact_color,
        "fun_fact_category": fun_fact_category
    }

@ui_router.get("/api/fun-fact", include_in_schema=True)
async def get_fun_fact(db: Session = Depends(get_db)):
    """
    Returns a random fun fact about LoLLMs from an active category.
    """
    fun_fact_content = "Welcome to lollms!"
    try:
        active_facts = db.query(FunFact).join(FunFactCategory).filter(FunFactCategory.is_active == True).all()
        if active_facts:
            fun_fact_content = random.choice(active_facts).content
    except Exception as e:
        print(f"Warning: Could not fetch a fun fact from the database. Error: {e}")

    return {"fun_fact": fun_fact_content}
# --- End Welcome Info & Fun Facts ---

# This part remains for serving the static files
STATIC_DIR = Path(__file__).parent.parent.parent / "frontend/dist"

def add_ui_routes(app):
    @app.get("/user_assets/logo", include_in_schema=False)
    async def get_custom_logo():
        logo_path = Path(APP_DATA_DIR) / "assets" / "logo.png"
        if logo_path.is_file():
            return FileResponse(str(logo_path))
        raise HTTPException(status_code=404, detail="Custom logo not found.")

    @app.get("/{full_path:path}", response_class=FileResponse, include_in_schema=False)
    async def serve_vue_app(full_path: str):
        path = STATIC_DIR / full_path
        if path.exists() and not path.is_dir():
            return FileResponse(path)
        
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        
        # Fallback for SPA routing
        return FileResponse(STATIC_DIR / "index.html")