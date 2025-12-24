# backend/routers/ui.py
import random
import mimetypes
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.db.models.fun_fact import FunFact, FunFactCategory
from backend.db.models.news import NewsArticle
from backend.models.fun_fact import WelcomeInfo
from backend.settings import settings
from backend.config import APP_DATA_DIR

ui_router = APIRouter()

# High-quality fallback facts used if the database is unpopulated or inaccessible.
FALLBACK_FACTS = [
    {"content": "LoLLMs stands for Lord of Large Language Models.", "category": "General", "color": "#3B82F6"},
    {"content": "The platform allows you to use your own local AI models privately.", "category": "Privacy", "color": "#10B981"},
    {"content": "You can organize chats into nested groups for complex projects.", "category": "Features", "color": "#F59E0B"},
    {"content": "LoLLMs supports RAG, enabling AI to 'read' your local PDFs and documents.", "category": "Knowledge", "color": "#EF4444"},
    {"content": "The Personality Zoo contains hundreds of AI behaviors created by the community.", "category": "Community", "color": "#8B5CF6"},
    {"content": "ParisNeo created LoLLMs to provide a unified interface for all AI technologies.", "category": "History", "color": "#EC4899"}
]

@ui_router.get("/api/welcome-info", response_model=WelcomeInfo)
async def get_welcome_info(db: Session = Depends(get_db)):
    """
    Returns welcome text, logo, slogan, and a random fun fact for the welcome page.
    Prioritizes forced system announcements if enabled by an administrator.
    """
    
    # 1. Check for Forced System Message (Announcement)
    force_enabled = settings.get("force_welcome_message", False)
    if force_enabled:
        fact_content = settings.get("forced_welcome_message_content", "No content provided.")
        fact_category = settings.get("forced_welcome_message_title", "Announcement")
        fact_color = "#D97706" # Warning/Gold color for forced messages
        
        return WelcomeInfo(
            welcome_text=settings.get("welcome_text", "lollms"),
            welcome_slogan=settings.get("welcome_slogan", "One tool to rule them all"),
            welcome_logo_url=settings.get("welcome_logo_url"),
            fun_fact=fact_content,
            fun_fact_color=fact_color,
            fun_fact_category=fact_category,
            latex_builder_enabled=settings.get("latex_builder_enabled", False),
            export_to_txt_enabled=settings.get("export_to_txt_enabled", True),
            export_to_markdown_enabled=settings.get("export_to_markdown_enabled", True),
            export_to_html_enabled=settings.get("export_to_html_enabled", True),
            export_to_pdf_enabled=settings.get("export_to_pdf_enabled", False),
            export_to_docx_enabled=settings.get("export_to_docx_enabled", False),
            export_to_xlsx_enabled=settings.get("export_to_xlsx_enabled", False),
            export_to_pptx_enabled=settings.get("export_to_pptx_enabled", False),
        )

    # 2. Random Fun Fact Logic (Default)
    # Initialize with a random fallback
    fallback = random.choice(FALLBACK_FACTS)
    fact_content = fallback["content"]
    fact_color = fallback["color"]
    fact_category = fallback["category"]

    try:
        # Fetch from regular fun facts
        fun_fact_query = db.query(FunFact).join(FunFactCategory).filter(FunFactCategory.is_active == True)
        fun_fact_count = fun_fact_query.count()
        
        # Fetch from news-based fun facts
        news_fun_facts_query = db.query(NewsArticle.fun_fact).filter(NewsArticle.fun_fact != "")
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
                    fact_content = random_news_fact[0]
                    fact_color = "#F59E0B"  # A default color for news facts
                    fact_category = "Current News"
    except Exception as e:
        print(f"Warning: Failed to fetch facts from DB, using fallback. {e}")

    return WelcomeInfo(
        welcome_text=settings.get("welcome_text", "lollms"),
        welcome_slogan=settings.get("welcome_slogan", "One tool to rule them all"),
        welcome_logo_url=settings.get("welcome_logo_url"),
        fun_fact=fact_content,
        fun_fact_color=fact_color,
        fun_fact_category=fact_category,
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
    """Returns a random fun fact about LoLLMs from an active category."""
    try:
        active_facts = db.query(FunFact).join(FunFactCategory).filter(FunFactCategory.is_active == True).all()
        if active_facts:
            fact = random.choice(active_facts)
            return {"fun_fact": fact.content, "category": fact.category.name, "color": fact.category.color}
    except:
        pass
    
    fallback = random.choice(FALLBACK_FACTS)
    return {"fun_fact": fallback["content"], "category": fallback["category"], "color": fallback["color"]}

# Static file serving
STATIC_DIR = Path(__file__).parent.parent.parent / "frontend/dist"

def add_ui_routes(app):
    @app.get("/user_assets/logo", include_in_schema=False)
    async def get_custom_logo():
        logo_path = Path(APP_DATA_DIR) / "assets" / "logo.png"
        if logo_path.is_file():
            return FileResponse(str(logo_path))
        raise HTTPException(status_code=404, detail="Custom logo not found.")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_vue_app(full_path: str):
        path = STATIC_DIR / full_path
        
        try:
            resolved_path = path.resolve()
            resolved_static = STATIC_DIR.resolve()
            
            if not str(resolved_path).startswith(str(resolved_static)):
                return FileResponse(STATIC_DIR / "index.html")

            if resolved_path.exists() and resolved_path.is_file():
                media_type, _ = mimetypes.guess_type(resolved_path)
                if resolved_path.suffix == '.js':
                    media_type = 'application/javascript'
                elif resolved_path.suffix == '.css':
                    media_type = 'text/css'
                
                return FileResponse(resolved_path, media_type=media_type)
        except Exception:
            pass
        
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        
        raise HTTPException(status_code=404, detail="UI not found. Please build the frontend.")
