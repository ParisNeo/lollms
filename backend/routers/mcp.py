import httpx
import asyncio
from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

from backend.database_setup import get_db, MCP as DBMCP, User as DBUser
from backend.session import get_current_active_user, get_current_admin_user, get_user_discussion, save_user_discussion
from backend.models import (
    MCPCreate, MCPUpdate, MCPPublic, ToolInfo, 
    DiscussionToolsUpdate, DiscussionInfo, UserAuthDetails, UserStarredDiscussion
)

mcp_router = APIRouter(prefix="/api/mcps", tags=["MCPs and Tools"])
discussion_tools_router = APIRouter(prefix="/api/discussions", tags=["MCPs and Tools"])

@mcp_router.post("/personal", response_model=MCPPublic, status_code=201)
def create_personal_mcp(
    mcp_data: MCPCreate,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="Current user not found in database.")

    new_mcp = DBMCP(**mcp_data.model_dump(), owner_user_id=user_db.id)
    db.add(new_mcp)
    try:
        db.commit()
        db.refresh(new_mcp)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An MCP with this name already exists for your account.")
    
    return MCPPublic(
        id=new_mcp.id,
        name=new_mcp.name,
        url=new_mcp.url,
        owner_username=user_db.username,
        created_at=new_mcp.created_at,
        updated_at=new_mcp.updated_at
    )

@mcp_router.post("/default", response_model=MCPPublic, status_code=201)
def create_default_mcp(
    mcp_data: MCPCreate,
    db: Session = Depends(get_db),
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
):
    new_mcp = DBMCP(**mcp_data.model_dump(), owner_user_id=None)
    db.add(new_mcp)
    try:
        db.commit()
        db.refresh(new_mcp)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A default MCP with this name already exists.")
    
    return MCPPublic(
        id=new_mcp.id,
        name=new_mcp.name,
        url=new_mcp.url,
        owner_username=None,
        created_at=new_mcp.created_at,
        updated_at=new_mcp.updated_at
    )

@mcp_router.get("", response_model=List[MCPPublic])
def list_my_mcps(
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found.")
    
    mcps_db = db.query(DBMCP).outerjoin(DBUser, DBMCP.owner_user_id == DBUser.id).filter(
        or_(DBMCP.owner_user_id == user_db.id, DBMCP.owner_user_id == None)
    ).all()

    response = []
    for mcp in mcps_db:
        owner_username = db.query(DBUser.username).filter(DBUser.id == mcp.owner_user_id).scalar() if mcp.owner_user_id else None
        response.append(MCPPublic(
            id=mcp.id,
            name=mcp.name,
            url=mcp.url,
            owner_username=owner_username,
            created_at=mcp.created_at,
            updated_at=mcp.updated_at
        ))
    return response

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

    user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found.")

    is_owner = mcp_db.owner_user_id == user_db.id
    is_admin = current_user.is_admin
    is_default = mcp_db.owner_user_id is None

    if not ((is_owner and not is_default) or (is_admin and is_default)):
        raise HTTPException(status_code=403, detail="You do not have permission to edit this MCP.")

    update_data = mcp_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(mcp_db, key, value)
    
    try:
        db.commit()
        db.refresh(mcp_db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An MCP with the new name already exists.")

    owner_username = user_db.username if mcp_db.owner_user_id else None
    return MCPPublic.model_validate(mcp_db, from_attributes=True, context={'owner_username': owner_username})

@mcp_router.delete("/{mcp_id}", status_code=204)
def delete_mcp(
    mcp_id: str,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    mcp_db = db.query(DBMCP).filter(DBMCP.id == mcp_id).first()
    if not mcp_db:
        raise HTTPException(status_code=404, detail="MCP not found.")

    user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found.")

    is_owner = mcp_db.owner_user_id == user_db.id
    is_admin = current_user.is_admin
    is_default = mcp_db.owner_user_id is None

    if not ((is_owner and not is_default) or (is_admin and is_default)):
        raise HTTPException(status_code=403, detail="You do not have permission to delete this MCP.")

    db.delete(mcp_db)
    db.commit()
    return None

async def _fetch_tools_from_mcp(mcp: DBMCP, client: httpx.AsyncClient) -> List[Dict]:
    try:
        response = await client.get(f"{mcp.url.rstrip('/')}/tools", timeout=5.0)
        response.raise_for_status()
        tools_data = response.json()
        if isinstance(tools_data, list):
            return [{"mcp_name": mcp.name, "tool": tool} for tool in tools_data]
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
        print(f"Failed to fetch tools from {mcp.name} ({mcp.url}): {e}")
    return []

@mcp_router.get("/tools", response_model=List[ToolInfo])
async def list_all_available_tools(
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found.")
    
    mcps_db = db.query(DBMCP).filter(
        or_(DBMCP.owner_user_id == user_db.id, DBMCP.owner_user_id == None)
    ).all()

    async with httpx.AsyncClient() as client:
        tasks = [_fetch_tools_from_mcp(mcp, client) for mcp in mcps_db]
        results = await asyncio.gather(*tasks)

    all_tools = []
    for mcp_tools_list in results:
        for item in mcp_tools_list:
            mcp_name = item["mcp_name"]
            tool_dict = item["tool"]
            if "name" in tool_dict:
                all_tools.append(ToolInfo(
                    name=f"{mcp_name}::{tool_dict['name']}",
                    description=tool_dict.get('description', '')
                ))
    return sorted(all_tools, key=lambda x: x.name)

@discussion_tools_router.get("/{discussion_id}/tools", response_model=List[ToolInfo])
async def get_discussion_tools(
    discussion_id: str,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    discussion_obj = get_user_discussion(current_user.username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    all_available_tools = await list_all_available_tools(db, current_user)
    active_tool_names = set(getattr(discussion_obj, 'active_tools', []))

    for tool in all_available_tools:
        if tool.name in active_tool_names:
            tool.is_active = True
            
    return all_available_tools

@discussion_tools_router.put("/{discussion_id}/tools", response_model=DiscussionInfo)
async def update_discussion_tools(
    discussion_id: str,
    update_request: DiscussionToolsUpdate,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    discussion_obj = get_user_discussion(current_user.username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    setattr(discussion_obj, 'active_tools', update_request.tools)
    save_user_discussion(current_user.username, discussion_id, discussion_obj)

    user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    is_starred = db.query(UserStarredDiscussion).filter_by(user_id=user_db.id, discussion_id=discussion_id).first() is not None

    return DiscussionInfo(
        id=discussion_obj.discussion_id,
        title=discussion_obj.title,
        is_starred=is_starred,
        rag_datastore_id=discussion_obj.rag_datastore_id,
        active_tools=update_request.tools,
        active_branch_id=discussion_obj.active_branch_id,
    )