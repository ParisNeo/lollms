# This script is a failsafe script if you loose admin password
import getpass
from sqlalchemy.orm import Session
from backend.db import init_database, get_db
from backend.db.models.user import User as DBUser
from backend.security import get_password_hash as hash_password
from backend.config import APP_DB_URL

def reset_password():
    # Initialize database session
    init_database(APP_DB_URL)
    db: Session = get_db()

    try:
        username = input("Enter the username to update password: ").strip()
        if not username:
            print("Username cannot be empty.")
            return

        new_password = getpass.getpass("Enter the new password: ")
        confirm_password = getpass.getpass("Confirm the new password: ")

        if new_password != confirm_password:
            print("Passwords do not match.")
            return

        user = db.query(DBUser).filter(DBUser.username == username).first()
        if not user:
            print(f"User '{username}' not found.")
            return

        # Hash the new password and update
        user.hashed_password = hash_password(new_password)
        db.commit()
        print(f"Password for user '{username}' has been updated successfully.")

    except Exception as e:
        db.rollback()
        print(f"Error updating password: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_password()
