# backend/routers/mcp.py
import traceback
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from backend.database_setup import get_db, MCP as DBMCP, App as DBApp
from backend.security import generate_sso_secret
from backend.session import get_current_active_user, get_user_lollms_client, user_sessions, load_mcps
from backend.models import (
    MCPCreate, MCPUpdate, MCPPublic, ToolInfo,
    AppCreate, AppUpdate, AppPublic,
    DiscussionToolsUpdate, DiscussionInfo, UserAuthDetails,
    SSOSecretResponse
)
from backend.discussion import get_user_discussion

mcp_router = APIRouter(prefix="/api/mcps", tags=["Services"])
apps_router = APIRouter(prefix="/api/apps", tags=["Services"])
discussion_tools_router = APIRouter(prefix="/api/discussions", tags=["Services"])

def _invalidate_user_mcp_cache(username: str):
    """Invalidates the lollms_client and tools cache for a given user."""
    if username in user_sessions and 'tools_cache' in user_sessions[username]:
        del user_sessions[username]['tools_cache']
        print(f"INFO: Invalidated tools cache for user: {username}")

def _format_mcp_public(mcp: DBMCP) -> MCPPublic:
    return MCPPublic(
        id=mcp.id, name=mcp.name, url=mcp.url, icon=mcp.icon,
        active=mcp.active, type=mcp.type,
        authentication_type=mcp.authentication_type,
        authentication_key="********" if mcp.authentication_key else "",
        owner_username=mcp.owner.username if mcp.owner else "System",
        created_at=mcp.created_at, updated_at=mcp.updated_at,
        sso_redirect_uri=mcp.sso_redirect_uri,
        sso_user_infos_to_share=mcp.sso_user_infos_to_share or [],
        sso_secret_exists=bool(mcp.sso_secret)
    )

