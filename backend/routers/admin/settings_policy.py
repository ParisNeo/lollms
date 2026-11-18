# backend/routers/admin/settings_policy.py
"""
Admin Settings Policy control panel.

Exposes endpoints that let administrators decide, per user-settable field:

* whether the user may modify it (``locked``)
* whether the administrator pins it to a specific value (``forced`` + ``forced_value``)

The policy is stored globally in ``user_setting_policies`` and enforced inside
``backend/routers/auth.py:update_my_details`` and ``get_my_details``.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.db.models.settings_policy import UserSettingPolicy
from backend.models.settings_policy import (
    PolicyField,
    PolicyFieldState,
    SettingsPolicyResponse,
    SettingsPolicyUpdateRequest,
    UserPolicySummaryResponse,
)
from backend.models.user import UserAuthDetails, UserUpdate
from backend.session import get_current_active_user, get_current_admin_user

router = APIRouter(prefix="/settings-policy", tags=["Admin: Settings Policy"])

# Non-admin surface: reports which fields the current user is not allowed to
# change (and any forced value), so the UI can render locked toggles / badges.
# Mounted at app root by main.py, not under /api/admin.
public_router = APIRouter(prefix="/api/settings-policy", tags=["Settings Policy (Public)"])


@public_router.get("/me", response_model=UserPolicySummaryResponse)
async def get_my_settings_policy(
    db: Session = Depends(get_db),
    user: UserAuthDetails = Depends(get_current_active_user),
):
    """Return the effective policy for the current user: which fields are
    locked and which are admin-forced (with the pinned value).

    Only rows that actually restrict the user (``locked`` or ``forced``) are
    returned so the frontend can cheaply disable inputs without shipping the
    full catalog on every page load.
    """
    snapshot: Dict[str, PolicyFieldState] = {
        name: state
        for name, state in _snapshot_policies(db).items()
        if state.locked or state.forced
    }
    return UserPolicySummaryResponse(policies=snapshot)


# --------------------------------------------------------------------------- #
# Catalog of fields the administrator may govern.
# Derived from UserUpdate so the panel only ever exposes real, updatable fields.
# --------------------------------------------------------------------------- #
_FIELD_LABELS = {
    "preferred_name": "Preferred Name",
    "email": "Email",
    "first_name": "First Name",
    "family_name": "Family Name",
    "birth_date": "Birth Date",
    "icon": "Avatar Icon",
    "message_font_size": "Message Font Size",
    "first_page": "First Page",
    "ai_response_language": "AI Response Language",
    "force_ai_response_language": "Force AI Response Language",
    "fun_mode": "Fun Mode",
    "put_thoughts_in_context": "Put Thoughts in Context",
    "auto_title": "Auto Title",
    "show_token_counter": "Show Token Counter",
    "chat_active": "Chat Active",
    "reasoning_activation": "Reasoning Activation",
    "reasoning_effort": "Reasoning Effort",
    "reasoning_summary": "Reasoning Summary",
    "share_personal_info_with_llm": "Share Personal Info with LLM",
    "share_dynamic_info_with_llm": "Share Dynamic Info with LLM",
    "tell_llm_os": "Tell LLM the OS",
    "coding_style_constraints": "Coding Style Constraints",
    "programming_language_preferences": "Language Preferences",
    "data_zone": "Data Zone",
    "user_personal_info": "Personal Info",
    "llm_ctx_size": "LLM Context Size",
    "rag_top_k": "RAG Top-K",
    "max_rag_len": "Max RAG Length",
    "rag_n_hops": "RAG Hops",
    "rag_min_sim_percent": "RAG Min Similarity",
    "rag_use_graph": "RAG Use Graph",
    "default_rag_chunk_size": "Default Chunk Size",
    "default_rag_chunk_overlap": "Default Chunk Overlap",
    # ── Chat capability flags (users.<flag>) ──
    "artefacts_enabled": "Workspace Artefacts",
    "auto_activate_artefacts": "Auto-Activate Files",
    "note_generation_enabled": "AI Notes",
    "inline_widgets_enabled": "Inline Widgets",
    "form_building_enabled": "Interactive Forms",
    "enable_books": "Book Building",
    "skills_building_enabled": "Skill Building",
    "skills_library_enabled": "Skill Auto-Search",
    "enable_skill_editing": "Skill Editing",
    "enable_skillmaker": "Skill Maker",
    "memory_enabled": "Long-Term Memory",
    "auto_memory_enabled": "Auto-Dream Cycle",
    "enable_episodic_memory": "Episodic Memory",
    "enable_deep_memory_pulling": "Deep Memory Pull",
    "prehydrate_rag": "Pre-Hydrate RAG",
    "enable_data_tools": "Data Tools",
    "image_generation_enabled": "Image Generation",
    "image_editing_enabled": "Image Editing",
    "image_annotation_enabled": "Image Annotation",
    "activate_generated_images": "Activate Generated Images",
    "powerpoint_enabled": "PowerPoint",
    "word_enabled": "Word",
    "excel_enabled": "Excel",
    "office_tools_enabled": "Office Tools",
    "enable_pdf": "PDF Tools",
    "enable_generate_video": "Video Generation",
    "enable_edit_video": "Video Editing",
    "enable_generate_music": "Music Generation",
    "enable_edit_music": "Music Editing",
    "enable_synthesize_speech": "Text-to-Speech",
    "suppress_images": "Suppress Vision",
    "enable_vlm_query": "VLM Query Fallback",
    "enable_computer_use": "Computer Use",
    "enable_code_execution": "Code Execution",
    "auto_approve_python": "Auto-Approve Python",
    "allow_dynamic_tools": "Dynamic Tools",
    "enable_toolset_editing": "Toolset Editing",
    "enable_toolsmith": "Toolsmith",
    "compact_workspace_tree": "Compact Workspace Tree",
    "orchestrator_mode": "Orchestrator Mode",
    "dynamic_effort": "Dynamic Effort",
    "list_available_models": "Model Discovery",
    "forward_artefact_chunks": "Stream Artefact Chunks",
    "enable_in_message_status": "In-Message Status",
    "clean_reasoning_at_save": "Clean Reasoning",
    "verbose": "Verbose Telemetry",
    "debug": "Debug Toolset",
    "debug_export": "Debug Export",
    "herd_mode_enabled": "Herd Mode",
    "scheduler_enabled": "Task Scheduler",
    "street_view_enabled": "Street View",
}

_TYPE_OVERRIDES = {
    "message_font_size": "int",
    "llm_ctx_size": "int",
    "rag_top_k": "int",
    "max_rag_len": "int",
    "rag_n_hops": "int",
    "rag_min_sim_percent": "float",
    "default_rag_chunk_size": "int",
    "default_rag_chunk_overlap": "int",
    "reasoning_effort": "enum",
    "first_page": "enum",
}

_ENUM_CHOICES = {
    "reasoning_effort": ["low", "medium", "high", "max"],
    "first_page": ["feed", "chat", "last_discussion", "new_discussion"],
}


def _infer_category(name: str) -> str:
    """Group related fields by prefix for a cleaner UI."""
    if name.startswith(("image_", "tti_", "iti_")):
        return "Images"
    if name.startswith(("rag_", "default_rag_")):
        return "RAG & Retrieval"
    if name.startswith(("web_search", "street_view", "google_")):
        return "Web & Workspace"
    if name.startswith(("memory", "enable_episodic", "enable_deep_memory")):
        return "Memory"
    if name.startswith(("skills_", "enable_skill", "enable_toolsmith", "enable_code", "allow_dynamic")):
        return "Skills & Tools"
    if name.startswith(("enable_", "auto_", "artefacts_", "inline_widgets", "form_building", "note_generation")):
        return "Chat Capabilities"
    if name.startswith(("herd_", "orchestrator", "dynamic_effort", "list_available_models")):
        return "Orchestration"
    if name.startswith(("powerpoint_", "word_", "excel_", "office_tools")):
        return "Office"
    if name.startswith(("message_", "ai_response", "force_ai_response", "reasoning_")):
        return "Generation"
    if name.startswith(("preferred_", "first_", "family_", "email", "birth_", "icon")):
        return "Profile"
    if name.startswith(("lollms_model_name", "llm_")):
        return "Model & LLM"
    return "General"


def _build_field_catalog() -> List[PolicyField]:
    """Build the authoritative field catalog.

    The catalog is the UNION of:
      * every column reflected from the ``User`` ORM model (this is what actually
        captures the full set of chat capability flags — ``enable_code_execution``,
        ``artefacts_enabled``, ``auto_activate_artefacts``, ``enable_books``,
        ``preflight_rag`` … — which live on the DB row, not on ``UserUpdate``), and
      * ``UserUpdate.model_fields`` (so any user-editable field that is validated
        but not on the model still appears).

    A dedicated blocklist hides identity/security/secret columns so the panel
    only ever exposes genuinely governable settings.
    """
    from sqlalchemy import inspect as sa_inspect
    from backend.db.models.user import User as DBUser
    from backend.user_setting_policies import get_manageable_settings

    # Ids/credentials/system bookkeeping that must never appear in the matrix.
    blocked = {
        "id", "username", "hashed_password", "external_id",
        "is_admin", "is_moderator", "is_active", "status",
        "created_at", "last_activity_at", "password_changed_at",
        "activation_token", "password_reset_token", "reset_token_expiry",
        "email_verification_code", "email_verification_code_expiry",
        "email_verification_token", "total_logins", "first_login_done",
        "google_api_key", "google_cse_id", "mcp_access_info",
        "lollms_model_name",
        "tti_binding_model_name", "iti_binding_model_name", "tti_models_config",
        "tts_binding_model_name", "tts_models_config",
        "stt_binding_model_name", "stt_models_config",
        "ttv_binding_model_name", "ttv_models_config",
        "safe_store_vectorizer", "active_personality_id", "active_voice_id",
        "last_discussion_id", "password",
    }

    # `get_manageable_settings()` already reflects the User model with its own
    # blocklist and human-friendly labels/grouping — reuse it as the base so the
    # chat capability flags are guaranteed to be present.
    manageable = get_manageable_settings()

    column_types: Dict[str, str] = {}
    for col in sa_inspect(DBUser).columns:
        if col.key in blocked:
            continue
        column_types[col.key] = _column_type_label(col)

    catalog_by_name: Dict[str, PolicyField] = {}

    # 1) Every reflected User column (base set — includes all chat flags).
    for name, ctype in column_types.items():
        catalog_by_name[name] = PolicyField(
            field_name=name,
            label=_FIELD_LABELS.get(
                name,
                manageable.get(name, {}).get("label", name.replace("_", " ").title()),
            ),
            category=_infer_category(name),
            type=_TYPE_OVERRIDES.get(name, ctype),
            choices=_ENUM_CHOICES.get(name),
            description="",
        )

    # 2) UserUpdate fields — fill in any not already covered and enrich descriptions.
    for name, field_info in UserUpdate.model_fields.items():
        if name in blocked:
            continue

        clean_type = str(field_info.annotation).lower()
        if name in _TYPE_OVERRIDES:
            ftype = _TYPE_OVERRIDES[name]
        elif "bool" in clean_type:
            ftype = "boolean"
        elif "int" in clean_type:
            ftype = "int"
        elif "float" in clean_type:
            ftype = "float"
        elif "list" in clean_type or "dict" in clean_type:
            ftype = "json"
        else:
            ftype = "string"

        existing = catalog_by_name.get(name)
        if existing:
            # Prefer the explicit UserUpdate description when available.
            if field_info.description:
                existing.description = field_info.description
        else:
            catalog_by_name[name] = PolicyField(
                field_name=name,
                label=_FIELD_LABELS.get(name, name.replace("_", " ").title()),
                category=_infer_category(name),
                type=ftype,
                choices=_ENUM_CHOICES.get(name),
                description=field_info.description or "",
            )

    catalog = list(catalog_by_name.values())
    catalog.sort(key=lambda f: (f.category, f.label))
    return catalog


def _column_type_label(column) -> str:
    """Map a SQLAlchemy column type to the coarse type string used by the UI."""
    try:
        type_name = type(column.type).__name__.lower()
    except Exception:
        return "string"
    if "bool" in type_name:
        return "boolean"
    if "int" in type_name:
        return "int"
    if "float" in type_name or "numeric" in type_name:
        return "float"
    if "json" in type_name:
        return "json"
    return "string"


def apply_policies_to_update(db: Session, requested_changes: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter and rewrite an incoming user update payload according to admin policies.

    * Locked fields in ``requested_changes`` are dropped (the user cannot change them).
    * Forced fields are overridden with the admin-pinned value when one is set;
      otherwise they are dropped entirely.
    * Unpoliced fields pass through unchanged.
    """
    if not requested_changes:
        return requested_changes

    rows = {
        row.field_name: row
        for row in db.query(UserSettingPolicy)
        .filter(UserSettingPolicy.field_name.in_(requested_changes.keys()))
        .all()
    }
    if not rows:
        return requested_changes

    sanitized: Dict[str, Any] = {}
    for field_name, new_value in requested_changes.items():
        policy = rows.get(field_name)
        if policy is None:
            sanitized[field_name] = new_value
            continue

        if policy.forced == "1":
            forced_value = policy.get_forced_value()
            if forced_value is not None:
                sanitized[field_name] = forced_value
            continue  # never accept the user's value for a forced field

        if policy.locked == "1":
            continue  # silently drop

        sanitized[field_name] = new_value

    return sanitized


