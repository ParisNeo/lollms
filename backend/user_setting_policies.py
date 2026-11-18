"""
Admin-controlled policy engine for user-managed settings.

Purpose
-------
Lets an administrator decide, per user-facing setting:

    * ``user_editable``: may regular users change this setting themselves?
    * ``force_value``:   a concrete value the admin pins for EVERY user.
                         When set, users cannot change it and the value is
                         authoritative everywhere (read + write).

Design
------
Policies live as a single JSON document in the ``global_configs`` table under
the key ``user_setting_policies`` so they survive restarts and stay in sync
across worker processes (each value is re-read from the DB on demand).

The canonical registry of *manageable* settings is derived from the ``User``
ORM model, minus a blocklist of identity / security / secret columns that must
never be exposed through the settings-policy matrix. Grouping mirrors the
capability groups used by the chat UI so the admin panel and the user panel
stay visually consistent.

This module is deliberately dependency-light: it only imports stable symbols
(the ``User`` model and ``GlobalConfig``) and never touches router code.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, Optional, Tuple

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from backend.db.models.config import GlobalConfig
from backend.db.models.user import User

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Storage key & constants
# ──────────────────────────────────────────────────────────────────────────────
POLICY_CONFIG_KEY = "user_setting_policies"
POLICY_CATEGORY = "User Settings Policy"

# Columns that are NEVER part of the user-settings policy matrix.
# These are identity, credentials, security tokens, secrets, or system-managed
# bookkeeping that must only be changed by dedicated flows.
_NON_MANAGED_COLUMNS = frozenset({
    # identity / security
    "id", "username", "hashed_password", "external_id",
    "is_admin", "is_moderator", "is_active", "status",
    "created_at", "last_activity_at", "password_changed_at",
    "activation_token", "password_reset_token", "reset_token_expiry",
    "email_verification_code", "email_verification_code_expiry",
    "email_verification_token",
    "first_name", "family_name", "email", "birth_date", "icon",
    "total_logins", "first_login_done",
    # secrets / integration credentials
    "google_api_key", "google_cse_id", "mcp_access_info",
    # model / binding pointers (managed by dedicated studios, not the policy matrix)
    "lollms_model_name",
    "tti_binding_model_name", "iti_binding_model_name", "tti_models_config",
    "tts_binding_model_name", "tts_models_config",
    "stt_binding_model_name", "stt_models_config",
    "ttv_binding_model_name", "ttv_models_config",
    "safe_store_vectorizer", "active_personality_id", "active_voice_id",
    "last_discussion_id",
})

# Columns whose values are lists/objects (JSON columns) — surfaced separately in
# the admin UI so the operator knows free-form editing is expected.
_JSON_COLUMNS = frozenset({
    "herd_participants", "herd_precode_participants",
    "herd_postcode_participants", "herd_model_pool",
    "web_search_providers", "image_studio_generation_params",
    "tti_models_config", "tts_models_config", "stt_models_config", "ttv_models_config",
})

# Groups mirror ChatInput.vue ``capabilityGroupMeta`` plus a few core buckets.
# Every key in _GROUP_MEMBERSHIP must be a managed column; unknown columns fall
# into the ``misc`` group at the end so nothing is silently invisible.
_GROUP_ORDER: Tuple[Tuple[str, str], ...] = (
    ("conversation", "Conversation & Artefacts"),
    ("skills", "Skills"),
    ("memory", "Memory"),
    ("knowledge", "Knowledge & RAG"),
    ("images", "Images"),
    ("office", "Office Documents"),
    ("media", "Media Generation"),
    ("vision", "Vision & Automation"),
    ("tools", "Code & Tools"),
    ("advanced", "Orchestration"),
    ("diagnostics", "Streaming & Diagnostics"),
    ("lifestyle", "Lifestyle"),
    ("rag", "RAG Tuning"),
    ("appearance", "Appearance & Locale"),
    ("misc", "Other"),
)

_GROUP_MEMBERSHIP: Dict[str, str] = {
    # conversation
    "artefacts_enabled": "conversation",
    "auto_activate_artefacts": "conversation",
    "note_generation_enabled": "conversation",
    "inline_widgets_enabled": "conversation",
    "form_building_enabled": "conversation",
    "enable_books": "conversation",
    "chat_active": "conversation",
    # skills
    "skills_building_enabled": "skills",
    "skills_library_enabled": "skills",
    "enable_skill_editing": "skills",
    "enable_skillmaker": "skills",
    # memory
    "memory_enabled": "memory",
    "auto_memory_enabled": "memory",
    "enable_episodic_memory": "memory",
    "enable_deep_memory_pulling": "memory",
    "include_memory_date_in_context": "memory",
    "put_thoughts_in_context": "memory",
    # knowledge
    "prehydrate_rag": "knowledge",
    "enable_data_tools": "knowledge",
    # images
    "image_generation_enabled": "images",
    "image_editing_enabled": "images",
    "image_annotation_enabled": "images",
    "activate_generated_images": "images",
    "image_generation_system_prompt": "images",
    "image_studio_prompt": "images",
    "image_studio_negative_prompt": "images",
    "image_studio_image_size": "images",
    "image_studio_n_images": "images",
    "image_studio_seed": "images",
    "image_studio_generation_params": "images",
    "max_image_width": "images",
    "max_image_height": "images",
    "compress_images": "images",
    "image_compression_quality": "images",
    # office
    "powerpoint_enabled": "office",
    "word_enabled": "office",
    "excel_enabled": "office",
    "office_tools_enabled": "office",
    "enable_pdf": "office",
    # media
    "enable_generate_video": "media",
    "enable_edit_video": "media",
    "enable_generate_music": "media",
    "enable_edit_music": "media",
    "enable_synthesize_speech": "media",
    # vision
    "suppress_images": "vision",
    "enable_vlm_query": "vision",
    "enable_computer_use": "vision",
    # tools
    "enable_code_execution": "tools",
    "auto_approve_python": "tools",
    "allow_dynamic_tools": "tools",
    "enable_toolset_editing": "tools",
    "enable_toolsmith": "tools",
    "compact_workspace_tree": "tools",
    # advanced
    "orchestrator_mode": "advanced",
    "dynamic_effort": "advanced",
    "list_available_models": "advanced",
    "reasoning_activation": "advanced",
    "reasoning_effort": "advanced",
    "reasoning_summary": "advanced",
    "rlm_enabled": "advanced",
    # diagnostics
    "forward_artefact_chunks": "diagnostics",
    "enable_in_message_status": "diagnostics",
    "clean_reasoning_at_save": "diagnostics",
    "verbose": "diagnostics",
    "debug": "diagnostics",
    "debug_export": "diagnostics",
    # lifestyle
    "herd_mode_enabled": "lifestyle",
    "herd_participants": "lifestyle",
    "herd_precode_participants": "lifestyle",
    "herd_postcode_participants": "lifestyle",
    "herd_rounds": "lifestyle",
    "herd_dynamic_mode": "lifestyle",
    "herd_model_pool": "lifestyle",
    "scheduler_enabled": "lifestyle",
    "street_view_enabled": "lifestyle",
    "google_drive_enabled": "lifestyle",
    "google_calendar_enabled": "lifestyle",
    "google_gmail_enabled": "lifestyle",
    "fun_mode": "lifestyle",
    # rag tuning
    "rag_top_k": "rag",
    "max_rag_len": "rag",
    "rag_n_hops": "rag",
    "rag_min_sim_percent": "rag",
    "rag_use_graph": "rag",
    "rag_graph_response_type": "rag",
    "rag_retrieval_mode": "rag",
    "rag_dense_weight": "rag",
    "rag_bm25_weight": "rag",
    "rag_graph_weight": "rag",
    "rag_rrf_k": "rag",
    "default_rag_chunk_size": "rag",
    "default_rag_chunk_overlap": "rag",
    "default_rag_metadata_mode": "rag",
    # appearance & locale
    "message_font_size": "appearance",
    "ai_response_language": "appearance",
    "force_ai_response_language": "appearance",
    "show_token_counter": "appearance",
    "discussion_sorting_mode": "appearance",
    "discussion_sorting_order": "appearance",
    "first_page": "appearance",
    "auto_title": "appearance",
    # misc / profile-adjacent but safe to expose
    "preferred_name": "misc",
    "data_zone": "misc",
    "user_personal_info": "misc",
    "share_personal_info_with_llm": "misc",
    "coding_style_constraints": "misc",
    "programming_language_preferences": "misc",
    "tell_llm_os": "misc",
    "share_dynamic_info_with_llm": "misc",
    "receive_notification_emails": "misc",
    "is_searchable": "misc",
    "web_search_enabled": "misc",
    "web_search_providers": "misc",
    "web_search_deep_analysis": "misc",
    "llm_temperature": "misc",
    "llm_top_k": "misc",
    "llm_top_p": "misc",
    "llm_repeat_penalty": "misc",
    "llm_repeat_last_n": "misc",
}


# ──────────────────────────────────────────────────────────────────────────────
# Registry derivation
# ──────────────────────────────────────────────────────────────────────────────
def _column_python_type(column) -> str:
    """Coarse type name used by the admin UI to pick an input widget."""
    try:
        type_name = type(column.type).__name__.lower()
    except Exception:
        return "string"
    if "bool" in type_name:
        return "boolean"
    if "int" in type_name:
        return "integer"
    if "float" in type_name or "numeric" in type_name:
        return "float"
    if "json" in type_name:
        return "json"
    return "string"


def get_manageable_settings() -> Dict[str, Dict[str, Any]]:
    """
    Return the ordered registry of settings an admin may govern.

    Each entry::

        {
          "key": str,
          "label": str,          # human-friendly (derived from key)
          "type": str,           # boolean|integer|float|string|json
          "group": str,          # group id
          "group_label": str,    # group display name
          "nullable": bool,
        }
    """
    mapper = sa_inspect(User)
    registry: Dict[str, Dict[str, Any]] = {}

    group_labels = dict(_GROUP_ORDER)

    for column in mapper.columns:
        key = column.key
        if key in _NON_MANAGED_COLUMNS:
            continue

        col_type = _column_python_type(column)
        # JSON columns are surfaced even if listed, using the json widget.
        if key in _JSON_COLUMNS and col_type != "json":
            col_type = "json"

        group = _GROUP_MEMBERSHIP.get(key, "misc")
        registry[key] = {
            "key": key,
            "label": key.replace("_", " ").replace("enable ", "").strip().title(),
            "type": col_type,
            "group": group,
            "group_label": group_labels.get(group, group.title()),
            "nullable": bool(column.nullable),
        }

    return registry


def get_group_ordering() -> Tuple[Tuple[str, str], ...]:
    """Expose the group order for the UI to render deterministically."""
    return _GROUP_ORDER


# ──────────────────────────────────────────────────────────────────────────────
# Policy load / save
# ──────────────────────────────────────────────────────────────────────────────
def _default_policy_for_setting(_key: str) -> Dict[str, Any]:
    """Default: users may edit, nothing forced."""
    return {"user_editable": True, "force_value": None}


def load_policies(db: Session) -> Dict[str, Dict[str, Any]]:
    """
    Load the raw policy dict served/stored by the admin panel.

    Every manageable setting is guaranteed to be present: missing rows fall back
    to the permissive default. Unknown/legacy keys are preserved untouched.
    """
    raw: Dict[str, Any] = {}
    record = db.query(GlobalConfig).filter(GlobalConfig.key == POLICY_CONFIG_KEY).first()
    if record and record.value:
        try:
            parsed = json.loads(record.value)
            if isinstance(parsed, dict):
                raw = parsed
        except (json.JSONDecodeError, TypeError):
            logger.warning("Malformed '%s' config; using defaults.", POLICY_CONFIG_KEY)

    registry = get_manageable_settings()
    policies: Dict[str, Dict[str, Any]] = {}

    for key in registry:
        stored = raw.get(key)
        if isinstance(stored, dict):
            policies[key] = {
                "user_editable": bool(stored.get("user_editable", True)),
                "force_value": stored.get("force_value", None),
            }
        else:
            policies[key] = _default_policy_for_setting(key)

    # Preserve any stored keys that are not in the current registry (forward-compat).
    for key, stored in raw.items():
        if key not in policies and isinstance(stored, dict):
            policies[key] = stored

    return policies


def save_policies(db: Session, new_policies: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Persist a (possibly partial) policy dict, sanitising against the registry.

    Returns the fully-materialised stored policy dict.
    """
    if not isinstance(new_policies, dict):
        raise ValueError("Policies payload must be a JSON object.")

    registry = get_manageable_settings()
    current = load_policies(db)

    merged: Dict[str, Dict[str, Any]] = dict(current)
    for key, entry in new_policies.items():
        if not isinstance(entry, dict):
            continue
        # Only govern known settings; ignore stray keys to avoid poisoning config.
        if key not in registry:
            continue
        base = merged.get(key, _default_policy_for_setting(key))
        user_editable = entry.get("user_editable", base.get("user_editable", True))
        force_value = entry.get("force_value", base.get("force_value"))
        merged[key] = {
            "user_editable": bool(user_editable),
            "force_value": force_value,
        }

    record = db.query(GlobalConfig).filter(GlobalConfig.key == POLICY_CONFIG_KEY).first()
    serialized = json.dumps(merged)
    if record:
        record.value = serialized
        record.description = "Per-setting admin control over user-editable / forced values."
        record.category = POLICY_CATEGORY
    else:
        record = GlobalConfig(
            key=POLICY_CONFIG_KEY,
            value=serialized,
            description="Per-setting admin control over user-editable / forced values.",
            category=POLICY_CATEGORY,
        )
        db.add(record)
    db.commit()
    return merged


