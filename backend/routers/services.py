# backend/routers/services.py
import traceback
import re
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from ascii_colors import ASCIIColors

from backend.db import get_db
from backend.db.models.service import MCP as DBMCP, App as DBApp
from backend.db.models.db_task import DBTask
from backend.security import generate_sso_secret
from backend.session import get_current_active_user, get_user_lollms_client, user_sessions, load_mcps, reload_lollms_client_mcp
from backend.models import (
    MCPCreate, MCPUpdate, MCPPublic, ToolInfo,
    AppCreate, AppUpdate, AppPublic,
    DiscussionToolsUpdate, DiscussionInfo, UserAuthDetails,
    TaskInfo
)
from backend.discussion import get_user_discussion
from backend.task_manager import task_manager, Task
from backend.utils import get_accessible_host

mcp_router = APIRouter(prefix="/api/mcps", tags=["Services"])
apps_router = APIRouter(prefix="/api/apps", tags=["Services"])
discussion_tools_router = APIRouter(prefix="/api/discussions", tags=["Services"])

def _generate_unique_client_id(db: Session, name: str) -> str:
    base_slug = re.sub(r'[^a-z0-9_]+', '', name.lower().replace(' ', '_'))
    client_id = base_slug
    counter = 1
    while True:
        exists_in_apps = db.query(DBApp).filter(DBApp.client_id == client_id).first()
        exists_in_mcps = db.query(DBMCP).filter(DBMCP.client_id == client_id).first()
        if not exists_in_apps and not exists_in_mcps:
            return client_id
        client_id = f"{base_slug}_{counter}"
        counter += 1

def _to_task_info(db_task: DBTask) -> TaskInfo:
    """Converts a DBTask SQLAlchemy model to a TaskInfo Pydantic model."""
    if not db_task:
        return None
    return TaskInfo(
        id=db_task.id, name=db_task.name, description=db_task.description,
        status=db_task.status, progress=db_task.progress,
        logs=[log for log in (db_task.logs or [])], result=db_task.result, error=db_task.error,
        created_at=db_task.created_at, started_at=db_task.started_at, completed_at=db_task.completed_at,
        file_name=db_task.file_name, total_files=db_task.total_files,
        owner_username=db_task.owner.username if db_task.owner else "System"
    )

def _reload_mcps_task(task: Task, username: str):
    task.log("Starting MCP client reload...")
    task.set_progress(20)
    try:
        reload_lollms_client_mcp(username)
        task.log("MCP client reloaded successfully.")
        task.set_progress(100)
        return {"message": "MCP client and tools cache re-initialized."}
    except Exception as e:
        task.log(f"Error during MCP reload: {e}", level="ERROR")
        raise e

def _invalidate_user_mcp_cache(username: str):
    """Invalidates the lollms_client and tools cache for a given user."""
    if username in user_sessions and 'tools_cache' in user_sessions[username]:
        del user_sessions[username]['tools_cache']
        print(f"INFO: Invalidated tools cache for user: {username}")

def _format_mcp_public(mcp: DBMCP) -> MCPPublic:
    # This function is specifically for DBMCP objects
    return MCPPublic(
        id=mcp.id, name=mcp.name, client_id=mcp.client_id, url=mcp.url, icon=mcp.icon,
        active=mcp.active, type=mcp.type,
        authentication_type=mcp.authentication_type,
        authentication_key="********" if mcp.authentication_key else "",
        owner_username=mcp.owner.username if mcp.owner else "System",
        created_at=mcp.created_at, updated_at=mcp.updated_at,
        sso_redirect_uri=mcp.sso_redirect_uri,
        sso_user_infos_to_share=mcp.sso_user_infos_to_share or []
    )

