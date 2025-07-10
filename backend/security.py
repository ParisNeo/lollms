# backend/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets
import smtplib
import subprocess
import shutil
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

def _send_email_smtp(to_email: str, subject: str, html_content: str):
    """Sends an email using a configured SMTP server."""
    smtp_host = settings.get("smtp_host")
    smtp_port = settings.get("smtp_port", 587)
    smtp_user = settings.get("smtp_user")
    smtp_password = settings.get("smtp_password")
    from_email = settings.get("smtp_from_email")
    use_tls = settings.get("smtp_use_tls", True)

    if not all([smtp_host, smtp_port, smtp_user, smtp_password, from_email]):
        print("ERROR: SMTP settings are incomplete. Cannot send email.")
        raise ValueError("SMTP settings are not fully configured.")

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    msg.attach(MIMEText(html_content, 'html'))
    
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if use_tls:
                server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, [to_email], msg.as_string())
        print(f"INFO: Email (SMTP) with subject '{subject}' sent successfully to {to_email}")
    except Exception as e:
        print(f"CRITICAL: Failed to send SMTP email to {to_email}. Error: {e}")
        raise

def _send_email_system_mail(to_email: str, subject: str, body: str):
    """Sends an email using the system's `mail` command."""
    if not shutil.which("mail"):
        raise FileNotFoundError("The 'mail' command was not found on the system. Please install mailutils or similar package.")
    
    try:
        # The `mail` command typically expects the body on stdin.
        # We also need to set the Content-Type for HTML emails.
        command = [
            'mail',
            '-s', subject,
            '-a', 'Content-Type: text/html; charset=UTF-8',
            to_email
        ]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, text=True)
        process.communicate(input=body)
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command)
        print(f"INFO: Email (system mail) with subject '{subject}' sent successfully to {to_email}")
    except Exception as e:
        print(f"CRITICAL: Failed to send system mail to {to_email}. Error: {e}")
        raise

def send_generic_email(to_email: str, subject: str, body: str):
    """
    Sends a generic HTML email to a user, automatically choosing the
    sending method based on global settings.
    """
    recovery_mode = settings.get("password_recovery_mode", "manual")

    if recovery_mode == "automatic":
        _send_email_smtp(to_email, subject, body)
    elif recovery_mode == "system_mail":
        _send_email_system_mail(to_email, subject, body)
    else:
        # Fallback for manual or misconfigured modes.
        print(f"WARNING: Email sending is set to '{recovery_mode}', which is not an automatic mode. Cannot send email to {to_email}.")


def send_password_reset_email(to_email: str, reset_link: str, username: str):
    """Prepares and sends a password reset email using the configured method."""
    subject = "Password Reset Request"
    html_content = f"""
    <html>
    <body>
        <p>Hello {username},</p>
        <p>You requested a password reset for your account. Please click the link below to set a new password:</p>
        <p><a href="{reset_link}">Reset Your Password</a></p>
        <p>This link will expire in 1 hour.</p>
        <p>If you did not request a password reset, please ignore this email.</p>
    </body>
    </html>
    """
    send_generic_email(to_email, subject, html_content)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None