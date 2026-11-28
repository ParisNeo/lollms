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
from backend.models.admin import (
    UserForAdminPanel, UserStats, UserActivityStat, AdminDashboardStats,
    TokenQuotaUpdate, TokenQuotaStatus, TokenQuotaUsage,
)
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
async def get_user_stats(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
):
    """Aggregate per-user usage statistics for the admin stats modal.

    Single source of truth shared by the JSON endpoint and every export format
    (html/pdf/docx/xlsx). All series are 30-day windows built from
    ``GenerationMetric`` plus the user's ``UserStats`` shape.
    """
    from backend.db.models.generation_metric import (
        GenerationMetric, KWH_PER_TOKEN, CO2_G_PER_KWH, calculate_co2_equivalents,
    )

    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    base = db.query(GenerationMetric).filter(GenerationMetric.user_id == user_id)
    rows_30d = base.filter(GenerationMetric.created_at >= cutoff_30d).all()

    total_tokens = total_prompt = total_completion = 0
    tokens_7d = tokens_30d = gens_7d = gens_30d = 0
    webui_tokens = api_tokens = webui_requests = api_requests = 0
    energy_kwh = co2_g = 0.0

    def _norm_dt(dt):
        if dt is None:
            return now
        if isinstance(dt, str):
            try:
                return datetime.fromisoformat(dt)
            except ValueError:
                return now
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    daily_tokens = defaultdict(int)
    daily_webui = defaultdict(int)
    daily_api = defaultdict(int)
    daily_prompt = defaultdict(int)
    daily_completion = defaultdict(int)
    daily_gens = defaultdict(int)
    model_totals = defaultdict(lambda: {"model_name": "", "total_tokens": 0, "count": 0})
    weekday_counts = defaultdict(list)

    for r in rows_30d:
        pt = int(r.prompt_tokens or 0)
        ct = int(r.completion_tokens or 0)
        tt = int(r.total_tokens or (pt + ct))
        energy_kwh += float(r.energy_kwh or 0)
        co2_g += float(r.co2_g or 0)
        dt = _norm_dt(r.created_at)
        day = dt.strftime("%Y-%m-%d")
        daily_tokens[day] += tt
        daily_prompt[day] += pt
        daily_completion[day] += ct
        daily_gens[day] += 1
        weekday_counts[dt.weekday()].append(1)
        if (r.source or "chat") == "chat":
            daily_webui[day] += tt
            webui_tokens += tt
            webui_requests += 1
        else:
            daily_api[day] += tt
            api_tokens += tt
            api_requests += 1
        mname = r.model_name or "unknown"
        m = model_totals[mname]
        m["model_name"] = mname
        m["total_tokens"] += tt
        m["count"] += 1

    # Lifetime totals (independent of the 30-day window).
    lifetime = db.query(
        func.coalesce(func.sum(GenerationMetric.total_tokens), 0),
        func.coalesce(func.sum(GenerationMetric.prompt_tokens), 0),
        func.coalesce(func.sum(GenerationMetric.completion_tokens), 0),
    ).filter(GenerationMetric.user_id == user_id).first()
    if lifetime:
        total_tokens, total_prompt, total_completion = (int(lifetime[0] or 0), int(lifetime[1] or 0), int(lifetime[2] or 0))

    seven = db.query(
        func.coalesce(func.sum(GenerationMetric.total_tokens), 0),
        func.count(GenerationMetric.id),
    ).filter(GenerationMetric.user_id == user_id, GenerationMetric.created_at >= cutoff_7d).first()
    if seven:
        tokens_7d, gens_7d = int(seven[0] or 0), int(seven[1] or 0)
    tokens_30d = sum(daily_tokens.values())
    gens_30d = sum(daily_gens.values())

    # Tasks per day (last 30 days) owned by this user. ``UserStats.tasks_per_day``
    # is a REQUIRED field, so we must always supply it (empty list is valid).
    task_rows = db.query(
        func.date(DBTask.created_at).label("d"),
        func.count(DBTask.id).label("c"),
    ).filter(
        DBTask.owner_user_id == user_id,
        DBTask.created_at >= cutoff_30d,
    ).group_by(func.date(DBTask.created_at)).all()
    tasks_per_day = [
        UserActivityStat(date=datetime.strptime(str(d), "%Y-%m-%d").date(), count=int(c or 0))
        for d, c in task_rows
        if d
    ]

    def _series(source_map):
        return [{"date": d, "count": int(v)} for d, v in sorted(source_map.items())]

    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_mean = {weekday_names[i]: round(len(weekday_counts.get(i, [])), 2) for i in range(7) if weekday_counts.get(i)}
    for i in range(7):
        weekday_mean.setdefault(weekday_names[i], 0.0)

    share_base = (webui_tokens + api_tokens) or 1
    webui_ratio = round(webui_tokens / share_base * 100, 1)
    api_ratio = round(api_tokens / share_base * 100, 1)

    top_models = sorted(model_totals.values(), key=lambda x: x["total_tokens"], reverse=True)[:10]

    from backend.models.admin import SourceConsumptionBreakdown
    source_breakdown = SourceConsumptionBreakdown(
        webui_tokens=webui_tokens,
        api_tokens=api_tokens,
        total_tokens=webui_tokens + api_tokens,
        webui_requests=webui_requests,
        api_requests=api_requests,
        total_requests=webui_requests + api_requests,
        webui_ratio=webui_ratio,
        api_ratio=api_ratio,
        webui_energy_kwh=round(webui_tokens * KWH_PER_TOKEN, 4),
        api_energy_kwh=round(api_tokens * KWH_PER_TOKEN, 4),
        webui_co2_g=round(webui_tokens * KWH_PER_TOKEN * CO2_G_PER_KWH, 2),
        api_co2_g=round(api_tokens * KWH_PER_TOKEN * CO2_G_PER_KWH, 2),
    )

    return UserStats(
        user_id=user_id,
        username=user.username,
        tokens_last_7d=tokens_7d,
        tokens_last_30d=tokens_30d,
        generations_last_7d=gens_7d,
        generations_last_30d=gens_30d,
        total_tokens=total_tokens,
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        total_generations_30d=gens_30d,
        total_energy_kwh=round(energy_kwh, 4),
        total_co2_g=round(co2_g, 2),
        co2_equivalents=calculate_co2_equivalents(co2_g),
        tokens_per_day=_series(daily_tokens),
        prompt_tokens_per_day=_series(daily_prompt),
        completion_tokens_per_day=_series(daily_completion),
        webui_tokens_per_day=_series(daily_webui),
        api_tokens_per_day=_series(daily_api),
        messages_per_day=_series(daily_gens),
        tasks_per_day=tasks_per_day,
        weekday_generation_mean=weekday_mean,
        source_breakdown=source_breakdown,
        top_models=top_models,
    )


