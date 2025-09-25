import os
import shutil
import base64
import io
import json
import time
import yaml
import uuid
from pathlib import Path
from datetime import datetime
from ascii_colors import trace_exception
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field as dataclass_field

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from PIL import Image

from backend.db import get_db as get_lollms_db
from backend.db.models.user import User as LollmsUser
from lollms_client import LollmsDiscussion
from backend.session import get_user_lollms_client
from backend.discussion import get_user_discussion_manager

# --- LEGACY DISCUSSION CLASSES FOR MIGRATION ---
@dataclass
class _LegacyMessage:
    sender: str
    sender_type: str
    content: str
    id: str = dataclass_field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    created_at: datetime = dataclass_field(default_factory=lambda: datetime.now(datetime.timezone.utc))
    binding_name: Optional[str] = None
    model_name: Optional[str] = None
    token_count: Optional[int] = None
    sources: Optional[List[Any]] = None
    steps: Optional[List[Any]] = None
    image_references: Optional[List[str]] = dataclass_field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "_LegacyMessage":
        created_at_val = data.get("created_at")
        if isinstance(created_at_val, str):
            try: created_at = datetime.fromisoformat(created_at_val)
            except ValueError: created_at = datetime.now(datetime.timezone.utc)
        else: created_at = datetime.now(datetime.timezone.utc)
        
        sender = data.get("sender", "unknown")
        sender_type = data.get("sender_type", "user" if sender not in ["lollms", "assistant"] else "assistant")

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            sender=sender,
            sender_type=sender_type,
            content=data.get("content", ""),
            parent_id=data.get("parent_message_id"), 
            created_at=created_at,
            binding_name=data.get("binding_name"),
            model_name=data.get("model_name"),
            token_count=data.get("token_count"),
            sources=data.get("sources",[]),
            steps=data.get("steps",[]),
            image_references=data.get("image_references", [])
        )

class LegacyDiscussion:
    def __init__(self, discussion_id: Optional[str] = None, title: Optional[str] = None):
        self.messages: List[_LegacyMessage] = []
        self.discussion_id: str = discussion_id or str(uuid.uuid4())
        self.title: str = title or f"Imported {self.discussion_id[:8]}"
        self.rag_datastore_ids: Optional[list] = None
        self.active_branch_id: Optional[str] = None

    @staticmethod
    def load_from_yaml(file_path: Path) -> Optional["LegacyDiscussion"]:
        if not file_path.exists(): return None
        try:
            with open(file_path, "r", encoding="utf-8") as file: data = yaml.safe_load(file)
        except Exception: return None

        if not isinstance(data, dict):
            discussion = LegacyDiscussion(discussion_id=file_path.stem)
            if isinstance(data, list):
                for msg_data in data:
                    if isinstance(msg_data, dict): discussion.messages.append(_LegacyMessage.from_dict(msg_data))
            return discussion

        discussion = LegacyDiscussion(discussion_id=data.get("discussion_id", file_path.stem), title=data.get("title"))
        discussion.rag_datastore_ids = data.get("rag_datastore_ids")
        discussion.active_branch_id = data.get("active_branch_id")
        
        for msg_data in data.get("messages", []):
            if isinstance(msg_data, dict): discussion.messages.append(_LegacyMessage.from_dict(msg_data))
        return discussion
# --- END LEGACY ---


def _fetch_and_process_icon(image_url: str) -> str | None:
    if not image_url or not image_url.startswith(('http', '/')):
        return None
    
    try:
        if image_url.startswith('/'):
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

def _migrate_discussions_for_user(user_id: str, temp_dir: Path):
    print(f"  - Searching for discussions for user ID: {user_id}")

    db_path = find_database_files(temp_dir)
    if len(db_path) == 0:
        print("CRITICAL: 'database.db' not found in uploaded files. Aborting migration.")
        shutil.rmtree(temp_dir)
        return

    db_path = db_path[0]

    print(f"  - Found database: {db_path.name}. Processing...")
    discussion_engine = create_engine(f"sqlite:///{db_path}")
    DiscussionSession = sessionmaker(bind=discussion_engine)
    discussion_session = DiscussionSession()
    result = discussion_session.execute(
        text("SELECT id, name FROM user WHERE id = :user_id"),
        {"user_id": user_id}
    )
    source_user = result.first()[1]
    
    try:
        discussions_query = text(
            "SELECT id, chat FROM chat WHERE user_id = :user_id"
        )
        discussions = discussion_session.execute(discussions_query, {"user_id": user_id}).fetchall()

        migrated_discussions_count = 0
        for disc in discussions:
            discussion_id = disc.id
            chat_data = json.loads(disc.chat)
            if chat_data is None:
                print(f"  - WARNING: No chat data found for discussion {discussion_id}. Skipping.")
                continue

            try:
                messages = chat_data.get("history",{}).get("messages", [])
                title = chat_data.get("title", f"Imported Discussion {discussion_id[:8]}")
            except AttributeError:
                print(f"  - WARNING: Invalid chat data format for discussion {discussion_id}. Skipping.")
                continue

            dm = get_user_discussion_manager(source_user)
            lc = get_user_lollms_client(source_user)
            lollms_discussion = LollmsDiscussion.create_new(
                lollms_client=lc, 
                db_manager=dm,
                id=discussion_id,
                autosave=True,
                discussion_metadata={"title": title},
            )

            for _, msg in messages.items():
                try:
                    content = msg.get("content", "")
                    sender = msg.get("role", "unknown")
                    message_type = "user" if sender.lower() == "user" else "assistant"
                    parent_message_id = msg.get("parent_id", None)
                    message_id = msg.get("id", None)

                    lollms_discussion.add_message(
                        sender=sender,
                        sender_type=message_type,
                        message_type=message_type,
                        content=content,
                        parent_message_id=parent_message_id,
                        message_id=message_id,
                    )
                except Exception as e:
                    print(f"  - WARNING: Error processing message: {e}. Skipping.")

            lollms_discussion.touch()
            migrated_discussions_count += 1

        print(f"  - SUCCESS: Migrated {migrated_discussions_count} discussions for user '{source_user}'.")
        return migrated_discussions_count

    except Exception as e:
        print(f"  - ERROR: Failed to migrate discussions for user '{source_user}'. Error: {e}")
        return 0
    finally:
        discussion_session.close()