def apply_forced_values_to_user(db: Session, user: UserAuthDetails) -> None:
    """Overwrite ``user``'s attributes in-memory with each forced admin value."""
    forced_rows = db.query(UserSettingPolicy).filter(UserSettingPolicy.forced == "1").all()
    for row in forced_rows:
        forced_value = row.get_forced_value()
        if forced_value is not None and hasattr(user, row.field_name):
            try:
                setattr(user, row.field_name, forced_value)
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# REST endpoints
# --------------------------------------------------------------------------- #
def _snapshot_policies(db: Session) -> Dict[str, PolicyFieldState]:
    snapshot: Dict[str, PolicyFieldState] = {}
    for row in db.query(UserSettingPolicy).all():
        snapshot[row.field_name] = PolicyFieldState(
            field_name=row.field_name,
            locked=row.locked == "1",
            forced=row.forced == "1",
            forced_value=row.get_forced_value(),
        )
    return snapshot


@router.get("", response_model=SettingsPolicyResponse)
async def get_settings_policy(
    db: Session = Depends(get_db),
    admin: UserAuthDetails = Depends(get_current_admin_user),
):
    """Return the full catalog of governable fields plus their current policy state."""
    return SettingsPolicyResponse(
        fields=_build_field_catalog(),
        policies=_snapshot_policies(db),
    )