@mcp_router.get("", response_model=List[MCPPublic])
def list_mcps(
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    query = db.query(DBMCP).options(joinedload(DBMCP.owner))
    if not current_user.is_admin:
        query = query.filter(or_(DBMCP.owner_user_id == current_user.id, DBMCP.type == 'system'))
    
    mcps_db = query.all()
    return [_format_mcp_public(mcp) for mcp in mcps_db]

@mcp_router.post("", response_model=MCPPublic, status_code=201)
def create_mcp(
    mcp_data: MCPCreate,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    if mcp_data.type == 'system' and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can create system-level MCPs.")
    
    owner_id = current_user.id if mcp_data.type == 'user' else None
    
    new_mcp = DBMCP(**mcp_data.model_dump(), owner_user_id=owner_id)
    db.add(new_mcp)
    try:
        db.commit()
        db.refresh(new_mcp, ["owner"])
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An MCP with this name already exists for this owner (user or system).")
    
    _invalidate_user_mcp_cache(current_user.username)
    return _format_mcp_public(new_mcp)

@mcp_router.put("/{mcp_id}", response_model=MCPPublic)
def update_mcp(
    mcp_id: str,
    mcp_update: MCPUpdate,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    mcp_db = db.query(DBMCP).filter(DBMCP.id == mcp_id).first()
    if not mcp_db:
        raise HTTPException(status_code=404, detail="MCP not found.")

    is_owner = mcp_db.owner_user_id == current_user.id
    if not is_owner and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to edit this MCP.")

    update_data = mcp_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(mcp_db, key, value)
    
    try:
        db.commit()
        db.refresh(mcp_db, ["owner"])
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An MCP with the new name already exists.")

    _invalidate_user_mcp_cache(current_user.username)
    return _format_mcp_public(mcp_db)

@mcp_router.post("/{mcp_id}/generate-sso-secret", response_model=SSOSecretResponse)
def generate_mcp_sso_secret(
    mcp_id: str,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    mcp_db = db.query(DBMCP).filter(DBMCP.id == mcp_id).first()
    if not mcp_db:
        raise HTTPException(status_code=404, detail="MCP not found.")

    is_owner = mcp_db.owner_user_id == current_user.id
    if not is_owner and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to generate a secret for this MCP.")

    new_secret = generate_sso_secret()
    mcp_db.sso_secret = new_secret
    db.commit()
    
    return SSOSecretResponse(sso_secret=new_secret)

@mcp_router.delete("/{mcp_id}", status_code=204)
def delete_mcp(
    mcp_id: str,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    mcp_db = db.query(DBMCP).filter(DBMCP.id == mcp_id).first()
    if not mcp_db:
        raise HTTPException(status_code=404, detail="MCP not found.")

    is_owner = mcp_db.owner_user_id == current_user.id
    if not is_owner and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this MCP.")

    db.delete(mcp_db)
    db.commit()
    _invalidate_user_mcp_cache(current_user.username)
    return None

# --- APPS LOGIC (Consolidated) ---

def _format_app_public(app: DBApp) -> AppPublic:
    return AppPublic(
        id=app.id, name=app.name, url=app.url, icon=app.icon,
        active=app.active, type=app.type,
        authentication_type=app.authentication_type,
        authentication_key="********" if app.authentication_key else "",
        owner_username=app.owner.username if app.owner else "System",
        created_at=app.created_at, updated_at=app.updated_at,
        sso_redirect_uri=app.sso_redirect_uri,
        sso_user_infos_to_share=app.sso_user_infos_to_share or [],
        sso_secret_exists=bool(app.sso_secret)
    )

@apps_router.get("", response_model=List[AppPublic])
def list_apps(db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_active_user)):
    query = db.query(DBApp).options(joinedload(DBApp.owner))
    if not current_user.is_admin:
        query = query.filter(or_(DBApp.owner_user_id == current_user.id, DBApp.type == 'system'))
        
    apps_db = query.all()
    return [_format_app_public(app) for app in apps_db]

@apps_router.post("", response_model=AppPublic, status_code=201)
def create_app(app_data: AppCreate, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_active_user)):
    if app_data.type == 'system' and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can create system-level apps.")
    
    owner_id = current_user.id if app_data.type == 'user' else None
    
    new_app = DBApp(**app_data.model_dump(), owner_user_id=owner_id)
    db.add(new_app)
    try:
        db.commit()
        db.refresh(new_app, ["owner"])
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An app with this name already exists for this owner (user or system).")
    return _format_app_public(new_app)

@apps_router.put("/{app_id}", response_model=AppPublic)
def update_app(app_id: str, app_update: AppUpdate, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_active_user)):
    app_db = db.query(DBApp).filter(DBApp.id == app_id).first()
    if not app_db:
        raise HTTPException(status_code=404, detail="App not found.")
    
    is_owner = app_db.owner_user_id == current_user.id
    if not is_owner and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to edit this app.")

    update_data = app_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(app_db, key, value)
    
    try:
        db.commit()
        db.refresh(app_db, ["owner"])
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An app with the new name already exists.")
    return _format_app_public(app_db)

@apps_router.post("/{app_id}/generate-sso-secret", response_model=SSOSecretResponse)
def generate_app_sso_secret(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    app_db = db.query(DBApp).filter(DBApp.id == app_id).first()
    if not app_db:
        raise HTTPException(status_code=404, detail="App not found.")

    is_owner = app_db.owner_user_id == current_user.id
    if not is_owner and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to generate a secret for this App.")

    new_secret = generate_sso_secret()
    app_db.sso_secret = new_secret
    db.commit()
    
    return SSOSecretResponse(sso_secret=new_secret)

@apps_router.delete("/{app_id}", status_code=204)
def delete_app(app_id: str, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_active_user)):
    app_db = db.query(DBApp).filter(DBApp.id == app_id).first()
    if not app_db:
        raise HTTPException(status_code=404, detail="App not found.")

    is_owner = app_db.owner_user_id == current_user.id
    if not is_owner and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this app.")

    db.delete(app_db)
    db.commit()
    return None

# --- TOOLS AND DISCUSSION LOGIC ---

@mcp_router.post("/reload", status_code=200)
def reload_user_lollms_client(current_user: UserAuthDetails = Depends(get_current_active_user)):
    _invalidate_user_mcp_cache(current_user.username)
    lc = get_user_lollms_client(current_user.username)
    lc.mcp = None
    servers_infos=load_mcps(current_user.username)
    lc.mcp = lc.mcp_binding_manager.create_binding(
                "remote_mcp",
                servers_infos = servers_infos
            )

    print(f"INFO: Triggered lollms_client reload for user: {current_user.username}")
    return {"status": "success", "message": "MCP client and tools cache re-initialized."}

@mcp_router.get("/tools", response_model=List[ToolInfo])
def list_all_available_tools(current_user: UserAuthDetails = Depends(get_current_active_user)):
    username = current_user.username
    if username not in user_sessions:
        user_sessions[username] = {}

    cached_tools = user_sessions[username].get('tools_cache')
    if cached_tools is not None:
        print(f"INFO: Serving cached tools for user: {username}")
        return cached_tools

    print(f"INFO: Building tools cache for user: {username}")
    try:
        lc = get_user_lollms_client(username)
        if not hasattr(lc, 'mcp') or not lc.mcp:
            user_sessions[username]['tools_cache'] = []
            return []
        
        tools = lc.mcp.discover_tools(force_refresh=True)
        all_tools = [ToolInfo(name=item["name"], description=item.get('description', '')) for item in tools]
        sorted_tools = sorted(all_tools, key=lambda x: x.name)
        
        user_sessions[username]['tools_cache'] = sorted_tools
        return sorted_tools
    except Exception as e:
        print(f"Error discovering tools for user {username}: {e}")
        traceback.print_exc()
        return []

@discussion_tools_router.get("/{discussion_id}/tools", response_model=List[ToolInfo])
def get_discussion_tools(
    discussion_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    discussion_obj = get_user_discussion(current_user.username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    all_available_tools = list_all_available_tools(current_user)
    
    metadata = discussion_obj.metadata or {}
    active_tool_names = set(metadata.get('active_tools', []))

    for tool in all_available_tools:
        tool.is_active = tool.name in active_tool_names
            
    return all_available_tools

@discussion_tools_router.put("/{discussion_id}/tools", response_model=DiscussionInfo)
async def update_discussion_tools(
    discussion_id: str,
    update_request: DiscussionToolsUpdate,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    from backend.database_setup import UserStarredDiscussion
    user_model_full = current_user.lollms_model_name
    binding_alias = None
    if user_model_full and '/' in user_model_full:
        binding_alias, _ = user_model_full.split('/', 1)
    lc = get_user_lollms_client(current_user.username, binding_alias)    
    discussion_obj = get_user_discussion(current_user.username, discussion_id, lollms_client=lc)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    discussion_obj.set_metadata_item('active_tools', update_request.tools)
    is_starred = db.query(UserStarredDiscussion).filter_by(user_id=current_user.id, discussion_id=discussion_id).first() is not None

    return DiscussionInfo(
        id=discussion_obj.id,
        title=discussion_obj.metadata.get('title', 'Untitled'),
        is_starred=is_starred,
        rag_datastore_ids=discussion_obj.metadata.get('rag_datastore_ids'),
        active_tools=discussion_obj.metadata.get('active_tools'),
        active_branch_id=discussion_obj.active_branch_id,
        created_at=discussion_obj.created_at,
        last_activity_at=discussion_obj.updated_at
    )