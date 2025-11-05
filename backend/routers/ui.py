# backend/routers/ui.py
import random
from pathlib import Path
from fastapi import FastAPI, Request, APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session, joinedload
import json

from backend.db import get_db
from backend.db.models.fun_fact import FunFact, FunFactCategory
from backend.db.models.news import NewsArticle
from backend.models.fun_fact import WelcomeInfo
from backend.settings import settings
from backend.config import APP_DATA_DIR

# This router will handle the API endpoint for fun facts.
ui_router = APIRouter()

# --- Welcome Info & Fun Facts ---
@ui_router.get("/api/welcome-info", response_model=WelcomeInfo)
async def get_welcome_info(db: Session = Depends(get_db)):
    """
    Returns welcome text, logo, slogan, and a random fun fact for the welcome page.
    """
    fact_content = "Welcome to lollms!"
    fact_color = "#3B82F6"
    fact_category = "General"

    # Fetch from regular fun facts
    fun_fact_query = db.query(FunFact).join(FunFactCategory).filter(FunFactCategory.is_active == True)
    fun_fact_count = fun_fact_query.count()
    
    # Fetch from news-based fun facts
    news_fun_facts_query = db.query(NewsArticle.fun_fact)
    news_fun_facts_count = news_fun_facts_query.count()

    total_facts = fun_fact_count + news_fun_facts_count
    if total_facts > 0:
        rand_index = random.randint(0, total_facts - 1)
        
        if rand_index < fun_fact_count:
            # It's a regular fun fact
            random_fact = fun_fact_query.offset(rand_index).first()
            if random_fact:
                fact_content = random_fact.content
                fact_color = random_fact.category.color
                fact_category = random_fact.category.name
        else:
            # It's a news-based fun fact
            news_index = rand_index - fun_fact_count
            random_news_fact = news_fun_facts_query.offset(news_index).first()
            if random_news_fact:
                fact_content = random_news_fact.fun_fact
                fact_color = "#F59E0B"  # A default color for news facts
                fact_category = "News"

    return WelcomeInfo(
        welcome_text=str(settings.get("welcome_text", "lollms")),
        welcome_slogan=str(settings.get("welcome_slogan", "One tool to rule them all")),
        welcome_logo_url=str(settings.get("welcome_logo_url","")),
        fun_fact=str(fact_content),
        fun_fact_color=str(fact_color),
        fun_fact_category=str(fact_category),
        latex_builder_enabled=settings.get("latex_builder_enabled", False),
        export_to_txt_enabled=settings.get("export_to_txt_enabled", True),
        export_to_markdown_enabled=settings.get("export_to_markdown_enabled", True),
        export_to_html_enabled=settings.get("export_to_html_enabled", True),
        export_to_pdf_enabled=settings.get("export_to_pdf_enabled", False),
        export_to_docx_enabled=settings.get("export_to_docx_enabled", False),
        export_to_xlsx_enabled=settings.get("export_to_xlsx_enabled", False),
        export_to_pptx_enabled=settings.get("export_to_pptx_enabled", False),
    )

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