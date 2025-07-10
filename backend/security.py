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
import tempfile


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
    A more robust function to convert an HTML string to a plain text string,
    preserving block-level spacing.
    """
    if not html_string:
        return ""
    
    text = html.unescape(html_string)

    # Replace block-level tags with double newlines
    text = re.sub(r'</(p|div|h[1-6]|blockquote|tr|li)>', '\n\n', text, flags=re.IGNORECASE)
    # Handle line breaks
    text = re.sub(r'<(br)\s*/?>', '\n', text, flags=re.IGNORECASE)
    # Handle list items with a prepended star
    text = re.sub(r'<li[^>]*>', '* ', text, flags=re.IGNORECASE)
    # Strip all remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Consolidate whitespace
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

def _send_email_smtp(to_email: str, subject: str, html_content: str, text_content: str):
    """Sends a multipart email using a configured SMTP server."""
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

    part1 = MIMEText(text_content, 'plain', 'utf-8')
    part2 = MIMEText(html_content, 'html', 'utf-8')

    msg.attach(part1)
    msg.attach(part2)
    
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

def _send_email_system_mail(to_email: str, subject: str, html_content: str, text_content: str):
    """
    Sends a multipart/alternative email using the system's `mailx` command.
    This approach is more robust for HTML content than piping to `mail`.
    """
    if not shutil.which("mailx"):
        print("CRITICAL: The 'mailx' command was not found. Please install mailx or a similar package (e.g., bsd-mailx).")
        raise FileNotFoundError("The 'mailx' command not found. Please install mailx.")

    boundary = f"----=_NextPart_{secrets.token_hex(16)}"
    
    # Construct the full multipart body
    multipart_body = (
        f"This is a multi-part message in MIME format.\n"
        f"--{boundary}\n"
        f"Content-Type: text/plain; charset=utf-8\n"
        f"Content-Transfer-Encoding: 7bit\n\n"
        f"{text_content}\n\n"
        f"--{boundary}\n"
        f"Content-Type: text/html; charset=utf-8\n"
        f"Content-Transfer-Encoding: 7bit\n\n"
        f"<html><body>{html_content}</body></html>\n\n"
        f"--{boundary}--\n"
    )

    sanitized_subject = subject.replace('\n', ' ').replace('\r', ' ')
    
    command = [
        'mailx',
        '-s', sanitized_subject,
        '-a', f'Content-Type: multipart/alternative; boundary="{boundary}"',
        to_email
    ]

    print(f"DEBUG: Executing system mail command: {' '.join(command)}")

    try:
        process = subprocess.run(
            command,
            input=multipart_body,
            capture_output=True,
            text=True,
            check=False,
            encoding='utf-8'
        )
        if process.returncode != 0:
            error_message = f"System 'mailx' command failed. Stderr: {process.stderr}"
            print(f"ERROR: {error_message}")
            raise subprocess.CalledProcessError(process.returncode, command, stderr=process.stderr)
        
        print(f"INFO: Email (system mailx) with subject '{subject}' sent to {to_email}.")
    except Exception as e:
        print(f"CRITICAL: An unexpected error occurred sending system mail: {e}")
        raise

def send_generic_email(to_email: str, subject: str, body: str, background_color: Optional[str] = "#f4f4f4", send_as_text: bool = False):
    """
    Prepares content and sends a generic email to a user, choosing the
    sending method based on global settings.
    """
    recovery_mode = settings.get("password_recovery_mode", "manual")
    if recovery_mode not in ["automatic", "system_mail"]:
        print(f"WARNING: Email sending is set to '{recovery_mode}'. Cannot send email to {to_email}.")
        return

    text_content = _convert_html_to_text(body)
    html_content = _get_full_html_email(body, background_color)

    if send_as_text:
        # If sending as plain text, we create a simple MIMEText message
        # instead of a multipart one. Both smtp and mailx can handle this.
        msg = MIMEText(text_content, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = settings.get("smtp_from_email", "noreply@localhost")
        msg['To'] = to_email
        
        if recovery_mode == "automatic":
            _send_email_smtp(to_email, subject, text_content, True) # SMTP can handle this simply
        else: # system_mail
             _send_email_system_mail(to_email, subject, "This email is in plain text format.", text_content)

    else: # Send as multipart HTML
        if recovery_mode == "automatic":
            _send_email_smtp(to_email, subject, html_content, text_content)
        elif recovery_mode == "system_mail":
            _send_email_system_mail(to_email, subject, body, text_content)

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