# ──────────────────────────────────────────────────────────────────────────────
# Enforcement helpers
# ──────────────────────────────────────────────────────────────────────────────
def coerce_forced_value(setting_key: str, raw_value: Any, expected_type: str) -> Any:
    """
    Best-effort coercion of an admin-supplied forced value to the setting type.
    Returns ``None`` when the value is empty/blank (meaning 'do not force').
    """
    if raw_value is None:
        return None
    if isinstance(raw_value, str) and raw_value.strip() == "":
        return None

    try:
        if expected_type == "boolean":
            if isinstance(raw_value, bool):
                return raw_value
            return str(raw_value).strip().lower() in ("1", "true", "yes", "on", "enabled")
        if expected_type == "integer":
            return int(raw_value)
        if expected_type == "float":
            return float(raw_value)
        if expected_type == "json":
            if isinstance(raw_value, (dict, list)):
                return raw_value
            return json.loads(raw_value)
        # string
        return str(raw_value)
    except (ValueError, TypeError, json.JSONDecodeError):
        logger.warning("Could not coerce forced value for %s to %s; ignoring.", setting_key, expected_type)
        return None


def sanitize_user_updates(
    db: Session,
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Filter an incoming user-preference update dict according to policy.

    Rules:
      * ``force_value`` set      → the admin value wins (incoming change dropped).
      * ``user_editable`` False  → the incoming change is dropped.
      * otherwise                → the incoming change is allowed through.
    """
    if not updates:
        return {}

    registry = get_manageable_settings()
    policies = load_policies(db)

    sanitized: Dict[str, Any] = {}
    for key, value in updates.items():
        # Unknown, unmanaged, or non-model fields are passed through so the
        # endpoint's own `hasattr` guard remains the final authority.
        policy = policies.get(key)
        if not policy or key not in registry:
            sanitized[key] = value
            continue

        force_value = policy.get("force_value")
        if force_value is not None:
            # Admin has pinned a value; never let the user override it here.
            continue
        if not policy.get("user_editable", True):
            continue
        sanitized[key] = value

    return sanitized


def apply_forced_values_to_user(db: Session, db_user: User) -> bool:
    """
    Overwrite the in-memory ``db_user`` with any admin-forced values.

    Returns ``True`` if at least one attribute was changed (caller may commit).
    """
    registry = get_manageable_settings()
    policies = load_policies(db)
    changed = False

    for key, policy in policies.items():
        force_value = policy.get("force_value")
        if force_value is None:
            continue
        if key not in registry:
            continue
        coerced = coerce_forced_value(key, force_value, registry[key]["type"])
        if coerced is None:
            continue
        if getattr(db_user, key, None) != coerced:
            setattr(db_user, key, coerced)
            changed = True

    return changed


def get_public_policy_summary(db: Session) -> Dict[str, Dict[str, Any]]:
    """
    Non-sensitive policy view for the current user's UI.

    Only reports whether a field is locked and, if forced, what the value is —
    never exposes other users' data. Used by the frontend to render disabled
    toggles and 'managed by admin' badges.
    """
    registry = get_manageable_settings()
    policies = load_policies(db)

    summary: Dict[str, Dict[str, Any]] = {}
    for key, policy in policies.items():
        if key not in registry:
            continue
        force_value = policy.get("force_value")
        summary[key] = {
            "user_editable": bool(policy.get("user_editable", True)) and force_value is None,
            "forced": force_value is not None,
            "force_value": force_value,
        }
    return summary