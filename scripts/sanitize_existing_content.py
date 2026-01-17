import sys
import os
from pathlib import Path
import bleach

# Add the project root to python path so we can import backend modules
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from backend.db import get_db, session as db_session_module
from backend.db.models.social import Post, Comment
from backend.db.models.dm import DirectMessage, Conversation

# Configuration matching the API fix
ALLOWED_TAGS = [
    'p', 'b', 'i', 'u', 'em', 'strong', 'a', 'br', 'ul', 'ol', 'li', 
    'code', 'pre', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'table', 'thead', 'tbody', 'tr', 'th', 'td', 'strike', 'hr', 'span', 'div'
]

ALLOWED_ATTRS = {
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'span': ['class'],
    'div': ['class'],
    'code': ['class'],
    'pre': ['class']
}

def sanitize_content(content: str) -> str:
    if not content:
        return content
    return bleach.clean(content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)

def run_sanitization():
    print("--- Starting Database Sanitization ---")
    
    # Initialize DB
    from backend.config import APP_DB_URL
    from backend.db import init_database
    init_database(APP_DB_URL)
    
    db = db_session_module.SessionLocal()
    
    try:
        # 1. Sanitize Posts
        print("Scanning Posts...")
        posts = db.query(Post).all()
        count = 0
        for post in posts:
            if post.content:
                clean = sanitize_content(post.content)
                if clean != post.content:
                    post.content = clean
                    count += 1
        print(f"  - Sanitized {count} Posts.")

        # 2. Sanitize Comments
        print("Scanning Comments...")
        comments = db.query(Comment).all()
        count = 0
        for comment in comments:
            if comment.content:
                clean = sanitize_content(comment.content)
                if clean != comment.content:
                    comment.content = clean
                    count += 1
        print(f"  - Sanitized {count} Comments.")

        # 3. Sanitize Direct Messages
        print("Scanning Direct Messages...")
        dms = db.query(DirectMessage).all()
        count = 0
        for dm in dms:
            if dm.content:
                clean = sanitize_content(dm.content)
                if clean != dm.content:
                    dm.content = clean
                    count += 1
        print(f"  - Sanitized {count} Direct Messages.")

        # 4. Sanitize Group Names
        print("Scanning Conversation Names...")
        convs = db.query(Conversation).all()
        count = 0
        for conv in convs:
            if conv.name:
                clean = sanitize_content(conv.name)
                if clean != conv.name:
                    conv.name = clean
                    count += 1
        print(f"  - Sanitized {count} Conversation names.")

        db.commit()
        print("--- Sanitization Complete. Database committed. ---")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_sanitization()
