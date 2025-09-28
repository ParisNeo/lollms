# [UPDATE] backend/routers/admin/user_management.py
import json
import shutil
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session, joinedload, aliased, Query as SQLAlchemyQuery
from sqlalchemy import func, case, literal_column, exists, select
from lollms_client import LollmsDataManager
from pydantic import EmailStr

from backend.db import get_db
from backend.db.models.user import User as DBUser, Friendship as DBFriendship
from backend.db.models.connections import WebSocketConnection
from backend.db.models.api_key import OpenAIAPIKey
from backend.db.models.db_task import DBTask
from backend.db.base import FriendshipStatus
from backend.models.user import (
    UserCreateAdmin, UserPasswordResetAdmin,
    AdminUserUpdate, BatchUsersSettingsUpdate, EmailUsersRequest,
    EnhanceEmailRequest, EnhancedEmailResponse, UserPublic, UserAuthDetails
)
from backend.models.admin import UserForAdminPanel, UserStats, UserActivityStat, AdminDashboardStats
from backend.session import get_current_admin_user, get_user_data_root, user_sessions, get_user_lollms_client
from backend.security import get_password_hash as hash_password, create_reset_token, send_generic_email
from backend.settings import settings
from backend.config import INITIAL_ADMIN_USER_CONFIG
from backend.task_manager import task_manager, Task, TaskInfo
from ascii_colors import trace_exception

user_management_router = APIRouter()

def _to_task_info(db_task) -> "TaskInfo":
    from backend.models.task import TaskInfo
    return TaskInfo(
        id=db_task.id, name=db_task.name, description=db_task.description,
        status=db_task.status, progress=db_task.progress,
        logs=[log for log in (db_task.logs or [])], result=db_task.result, error=db_task.error,
        created_at=db_task.created_at, started_at=db_task.started_at, updated_at=db_task.updated_at, completed_at=db_task.completed_at,
        file_name=db_task.file_name, total_files=db_task.total_files,
        owner_username=db_task.owner.username if db_task.owner else "System"
    )

def _email_users_task(task: Task, user_ids: List[int], subject: str, body: str, background_color: str, send_as_text: bool):
    db_session_local = next(get_db())
    try:
        users = db_session_local.query(DBUser).filter(DBUser.id.in_(user_ids)).all()
        sent_count = 0
        for i, user in enumerate(users):
            if task.cancellation_event.is_set():
                task.log("Cancellation requested.", level="WARNING")
                break
            if user.email and user.receive_notification_emails:
                try:
                    send_generic_email(user.email, subject, body, background_color, send_as_text)
                    sent_count += 1
                    task.log(f"Email sent to {user.username}.")
                except Exception as e:
                    task.log(f"Failed to send to {user.username}: {e}", level="ERROR")
            task.set_progress(5 + int(90 * (i + 1) / len(users)))
        task.set_progress(100)
        return {"message": f"Emails sent to {sent_count} of {len(users)} users."}
    finally:
        db_session_local.close()

@user_management_router.get("/stats", response_model=AdminDashboardStats)
async def get_dashboard_stats(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    total_users = db.query(DBUser).count()
    active_24h = db.query(DBUser).filter(DBUser.last_activity_at > now - timedelta(hours=24)).count()
    new_7d = db.query(DBUser).filter(DBUser.created_at > now - timedelta(days=7)).count()
    pending_approval = db.query(DBUser).filter(DBUser.is_active == False, DBUser.activation_token.isnot(None)).count() if settings.get("registration_mode") == "admin_approval" else 0
    pending_resets = db.query(DBUser).filter(DBUser.password_reset_token.isnot(None), DBUser.reset_token_expiry > now).count()
    return AdminDashboardStats(total_users=total_users, active_users_24h=active_24h, new_users_7d=new_7d, pending_approval=pending_approval, pending_password_resets=pending_resets)

@user_management_router.get("/users", response_model=List[UserForAdminPanel])
async def admin_get_all_users(
    filter_online: Optional[bool] = Query(None),
    filter_has_keys: Optional[bool] = Query(None),
    sort_by: str = Query('username', enum=['username', 'email', 'last_activity_at', 'created_at', 'task_count', 'api_key_count']),
    sort_order: str = Query('asc', enum=['asc', 'desc']),
    db: Session = Depends(get_db)
):
    online_users_subquery = select(WebSocketConnection.user_id).distinct()
    
    query = db.query(
        DBUser,
        case((DBUser.id.in_(online_users_subquery), True), else_=False).label('is_online'),
        func.count(DBTask.id).label('task_count'),
        func.count(OpenAIAPIKey.id).label('api_key_count')
    ).outerjoin(DBTask, DBUser.id == DBTask.owner_user_id) \
     .outerjoin(OpenAIAPIKey, DBUser.id == OpenAIAPIKey.user_id) \
     .group_by(DBUser.id)

    if filter_online is not None:
        if filter_online:
            query = query.filter(DBUser.id.in_(online_users_subquery))
        else:
            query = query.filter(DBUser.id.notin_(online_users_subquery))

    if filter_has_keys is not None:
        if filter_has_keys:
            query = query.filter(exists().where(OpenAIAPIKey.user_id == DBUser.id))
        else:
            query = query.filter(~exists().where(OpenAIAPIKey.user_id == DBUser.id))

    # Sorting logic
    sort_column = getattr(DBUser, sort_by) if hasattr(DBUser, sort_by) else literal_column(sort_by)
    if sort_order == 'desc':
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    results = query.all()
    
    users_for_panel = []
    for user, is_online, task_count, api_key_count in results:
        user_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin or False,
            "is_moderator": user.is_moderator or False,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "last_activity_at": user.last_activity_at,
            "is_online": is_online,
            "api_key_count": api_key_count,
            "task_count": task_count,
            "generation_count": 0  # Placeholder, logic to be added
        }
        users_for_panel.append(UserForAdminPanel.model_validate(user_data))
        
    return users_for_panel

