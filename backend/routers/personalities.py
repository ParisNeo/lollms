import base64
import datetime
import io
import shutil
import tempfile
import zipfile
import re
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response, status
from pydantic import BaseModel, Field
from PIL import Image

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, desc
from sqlalchemy.exc import IntegrityError

from backend.db import get_db
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.user import User as DBUser
from backend.models import (
    UserAuthDetails, PersonalityCreate, PersonalityUpdate, 
    PersonalityPublic, PersonalitySendRequest, PersonalityPromptGenerateRequest
)
from backend.session import (
    get_current_active_user,
    get_current_db_user_from_token,
    build_lollms_client_from_params,
    get_user_lollms_client,
    user_sessions
)
from backend.ws_manager import manager
from backend.task_manager import task_manager, Task
from backend.tasks.utils import _to_task_info
from ascii_colors import trace_exception, ASCIIColors as ASCIIColors_log

from backend.personalities import (
    discover_catalog, resolve_handbag_path, materialize_legacy_handbag,
    global_personalities_root, user_personalities_root,
    slugify_handbag_name, read_handbag_detail, write_handbag_files,
    delete_handbag, install_handbag_from_zip,
    migrate_db_personalities_to_handbags, migrate_legacy_user_personality_folders,
    _safe_resolve,
    ensure_personality_roots,
    ensure_default_lollms_handbag,
    write_handbag_skill, write_handbag_tool, copy_skill_from_library, export_skill_to_library,
    _data_root,
)
from backend.db.models.personality_share import PersonalityShareLink, UserPersonalityPreference
from backend.models.personality import (
    PersonalityShareCreate, PersonalityShareOut,
    UserPersonalityPreferenceSet, UserPersonalityPreferenceOut,
)

personalities_router = APIRouter(prefix="/api/personalities", tags=["Personalities"])

# Handbag roots are filesystem-only and safe to create at import time.
# The full DB -> handbag migration runs exactly once inside
# ``main._do_startup_tasks`` (via ``backend.bootstrap_personalities``)
# AFTER ``init_database()`` has initialised the SQLAlchemy engine; doing DB
# work here at import time would fail because the engine is not yet wired
# (this is why the original import-time bootstrap silently did nothing and
# legacy DB personalities were never migrated).
try:
    ensure_personality_roots()
except Exception as _boot_err:  # never block startup over this
    trace_exception(_boot_err)

class EnhancePromptRequest(BaseModel):
    prompt_text: str
    modification_prompt: str

class GenerateIconRequest(BaseModel):
    prompt: str

class HandbagCreate(BaseModel):
    # ``name`` is optional: the "New Personality" action sends an empty/blank
    # name and expects the server to auto-generate a usable slug. Previously a
    # blank name failed Pydantic validation with a 422 *before* reaching the
    # handler, so the UI "New" button silently did nothing. ``str = ""`` keeps
    # the field present/typed while allowing the handler to default it.
    name: str = Field(default="", max_length=128)
    display_name: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    prompt_text: Optional[str] = None
    icon_base64: Optional[str] = None
    # Extra RAG sources: ``str`` / ``Path`` or a mixed list of them (mirrors
    # ``Handbag.normalize_extra_knowledge_bases``). Each entry can point at a
    # SafeStore ``.db`` (anywhere on disk), a document file, or a directory
    # that will be recursively scanned. Stored in ``handbag.yaml`` so
    # ``LollmsPersonality.from_handbag()`` wires them into the personality's
    # RAG pipeline on the next chat turn — no manual per-personality DB
    # plumbing required.
    extra_knowledge_bases: Optional[List[Any]] = None
    scope: str = "personal"  # 'personal' | 'global' (global requires admin)

class HandbagUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    prompt_text: Optional[str] = None
    icon_base64: Optional[str] = None
    # See ``HandbagCreate.extra_knowledge_bases``. Passing ``[]`` clears the
    # key entirely; passing ``None`` leaves the stored value untouched.
    extra_knowledge_bases: Optional[List[Any]] = None

class SkillCreate(BaseModel):
    name: str
    content: str

class SkillFromLibrary(BaseModel):
    name: str

class ToolUpdate(BaseModel):
    content: str

class GenerateSkillRequest(BaseModel):
    prompt: str
    existing_content: Optional[str] = None

class GenerateToolRequest(BaseModel):
    prompt: str
    existing_content: Optional[str] = None

