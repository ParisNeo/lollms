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

from collections import defaultdict

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

# ──────────────────────────────────────────────────────────────────────────────
# Welcome email — sent on the inactive→active transition of an account.
# ────
# Design notes:
#   • Non-blocking: dispatched through task_manager because SMTP can be slow.
#   • Opt-out respected: skipped when receive_notification_emails is False —
#     this is a policy message, not a security-critical notice.
#   • Only fires on transition: Reactivating an already-active account must NOT
#     re-send, otherwise a repeated click spams the user.
#   • Content uses the global welcome config so the email matches the landing
#     page (same logo/slogan the admin already set up). Never embeds secrets.
# ──────────────────────────────────────────────────────────────────────────────
_WELCOME_EMAIL_STYLES = (
    "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
    "Helvetica, Arial, sans-serif; line-height: 1.55; color: #111827;"
)

def _render_welcome_email_html(username: str, server_url: str) -> str:
    """Render the welcome HTML body. All values are admin-controlled globals +
    the already-public username, never user-private data."""
    try:
        welcome_text = settings.get("welcome_text") or "lollms"
    except Exception:
        welcome_text = "lollms"
    try:
        welcome_slogan = settings.get("welcome_slogan") or "One tool to rule them all"
    except Exception:
        welcome_slogan = "One tool to rule them all"

    # Minimal, self-contained HTML. Inline styles only (Gmail/Outlook safe).
    return f"""
<div style="{_WELCOME_EMAIL_STYLES}">
  <h2 style="margin:0 0 8px 0;">Welcome to {welcome_text}, {username}!</h2>
  <p style="margin:0 0 12px 0; color:#4b5563;">{welcome_slogan}</p>

  <p>Your account is now active. Here is what LoLLMS gives you:</p>

  <ul style="padding-left:20px; margin:12px 0;">
    <li><strong>Sovereign AI chat</strong> — hold conversations with LLMs, switch models at will,
        and keep full ownership of every message. Nothing leaves your server unless you choose so.</li>
    <li><strong>Multimodal studios</strong> — image generation and editing, video, music,
        voice synthesis and transcription, all wired to your own bindings.</li>
    <li><strong>Artefacts &amp; workspaces</strong> — versioned documents, code, notes, and
        data stores that the AI can read and build on inside each discussion.</li>
    <li><strong>Personalities, skills &amp; MCPs</strong> — reusable assistants, tools, and
        behaviours you can share with people you trust.</li>
    <li><strong>Recipes, prompts &amp; memory</strong> — save what works, and let the AI
        remember what matters to you.</li>
  </ul>

  <p>Open the app here:</p>
  <p style="margin:16px 0;">
    <a href="{server_url}"
       style="display:inline-block; padding:10px 18px; background:#6366f1; color:#ffffff;
              text-decoration:none; border-radius:8px; font-weight:600;">
      Go to {welcome_text}
    </a>
  </p>

  <hr style="border:none; border-top:1px solid #e5e7eb; margin:20px 0;" />

  <p style="font-size:12px; color:#6b7280; margin:0;">
    You are receiving this message because your account on {server_url} was activated.
    If this was unexpected, please contact the administrator of this server.
  </p>
  <p style="font-size:12px; color:#6b7280; margin:12px 0 0 0;">
    — The {welcome_text} team
  </p>
</div>
""".strip()


def _welcome_email_task(task: Task, to_email: str, username: str, server_url: str):
    """Background worker: render and send one welcome email. Failures are logged
    to the task but never bubbled — the activation itself already succeeded."""
    try:
        html = _render_welcome_email_html(username, server_url)
        subject = f"Welcome to {settings.get('welcome_text') or 'LoLLMS'}!"
        send_generic_email(
            to_email=to_email,
            subject=subject,
            body=html,
            background_color="#ffffff",
            send_as_text=False,
        )
        task.log(f"Welcome email sent to {username} <{to_email}>.")
    except Exception as exc:
        # Do not raise — this would fail the task and confuse the admin into
        # thinking activation failed. The account is already active.
        task.log(f"Welcome email failed for {username} <{to_email}>: {exc}", level="ERROR")


