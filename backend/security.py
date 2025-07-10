# backend/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext

from backend.config import SECRET_KEY, ALGORITHM
from backend.settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
        expire_minutes = settings.get("access_token_expire_minutes", 30)
        try:
            minutes = int(expire_minutes)
        except (ValueError, TypeError):
            print(f"WARNING: Invalid 'access_token_expire_minutes' value ({expire_minutes}). Using fallback of 30 minutes.")
            minutes = 30
            
        expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_reset_token() -> str:
    """Generates a secure, URL-safe random token for password resets."""
    return secrets.token_urlsafe(32)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None