def _generate_personality_task(task: Task, username: str, prompt_text: str):
    task.log("Starting personality generation...")
    task.set_progress(10)
    try:
        lc = build_lollms_client_from_params(username=username)
        task.log("LLM Client initialized.")
        task.set_progress(30)
        
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "A creative, concise name for the personality."},
                "description": {"type": "string", "description": "A short summary of who the personality is and what they do."},
                "category": {"type": "string", "description": "A general category, e.g., 'Coding', 'Writing', 'Fun', 'Expert', 'Philosophy'."},
                "prompt_text": {"type": "string", "description": "A comprehensive system prompt that defines the persona's tone, knowledge, behavioral guidelines, constraints, and operational mode."},
                "icon_prompt": {"type": "string", "description": "A descriptive prompt for an image generator to create an avatar/icon for this personality. E.g., 'A wise old robotic wizard with glowing blue runes, digital art'."}
            },
            "required": ["name", "description", "category", "prompt_text", "icon_prompt"]
        }
        
        system_prompt = "You are a master AI Persona Architect. Your job is to create rich, vivid, deep, and highly effective AI personalities based on user concepts."
        user_prompt = f"Design a complete AI personality based on this concept:\n\"{prompt_text}\""
        
        task.log("Generating structured personality blueprint...")
        personality_data = lc.generate_structured_content(user_prompt, schema=schema, system_prompt=system_prompt)
        
        if not personality_data or not isinstance(personality_data, dict):
            raise Exception("AI failed to return valid personality structure.")
            
        task.set_progress(70)
        task.log(f"Generated blueprint for '{personality_data.get('name')}'. Generating icon...")
        
        icon_base64 = None
        icon_prompt = personality_data.get("icon_prompt")
        
        if icon_prompt:
            try:
                tti_client = build_lollms_client_from_params(username=username, load_llm=False, load_tti=True)
                if tti_client.tti:
                    img_bytes = tti_client.tti.generate_image(icon_prompt, width=512, height=512)
                    if img_bytes:
                        if isinstance(img_bytes, list):
                            img_bytes = img_bytes[0]
                        if isinstance(img_bytes, str) and img_bytes.startswith('data:'):
                            img_bytes = base64.b64decode(img_bytes.split(',', 1)[1])
                        elif isinstance(img_bytes, str):
                            img_bytes = base64.b64decode(img_bytes)

                        with Image.open(io.BytesIO(img_bytes)) as img:
                            if img.mode not in ("RGB", "RGBA"):
                                img = img.convert("RGBA")
                            img.thumbnail((128, 128))
                            buf = io.BytesIO()
                            img.save(buf, format="PNG")
                            icon_base64 = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
                            task.log("Icon generated successfully.")
            except Exception as tti_err:
                task.log(f"Icon generation skipped or failed: {tti_err}", "WARNING")
                
        task.set_progress(90)
        
        db = next(get_db())
        try:
            user = db.query(DBUser).filter(DBUser.username == username).first()
            if not user:
                raise Exception("User not found.")
            
            new_pers = DBPersonality(
                name=personality_data.get("name", "New Persona"),
                author=username,
                category=personality_data.get("category", "Custom"),
                description=personality_data.get("description", ""),
                prompt_text=personality_data.get("prompt_text", ""),
                icon_base64=icon_base64,
                owner_user_id=user.id,
                is_public=False
            )
            db.add(new_pers)
            db.commit()
            db.refresh(new_pers)
            
            task.set_progress(100)
            task.log("Personality saved to your library!")
            
            return {
                "id": new_pers.id,
                "name": new_pers.name,
                "category": new_pers.category,
                "description": new_pers.description,
                "prompt_text": new_pers.prompt_text,
                "icon_base64": new_pers.icon_base64
            }
        finally:
            db.close()
            
    except Exception as e:
        task.log(f"Generation failed: {e}", "ERROR")
        trace_exception(e)
        raise e

def _enhance_prompt_task(task: Task, username: str, prompt_text: str, custom_instruction: Optional[str]):
    task.log("Starting prompt enhancement...")
    task.set_progress(10)
    try:
        lc = get_user_lollms_client(username)
        enhance_instruction = custom_instruction.strip() if custom_instruction else "Enhance the system prompt:"
        enhance_instruction += f"\nOriginal system prompt:\n{prompt_text}\n"
        
        output_schema = {
            "type": "object",
            "properties": {
                "enhanced_system_prompt": {"type": "string", "description": "The enhanced core system prompt."}
            },
            "required": ["enhanced_system_prompt"],
            "description": "JSON object defining the enhanced system prompt."
        }

        system_prompt = "You are an expert personality designer for AI assistants. Improve the prompt based on user instructions."
        task.set_progress(30)
        
        generated_data_dict = lc.generate_structured_content(
            enhance_instruction,
            system_prompt=system_prompt,
            schema=output_schema
        )
        
        task.log("Prompt enhanced successfully.")
        task.set_progress(100)
        return generated_data_dict
    except Exception as e:
        task.log(f"Prompt enhancement failed: {e}", "ERROR")
        trace_exception(e)
        raise e

def _generate_icon_task(task: Task, username: str, prompt: str):
    task.log("Starting icon generation...")
    task.set_progress(10)
    try:
        lc = build_lollms_client_from_params(username=username, load_llm=True, load_tti=True)
        if not lc.tti:
            raise Exception("Text-to-Image service is not configured for this user.")

        task.log("Refining prompt with LLM...")
        refinement_sys = "You are an expert prompt engineer. Convert the user's description into a detailed stable diffusion icon prompt. Output ONLY the prompt."
        refined_prompt = lc.generate_text(prompt, system_prompt=refinement_sys, max_new_tokens=200).strip()
        
        task.log("Rendering icon with TTI...")
        img_data = lc.tti.generate_image(refined_prompt, width=512, height=512)
        if not img_data:
            raise Exception("Image generation returned empty data.")
            
        if isinstance(img_data, list):
            img_data = img_data[0]
            
        if isinstance(img_data, str):
            if img_data.startswith("data:"):
                img_data = img_data.split(",", 1)[1]
            img_data = base64.b64decode(img_data)

        with Image.open(io.BytesIO(img_data)) as img:
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            img.thumbnail((128, 128))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            icon_b64 = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"

        task.log("Icon generated successfully.")
        task.set_progress(100)
        return {"icon_base64": icon_b64}
    except Exception as e:
        task.log(f"Icon generation failed: {e}", "ERROR")
        trace_exception(e)
        raise e

