# backend/routers/help.py
import os
import re
from pathlib import Path
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import PlainTextResponse

from backend.models import UserAuthDetails
from backend.session import get_current_active_user
from backend.config import PROJECT_ROOT

help_router = APIRouter(prefix="/api/help", tags=["Help & Documentation"])

# Robust path resolution
HELP_DOCS_DIR = (PROJECT_ROOT / "docs" / "markdown" / "help").resolve()
HELP_INDEX_FILE = HELP_DOCS_DIR / "help_index.md"
ADMIN_HELP_FILE = HELP_DOCS_DIR / "admin_specific_help.md"

# --- DEFAULT CONTENT FOR BOOTSTRAPPING ---
DEFAULT_HELP_CONTENT = {
    "help_index.md": """# LoLLMs Help Center
Welcome to the Documentation Portal. LoLLMs is a multi-modal AI orchestration platform.

### 🚀 Getting Started
*   [**Beginner's Guide**](level_0_beginner.md) - The basics of chatting and basic settings.
*   [**Understanding Personalities**](level_0_beginner.md#personalities) - How to use AI personas.

### 🛠️ Core Features
*   [**Intermediate Guide**](level_2_intermediate.md) - RAG (Data Stores), Image Generation, and Social.

### ⚡ Power Usage
*   [**Expert Guide**](level_4_expert.md) - For developers. Bindings, Models, and APIs.

### 🛡️ Administration
*   [**Administrator Guide**](admin_specific_help.md) - Server management and security.
""",
    "level_0_beginner.md": """# Beginner's Guide to LoLLMs
Welcome! This guide covers the basics.
## 1. The Main Chat
Type your questions at the bottom. Click the square icon to stop generation.
## 2. Personalities
Click the personality name in the top header to change behavior.
""",
    "level_2_intermediate.md": """# Intermediate Guide
## 1. Data Stores (RAG)
Go to **Data Stores** to upload PDFs. Then 'Mount' the store in your chat.
## 2. Image Generation
Ask the AI to "Draw a picture of..." if a TTI engine is configured.
""",
    "level_4_expert.md": """# Expert & Developer Guide
## 1. Managing Bindings
Increase Context Size in Settings > Bindings to remember longer chats.
## 2. API Access
LoLLMs is OpenAI-compatible. Use your API Key at `http://[IP]:9642/v1`.
""",
    "admin_specific_help.md": """# Administrator Guide
## 1. Dashboard
Monitor hardware usage and terminate processes directly.
## 2. Security
Enable HTTPS in **Settings > Server Settings**.
"""
}

def ensure_help_files():
    """Bootstraps the help directory if files are missing."""
    if not HELP_DOCS_DIR.exists():
        HELP_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, content in DEFAULT_HELP_CONTENT.items():
        file_path = HELP_DOCS_DIR / filename
        if not file_path.exists():
            file_path.write_text(content, encoding="utf-8")
            print(f"INFO [Help]: Bootstrapped {filename}")

ensure_help_files()

def _get_markdown_content(file_path: Path) -> str:
    if not file_path.is_file():
        return ""
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"ERROR [Help]: Failed to read {file_path}: {e}")
        return f"Error reading help file: {str(e)}"

@help_router.get("/keywords", response_model=List[Dict[str, str]])
async def get_data_zone_keywords():
    return [
        {"keyword": "{{date}}", "description": "Current date (YYYY-MM-DD)."},
        {"keyword": "{{time}}", "description": "Current time (HH:MM:SS)."},
        {"keyword": "{{user_name}}", "description": "Your username."},
    ]

@help_router.get("/index", response_class=PlainTextResponse)
async def get_help_index():
    if not HELP_INDEX_FILE.is_file():
        raise HTTPException(status_code=404, detail="Index file missing.")
    return _get_markdown_content(HELP_INDEX_FILE)

@help_router.get("/topic", response_class=PlainTextResponse)
async def get_help_topic_content(
    topic_filename: str = Query(..., description="Filename of the help topic"),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    if not topic_filename.endswith(".md"):
        topic_filename += ".md"
    
    # Secure filename
    safe_filename = os.path.basename(topic_filename)
    target_path = (HELP_DOCS_DIR / safe_filename).resolve()

    # Unauthorized access check
    if not str(target_path).startswith(str(HELP_DOCS_DIR)):
        raise HTTPException(status_code=403, detail="Unauthorized.")

    if not target_path.is_file():
        print(f"ERROR [Help]: File not found at {target_path}")
        raise HTTPException(status_code=404, detail=f"File '{safe_filename}' not found.")

    content = _get_markdown_content(target_path)
    
    if current_user.is_admin and safe_filename != "admin_specific_help.md":
        if ADMIN_HELP_FILE.is_file():
            content += f"\n\n---\n\n{_get_markdown_content(ADMIN_HELP_FILE)}"

    return PlainTextResponse(content, media_type="text/markdown")

@help_router.get("/search", response_class=PlainTextResponse)
async def search_help_topics(
    query: str = Query(..., min_length=2),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    results = [f"# Search Results: {query}\n"]
    searchable = ["level_0_beginner.md", "level_2_intermediate.md", "level_4_expert.md"]
    if current_user.is_admin: searchable.append("admin_specific_help.md")

    found = False
    for filename in searchable:
        path = HELP_DOCS_DIR / filename
        if not path.is_file(): continue
        content = _get_markdown_content(path)
        sections = re.split(r'\n(?=# )', content)
        for section in sections:
            if query.lower() in section.lower():
                results.append(f"## Found in {filename.replace('.md','').title()}\n")
                results.append(section.strip() + "\n\n---\n")
                found = True
    return "\n".join(results) if found else "No results found."
