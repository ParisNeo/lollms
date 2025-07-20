import traceback
import datetime
from typing import Dict, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from sqlalchemy import or_
from jose import JWTError, jwt

from backend.database_setup import (
    User as DBUser,
    App as DBApp,
    MCP as DBMCP,
    get_db,
)
from backend.models import (
    UserAuthDetails,
    UserPublic
)
from backend.security import verify_password, ALGORITHM, create_sso_token, decode_sso_token
from backend.session import get_current_active_user

sso_router = APIRouter(prefix="/api/sso", tags=["SSO"])

class AppDetailsResponse(UserPublic):
    name: str
    icon: Optional[str] = None
    sso_user_infos_to_share: list[str] = []

def get_app_or_mcp(db: Session, app_name: str) -> Optional[Union[DBApp, DBMCP]]:
    """Fetches an App or MCP by its unique name."""
    app = db.query(DBApp).filter(DBApp.name == app_name).first()
    if app:
        return app
    mcp = db.query(DBMCP).filter(DBMCP.name == app_name).first()
    return mcp

@sso_router.get("/app_details/{app_name}")
def get_app_details(app_name: str, db: Session = Depends(get_db)):
    """Provides public details about an app for the SSO login screen."""
    service = get_app_or_mcp(db, app_name)
    if not service or not service.active or service.authentication_type != 'lollms_sso':
        raise HTTPException(status_code=404, detail="Application not found or SSO is not enabled for it.")
    
    return {
        "name": service.name,
        "icon": service.icon,
        "sso_user_infos_to_share": service.sso_user_infos_to_share or []
    }

@sso_router.post("/token")
def sso_login_for_token(
    app_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Authenticates a user and returns an app-specific JWT for SSO.
    This is called by the LoLLMs UI itself during the SSO flow.
    """
    service = get_app_or_mcp(db, app_name)
    if not service or not service.active or service.authentication_type != 'lollms_sso' or not service.sso_secret:
        raise HTTPException(status_code=400, detail="Invalid application or SSO not configured correctly.")

    user = db.query(DBUser).filter(DBUser.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive.")

    user_data_to_share = {"username": user.username}
    allowed_scopes = service.sso_user_infos_to_share or []
    
    if "email" in allowed_scopes: user_data_to_share["email"] = user.email
    if "first_name" in allowed_scopes: user_data_to_share["first_name"] = user.first_name
    if "family_name" in allowed_scopes: user_data_to_share["family_name"] = user.family_name
    if "birth_date" in allowed_scopes and user.birth_date:
        user_data_to_share["birth_date"] = user.birth_date.isoformat()

    to_encode = {
        "sub": user.username,
        "user_info": user_data_to_share
    }
    
    encoded_jwt = create_sso_token(to_encode, service.sso_secret, audience=app_name)
    return {"access_token": encoded_jwt, "token_type": "bearer"}

@sso_router.post("/authorize")
def sso_authorize_logged_in_user(
    app_name: str = Form(...),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generates an SSO token for an already authenticated user."""
    service = get_app_or_mcp(db, app_name)
    if not service or not service.active or service.authentication_type != 'lollms_sso' or not service.sso_secret:
        raise HTTPException(status_code=400, detail="Invalid application or SSO not configured correctly.")

    user = db.query(DBUser).filter(DBUser.id == current_user.id).first()

    user_data_to_share = {"username": user.username}
    allowed_scopes = service.sso_user_infos_to_share or []
    
    if "email" in allowed_scopes: user_data_to_share["email"] = user.email
    if "first_name" in allowed_scopes: user_data_to_share["first_name"] = user.first_name
    if "family_name" in allowed_scopes: user_data_to_share["family_name"] = user.family_name
    if "birth_date" in allowed_scopes and user.birth_date:
        user_data_to_share["birth_date"] = user.birth_date.isoformat()

    to_encode = {
        "sub": user.username,
        "user_info": user_data_to_share
    }
    
    encoded_jwt = create_sso_token(to_encode, service.sso_secret, audience=app_name)
    return {"access_token": encoded_jwt, "token_type": "bearer"}


@sso_router.post("/introspect")
def sso_introspect_token(
    token: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Lets a client application verify an SSO token.
    """
    try:
        # First, decode without verification to get the audience (app_name)
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        app_name = unverified_payload.get("aud")
        if not app_name:
            raise JWTError("Audience (app_name) not found in token.")
    except JWTError as e:
        return {"active": False, "error": f"Invalid token structure: {e}"}

    service = get_app_or_mcp(db, app_name)
    if not service or not service.sso_secret:
        return {"active": False, "error": "Application not found or SSO misconfigured."}

    payload = decode_sso_token(token, service.sso_secret, audience=app_name)
    if not payload:
        return {"active": False, "error": "Token validation failed: Invalid signature, expiration, or audience."}

    # Check if the user still exists and is active in our system
    user = db.query(DBUser).filter(DBUser.username == payload.get("sub")).first()
    if not user or not user.is_active:
        return {"active": False, "error": "User does not exist or is inactive."}
        
    return {"active": True, **payload}