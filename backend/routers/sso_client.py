# [CREATE] backend/routers/sso_client.py
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
import secrets

from backend.db import get_db
from backend.settings import settings
from backend.db.models.user import User as DBUser
from backend.security import create_access_token, get_password_hash
from backend.config import APP_SETTINGS

sso_client_router = APIRouter(prefix="/api/sso-client", tags=["SSO Client"])

oauth = OAuth()

def get_oauth_client():
    if not settings.get("sso_client_enabled"):
        raise HTTPException(status_code=404, detail="SSO not enabled")

    # Clear previous registration if settings have changed
    if 'oidc_provider' in oauth._clients:
        client_id_changed = oauth._clients['oidc_provider'].client_id != settings.get("sso_client_id")
        secret_changed = oauth._clients['oidc_provider'].client_secret != settings.get("sso_client_secret")
        url_changed = oauth._clients['oidc_provider'].server_metadata_url != settings.get("sso_client_provider_url")
        
        if client_id_changed or secret_changed or url_changed:
            oauth.unregister('oidc_provider')

    if 'oidc_provider' not in oauth._clients:
        discovery_url = settings.get("sso_client_provider_url")
        if not discovery_url:
            raise HTTPException(status_code=500, detail="SSO Provider URL not configured")
        
        oauth.register(
            name='oidc_provider',
            client_id=settings.get("sso_client_id"),
            client_secret=settings.get("sso_client_secret"),
            server_metadata_url=discovery_url,
            client_kwargs={'scope': 'openid email profile'},
        )
    return oauth.oidc_provider

@sso_client_router.get("/config")
def get_sso_config():
    return {
        "enabled": settings.get("sso_client_enabled"),
        "display_name": settings.get("sso_client_display_name"),
        "icon_url": settings.get("sso_client_icon_url"),
    }

@sso_client_router.get("/login")
async def sso_login(request: Request):
    client = get_oauth_client()
    redirect_uri = request.url_for('sso_callback')
    return await client.authorize_redirect(request, redirect_uri)

@sso_client_router.get("/callback", name="sso_callback")
async def sso_callback(request: Request, db: Session = Depends(get_db)):
    client = get_oauth_client()
    try:
        token = await client.authorize_access_token(request)
        user_info = await client.parse_id_token(request, token)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"SSO authentication failed: {e}")

    email = user_info.get('email')
    if not email:
        raise HTTPException(status_code=400, detail="Email not provided by SSO provider.")

    user = db.query(DBUser).filter(DBUser.email == email).first()

    if not user:
        if not settings.get("sso_client_auto_create_users"):
            return HTMLResponse(content=f"<h1>Login Failed</h1><p>User with email {email} does not exist. Please contact an administrator to create an account.</p>")

        username = user_info.get('preferred_username', user_info.get('name', email.split('@')[0]))
        base_username = username
        counter = 1
        while db.query(DBUser).filter(DBUser.username == username).first():
            username = f"{base_username}{counter}"
            counter += 1

        user = DBUser(
            username=username,
            email=email,
            first_name=user_info.get('given_name'),
            family_name=user_info.get('family_name'),
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            is_active=True,
            first_login_done=True,
            lollms_model_name=settings.get("default_lollms_model_name"),
            safe_store_vectorizer=settings.get("default_safe_store_vectorizer"),
            llm_ctx_size=settings.get("default_llm_ctx_size"),
            user_ui_level=settings.get("default_user_ui_level", 0),
            auto_title=settings.get("default_auto_title", False),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    if not user.is_active:
        return HTMLResponse(content="<h1>Login Failed</h1><p>Your account is inactive. Please contact an administrator.</p>")

    lollms_token = create_access_token(data={"sub": user.username})

    html_content = f"""
    <html>
        <head><title>Redirecting...</title></head>
        <body>
            <script>
                localStorage.setItem('lollms-token', '{lollms_token}');
                window.location.href = '/';
            </script>
            <p>Authentication successful. Redirecting you to the application...</p>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)
