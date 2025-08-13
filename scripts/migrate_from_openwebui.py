import os
import requests
import base64
import io
import time
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from PIL import Image

# --- Configuration ---
# Load database URLs from .env file
load_dotenv()
OPENWEBUI_DB_URL = os.getenv("OPENWEBUI_DB_URL")
LOLLMS_DB_URL = os.getenv("LOLLMS_DB_URL")

# Check if configuration is present
if not OPENWEBUI_DB_URL or not LOLLMS_DB_URL:
    print("CRITICAL: Database URLs are not configured. Please create a .env file with OPENWEBUI_DB_URL and LOLLMS_DB_URL.")
    exit(1)

# --- Database Connections ---
try:
    source_engine = create_engine(OPENWEBUI_DB_URL)
    SourceSession = sessionmaker(bind=source_engine)
    source_session = SourceSession()

    dest_engine = create_engine(LOLLMS_DB_URL)
    DestSession = sessionmaker(bind=dest_engine)
    dest_session = DestSession()
    print("INFO: Successfully connected to both source and destination databases.")
except Exception as e:
    print(f"CRITICAL: Failed to connect to a database. Error: {e}")
    exit(1)

# --- Helper Functions ---

def fetch_and_process_icon(image_url: str) -> str | None:
    """
    Downloads an image from a URL, resizes it, and converts it to a Base64 data URI.
    """
    if not image_url or not image_url.startswith('http'):
        return None
    
    try:
        # Some OpenWebUI URLs might be relative, prepend a placeholder
        if image_url.startswith('/'):
            # You might need to change this if your OpenWebUI is not at localhost
            image_url = f"http://localhost:8080{image_url}"

        print(f"  - Fetching icon from: {image_url}")
        response = requests.get(image_url, timeout=10, stream=True)
        response.raise_for_status()

        image_data = response.content
        image = Image.open(io.BytesIO(image_data))
        image.thumbnail((128, 128))

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        base64_encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        return f"data:image/png;base64,{base64_encoded}"
    except requests.RequestException as e:
        print(f"  - WARNING: Could not fetch image from {image_url}. Error: {e}")
    except Exception as e:
        print(f"  - WARNING: Could not process image from {image_url}. Error: {e}")
    return None

def migrate_users():
    """
    Main function to perform the user migration.
    """
    print("\n--- Starting OpenWebUI User Migration ---")
    
    try:
        # Fetch all users from the OpenWebUI 'users' table
        source_users_query = text("SELECT id, name, email, password, role, profile_image_url, created_at, last_active_at FROM users")
        source_users = source_session.execute(source_users_query).fetchall()
    except SQLAlchemyError as e:
        print(f"CRITICAL: Failed to query source database. Is the table name 'users' correct? Error: {e}")
        return

    if not source_users:
        print("INFO: No users found in the OpenWebUI database. Nothing to migrate.")
        return

    print(f"INFO: Found {len(source_users)} users in OpenWebUI database. Starting migration process...")
    migrated_count = 0
    skipped_count = 0

    for user in source_users:
        print(f"\nProcessing user: {user.name} ({user.email})")

        # 1. Check if user already exists in the destination DB by email
        existing_user_query = text("SELECT id FROM users WHERE email = :email")
        existing_user = dest_session.execute(existing_user_query, {"email": user.email}).first()

        if existing_user:
            print("  - INFO: User with this email already exists in the destination database. Skipping.")
            skipped_count += 1
            continue

        # 2. Map source data to destination schema
        is_admin = (user.role == 'admin')
        
        # 3. Process profile icon
        icon_b64 = fetch_and_process_icon(user.profile_image_url)

        # 4. Prepare the user data for insertion
        # We prefix the Argon2 hash to identify it later. This is a simple and effective method.
        # Passlib can recognize hashes by their format, but a prefix makes it explicit.
        password_hash_with_marker = f"argon2_hash:{user.password}"

        new_user_data = {
            "username": user.name,
            "email": user.email,
            "hashed_password": password_hash_with_marker,
            "is_admin": is_admin,
            "is_active": True,  # We assume all migrated users are active
            "created_at": user.created_at or datetime.utcnow(),
            "last_activity_at": user.last_active_at,
            "icon": icon_b64,
            # Other fields like first_name, family_name, etc., will be NULL
        }

        # 5. Insert the new user into the destination database
        try:
            insert_query = text("""
                INSERT INTO users (username, email, hashed_password, is_admin, is_active, created_at, last_activity_at, icon)
                VALUES (:username, :email, :hashed_password, :is_admin, :is_active, :created_at, :last_activity_at, :icon)
            """)
            dest_session.execute(insert_query, new_user_data)
            dest_session.commit()
            print(f"  - SUCCESS: User '{user.name}' migrated successfully.")
            migrated_count += 1
        except IntegrityError as e:
            dest_session.rollback()
            print(f"  - ERROR: Failed to insert user '{user.name}'. A user with this username might already exist. Error: {e.orig}")
            skipped_count += 1
        except Exception as e:
            dest_session.rollback()
            print(f"  - ERROR: An unexpected error occurred while inserting user '{user.name}'. Error: {e}")
            skipped_count += 1
        
        # Add a small delay to be respectful to the icon host server
        time.sleep(0.1)

    print("\n--- Migration Complete ---")
    print(f"Successfully migrated: {migrated_count} users.")
    print(f"Skipped (already exist or error): {skipped_count} users.")


if __name__ == "__main__":
    migrate_users()
    source_session.close()
    dest_session.close()
    print("INFO: Database connections closed.")