def find_database_files(directory):
    if not os.path.exists(directory):
        print(f"The directory {directory} does not exist.")
        return

    db_files = list(Path(directory).glob('*.db'))
    sql3_files = list(Path(directory).glob('*.sql3'))

    database_files = db_files + sql3_files

    return database_files

def discover_database_schema(db_path: str):
    try:
        engine = create_engine(f"sqlite:///{db_path}",
                                pool_size=20,          # base pool size
                                max_overflow=30,       # additional connections beyond pool_size
                                pool_timeout=30,       # seconds to wait before raising TimeoutError
                                pool_pre_ping=True    # helps detect stale connections                               
                               )
        inspector = inspect(engine)

        markdown_output = "# Database Schema\n\n"

        table_names = inspector.get_table_names()

        if not table_names:
            return "## No tables found in the database."

        for table_name in table_names:
            markdown_output += f"## Table: `{table_name}`\n\n"
            columns = inspector.get_columns(table_name)

            if not columns:
                markdown_output += "  *No columns found.*\n\n"
                continue

            markdown_output += "| Column Name | Data Type | Nullable |\n"
            markdown_output += "|---|---|---|\n"
            for column in columns:
                markdown_output += f"| `{column['name']}` | `{column['type']}` | `{column['nullable']}` |\n"
            markdown_output += "\n"

        with open("database_schema.log","w",encoding="utf8", errors="ignore") as f:
            f.write(markdown_output)
        return markdown_output

    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None
def timestamp_to_datetime(timestamp):
  try:
    dt_object = datetime.fromtimestamp(timestamp)
    return dt_object
  except (TypeError, ValueError) as e:
    print(f"Error converting timestamp: {e}")
    return None    
    
def run_openwebui_migration(temp_dir_str: str):
    temp_dir = Path(temp_dir_str)
    print("\n--- Background OpenWebUI Migration Process Started ---")

    db_path = find_database_files(temp_dir)
    if len(db_path) == 0:
        print("CRITICAL: 'database.db' not found in uploaded files. Aborting migration.")
        shutil.rmtree(temp_dir)
        return

    db_path = db_path[0]
    schema = discover_database_schema(db_path)
    source_engine = create_engine(f"sqlite:///{db_path}")
    SourceSession = sessionmaker(bind=source_engine)
    source_session = SourceSession()
    lollms_db_session = next(get_lollms_db())

    max_retries = 5
    retry_delay = 0.5

    for attempt in range(max_retries):
        try:
            source_users_query = text("""
SELECT 
    u.id, 
    u.name, 
    u.email, 
    a.password,
    u.role, 
    u.profile_image_url, 
    u.created_at, 
    u.last_active_at
FROM user u
JOIN auth a ON u.email = a.email
""")
            source_users = source_session.execute(source_users_query).fetchall()

            print(f"INFO: Found {len(source_users)} users in 'database.db'.")
            migrated_users_count = 0
            skipped_users_count = 0

            for user in source_users:
                print(f"\nProcessing user: {user.name} ({user.email})")

                existing_user = lollms_db_session.query(LollmsUser).filter(LollmsUser.email == user.email).first()
                if existing_user:
                    print("  - INFO: User already exists. Skipping user data migration.")
                    skipped_users_count += 1
                    _migrate_discussions_for_user(user.id, temp_dir)
                    continue

                icon_b64 = _fetch_and_process_icon(user.profile_image_url)
                password_hash_with_marker = f"argon2_hash:{user.password}"

                new_lollms_user = LollmsUser(
                    username=user.name,
                    email=user.email,
                    hashed_password=password_hash_with_marker,
                    is_admin=(user.role == 'admin'),
                    is_active=True,
                    created_at=timestamp_to_datetime(user.created_at) or datetime.utcnow(),
                    last_activity_at=timestamp_to_datetime(user.last_active_at),
                    icon=icon_b64,
                    lollms_model_name = "gemma3:27b"
                )

                lollms_db_session.add(new_lollms_user)
                try:
                    lollms_db_session.commit()
                    print(f"  - SUCCESS: Migrated user '{user.name}'.")
                    migrated_users_count += 1
                    _migrate_discussions_for_user(  user.id, temp_dir)

                except IntegrityError as e:
                    trace_exception(e)
                    lollms_db_session.rollback()
                    print(f"  - ERROR: Failed to insert user '{user.name}'. Username might be a duplicate. Skipping. Error: {e.orig}")
                    skipped_users_count += 1

                time.sleep(0.1)

            print("\n--- Migration Task Finished ---")
            print(f"Migrated users: {migrated_users_count}")
            print(f"Skipped users: {skipped_users_count}")
            break

        except Exception as e:
            trace_exception(e)
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("CRITICAL: Migration failed after multiple retries.")
                return

        finally:
            source_session.close()
            lollms_db_session.close()
            try:
                shutil.rmtree(temp_dir)
                print(f"INFO: Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                print(f"Error cleaning up temporary directory: {e}")