@personalities_router.post("/generate_from_prompt", status_code=status.HTTP_202_ACCEPTED)
async def generate_personality(
    payload: PersonalityPromptGenerateRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    task = task_manager.submit_task(
        name=f"Generate Persona: {payload.prompt[:30]}...",
        target=_generate_personality_task,
        args=(current_user.username, payload.prompt),
        description=f"Creating rich personality from prompt: '{payload.prompt[:40]}...'",
        owner_username=current_user.username
    )
    return task

@personalities_router.post("/enhance_prompt", status_code=status.HTTP_200_OK)
async def enhance_prompt(
    payload: EnhancePromptRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    try:
        lc = build_lollms_client_from_params(username=current_user.username)
        prompt = f"""You are an expert Prompt Engineer for AI personas.
Improve and expand the following system prompt based on the user's enhancement instructions.

[CURRENT SYSTEM PROMPT]:
{payload.prompt_text}

[INSTRUCTIONS FOR ENHANCEMENT]:
{payload.modification_prompt}

[OUTPUT INSTRUCTION]:
Return ONLY the newly revised, high-fidelity system prompt text. Do not wrap in markdown or add conversational intro."""
        
        enhanced_text = lc.generate_text(prompt, max_new_tokens=2048)
        return {"enhanced_prompt": enhanced_text.strip()}
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=str(e))

def _extract_icon_bytes(raw) -> bytes:
    """Normalize any TTI client return shape into raw image bytes.

    Mirrors the extraction used by the working image-studio pipeline: the TTI
    binding may return ``bytes``, a base64 ``str`` (with or without a
    ``data:`` prefix), a ``list`` (take the first), or a ``dict`` carrying the
    image under ``image`` / ``images`` / ``b64_json`` / ``data``. Handling only
    ``str``/``list`` (the previous behaviour) left dict returns unconverted and
    produced corrupted output.
    """
    if raw is None:
        raise ValueError("Image generation returned no data.")
    # Unwrap lists (some TTI clients return a list of results).
    if isinstance(raw, (list, tuple)):
        if not raw:
            raise ValueError("Image generation returned an empty list.")
        return _extract_icon_bytes(raw[0])
    # Unwrap dicts (OpenAI-style / lollms-style payloads).
    if isinstance(raw, dict):
        for key in ("image", "images", "b64_json", "data", "image_base64"):
            if key in raw and raw[key]:
                value = raw[key]
                if isinstance(value, (list, tuple)):
                    value = value[0] if value else None
                if isinstance(value, dict):
                    for sub in ("b64_json", "image", "data"):
                        if value.get(sub):
                            return _extract_icon_bytes(value[sub])
                    raise ValueError("Unrecognized nested image payload.")
                return _extract_icon_bytes(value)
        raise ValueError("Unrecognized image payload structure.")
    if isinstance(raw, str):
        if raw.startswith("data:"):
            raw = raw.split(",", 1)[1]
        try:
            return base64.b64decode(raw)
        except Exception as exc:
            raise ValueError(f"Could not decode base64 image: {exc}") from exc
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    raise ValueError(f"Unsupported image data type: {type(raw).__name__}")


@personalities_router.post("/generate_icon", status_code=status.HTTP_200_OK)
async def generate_icon(
    payload: GenerateIconRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """Generate a crisp 128px persona icon, matching the image-studio quality path.

    The image studio refines the user prompt with the LLM before rendering and
    passes a negative prompt to the TTI binding. The old icon endpoint skipped
    both, sending a terse persona phrase straight to the diffusion model — the
    root cause of the "messed up" icons.
    """
    try:
        lc = build_lollms_client_from_params(username=current_user.username, load_llm=True, load_tti=True)
        if not lc.tti:
            raise HTTPException(status_code=400, detail="TTI binding is not configured.")

        # 1) Refine the terse persona phrase into a detailed icon prompt.
        refined_prompt = payload.prompt
        if lc.llm:
            refine_system = (
                "You are an expert prompt engineer for text-to-image models. "
                "Convert the user's description into a single detailed, high-quality "
                "prompt for a clean profile icon / avatar: a centered subject, "
                "simple uncluttered background, professional digital art, crisp "
                "details, good lighting. Output ONLY the prompt, no quotes, no extra text."
            )
            try:
                refined = lc.generate_text(
                    f"Persona description: {payload.prompt}\n\nIcon prompt:",
                    system_prompt=refine_system,
                    max_new_tokens=160,
                )
                if isinstance(refined, str) and refined.strip():
                    refined_prompt = refined.strip().strip('"').strip()
            except Exception as refine_err:
                # Non-fatal: fall back to the raw prompt rather than failing.
                trace_exception(refine_err)

        # 2) Render. A negative prompt steers away from the common bad outputs
        #    (text, watermarks, cluttered scenes) that make icons look broken.
        negative_prompt = "text, watermark, logo, blurry, low quality, deformed, cluttered background, multiple subjects"
        img_bytes = lc.tti.generate_image(
            refined_prompt, width=512, height=512, negative_prompt=negative_prompt
        )

        # 3) Robust extraction (bytes / base64 / list / dict).
        img_bytes = _extract_icon_bytes(img_bytes)

        # 4) Square-crop then downscale to a tight 128px PNG icon.
        with Image.open(io.BytesIO(img_bytes)) as img:
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            width, height = img.size
            side = min(width, height)
            left = (width - side) // 2
            top = (height - side) // 2
            img = img.crop((left, top, left + side, top + side))
            img.thumbnail((128, 128))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            icon_base64 = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
            return {"icon_base64": icon_base64}
    except HTTPException:
        raise
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=str(e))

# --- Handbag-surface endpoints (Personality Studio + Personalities Zoo) ---
# Declared before `/{personality_id}` so literal routes win path matching.

@personalities_router.get("/catalog")
def get_personality_catalog(db_user: DBUser = Depends(get_current_db_user_from_token),
                            db: Session = Depends(get_db)):
    """Full handbag catalog. **Always** returns a valid JSON payload.

    Nothing that happens below can bubble up as a 500: if any stage fails we
    log via ``trace_exception`` (→ ``logs/trace_exception.log``) and return a
    valid empty catalog so the UI can at least render.
    """
    empty = {"global": [], "personal": [], "shared": []}

    # Phase 0 — guarantee the on-disk roots exist (idempotent)
    try:
        ensure_personality_roots()
    except Exception as roots_err:
        trace_exception(roots_err)
        ASCIIColors_log.error(f"[personalities] roots prep failed: {roots_err}")

    # Guarantee the calling user's own folder exists
    try:
        user_personalities_root(db_user.username).mkdir(parents=True, exist_ok=True)
    except Exception as mk_err:
        trace_exception(mk_err)

    # Phase 1a — relocate any handbags still in the legacy per-user layout.
    # Runs here as well as at startup so a failed/deferred startup migration
    # can never keep the user's personalities hidden from the catalog.
    try:
        migrate_legacy_user_personality_folders(db)
    except Exception as legacy_err:
        trace_exception(legacy_err)

    # Phase 1b — one-shot legacy DB -> handbag migration (idempotent, never fatal).
    # The helper already logs its own result; re-logging here duplicated the
    # message under a misleading "legacy" wording on every catalog refresh.
    try:
        migrate_db_personalities_to_handbags(db)
    except Exception as bridge_exc:
        trace_exception(bridge_exc)

    # Phase 1c — mandatory 'lollms' persona (defense-in-depth: seed here if
    # the startup bootstrap has not run on this instance yet).
    try:
        ensure_default_lollms_handbag()
    except Exception as seed_err:
        trace_exception(seed_err)

    # Phase 2 — filesystem discovery (single source of truth)
    try:
        return discover_catalog(db, db_user)
    except Exception as e:
        trace_exception(e)
        ASCIIColors_log.error(f"[personalities] catalog discovery failed: {e}")
        return empty


@personalities_router.get("/system_info")
def get_personalities_system_info(
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db),
):
    """Diagnostic: shows where handbag roots resolve and what exists there.

    Hit ``GET /api/personalities/system_info`` while authenticated to see the
    exact filesystem paths the backend is using, plus the count of legacy DB
    rows still awaiting migration. Useful when the studio appears empty.
    """
    from backend.personalities import _data_root
    info: Dict[str, Any] = {
        "cwd": str(Path.cwd()),
        "data_root": str(_data_root()),
        "global_root": str(global_personalities_root()),
        "user_root": str(user_personalities_root(db_user.username)),
        "global_exists": global_personalities_root().is_dir(),
        "user_exists": user_personalities_root(db_user.username).is_dir(),
    }
    try:
        base = _data_root() / "personalities"
        if base.is_dir():
            info["personalities_entries"] = sorted(p.name for p in base.iterdir())
        else:
            info["personalities_entries"] = []
    except Exception as e:
        info["personalities_entries_error"] = str(e)
    try:
        from backend.db.models.personality import Personality as DBPersonality
        info["legacy_db_rows"] = db.query(DBPersonality).count()
    except Exception as e:
        info["legacy_db_rows_error"] = str(e)
    return info


