# backend/main.py
import os
import shutil
import traceback
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

# Configuration needs to be loaded first
from backend.config import (
    APP_VERSION, APP_DATA_DIR, APP_DB_URL,
    LOLLMS_CLIENT_DEFAULTS, SAFE_STORE_DEFAULTS,
    INITIAL_ADMIN_USER_CONFIG, DEFAULT_RAG_TOP_K, SERVER_CONFIG
)

# Database imports
from backend.database.setup import init_database, get_db, hash_password
from backend.database.setup import User as DBUser # For startup admin creation

# Service imports for startup (if needed, e.g. auth for admin check)
# from backend.services.auth_service import ...

# Routers
from backend.routers.static import static_router, mount_static_directories
from backend.routers.auth import auth_router, user_self_router
from backend.routers.uploads import upload_router # Assuming you create this
from backend.routers.discussions import discussion_router # Assuming you create this
from backend.routers.lollms_config import lollms_config_router # Assuming you create this
from backend.routers.datastores import datastore_router # Assuming you create this
from backend.routers.store_files import store_files_router # Assuming you create this
from backend.routers.prompts import prompts_router # Assuming you create this
from backend.routers.friendships import friendships_router # Assuming you create this
from backend.routers.admin import admin_router # Assuming you create this


app = FastAPI(
    title="Simplified LoLLMs Chat API",
    description="API for multi-user LoLLMs chat with RAG, prompts, friends, and more.",
    version=APP_VERSION
)

@app.on_event("startup")
async def on_startup() -> None:
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"INFO: Data directory ensured at: {APP_DATA_DIR}")
    except Exception as e:
        print(f"CRITICAL: Failed to initialize data directory: {e}")
        return # Critical error, should probably exit

    try:
        init_database(APP_DB_URL) # Pass the actual URL
        print(f"INFO: Database initialized at: {APP_DB_URL}")
    except Exception as e:
        print(f"CRITICAL: Failed to initialize database: {e}")
        return # Critical error

    # Initial Admin User Creation
    db: Session = next(get_db())
    try:
        admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
        admin_password = INITIAL_ADMIN_USER_CONFIG.get("password")

        if not admin_username or not admin_password:
            print("WARNING: Initial admin user not configured in config.toml.")
            return

        existing_admin = db.query(DBUser).filter(DBUser.username == admin_username).first()
        if not existing_admin:
            new_admin = DBUser(
                username=admin_username,
                hashed_password=hash_password(admin_password),
                is_admin=True,
                lollms_model_name=LOLLMS_CLIENT_DEFAULTS.get("default_model_name"),
                safe_store_vectorizer=SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
                llm_temperature=LOLLMS_CLIENT_DEFAULTS.get("temperature"),
                llm_top_k=LOLLMS_CLIENT_DEFAULTS.get("top_k"),
                llm_top_p=LOLLMS_CLIENT_DEFAULTS.get("top_p"),
                llm_repeat_penalty=LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
                llm_repeat_last_n=LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n"),
                theme_preference='system', 
                rag_top_k=DEFAULT_RAG_TOP_K
            )
            db.add(new_admin)
            db.commit()
            print(f"INFO: Initial admin user '{admin_username}' created.")
        else:
            print(f"INFO: Initial admin user '{admin_username}' already exists.")
    except Exception as e:
        print(f"ERROR: Initial admin user setup failed: {e}")
        traceback.print_exc()
        db.rollback() # Rollback on error
    finally:
        db.close()

# Include routers
app.include_router(static_router) # For /, /admin, /favicon.ico etc.
mount_static_directories(app) # For /locales

app.include_router(auth_router)
app.include_router(user_self_router)
app.include_router(upload_router)
app.include_router(discussion_router)
app.include_router(lollms_config_router)
app.include_router(datastore_router)
app.include_router(store_files_router)
app.include_router(prompts_router)
app.include_router(friendships_router)
app.include_router(admin_router)


# --- Main Execution ---
def run():
    import uvicorn
    host = SERVER_CONFIG.get("host", "127.0.0.1")
    port = int(SERVER_CONFIG.get("port", 9642))
    
    # APP_DATA_DIR creation is now in on_startup
    # Ensure it exists before uvicorn.run if critical operations outside startup depend on it.
    # In this case, startup handles it.

    print(f"--- Simplified LoLLMs Chat API Server (v{APP_VERSION}) ---")
    print(f"Data directory: {APP_DATA_DIR}")
    print(f"Database URL: {APP_DB_URL}")
    print(f"Access UI at: http://{host}:{port}/")
    print(f"Access Admin Panel at: http://{host}:{port}/admin (requires admin login)")
    print("--------------------------------------------------------------------")
    
    # Note: The path to the app for uvicorn changes.
    # If you run this script directly from `your_project_root/backend/main.py`:
    # uvicorn.run("main:app", host=host, port=port, reload=False) # This is correct if running this file.
    # If you run from `your_project_root` using `python -m backend.main`:
    # uvicorn.run("backend.main:app", ...)
    # For a Dockerfile or external runner, it would be "backend.main:app"
    uvicorn.run(app, host=host, port=port) # Simpler: pass app object directly

if __name__ == "__main__":
    run()