@user_management_router.get("/users/{user_id}/stats/export")
async def export_user_stats(
    user_id: int,
    format: str = Query("xlsx", pattern="^(xlsx|html|docx|pdf)$"),
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Export a single user's statistics in html/pdf/docx/xlsx.

    Strictly scoped to ``user_id`` so the exported document can never leak
    another user's data. Reuses ``get_user_stats`` as the single source of
    truth so every format matches the on-screen modal exactly.
    """
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    report = await get_user_stats(user_id=user_id, db=db, current_admin=current_admin)
    data = report.model_dump() if hasattr(report, "model_dump") else dict(report)

    import io as _io
    from datetime import datetime as _dt
    from fastapi import Response as _Resp

    stamp = _dt.now().strftime("%Y-%m-%d %H:%M")
    filename_base = f"user_stats_{user.username}_{_dt.now().strftime('%Y%m%d_%H%M%S')}"
    title = f"User Statistics — {user.username}"
    subtitle = (
        f"Account: {user.username} (id {user.id}) · Role: "
        f"{'Admin' if getattr(user, 'is_admin', False) else ('Moderator' if getattr(user, 'is_moderator', False) else 'User')}"
        f" · Status: {user.status} · Generated: {stamp}"
    )

    def _num(n):
        try:
            return f"{int(n):,}"
        except Exception:
            return str(n)

    sb = data.get("source_breakdown") or {}
    tokens_per_day = data.get("tokens_per_day") or []
    webui_per_day = data.get("webui_tokens_per_day") or []
    api_per_day = data.get("api_tokens_per_day") or []
    generations_per_day = data.get("messages_per_day") or []
    top_models = data.get("top_models") or []

    # Charts are rendered once (PNG bytes) and reused across HTML/DOCX/PDF.
    # ``_user_stats_charts`` degrades to an empty list when matplotlib is absent.
    try:
        from backend.routers.admin import _user_stats_charts as _charts_mod
        chart_items = _charts_mod.build_charts(data)
    except Exception:
        _charts_mod = None
        chart_items = []

    def _build_html():
        rows = "".join(
            f"<tr><td>{t.get('date','')}</td><td>{_num(t.get('count',0))}</td></tr>"
            for t in tokens_per_day
        )
        model_rows = "".join(
            f"<tr><td>{m.get('model_name','')}</td><td>{_num(m.get('total_tokens',0))}</td>"
            f"<td>{_num(m.get('count',0))}</td></tr>"
            for m in top_models
        )
        kpi = (
            f"<div class='kpi'><b>Total tokens:</b> {_num(data.get('total_tokens',0))} "
            f"({_num(data.get('total_prompt_tokens',0))} in · {_num(data.get('total_completion_tokens',0))} out)</div>"
            f"<div class='kpi'><b>Lifetime generations:</b> {_num(data.get('total_generations_30d',0))}</div>"
            f"<div class='kpi'><b>Tokens (7d / 30d):</b> {_num(data.get('tokens_last_7d',0))} / {_num(data.get('tokens_last_30d',0))}</div>"
            f"<div class='kpi'><b>WebUI / API tokens:</b> {_num(sb.get('webui_tokens',0))} / {_num(sb.get('api_tokens',0))}</div>"
            f"<div class='kpi'><b>Energy:</b> {data.get('total_energy_kwh',0)} kWh · {data.get('total_co2_g',0)} g CO₂</div>"
        )
        charts_html = ""
        if chart_items and _charts_mod is not None:
            blocks = "".join(
                f"<div class='chart'><div class='chart-title'>{c_title}</div>"
                f"<img src='{_charts_mod.png_to_data_uri(c_png)}' alt='{c_title}' /></div>"
                for c_title, c_png in chart_items
            )
            charts_html = f"<h2>Charts</h2>{blocks}"
        return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:32px;color:#1f2937;}}
h1{{font-size:22px;margin:0 0 4px;}} .sub{{color:#6b7280;font-size:12px;margin-bottom:20px;}}
.kpi{{padding:6px 0;font-size:13px;border-bottom:1px solid #eee;}}
table{{border-collapse:collapse;width:100%;margin:12px 0 24px;font-size:12px;}}
th,td{{border:1px solid #e5e7eb;padding:6px 8px;text-align:left;}}
th{{background:#f3f4f6;font-weight:700;}}
h2{{font-size:15px;margin:24px 0 4px;}}
.chart{{margin:14px 0 22px;page-break-inside:avoid;}}
.chart-title{{font-size:12px;font-weight:700;color:#374151;margin-bottom:6px;}}
.chart img{{width:100%;max-width:720px;height:auto;border:1px solid #eef0f3;border-radius:6px;}}
</style></head><body>
<h1>{title}</h1><div class="sub">{subtitle}</div>
<div>{kpi}</div>
{charts_html}
<h2>Tokens per day (30 days)</h2>
<table><thead><tr><th>Date</th><th>Tokens</th></tr></thead>
<tbody>{rows or '<tr><td colspan="2">No data</td></tr>'}</tbody></table>
<h2>Top models</h2>
<table><thead><tr><th>Model</th><th>Tokens</th><th>Calls</th></tr></thead>
<tbody>{model_rows or '<tr><td colspan="3">No data</td></tr>'}</tbody></table>
</body></html>"""

    if format == "html":
        return _Resp(
            content=_build_html().encode("utf-8"),
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.html"'},
        )

    # DOCX / PDF reuse the shared, Windows-safe conversion helpers in
    # ``backend.routers.files`` (the same ones powering the consumption-analytics
    # export). This avoids importing WeasyPrint directly, which raises an
    # ``OSError`` at import time on hosts missing GTK/Pango (libgobject) — that
    # turned every PDF request into a 500. The helpers transparently fall back
    # to a pure-Python engine, so PDF/DOCX work on any platform.
    try:
        from backend.routers.files import (
            md2_to_html, html_to_docx_bytes, md_to_pdf_bytes, html_to_pdf_bytes,
        )
    except Exception:
        md2_to_html = html_to_docx_bytes = md_to_pdf_bytes = html_to_pdf_bytes = None

    if format == "docx":
        # Prefer a NATIVE python-docx build so chart PNGs embed cleanly via
        # add_picture (the generic HTML->DOCX converter cannot reliably embed
        # images). Fall back to the shared HTML helper when python-docx is
        # unavailable, preserving the previous table-only behaviour.
        try:
            from docx import Document
            from docx.shared import Inches
        except Exception:
            Document = None

        if Document is not None:
            try:
                doc = Document()
                doc.add_heading(title, level=1)
                doc.add_paragraph(subtitle)

                doc.add_heading("Summary", level=2)
                summary = doc.add_table(rows=0, cols=2)
                try:
                    summary.style = "Light Grid Accent 1"
                except Exception:
                    pass
                metrics = [
                    ("Total tokens", _num(data.get("total_tokens", 0))),
                    ("Prompt tokens", _num(data.get("total_prompt_tokens", 0))),
                    ("Completion tokens", _num(data.get("total_completion_tokens", 0))),
                    ("Tokens (7d)", _num(data.get("tokens_last_7d", 0))),
                    ("Tokens (30d)", _num(data.get("tokens_last_30d", 0))),
                    ("WebUI tokens", _num(sb.get("webui_tokens", 0))),
                    ("API tokens", _num(sb.get("api_tokens", 0))),
                    ("Energy (kWh)", str(data.get("total_energy_kwh", 0))),
                    ("CO2 (g)", str(data.get("total_co2_g", 0))),
                ]
                for label, value in metrics:
                    cells = summary.add_row().cells
                    cells[0].text = str(label)
                    cells[1].text = str(value)

                # Embed charts as images (one section per figure).
                if chart_items:
                    doc.add_heading("Charts", level=2)
                    for c_title, c_png in chart_items:
                        doc.add_heading(c_title, level=3)
                        stream = _io.BytesIO(c_png)
                        stream.seek(0)
                        try:
                            doc.add_picture(stream, width=Inches(6.3))
                        except Exception:
                            # A malformed image must not sink the whole export.
                            pass

                doc.add_heading("Top models", level=2)
                mt = doc.add_table(rows=1, cols=3)
                try:
                    mt.style = "Light Grid Accent 1"
                except Exception:
                    pass
                hdr = mt.rows[0].cells
                hdr[0].text, hdr[1].text, hdr[2].text = "Model", "Tokens", "Calls"
                if top_models:
                    for m in top_models:
                        c = mt.add_row().cells
                        c[0].text = str(m.get("model_name") or "unknown")
                        c[1].text = _num(m.get("total_tokens", 0))
                        c[2].text = _num(m.get("count", 0))
                else:
                    mt.add_row().cells[0].text = "No model usage recorded."

                bio = _io.BytesIO()
                doc.save(bio)
                content = bio.getvalue()
            except Exception as e:
                trace_exception(e)
                raise HTTPException(status_code=500, detail=f"DOCX generation failed: {e}")
        else:
            if html_to_docx_bytes is None:
                raise HTTPException(status_code=501, detail="DOCX export is unavailable (helper import failed).")
            try:
                content = html_to_docx_bytes(_build_html())
            except Exception as e:
                trace_exception(e)
                raise HTTPException(status_code=500, detail=f"DOCX generation failed: {e}")

        return _Resp(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.docx"'},
        )

    if format == "pdf":
        # Prefer a self-contained reportlab build so chart images are drawn as
        # native Image flowables (guaranteed rendering, cross-platform). When
        # reportlab is unavailable we fall back to the shared HTML->PDF helper
        # (charts are inlined as base64 <img>, rendered by engines that support
        # them; at worst the tabular report still exports).
        content = None
        if chart_items:
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import mm
                from reportlab.platypus import (
                    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                    Image as RLImage, PageBreak,
                )
                from reportlab.lib import colors as rl_colors

                pdf_buf = _io.BytesIO()
                docpdf = SimpleDocTemplate(
                    pdf_buf, pagesize=A4,
                    leftMargin=16 * mm, rightMargin=16 * mm,
                    topMargin=14 * mm, bottomMargin=14 * mm,
                    title=title,
                )
                styles = getSampleStyleSheet()
                body_style = ParagraphStyle(
                    "UsrSub", parent=styles["Normal"], fontSize=8.5,
                    textColor=rl_colors.HexColor("#6b7280"),
                )
                h2_style = ParagraphStyle(
                    "UsrH2", parent=styles["Heading2"], fontSize=12,
                    spaceBefore=10, spaceAfter=4,
                )
                story = [
                    Paragraph(title, styles["Title"]),
                    Paragraph(subtitle, body_style),
                    Spacer(1, 8),
                    Paragraph("Summary", h2_style),
                ]
                kv_rows = [
                    ["Total tokens", _num(data.get("total_tokens", 0))],
                    ["Prompt tokens", _num(data.get("total_prompt_tokens", 0))],
                    ["Completion tokens", _num(data.get("total_completion_tokens", 0))],
                    ["Tokens (7d / 30d)", f"{_num(data.get('tokens_last_7d', 0))} / {_num(data.get('tokens_last_30d', 0))}"],
                    ["WebUI / API tokens", f"{_num(sb.get('webui_tokens', 0))} / {_num(sb.get('api_tokens', 0))}"],
                    ["Energy (kWh)", str(data.get("total_energy_kwh", 0))],
                    ["CO2 (g)", str(data.get("total_co2_g", 0))],
                ]
                kv_table = Table(kv_rows, colWidths=[70 * mm, 100 * mm])
                kv_table.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.4, rl_colors.HexColor("#e5e7eb")),
                    ("BACKGROUND", (0, 0), (0, -1), rl_colors.HexColor("#f3f4f6")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]))
                story.append(kv_table)
                story.append(PageBreak())

                # One chart per page, scaled to the printable width.
                page_width = A4[0] - 32 * mm
                for c_title, c_png in chart_items:
                    story.append(Paragraph(c_title, h2_style))
                    try:
                        img = RLImage(_io.BytesIO(c_png))
                        # Preserve aspect ratio, clamp to page width.
                        ratio = img.imageHeight / float(img.imageWidth or 1)
                        img.drawWidth = page_width
                        img.drawHeight = page_width * ratio
                        story.append(img)
                    except Exception:
                        pass
                    story.append(Spacer(1, 6))
                    story.append(PageBreak())

                docpdf.build(story)
                content = pdf_buf.getvalue()
            except Exception as e:
                trace_exception(e)
                content = None  # fall through to helper path

        if content is None:
            if html_to_pdf_bytes is None and md_to_pdf_bytes is None:
                raise HTTPException(status_code=501, detail="PDF export is unavailable (no PDF engine).")
            html = _build_html()
            try:
                content = html_to_pdf_bytes(html) if html_to_pdf_bytes else md_to_pdf_bytes(html)
            except Exception as e:
                try:
                    content = html_to_pdf_bytes(html)
                except Exception:
                    trace_exception(e)
                    raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

        return _Resp(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.pdf"'},
        )

    # ---- XLSX: styled tables + native Excel charts -----------------------
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()

    _HEADER_FILL = PatternFill("solid", fgColor="4F46E5")
    _HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
    _TITLE_FONT = Font(bold=True, size=16, color="1F2937")
    _SUB_FONT = Font(italic=True, size=10, color="6B7280")
    _THIN = Side(style="thin", color="E5E7EB")
    _BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
    _CENTER = Alignment(horizontal="center", vertical="center")

    def _style_header(ws, row, ncols):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=row, column=c)
            cell.fill = _HEADER_FILL
            cell.font = _HEADER_FONT
            cell.alignment = _CENTER
            cell.border = _BORDER

    def _style_body(ws, first_row, last_row, ncols, right_cols=()):
        for r in range(first_row, last_row + 1):
            for c in range(1, ncols + 1):
                cell = ws.cell(row=r, column=c)
                cell.border = _BORDER
                if c in right_cols:
                    cell.alignment = Alignment(horizontal="right")

    # --- Summary sheet (user info block + KPIs) ---
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = title
    ws["A1"].font = _TITLE_FONT
    ws["A2"] = subtitle
    ws["A2"].font = _SUB_FONT
    ws.merge_cells("A1:D1")
    ws.merge_cells("A2:D2")

    ws["A4"] = "User Information"
    ws["A4"].font = Font(bold=True, size=13)
    info_rows = [
        ("Username", user.username),
        ("User ID", user.id),
        ("Role", "Admin" if getattr(user, "is_admin", False) else ("Moderator" if getattr(user, "is_moderator", False) else "User")),
        ("Status", user.status),
        ("Email", user.email or "—"),
    ]
    r = 5
    for label, value in info_rows:
        ws.cell(row=r, column=1, value=label).font = Font(bold=True)
        ws.cell(row=r, column=2, value=value)
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Key Metrics").font = Font(bold=True, size=13)
    r += 1
    ws.cell(row=r, column=1, value="Metric")
    ws.cell(row=r, column=2, value="Value")
    _style_header(ws, r, 2)
    metrics = [
        ("Total tokens", int(data.get("total_tokens", 0))),
        ("Prompt tokens", int(data.get("total_prompt_tokens", 0))),
        ("Completion tokens", int(data.get("total_completion_tokens", 0))),
        ("Tokens last 7d", int(data.get("tokens_last_7d", 0))),
        ("Tokens last 30d", int(data.get("tokens_last_30d", 0))),
        ("Generations last 7d", int(data.get("generations_last_7d", 0))),
        ("Generations last 30d", int(data.get("generations_last_30d", 0))),
        ("WebUI tokens", int(sb.get("webui_tokens", 0))),
        ("API tokens", int(sb.get("api_tokens", 0))),
        ("Energy (kWh)", float(data.get("total_energy_kwh", 0))),
        ("CO2 (g)", float(data.get("total_co2_g", 0))),
    ]
    first_metric_row = r + 1
    for label, value in metrics:
        r += 1
        ws.cell(row=r, column=1, value=label)
        ws.cell(row=r, column=2, value=value)
    _style_body(ws, first_metric_row, r, 2, right_cols=(2,))
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 24

    # --- WebUI vs API split: small data block + native pie chart ---
    split_label_row = r + 2
    ws.cell(row=split_label_row, column=1, value="WebUI vs API tokens").font = Font(bold=True, size=13)
    ws.cell(row=split_label_row + 1, column=1, value="Channel")
    ws.cell(row=split_label_row + 1, column=2, value="Tokens")
    _style_header(ws, split_label_row + 1, 2)
    ws.cell(row=split_label_row + 2, column=1, value="WebUI")
    ws.cell(row=split_label_row + 2, column=2, value=int(sb.get("webui_tokens", 0)))
    ws.cell(row=split_label_row + 3, column=1, value="API")
    ws.cell(row=split_label_row + 3, column=2, value=int(sb.get("api_tokens", 0)))
    _style_body(ws, split_label_row + 2, split_label_row + 3, 2, right_cols=(2,))
    if (int(sb.get("webui_tokens", 0)) + int(sb.get("api_tokens", 0))) > 0:
        from openpyxl.chart import PieChart, Reference
        pie = PieChart()
        pie.title = "WebUI vs API token share"
        pdata = Reference(ws, min_col=2, min_row=split_label_row + 1, max_row=split_label_row + 3)
        plabels = Reference(ws, min_col=1, min_row=split_label_row + 2, max_row=split_label_row + 3)
        pie.add_data(pdata, titles_from_data=True)
        pie.set_categories(plabels)
        pie.height = 7
        pie.width = 11
        ws.add_chart(pie, "D5")

    # --- Timeline sheet + chart ---
    ws2 = wb.create_sheet("Timeline")
    ws2["A1"] = "Tokens per day"
    ws2["A1"].font = Font(bold=True, size=13)
    headers = ["Date", "Tokens", "WebUI", "API", "Generations"]
    for i, h in enumerate(headers, start=1):
        ws2.cell(row=3, column=i, value=h)
    _style_header(ws2, 3, len(headers))

    webui_map = {str(w.get("date")): int(w.get("count", 0)) for w in webui_per_day}
    api_map = {str(a.get("date")): int(a.get("count", 0)) for a in api_per_day}
    gen_map = {str(g.get("date")): int(g.get("count", 0)) for g in generations_per_day}

    row_idx = 4
    for t in tokens_per_day:
        d = str(t.get("date"))
        ws2.cell(row=row_idx, column=1, value=d)
        ws2.cell(row=row_idx, column=2, value=int(t.get("count", 0)))
        ws2.cell(row=row_idx, column=3, value=webui_map.get(d, 0))
        ws2.cell(row=row_idx, column=4, value=api_map.get(d, 0))
        ws2.cell(row=row_idx, column=5, value=gen_map.get(d, 0))
        row_idx += 1
    last_row = row_idx - 1
    if last_row >= 4:
        _style_body(ws2, 4, last_row, len(headers), right_cols=(2, 3, 4, 5))
        from openpyxl.chart import BarChart, Reference
        chart = BarChart()
        chart.type = "col"
        chart.title = f"Tokens per day — {user.username}"
        chart.y_axis.title = "Tokens"
        chart.x_axis.title = "Date"
        data_ref = Reference(ws2, min_col=2, min_row=3, max_row=last_row)
        cats_ref = Reference(ws2, min_col=1, min_row=4, max_row=last_row)
        chart.add_data(data_ref, titles_from_data=True)
        chart.set_categories(cats_ref)
        chart.height = 9
        chart.width = 24
        ws2.add_chart(chart, "G3")
    for col, w in zip("ABCDE", (14, 12, 12, 12, 14)):
        ws2.column_dimensions[col].width = w

    # --- Top models sheet + chart ---
    ws3 = wb.create_sheet("Top Models")
    ws3["A1"] = "Top models"
    ws3["A1"].font = Font(bold=True, size=13)
    m_headers = ["Model", "Tokens", "Calls"]
    for i, h in enumerate(m_headers, start=1):
        ws3.cell(row=3, column=i, value=h)
    _style_header(ws3, 3, len(m_headers))
    mr = 4
    for m in top_models:
        ws3.cell(row=mr, column=1, value=m.get("model_name", ""))
        ws3.cell(row=mr, column=2, value=int(m.get("total_tokens", 0)))
        ws3.cell(row=mr, column=3, value=int(m.get("count", 0)))
        mr += 1
    m_last = mr - 1
    if m_last >= 4:
        _style_body(ws3, 4, m_last, len(m_headers), right_cols=(2, 3))
        from openpyxl.chart import BarChart, Reference
        chart2 = BarChart()
        chart2.type = "bar"
        chart2.title = "Tokens by model"
        chart2.y_axis.title = "Model"
        chart2.x_axis.title = "Tokens"
        data_ref2 = Reference(ws3, min_col=2, min_row=3, max_row=m_last)
        cats_ref2 = Reference(ws3, min_col=1, min_row=4, max_row=m_last)
        chart2.add_data(data_ref2, titles_from_data=True)
        chart2.set_categories(cats_ref2)
        chart2.height = 8
        chart2.width = 22
        ws3.add_chart(chart2, "E3")
    for col, w in zip("ABC", (28, 14, 12)):
        ws3.column_dimensions[col].width = w

    bio = _io.BytesIO()
    wb.save(bio)
    return _Resp(
        content=bio.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename_base}.xlsx"'},
    )


