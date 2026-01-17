from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import secrets
import smtplib
import subprocess
import shutil
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import html
import platform
import tempfile
import os
import bleach

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext

from backend.config import SECRET_KEY, ALGORITHM
from backend.settings import settings
import json

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
api_key_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# --- Sanitization Configuration ---
ALLOWED_TAGS = [
    'p', 'b', 'i', 'u', 'em', 'strong', 'a', 'br', 'ul', 'ol', 'li', 
    'code', 'pre', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'table', 'thead', 'tbody', 'tr', 'th', 'td', 'strike', 'hr', 'span', 'div'
]

ALLOWED_ATTRS = {
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'span': ['class'],
    'div': ['class'],
    'code': ['class'],
    'pre': ['class']
}

def sanitize_content(content: str) -> str:
    """
    Sanitizes user input to prevent XSS while allowing basic formatting.
    Centralized logic used by Routers and Maintenance Tasks.
    """
    if not content:
        return content
    # bleach.clean will strip or escape tags not in ALLOWED_TAGS
    # and strip attributes not in ALLOWED_ATTRS.
    return bleach.clean(content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed one."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)

def generate_api_key() -> Tuple[str, str]:
    """Generates a secure API key and its non-secret prefix."""
    prefix = secrets.token_urlsafe(6)  # e.g., lollms_aBcDeF12
    
    # Ensure the prefix does not contain underscores.  Regenerate if it does.
    while "_" in prefix:
        prefix = secrets.token_urlsafe(6)
    key = secrets.token_urlsafe(32)
    prefix = "lollms_" + prefix
    full_key = f"{prefix}_{key}"
        
    return full_key, prefix

def generate_sso_secret() -> str:
    """Generates a secure, URL-safe random string for SSO client secrets."""
    return secrets.token_urlsafe(32)

def hash_api_key(api_key: str) -> str:
    """Hashes a plain text API key for storage."""
    return api_key_context.hash(api_key)

def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verifies a plain text API key against a stored hash."""
    return api_key_context.verify(plain_key, hashed_key)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a JWT access token for the main application using the global SECRET_KEY.
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        try:
            expire_minutes = settings.get("access_token_expire_minutes", 30*24*3600)
            if isinstance(expire_minutes, dict):
                expire_minutes = expire_minutes.get("value", 30*24*3600) # Default to 30 days
            elif isinstance(expire_minutes, str):
                try:
                    expire_minutes = json.loads(expire_minutes).get("value", 30*24*3600) # Default to 30 days
                except Exception: 
                    expire_minutes = 30*24*3600
            minutes = int(expire_minutes)
        except (ValueError, TypeError):
            print(f"WARNING: Invalid 'access_token_expire_minutes' value ({expire_minutes}). Using fallback of 30 days.")
            minutes = 30*24*3600 # 30 days in minutes

        expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_sso_token(data: dict, secret_key: str, audience: str) -> str:
    """
    Creates a JWT access token specifically for an SSO application.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=15) # SSO tokens have a short lifespan
    to_encode.update({
        "exp": expire,
        "aud": audience
    })
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)
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

    text = re.sub(r'</(p|div|h[1-6]|blockquote|tr|li)>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<br>\s*', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', '* ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

def _get_full_html_email(body: str, background_color: Optional[str]) -> str:
    """Wraps the email body in a full HTML document with a background color."""
    safe_bg_color = "#f4f4f4"  # Default light gray background
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

def _send_email_smtp(to_email: str, subject: str, html_content: Optional[str], text_content: str):
    """Sends an email using a configured SMTP server. It can be text-only or multipart."""
    smtp_host = settings.get("smtp_host")
    smtp_port = settings.get("smtp_port", 587)
    smtp_user = settings.get("smtp_user")
    smtp_password = settings.get("smtp_password")
    from_email = settings.get("smtp_from_email")
    use_tls = settings.get("smtp_use_tls", True)

    if not all([smtp_host, smtp_port, smtp_user, smtp_password, from_email]):
        raise ValueError("SMTP settings are not fully configured.")

    if html_content:
        msg = MIMEMultipart('alternative')
        part1 = MIMEText(text_content, 'plain', 'utf-8')
        part2 = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(part1)
        msg.attach(part2)
    else:
        msg = MIMEText(text_content, 'plain', 'utf-8')

    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if use_tls:
                server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, [to_email], msg.as_string())
        print(f"INFO: Email (SMTP) sent to {to_email}")
    except Exception as e:
        print(f"CRITICAL: Failed to send SMTP email. Error: {e}")
        raise