@mcp_router.get("", response_model=List[MCPPublic])
def list_mcps(
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    all_mcps = []
    accessible_host = get_accessible_host()

    # 1. Get manually registered MCPs from the DBMCP table
    mcp_query = db.query(DBMCP).options(joinedload(DBMCP.owner))
    if not current_user.is_admin:
        mcp_query = mcp_query.filter(or_(DBMCP.owner_user_id == current_user.id, DBMCP.type == 'system'))
    
    for mcp in mcp_query.all():
        all_mcps.append(_format_mcp_public(mcp))

    # 2. Get installed MCPs from the DBApp table
    app_query = db.query(DBApp).options(joinedload(DBApp.owner)).filter(DBApp.app_metadata['item_type'].as_string() == 'mcp')
    if not current_user.is_admin:
        app_query = app_query.filter(or_(DBApp.owner_user_id == current_user.id, DBApp.type == 'system'))

    for app in app_query.all():
        url = app.url
        if app.is_installed and app.status == 'running' and app.port:
            url = f"http://{accessible_host}:{app.port}/mcp"
        
        all_mcps.append(MCPPublic(
            id=app.id, name=app.name, client_id=app.client_id, url=url, icon=app.icon,
            active=app.active, type=app.type,
            authentication_type=app.authentication_type,
            authentication_key="********" if app.authentication_key else "",
            owner_username=app.owner.username if app.owner else "System",
            created_at=app.created_at, updated_at=app.updated_at,
            sso_redirect_uri=app.sso_redirect_uri,
            sso_user_infos_to_share=app.sso_user_infos_to_share or []
        ))

    return sorted(all_mcps, key=lambda m: m.name)

@mcp_router.post("", response_model=MCPPublic, status_code=201)
def create_mcp(
    mcp_data: MCPCreate,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    if mcp_data.type == 'system' and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can create system-level MCPs.")
    
    owner_id = current_user.id if mcp_data.type == 'user' else None

    if mcp_data.client_id:
        if db.query(DBMCP).filter(DBMCP.client_id == mcp_data.client_id).first() or \
           db.query(DBApp).filter(DBApp.client_id == mcp_data.client_id).first():
            raise HTTPException(status_code=409, detail=f"Client ID '{mcp_data.client_id}' is already in use.")
        client_id_to_set = mcp_data.client_id
    else:
        client_id_to_set = _generate_unique_client_id(db, mcp_data.name)

    mcp_dict = mcp_data.model_dump(exclude={"client_id"})
    url = mcp_dict.get('url')
    if url and not url.endswith('/mcp'):
        if url.endswith('/'):
            mcp_dict['url'] = url + 'mcp'
        else:
            mcp_dict['url'] = url + '/mcp'
            
    new_mcp = DBMCP(**mcp_dict, client_id=client_id_to_set, owner_user_id=owner_id)
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
    if 'url' in update_data and update_data['url']:
        url = update_data['url']
        if not url.endswith('/mcp'):
            if url.endswith('/'):
                update_data['url'] = url + 'mcp'
            else:
                update_data['url'] = url + '/mcp'

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
    accessible_host = get_accessible_host()
    url_to_return = app.url
    item_type = (app.app_metadata or {}).get('item_type', 'app')

    if app.is_installed and app.status == 'running' and app.port:
        url_to_return = f"http://{accessible_host}:{app.port}"
        if item_type == 'mcp':
            url_to_return += '/mcp'

    return AppPublic(
        id=app.id,
        name=app.name,
        client_id=app.client_id,
        url=url_to_return,
        icon=app.icon,
        active=app.active,
        type=app.type,
        authentication_type=app.authentication_type,
        authentication_key="********" if app.authentication_key else "",
        owner_username=app.owner.username if app.owner else "System",
        created_at=app.created_at,
        updated_at=app.updated_at,
        sso_redirect_uri=app.sso_redirect_uri,
        sso_user_infos_to_share=app.sso_user_infos_to_share or [],
        is_installed=app.is_installed,
        port=app.port,
        status=app.status,
        autostart=app.autostart,
        allow_openai_api_access=app.allow_openai_api_access,
        item_type=item_type
    )

@apps_router.get("", response_model=List[AppPublic])
def list_apps(db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_active_user)):
    query = db.query(DBApp).options(joinedload(DBApp.owner)).filter(
        (DBApp.app_metadata['item_type'] == None) | (DBApp.app_metadata['item_type'].as_string() == 'app')
    )
    if not current_user.is_admin:
        query = query.filter(or_(DBApp.owner_user_id == current_user.id, DBApp.type == 'system'))
        
    apps_db = query.all()
    return [_format_app_public(app) for app in apps_db]

@apps_router.post("", response_model=AppPublic, status_code=201)
def create_app(app_data: AppCreate, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_active_user)):
    if app_data.type == 'system' and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can create system-level apps.")
    
    owner_id = current_user.id if app_data.type == 'user' else None
    
    if app_data.client_id:
        if db.query(DBMCP).filter(DBMCP.client_id == app_data.client_id).first() or \
           db.query(DBApp).filter(DBApp.client_id == app_data.client_id).first():
            raise HTTPException(status_code=409, detail=f"Client ID '{app_data.client_id}' is already in use.")
        client_id_to_set = app_data.client_id
    else:
        client_id_to_set = _generate_unique_client_id(db, app_data.name)

    new_app = DBApp(**app_data.model_dump(exclude={"client_id"}), client_id=client_id_to_set, owner_user_id=owner_id)
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
    
    if app_db.is_installed:
        if 'active' in update_data:
            raise HTTPException(status_code=400, detail="Cannot change 'active' status of an installed app directly. Use the start/stop controls in Apps Management.")
        if app_update.port and app_update.port != app_db.port:
            if db.query(DBApp).filter(DBApp.port == app_update.port, DBApp.id != app_id).first():
                raise HTTPException(status_code=409, detail=f"Port {app_update.port} is already in use by another app.")

    for key, value in update_data.items():
        setattr(app_db, key, value)
    
    try:
        db.commit()
        db.refresh(app_db, ["owner"])
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An app with the new name already exists.")
    return _format_app_public(app_db)

@apps_router.delete("/{app_id}", status_code=204)
def delete_app(app_id: str, db: Session = Depends(get_db), current_user: UserAuthDetails = Depends(get_current_active_user)):
    app_db = db.query(DBApp).filter(DBApp.id == app_id).first()
    if not app_db:
        raise HTTPException(status_code=404, detail="App not found.")

    is_owner = app_db.owner_user_id == current_user.id
    if not is_owner and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this app.")
        
    if app_db.is_installed:
        raise HTTPException(status_code=400, detail="Installed apps cannot be deleted from this menu. Please use the Apps Management panel to uninstall.")


    db.delete(app_db)
    db.commit()
    return None

# --- TOOLS AND DISCUSSION LOGIC ---

@mcp_router.post("/reload", response_model=TaskInfo, status_code=202)
def reload_user_lollms_client(
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """Triggers a background task to reload MCPs for the current user."""
    db_task = task_manager.submit_task(
        name=f"Reload MCPs for {current_user.username}",
        target=_reload_mcps_task,
        args=(current_user.username,),
        description="Refreshes the connection to all MCP servers and re-discovers available tools."
    )
    return _to_task_info(db_task)

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
    db: Session = Depends(get_db) # Added db dependency for list_all_available_tools call
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
    from backend.db.models.user import UserStarredDiscussion
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