def _maybe_send_welcome_email(db: Session, user: DBUser, server_url: str) -> bool:
    """Dispatch the welcome email if (a) SMTP is configured, (b) the user has
    an email, (c) they have not opted out of notifications. Returns True iff
    a task was queued. Never raises — a failure to notify must not fail the
    activation."""
    try:
        # (a) Is SMTP configured? Same gate used everywhere else in this file.
        if settings.get("password_recovery_mode") not in ["automatic", "gmail", "system_mail", "outlook"]:
            return False
        # (b) Has a valid recipient address?
        if not user or not user.email:
            return False
        # (c) Has the user opted out of notification emails?
        if getattr(user, "receive_notification_emails", True) is False:
            return False

        task_manager.submit_task(
            name=f"Welcome email → {user.username}",
            target=_welcome_email_task,
            args=(user.email, user.username, server_url),
            owner_username="system",
        )
        return True
    except Exception:
        # Never surface this to the caller — see docstring.
        return False


def _resolve_server_base_url(request: Optional[Request]) -> str:
    """Return the base URL to feature in the welcome email. Falls back to a
    relative '/' when the request is unavailable (bulk path may be called from
    a background scheduler in the future)."""
    if request is not None:
        try:
            return str(request.base_url).rstrip("/")
        except Exception:
            pass
    return "/"


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
    sort_by: str = Query(
        'username',
        enum=[
            'username', 'email', 'last_activity_at', 'created_at',
            'task_count', 'api_key_count', 'connection_count', 'status',
            'total_tokens', 'generation_count',
        ],
    ),
    sort_order: str = Query('asc', enum=['asc', 'desc']),
    db: Session = Depends(get_db)
):
    from backend.db.models.generation_metric import (
        GenerationMetric, KWH_PER_TOKEN, CO2_G_PER_KWH,
    )

    online_users_subquery = select(WebSocketConnection.user_id).distinct()

    # Token usage is pre-aggregated in its own subquery so joining GenerationMetric
    # does not multiply the outer task / api-key / connection row counts.
    token_agg = db.query(
        GenerationMetric.user_id.label('user_id'),
        func.coalesce(func.sum(GenerationMetric.total_tokens), 0).label('total_tokens'),
        func.coalesce(func.sum(GenerationMetric.prompt_tokens), 0).label('prompt_tokens'),
        func.coalesce(func.sum(GenerationMetric.completion_tokens), 0).label('completion_tokens'),
        func.count(GenerationMetric.id).label('generation_count'),
        func.coalesce(
            func.sum(case((GenerationMetric.source == 'chat', GenerationMetric.total_tokens), else_=0)),
            0,
        ).label('webui_tokens'),
        func.coalesce(
            func.sum(case((GenerationMetric.source != 'chat', GenerationMetric.total_tokens), else_=0)),
            0,
        ).label('api_tokens'),
    ).filter(GenerationMetric.user_id.isnot(None)).group_by(GenerationMetric.user_id).subquery()

    query = db.query(
        DBUser,
        case((DBUser.id.in_(online_users_subquery), True), else_=False).label('is_online'),
        func.count(func.distinct(DBTask.id)).label('task_count'),
        func.count(func.distinct(OpenAIAPIKey.id)).label('api_key_count'),
        func.count(func.distinct(WebSocketConnection.id)).label('connection_count'),
        func.coalesce(token_agg.c.total_tokens, 0).label('total_tokens'),
        func.coalesce(token_agg.c.prompt_tokens, 0).label('prompt_tokens'),
        func.coalesce(token_agg.c.completion_tokens, 0).label('completion_tokens'),
        func.coalesce(token_agg.c.generation_count, 0).label('generation_count'),
        func.coalesce(token_agg.c.webui_tokens, 0).label('webui_tokens'),
        func.coalesce(token_agg.c.api_tokens, 0).label('api_tokens'),
    ).outerjoin(DBTask, DBUser.id == DBTask.owner_user_id) \
     .outerjoin(OpenAIAPIKey, DBUser.id == OpenAIAPIKey.user_id) \
     .outerjoin(WebSocketConnection, DBUser.id == WebSocketConnection.user_id) \
     .outerjoin(token_agg, DBUser.id == token_agg.c.user_id) \
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

    # Sorting: total_tokens / generation_count live in the token subquery, so they
    # need their own branch (they are not ORM attributes on DBUser).
    if sort_by == 'total_tokens':
        token_sort = func.coalesce(token_agg.c.total_tokens, 0)
        query = query.order_by(token_sort.desc() if sort_order == 'desc' else token_sort.asc())
    elif sort_by == 'generation_count':
        gen_sort = func.coalesce(token_agg.c.generation_count, 0)
        query = query.order_by(gen_sort.desc() if sort_order == 'desc' else gen_sort.asc())
    else:
        sort_column = getattr(DBUser, sort_by) if hasattr(DBUser, sort_by) else literal_column(sort_by)
        query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())

    results = query.all()

    users_for_panel = []
    for row in results:
        (
            user, is_online, task_count, api_key_count, connection_count,
            total_tokens, prompt_tokens, completion_tokens,
            generation_count, webui_tokens, api_tokens,
        ) = row
        try:
            total_tokens = int(total_tokens or 0)
            energy_kwh = total_tokens * KWH_PER_TOKEN
            co2_g = energy_kwh * CO2_G_PER_KWH

            # Distinguishing "has a verified email" from "has an email" uses the
            # presence of ``email_verification_code``/``email_verification_token``
            # as the not-yet-verified signal — those columns are cleared on
            # successful verification in /auth/verify-email-code.
            has_verification_pending = bool(
                getattr(user, "email_verification_code", None)
                or getattr(user, "email_verification_token", None)
            )
            email_verified = bool(user.email) and not has_verification_pending

            now = datetime.now(timezone.utc)
            reset_expiry = getattr(user, "reset_token_expiry", None)
            if reset_expiry is not None and reset_expiry.tzinfo is None:
                reset_expiry = reset_expiry.replace(tzinfo=timezone.utc)
            has_pending_password_reset = bool(
                getattr(user, "password_reset_token", None)
                and reset_expiry
                and reset_expiry > now
            )

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
                "total_logins": getattr(user, "total_logins", 0) or 0,
                "email_verified": email_verified,
                "has_pending_password_reset": has_pending_password_reset,
                "is_online": is_online,
                "connection_count": connection_count,
                "api_key_count": api_key_count,
                "task_count": task_count,
                "generation_count": int(generation_count or 0),
                "total_tokens": total_tokens,
                "total_prompt_tokens": int(prompt_tokens or 0),
                "total_completion_tokens": int(completion_tokens or 0),
                "total_energy_kwh": round(energy_kwh, 4),
                "total_co2_g": round(co2_g, 2),
                "webui_tokens": int(webui_tokens or 0),
                "api_tokens": int(api_tokens or 0),
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

    from backend.db.models.generation_metric import GenerationMetric, calculate_co2_equivalents, KWH_PER_TOKEN, CO2_G_PER_KWH

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

    # Metrics Telemetry (per-day series split by source so the modal can chart
    # WebUI vs API independently, not just the lifetime rollup).
    metrics = db.query(
        func.date(GenerationMetric.created_at).label('metric_date'),
        GenerationMetric.source,
        func.count(GenerationMetric.id).label('gen_count'),
        func.sum(GenerationMetric.total_tokens).label('tok_count'),
        func.sum(GenerationMetric.prompt_tokens).label('p_tok'),
        func.sum(GenerationMetric.completion_tokens).label('c_tok')
    ).filter(
        GenerationMetric.user_id == user_id,
        GenerationMetric.created_at >= thirty_days_ago
    ).group_by(
        func.date(GenerationMetric.created_at),
        GenerationMetric.source,
    ).all()

    daily_msgs = defaultdict(int)         # generation count (kept for backward-compat consumers)
    daily_tokens = defaultdict(int)       # total tokens
    daily_prompt = defaultdict(int)       # prompt tokens
    daily_completion = defaultdict(int)   # completion tokens
    daily_webui_tokens = defaultdict(int) # WebUI (source=='chat') tokens
    daily_api_tokens = defaultdict(int)   # API (source!='chat') tokens
    daily_webui_gens = defaultdict(int)   # WebUI generation count
    daily_api_gens = defaultdict(int)     # API generation count

    total_tokens = 0
    total_prompt = 0
    total_comp = 0
    total_generations_30d = 0

    for date_str, src, count, tokens, p_tok, c_tok in metrics:
        if not date_str:
            continue
        d_str = str(date_str)
        cnt = count or 0
        tok = tokens or 0
        p = p_tok or 0
        c = c_tok or 0

        daily_msgs[d_str] += cnt
        daily_tokens[d_str] += tok
        daily_prompt[d_str] += p
        daily_completion[d_str] += c
        total_generations_30d += cnt
        total_tokens += tok
        total_prompt += p
        total_comp += c

        if src == "chat":
            daily_webui_tokens[d_str] += tok
            daily_webui_gens[d_str] += cnt
        else:
            daily_api_tokens[d_str] += tok
            daily_api_gens[d_str] += cnt

    top_models_raw = db.query(
        GenerationMetric.model_name,
        func.sum(GenerationMetric.total_tokens).label('tok_sum'),
        func.count(GenerationMetric.id).label('usage_count')
    ).filter(
        GenerationMetric.user_id == user_id
    ).group_by(GenerationMetric.model_name).order_by(desc('tok_sum')).limit(5).all()

    top_models = [
        {"model_name": row[0] or "unknown", "total_tokens": row[1] or 0, "count": row[2] or 0}
        for row in top_models_raw
    ]

    message_stats = [
        UserActivityStat(date=datetime.strptime(d_str, '%Y-%m-%d').date(), count=c)
        for d_str, c in sorted(daily_msgs.items())
    ]
    tokens_per_day = [
        UserActivityStat(date=datetime.strptime(d_str, '%Y-%m-%d').date(), count=c)
        for d_str, c in sorted(daily_tokens.items())
    ]
    generations_per_day = [
        UserActivityStat(date=datetime.strptime(d_str, '%Y-%m-%d').date(), count=c)
        for d_str, c in sorted(daily_msgs.items())
    ]
    webui_tokens_per_day = [
        UserActivityStat(date=datetime.strptime(d_str, '%Y-%m-%d').date(), count=c)
        for d_str, c in sorted(daily_webui_tokens.items())
    ]
    api_tokens_per_day = [
        UserActivityStat(date=datetime.strptime(d_str, '%Y-%m-%d').date(), count=c)
        for d_str, c in sorted(daily_api_tokens.items())
    ]
    prompt_tokens_per_day = [
        UserActivityStat(date=datetime.strptime(d_str, '%Y-%m-%d').date(), count=c)
        for d_str, c in sorted(daily_prompt.items())
    ]
    completion_tokens_per_day = [
        UserActivityStat(date=datetime.strptime(d_str, '%Y-%m-%d').date(), count=c)
        for d_str, c in sorted(daily_completion.items())
    ]

    # ── Weekly / monthly rollups (rolling windows ending today) ────────────
    def _sum_since(days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        val = db.query(
            func.coalesce(func.sum(GenerationMetric.total_tokens), 0)
        ).filter(
            GenerationMetric.user_id == user_id,
            GenerationMetric.created_at >= cutoff,
        ).scalar()
        return int(val or 0)

    tokens_last_7d = _sum_since(7)
    tokens_last_30d = _sum_since(30)

    gen_last_7d = int(
        db.query(func.count(GenerationMetric.id)).filter(
            GenerationMetric.user_id == user_id,
            GenerationMetric.created_at >= (datetime.now(timezone.utc) - timedelta(days=7)),
        ).scalar() or 0
    )
    gen_last_30d = total_generations_30d

    # ── Weekday profile (Monday..Sunday mean over the 30-day window) ───────
    weekday_buckets = defaultdict(list)
    for d_str, c in daily_msgs.items():
        try:
            weekday_buckets[datetime.strptime(d_str, '%Y-%m-%d').date().weekday()].append(c)
        except ValueError:
            continue
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_generation_mean = {
        name: (sum(weekday_buckets[i]) / len(weekday_buckets[i]) if weekday_buckets[i] else 0.0)
        for i, name in enumerate(weekday_names)
    }

    # Lifetime totals (unfiltered by the 30-day window) so the admin-list token
    # column and this per-user detail view report the same underlying figure.
    lifetime_totals = db.query(
        func.coalesce(func.sum(GenerationMetric.total_tokens), 0),
        func.coalesce(func.sum(GenerationMetric.prompt_tokens), 0),
        func.coalesce(func.sum(GenerationMetric.completion_tokens), 0),
        func.count(GenerationMetric.id),
    ).filter(GenerationMetric.user_id == user_id).first()
    lifetime_tokens = int(lifetime_totals[0] or 0) if lifetime_totals else 0
    lifetime_prompt = int(lifetime_totals[1] or 0) if lifetime_totals else 0
    lifetime_completion = int(lifetime_totals[2] or 0) if lifetime_totals else 0
    lifetime_gen_count = int(lifetime_totals[3] or 0) if lifetime_totals else 0

    source_rows = db.query(
        GenerationMetric.source,
        func.count(GenerationMetric.id).label('req_count'),
        func.sum(GenerationMetric.total_tokens).label('tot_tok')
    ).filter(
        GenerationMetric.user_id == user_id,
        GenerationMetric.created_at >= thirty_days_ago
    ).group_by(GenerationMetric.source).all()

    webui_tokens = 0
    api_tokens = 0
    webui_reqs = 0
    api_reqs = 0

    for src, req_c, tok_c in source_rows:
        t = tok_c or 0
        r = req_c or 0
        if src == "chat":
            webui_tokens += t
            webui_reqs += r
        else:
            api_tokens += t
            api_reqs += r

    total_reqs = webui_reqs + api_reqs
    sum_tokens = webui_tokens + api_tokens if (webui_tokens + api_tokens) > 0 else total_tokens

    webui_ratio = round((webui_tokens / sum_tokens * 100.0), 1) if sum_tokens > 0 else 0.0
    api_ratio = round((api_tokens / sum_tokens * 100.0), 1) if sum_tokens > 0 else 0.0

    from backend.models.admin import SourceConsumptionBreakdown

    source_breakdown = SourceConsumptionBreakdown(
        webui_tokens=webui_tokens,
        api_tokens=api_tokens,
        total_tokens=sum_tokens,
        webui_requests=webui_reqs,
        api_requests=api_reqs,
        total_requests=total_reqs,
        webui_ratio=webui_ratio,
        api_ratio=api_ratio,
        webui_energy_kwh=round(webui_tokens * KWH_PER_TOKEN, 4),
        api_energy_kwh=round(api_tokens * KWH_PER_TOKEN, 4),
        webui_co2_g=round(webui_tokens * KWH_PER_TOKEN * CO2_G_PER_KWH, 2),
        api_co2_g=round(api_tokens * KWH_PER_TOKEN * CO2_G_PER_KWH, 2)
    )

    # Prefer the lifetime metrics when available — the admin user list shows
    # lifetime totals, so the detail modal must match to avoid a confusing
    # discontinuity between the two views. Fall back to the 30-day window only
    # when no generation metrics exist at all (e.g. brand-new account).
    if lifetime_gen_count > 0:
        sum_tokens = lifetime_tokens
        total_prompt = lifetime_prompt
        total_comp = lifetime_completion

    energy_kwh = sum_tokens * KWH_PER_TOKEN
    co2_g = energy_kwh * CO2_G_PER_KWH
    equivalents = calculate_co2_equivalents(co2_g)

    return UserStats(
        tasks_per_day=task_stats,
        messages_per_day=message_stats,
        tokens_per_day=tokens_per_day,
        # New: richer breakdown of the same 30-day window so the single-user
        # detail view can match the depth of the global dashboard.
        generations_per_day=generations_per_day,
        webui_tokens_per_day=webui_tokens_per_day,
        api_tokens_per_day=api_tokens_per_day,
        prompt_tokens_per_day=prompt_tokens_per_day,
        completion_tokens_per_day=completion_tokens_per_day,
        tokens_last_7d=tokens_last_7d,
        tokens_last_30d=tokens_last_30d,
        generations_last_7d=gen_last_7d,
        generations_last_30d=gen_last_30d,
        weekday_generation_mean=weekday_generation_mean,
        total_generations_30d=total_generations_30d,
        # Preserved fields
        total_tokens=sum_tokens,
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_comp,
        total_energy_kwh=round(energy_kwh, 4),
        total_co2_g=round(co2_g, 2),
        co2_equivalents=equivalents,
        top_models=top_models,
        source_breakdown=source_breakdown,
    )

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
async def admin_activate_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Capture the transition BEFORE writing so we only send the welcome email
    # on an inactive→active change (re-clicking /activate is a no-op for mail).
    was_active = bool(user.is_active) and user.status == "active"

    user.is_active = True
    user.status = "active"
    user.activation_token = user.password_reset_token = user.reset_token_expiry = None
    db.commit()
    db.refresh(user)

    # Best-effort welcome email. Failure here must never fail activation.
    if not was_active:
        _maybe_send_welcome_email(db, user, _resolve_server_base_url(request))

    return _project_user_public(user)

@user_management_router.post("/users/bulk-activate", response_model=Dict[str, Any])
async def admin_bulk_activate(
    payload: Dict[str, List[int]],
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Activate every user in ``user_ids`` in one call. Returns per-id results so
    the UI can surface individual failures (missing user, etc.) without the
    whole batch rolling back. Welcome emails are sent (non-blocking) only for
    users that made a genuine inactive→active transition.
    """
    ids = payload.get("user_ids") or []
    if not ids:
        raise HTTPException(status_code=400, detail="No user IDs provided.")
    users = db.query(DBUser).filter(DBUser.id.in_(ids)).all()
    updated = []
    transitioned = []
    for u in users:
        # Only users moving into the active state qualify for a welcome email.
        was_active = bool(u.is_active) and u.status == "active"
        u.is_active = True
        u.status = "active"
        u.activation_token = None
        u.password_reset_token = None
        u.reset_token_expiry = None
        updated.append(u.id)
        if not was_active:
            transitioned.append(u)
    db.commit()

    server_url = _resolve_server_base_url(request)
    welcome_queued = 0
    for u in transitioned:
        db.refresh(u)
        if _maybe_send_welcome_email(db, u, server_url):
            welcome_queued += 1

    return {
        "updated": updated,
        "count": len(updated),
        "welcome_emails_queued": welcome_queued,
    }


@user_management_router.post("/users/bulk-deactivate", response_model=Dict[str, Any])
async def admin_bulk_deactivate(
    payload: Dict[str, List[int]],
    db: Session = Depends(get_db),
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
):
    """Deactivate every user in ``user_ids``. Skips the current admin and super-admin."""
    ids = payload.get("user_ids") or []
    if not ids:
        raise HTTPException(status_code=400, detail="No user IDs provided.")
    users = db.query(DBUser).filter(DBUser.id.in_(ids)).all()
    updated = []
    skipped = []
    for u in users:
        if u.id == current_admin.id or u.username == INITIAL_ADMIN_USER_CONFIG.get("username"):
            skipped.append(u.id)
            continue
        u.is_active = False
        u.status = "inactivated_by_admin"
        if u.username in user_sessions:
            del user_sessions[u.username]
        updated.append(u.id)
    db.commit()
    return {"updated": updated, "skipped": skipped, "count": len(updated)}


@user_management_router.post("/users/bulk-disconnect", response_model=Dict[str, Any])
async def admin_bulk_disconnect(
    payload: Dict[str, List[int]],
    db: Session = Depends(get_db),
):
    """Force disconnect every user in ``user_ids`` (session clear + WS kick)."""
    ids = payload.get("user_ids") or []
    if not ids:
        raise HTTPException(status_code=400, detail="No user IDs provided.")
    from backend.ws_manager import manager
    disconnected = []
    for uid in ids:
        user = db.query(DBUser).filter(DBUser.id == uid).first()
        if not user:
            continue
        if user.username in user_sessions:
            del user_sessions[user.username]
        try:
            manager.disconnect_user_sync(user.id)
        except Exception:
            pass
        disconnected.append(user.id)
    return {"disconnected": disconnected, "count": len(disconnected)}


@user_management_router.post("/users/bulk-set-role", response_model=Dict[str, Any])
async def admin_bulk_set_role(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
):
    """
    Grant or revoke a role for every user in ``user_ids``.
    Payload: ``{ "user_ids": [...], "role": "admin"|"moderator", "grant": true|false }``
    Super-admin and self demotions are silently skipped.
    """
    ids = payload.get("user_ids") or []
    role = payload.get("role")
    grant = bool(payload.get("grant", True))
    if not ids:
        raise HTTPException(status_code=400, detail="No user IDs provided.")
    if role not in ("admin", "moderator"):
        raise HTTPException(status_code=400, detail="role must be 'admin' or 'moderator'.")

    users = db.query(DBUser).filter(DBUser.id.in_(ids)).all()
    updated = []
    skipped = []
    for u in users:
        if not grant and (u.id == current_admin.id or u.username == INITIAL_ADMIN_USER_CONFIG.get("username")):
            skipped.append(u.id)
            continue
        if role == "admin":
            u.is_admin = grant
            if not grant:
                # Revoking admin also revokes moderator (matches single-user rule).
                u.is_moderator = False
        else:
            u.is_moderator = grant
            if grant and not u.is_admin:
                pass  # moderator without admin is allowed
        updated.append(u.id)
    db.commit()
    return {"updated": updated, "skipped": skipped, "count": len(updated)}


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

@user_management_router.post("/users/{user_id}/email", response_model=TaskInfo, status_code=202)
async def admin_email_single_user(
    user_id: int,
    payload: EmailUsersRequest,
    db: Session = Depends(get_db),
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
):
    """
    Send a one-off email to a single user without going through the multi-recipient
    campaign UI. Thin wrapper around the existing ``email_users`` task path so
    delivery, logging, and audit (EmailProposal) behave identically.

    Payload: ``EmailUsersRequest`` where ``user_ids`` is overridden with the path
    ``user_id`` — callers pass only subject/body/background_color/send_as_text.
    """
    if settings.get("password_recovery_mode") not in ["automatic", "gmail", "system_mail", "outlook"]:
        raise HTTPException(
            status_code=412,
            detail="Email dispatch is not configured. Configure SMTP or system mail in Admin Settings.",
        )
    target = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if not target.email:
        raise HTTPException(status_code=400, detail=f"User '{target.username}' has no email address.")
    if not target.receive_notification_emails:
        raise HTTPException(
            status_code=409,
            detail=f"User '{target.username}' has opted out of notification emails.",
        )

    # Archive as a single-recipient Campaign so it appears in the audit trail
    # alongside batch and newsletter sends.
    proposal = EmailProposal(
        title=payload.subject,
        content=payload.body,
        source_topic=f"Direct message to {target.username}",
        status=EmailStatus.APPROVED,
        recipients=[target.id],
        generated_by=current_admin.username,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    db_task = task_manager.submit_task(
        name=f"Direct email to {target.username}: {payload.subject[:40]}",
        target=_email_users_task,
        args=(
            [target.id],
            payload.subject,
            payload.body,
            payload.background_color,
            payload.send_as_text,
            proposal.id,
        ),
        owner_username=current_admin.username,
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