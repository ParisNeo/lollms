# backend/migration_utils.py
import os
import shutil
import base64
import io
import json
import time
from pathlib import Path
from datetime import datetime
from ascii_colors import trace_exception
from typing import List, Dict, Any

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from PIL import Image

from backend.database_setup import User as LollmsUser, get_db as get_lollms_db
from backend.security import get_password_hash
from backend.session import get_user_data_root
from lollms_client import LollmsDiscussion
from backend.session import get_user_discussion_path, get_user_lollms_client
from backend.discussion import get_user_discussion_manager, get_user_discussion
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

def _migrate_discussions_for_user(user_id: str, temp_dir: Path):
    """Migrates all discussions for a single user from the web_ui.db database."""
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
        # Query the 'chat' table to get discussions for the user
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
                messages = chat_data.get("history",{}).get("messages", [])  # Access messages within chat data
                title = chat_data.get("title", f"Imported Discussion {discussion_id[:8]}")
            except AttributeError:
                print(f"  - WARNING: Invalid chat data format for discussion {discussion_id}. Skipping.")
                continue

            # Create a LollmsDiscussion object
            dm = get_user_discussion_manager(source_user)
            lc = get_user_lollms_client(source_user)
            lollms_discussion = LollmsDiscussion.create_new(
                lollms_client=lc, 
                db_manager=dm,
                id=discussion_id,
                autosave=True,
                discussion_metadata={"title": title},
            )

            # Add messages to the discussion
            for _, msg in messages.items():
                try:
                    content = msg.get("content", "")
                    sender = msg.get("role", "unknown")
                    message_type = "user" if sender.lower() == "user" else "assistant"  # 1 for user, 2 for bot
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

            # Save the discussion to the user's folder
            lollms_discussion.touch()
            migrated_discussions_count += 1

        print(f"  - SUCCESS: Migrated {migrated_discussions_count} discussions for user '{source_user}'.")
        return migrated_discussions_count

    except Exception as e:
        print(f"  - ERROR: Failed to migrate discussions for user '{source_user}'. Error: {e}")
        return 0
    finally:
        discussion_session.close()

# --- Main Migration Function ---
def find_database_files(directory):
    # Ensure the directory exists
    if not os.path.exists(directory):
        print(f"The directory {directory} does not exist.")
        return

    # Use glob to find all .db and .sql3 files
    db_files = list(Path(directory).glob('*.db'))
    sql3_files = list(Path(directory).glob('*.sql3'))

    # Combine the results
    database_files = db_files + sql3_files

    return database_files

def discover_database_schema(db_path: str):
    """
    Discovers all tables in a SQLite database and their content,
    outputting the schema in Markdown format.

    Args:
        db_path: The path to the SQLite database file.

    Returns:
        A string containing the Markdown representation of the database schema.
        Returns None if there's an error connecting to the database.
    """
    try:
        engine = create_engine(f"sqlite:///{db_path}")
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

            # Fetch a few rows of data (limit to 5 for brevity)
            # try:
            #     with engine.connect() as connection:
            #         result = connection.execute(text(f"SELECT * FROM {table_name} LIMIT 5"))
            #         rows = result.fetchall()

            #         if rows:
            #             markdown_output += "### Sample Data:\n\n"
            #             # Create a header row
            #             header = [column['name'] for column in columns]
            #             markdown_output += "| " + " | ".join(header) + " |\n"
            #             markdown_output += "| " + " | ".join(["---"] * len(header)) + " |\n"

            #             for row in rows:
            #                 markdown_output += "| " + " | ".join(str(value) for value in row) + " |\n"
            #             markdown_output += "\n"
            #         else:
            #             markdown_output += "  *No data found in the table.*\n\n"
            # except Exception as e:
            #     markdown_output += f"  *Error fetching data: {e}*\n\n"

        with open("database_schema.log","w",encoding="utf8", errors="ignore") as f:
            f.write(markdown_output)
        return markdown_output

    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None
def timestamp_to_datetime(timestamp):
  """
  Converts an integer timestamp to a datetime object.

  Args:
    timestamp: An integer representing the timestamp.

  Returns:
    A datetime object representing the timestamp, or None if the input is invalid.
  """
  try:
    dt_object = datetime.fromtimestamp(timestamp)
    return dt_object
  except (TypeError, ValueError) as e:
    print(f"Error converting timestamp: {e}")
    return None    
    
def run_openwebui_migration(temp_dir_str: str):
    """
    Main background task to perform the full OpenWebUI migration.

    Args:
        temp_dir_str: The string path to the temporary directory with uploaded DB files.
    """
    temp_dir = Path(temp_dir_str)
    print("\n--- Background OpenWebUI Migration Process Started ---")

    # Find the main user database file
    db_path = find_database_files(temp_dir)
    if len(db_path) == 0:
        print("CRITICAL: 'database.db' not found in uploaded files. Aborting migration.")
        shutil.rmtree(temp_dir)
        return

    db_path = db_path[0]
    schema = discover_database_schema(db_path)
    # print(schema)
    source_engine = create_engine(f"sqlite:///{db_path}")
    SourceSession = sessionmaker(bind=source_engine)
    source_session = SourceSession()
    lollms_db_session = next(get_lollms_db())

    max_retries = 5
    retry_delay = 0.5  # seconds

    for attempt in range(max_retries):
        try:
            # Changed query to select from the 'auth' table
            source_users_query = text("""
SELECT 
    u.id, 
    u.name, 
    u.email, 
    a.password,  -- Replaces u.oauth_sub
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

                # Check if user already exists
                existing_user = lollms_db_session.query(LollmsUser).filter(LollmsUser.email == user.email).first()
                if existing_user:
                    print("  - INFO: User already exists. Skipping user data migration.")
                    skipped_users_count += 1
                    _migrate_discussions_for_user(user.id, temp_dir)
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
                    # Now migrate their discussions
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
            break  # Exit the retry loop if successful

        except Exception as e:
            trace_exception(e)  # Print the full traceback
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("CRITICAL: Migration failed after multiple retries.")
                # Handle the error appropriately (e.g., log it, notify the user)
                return

        finally:
            source_session.close()
            lollms_db_session.close()
            # Clean up the temporary directory
            try:
                shutil.rmtree(temp_dir)
                print(f"INFO: Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                print(f"Error cleaning up temporary directory: {e}")