@user_management_router.post("/users", response_model=UserPublic, status_code=201)
async def admin_add_new_user(user_data: UserCreateAdmin, db: Session = Depends(get_db)):
    if db.query(DBUser).filter(DBUser.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already registered.")
    if user_data.email and db.query(DBUser).filter(DBUser.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already in use.")

    new_user = DBUser(
        username=user_data.username, hashed_password=hash_password(user_data.password),
        is_admin=user_data.is_admin, is_moderator=(user_data.is_admin or user_data.is_moderator),
        email=user_data.email, lollms_model_name=user_data.lollms_model_name,
        safe_store_vectorizer=user_data.safe_store_vectorizer or settings.get("default_safe_store_vectorizer"),
        llm_ctx_size=user_data.llm_ctx_size if user_data.llm_ctx_size is not None else settings.get("default_llm_ctx_size"),
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@user_management_router.get("/users/{user_id}/stats", response_model=UserStats)
async def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    # Get task stats
    task_stats_raw = db.query(
        func.date(DBTask.created_at),
        func.count(DBTask.id)
    ).filter(
        DBTask.owner_user_id == user_id,
        DBTask.created_at >= thirty_days_ago
    ).group_by(
        func.date(DBTask.created_at)
    ).all()
    task_stats = [UserActivityStat(date=date, count=count) for date, count in task_stats_raw]

    # Get message stats (generations)
    message_stats = []
    try:
        user_discussions_db_path = get_user_data_root(user.username) / "discussions.db"
        if user_discussions_db_path.exists():
            dm = LollmsDataManager(db_path=f"sqlite:///{user_discussions_db_path.resolve()}")
            session = dm.get_session()
            try:
                message_stats_raw = session.query(
                    func.date(dm.MessageModel.created_at),
                    func.count(dm.MessageModel.id)
                ).filter(
                    dm.MessageModel.sender_type == 'assistant',
                    dm.MessageModel.created_at >= thirty_days_ago
                ).group_by(
                    func.date(dm.MessageModel.created_at)
                ).all()
                message_stats = [UserActivityStat(date=date, count=count) for date, count in message_stats_raw]
            finally:
                session.close()
    except Exception as e:
        trace_exception(e)
        # Fail gracefully if discussion DB can't be read
        print(f"Warning: Could not read discussion database for user {user.username}: {e}")

    return UserStats(tasks_per_day=task_stats, messages_per_day=message_stats)
@user_management_router.put("/users/{user_id}", response_model=UserPublic)
async def admin_update_user(user_id: int, update_data: AdminUserUpdate, db: Session = Depends(get_db), current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == current_admin.id and update_data.is_admin is False:
        raise HTTPException(status_code=403, detail="Cannot revoke own admin status.")
    if user.username == INITIAL_ADMIN_USER_CONFIG.get("username") and update_data.is_admin is False:
        raise HTTPException(status_code=403, detail="Cannot revoke initial superadmin status.")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    if 'is_admin' in update_dict and update_dict['is_admin']:
        update_dict['is_moderator'] = True

    for key, value in update_dict.items():
        setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    if user.username in user_sessions:
        user_sessions[user.username]["lollms_clients_cache"] = {}
    return user

@user_management_router.post("/users/batch-update-settings", response_model=Dict[str, str])
async def admin_batch_update_user_settings(update_data: BatchUsersSettingsUpdate, db: Session = Depends(get_db)):
    if not update_data.user_ids:
        raise HTTPException(status_code=400, detail="No user IDs provided.")
    
    users = db.query(DBUser).filter(DBUser.id.in_(update_data.user_ids)).all()
    if not users:
        raise HTTPException(status_code=404, detail="No valid users found.")

    update_fields = update_data.model_dump(exclude={"user_ids"}, exclude_unset=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="No settings provided.")

    for user in users:
        for key, value in update_fields.items():
            setattr(user, key, value)
        if user.username in user_sessions:
            user_sessions[user.username]["lollms_clients_cache"] = {}
    
    db.commit()
    return {"message": f"Updated settings for {len(users)} users."}

@user_management_router.post("/users/{user_id}/activate", response_model=UserPublic)
async def admin_activate_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user.is_active = True
    user.activation_token = user.password_reset_token = user.reset_token_expiry = None
    db.commit()
    db.refresh(user)
    return user

@user_management_router.post("/users/{user_id}/deactivate", response_model=UserPublic)
async def admin_deactivate_user(user_id: int, db: Session = Depends(get_db), current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == current_admin.id:
        raise HTTPException(status_code=403, detail="Cannot deactivate own account.")
    
    user.is_active = False
    db.commit()
    db.refresh(user)
    if user.username in user_sessions:
        del user_sessions[user.username]
    return user

@user_management_router.post("/users/{user_id}/reset-password", response_model=Dict[str, str])
async def admin_reset_user_password(user_id: int, payload: UserPasswordResetAdmin, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user.hashed_password = hash_password(payload.new_password)
    user.password_reset_token = user.reset_token_expiry = None
    db.commit()
    return {"message": f"Password for '{user.username}' reset."}

@user_management_router.post("/users/{user_id}/generate-reset-link", response_model=Dict[str, str])
async def admin_generate_password_reset_link(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    token = create_reset_token()
    user.password_reset_token = token
    user.reset_token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    db.commit()
    reset_link = f"{str(request.base_url).strip('/')}/reset-password?token={token}"
    return {"reset_link": reset_link}

@user_management_router.delete("/users/{user_id}", response_model=Dict[str, str])
async def admin_remove_user(user_id: int, db: Session = Depends(get_db), current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.username == INITIAL_ADMIN_USER_CONFIG.get("username") or user.id == current_admin.id:
        raise HTTPException(status_code=403, detail="This account cannot be deleted.")
    
    user_data_dir = get_user_data_root(user.username)
    if user.username in user_sessions:
        del user_sessions[user.username]
    db.delete(user)
    db.commit()
    
    if user_data_dir.exists():
        task_manager.submit_task(
            name=f"Delete user data for {user.username}",
            target=shutil.rmtree,
            args=(user_data_dir,),
            kwargs={'ignore_errors': True}
        )
    return {"message": f"User '{user.username}' deleted. Data cleanup initiated."}

@user_management_router.post("/email-users", response_model=TaskInfo, status_code=202)
async def email_users(payload: EmailUsersRequest, current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    if settings.get("password_recovery_mode") not in ["automatic", "system_mail", "outlook"]:
        raise HTTPException(status_code=412, detail="Email sending is not enabled.")
    if not payload.user_ids:
        raise HTTPException(status_code=400, detail="No users selected.")
    
    db_task = task_manager.submit_task(
        name=f"Emailing {len(payload.user_ids)} users",
        target=_email_users_task,
        args=(payload.user_ids, payload.subject, payload.body, payload.background_color, payload.send_as_text),
        owner_username=current_admin.username
    )
    return _to_task_info(db_task)

@user_management_router.post("/enhance-email", response_model=EnhancedEmailResponse)
async def enhance_email_with_ai(payload: EnhanceEmailRequest, current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    try:
        lc = get_user_lollms_client(current_admin.username)
        prompt = f"""{payload.prompt.strip() if payload.prompt else 'You are an expert copywriter and designer. Enhance the following email draft to be more engaging and professional. Also, suggest a suitable HTML background color.'}
Return ONLY a single valid JSON object with keys: "subject", "body", "background_color".

Original Subject: {payload.subject}
Original Body: {payload.body}
Current Background: {payload.background_color or "#FFFFFF"}
"""
        raw_response = lc.generate_text(prompt, stream=False)
        json_match = raw_response[raw_response.find('{'):raw_response.rfind('}') + 1]
        enhanced_data = json.loads(json_match)
        return EnhancedEmailResponse(**enhanced_data)
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"AI enhancement failed: {e}")