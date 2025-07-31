import traceback
import datetime
from typing import Dict, Optional, Union, List

from fastapi import APIRouter, Depends, HTTPException, status, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_
from jose import JWTError, jwt
from ascii_colors import ASCIIColors

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.service import App as DBApp, MCP as DBMCP
from backend.models import (
    UserAuthDetails,
    UserPublic
)
from backend.security import verify_password, ALGORITHM, create_sso_token, decode_sso_token
from backend.session import get_current_active_user
from backend.config import SECRET_KEY

sso_router = APIRouter(prefix="/api/sso", tags=["SSO"])

class SSOAppDetailsResponse(BaseModel):
    name: str
    icon: Optional[str] = None
    sso_user_infos_to_share: List[str] = []

def get_app_or_mcp_by_client_id(db: Session, client_id: str) -> Optional[Union[DBApp, DBMCP]]:
    """Fetches an App or MCP by its unique client_id."""
    app = db.query(DBApp).filter(DBApp.client_id == client_id).first()
    if app:
        return app
    mcp = db.query(DBMCP).filter(DBMCP.client_id == client_id).first()
    return mcp

@sso_router.get("/app_details/{client_id}", response_model=SSOAppDetailsResponse)
def get_app_details(client_id: str, db: Session = Depends(get_db)):
    """Provides public details about an app for the SSO login screen."""
    ASCIIColors.info(f"[SSO] App details requested for client_id: {client_id}")
    service = get_app_or_mcp_by_client_id(db, client_id)
    
    if not service:
        ASCIIColors.error(f"[SSO] Service with client_id '{client_id}' not found.")
        raise HTTPException(status_code=404, detail="Application not found.")
        
    if not service.active or service.authentication_type != 'lollms_sso':
        ASCIIColors.warning(f"[SSO] Service '{service.name}' found but is inactive or SSO is not enabled.")
        raise HTTPException(status_code=404, detail="Application not found or SSO is not enabled for it.")
    
    ASCIIColors.green(f"[SSO] Found service '{service.name}' for client_id '{client_id}'. Returning details.")
    return SSOAppDetailsResponse(
        name=service.name,
        icon=service.icon,
        sso_user_infos_to_share=service.sso_user_infos_to_share or []
    )

