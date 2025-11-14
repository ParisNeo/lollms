import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from typing import Optional

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.group import Group as DBGroup
from backend.models.scim import SCIMUser, SCIMGroup, SCIMListResponse, SCIMPatchRequest, SCIMName, SCIMEmail, SCIMMeta, SCIMMember
from backend.settings import settings
from backend.security import get_password_hash
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

scim_router = APIRouter(prefix="/api/scim/v2", tags=["SCIM"])

auth_scheme = HTTPBearer()

async def verify_scim_token(credentials: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    scim_token = settings.get("scim_token")
    if not settings.get("scim_enabled") or not scim_token:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="SCIM is not configured or enabled on the server."
        )
    
    if not secrets.compare_digest(credentials.credentials, scim_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid SCIM authentication token.",
        )

SCIM_AUTH = Depends(verify_scim_token)

def user_to_scim_resource(user: DBUser, request: Request) -> dict:
    scim_user = SCIMUser(
        id=str(user.id),
        external_id=user.external_id,
        user_name=user.username,
        name=SCIMName(given_name=user.first_name, family_name=user.family_name),
        display_name=f"{user.first_name} {user.family_name}".strip() or user.username,
        emails=[SCIMEmail(value=user.email)] if user.email else [],
        active=user.is_active,
        meta=SCIMMeta(
            resource_type="User",
            location=str(request.url_for("get_scim_user", user_id=user.id))
        )
    )
    return scim_user.model_dump(by_alias=True, exclude_none=True)

def group_to_scim_resource(group: DBGroup, request: Request) -> dict:
    scim_group = SCIMGroup(
        id=str(group.id),
        external_id=group.external_id,
        display_name=group.display_name,
        members=[SCIMMember(value=str(member.id), display=member.username) for member in group.members],
        meta=SCIMMeta(
            resource_type="Group",
            location=str(request.url_for("get_scim_group", group_id=group.id))
        )
    )
    return scim_group.model_dump(by_alias=True, exclude_none=True)

@scim_router.get("/Users", dependencies=[SCIM_AUTH], response_model=SCIMListResponse)
async def get_scim_users(request: Request, db: Session = Depends(get_db), startIndex: int = 1, count: int = 100):
    total_users = db.query(DBUser).count()
    users = db.query(DBUser).offset(startIndex - 1).limit(count).all()
    
    resources = [user_to_scim_resource(user, request) for user in users]
    
    return SCIMListResponse(
        total_results=total_users,
        start_index=startIndex,
        items_per_page=len(resources),
        Resources=resources
    )

@scim_router.get("/Users/{user_id}", dependencies=[SCIM_AUTH], response_model=SCIMUser)
async def get_scim_user(user_id: str, request: Request, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user_to_scim_resource(user, request)

@scim_router.post("/Users", dependencies=[SCIM_AUTH], response_model=SCIMUser, status_code=201)
async def create_scim_user(scim_user: SCIMUser, request: Request, response: Response, db: Session = Depends(get_db)):
    if db.query(DBUser).filter(DBUser.username == scim_user.user_name).first():
        raise HTTPException(status_code=409, detail="User with this username already exists")
    if scim_user.emails and db.query(DBUser).filter(DBUser.email == scim_user.emails[0].value).first():
        raise HTTPException(status_code=409, detail="User with this email already exists")

    new_user = DBUser(
        username=scim_user.user_name,
        external_id=scim_user.external_id,
        email=scim_user.emails[0].value if scim_user.emails else None,
        first_name=scim_user.name.given_name if scim_user.name else None,
        family_name=scim_user.name.family_name if scim_user.name else None,
        is_active=scim_user.active,
        hashed_password=get_password_hash(secrets.token_urlsafe(32)), # Random unusable password
        first_login_done=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    resource = user_to_scim_resource(new_user, request)
    response.headers["Location"] = resource["meta"]["location"]
    return resource

@scim_router.patch("/Users/{user_id}", dependencies=[SCIM_AUTH], response_model=SCIMUser)
async def patch_scim_user(user_id: str, patch_request: SCIMPatchRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for op in patch_request.operations:
        if op.op.lower() == "replace" and isinstance(op.value, dict) and 'active' in op.value:
            user.is_active = op.value['active']
        elif op.op.lower() == "replace" and op.path and op.path.lower() == "active":
            user.is_active = op.value

    db.commit()
    db.refresh(user)
    return user_to_scim_resource(user, request)

@scim_router.get("/Groups", dependencies=[SCIM_AUTH], response_model=SCIMListResponse)
async def get_scim_groups(request: Request, db: Session = Depends(get_db), startIndex: int = 1, count: int = 100):
    total_groups = db.query(DBGroup).count()
    groups = db.query(DBGroup).offset(startIndex - 1).limit(count).all()
    resources = [group_to_scim_resource(group, request) for group in groups]
    return SCIMListResponse(
        total_results=total_groups,
        start_index=startIndex,
        items_per_page=len(resources),
        Resources=resources
    )

@scim_router.get("/Groups/{group_id}", dependencies=[SCIM_AUTH], response_model=SCIMGroup)
async def get_scim_group(group_id: str, request: Request, db: Session = Depends(get_db)):
    group = db.query(DBGroup).filter(DBGroup.id == int(group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group_to_scim_resource(group, request)

@scim_router.patch("/Groups/{group_id}", dependencies=[SCIM_AUTH], status_code=204)
async def patch_scim_group(group_id: str, patch_request: SCIMPatchRequest, db: Session = Depends(get_db)):
    group = db.query(DBGroup).filter(DBGroup.id == int(group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    for op in patch_request.operations:
        if op.path and op.path.lower() == "members":
            if op.op.lower() == "add":
                if isinstance(op.value, list):
                    for member_data in op.value:
                        user_id = member_data.get('value')
                        user = db.query(DBUser).filter(DBUser.id == int(user_id)).first()
                        if user and user not in group.members:
                            group.members.append(user)
            elif op.op.lower() == "remove":
                # SCIM spec says path can be a filter. e.g., members[value eq "userId"]
                # We'll simplify and just expect a list of members to remove in `value`.
                path_filter_match = None
                if op.path and '[' in op.path:
                    import re
                    match = re.search(r'\[value eq "([^"]+)"\]', op.path)
                    if match:
                        path_filter_match = match.group(1)

                if path_filter_match: # DELETE members[value eq "2819c223-7f76-453a-919d-413861904646"]
                    user = db.query(DBUser).filter(DBUser.id == int(path_filter_match)).first()
                    if user and user in group.members:
                        group.members.remove(user)
                elif isinstance(op.value, list): # PATCH with op: remove, path: members, value: [...]
                    for member_data in op.value:
                        user_id = member_data.get('value')
                        user = db.query(DBUser).filter(DBUser.id == int(user_id)).first()
                        if user and user in group.members:
                            group.members.remove(user)
    db.commit()
    return Response(status_code=204)
