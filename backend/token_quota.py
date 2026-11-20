# backend/token_quota.py
"""
Per-user token quota resolution, usage accounting, and enforcement.

The quota system distinguishes *input* (prompt) tokens from *output*
(completion) tokens because they are not billed/consumed identically.

Resolution precedence for each dimension (input / output / period / enabled):
    1. Per-user override columns on ``User`` (when not NULL).
    2. Global defaults from ``settings`` (``token_quota_*``).

A value of ``0`` on a max dimension means "unlimited". A user with
``token_quota_exempt == True`` is never restricted. Admin/super-admin users are
also never restricted so they cannot lock themselves out.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db.models.generation_metric import GenerationMetric
from backend.settings import settings

VALID_PERIODS = ("daily", "weekly", "monthly")
DEFAULT_PERIOD = "monthly"


@dataclass(frozen=True)
class QuotaStatus:
    """Resolved, UI-facing snapshot of a user's quota for the current period."""
    enforced: bool
    exempt: bool
    period: str
    period_start: _dt.datetime
    period_end: _dt.datetime
    input_max: int  # 0 = unlimited
    output_max: int  # 0 = unlimited
    input_used: int
    output_used: int

    @property
    def input_remaining(self) -> Optional[int]:
        if self.input_max <= 0:
            return None
        return max(0, self.input_max - self.input_used)

    @property
    def output_remaining(self) -> Optional[int]:
        if self.output_max <= 0:
            return None
        return max(0, self.output_max - self.output_used)

    @property
    def input_exhausted(self) -> bool:
        return self.input_max > 0 and self.input_used >= self.input_max

    @property
    def output_exhausted(self) -> bool:
        return self.output_max > 0 and self.output_used >= self.output_max

    @property
    def exhausted(self) -> bool:
        return self.input_exhausted or self.output_exhausted


def _normalize_period(value: Optional[str]) -> str:
    if isinstance(value, str) and value.lower() in VALID_PERIODS:
        return value.lower()
    return DEFAULT_PERIOD


def _period_window(period: str, now: Optional[_dt.datetime] = None) -> Tuple[_dt.datetime, _dt.datetime]:
    """Return the [start, end) UTC window for the current period."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_dt.timezone.utc)

    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + _dt.timedelta(days=1)
    elif period == "weekly":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) - _dt.timedelta(days=now.weekday())
        end = start + _dt.timedelta(days=7)
    else:  # monthly
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
    return start, end


def _coerce_bool(value, default: bool = False) -> bool:
    """Coerce a DB-stored setting to a real bool.

    Settings may be stored as JSON booleans, ints (0/1), or strings
    (``"true"``/``"false"``). ``bool("false")`` is ``True`` in Python, so a naive
    cast could wrongly enable quotas. This normaliser guarantees the master
    switch stays OFF unless it is unambiguously truthy.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on", "enabled")
    return default


def _resolve_int(override_value: Optional[int], setting_key: str) -> int:
    if override_value is not None:
        try:
            return max(0, int(override_value))
        except (TypeError, ValueError):
            pass
    try:
        return max(0, int(settings.get(setting_key, 0) or 0))
    except (TypeError, ValueError):
        return 0


def resolve_effective_quota(user) -> Tuple[bool, bool, str, int, int]:
    """
    Resolve (enforced, exempt, period, input_max, output_max) for a user object.

    Admins are always exempt so a misconfigured quota can never lock the only
    administrator out of the system.
    """
    is_admin = bool(getattr(user, "is_admin", False))
    exempt = bool(getattr(user, "token_quota_exempt", False)) or is_admin

    enabled_override = getattr(user, "token_quota_enabled", None)
    if enabled_override is not None:
        enabled = _coerce_bool(enabled_override, default=False)
    else:
        enabled = _coerce_bool(settings.get("token_quota_enabled", False), default=False)

    period = _normalize_period(
        getattr(user, "token_quota_period", None)
        or settings.get("token_quota_period", DEFAULT_PERIOD)
    )

    input_max = _resolve_int(getattr(user, "token_quota_input_max", None), "token_quota_input_max")
    output_max = _resolve_int(getattr(user, "token_quota_output_max", None), "token_quota_output_max")

    return (enabled and not exempt, exempt, period, input_max, output_max)


def compute_usage(db: Session, user_id: int, start: _dt.datetime, end: _dt.datetime) -> Tuple[int, int]:
    """Sum prompt vs completion tokens consumed by a user in [start, end)."""
    row = db.query(
        func.coalesce(func.sum(GenerationMetric.prompt_tokens), 0),
        func.coalesce(func.sum(GenerationMetric.completion_tokens), 0),
    ).filter(
        GenerationMetric.user_id == user_id,
        GenerationMetric.created_at >= start,
        GenerationMetric.created_at < end,
    ).first()
    input_used = int(row[0] or 0) if row else 0
    output_used = int(row[1] or 0) if row else 0
    return input_used, output_used


def get_quota_status(db: Session, user, now: Optional[_dt.datetime] = None) -> QuotaStatus:
    """Build a full :class:`QuotaStatus` snapshot for the user's current period."""
    enforced, exempt, period, input_max, output_max = resolve_effective_quota(user)
    start, end = _period_window(period, now)
    input_used, output_used = compute_usage(db, user.id, start, end)
    return QuotaStatus(
        enforced=enforced,
        exempt=exempt,
        period=period,
        period_start=start,
        period_end=end,
        input_max=input_max,
        output_max=output_max,
        input_used=input_used,
        output_used=output_used,
    )


def build_exhausted_message(status: QuotaStatus) -> str:
    """Human-readable message informing the user their quota is exhausted."""
    reset_local = status.period_end
    reset_str = reset_local.strftime("%Y-%m-%d %H:%M UTC")
    exceeded = []
    if status.input_exhausted:
        exceeded.append(f"input tokens ({status.input_used:,}/{status.input_max:,})")
    if status.output_exhausted:
        exceeded.append(f"output tokens ({status.output_used:,}/{status.output_max:,})")
    detail = " and ".join(exceeded) if exceeded else "token quota"
    return (
        f"Your {status.period} token quota is exhausted: {detail}. "
        f"Your quota resets on {reset_str}."
    )


class TokenQuotaExceeded(Exception):
    """Raised when a user has no remaining quota for the requested operation."""

    def __init__(self, status: QuotaStatus):
        self.status = status
        self.message = build_exhausted_message(status)
        super().__init__(self.message)