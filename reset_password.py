import sys
import os
from pathlib import Path
import argparse

# Add project root to sys.path to allow imports
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

try:
    from backend.db import session as db_session_module
    from backend.db.models.user import User
    from backend.security import get_password_hash
    from backend.config import APP_DB_URL
    from ascii_colors import ASCIIColors
except ImportError as e:
    print(f"Error importing backend modules: {e}")
    print("Make sure you are running this from the project root and requirements are installed.")
    sys.exit(1)

def reset_password(username, new_password):
    print(ASCIIColors.cyan(f"--- LoLLMs Password Reset Tool ---"))
    
    # Initialize DB connection
    try:
        db_session_module.init_database(APP_DB_URL)
        db = db_session_module.SessionLocal()
    except Exception as e:
        print(ASCIIColors.red(f"Failed to connect to database: {e}"))
        sys.exit(1)

    try:
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            print(ASCIIColors.red(f"User '{username}' not found."))
            sys.exit(1)
            
        print(ASCIIColors.yellow(f"User found: {username} (ID: {user.id})"))
        
        # Hash and update
        hashed = get_password_hash(new_password)
        user.hashed_password = hashed
        
        # Ensure user is active if we are resetting credentials (optional but helpful)
        user.is_active = True
        
        db.commit()
        print(ASCIIColors.green(f"Successfully reset password for user '{username}'."))
        
    except Exception as e:
        print(ASCIIColors.red(f"An error occurred: {e}"))
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset a user's password in LoLLMs.")
    parser.add_argument("username", help="The username to reset")
    parser.add_argument("password", help="The new password")
    
    args = parser.parse_args()
    
    reset_password(args.username, args.password)
