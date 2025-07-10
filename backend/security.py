# backend/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets
import smtplib
import subprocess
import shutil
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import html
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

def _convert_html_to_text(html_string: str) -> str:
    """
    A simple function to convert an HTML string to a plain text string.
    """
    if not html_string:
        return ""
    
    text = html.unescape(html_string)
    
    text = re.sub(r'</(p|div|h[1-6]|li|tr)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<(td|th)[^>]*>', '  ', text, flags=re.IGNORECASE)
    text = re.sub(r'<(br|hr)\s*/?>', '\n', text, flags=re.IGNORECASE)
    
    text = re.sub(r'<[^>]+>', '', text)
    
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def _get_full_html_email(body: str, background_color: Optional[str]) -> str:
    """Wraps the email body in a full HTML document with a background color."""
    safe_bg_color = "#f4f4f4" # Default light gray background
    if background_color and re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', background_color):
        safe_bg_color = background_color
    
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email</title>
</head>
<body style="margin: 0; padding: 20px; font-family: sans-serif; background-color: {safe_bg_color};">
    <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 20px; border-radius: 8px;">
        {body}
    </div>
</body>
</html>
"""

def _send_email_smtp(to_email: str, subject: str, content: str, is_text_only: bool):
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

    if is_text_only:
        msg = MIMEText(content, 'plain', 'utf-8')
    else:
        msg = MIMEMultipart('alternative')
        text_part = MIMEText(_convert_html_to_text(content), 'plain', 'utf-8')
        html_part = MIMEText(content, 'html', 'utf-8')
        msg.attach(text_part)
        msg.attach(html_part)

    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    
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

def _sanitize_for_system_mail(body: str) -> str:
    """
    Escapes characters that have special meaning to the `mail` command-line utility.
    The primary issue is a tilde (~) at the beginning of a line.
    """
    if body.startswith('~'):
        body = '~' + body
    return re.sub(r'\n~', '\n~~', body)

def _send_email_system_mail(to_email: str, subject: str, body: str, is_text_only: bool):
    """Sends an email using the system's `mail` command with enhanced debugging."""
    if not shutil.which("mail"):
        print("CRITICAL: The 'mail' command was not found on the system. Please install mailutils or a similar package.")
        raise FileNotFoundError("The 'mail' command was not found on the system. Please install mailutils or similar package.")
    
    sanitized_subject = subject.replace('\n', ' ').replace('\r', ' ')
    sanitized_body = _sanitize_for_system_mail(body)

    command = ['mail', '-s', sanitized_subject]
    
    if not is_text_only:
        command.extend(['-a', 'Content-Type: text/html; charset=UTF-8'])
    
    command.append(to_email)
    
    print(f"DEBUG: Executing system mail command: {' '.join(command)}")
    
    try:
        process = subprocess.run(
            command,
            input=sanitized_body,
            capture_output=True,
            text=True,
            check=False,
            encoding='utf-8'
        )

        print(f"DEBUG: System mail command finished with exit code: {process.returncode}")
        if process.stdout:
            print(f"DEBUG: System mail command STDOUT:\n---_---_---\n{process.stdout}\n---_---_---")
        if process.stderr:
            print(f"WARNING: System mail command STDERR:\n---_---_---\n{process.stderr}\n---_---_---")

        if process.returncode != 0:
            error_message = f"System 'mail' command failed with exit code {process.returncode}."
            if process.stderr:
                error_message += f" Stderr: {process.stderr}"
            raise subprocess.CalledProcessError(process.returncode, command, output=process.stdout, stderr=process.stderr)

        print(f"INFO: Email (system mail) with subject '{subject}' sent to {to_email}. Exit code {process.returncode}.")
    
    except FileNotFoundError:
        print("CRITICAL: The 'mail' command could not be found. Is it installed and in the system's PATH?")
        raise
    except Exception as e:
        print(f"CRITICAL: An unexpected error occurred while trying to send system mail to {to_email}. Error: {e}")
        raise

def send_generic_email(to_email: str, subject: str, body: str, background_color: Optional[str] = "#f4f4f4", send_as_text: bool = False):
    """
    Sends a generic email to a user, automatically choosing the
    sending method based on global settings.
    """
    recovery_mode = settings.get("password_recovery_mode", "manual")
    
    content_to_send = ""
    is_text_only_final = send_as_text

    if recovery_mode == "automatic":
        if send_as_text:
            content_to_send = _convert_html_to_text(body)
        else:
            content_to_send = _get_full_html_email(body, background_color)
    elif recovery_mode == "system_mail":
        if send_as_text:
            content_to_send = _convert_html_to_text(body)
        else:
            # For system mail, send only the core HTML fragment, not a full document.
            content_to_send = body
    
    if recovery_mode == "automatic":
        _send_email_smtp(to_email, subject, content_to_send, is_text_only=is_text_only_final)
    elif recovery_mode == "system_mail":
        _send_email_system_mail(to_email, subject, content_to_send, is_text_only=is_text_only_final)
    else:
        print(f"WARNING: Email sending is set to '{recovery_mode}', which is not an automatic mode. Cannot send email to {to_email}.")


def send_password_reset_email(to_email: str, reset_link: str, username: str):
    """Prepares and sends a password reset email using the configured method."""
    subject = "Password Reset Request"
    body_content = f"""
    <p>Hello {username},</p>
    <p>You requested a password reset for your account. Please click the link below to set a new password:</p>
    <p><a href="{reset_link}" style="color: #ffffff; background-color: #007bff; padding: 10px 15px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Your Password</a></p>
    <p>This link will expire in 1 hour.</p>
    <p>If you did not request a password reset, please ignore this email.</p>
    """
    send_generic_email(to_email, subject, body_content, send_as_text=False)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None