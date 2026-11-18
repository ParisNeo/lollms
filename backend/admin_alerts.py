"""
Centralised operational alerting for administrators.

This module provides a small, dependency-light service used across the backend
to raise durable, deduplicated admin alerts for things like token overconsumption
and system incidents. Alerts are persisted (:class:`AdminAlert`) and optionally
pushed live to connected admins via the WebSocket manager using the
``admin_alert`` event type.

Design goals:
  * **Fail-safe**: raising an alert must never break the caller (generation,
    startup, scheduling). Every public function swallows its own errors.
  * **Deduplicated**: a repeated condition bumps an existing open row instead of
    spawning duplicates; severity only ever escalates upward automatically.
  * **Self-bootstrapping**: ``ensure_schema`` lazily creates the table and seeds
    threshold settings so the feature works even on an un-migrated database.
"""
import datetime
import json
import logging
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db.models.admin_alert import AdminAlert

logger = logging.getLogger(__name__)

# Default threshold settings inserted lazily so the alerting feature works even
# on databases created before the settings/table migration ran.
_DEFAULT_ALERT_SETTINGS = {
    "admin_alerts_enabled": (True, "boolean"),
    "alert_token_user_daily_limit": (0, "integer"),
    "alert_token_user_daily_critical": (0, "integer"),
    "alert_token_recent_burst_tokens": (0, "integer"),
    "alert_token_burst_window_minutes": (15, "integer"),
    "alert_token_system_daily_limit": (0, "integer"),
    "alert_token_single_generation": (0, "integer"),
    "alert_scan_interval_minutes": (15, "integer"),
}

_schema_ready = False


def ensure_schema(db: Session) -> None:
    """
    Idempotently create the ``admin_alerts`` table and seed default settings.

    Runs at most cheaply once per process. Any failure is swallowed (the caller
    has its own try/except); this is a best-effort bootstrap so the feature does
    not depend on the migration having run.
    """
    global _schema_ready
    if _schema_ready:
        return
    try:
        # Create the table if this database predates it.
        AdminAlert.__table__.create(bind=db.get_bind(), checkfirst=True)

        # Seed default settings rows when absent, stored in the same JSON shape
        # used by GlobalConfig so the settings loader reads them transparently.
        from backend.db.models.config import GlobalConfig

        existing_keys = {row[0] for row in db.query(GlobalConfig.key).all()}
        added = False
        for key, (value, type_) in _DEFAULT_ALERT_SETTINGS.items():
            if key in existing_keys:
                continue
            db.add(GlobalConfig(
                key=key,
                value=json.dumps({"value": value, "type": type_}),
                category="Admin Alerts",
            ))
            added = True
        if added:
            db.commit()
        _schema_ready = True
    except Exception as exc:  # pragma: no cover - bootstrap best effort
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("Admin alert schema bootstrap skipped: %s", exc)


# Severity ordering for escalation of an existing open alert.
SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}


def _broadcast(alert_dict: dict) -> None:
    """Best-effort live push to connected admins."""
    try:
        from backend.ws_manager import manager
        manager.broadcast_sync({"type": "admin_alert", "data": alert_dict})
    except Exception:
        # Never let a socket failure surface to the caller.
        pass


