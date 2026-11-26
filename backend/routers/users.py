# backend/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, exists

from backend.db import get_db
from backend.db.utils import get_friendship_record
from backend.db.base import follows_table
from backend.db.models.user import User as DBUser
from backend.db.models.service import MCP as DBMCP
from backend.models import UserAuthDetails, UserProfileResponse, UserPublic
from backend.models.user import UserMCPAccessInfo
from backend.models.admin import UserStats, UserActivityStat
from backend.session import get_current_active_user
from typing import List, Optional
import datetime
from datetime import timezone, timedelta
from collections import defaultdict
from sqlalchemy import func, desc

# Self-healing schema patch: backfill columns that were added to the ORM
# model after some installs had already created the ``users`` table.
# Runs once at module-import time (before the app serves any request) so
# ORM SELECTs for the new columns succeed on legacy databases.
# Wrapped in try/except so fresh installs (where ``Base.metadata.create_all``
# already creates the correct schema) and repeated imports are unaffected.
try:
    from sqlalchemy import inspect as _sa_inspect, text as _sa_text
    from backend.db import session as _db_session
    _db_engine = getattr(_db_session, "engine", None)
    if _db_engine is None:
        raise RuntimeError("Database engine not initialized yet; skipping schema auto-migration.")

    with _db_engine.begin() as _migration_conn:
        _insp = _sa_inspect(_migration_conn)
        if _insp.has_table('users'):
            _cols = {c['name'] for c in _insp.get_columns('users')}
            if 'mcp_access_info' not in _cols:
                _migration_conn.execute(_sa_text("ALTER TABLE users ADD COLUMN mcp_access_info JSON"))
            if 'ttv_binding_model_name' not in _cols:
                _migration_conn.execute(_sa_text("ALTER TABLE users ADD COLUMN ttv_binding_model_name VARCHAR"))
            if 'ttv_models_config' not in _cols:
                _migration_conn.execute(_sa_text("ALTER TABLE users ADD COLUMN ttv_models_config JSON"))
except Exception:
    # Non-fatal: log at debug via logging if available, but never block boot.
    import logging as _mig_log
    _mig_log.getLogger(__name__).debug("Schema auto-migration skipped (non-fatal).", exc_info=True)

users_router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
    dependencies=[Depends(get_current_active_user)]
)

def _project_user_public(user: DBUser) -> UserPublic:
    """
    Transforms a DBUser ORM object into a completely decoupled, flat UserPublic model.
    This guarantees that the JSON serializer never accesses lazy-loaded ORM relationships
    (discussions, notes, memories) that cause huge payload warning loops.
    """
    return UserPublic(
        id=user.id,
        username=user.username,
        icon=user.icon,
        is_active=user.is_active,
        is_admin=getattr(user, "is_admin", False) or False,
        is_moderator=getattr(user, "is_moderator", False) or False,
        status=user.status,
        created_at=user.created_at
    )