@router.put("", response_model=SettingsPolicyResponse)
async def update_settings_policy(
    payload: SettingsPolicyUpdateRequest,
    db: Session = Depends(get_db),
    admin: UserAuthDetails = Depends(get_current_admin_user),
):
    """Bulk-upsert the policy for one or many fields in a single transaction."""
    valid_fields = {f.field_name for f in _build_field_catalog()}

    for field_name, change in payload.policies.items():
        if field_name not in valid_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Field '{field_name}' is not a governable user setting.",
            )

        policy = (
            db.query(UserSettingPolicy)
            .filter(UserSettingPolicy.field_name == field_name)
            .first()
        )
        if policy is None:
            policy = UserSettingPolicy(field_name=field_name, locked="0", forced="0")
            db.add(policy)

        if change.locked is not None:
            policy.locked = "1" if change.locked else "0"
        if change.forced is not None:
            policy.forced = "1" if change.forced else "0"
            if not change.forced:
                # Clearing "forced" also drops the pinned value.
                policy.forced_value = None

        if change.forced_value is not None:
            try:
                policy.set_forced_value(change.forced_value)
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid forced value for '{field_name}': {exc}",
                )

    db.commit()

    return SettingsPolicyResponse(
        fields=_build_field_catalog(),
        policies=_snapshot_policies(db),
    )