@sso_router.post("/token")
def sso_login_for_token(
    client_id: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Authenticates a user and returns an app-specific JWT for SSO.
    This is called by the LoLLMs UI itself during the SSO flow.
    """
    ASCIIColors.info(f"[SSO] Token request received for client_id: {client_id}, user: {username}")
    service = get_app_or_mcp_by_client_id(db, client_id)
    if not service or not service.active or service.authentication_type != 'lollms_sso':
        ASCIIColors.error(f"[SSO] Invalid client_id '{client_id}' or SSO not configured correctly.")
        raise HTTPException(status_code=400, detail="Invalid application or SSO not configured correctly.")

    user = db.query(DBUser).filter(DBUser.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        ASCIIColors.warning(f"[SSO] Authentication failed for user '{username}'.")
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    if not user.is_active:
        ASCIIColors.warning(f"[SSO] User '{username}' is inactive.")
        raise HTTPException(status_code=403, detail="User account is inactive.")

    ASCIIColors.green(f"[SSO] User '{username}' authenticated successfully for '{service.name}'.")
    user_data_to_share = {"username": user.username}
    allowed_scopes = service.sso_user_infos_to_share or []
    ASCIIColors.info(f"[SSO] Allowed scopes for '{service.name}': {allowed_scopes}")
    
    if "email" in allowed_scopes: user_data_to_share["email"] = user.email
    if "first_name" in allowed_scopes: user_data_to_share["first_name"] = user.first_name
    if "family_name" in allowed_scopes: user_data_to_share["family_name"] = user.family_name
    if "birth_date" in allowed_scopes and user.birth_date:
        user_data_to_share["birth_date"] = user.birth_date.isoformat()

    ASCIIColors.info(f"[SSO] User data being shared: {list(user_data_to_share.keys())}")
    to_encode = { "sub": user.username, "user_info": user_data_to_share }
    
    encoded_jwt = create_sso_token(to_encode, SECRET_KEY, audience=client_id)
    ASCIIColors.green(f"[SSO] SSO token generated for user '{username}' and client '{client_id}'.")
    return {"access_token": encoded_jwt, "token_type": "bearer"}

@sso_router.post("/authorize")
def sso_authorize_logged_in_user(
    client_id: str = Form(...),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generates an SSO token for an already authenticated user."""
    ASCIIColors.info(f"[SSO] Authorization request for logged-in user '{current_user.username}' and client_id '{client_id}'.")
    service = get_app_or_mcp_by_client_id(db, client_id)
    if not service or not service.active or service.authentication_type != 'lollms_sso':
        ASCIIColors.error(f"[SSO] Invalid client_id '{client_id}' or SSO not configured correctly for logged-in user flow.")
        raise HTTPException(status_code=400, detail="Invalid application or SSO not configured correctly.")

    user = db.query(DBUser).filter(DBUser.id == current_user.id).first()

    user_data_to_share = {"username": user.username}
    allowed_scopes = service.sso_user_infos_to_share or []
    ASCIIColors.info(f"[SSO] Allowed scopes for '{service.name}': {allowed_scopes}")
    
    if "email" in allowed_scopes: user_data_to_share["email"] = user.email
    if "first_name" in allowed_scopes: user_data_to_share["first_name"] = user.first_name
    if "family_name" in allowed_scopes: user_data_to_share["family_name"] = user.family_name
    if "birth_date" in allowed_scopes and user.birth_date:
        user_data_to_share["birth_date"] = user.birth_date.isoformat()
    
    ASCIIColors.info(f"[SSO] User data being shared: {list(user_data_to_share.keys())}")
    to_encode = { "sub": user.username, "user_info": user_data_to_share }
    
    encoded_jwt = create_sso_token(to_encode, SECRET_KEY, audience=client_id)
    ASCIIColors.green(f"[SSO] SSO token generated for user '{user.username}' and client '{client_id}'.")
    return {"access_token": encoded_jwt, "token_type": "bearer", "sso_redirect_uri":service.sso_redirect_uri}


@sso_router.post("/introspect")
def sso_introspect_token(
    token: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Lets a client application verify an SSO token.
    """
    ASCIIColors.info(f"[SSO] Token introspection request received.")
    try:
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        client_id = unverified_payload.get("aud")
        if not client_id:
            raise JWTError("Audience (client_id) not found in token.")
        ASCIIColors.info(f"[SSO] Token introspection for aud (client_id): {client_id}")
    except JWTError as e:
        ASCIIColors.warning(f"[SSO] Introspection failed: Invalid token structure. {e}")
        return {"active": False, "error": f"Invalid token structure: {e}"}

    service = get_app_or_mcp_by_client_id(db, client_id)
    if not service:
        ASCIIColors.error(f"[SSO] Introspection failed: Service for client_id '{client_id}' not found.")
        return {"active": False, "error": "Application not found or SSO misconfigured."}

    payload = decode_sso_token(token, SECRET_KEY, audience=client_id)
    if not payload:
        ASCIIColors.warning(f"[SSO] Introspection failed: Token validation failed for client_id '{client_id}'.")
        return {"active": False, "error": "Token validation failed: Invalid signature, expiration, or audience."}

    user = db.query(DBUser).filter(DBUser.username == payload.get("sub")).first()
    if not user or not user.is_active:
        ASCIIColors.warning(f"[SSO] Introspection failed: User '{payload.get('sub')}' not found or is inactive.")
        return {"active": False, "error": "User does not exist or is inactive."}
    
    ASCIIColors.green(f"[SSO] Introspection successful for user '{user.username}' and client '{client_id}'.")
    return {"active": True, **payload}