@users_router.get("/search", response_model=List[UserPublic])
def search_for_users(
    q: str = Query(..., min_length=2, max_length=50),
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Searches for users.
    - If the query is a partial match, it returns only users who have enabled searchability.
    - If the query is an exact username match, it returns that user regardless of their searchability setting.
    - Excludes the current user from results.
    """
    search_term = f"%{q}%"

    users = db.query(DBUser).filter(
        DBUser.id != current_user.id,
        or_(
            DBUser.username == q,
            and_(
                DBUser.is_searchable == True,
                DBUser.username.ilike(search_term)
            )
        )
    ).limit(10).all()

    return [_project_user_public(u) for u in users]


@users_router.get("/mention_search", response_model=List[UserPublic])
def search_for_mentions(
    q: Optional[str] = Query(default="", max_length=50),
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Searches for users to mention.
    Returns users whose username matches the query and are searchable.
    Excludes the current user.
    """
    query_str = (q or "").strip()
    search_term = f"{query_str}%" if query_str else "%"
    users = db.query(DBUser).filter(
        DBUser.id != current_user.id,
        DBUser.is_searchable == True,
        DBUser.username.ilike(search_term)
    ).limit(5).all()
    return [_project_user_public(u) for u in users]


@users_router.get("/me/accessible-mcps", response_model=List[UserMCPAccessInfo])
def get_my_accessible_mcps(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Fetch all MCP servers that the current user can actively access (Personal or System).
    """
    # Personal MCPs are owned by the user
    personal_mcps = db.query(DBMCP).filter(DBMCP.owner_user_id == current_user.id).all()
    
    # System MCPs explicitly granted to user via access info JSON (or all if system defaults to public)
    # We read the mcp_access_info column if it exists, otherwise we fallback to querying non-personal ones marked active.
    user_db = db.query(DBUser).filter(DBUser.id == current_user.id).first()
    accessible_system_mcp_ids = set()
    
    mcp_access_info = getattr(user_db, "mcp_access_info", None) if user_db else None
    if isinstance(mcp_access_info, list):
        for m in mcp_access_info:
            if isinstance(m, dict) and "id" in m:
                accessible_system_mcp_ids.add(m["id"])

    system_mcps = db.query(DBMCP).filter(
        DBMCP.owner_user_id.is_(None),
        DBMCP.active == True
    ).all()

    results = []
    for mcp in personal_mcps:
        results.append(UserMCPAccessInfo(
            id=int(mcp.id),
            name=str(mcp.name),
            display_name=mcp.display_name,
            description=mcp.description,
            icon=mcp.icon,
            is_personal=True
        ))
        
    for mcp in system_mcps:
        # If there's an explicit access whitelist configured, adhere to it
        if accessible_system_mcp_ids and mcp.id not in accessible_system_mcp_ids:
            continue
            
        results.append(UserMCPAccessInfo(
            id=int(mcp.id),
            name=str(mcp.name),
            display_name=mcp.display_name,
            description=mcp.description,
            icon=mcp.icon,
            is_personal=False
        ))

    return results


@users_router.get("/me/stats", response_model=UserStats)
def get_current_user_personal_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Admin-parity personal statistics for the logged-in user.

    Returns exactly the ``UserStats`` shape the admin per-user modal sees, but
    every query is hard-scoped to ``current_user.id`` so one account can only
    ever read its own telemetry. This is the single source of truth shared by
    the on-screen dashboard and ``/me/stats/export``.
    """
    from backend.db.models.generation_metric import (
        GenerationMetric, calculate_co2_equivalents, KWH_PER_TOKEN, CO2_G_PER_KWH,
    )
    from backend.db.models.api_key import OpenAIAPIKey
    from backend.models.admin import SourceConsumptionBreakdown

    now = datetime.datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    cutoff_7d = now - timedelta(days=7)
    uid = current_user.id

    def _norm_dt(value):
        if value is None:
            return now
        if isinstance(value, str):
            try:
                return datetime.datetime.fromisoformat(value)
            except ValueError:
                return now
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    # ── Windowed rows (single fetch, aggregated in Python) ──
    rows = db.query(GenerationMetric).filter(
        GenerationMetric.user_id == uid,
        GenerationMetric.created_at >= cutoff,
    ).all()

    daily_tokens = defaultdict(int)
    daily_prompt = defaultdict(int)
    daily_completion = defaultdict(int)
    daily_gens = defaultdict(int)
    daily_webui = defaultdict(int)
    daily_api = defaultdict(int)
    weekday_counts = defaultdict(int)
    model_totals = defaultdict(lambda: {"model_name": "", "total_tokens": 0, "count": 0})

    window_tokens = 0
    window_prompt = 0
    window_completion = 0
    webui_tokens = api_tokens = webui_reqs = api_reqs = 0

    for r in rows:
        pt = int(r.prompt_tokens or 0)
        ct = int(r.completion_tokens or 0)
        tt = int(r.total_tokens or (pt + ct))
        dt = _norm_dt(r.created_at)
        day = dt.strftime("%Y-%m-%d")
        daily_tokens[day] += tt
        daily_prompt[day] += pt
        daily_completion[day] += ct
        daily_gens[day] += 1
        weekday_counts[dt.weekday()] += 1
        window_tokens += tt
        window_prompt += pt
        window_completion += ct
        if (r.source or "chat") == "chat":
            daily_webui[day] += tt
            webui_tokens += tt
            webui_reqs += 1
        else:
            daily_api[day] += tt
            api_tokens += tt
            api_reqs += 1
        mname = r.model_name or "unknown"
        m = model_totals[mname]
        m["model_name"] = mname
        m["total_tokens"] += tt
        m["count"] += 1

    # ── Lifetime totals (independent of the window) ──
    lifetime = db.query(
        func.coalesce(func.sum(GenerationMetric.total_tokens), 0),
        func.coalesce(func.sum(GenerationMetric.prompt_tokens), 0),
        func.coalesce(func.sum(GenerationMetric.completion_tokens), 0),
    ).filter(GenerationMetric.user_id == uid).first()
    lifetime_tokens = int((lifetime[0] if lifetime else 0) or 0)
    lifetime_prompt = int((lifetime[1] if lifetime else 0) or 0)
    lifetime_completion = int((lifetime[2] if lifetime else 0) or 0)

    # ── Last-7d window ──
    seven = db.query(
        func.coalesce(func.sum(GenerationMetric.total_tokens), 0),
        func.count(GenerationMetric.id),
    ).filter(
        GenerationMetric.user_id == uid,
        GenerationMetric.created_at >= cutoff_7d,
    ).first()
    tokens_7d = int((seven[0] if seven else 0) or 0)
    gens_7d = int((seven[1] if seven else 0) or 0)
    tokens_30d = window_tokens
    gens_30d = sum(daily_gens.values())

    # ── Per-API-key consumption ──
    # The metering table does NOT carry a per-key foreign key, so token counts
    # cannot be attributed to an individual key. We therefore always return the
    # account's keys (name/prefix/status/last-used) so the dashboard can display
    # them, with token counters sourced from per-key attribution *only if* the
    # metering schema ever grows an ``api_key_id`` column. This keeps the field
    # schema-stable and never fabricates usage.
    api_key_usage = []
    user_keys = db.query(OpenAIAPIKey).filter(OpenAIAPIKey.user_id == uid).all()
    per_key_metrics = {}
    if user_keys and hasattr(GenerationMetric, "api_key_id"):
        key_metric_rows = db.query(
            GenerationMetric.api_key_id,
            func.coalesce(func.sum(GenerationMetric.total_tokens), 0),
            func.coalesce(func.sum(GenerationMetric.prompt_tokens), 0),
            func.coalesce(func.sum(GenerationMetric.completion_tokens), 0),
            func.count(GenerationMetric.id),
        ).filter(
            GenerationMetric.user_id == uid,
            GenerationMetric.api_key_id.isnot(None),
        ).group_by(GenerationMetric.api_key_id).all()
        for kid, tok, p_tok, c_tok, calls in key_metric_rows:
            per_key_metrics[kid] = (int(tok or 0), int(p_tok or 0), int(c_tok or 0), int(calls or 0))

    for k in user_keys:
        tok, p_tok, c_tok, calls = per_key_metrics.get(k.id, (0, 0, 0, 0))
        api_key_usage.append({
            "api_key_id": int(k.id),
            "name": getattr(k, "name", None) or f"Key #{k.id}",
            "key_prefix": getattr(k, "key_prefix", None) or "",
            "is_active": bool(getattr(k, "is_active", True)),
            "total_tokens": tok,
            "prompt_tokens": p_tok,
            "completion_tokens": c_tok,
            "calls": calls,
            "last_used_at": (
                _norm_dt(k.last_used_at).isoformat()
                if getattr(k, "last_used_at", None) else None
            ),
        })
    api_key_usage.sort(key=lambda x: (x["total_tokens"], x["is_active"]), reverse=True)

    def _series(source_map):
        return [{"date": d, "count": int(v)} for d, v in sorted(source_map.items())]

    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_mean = {weekday_names[i]: float(weekday_counts.get(i, 0)) for i in range(7)}

    total_reqs = webui_reqs + api_reqs
    sum_tokens = (webui_tokens + api_tokens) or window_tokens
    webui_ratio = round((webui_tokens / sum_tokens * 100.0), 1) if sum_tokens > 0 else 0.0
    api_ratio = round((api_tokens / sum_tokens * 100.0), 1) if sum_tokens > 0 else 0.0

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
        api_co2_g=round(api_tokens * KWH_PER_TOKEN * CO2_G_PER_KWH, 2),
    )

    # Lifetime energy/CO₂ derived from lifetime tokens so the carbon block
    # matches the lifetime token counter.
    lifetime_energy = lifetime_tokens * KWH_PER_TOKEN
    lifetime_co2 = lifetime_energy * CO2_G_PER_KWH

    top_models = sorted(model_totals.values(), key=lambda x: x["total_tokens"], reverse=True)[:10]

    # Tasks/day (window). ``tasks_per_day`` is REQUIRED → always supply it.
    from backend.db.models.db_task import DBTask
    task_rows = db.query(
        func.date(DBTask.created_at).label("d"),
        func.count(DBTask.id).label("c"),
    ).filter(
        DBTask.owner_user_id == uid,
        DBTask.created_at >= cutoff,
    ).group_by(func.date(DBTask.created_at)).all()
    tasks_per_day = [
        UserActivityStat(date=datetime.datetime.strptime(str(d), "%Y-%m-%d").date(), count=int(c or 0))
        for d, c in task_rows if d
    ]

    return UserStats(
        user_id=uid,
        username=current_user.username,
        tokens_last_7d=tokens_7d,
        tokens_last_30d=tokens_30d,
        generations_last_7d=gens_7d,
        generations_last_30d=gens_30d,
        total_tokens=lifetime_tokens,
        total_prompt_tokens=lifetime_prompt,
        total_completion_tokens=lifetime_completion,
        total_generations_30d=gens_30d,
        total_energy_kwh=round(lifetime_energy, 4),
        total_co2_g=round(lifetime_co2, 2),
        co2_equivalents=calculate_co2_equivalents(lifetime_co2),
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
        api_key_usage=api_key_usage,
    )

@users_router.get("/me/stats/export")
def export_current_user_stats(
    format: str = Query("xlsx", pattern="^(xlsx|html|docx|pdf)$"),
    days: int = Query(30, ge=1, le=365),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Export the *current* user's statistics in html/pdf/docx/xlsx.

    Mirrors the admin per-user export but is strictly scoped to
    ``current_user.id`` — a regular user can never request another account's
    report because the id is taken from the authenticated session, not a
    path/query parameter. Reuses ``get_current_user_personal_stats`` as the
    single source of truth so every format matches the on-screen dashboard.
    """
    report = get_current_user_personal_stats(days=days, current_user=current_user, db=db)
    data = report.model_dump() if hasattr(report, "model_dump") else dict(report)

    import io as _io
    from datetime import datetime as _dt
    from fastapi import Response as _Resp

    stamp = _dt.now().strftime("%Y-%m-%d %H:%M")
    filename_base = f"my_stats_{current_user.username}_{_dt.now().strftime('%Y%m%d_%H%M%S')}"
    title = f"My Statistics — {current_user.username}"
    subtitle = (
        f"Account: {current_user.username} · Window: last {days} day(s) · "
        f"Generated: {stamp}"
    )

    def _num(n):
        try:
            return f"{int(n):,}"
        except Exception:
            return str(n)

    sb = data.get("source_breakdown") or {}
    tokens_per_day = data.get("tokens_per_day") or []
    top_models = data.get("top_models") or []
    api_key_usage = data.get("api_key_usage") or []

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
        key_rows_html = "".join(
            f"<tr><td>{k.get('name','')}</td><td>{k.get('key_prefix','')}</td>"
            f"<td>{_num(k.get('total_tokens',0))}</td><td>{_num(k.get('calls',0))}</td>"
            f"<td>{'Yes' if k.get('is_active') else 'No'}</td></tr>"
            for k in api_key_usage
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
<h2>Tokens per day</h2>
<table><thead><tr><th>Date</th><th>Tokens</th></tr></thead>
<tbody>{rows or '<tr><td colspan="2">No data</td></tr>'}</tbody></table>
<h2>Top models</h2>
<table><thead><tr><th>Model</th><th>Tokens</th><th>Calls</th></tr></thead>
<tbody>{model_rows or '<tr><td colspan="3">No data</td></tr>'}</tbody></table>
<h2>Usage by API key</h2>
<table><thead><tr><th>Key</th><th>Prefix</th><th>Tokens</th><th>Calls</th><th>Active</th></tr></thead>
<tbody>{key_rows_html or '<tr><td colspan="5">No API key usage recorded.</td></tr>'}</tbody></table>
</body></html>"""

    if format == "html":
        return _Resp(
            content=_build_html().encode("utf-8"),
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.html"'},
        )

    try:
        from backend.routers.files import (
            md2_to_html, html_to_docx_bytes, md_to_pdf_bytes, html_to_pdf_bytes,
        )
    except Exception:
        md2_to_html = html_to_docx_bytes = md_to_pdf_bytes = html_to_pdf_bytes = None

    if format == "docx":
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

                if chart_items:
                    doc.add_heading("Charts", level=2)
                    for c_title, c_png in chart_items:
                        doc.add_heading(c_title, level=3)
                        stream = _io.BytesIO(c_png)
                        stream.seek(0)
                        try:
                            doc.add_picture(stream, width=Inches(6.3))
                        except Exception:
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
                raise HTTPException(status_code=501, detail="DOCX export is unavailable.")
            content = html_to_docx_bytes(_build_html())

        return _Resp(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.docx"'},
        )

    if format == "pdf":
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
                    topMargin=14 * mm, bottomMargin=14 * mm, title=title,
                )
                styles = getSampleStyleSheet()
                body_style = ParagraphStyle("UsrSub", parent=styles["Normal"], fontSize=8.5,
                                            textColor=rl_colors.HexColor("#6b7280"))
                h2_style = ParagraphStyle("UsrH2", parent=styles["Heading2"], fontSize=12,
                                          spaceBefore=10, spaceAfter=4)
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
                page_width = A4[0] - 32 * mm
                for c_title, c_png in chart_items:
                    story.append(Paragraph(c_title, h2_style))
                    try:
                        img = RLImage(_io.BytesIO(c_png))
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
                content = None

        if content is None:
            if html_to_pdf_bytes is None and md_to_pdf_bytes is None:
                raise HTTPException(status_code=501, detail="PDF export is unavailable.")
            html = _build_html()
            content = html_to_pdf_bytes(html) if html_to_pdf_bytes else md_to_pdf_bytes(html)

        return _Resp(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.pdf"'},
        )

    # ---- XLSX ----
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.chart import BarChart, PieChart, Reference

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

    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = title
    ws["A1"].font = _TITLE_FONT
    ws["A2"] = subtitle
    ws["A2"].font = _SUB_FONT
    ws.merge_cells("A1:D1")
    ws.merge_cells("A2:D2")

    ws["A4"] = "Key Metrics"
    ws["A4"].font = Font(bold=True, size=13)
    ws["A5"] = "Metric"
    ws["B5"] = "Value"
    _style_header(ws, 5, 2)
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
    r = 5
    for label, value in metrics:
        r += 1
        ws.cell(row=r, column=1, value=label)
        ws.cell(row=r, column=2, value=value)
    _style_body(ws, 6, r, 2, right_cols=(2,))
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 24

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
        pie = PieChart()
        pie.title = "WebUI vs API token share"
        pdata = Reference(ws, min_col=2, min_row=split_label_row + 1, max_row=split_label_row + 3)
        plabels = Reference(ws, min_col=1, min_row=split_label_row + 2, max_row=split_label_row + 3)
        pie.add_data(pdata, titles_from_data=True)
        pie.set_categories(plabels)
        pie.height = 7
        pie.width = 11
        ws.add_chart(pie, "D5")

    ws2 = wb.create_sheet("Timeline")
    ws2["A1"] = "Tokens per day"
    ws2["A1"].font = Font(bold=True, size=13)
    headers = ["Date", "Tokens"]
    for i, h in enumerate(headers, start=1):
        ws2.cell(row=3, column=i, value=h)
    _style_header(ws2, 3, len(headers))
    row_idx = 4
    for t in tokens_per_day:
        ws2.cell(row=row_idx, column=1, value=str(t.get("date")))
        ws2.cell(row=row_idx, column=2, value=int(t.get("count", 0)))
        row_idx += 1
    last_row = row_idx - 1
    if last_row >= 4:
        _style_body(ws2, 4, last_row, len(headers), right_cols=(2,))
        chart = BarChart()
        chart.type = "col"
        chart.title = f"Tokens per day — {current_user.username}"
        chart.y_axis.title = "Tokens"
        chart.x_axis.title = "Date"
        data_ref = Reference(ws2, min_col=2, min_row=3, max_row=last_row)
        cats_ref = Reference(ws2, min_col=1, min_row=4, max_row=last_row)
        chart.add_data(data_ref, titles_from_data=True)
        chart.set_categories(cats_ref)
        chart.height = 9
        chart.width = 24
        ws2.add_chart(chart, "D3")
    for col, w in zip("AB", (14, 12)):
        ws2.column_dimensions[col].width = w

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
    for col, w in zip("ABC", (28, 14, 12)):
        ws3.column_dimensions[col].width = w

    ws4 = wb.create_sheet("API Keys")
    ws4["A1"] = "Usage by API key"
    ws4["A1"].font = Font(bold=True, size=13)
    k_headers = ["Key", "Prefix", "Tokens", "Prompt", "Completion", "Calls", "Active"]
    for i, h in enumerate(k_headers, start=1):
        ws4.cell(row=3, column=i, value=h)
    _style_header(ws4, 3, len(k_headers))
    kr = 4
    for k in api_key_usage:
        ws4.cell(row=kr, column=1, value=k.get("name", ""))
        ws4.cell(row=kr, column=2, value=k.get("key_prefix", ""))
        ws4.cell(row=kr, column=3, value=int(k.get("total_tokens", 0)))
        ws4.cell(row=kr, column=4, value=int(k.get("prompt_tokens", 0)))
        ws4.cell(row=kr, column=5, value=int(k.get("completion_tokens", 0)))
        ws4.cell(row=kr, column=6, value=int(k.get("calls", 0)))
        ws4.cell(row=kr, column=7, value="Yes" if k.get("is_active") else "No")
        kr += 1
    k_last = kr - 1
    if k_last >= 4:
        _style_body(ws4, 4, k_last, len(k_headers), right_cols=(3, 4, 5, 6))
    for col, w in zip("ABCDEFG", (28, 14, 14, 12, 14, 10, 10)):
        ws4.column_dimensions[col].width = w

    bio = _io.BytesIO()
    wb.save(bio)
    return _Resp(
        content=bio.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename_base}.xlsx"'},
    )


@users_router.get("/{username}", response_model=UserProfileResponse)
def get_user_profile(
    username: str,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Fetches a user's public profile along with the relationship
    status relative to the current authenticated user.
    """
    # Resolve 'me' keyword to current user's username
    target_username = current_user.username if username == "me" else username

    target_user = db.query(DBUser).filter(DBUser.username == target_username).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    is_following = db.query(exists().where(and_(
        follows_table.c.follower_id == current_user.id,
        follows_table.c.following_id == target_user.id
    ))).scalar()

    friendship = get_friendship_record(db, int(current_user.id), int(target_user.id))
    friendship_status = friendship.status if friendship else None

    return UserProfileResponse(
        user=_project_user_public(target_user),
        relationship={
            "is_following": bool(is_following),
            "friendship_status": friendship_status
        }
    )