@router.post("/apply")
async def apply_policies_to_all_users(
    db: Session = Depends(get_db),
    admin: UserAuthDetails = Depends(get_current_admin_user),
):
    """Push every currently forced value onto all existing user rows in one pass.

    Locked-only fields are untouched (locking prevents future user edits but does
    not rewrite stored values). Forced fields are rewritten authoritatively.
    """
    from backend.db.models.user import User as DBUser

    forced_rows = (
        db.query(UserSettingPolicy).filter(UserSettingPolicy.forced == "1").all()
    )
    if not forced_rows:
        return {"updated_users": 0, "forced_fields": 0}

    forced_map = {}
    for row in forced_rows:
        forced_value = row.get_forced_value()
        if forced_value is not None:
            forced_map[row.field_name] = forced_value

    if not forced_map:
        return {"updated_users": 0, "forced_fields": 0}

    updated_users = 0
    for db_user in db.query(DBUser).all():
        user_changed = False
        for field_name, forced_value in forced_map.items():
            if hasattr(db_user, field_name) and getattr(db_user, field_name) != forced_value:
                setattr(db_user, field_name, forced_value)
                user_changed = True
        if user_changed:
            updated_users += 1

    db.commit()
    return {"updated_users": updated_users, "forced_fields": len(forced_map)}


@router.delete("/{field_name}", status_code=status.HTTP_204_NO_CONTENT)
async def reset_field_policy(
    field_name: str,
    db: Session = Depends(get_db),
    admin: UserAuthDetails = Depends(get_current_admin_user),
):
    """Remove the policy for a field, restoring the default 'user is free' behaviour."""
    policy = (
        db.query(UserSettingPolicy)
        .filter(UserSettingPolicy.field_name == field_name)
        .first()
    )
    if policy:
        db.delete(policy)
        db.commit()
    return None