def _build_quota_status(db: Session, user: DBUser) -> TokenQuotaStatus:
    """Resolve the effective quota for a user and attach current-period usage."""
    from backend.token_quota import get_quota_status
    status = get_quota_status(db, user)
    return TokenQuotaStatus(
        enforced=status.enforced,
        exempt=status.exempt,
        period=status.period,
        enabled=getattr(user, "token_quota_enabled", None),
        input_max=status.input_max,
        output_max=status.output_max,
        reset_at=status.period_end,
        usage=TokenQuotaUsage(
            input_used=status.input_used,
            input_max=status.input_max,
            output_used=status.output_used,
            output_max=status.output_max,
            period_start=status.period_start,
            period_end=status.period_end,
        ),
    )


@user_management_router.get("/users/{user_id}/token-quota", response_model=TokenQuotaStatus)
async def admin_get_user_token_quota(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
):
    """Return a single user's resolved quota overrides + current-period usage."""
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _build_quota_status(db, user)


@user_management_router.put("/users/{user_id}/token-quota", response_model=TokenQuotaStatus)
async def admin_update_user_token_quota(
    user_id: int,
    payload: TokenQuotaUpdate,
    db: Session = Depends(get_db),
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
):
    """
    Update a user's token quota overrides.

    Semantics per field:
      • ``None`` → inherit the global default (column set to NULL).
      • ``0``    → unlimited for that direction.
      • ``> 0``  → explicit per-user maximum.
    Only fields present in the payload are touched so partial updates are safe.
    """
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    provided = payload.model_dump(exclude_unset=True)

    if "period" in provided:
        period = provided["period"]
        if period is not None and period not in ("daily", "weekly", "monthly"):
            raise HTTPException(
                status_code=400,
                detail="period must be 'daily', 'weekly', 'monthly', or null.",
            )
        user.token_quota_period = period

    if "enabled" in provided:
        user.token_quota_enabled = provided["enabled"]

    if "exempt" in provided:
        user.token_quota_exempt = bool(provided["exempt"])

    for field_name in ("input_max", "output_max"):
        if field_name in provided:
            value = provided[field_name]
            if value is not None and int(value) < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"{field_name} must be >= 0 (0 = unlimited) or null to inherit.",
                )
            setattr(user, f"token_quota_{field_name}", value)

    db.commit()
    db.refresh(user)
    return _build_quota_status(db, user)


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
    current_admin: UserAuthDetails = Depends(get_current_admin_user),
):
    """
    Activate every user in ``user_ids`` in one call. Skips the current admin and
    the super-admin (mirrors bulk-deactivate). Returns per-id results so the UI
    can surface individual failures without the whole batch rolling back.
    Welcome emails are sent (non-blocking) only for non-skipped users that made
    a genuine inactive→active transition.
    """
    ids = payload.get("user_ids") or []
    if not ids:
        raise HTTPException(status_code=400, detail="No user IDs provided.")
    users = db.query(DBUser).filter(DBUser.id.in_(ids)).all()
    updated = []
    skipped = []
    transitioned = []
    for u in users:
        # Never let a bulk operation re-activate the acting admin or the
        # environment's root super-admin account.
        if u.id == current_admin.id or u.username == INITIAL_ADMIN_USER_CONFIG.get("username"):
            skipped.append(u.id)
            continue
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
        "skipped": skipped,
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