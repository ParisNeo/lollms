# backend/migration_utils.py
import os
import shutil
import base64
import io
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from PIL import Image

from backend.database_setup import User as LollmsUser, get_db as get_lollms_db
from backend.security import get_password_hash
from backend.session import get_user_data_root
from lollms_client import LollmsDiscussion

# --- Helper Functions ---

def _fetch_and_process_icon(image_url: str) -> str | None:
    """Downloads an image, resizes it, and converts it to a Base64 data URI."""
    if not image_url or not image_url.startswith(('http', '/')):
        return None
    
    try:
        if image_url.startswith('/'):
            # This needs to be configured if OpenWebUI is not at localhost
            image_url = f"http://localhost:8080{image_url}"

        print(f"    - Fetching icon: {image_url}")
        response = requests.get(image_url, timeout=10, stream=True)
        response.raise_for_status()

        image = Image.open(io.BytesIO(response.content))
        image.thumbnail((128, 128))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        base64_encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{base64_encoded}"
    except Exception as e:
        print(f"    - WARNING: Could not process icon from {image_url}. Error: {e}")
    return None

def _migrate_discussions_for_user(user_name: str, openwebui_user_id: str, temp_dir: Path):
    """Migrates all discussions for a single user."""
    print(f"  - Searching for discussion database for user ID: {openwebui_user_id}")
    
    # OpenWebUI names discussion dbs like `discussions_db_13d71e21-....`
    discussion_db_path = None
    for f in temp_dir.iterdir():
        if f.name.startswith("discussions_") and openwebui_user_id in f.name:
            discussion_db_path = f
            break
            
    if not discussion_db_path:
        print(f"  - INFO: No discussion database found for user '{user_name}'. Skipping discussion migration.")
        return 0

    print(f"  - Found discussion DB: {discussion_db_path.name}. Processing...")
    discussion_engine = create_engine(f"sqlite:///{discussion_db_path}")
    DiscussionSession = sessionmaker(bind=discussion_engine)
    discussion_session = DiscussionSession()
    
    try:
        discussions_query = text("SELECT id, discussion_metadata FROM discussions")
        messages_query = text("SELECT id, discussion_id, parent_id, sender, content, created_at FROM messages ORDER BY created_at ASC")

        discussions = discussion_session.execute(discussions_query).fetchall()
        messages = discussion_session.execute(messages_query).fetchall()
        
        messages_by_discussion: Dict[str, List[Dict[str, Any]]] = {}
        for msg in messages:
            if msg.discussion_id not in messages_by_discussion:
                messages_by_discussion[msg.discussion_id] = []
            messages_by_discussion[msg.discussion_id].append(dict(msg._mapping))

        migrated_discussions_count = 0
        for disc in discussions:
            # Create a LollmsDiscussion object
            discussion_id = disc.id
            metadata = json.loads(disc.discussion_metadata) if disc.discussion_metadata else {}
            title = metadata.get("title", f"Imported Discussion {discussion_id[:8]}")

            # Prepare the LollmsDiscussion object
            lollms_discussion = LollmsDiscussion.create_discussion(
                discussion_id=discussion_id,
                title=title
            )
            
            # Add messages to the discussion
            discussion_messages = messages_by_discussion.get(discussion_id, [])
            for msg_data in discussion_messages:
                lollms_discussion.add_message(
                    message_type=1 if msg_data["sender"].lower() == "user" else 2, # 1 for user, 2 for bot
                    content=msg_data["content"],
                    parent_message_id=msg_data["parent_id"],
                    message_id=msg_data["id"],
                    # Other fields can be added if needed
                )
            
            # Save the discussion to the user's folder
            user_discussions_path = get_user_data_root(user_name) / "discussions"
            user_discussions_path.mkdir(parents=True, exist_ok=True)
            lollms_discussion.save(user_discussions_path)
            migrated_discussions_count += 1

        print(f"  - SUCCESS: Migrated {migrated_discussions_count} discussions for user '{user_name}'.")
        return migrated_discussions_count

    except Exception as e:
        print(f"  - ERROR: Failed to migrate discussions for user '{user_name}'. Error: {e}")
        return 0
    finally:
        discussion_session.close()

# --- Main Migration Function ---

def run_openwebui_migration(temp_dir_str: str):
    """
    Main background task to perform the full OpenWebUI migration.
    
    Args:
        temp_dir_str: The string path to the temporary directory with uploaded DB files.
    """
    temp_dir = Path(temp_dir_str)
    print("\n--- Background OpenWebUI Migration Process Started ---")
    
    # Find the main user database file
    db_path = temp_dir / "database.db"
    if not db_path.exists():
        print("CRITICAL: 'database.db' not found in uploaded files. Aborting migration.")
        shutil.rmtree(temp_dir)
        return

    source_engine = create_engine(f"sqlite:///{db_path}")
    SourceSession = sessionmaker(bind=source_engine)
    source_session = SourceSession()
    
    lollms_db_session = next(get_lollms_db())

    try:
        source_users_query = text("SELECT id, name, email, password, role, profile_image_url, created_at, last_active_at FROM users")
        source_users = source_session.execute(source_users_query).fetchall()
        
        print(f"INFO: Found {len(source_users)} users in 'database.db'.")
        migrated_users_count = 0
        skipped_users_count = 0

        for user in source_users:
            print(f"\nProcessing user: {user.name} ({user.email})")
            
            # Check if user already exists
            existing_user = lollms_db_session.query(LollmsUser).filter(LollmsUser.email == user.email).first()
            if existing_user:
                print("  - INFO: User already exists. Skipping user data migration.")
                skipped_users_count += 1
                _migrate_discussions_for_user(existing_user.username, user.id, temp_dir)
                continue

            # Migrate user data
            icon_b64 = _fetch_and_process_icon(user.profile_image_url)
            password_hash_with_marker = f"argon2_hash:{user.password}"
            
            new_lollms_user = LollmsUser(
                username=user.name,
                email=user.email,
                hashed_password=password_hash_with_marker,
                is_admin=(user.role == 'admin'),
                is_active=True,
                created_at=user.created_at or datetime.utcnow(),
                last_activity_at=user.last_active_at,
                icon=icon_b64
            )
            
            lollms_db_session.add(new_lollms_user)
            try:
                lollms_db_session.commit()
                print(f"  - SUCCESS: Migrated user '{user.name}'.")
                migrated_users_count += 1
                # Now migrate their discussions
                _migrate_discussions_for_user(new_lollms_user.username, user.id, temp_dir)

            except IntegrityError as e:
                lollms_db_session.rollback()
                print(f"  - ERROR: Failed to insert user '{user.name}'. Username might be a duplicate. Skipping. Error: {e.orig}")
                skipped_users_count += 1
            
            time.sleep(0.1)

        print("\n--- Migration Task Finished ---")
        print(f"Migrated users: {migrated_users_count}")
        print(f"Skipped users: {skipped_users_count}")

    except Exception as e:
        print(f"CRITICAL: An uncaught error occurred during migration. {e}")
    finally:
        source_session.close()
        lollms_db_session.close()
        # Clean up the temporary directory
        shutil.rmtree(temp_dir)
        print(f"INFO: Cleaned up temporary directory: {temp_dir}")