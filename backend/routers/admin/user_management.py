# backend/routers/admin/user_management.py
import json
import shutil
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
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
from backend.db.models.email_marketing import EmailProposal, EmailStatus
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

from sqlalchemy import func, desc, or_, and_

user_management_router = APIRouter()

def safe_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    return datetime.now(timezone.utc)


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

def _email_users_task(task: Task, user_ids: List[int], subject: str, body: str, background_color: str, send_as_text: bool, proposal_id: Optional[int] = None):
    db_session_local = next(get_db())
    try:
        users = db_session_local.query(DBUser).filter(DBUser.id.in_(user_ids)).all()
        sent_count = 0
        actual_recipients = []
        for i, user in enumerate(users):
            if task.cancellation_event.is_set():
                task.log("Cancellation requested.", level="WARNING")
                break
            if user.email and user.receive_notification_emails:
                try:
                    send_generic_email(user.email, subject, body, background_color, send_as_text)
                    sent_count += 1
                    actual_recipients.append(user.id)
                    task.log(f"Email sent to {user.username}.")
                except Exception as e:
                    task.log(f"Failed to send to {user.username}: {e}", level="ERROR")
            task.set_progress(5 + int(90 * (i + 1) / max(len(users), 1)))

        # Update archived campaign record in DB
        if proposal_id:
            proposal = db_session_local.query(EmailProposal).filter(EmailProposal.id == proposal_id).first()
            if proposal:
                proposal.status = EmailStatus.SENT
                proposal.sent_at = datetime.now(timezone.utc)
                proposal.recipients = actual_recipients
                db_session_local.commit()

        task.set_progress(100)
        return {"message": f"Emails sent to {sent_count} of {len(users)} users.", "proposal_id": proposal_id}
    finally:
        db_session_local.close()

@user_management_router.get("/stats", response_model=AdminDashboardStats)
async def get_dashboard_stats(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    total_users = db.query(DBUser).count()
    active_24h = db.query(DBUser).filter(DBUser.last_activity_at > now - timedelta(hours=24)).count()
    new_7d = db.query(DBUser).filter(DBUser.created_at > now - timedelta(days=7)).count()

    pending_approval = db.query(DBUser).filter(
        or_(
            DBUser.status == "pending_admin_validation",
            and_(DBUser.is_active == False, DBUser.status == "pending")
        )
    ).count()

    pending_resets = db.query(DBUser).filter(DBUser.password_reset_token.isnot(None), DBUser.reset_token_expiry > now).count()
    return AdminDashboardStats(total_users=total_users, active_users_24h=active_24h, new_users_7d=new_7d, pending_approval=pending_approval, pending_password_resets=pending_resets)

@user_management_router.get("/users", response_model=List[UserForAdminPanel])
async def admin_get_all_users(
    filter_online: Optional[bool] = Query(None),
    filter_has_keys: Optional[bool] = Query(None),
    status_filter: Optional[str] = Query(None, description="Filter by user status"),
    sort_by: str = Query('username', enum=['username', 'email', 'last_activity_at', 'created_at', 'task_count', 'api_key_count', 'connection_count', 'status']),
    sort_order: str = Query('asc', enum=['asc', 'desc']),
    db: Session = Depends(get_db)
):
    online_users_subquery = select(WebSocketConnection.user_id).distinct()
    
    query = db.query(
        DBUser,
        case((DBUser.id.in_(online_users_subquery), True), else_=False).label('is_online'),
        func.count(func.distinct(DBTask.id)).label('task_count'),
        func.count(func.distinct(OpenAIAPIKey.id)).label('api_key_count'),
        func.count(func.distinct(WebSocketConnection.id)).label('connection_count')
    ).outerjoin(DBTask, DBUser.id == DBTask.owner_user_id) \
     .outerjoin(OpenAIAPIKey, DBUser.id == OpenAIAPIKey.user_id) \
     .outerjoin(WebSocketConnection, DBUser.id == WebSocketConnection.user_id) \
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

    if status_filter:
        if status_filter in ["pending_admin_validation", "pending", "pending_approval"]:
            query = query.filter(
                or_(
                    DBUser.status == "pending_admin_validation",
                    DBUser.status == "pending",
                    and_(DBUser.is_active == False, DBUser.status.notin_(["inactivated_by_admin", "blocked_by_lollms"]))
                )
            )
        else:
            query = query.filter(DBUser.status == status_filter)

    sort_column = getattr(DBUser, sort_by) if hasattr(DBUser, sort_by) else literal_column(sort_by)
    if sort_order == 'desc':
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    results = query.all()
    
    users_for_panel = []
    for user, is_online, task_count, api_key_count, connection_count in results:
        try:
            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "icon": user.icon,
                "is_admin": getattr(user, "is_admin", False) or False,
                "is_moderator": getattr(user, "is_moderator", False) or False,
                "is_active": user.is_active,
                "status": user.status,
                "created_at": safe_datetime(user.created_at),
                "last_activity_at": safe_datetime(user.last_activity_at),
                "is_online": is_online,
                "connection_count": connection_count,
                "total_logins": getattr(user, "total_logins", 0),
                "api_key_count": api_key_count,
                "task_count": task_count,
                "generation_count": 0
            }
            users_for_panel.append(UserForAdminPanel.model_validate(user_data))
        except Exception as e:
            trace_exception(e)
    return users_for_panel

