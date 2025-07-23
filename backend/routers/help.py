# backend/routers/help.py
import os
import re # NEW IMPORT for stripping markdown
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import PlainTextResponse
from backend.models import UserAuthDetails
from backend.session import get_current_active_user
from typing import List, Dict

help_router = APIRouter(prefix="/api/help", tags=["Help & Documentation"])

HELP_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "markdown" / "help"
HELP_INDEX_FILE = HELP_DOCS_DIR / "help_index.md"
ADMIN_HELP_FILE = HELP_DOCS_DIR / "admin_specific_help.md" # New constant for admin file

@help_router.get("/keywords", response_model=List[Dict[str, str]])
async def get_data_zone_keywords():
    """
    Returns a list of available dynamic keywords for use in data zones.
    """
    return [
        {"keyword": "{{date}}", "description": "The current server date (e.g., 2025-07-23)."},
        {"keyword": "{{time}}", "description": "The current server time (e.g., 23:06:51)."},
        {"keyword": "{{ip_address}}", "description": "Your public IP address as seen by the server."},
        {"keyword": "{{user_name}}", "description": "Your registered username."},
        {"keyword": "{{user_email}}", "description": "Your registered email address."},
    ]

def _get_markdown_content(file_path: Path) -> str:
    """Helper to safely read a markdown file."""
    if not file_path.is_file():
        return ""
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception:
        return f"Error reading help file: {file_path.name}"

@help_router.get("/index", response_class=PlainTextResponse)
async def get_help_index():
    """
    Returns the markdown content of the help_index.md file,
    which lists available help topics and their associated files/sections.
    """
    if not HELP_INDEX_FILE.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Help index file not found.")
    
    return _get_markdown_content(HELP_INDEX_FILE)

@help_router.get("/topic", response_class=PlainTextResponse)
async def get_help_topic_content(
    topic_filename: str = Query(..., description="Filename of the help topic (e.g., 'level_0_beginner.md')"),
    section_id: str = Query(None, description="Optional section ID within the topic to highlight or link to"),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Returns the markdown content for a specific help topic file.
    Dynamically appends admin-specific help if the user is an admin.
    """
    # Prevent path traversal vulnerabilities
    if ".." in topic_filename or "/" in topic_filename or "\\" in topic_filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid topic filename.")

    # Determine which files are accessible based on user's role/level
    allowed_files = set()
    if HELP_INDEX_FILE.is_file():
        index_content = _get_markdown_content(HELP_INDEX_FILE)
        for line in index_content.splitlines():
            if line.strip().startswith("- [") and "](help/" in line:
                # Extract filename from markdown link format - [Title](help/filename.md#section)
                match = re.search(r'\]\(help\/([^\)#]+)', line) # Simpler regex to get filename
                if match:
                    allowed_files.add(match.group(1))

    # Explicitly allow level-based files (as they are the base content)
    allowed_files.add("level_0_beginner.md")
    allowed_files.add("level_2_intermediate.md")
    allowed_files.add("level_4_expert.md")
    
    # admin_specific_help.md is *not* in allowed_files because it's not a standalone topic
    # but appended dynamically.

    if topic_filename not in allowed_files:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this help topic is forbidden.")

    file_path = HELP_DOCS_DIR / topic_filename
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Help topic file not found.")

    base_content = _get_markdown_content(file_path)
    
    # Dynamically append admin-specific help if user is admin
    if current_user.is_admin:
        admin_content = _get_markdown_content(ADMIN_HELP_FILE)
        if admin_content:
            base_content += f"\n\n---\n\n{admin_content}" # Add a separator

    return PlainTextResponse(base_content, media_type="text/markdown")

@help_router.get("/search", response_class=PlainTextResponse)
async def search_help_topics(
    query: str = Query(..., min_length=2, description="Search query for help topics"),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Searches through help topics and returns a combined markdown document with relevant sections.
    """
    search_results_content = "# Search Results\n\n"
    
    # Files to search (controlled by role/level for relevance and combining admin content)
    files_to_search_base = []
    
    # Base level files
    files_to_search_base.append("level_0_beginner.md")
    if current_user.user_ui_level >= 2:
        files_to_search_base.append("level_2_intermediate.md")
    if current_user.user_ui_level >= 4:
        files_to_search_base.append("level_4_expert.md")
    
    found_any = False
    
    for filename in set(files_to_search_base): # Use set to avoid duplicates
        file_path = HELP_DOCS_DIR / filename
        if file_path.is_file():
            content = _get_markdown_content(file_path)
            
            # Add admin-specific content if this is a top-level help file and user is admin
            if current_user.is_admin and filename == f"level_{current_user.user_ui_level}_expert.md": # Or whichever is the highest level base file
                 admin_content = _get_markdown_content(ADMIN_HELP_FILE)
                 if admin_content:
                    content += f"\n\n---\n\n{admin_content}"

            # Simple substring search (can be improved with regex/indexing for production)
            # This logic attempts to find full sections relevant to the query
            
            # Using regex to capture headings and their content
            # This regex captures sections starting with any level of heading and ending before the next heading or end of string.
            # It also handles potential '---' separators for combining content.
            sections_regex = re.compile(r'^(#+ .*?)(?:\n(.*?))?(?=\n#+ |\n---|$)', re.DOTALL | re.MULTILINE)
            
            matches = sections_regex.findall(content)
            
            relevant_sections = []
            
            for heading_line, section_body in matches:
                full_section_text = heading_line + "\n" + section_body if section_body else heading_line
                if query.lower() in full_section_text.lower():
                    # Preserve original heading level by just joining them
                    relevant_sections.append(full_section_text.strip())

            if relevant_sections:
                # Add a sub-heading indicating which original file these results came from
                search_results_content += f"## From '{filename.replace('.md', '').replace('_', ' ').title()}'\n\n"
                search_results_content += "\n\n---\n\n".join(relevant_sections) + "\n\n"
                found_any = True
    
    if not found_any:
        search_results_content += "No results found for your query. Please try a different search term."

    return PlainTextResponse(search_results_content, media_type="text/markdown")