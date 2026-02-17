# lollms/scripts/setup_wizard.py
import sys
import traceback
from pathlib import Path

# Rich imports for modern terminal styling
from ascii_colors import Console
from ascii_colors import Style

# Setup PYTHONPATH to allow imports from backend
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from backend.db import session as db_session_module
    from backend.db.base import Base

    # Import all models to ensure they are registered in SQLAlchemy metadata
    # before create_all is called. This prevents NoReferencedTableError for
    # foreign keys defined in Base (like user_group_link).
    from backend.db.models import (
        user, group, personality, config, service,
        social, dm, discussion, discussion_group,
        memory, note, notebook, image, voice,
        fun_fact, news, broadcast, api_key,
        connections, datastore, db_task, email_marketing,
        friends, prompt
    )

    from backend.db.models.user import User
    from backend.security import get_password_hash
    from backend.config import INITIAL_ADMIN_USER_CONFIG, APP_DB_URL
except ImportError as e:
    print("\n[ERROR] Failed to import necessary modules.")
    print(f"Details: {e}")
    print("Please ensure you are running this script from the project's root directory.")
    sys.exit(1)

# Initialise a Rich console for styled output
console = Console()

def get_db_session():
    """Initialise the database and return a session."""
    db_session_module.init_database(APP_DB_URL)
    # Ensure all tables are created
    Base.metadata.create_all(bind=db_session_module.engine)
    return db_session_module.SessionLocal()

def create_admin_if_not_exists(db):
    """Create the default admin user if it does not already exist."""
    admin_username = INITIAL_ADMIN_USER_CONFIG.get("username", "admin")
    admin_password = INITIAL_ADMIN_USER_CONFIG.get("password", "admin")

    # If the admin already exists, do nothing
    if db.query(User).filter(User.username == admin_username).first():
        return

    new_admin = User(
        username=admin_username,
        hashed_password=get_password_hash(admin_password),
        is_admin=True,
        is_active=True,
        status="active",
        first_login_done=False
    )
    db.add(new_admin)
    db.commit()

def main_wizard():
    """Run the installation wizard with Rich‑styled output."""
    # Header
    console.print("=" * 60, style=Style(color="cyan"))
    console.print(" " * 18 + "LoLLMs Installation Wizard", style=Style(color="cyan", bold=True))
    console.print("=" * 60, style=Style(color="cyan"))

    console.print("\nInitializing system database and creating administrator account...", style="bright_white")

    db = None
    try:
        db = get_db_session()
        create_admin_if_not_exists(db)

        # Success message
        console.print("\n" + "Installation completed successfully!".upper(),
                      style=Style(color="green", bold=True))

        # Show default credentials
        console.print("\n" + "=" * 40, style=Style(color="cyan"))
        console.print("  DEFAULT ADMINISTRATOR CREDENTIALS", style=Style(color="cyan", bold=True))
        console.print("=" * 40, style=Style(color="cyan"))
        console.print(f"  Username: {INITIAL_ADMIN_USER_CONFIG.get('username', 'admin')}",
                      style=Style(color="yellow"))
        console.print(f"  Password: {INITIAL_ADMIN_USER_CONFIG.get('password', 'admin')}",
                      style=Style(color="yellow"))
        console.print("=" * 40, style=Style(color="cyan"))

        # Important next steps
        console.print("\n" + "IMPORTANT NEXT STEPS:", style=Style(color="magenta", bold=True))

        console.print(f"\n{Style(color='cyan').render('1. Change your password:')}")
        console.print("   Log in to the web interface and go to "
                      + "[bold yellow]Settings > Account[/] to set a secure password.")

        console.print(f"\n{Style(color='cyan').render('2. Configure AI Bindings:')}")
        console.print("   No AI models or providers are configured yet. You must do this manually.")
        console.print("   Navigate to " + "[bold yellow]Settings > LLM Bindings[/] to add your first provider "
                      "(e.g., Ollama, OpenAI, etc.).")
        console.print("   You can also configure " + "[bold yellow]TTI (Images), TTS (Speech)[/]"
                      + " and other services in their respective settings tabs.")

        console.print("\n" + "-" * 60, style=Style(color="cyan"))
        input(f"\n{Style(color='green').render('Setup finished.')}"
              " Press Enter to launch the LoLLMs application...")

    except Exception as e:
        console.print(f"\n[ERROR] Setup failed: {e}", style=Style(color="red", bold=True))
        traceback.print_exc()
        sys.exit(1)
    finally:
        if db:
            db.close()

if __name__ == "__main__":
    main_wizard()