def _project_user_public(user: DBUser) -> UserPublic:
    return UserPublic(
        id=user.id,
        username=user.username,
        email=user.email,
        icon=user.icon,
        is_active=user.is_active,
        is_admin=getattr(user, "is_admin", False) or False,
        is_moderator=getattr(user, "is_moderator", False) or False,
        status=user.status,
        created_at=user.created_at,
        last_activity_at=user.last_activity_at
    )

@user_management_router.post("/users", response_model=UserPublic, status_code=201)
async def admin_add_new_user(user_data: UserCreateAdmin, db: Session = Depends(get_db)):
    if db.query(DBUser).filter(DBUser.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already registered.")
    if user_data.email and db.query(DBUser).filter(DBUser.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already in use.")

    user_dict = user_data.model_dump(exclude={'username', 'password'})

    defaults_map = {
        'lollms_model_name': 'default_lollms_model_name',
        'safe_store_vectorizer': 'default_safe_store_vectorizer',
        'llm_temperature': 'default_llm_temperature',
        'llm_repeat_last_n': 'default_llm_repeat_last_n',
        'rag_top_k': 'default_rag_top_k',
        'max_rag_len': 'default_max_rag_len',
        'rag_n_hops': 'default_rag_n_hops',
        'rag_min_sim_percent': 'default_rag_min_sim_percent',
        'rag_use_graph': 'default_rag_use_graph',
        'rag_graph_response_type': 'default_rag_graph_response_type',
    }

    for field, setting_key in defaults_map.items():
        if user_dict.get(field) is None:
            user_dict[field] = settings.get(setting_key)

    if user_dict.get('user_ui_level', 0) == 0:
        beginner_default = settings.get('default_lollms_model_name_beginner')
        if beginner_default:
            user_dict['lollms_model_name'] = beginner_default

    user_dict.pop('google_client_secret_json', None)

    new_user = DBUser(
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        is_active=True,
        status="active",
        **user_dict
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return _project_user_public(new_user)

@user_management_router.get("/users/{user_id}/stats", response_model=UserStats)
async def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

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

    if 'status' in update_dict:
        if update_dict['status'] == 'active':
            update_dict['is_active'] = True
        else:
            update_dict['is_active'] = False

    if 'is_active' in update_dict:
        if update_dict['is_active']:
            update_dict['status'] = 'active'
        else:
            update_dict['status'] = 'inactivated_by_admin'

    if update_dict.get('is_admin') is True:
        update_dict['is_moderator'] = True

    for key, value in update_dict.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    if user.username in user_sessions:
        user_sessions[user.username]["lollms_clients_cache"] = {}
    return _project_user_public(user)

@user_management_router.post("/users/batch-update-settings", response_model=Dict[str, str])
async def admin_batch_update_user_settings(update_data: BatchUsersSettingsUpdate, db: Session = Depends(get_db)):
    if not update_data.user_ids:
        raise HTTPException(status_code=400, detail="No user IDs provided.")

    users = db.query(DBUser).filter(DBUser.id.in_(update_data.user_ids)).all()
    if not users:
        raise HTTPException(status_code=404, detail="No valid users found.")

    raw_fields = update_data.model_dump(exclude={"user_ids"}, exclude_unset=True)
    update_fields = {}
    if "settings" in raw_fields and isinstance(raw_fields["settings"], dict):
        update_fields.update(raw_fields["settings"])
    for k, v in raw_fields.items():
        if k != "settings":
            update_fields[k] = v

    if not update_fields:
        raise HTTPException(status_code=400, detail="No settings provided.")

    for user in users:
        for key, value in update_fields.items():
            if hasattr(user, key):
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
    user.status = "active"
    user.activation_token = user.password_reset_token = user.reset_token_expiry = None
    db.commit()
    db.refresh(user)
    return _project_user_public(user)

@user_management_router.post("/users/{user_id}/disconnect", response_model=Dict[str, str])
async def admin_disconnect_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.username in user_sessions:
        del user_sessions[user.username]
    
    from backend.ws_manager import manager
    manager.disconnect_user_sync(user_id)
    
    return {"message": f"User '{user.username}' disconnected and session cleared."}

@user_management_router.post("/users/{user_id}/deactivate", response_model=UserPublic)
async def admin_deactivate_user(user_id: int, db: Session = Depends(get_db), current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == current_admin.id:
        raise HTTPException(status_code=403, detail="Cannot deactivate own account.")

    user.is_active = False
    user.status = "inactivated_by_admin"
    db.commit()
    db.refresh(user)
    if user.username in user_sessions:
        del user_sessions[user.username]
    return _project_user_public(user)

@user_management_router.post("/users/{user_id}/reset-password", response_model=Dict[str, str])
async def admin_reset_user_password(user_id: int, payload: UserPasswordResetAdmin, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user.hashed_password = hash_password(payload.new_password)
    user.password_reset_token = user.reset_token_expiry = None
    user.password_changed_at = datetime.now(timezone.utc)
    db.commit()
    if user.username in user_sessions:
        del user_sessions[user.username]
    from backend.ws_manager import manager
    manager.disconnect_user_sync(user.id)
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
async def email_users(
    payload: EmailUsersRequest, 
    db: Session = Depends(get_db),
    current_admin: UserAuthDetails = Depends(get_current_admin_user)
):
    if settings.get("password_recovery_mode") not in ["automatic", "gmail", "system_mail", "outlook"]:
        raise HTTPException(status_code=412, detail="Email dispatch is not configured. Please configure SMTP or system mail in Admin Settings.")
    if not payload.user_ids:
        raise HTTPException(status_code=400, detail="No users selected.")
    
    # Auto-create an EmailProposal (Campaign) in DB to archive this targeted campaign
    proposal = EmailProposal(
        title=payload.subject,
        content=payload.body,
        source_topic=f"Targeted Campaign ({len(payload.user_ids)} recipients)",
        status=EmailStatus.APPROVED,
        recipients=payload.user_ids,
        generated_by=current_admin.username
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    
    db_task = task_manager.submit_task(
        name=f"Targeted Campaign: {payload.subject[:30]}",
        target=_email_users_task,
        args=(payload.user_ids, payload.subject, payload.body, payload.background_color, payload.send_as_text, proposal.id),
        owner_username=current_admin.username
    )
    return db_task

@user_management_router.post("/enhance-email", response_model=EnhancedEmailResponse)
async def enhance_email_with_ai(payload: EnhanceEmailRequest, current_admin: UserAuthDetails = Depends(get_current_admin_user)):
    try:
        lc = get_user_lollms_client(current_admin.username)
        
        schema = {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "The enhanced subject line."},
                "body": {"type": "string", "description": "The enhanced email body content (HTML allowed)."},
                "background_color": {"type": "string", "description": "Suggested hex code for background color (e.g. #FFFFFF)."}
            },
            "required": ["subject", "body"]
        }
        
        system_prompt = "You are an expert copywriter and designer. Enhance the email draft to be more engaging and professional."
        
        prompt = f"""Original Subject: {payload.subject}
Original Body: {payload.body}
Current Background: {payload.background_color or "#FFFFFF"}

Instruction: {payload.prompt.strip() if payload.prompt else 'Enhance this email.'}
"""

        enhanced_data = lc.generate_structured_content(prompt, system_prompt=system_prompt, schema=schema)
        
        if not enhanced_data or not isinstance(enhanced_data, dict):
             raise ValueError("AI failed to generate valid structured data.")

        return EnhancedEmailResponse(**enhanced_data)
        
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"AI enhancement failed: {e}")