def _send_email_gmail(to_email: str, subject: str, html_content: Optional[str], text_content: str):
    """Sends an email using Gmail's SMTP servers with pre-configured host/port."""
    smtp_host = "smtp.gmail.com"
    smtp_port = 587
    smtp_user = settings.get("smtp_user")
    smtp_password = settings.get("smtp_password")
    # For Gmail, the 'From' header is generally overwritten by the authenticated user,
    # but we set it for correctness. We rely on smtp_user as the sender.
    from_email = smtp_user 
    use_tls = True

    if not all([smtp_user, smtp_password]):
        raise ValueError("Gmail credentials (user and app password) are not configured.")

    if html_content:
        msg = MIMEMultipart('alternative')
        part1 = MIMEText(text_content, 'plain', 'utf-8')
        part2 = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(part1)
        msg.attach(part2)
    else:
        msg = MIMEText(text_content, 'plain', 'utf-8')

    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if use_tls:
                server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, [to_email], msg.as_string())
        print(f"INFO: Email (Gmail) sent to {to_email}")
    except Exception as e:
        print(f"CRITICAL: Failed to send Gmail email. Error: {e}")
        raise

def _send_email_system_mail_text(to_email: str, subject: str, text_content: str):
    """Sends a plain text email using system commands."""
    
    # Try sendmail first
    if shutil.which("sendmail"):
        safe_subject = subject.replace("\n", " ").replace("\r", " ")
        full_email = (
            f"To: {to_email}\n"
            f"Subject: {safe_subject}\n"
            f"Content-Type: text/plain; charset=utf-8\n"
            f"\n"
            f"{text_content}"
        )
        # -t reads recipients from headers
        command = ["sendmail", "-t"]
        try:
            subprocess.run(command, input=full_email, capture_output=True, text=True, check=True, encoding="utf-8")
            print(f"INFO: Email (Text system mail) sent to {to_email} via sendmail.")
            return
        except subprocess.CalledProcessError as e:
            print(f"WARNING: sendmail failed: {e.stderr}")
            # Fall through to mailx

    if not shutil.which("mailx"):
        raise FileNotFoundError("Neither 'sendmail' nor 'mailx' found.")
    
    # Fallback to mailx for simple text
    command = ["mailx", "-s", subject, to_email]
    try:
        subprocess.run(command, input=text_content, capture_output=True, text=True, check=True, encoding="utf-8")
        print(f"INFO: Email (Text system mail) sent to {to_email} via mailx.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: mailx failed: {e.stderr}")
        raise

def _send_email_system_mail_html(to_email: str, subject: str, html_content: str, text_content: str):
    """Alternative approach using sendmail or a temporary file with mailx."""
    
    # Check for sendmail first (more reliable for MIME)
    if shutil.which("sendmail"):
        return _send_email_sendmail_html(to_email, subject, html_content, text_content)
    
    if not shutil.which("mailx"):
        raise FileNotFoundError("Neither 'sendmail' nor 'mailx' found.")
    
    safe_subject = subject.replace("\n", " ").replace("\r", " ")
    boundary = f"----=_NextPart_{secrets.token_hex(16)}"
    
    # Create full email with headers
    full_email = (
        f"To: {to_email}\n"
        f"Subject: {safe_subject}\n"
        f"MIME-Version: 1.0\n"
        f"Content-Type: multipart/alternative; boundary=\"{boundary}\"\n"
        f"\n"
        f"This is a multi-part message in MIME format.\n"
        f"--{boundary}\n"
        f"Content-Type: text/plain; charset=utf-8\n"
        f"Content-Transfer-Encoding: 8bit\n\n"
        f"{text_content}\n\n"
        f"--{boundary}\n"
        f"Content-Type: text/html; charset=utf-8\n"
        f"Content-Transfer-Encoding: 8bit\n\n"
        f"{html_content}\n\n"
        f"--{boundary}--\n"
    )
    
    # Write to temp file and use mailx -t (read headers from message)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.eml', delete=False) as f:
        f.write(full_email)
        temp_file = f.name
    
    try:
        command = ["mailx", "-v", "-t"]  # -t means read headers from message
        
        with open(temp_file, 'r') as f:
            process = subprocess.run(
                command,
                stdin=f,
                capture_output=True,
                text=True,
                check=True
            )
        
        print(f"INFO: Email (HTML system mail) sent to {to_email}.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: System 'mailx' command failed.\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}")
        raise
    finally:
        os.unlink(temp_file)

