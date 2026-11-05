# backend/discussion_manager.py
from typing import Any, Dict, List

from ascii_colors import trace_exception
from lollms_client import LollmsDataManager

from backend.personalities import (
    discover_global_handbags,
    discover_personal_handbags,
)
from backend.session import get_user_data_root, user_sessions


_DEFAULT_PERSONA_ICON = "🤖"


def get_user_discussion_manager(username: str) -> LollmsDataManager:
    """
    Creates a new LollmsDataManager instance for a given user for each request.
    This ensures that each request (e.g., from a different browser tab) has an
    isolated discussion management context, preventing state mingling.
    """
    user_data_path = get_user_data_root(username)
    db_path = user_data_path / "discussions.db"
    db_url = f"sqlite:///{db_path.resolve()}"
    manager = LollmsDataManager(db_path=db_url)
    return manager


def _persona_id(scope: str, owner: str | None, handbag_name: str) -> str:
    """Deterministic, stable persona identity keyed by (scope, owner, handbag_name)."""
    return f"{scope}:{owner or ''}:{handbag_name}"


def _normalize_persona(dto: Dict[str, Any]) -> Dict[str, Any]:
    """Map a handbag DTO to the discussion-list persona view model."""
    scope = dto.get("scope", "global")
    owner = dto.get("owner")
    handbag_name = dto.get("handbag_name") or dto.get("name") or ""
    return {
        "id": _persona_id(scope, owner, handbag_name),
        "handbag_name": handbag_name,
        "name": dto.get("name") or handbag_name,
        "icon": dto.get("icon") or _DEFAULT_PERSONA_ICON,
        "scope": scope,
        "owner": owner,
    }


def get_user_personas(username: str) -> List[Dict[str, Any]]:
    """
    Canonical, deduplicated, icon-bearing persona list for the discussion list.

    Filesystem-only (post-bootstrap handbags are the source of truth). Never
    touches the DB and never raises: a failure in one source is logged and
    skipped so a corrupted handbag folder cannot break the discussion endpoint.
    """
    if not username:
        return []

    dedup: Dict[str, Dict[str, Any]] = {}

    sources = []
    try:
        sources.append(discover_global_handbags)
    except Exception as exc:
        trace_exception(exc)
    try:
        sources.append(
            lambda: discover_personal_handbags(username, username, "personal")
        )
    except Exception as exc:
        trace_exception(exc)

    for discover in sources:
        try:
            for dto in discover():
                persona = _normalize_persona(dto)
                if persona["handbag_name"]:
                    dedup[persona["id"]] = persona
        except Exception as exc:
            trace_exception(exc)
            continue

    return sorted(
        dedup.values(),
        key=lambda p: (p["scope"] != "personal", (p["name"] or "").lower()),
    )