def emit_alert(
    db: Session,
    *,
    dedupe_key: str,
    category: str,
    severity: str,
    title: str,
    message: Optional[str] = None,
    related_user_id: Optional[int] = None,
    related_username: Optional[str] = None,
    metadata: Optional[dict] = None,
    push: bool = True,
) -> Optional[AdminAlert]:
    """
    Create or refresh an admin alert. Never raises.

    Deduplication: if an *unacknowledged* alert with the same ``dedupe_key``
    exists, it is updated in place (occurrence++ , last_seen=now, severity
    escalated upward) instead of inserting a duplicate row.

    Returns the affected ``AdminAlert`` on success, or ``None`` on any failure.
    """
    if severity not in SEVERITY_RANK:
        severity = "warning"

    try:
        ensure_schema(db)
        now = datetime.datetime.now(datetime.timezone.utc)

        existing = (
            db.query(AdminAlert)
            .filter(AdminAlert.dedupe_key == dedupe_key, AdminAlert.acknowledged.is_(False))
            .first()
        )

        metadata_json = json.dumps(metadata) if metadata else None

        if existing:
            existing.occurrence_count = (existing.occurrence_count or 0) + 1
            existing.last_seen_at = now
            # Escalate severity upward only (never downgrade an open alert).
            if SEVERITY_RANK.get(severity, 1) > SEVERITY_RANK.get(existing.severity, 1):
                existing.severity = severity
            if title:
                existing.title = title
            if message is not None:
                existing.message = message
            if metadata_json is not None:
                existing.metadata_json = metadata_json
            if related_user_id is not None:
                existing.related_user_id = related_user_id
            if related_username is not None:
                existing.related_username = related_username
            db.commit()
            alert = existing
        else:
            alert = AdminAlert(
                dedupe_key=dedupe_key,
                category=category,
                severity=severity,
                title=title,
                message=message,
                related_user_id=related_user_id,
                related_username=related_username,
                metadata_json=metadata_json,
                occurrence_count=1,
                first_seen_at=now,
                last_seen_at=now,
                acknowledged=False,
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)

        if push:
            _broadcast(alert.to_dict())
        return alert
    except Exception as exc:  # pragma: no cover - alerting must not break flow
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("emit_alert(%s) failed: %s", dedupe_key, exc)
        return None


# ── Convenience wrappers for common incident categories ────────────────────

def emit_system_incident(db: Session, title: str, message: str,
                         severity: str = "warning", subtitle: str = "") -> Optional[AdminAlert]:
    """A generic system incident (startup step failure, watchdog trip, etc.)."""
    key = f"system_incident:{subtitle or title}".lower().replace(" ", "_")[:120]
    return emit_alert(
        db, dedupe_key=key, category="system", severity=severity,
        title=title, message=message,
    )


def emit_security_incident(db: Session, title: str, message: str,
                           severity: str = "critical", subtitle: str = "") -> Optional[AdminAlert]:
    """A security-relevant event (auth anomaly, suspicious activity, etc.)."""
    key = f"security:{subtitle or title}".lower().replace(" ", "_")[:120]
    return emit_alert(
        db, dedupe_key=key, category="security", severity=severity,
        title=title, message=message,
    )


def emit_task_failure(db: Session, task_name: str, error: str,
                      owner: Optional[str] = None) -> Optional[AdminAlert]:
    """A background task that ended in failure."""
    key = f"task_failure:{task_name}".lower().replace(" ", "_")[:120]
    return emit_alert(
        db, dedupe_key=key, category="task", severity="warning",
        title=f"Task failed: {task_name}",
        message=(error or "")[:2000],
        related_username=owner,
    )


# ── Token-consumption scanning ─────────────────────────────────────────────

def _get_int_setting(settings_obj, key: str, default: int) -> int:
    try:
        raw = settings_obj.get(key, default)
        return int(raw)
    except (TypeError, ValueError):
        return default