def _send_email_sendmail_html(to_email: str, subject: str, html_content: str, text_content: str):
    """Send HTML email using sendmail (more reliable for MIME)."""
    
    if not shutil.which("sendmail"):
        raise FileNotFoundError("The 'sendmail' command not found.")
    
    safe_subject = subject.replace("\n", " ").replace("\r", " ")
    boundary = f"----=_NextPart_{secrets.token_hex(16)}"
    
    full_email = (
        f"To: {to_email}\n"
        f"Subject: {safe_subject}\n"
        f"MIME-Version: 1.0\n"
        f"Content-Type: multipart/alternative; boundary=\"{boundary}\"\n"
        f"\n"
        f"This is a multi-part message in MIME format.\n"
        f"--{boundary}\n"
        f"Content-Type: text/plain; charset=utf-8\n"
        f"Content-Transfer-Encoding: 8bit\n\n"
        f"{text_content}\n\n"
        f"--{boundary}\n"
        f"Content-Type: text/html; charset=utf-8\n"
        f"Content-Transfer-Encoding: 8bit\n\n"
        f"{html_content}\n\n"
        f"--{boundary}--\n"
    )
    
    # Use -t to read headers from the input (To, Subject, etc.)
    command = ["sendmail", "-t"]
    
    try:
        process = subprocess.run(
            command,
            input=full_email,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8"
        )
        print(f"INFO: Email sent via sendmail to {to_email}.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Sendmail command failed.\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}")
        raise

def _send_email_outlook(to_email: str, subject: str, body: str):
    """Sends an email using Outlook."""
    try:
        import win32com.client
    except ImportError:
        print("win32com.client not installed. Please install pywin32.")
        return

    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To = to_email
        mail.Subject = subject
        # Check if the body contains HTML tags.  If so, treat it as HTML.
        if "<" in body and ">" in body:
            mail.HTMLBody = body  # Use HTMLBody for HTML content
        else:
            mail.Body = body  # Use Body for plain text
        mail.Send()
        print(f"INFO: Email sent using Outlook to {to_email}")
    except Exception as e:
        print(f"ERROR: Failed to send email using Outlook. Error: {e}")


def send_generic_email(to_email: str, subject: str, body: str, background_color: Optional[str] = "#f4f4f4", send_as_text: bool = False):
    """
    Prepares and sends a generic email, handling both HTML and plain text modes correctly.
    """
    recovery_mode = settings.get("password_recovery_mode", "manual")
    
    # Prepare HTML wrapper if needed
    html_body = _get_full_html_email(body, background_color) if not send_as_text else None
    
    # FIX: Accept 'automatic' as 'smtp' since that's what the UI/Settings calls it
    if recovery_mode == "smtp" or recovery_mode == "automatic":
        text_content = _convert_html_to_text(body)
        _send_email_smtp(to_email, subject, html_body, text_content)
    elif recovery_mode == "gmail":
        text_content = _convert_html_to_text(body)
        _send_email_gmail(to_email, subject, html_body, text_content)
    elif recovery_mode == "system_mail":
        text_content = _convert_html_to_text(body)
        if send_as_text:
             _send_email_system_mail_text(to_email, subject, text_content)
        else:
             _send_email_system_mail_html(to_email, subject, html_body, text_content)
    elif recovery_mode == "outlook":
        if platform.system() == "Windows":
            _send_email_outlook(to_email, subject, body)
        else:
            print("Outlook integration is only supported on Windows.")
    else:
        print(f"WARNING: Email sending is set to '{recovery_mode}'. No email sending configured or manual mode active.")

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

def decode_main_access_token(token: str) -> Optional[dict]:
    """Decodes a main application JWT using the global SECRET_KEY."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def decode_sso_token(token: str, secret_key: str, audience: str) -> Optional[dict]:
    """Decodes an SSO JWT using the application-specific secret key and audience."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM], audience=audience)
        return payload
    except JWTError:
        return None
