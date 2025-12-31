# backend/routers/services_management.py
import re
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.db import get_db
from backend.db.models.service import MCP as DBMCP, App as DBApp
from backend.db.models.user import User as DBUser
from backend.session import get_current_active_user, get_current_admin_user

router = APIRouter(tags=["Services Management"])

# --- Pydantic Models ---
class ServiceBase(BaseModel):
    name: str
    url: str
    description: Optional[str] = None
    icon: Optional[str] = None
    authentication_type: Optional[str] = None
    authentication_key: Optional[str] = None
    sso_redirect_uri: Optional[str] = None
    sso_user_infos_to_share: Optional[List[str]] = None
    client_id: Optional[str] = None

class MCPCreate(ServiceBase):
    pass

class MCPUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    active: Optional[bool] = None
    authentication_type: Optional[str] = None
    authentication_key: Optional[str] = None
    sso_redirect_uri: Optional[str] = None
    sso_user_infos_to_share: Optional[List[str]] = None

class MCPOut(ServiceBase):
    id: int
    type: str
    active: bool
    owner_user_id: Optional[int] = None
    
    class Config:
        from_attributes = True

class AppCreate(ServiceBase):
    pass

class AppOut(ServiceBase):
    id: int
    type: str
    active: bool
    owner_user_id: Optional[int] = None
    status: str
    
    class Config:
        from_attributes = True

# --- MCP Endpoints ---

@router.get("/api/mcps", response_model=List[MCPOut])
def list_mcps(
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lists all MCPs available to the user (System MCPs + User's own MCPs).
    """
    mcps = db.query(DBMCP).filter(
        (DBMCP.type == 'system') | 
        ((DBMCP.type == 'user') & (DBMCP.owner_user_id == current_user.id))
    ).all()
    return mcps

@router.post("/api/mcps", response_model=MCPOut)
def create_mcp(
    mcp_data: MCPCreate,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Registers a new personal MCP for the current user.
    """
    # Auto-generate client_id if not provided
    if not mcp_data.client_id:
        base_slug = re.sub(r'[^a-z0-9_]+', '', mcp_data.name.lower().replace(' ', '_'))
        new_client_id = base_slug
        counter = 1
        while db.query(DBMCP).filter(DBMCP.client_id == new_client_id).first():
            new_client_id = f"{base_slug}_{counter}"
            counter += 1
        mcp_data.client_id = new_client_id

    # Create the MCP record
    new_mcp = DBMCP(
        name=mcp_data.name,
        url=mcp_data.url,
        description=mcp_data.description,
        icon=mcp_data.icon,
        authentication_type=mcp_data.authentication_type,
        authentication_key=mcp_data.authentication_key,
        sso_redirect_uri=mcp_data.sso_redirect_uri,
        sso_user_infos_to_share=mcp_data.sso_user_infos_to_share,
        client_id=mcp_data.client_id,
        
        # Enforce user ownership
        owner_user_id=current_user.id,
        type='user',  # CRITICAL: Must be 'user' to appear in "My Personal MCPs"
        active=True
    )
    
    db.add(new_mcp)
    db.commit()
    db.refresh(new_mcp)
    return new_mcp

@router.put("/api/mcps/{mcp_id}", response_model=MCPOut)
def update_mcp(
    mcp_id: int,
    mcp_update: MCPUpdate,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    mcp = db.query(DBMCP).filter(DBMCP.id == mcp_id).first()
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP not found")
    
    # Only allow owner or admin to edit
    if mcp.owner_user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to edit this MCP")

    update_data = mcp_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(mcp, key, value)

    db.commit()
    db.refresh(mcp)
    return mcp

@router.delete("/api/mcps/{mcp_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mcp(
    mcp_id: int,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    mcp = db.query(DBMCP).filter(DBMCP.id == mcp_id).first()
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP not found")

    if mcp.owner_user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this MCP")

    db.delete(mcp)
    db.commit()

# --- App Endpoints (for consistency) ---

@router.get("/api/apps", response_model=List[AppOut])
def list_apps(
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return db.query(DBApp).filter(
        (DBApp.type == 'system') | 
        ((DBApp.type == 'user') & (DBApp.owner_user_id == current_user.id))
    ).all()

@router.post("/api/apps", response_model=AppOut)
def create_app(
    app_data: AppCreate,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not app_data.client_id:
        base_slug = re.sub(r'[^a-z0-9_]+', '', app_data.name.lower().replace(' ', '_'))
        new_client_id = base_slug
        counter = 1
        while db.query(DBApp).filter(DBApp.client_id == new_client_id).first():
            new_client_id = f"{base_slug}_{counter}"
            counter += 1
        app_data.client_id = new_client_id

    new_app = DBApp(
        name=app_data.name,
        url=app_data.url,
        description=app_data.description,
        icon=app_data.icon,
        authentication_type=app_data.authentication_type,
        authentication_key=app_data.authentication_key,
        sso_redirect_uri=app_data.sso_redirect_uri,
        sso_user_infos_to_share=app_data.sso_user_infos_to_share,
        client_id=app_data.client_id,
        
        owner_user_id=current_user.id,
        type='user',
        active=True,
        is_installed=True,
        status='running' 
    )
    
    db.add(new_app)
    db.commit()
    db.refresh(new_app)
    return new_app

@router.delete("/api/apps/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_app(
    app_id: int,
    current_user: DBUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    app = db.query(DBApp).filter(DBApp.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    if app.owner_user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this App")

    db.delete(app)
    db.commit()
