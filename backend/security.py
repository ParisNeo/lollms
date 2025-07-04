# backend/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext

from backend.config import SECRET_KEY, ALGORITHM
# --- MODIFIED: Import the new settings manager ---
from backend.settings import settings

# --- Password Hashing Context ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- OAuth2 Scheme ---
# This tells FastAPI where to look for the token. The `tokenUrl` points to our
# login endpoint in `routers/auth.py`.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed one."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a JWT access token with a dynamically configured expiration time.
    
    Args:
        data: The data to encode in the token (typically {'sub': username}).
        expires_delta: An optional override for the expiration time.

    Returns:
        The encoded JWT token as a string.
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # --- MODIFIED: Get expiration from the database-backed settings ---
        # The default value of 30 is a fallback in case the settings system
        # fails to load, ensuring the app doesn't crash. The primary default
        # is set during the database bootstrap process from config.toml.
        expire_minutes = settings.get("access_token_expire_minutes", 30)
        try:
            # Ensure the value is an integer
            minutes = int(expire_minutes)
        except (ValueError, TypeError):
            print(f"WARNING: Invalid 'access_token_expire_minutes' value ({expire_minutes}). Using fallback of 30 minutes.")
            minutes = 30
            
        expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        # Remplacez par votre clé secrète et algorithme
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None
