# lollms/scripts/setup_wizard.py
import sys
from pathlib import Path

# Setup PYTHONPATH to allow imports from backend
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from backend.db import session as db_session_module
    from backend.db.base import Base
    from backend.db.models.user import User
    from backend.security import get_password_hash
    from backend.config import INITIAL_ADMIN_USER_CONFIG, APP_DB_URL
except ImportError as e:
    print("\n[ERROR] Failed to import necessary modules.")
    print(f"Details: {e}")
    print("Please ensure you are running this script from the project's root directory.")
    sys.exit(1)

class ASCIIColors:
    @staticmethod
    def green(text): return f"\033[92m{text}\033[0m"
    @staticmethod
    def yellow(text): return f"\033[93m{text}\033[0m"
    @staticmethod
    def magenta(text): return f"\033[95m{text}\033[0m"
    @staticmethod
    def cyan(text): return f"\033[96m{text}\033[0m"
    @staticmethod
    def red(text): return f"\033[91m{text}\033[0m"

def get_db_session():
    db_session_module.init_database(APP_DB_URL)
    Base.metadata.create_all(bind=db_session_module.engine)
    return db_session_module.SessionLocal()

def create_admin_if_not_exists(db):
    admin_username = INITIAL_ADMIN_USER_CONFIG.get("username", "admin")
    admin_password = INITIAL_ADMIN_USER_CONFIG.get("password", "admin")
    
    # Check if any user exists, if so we assume admin exists or setup is partially done
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
    print(ASCIIColors.cyan("="*60))
    print(ASCIIColors.cyan(" " * 18 + "LoLLMs Installation Wizard"))
    print(ASCIIColors.cyan("="*60))

    print("\nInitializing system database and creating administrator account...")

    db = get_db_session()
    try:
        create_admin_if_not_exists(db)
        
        print("\n" + ASCIIColors.green("Installation completed successfully!"))
        
        print("\n" + "="*40)
        print(ASCIIColors.cyan("  DEFAULT ADMINISTRATOR CREDENTIALS"))
        print("="*40)
        print(f"  Username: {ASCIIColors.yellow(INITIAL_ADMIN_USER_CONFIG.get('username', 'admin'))}")
        print(f"  Password: {ASCIIColors.yellow(INITIAL_ADMIN_USER_CONFIG.get('password', 'admin'))}")
        print("="*40)

        print("\n" + ASCIIColors.magenta("IMPORTANT NEXT STEPS:"))
        
        print(f"\n{ASCIIColors.cyan('1. Change your password:')}")
        print("   Log in to the web interface and go to " + ASCIIColors.yellow("Settings > Account") + " to set a secure password.")
        
        print(f"\n{ASCIIColors.cyan('2. Configure AI Bindings:')}")
        print("   No AI models or providers are configured yet. You must do this manually.")
        print("   Navigate to " + ASCIIColors.yellow("Settings > LLM Bindings") + " to add your first provider (e.g., Ollama, OpenAI, etc.).")
        print("   You can also configure " + ASCIIColors.yellow("TTI (Images), TTS (Speech)") + ", and other services in their respective settings tabs.")

        print("\n" + "-"*60)
        input(f"\n{ASCIIColors.green('Setup finished.')} Press Enter to launch the LoLLMs application...")
        
    except Exception as e:
        print(ASCIIColors.red(f"\n[ERROR] Setup failed: {e}"))
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main_wizard()