def check_token_consumption(db: Session, _unused_settings=None) -> dict:
    """
    Scan recent generation metrics and raise alerts for overconsumption.

    Checks (each only fires when its threshold setting is > 0):
      * Per-user 24h tokens  → warning at ``alert_token_user_daily_limit``,
                               critical at ``alert_token_user_daily_critical``.
      * Per-user recent burst → ``alert_token_recent_burst_tokens`` within
                               ``alert_token_burst_window_minutes``.
      * Platform-wide 24h     → ``alert_token_system_daily_limit``.

    Returns a small summary dict (counts of alerts raised per kind).

    The ``_unused_settings`` parameter is accepted for backward compatibility
    with older callers that passed ``db, settings`` positionally. Settings are
    always read from :mod:`backend.settings` inside this function.
    """
    from backend.db.models.generation_metric import (
        GenerationMetric, KWH_PER_TOKEN, CO2_G_PER_KWH,
    )

    ensure_schema(db)

    now = datetime.datetime.now(datetime.timezone.utc)
    day_ago = now - datetime.timedelta(hours=24)

    result = {"user_alerts": 0, "system_alerts": 0}

    try:
        from backend.settings import settings as settings_obj
    except Exception:
        settings_obj = None

    if settings_obj is not None and not bool(settings_obj.get("admin_alerts_enabled", True)):
        return result

    # ── Per-user 24h consumption ──
    user_warn = _get_int_setting(settings_obj, "alert_token_user_daily_limit", 0) if settings_obj else 0
    user_crit = _get_int_setting(settings_obj, "alert_token_user_daily_critical", 0) if settings_obj else 0

    if user_warn > 0 or user_crit > 0:
        rows = (
            db.query(
                GenerationMetric.user_id,
                GenerationMetric.username,
                func.coalesce(func.sum(GenerationMetric.total_tokens), 0).label("tok"),
            )
            .filter(
                GenerationMetric.created_at >= day_ago,
                GenerationMetric.user_id.isnot(None),
            )
            .group_by(GenerationMetric.user_id, GenerationMetric.username)
            .all()
        )
        for user_id, username, tokens in rows:
            tokens = int(tokens or 0)
            severity = None
            if user_crit > 0 and tokens >= user_crit:
                severity = "critical"
            elif user_warn > 0 and tokens >= user_warn:
                severity = "warning"
            if not severity:
                continue
            energy = tokens * KWH_PER_TOKEN
            co2 = energy * CO2_G_PER_KWH
            key = f"user_token_daily:{user_id}:{severity}"
            emit_alert(
                db,
                dedupe_key=key,
                category="tokens",
                severity=severity,
                title=f"High token usage by {username or ('user #' + str(user_id))}",
                message=(
                    f"{tokens:,} tokens in the last 24h "
                    f"(~{energy:.3f} kWh, ~{co2:.1f} g CO2)."
                ),
                related_user_id=user_id,
                related_username=username,
                metadata={"tokens_24h": tokens, "threshold": user_crit if severity == "critical" else user_warn},
            )
            result["user_alerts"] += 1

    # ── Per-user recent burst ──
    burst_tokens = _get_int_setting(settings_obj, "alert_token_recent_burst_tokens", 0) if settings_obj else 0
    burst_window = _get_int_setting(settings_obj, "alert_token_burst_window_minutes", 15) if settings_obj else 15
    if burst_tokens > 0 and burst_window > 0:
        window_start = now - datetime.timedelta(minutes=burst_window)
        rows = (
            db.query(
                GenerationMetric.user_id,
                GenerationMetric.username,
                func.coalesce(func.sum(GenerationMetric.total_tokens), 0).label("tok"),
            )
            .filter(
                GenerationMetric.created_at >= window_start,
                GenerationMetric.user_id.isnot(None),
            )
            .group_by(GenerationMetric.user_id, GenerationMetric.username)
            .all()
        )
        for user_id, username, tokens in rows:
            tokens = int(tokens or 0)
            if tokens < burst_tokens:
                continue
            key = f"user_token_burst:{user_id}"
            emit_alert(
                db,
                dedupe_key=key,
                category="tokens",
                severity="warning",
                title=f"Token burst from {username or ('user #' + str(user_id))}",
                message=(
                    f"{tokens:,} tokens in the last {burst_window} min "
                    f"(threshold {burst_tokens:,})."
                ),
                related_user_id=user_id,
                related_username=username,
                metadata={"tokens_window": tokens, "window_minutes": burst_window},
            )
            result["user_alerts"] += 1

    # ── Platform-wide 24h ──
    system_limit = _get_int_setting(settings_obj, "alert_token_system_daily_limit", 0) if settings_obj else 0
    if system_limit > 0:
        total = db.query(func.coalesce(func.sum(GenerationMetric.total_tokens), 0)).filter(
            GenerationMetric.created_at >= day_ago
        ).scalar()
        total = int(total or 0)
        if total >= system_limit:
            emit_alert(
                db,
                dedupe_key="system_token_daily",
                category="tokens",
                severity="critical",
                title="Platform-wide token budget exceeded",
                message=f"{total:,} tokens across all users in the last 24h (limit {system_limit:,}).",
                metadata={"tokens_24h": total, "limit": system_limit},
            )
            result["system_alerts"] += 1

    return result