@personalities_router.put("/preference", response_model=UserPersonalityPreferenceOut)
def set_personality_preference(payload: UserPersonalityPreferenceSet,
                               db_user: DBUser = Depends(get_current_db_user_from_token),
                               db: Session = Depends(get_db)):
    """Upsert the caller's active persona preference.

    * Validate the target handbag actually resolves (scope/owner/ACL) —
      never persist a reference the reader cannot resolve, that was the
      silent-revert source.
    * Upsert strictly on ``user_id`` (unique). Race-safe: if a concurrent
      INSERT beats us, fall back to an UPDATE on the existing row.
    * Any DB failure raises 500 rather than being reported as success.
    """
    if payload.scope == "shared" and payload.owner_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="owner_id is required when scope == 'shared'")

    resolved = resolve_handbag_path(payload.scope, payload.handbag_name, db_user,
                                    owner_id=payload.owner_id, db=db)
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(f"Personality handbag '{payload.scope}/"
                    f"{payload.handbag_name}' not found or access denied"),
        )

    owner_id = payload.owner_id if payload.scope == "shared" else None
    row = db.query(UserPersonalityPreference).filter(
        UserPersonalityPreference.user_id == db_user.id).first()
    if row:
        row.scope = payload.scope
        row.handbag_name = payload.handbag_name
        row.owner_id = owner_id
    else:
        row = UserPersonalityPreference(
            user_id=db_user.id, scope=payload.scope,
            handbag_name=payload.handbag_name, owner_id=owner_id)
        db.add(row)

    try:
        db.commit()
    except IntegrityError:
        # Concurrent insert on the unique user_id column: roll back and
        # convert to an update on the row that just won the race.
        db.rollback()
        row = db.query(UserPersonalityPreference).filter(
            UserPersonalityPreference.user_id == db_user.id).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist personality preference",
            )
        row.scope = payload.scope
        row.handbag_name = payload.handbag_name
        row.owner_id = owner_id
        db.commit()
    except Exception as exc:
        db.rollback()
        trace_exception(exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist personality preference: {exc}",
        )

    db.refresh(row)
    ASCIIColors_log.info(
        f"[personalities] preference set: user_id={db_user.id} "
        f"scope={row.scope} handbag={row.handbag_name} owner_id={row.owner_id}"
    )
    return row


@personalities_router.get("/preference", response_model=UserPersonalityPreferenceOut)
def get_personality_preference(db_user: DBUser = Depends(get_current_db_user_from_token),
                               db: Session = Depends(get_db)):
    """Return the caller's stored active-persona preference.

    ``404`` means "no preference set" and the client should treat the
    runtime fallback (first personal / first global) as active. Any other
    failure raises 500 so the SPA can distinguish "unset" from "backend
    broke", instead of both looking like "reverted to first in list".
    """
    try:
        row = db.query(UserPersonalityPreference).filter(
            UserPersonalityPreference.user_id == db_user.id).first()
    except Exception as exc:
        trace_exception(exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read personality preference: {exc}",
        )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No preference set")
    return row


@personalities_router.post("/share", response_model=PersonalityShareOut,
                           status_code=status.HTTP_201_CREATED)
def share_personality(payload: PersonalityShareCreate,
                      db_user: DBUser = Depends(get_current_db_user_from_token),
                      db: Session = Depends(get_db)):
    if bool(payload.shared_with_user_id is not None) == bool(payload.group_id is not None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Provide exactly one of shared_with_user_id or group_id")
    if payload.shared_with_user_id is not None and payload.shared_with_user_id == db_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Cannot share a personality with yourself")
    if resolve_handbag_path("personal", payload.handbag_name, db_user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Personal handbag not found")
    if payload.shared_with_user_id is not None:
        target = db.query(DBUser).filter(DBUser.id == payload.shared_with_user_id).first()
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")
    link = PersonalityShareLink(
        owner_user_id=db_user.id, handbag_name=payload.handbag_name,
        shared_with_user_id=payload.shared_with_user_id,
        group_id=payload.group_id, permission=payload.permission)
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This personality is already shared with that target")
    db.refresh(link)
    return link


@personalities_router.get("/share/received", response_model=List[PersonalityShareOut])
def list_received_shares(db_user: DBUser = Depends(get_current_db_user_from_token),
                         db: Session = Depends(get_db)):
    """List share links visible to the caller. Never raises out of the route:
    a DB hiccup yields an empty list rather than a 500 the SPA might mask."""
    try:
        memberships = getattr(db_user, "group_memberships", []) or []
        group_ids = [m.group_id for m in memberships if getattr(m, "group_id", None) is not None]
        valid_target = or_(PersonalityShareLink.shared_with_user_id.isnot(None),
                           PersonalityShareLink.group_id.isnot(None))
        q = db.query(PersonalityShareLink).filter(valid_target)
        if group_ids:
            return q.filter((PersonalityShareLink.shared_with_user_id == db_user.id)
                            | (PersonalityShareLink.group_id.in_(group_ids)))\
                    .order_by(PersonalityShareLink.id.desc()).all()
        return q.filter(PersonalityShareLink.shared_with_user_id == db_user.id)\
                .order_by(PersonalityShareLink.id.desc()).all()
    except Exception as exc:
        trace_exception(exc)
        ASCIIColors_log.warning(f"[personalities] share/received lookup failed: {exc}")
        return []


@personalities_router.delete("/share/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share(link_id: int,
                 db_user: DBUser = Depends(get_current_db_user_from_token),
                 db: Session = Depends(get_db)):
    link = db.query(PersonalityShareLink).filter(PersonalityShareLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found")
    if link.owner_user_id != db_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only the owner can revoke this share")
    db.delete(link)
    db.commit()


def _enforce_capability(name: str, message: str) -> None:
    """Raise 403 when an admin-disabled capability is off. Missing policy module
    or missing capability key means 'not restricted' (fail-open), matching the
    pre-policy behaviour so this remains backward compatible on older installs.
    """
    try:
        from backend.user_setting_policies import get_capability
    except Exception:
        return
    try:
        allowed = bool(get_capability(name, default=True))
    except Exception:
        return
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def _studio_write_path(scope: str, handbag_name: str, db_user: DBUser,
                       db: Session) -> Path:
    """Resolve a handbag for mutation: personal = own folder, global = admin only."""
    if scope == "global":
        if not getattr(db_user, "is_admin", False):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only admins can modify global personalities")
    elif scope != "personal":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Shared handbags are read-only")
    try:
        if scope == "personal":
            path = _safe_resolve(user_personalities_root(db_user.username), handbag_name)
        else:
            path = _safe_resolve(global_personalities_root(), handbag_name)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Handbag not found or access denied")
    if not path.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Handbag not found or access denied")
    return path


@personalities_router.post("/studio/handbags", status_code=status.HTTP_201_CREATED)
def create_handbag(payload: HandbagCreate,
                   db_user: DBUser = Depends(get_current_db_user_from_token)):
    if payload.scope not in ("global", "personal"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="scope must be 'personal' or 'global'")
    if payload.scope == "global" and not getattr(db_user, "is_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only admins can create global personalities")
    root = (global_personalities_root() if payload.scope == "global"
            else user_personalities_root(db_user.username))
    # Ensure the target root exists before we test membership on it — a missing
    # root made ``(root / slug).exists()`` always False yet the later
    # ``materialize_legacy_handbag`` write could still fail on the same absent
    # parent, surfacing as an opaque 400.
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        trace_exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Could not prepare personality storage: {exc}")

    requested_name = (payload.name or "").strip()
    explicit_name = bool(requested_name)
    base_slug = slugify_handbag_name(requested_name) if explicit_name else ""
    if not base_slug:
        # Auto-name path: the "New" button sends no/blank name. Provide a
        # stable human default and let the collision loop suffix it.
        base_slug = "new-personality"
        explicit_name = False

    # Resolve a *unique* slug. Explicit duplicates stay a 409 (so a real rename
    # clash is reported); auto-generated ones silently advance to the next free
    # suffix so "New" always creates something.
    slug = base_slug
    counter = 1
    while (root / slug).exists():
        if explicit_name:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"A handbag named '{base_slug}' already exists")
        counter += 1
        slug = f"{base_slug}-{counter}"

    path = materialize_legacy_handbag(
        name=slug,
        prompt_text=payload.prompt_text or f"# {payload.display_name or slug}\n",
        description=payload.description,
        author=payload.author or db_user.username,
        category=payload.category,
        root=root,
    )
    if path is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid personality name")
    if (payload.display_name or payload.icon_base64
            or payload.extra_knowledge_bases is not None):
        write_handbag_files(
            path,
            display_name=payload.display_name,
            icon_base64=payload.icon_base64,
            extra_knowledge_bases=payload.extra_knowledge_bases,
        )
    return {"handbag_name": slug, "scope": payload.scope}


@personalities_router.get("/studio/handbags/{scope}/{handbag_name}")
def get_handbag_detail(scope: str, handbag_name: str,
                       owner_id: Optional[int] = None,
                       db_user: DBUser = Depends(get_current_db_user_from_token),
                       db: Session = Depends(get_db)):
    path = resolve_handbag_path(scope, handbag_name, db_user,
                                owner_id=owner_id, db=db)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Handbag not found or access denied")
    detail = read_handbag_detail(path)
    detail.update({"handbag_name": handbag_name, "scope": scope,
                   "owner_id": owner_id})
    return detail


@personalities_router.put("/studio/handbags/{scope}/{handbag_name}")
def update_handbag(scope: str, handbag_name: str, payload: HandbagUpdate,
                   db_user: DBUser = Depends(get_current_db_user_from_token),
                   db: Session = Depends(get_db)):
    path = _studio_write_path(scope, handbag_name, db_user, db)
    write_handbag_files(
        path,
        display_name=payload.display_name,
        description=payload.description,
        author=payload.author,
        category=payload.category,
        prompt_text=payload.prompt_text,
        icon_base64=payload.icon_base64,
        extra_knowledge_bases=payload.extra_knowledge_bases,
    )
    return {"handbag_name": handbag_name, "scope": scope, "updated": True}


@personalities_router.delete("/studio/handbags/{scope}/{handbag_name}",
                             status_code=status.HTTP_204_NO_CONTENT)
def remove_handbag(scope: str, handbag_name: str,
                   db_user: DBUser = Depends(get_current_db_user_from_token),
                   db: Session = Depends(get_db)):
    _studio_write_path(scope, handbag_name, db_user, db)  # ACL check
    root = (global_personalities_root() if scope == "global"
            else user_personalities_root(db_user.username))
    try:
        delete_handbag(root, handbag_name)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Handbag not found")


@personalities_router.get("/studio/handbags/{scope}/{handbag_name}/tools/{filename}")
def get_handbag_tool(
    scope: str, handbag_name: str, filename: str,
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    path = resolve_handbag_path(scope, handbag_name, db_user, db=db)
    if not path:
        raise HTTPException(status_code=404, detail="Handbag not found")
    tool_file = path / "tools" / filename
    if not tool_file.is_file() or not tool_file.name.endswith(".py"):
        raise HTTPException(status_code=404, detail="Tool not found")
    return {"content": tool_file.read_text(encoding="utf-8")}


@personalities_router.put("/studio/handbags/{scope}/{handbag_name}/tools/{filename}")
def update_handbag_tool(
    scope: str, handbag_name: str, filename: str, payload: ToolUpdate,
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    path = _studio_write_path(scope, handbag_name, db_user, db)
    _enforce_capability(
        "personality_tools_editable",
        "Editing personality tools is disabled by the administrator.",
    )
    write_handbag_tool(path, filename, payload.content)
    return {"status": "ok", "filename": filename}


@personalities_router.get("/studio/handbags/{scope}/{handbag_name}/skills/{skill_name}")
def get_handbag_skill(
    scope: str, handbag_name: str, skill_name: str,
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    path = resolve_handbag_path(scope, handbag_name, db_user, db=db)
    if not path:
        raise HTTPException(status_code=404, detail="Handbag not found")
    skill_file = path / "skills" / skill_name
    if not skill_file.exists():
        skill_file = path / "skills" / f"{skill_name}.md"
    if not skill_file.is_file():
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"content": skill_file.read_text(encoding="utf-8")}


@personalities_router.post("/studio/handbags/{scope}/{handbag_name}/skills")
def create_handbag_skill(
    scope: str, handbag_name: str, payload: SkillCreate,
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    path = _studio_write_path(scope, handbag_name, db_user, db)
    _enforce_capability(
        "personality_skills_editable",
        "Editing personality skills is disabled by the administrator.",
    )
    write_handbag_skill(path, payload.name, payload.content)
    return {"status": "ok", "name": payload.name}


@personalities_router.get("/studio/skills-library")
def list_skills_library(
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db),
):
    """List installable skills from the shared skills library.

    The library is the UNION of two sources so the "From Library" picker never
    shows empty while the user actually has skills:

      * **DB skills** the caller can see (own + system), served by
        ``GET /api/skills`` and stored in the ``skills`` table. ``source`` is
        ``"db"``; ``name`` is the display name and ``stem`` is a filesystem-safe
        slug derived from it.
      * **Filesystem skills** under ``<data_root>/skills`` (``.md`` only),
        ``source`` is ``"file"``.

    Entries are de-duplicated by their resolved output filename (``stem``) so
    importing the same skill from either source targets one file. The DB wins
    on collision because it usually carries richer content.
    """
    from backend.db.models.skill import Skill as DBSkill
    from sqlalchemy import or_

    items: List[Dict[str, Any]] = []
    seen_stems = set()

    def _slug_stem(raw: str) -> str:
        s = re.sub(r"[^A-Za-z0-9_\-]+", "_", str(raw or "")).strip("_ ")
        return s or "skill"

    # 1) DB-backed skills visible to this user (own + system).
    try:
        rows = (
            db.query(DBSkill)
            .filter(or_(DBSkill.owner_user_id == db_user.id,
                        DBSkill.owner_user_id.is_(None)))
            .order_by(DBSkill.name)
            .all()
        )
        for row in rows:
            stem = _slug_stem(row.name)
            if stem in seen_stems:
                continue
            seen_stems.add(stem)
            items.append({
                "name": row.name,
                "stem": stem,
                "source": "db",
                "description": row.description or "",
                "category": row.category or "",
            })
    except Exception as exc:
        trace_exception(exc)

    # 2) Filesystem skills under <data_root>/skills.
    lib_root = _data_root() / "skills"
    try:
        if lib_root.is_dir():
            for p in sorted(lib_root.iterdir(), key=lambda x: x.name.lower()):
                if not (p.is_file() and p.suffix.lower() == ".md"):
                    continue
                if p.stem in seen_stems:
                    continue
                seen_stems.add(p.stem)
                items.append({
                    "name": p.name,
                    "stem": p.stem,
                    "source": "file",
                    "description": "",
                    "category": "",
                })
    except Exception as exc:
        trace_exception(exc)

    items.sort(key=lambda x: (x.get("name") or "").lower())
    return {"skills": items}


@personalities_router.post("/studio/handbags/{scope}/{handbag_name}/skills/import")
async def import_skill_file(
    scope: str,
    handbag_name: str,
    file: UploadFile = File(...),
    name: Optional[str] = Query(None),
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db),
):
    """Import a single ``SKILL.md`` into a handbag's ``skills/`` folder.

    * Markdown only (rejects anything else) — skill bodies are prose+code and
      must never be an executable or opaque binary.
    * The skill name is inferred from YAML frontmatter ``name:`` when present;
      if absent we fall back to the frontend-supplied ``name``, then to the
      uploaded filename stem. The caller is expected to have prompted the user
      for a name when frontmatter had none.
    * Refuses to overwrite an existing skill with the same resolved name.
    """
    if not (file.filename or "").lower().endswith(".md"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Only Markdown (.md) skill files are allowed")
    path = _studio_write_path(scope, handbag_name, db_user, db)
    _enforce_capability(
        "personality_skills_editable",
        "Editing personality skills is disabled by the administrator.",
    )

    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Skill file must be UTF-8 text")

    resolved = None
    body = text
    # Parse simple YAML frontmatter (--- ... ---) for a `name:` key.
    if text.lstrip().startswith("---"):
        stripped = text.lstrip()
        end = stripped.find("\n---", 3)
        if end != -1:
            frontmatter = stripped[3:end]
            body = stripped[end + 4:].lstrip("\n")
            for line in frontmatter.splitlines():
                if line.strip().lower().startswith("name:"):
                    resolved = line.split(":", 1)[1].strip().strip("\"'")
                    break
    if not resolved and name:
        resolved = name.strip()
    if not resolved:
        resolved = Path(file.filename).stem

    # Force a .md suffix and strip path separators to prevent traversal.
    safe = re.sub(r"[^A-Za-z0-9_\-\. ]", "_", resolved).strip().replace("/", "_")
    if not safe:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Could not determine a valid skill name")
    if not safe.lower().endswith(".md"):
        safe += ".md"

    skills_dir = path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    target = skills_dir / safe
    if target.exists():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"A skill named '{safe}' already exists")
    target.write_text(body, encoding="utf-8")
    return {"status": "ok", "name": safe}


@personalities_router.post("/studio/handbags/{scope}/{handbag_name}/skills/from-library")
def add_skill_from_library(
    scope: str, handbag_name: str, payload: SkillFromLibrary,
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    """Copy a library skill into this handbag's ``skills/`` folder.

    Resolution order (first hit wins) so the picker works whether the skill
    lives on disk or only in the DB:

      1. Filesystem ``<data_root>/skills/<name>`` (legacy export path).
      2. DB skill by exact case-insensitive ``name`` visible to the caller
         (own + system) — written to ``skills/<slug(name)>.md``.
    """
    from backend.db.models.skill import Skill as DBSkill
    from sqlalchemy import func, or_

    path = _studio_write_path(scope, handbag_name, db_user, db)
    _enforce_capability(
        "personality_skills_editable",
        "Editing personality skills is disabled by the administrator.",
    )
    lib_root = _data_root() / "skills"

    # 1) Filesystem copy
    try:
        copy_skill_from_library(path, payload.name, lib_root)
        return {"status": "ok", "name": payload.name, "source": "file"}
    except ValueError:
        pass  # fall through to DB lookup

    # 2) DB fallback
    row = (
        db.query(DBSkill)
        .filter(
            func.lower(DBSkill.name) == func.lower(payload.name),
            or_(DBSkill.owner_user_id == db_user.id,
                DBSkill.owner_user_id.is_(None)),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404,
                            detail=f"Skill '{payload.name}' not found in library")

    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", row.name).strip("_ ") or "skill"
    if not safe.lower().endswith(".md"):
        safe += ".md"
    skills_dir = path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    target = skills_dir / safe
    if target.exists():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"A skill named '{safe}' already exists")
    target.write_text(row.content or "", encoding="utf-8")
    return {"status": "ok", "name": safe, "source": "db"}


@personalities_router.post("/studio/handbags/{scope}/{handbag_name}/skills/{skill_name}/to-library")
def add_skill_to_library(
    scope: str, handbag_name: str, skill_name: str,
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db)
):
    path = _studio_write_path(scope, handbag_name, db_user, db)
    lib_root = _data_root() / "skills"
    try:
        export_skill_to_library(path, skill_name, lib_root)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "ok", "name": skill_name}


@personalities_router.post("/studio/generate_skill")
def generate_skill_endpoint(
    payload: GenerateSkillRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    try:
        lc = build_lollms_client_from_params(username=current_user.username)
        prompt = f"Create a skill definition based on this description:\n{payload.prompt}\n"
        if payload.existing_content:
            prompt = f"Modify and improve this existing skill based on instructions:\n{payload.prompt}\n\nOriginal Skill:\n{payload.existing_content}"
        prompt += "\nOutput ONLY the raw markdown content of the skill without any conversational intro or markdown fences."
        content = lc.generate_text(prompt, max_new_tokens=2048)
        content = re.sub(r"^```[a-zA-Z]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
        return {"content": content.strip()}
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=str(e))


@personalities_router.post("/studio/generate_tool")
def generate_tool_endpoint(
    payload: GenerateToolRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    try:
        lc = build_lollms_client_from_params(username=current_user.username)
        prompt = f"Create a Python LCP tool based on this description:\n{payload.prompt}\n"
        if payload.existing_content:
            prompt = f"Modify and improve this existing LCP tool based on instructions:\n{payload.prompt}\n\nOriginal Tool:\n{payload.existing_content}"
        prompt += "\n\nOutput ONLY the raw Python code without any conversational intro or markdown fences."
        content = lc.generate_text(prompt, max_new_tokens=2048)
        content = re.sub(r"^```[a-zA-Z]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
        return {"content": content.strip()}
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=str(e))


@personalities_router.get("/studio/handbags/{scope}/{handbag_name}/export")
def export_handbag_zip(
    scope: str, handbag_name: str,
    owner_id: Optional[int] = None,
    db_user: DBUser = Depends(get_current_db_user_from_token),
    db: Session = Depends(get_db),
):
    """Stream a handbag (persona) as a self-contained ZIP archive.

    Reads through ``resolve_handbag_path`` so ACL is enforced (personal = own,
    global = any reader, shared = owner/recipient). The archive keeps the
    handbag directory layout intact (``handbag.yaml``, ``SOUL.md``, ``skills/``,
    ``tools/``, ``databases/``, ``icon.*`` …) so the same file round-trips via
    ``POST /studio/upload`` on any LoLLMs instance — including one where the
    persona has skills/tools the current user cannot edit.
    """
    path = resolve_handbag_path(scope, handbag_name, db_user,
                                owner_id=owner_id, db=db)
    if path is None or not path.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Handbag not found or access denied")

    archive_root = re.sub(r"[^A-Za-z0-9_\-\. ]", "_", path.name).strip() or "personality"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in path.rglob("*"):
            if not entry.is_file():
                continue
            # Path traversal guard: rglob can only return children of `path`,
            # but keep an explicit check so a symlink never escapes the tree.
            try:
                rel = entry.relative_to(path)
            except ValueError:
                continue
            if any(part in ("..", "") for part in rel.parts):
                continue
            zf.write(entry, arcname=str(Path(archive_root) / rel))
    buffer.seek(0)

    filename = f"personality_{archive_root}.zip"
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@personalities_router.post("/studio/upload", status_code=status.HTTP_201_CREATED)
async def upload_handbag_zip(scope: str = "personal",
                             file: UploadFile = File(...),
                             db_user: DBUser = Depends(get_current_db_user_from_token)):
    if scope not in ("global", "personal"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="scope must be 'personal' or 'global'")
    if scope == "global" and not getattr(db_user, "is_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only admins can install global personalities")
    root = (global_personalities_root() if scope == "global"
            else user_personalities_root(db_user.username))
    work_dir = Path(tempfile.mkdtemp(prefix="handbag_upload_"))
    try:
        zip_path = work_dir / "upload.zip"
        zip_path.write_bytes(await file.read())
        final = install_handbag_from_zip(zip_path, root)
        return {"handbag_name": final.name, "scope": scope}
    except zipfile.BadZipFile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid ZIP archive")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@personalities_router.get("/my", response_model=List[PersonalityPublic])
def get_my_personalities(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return db.query(DBPersonality).filter(DBPersonality.owner_user_id == current_user.id).order_by(DBPersonality.name).all()

@personalities_router.get("/public", response_model=List[PersonalityPublic])
def get_public_personalities(
    db: Session = Depends(get_db)
):
    return db.query(DBPersonality).filter(DBPersonality.is_public == True).order_by(DBPersonality.category, DBPersonality.name).all()

@personalities_router.get("/{personality_id}", response_model=PersonalityPublic)
def get_personality(
    personality_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not personality:
        raise HTTPException(status_code=404, detail="Personality not found")
        
    if not personality.is_public and personality.owner_user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to view this personality")
        
    return personality

@personalities_router.post("", response_model=PersonalityPublic, status_code=status.HTTP_201_CREATED)
def create_personality(
    personality_data: PersonalityCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    new_personality = DBPersonality(
        **personality_data.model_dump(),
        owner_user_id=current_user.id
    )
    db.add(new_personality)
    try:
        db.commit()
        db.refresh(new_personality)
        return new_personality
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error creating personality.")

@personalities_router.put("/{personality_id}", response_model=PersonalityPublic)
def update_personality(
    personality_id: str,
    personality_data: PersonalityUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not personality:
        raise HTTPException(status_code=404, detail="Personality not found")
    
    if personality.owner_user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to edit this personality")

    update_dict = personality_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(personality, key, value)

    try:
        db.commit()
        db.refresh(personality)
        return personality
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error updating personality.")

@personalities_router.delete("/{personality_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_personality(
    personality_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not personality:
        raise HTTPException(status_code=404, detail="Personality not found")

    if personality.owner_user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this personality")

    db.delete(personality)
    db.commit()

@personalities_router.post("/{personality_id}/send", status_code=status.HTTP_200_OK)
async def send_personality(
    personality_id: str,
    payload: PersonalitySendRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not personality:
        raise HTTPException(status_code=404, detail="Personality not found")

    target_user = db.query(DBUser).filter(DBUser.username == payload.target_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Target user '{payload.target_username}' not found")

    new_pers = DBPersonality(
        name=personality.name,
        author=f"Shared by {current_user.username}",
        category=personality.category,
        description=personality.description,
        prompt_text=personality.prompt_text,
        icon_base64=personality.icon_base64,
        owner_user_id=target_user.id,
        is_public=False
    )
    db.add(new_pers)
    try:
        db.commit()
        db.refresh(new_pers)
        
        manager.send_personal_message_sync({
            "type": "personality_shared",
            "data": {
                "message": f"🎁 {current_user.username} shared AI persona: {personality.name}",
                "sender_username": current_user.username,
                "sender_icon": current_user.icon,
                "personality_id": new_pers.id,
                "name": new_pers.name,
                "type": "success",
                "duration": 6000
            }
        }, target_user.id)
        
        return {"message": f"Personality successfully sent to {payload.target_username}."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@personalities_router.get("/{personality_id}/export")
def export_personality(
    personality_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not personality:
        raise HTTPException(status_code=404, detail="Personality not found")
        
    export_dict = {
        "name": personality.name,
        "author": personality.author or current_user.username,
        "category": personality.category or "Custom",
        "description": personality.description or "",
        "prompt_text": personality.prompt_text or "",
        "icon_base64": personality.icon_base64,
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("personality.json", json.dumps(export_dict, indent=2))
        
    zip_buffer.seek(0)
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', personality.name)
    filename = f"personality_{safe_name}.zip"
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@personalities_router.post("/import", response_model=PersonalityPublic)
async def import_personality(
    file: UploadFile = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    content_bytes = await file.read()
    try:
        with zipfile.ZipFile(io.BytesIO(content_bytes)) as zip_file:
            json_file = next((f for f in zip_file.namelist() if f.endswith(".json")), None)
            if not json_file:
                raise ValueError("No personality.json found in ZIP archive.")
            data = json.loads(zip_file.read(json_file).decode("utf-8"))
    except zipfile.BadZipFile:
        try:
            data = json.loads(content_bytes.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid personality ZIP or JSON file.")

    new_pers = DBPersonality(
        name=data.get("name", "Imported Persona"),
        author=data.get("author", current_user.username),
        category=data.get("category", "Imported"),
        description=data.get("description", ""),
        prompt_text=data.get("prompt_text", ""),
        icon_base64=data.get("icon_base64"),
        owner_user_id=current_user.id,
        is_public=False
    )
    db.add(new_pers)
    db.commit()
    db.refresh(new_pers)
    return new_pers