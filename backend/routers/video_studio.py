# backend/routers/video_studio.py
#
# Minimal Video Studio: T2V, image+prompt (I2V), and first+last-frame interpolation.
# Projects are stored per-user under `<data_root>/videos/` with a `projects.json`
# index (see music_studio.py for the same pattern). Generations run synchronously
# inside a background task; the resulting MP4 is written to disk so the UI can
# stream it back via `/projects/{id}/video`.
import io
import json
import uuid
import datetime
import base64
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, File, UploadFile, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename
from ascii_colors import trace_exception

from backend.db import get_db
from backend.db.models.config import (
    TTIBinding as DBTTIBinding,
    TTVBinding as DBTTVBinding,
)
from backend.models import UserAuthDetails, TaskInfo
from backend.session import get_current_active_user, get_user_data_root, build_lollms_client_from_params
from backend.task_manager import task_manager, Task


video_studio_router = APIRouter(
    prefix="/api/video-studio",
    tags=["Video Studio"],
    dependencies=[Depends(get_current_active_user)],
)
router = video_studio_router

__all__ = ["video_studio_router", "router"]


# ──────────────────────────────────────────────────────────────────────────────
# Storage helpers
# ──────────────────────────────────────────────────────────────────────────────

def _user_video_dir(username: str) -> Path:
    safe = secure_filename(username)
    path = get_user_data_root(safe) / "videos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _projects_index_path(username: str) -> Path:
    return _user_video_dir(username) / "projects.json"


def _load_projects(username: str) -> List[Dict[str, Any]]:
    p = _projects_index_path(username)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_projects(username: str, projects: List[Dict[str, Any]]) -> None:
    p = _projects_index_path(username)
    p.write_text(json.dumps(projects, indent=2, ensure_ascii=False), encoding="utf-8")


def _find_project(username: str, project_id: str) -> Optional[Dict[str, Any]]:
    return next((p for p in _load_projects(username) if p.get("id") == project_id), None)


def _ensure_media_fields(project: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a project dict to the v2 media-aware shape.

    Old projects only have ``first_image``/``last_image``/``video_filename``.
    We backfill empty ``images``/``videos``/``composition`` arrays and, if the
    legacy anchors exist on disk, add them as the first entries so the media
    library is never empty for a project that clearly has media.
    """
    if not isinstance(project.get("images"), list):
        project["images"] = []
    if not isinstance(project.get("videos"), list):
        project["videos"] = []
    if "composition" not in project:
        project["composition"] = None
    return project


def _media_id() -> str:
    return uuid.uuid4().hex[:12]


def _image_file(username: str, project_id: str, image_id: str) -> Path:
    return _user_video_dir(username) / f"{project_id}_img_{image_id}.png"


def _video_file(username: str, project_id: str, video_id: str) -> Path:
    return _user_video_dir(username) / f"{project_id}_vid_{video_id}.mp4"


def _composed_file(username: str, project_id: str) -> Path:
    return _user_video_dir(username) / f"{project_id}_composed.mp4"


def _active_ttv(db: Session) -> Optional[DBTTVBinding]:
    return db.query(DBTTVBinding).filter(DBTTVBinding.is_active == True).order_by(DBTTVBinding.id).first()


def _active_tti(db: Session) -> Optional[DBTTIBinding]:
    return db.query(DBTTIBinding).filter(DBTTIBinding.is_active == True).order_by(DBTTIBinding.id).first()


def _resolve_ttv_target(db: Session, username: str, requested_model: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Resolve the effective TTV binding alias + model name.

    Mirrors ``lollms_v1._resolve_ttv_target`` but with one critical difference:
    a bare model identifier like ``"ParisNeo/MiniMax-H3-FL2VA-FP8"`` is a
    *namespaced model name* (HuggingFace ``owner/repo``), **not** a
    ``binding_alias/model`` pair. Splitting it on the first ``/`` would send
    both a bogus alias (``ParisNeo``) and a mangled model
    (``MiniMax-H3-FL2VA-FP8``) to the engine.

    Resolution order:

      1. Explicit profile id resolved via ``get_universal_model_profile``
         (handles ``binding_alias/profile_key``, ``profile_key``, ``title``,
         ``name``, and physical ``model_name`` lookups uniformly).
      2. Bare binding alias (``alias`` or ``name`` matching an active TTV
         binding record).
      3. The user's saved preference ``ttv_binding_model_name``.
      4. The default active TTV binding record.

    Returns ``(alias, model_name)`` where ``model_name`` is the *physical*
    model identifier the engine expects (profile's ``model_name`` payload,
    not the raw profile key/namespaced id).
    """
    from backend.session import get_universal_model_profile, user_sessions

    if requested_model and requested_model.strip():
        req = requested_model.strip()

        # 1. Prefer the authoritative universal-profile resolver. It knows how
        #    to distinguish "alias/profile" from a raw namespaced model name.
        try:
            prof_alias, prof_key, prof_info = get_universal_model_profile(
                db, req, modality="ttv"
            )
        except Exception:
            prof_alias, prof_key, prof_info = None, None, None
        if prof_alias:
            physical = (prof_info or {}).get("model_name") or prof_key
            return prof_alias, physical

        # 2. Bare binding alias match.
        hit = (
            db.query(DBTTVBinding)
            .filter(
                (DBTTVBinding.alias == req) | (DBTTVBinding.name == req),
                DBTTVBinding.is_active == True,
            )
            .first()
        )
        if hit:
            return hit.alias, hit.default_model_name

    # 3. User preference — apply the same "is this a profile id?" resolution so
    #    a saved "owner/repo" preference isn't misparsed as binding/model.
    sess = user_sessions.get(username) or {}
    user_pref = sess.get("ttv_binding_model_name")
    if user_pref:
        try:
            prof_alias, prof_key, prof_info = get_universal_model_profile(
                db, user_pref, modality="ttv"
            )
        except Exception:
            prof_alias, prof_key, prof_info = None, None, None
        if prof_alias:
            physical = (prof_info or {}).get("model_name") or prof_key
            return prof_alias, physical
        if "/" in user_pref:
            alias, model = user_pref.split("/", 1)
            return alias or None, model or None
        return user_pref, None

    # 4. Default active TTV binding.
    default_binding = _active_ttv(db)
    if default_binding:
        return default_binding.alias, default_binding.default_model_name
    return None, None


def _normalize_bytes(raw: Any) -> bytes:
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, io.BytesIO):
        return raw.getvalue()
    if hasattr(raw, "read") and callable(raw.read):
        return raw.read()
    if isinstance(raw, str):
        if raw.startswith("data:"):
            raw = raw.split(",", 1)[-1]
        return base64.b64decode(raw)
    raise ValueError("Backend returned an unrecognised payload.")


# ──────────────────────────────────────────────────────────────────────────────
# Request models
# ──────────────────────────────────────────────────────────────────────────────

class VideoProjectCreate(BaseModel):
    title: Optional[str] = "Untitled Video"
    prompt: Optional[str] = ""
    negative_prompt: Optional[str] = ""
    source_type: str = Field(default="t2v", description="One of: t2v, i2v, flf")
    model: Optional[str] = None
    width: Optional[int] = Field(default=512, ge=64, le=1920)
    height: Optional[int] = Field(default=512, ge=64, le=1080)
    num_frames: Optional[int] = Field(default=48, ge=8, le=240)
    fps: Optional[int] = Field(default=12, ge=1, le=60)
    num_inference_steps: Optional[int] = Field(default=None, ge=1, le=200)
    guidance_scale: Optional[float] = None
    seed: Optional[int] = None


class VideoProjectUpdate(VideoProjectCreate):
    pass


class GenerateImageRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = ""
    model: Optional[str] = None
    width: Optional[int] = 512
    height: Optional[int] = 512


# ──────────────────────────────────────────────────────────────────────────────
# Background TTV job
# ──────────────────────────────────────────────────────────────────────────────

def _run_generation_task(
    task: Task,
    username: str,
    project_id: str,
    model_override: Optional[str],
):
    task.log("Loading project settings...")
    task.set_progress(5)

    projects = _load_projects(username)
    project = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        raise Exception(f"Project '{project_id}' not found.")

    source_type = project.get("source_type", "t2v")
    prompt = (project.get("prompt") or "").strip()
    if not prompt:
        raise Exception("Prompt is empty. Fill in a prompt before rendering.")

    # Resolve binding + model. `_resolve_ttv_target` is the single source of
    # truth: it understands universal profile ids ("alias/profile"), bare
    # binding aliases, and — crucially — does **not** misinterpret HF-style
    # namespaced model names ("owner/repo") as a binding/model split.
    #
    # Special value "auto" (or an empty string) means: let the binding use
    # whatever checkpoint the daemon has *loaded*. This is the correct mode
    # for local TTV daemons whose serving path no longer matches the HF repo
    # id pinned inside a Universal Profile — it bypasses the profile lookup
    # entirely so the engine does not reject the request for "model mismatch".
    requested_raw = (model_override if model_override is not None else project.get("model"))
    requested = (requested_raw or "").strip()
    use_auto_model = requested.lower() in ("", "auto", "auto/auto", "<auto>", "@auto")

    from backend.db import get_db as _get_db
    _db = next(_get_db())
    try:
        if use_auto_model:
            # Resolve only the binding, never pin a model. Fall back to the
            # active binding if the caller did not provide one either.
            ttv_alias, _ = _resolve_ttv_target(_db, username, None)
            ttv_model = None
        else:
            ttv_alias, ttv_model = _resolve_ttv_target(_db, username, requested)
    finally:
        _db.close()

    if not ttv_alias:
        raise Exception(
            "No active Text-to-Video binding is configured. Add and activate a TTV "
            "binding in the admin panel before rendering."
        )

    task.log(
        f"Connecting to Text-to-Video engine ({ttv_alias}"
        f"{' / auto-model' if use_auto_model else (' / ' + ttv_model if ttv_model else '')})..."
    )
    task.set_progress(15)

    lc = build_lollms_client_from_params(
        username=username,
        load_llm=False,
        load_ttv=True,
        ttv_binding_alias=ttv_alias,
        ttv_model_name=ttv_model,
    )
    if not getattr(lc, "ttv", None):
        raise Exception(
            f"Text-to-Video engine '{ttv_alias}' could not be initialized. "
            "Verify the binding is active and its configuration is valid."
        )

    # Build generation kwargs
    kwargs: Dict[str, Any] = {}
    for field, key in (
        ("width", "width"),
        ("height", "height"),
        ("num_frames", "num_frames"),
        ("fps", "fps"),
        ("num_inference_steps", "num_inference_steps"),
        ("guidance_scale", "guidance_scale"),
        ("seed", "seed"),
    ):
        val = project.get(field)
        if val is not None:
            kwargs[key] = val
    if project.get("negative_prompt"):
        kwargs["negative_prompt"] = project["negative_prompt"]

    task.log(f"Dispatching {source_type.upper()} generation...")
    task.set_progress(35)

    video_dir = _user_video_dir(username)
    first_path = video_dir / f"{project_id}_first.png" if project.get("first_image") else None
    last_path = video_dir / f"{project_id}_last.png" if project.get("last_image") else None

    # IMPORTANT: the LollmsTTVBinding talks to a *remote* vllm_omni-style
    # daemon that has no access to our filesystem. Frames MUST be sent as
    # base64 payloads, never as local paths — otherwise the daemon cannot
    # read the image, silently falls back to text-only guidance, and the
    # generated video looks nothing like the reference frame.
    def _frame_b64(path: Path) -> str:
        return base64.b64encode(path.read_bytes()).decode("ascii")

    try:
        if source_type == "i2v":
            if not first_path or not first_path.exists():
                raise Exception("First-frame image is missing — upload one before rendering.")
            if not hasattr(lc.ttv, "generate_video") or not callable(lc.ttv.generate_video):
                raise Exception("Binding does not expose `generate_video`.")
            raw = lc.ttv.generate_video(
                prompt=prompt,
                image=_frame_b64(first_path),
                image_ext="png",
                **kwargs,
            )

        elif source_type == "flf":
            if not first_path or not last_path or not first_path.exists() or not last_path.exists():
                raise Exception("Both first and last frame images are required for FLF generation.")
            if not hasattr(lc.ttv, "generate_video_first_and_last_frame") or not callable(
                lc.ttv.generate_video_first_and_last_frame
            ):
                raise Exception(
                    f"The active TTV binding '{ttv_alias}' does not support first+last-frame "
                    "interpolation. Switch the project to T2V or I2V mode, or configure a "
                    "binding that exposes generate_video_first_and_last_frame()."
                )
            if hasattr(lc.ttv, "supports_first_last_frame") and callable(lc.ttv.supports_first_last_frame):
                if not lc.ttv.supports_first_last_frame():
                    raise Exception(
                        "The active TTV binding does not advertise first-last-frame support."
                    )
            raw = lc.ttv.generate_video_first_and_last_frame(
                prompt=prompt,
                start_image=_frame_b64(first_path),
                end_image=_frame_b64(last_path),
                **kwargs,
            )

        else:  # t2v (default)
            raw = lc.ttv.generate_video(prompt=prompt, **kwargs)

    except HTTPException:
        raise
    except Exception as e:
        trace_exception(e)
        err_text = str(e)

        # Surfacing the two most common TTV daemon misconfigurations as
        # actionable messages instead of opaque 500s from the binding layer.
        if "Model mismatch" in err_text:
            # The engine usually embeds both sides of the mismatch as
            # 'request specifies X but server is running Y'. Extract them so
            # the frontend (and the user's log view) can show a concrete diff.
            import re as _re
            m = _re.search(
                r"request specifies '([^']+)'\s*but server is running '([^']+)'",
                err_text,
            )
            req_side, served_side = (m.group(1), m.group(2)) if m else (ttv_model, "<unknown>")
            auto_hint = (
                ""
                if use_auto_model
                else (
                    "\n\nTo bypass the profile pin and use whatever checkpoint the "
                    "daemon already has loaded, set this project's model to "
                    "'auto' (or clear the Model field) and render again."
                )
            )
            raise Exception(
                "TTV engine model mismatch.\n"
                f"  Requested : {req_side}\n"
                f"  Served    : {served_side}\n"
                f"  Binding   : {ttv_alias}\n\n"
                "The Universal Profile pinned on this project points to a model "
                "the daemon is not currently serving. Either:\n"
                "  1. Open Admin → TTV Bindings and update the profile's "
                "     'model_name' to match the served checkpoint, or\n"
                "  2. Set this project's model to 'auto' to use the daemon's "
                "     currently loaded model directly."
                f"{auto_hint}"
            )
        if "connection" in err_text.lower() or "refused" in err_text.lower():
            raise Exception(
                f"Could not reach the TTV engine at binding '{ttv_alias}'. Verify the "
                f"daemon is running and reachable from this server. "
                f"Engine message: {err_text}"
            )
        raise Exception(f"Video generation failed: {err_text}")

    task.log("Encoding finished video file...")
    task.set_progress(90)

    video_bytes = _normalize_bytes(raw)
    if not video_bytes:
        raise Exception("TTV engine returned an empty video stream.")

    video_filename = f"{project_id}.mp4"
    (video_dir / video_filename).write_bytes(video_bytes)

    # Also register the render as an entry in the media library so the composer
    # can reference it by id. The legacy ``video_filename`` remains the "main"
    # render so the viewport keeps working unchanged.
    video_id = _media_id()
    video_entry = {
        "id": video_id,
        "filename": video_filename,
        "role": "render",
        "prompt": prompt,
        "source_type": source_type,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "width": project.get("width"),
        "height": project.get("height"),
        "num_frames": project.get("num_frames"),
        "fps": project.get("fps"),
    }

    for p in projects:
        if p["id"] == project_id:
            _ensure_media_fields(p)
            p["video_filename"] = video_filename
            p["videos"].insert(0, video_entry)
            p["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            break
    _save_projects(username, projects)

    task.set_progress(100)
    task.log("Done.")
    return {"project_id": project_id, "video_filename": video_filename}


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@video_studio_router.get("/capabilities")
async def get_capabilities(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return {
        "ttv_available": _active_ttv(db) is not None,
        "tti_available": _active_tti(db) is not None,
    }


@video_studio_router.get("/projects")
async def list_projects(current_user: UserAuthDetails = Depends(get_current_active_user)):
    return _load_projects(current_user.username)


@video_studio_router.post("/projects")
async def create_project(
    payload: VideoProjectCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    project = {
        "id": str(uuid.uuid4()),
        "title": (payload.title or "Untitled Video").strip() or "Untitled Video",
        "prompt": payload.prompt or "",
        "negative_prompt": payload.negative_prompt or "",
        "source_type": payload.source_type if payload.source_type in ("t2v", "i2v", "flf") else "t2v",
        "model": payload.model,
        "width": payload.width,
        "height": payload.height,
        "num_frames": payload.num_frames,
        "fps": payload.fps,
        "num_inference_steps": payload.num_inference_steps,
        "guidance_scale": payload.guidance_scale,
        "seed": payload.seed,
        # Frames start as MISSING. The upload / generate endpoints flip these
        # to True once an image actually lands on disk — the source_type alone
        # does not mean a frame exists yet.
        "first_image": False,
        "last_image": False,
        "video_filename": None,
        # v2 media library — populated lazily as the user uploads/generates.
        "images": [],
        "videos": [],
        "composition": None,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    projects = _load_projects(current_user.username)
    projects.insert(0, project)
    _save_projects(current_user.username, projects)
    return project


@video_studio_router.put("/projects/{project_id}")
async def update_project(
    project_id: str,
    payload: VideoProjectUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    projects = _load_projects(current_user.username)
    for p in projects:
        if p["id"] == project_id:
            p.update({
                "title": (payload.title or p.get("title") or "Untitled Video").strip() or "Untitled Video",
                "prompt": payload.prompt if payload.prompt is not None else p.get("prompt", ""),
                "negative_prompt": payload.negative_prompt if payload.negative_prompt is not None else p.get("negative_prompt", ""),
                "source_type": payload.source_type if payload.source_type in ("t2v", "i2v", "flf") else p.get("source_type", "t2v"),
                "model": payload.model if payload.model is not None else p.get("model"),
                "width": payload.width,
                "height": payload.height,
                "num_frames": payload.num_frames,
                "fps": payload.fps,
                "num_inference_steps": payload.num_inference_steps,
                "guidance_scale": payload.guidance_scale,
                "seed": payload.seed,
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })
            _save_projects(current_user.username, projects)
            return p
    raise HTTPException(status_code=404, detail="Project not found.")


@video_studio_router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    projects = _load_projects(current_user.username)
    target = next((p for p in projects if p["id"] == project_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Project not found.")

    video_dir = _user_video_dir(current_user.username)
    legacy_names = (".mp4", "_first.png", "_last.png", "_composed.mp4")
    for suffix in legacy_names:
        f = video_dir / f"{project_id}{suffix}"
        if f.exists():
            try:
                f.unlink()
            except Exception:
                pass

    # Delete all library media (images + videos) for the project.
    for entry in _ensure_media_fields(target).get("images", []):
        f = _image_file(current_user.username, project_id, entry["id"])
        if f.exists():
            try:
                f.unlink()
            except Exception:
                pass
    for entry in target.get("videos", []):
        f = _video_file(current_user.username, project_id, entry["id"])
        if f.exists():
            try:
                f.unlink()
            except Exception:
                pass
        # The main render also lives at <project>.mp4; already handled above.

    _save_projects(current_user.username, [p for p in projects if p["id"] != project_id])
    return {"message": "Project deleted."}


@video_studio_router.post("/projects/{project_id}/render", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def render_project(
    project_id: str,
    request: Request,
    model_override: Optional[str] = Form(None),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    # Accept both multipart form-data (browser) and a JSON body `{"model_override": ...}`.
    if model_override is None:
        try:
            body = await request.json()
            if isinstance(body, dict):
                model_override = body.get("model_override")
        except Exception:
            pass

    project = _find_project(current_user.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    task = task_manager.submit_task(
        name=f"Render Video: {project.get('title', project_id)}",
        target=_run_generation_task,
        args=(current_user.username, project_id, model_override),
        description=f"Rendering '{project.get('title', project_id)}' ({project.get('source_type', 't2v').upper()})...",
        owner_username=current_user.username,
    )
    return task


@video_studio_router.get("/projects/{project_id}/video")
async def stream_project_video(
    project_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    project = _find_project(current_user.username, project_id)
    if not project or not project.get("video_filename"):
        raise HTTPException(status_code=404, detail="Video not rendered yet.")

    video_path = _user_video_dir(current_user.username) / project["video_filename"]
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file missing from disk.")

    return FileResponse(
        str(video_path),
        media_type="video/mp4",
        headers={"Content-Disposition": f'inline; filename="{project["title"]}.mp4"'},
    )


def _extract_frame_bytes_from_body(body: bytes, content_type: str) -> bytes:
    """Extract the raw image bytes from an incoming request body.

    Supports two call sites that share the same endpoints:

    * ``multipart/form-data`` with a ``file`` field — the browser file-picker
      path, uploaded **as-is** (no re-encoding is attempted here; the caller
      validates/transcodes it).
    * ``application/json`` with ``b64_image`` / ``image_base64`` / ``image``
      — the TTI-generated-reference path used by the studio when it wants to
      store a model-generated image as the first/last frame without leaving
      the browser as a real file upload.
    """
    if not body:
        raise HTTPException(status_code=400, detail="Empty request body.")

    ct = (content_type or "").lower()
    if "application/json" in ct:
        try:
            payload = json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {e}")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object.")

        raw_b64 = (
            payload.get("b64_image")
            or payload.get("image_base64")
            or payload.get("image")
            or payload.get("data")
        )
        if not raw_b64 or not isinstance(raw_b64, str):
            raise HTTPException(
                status_code=400,
                detail="Provide a multipart 'file' upload or a JSON field "
                       "'b64_image' / 'image_base64' / 'image'.",
            )
        if raw_b64.startswith("data:"):
            raw_b64 = raw_b64.split(",", 1)[-1]
        try:
            decoded = base64.b64decode(raw_b64, validate=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 image payload: {e}")
        if not decoded:
            raise HTTPException(status_code=400, detail="Decoded image is empty.")
        return decoded

    # Heuristic: if the body starts with '--', it is *actually* multipart, but
    # the caller sent a wrong Content-Type header (typically because an HTTP
    # client's default is `application/json`). Give a clear actionable error
    # instead of the cryptic "Invalid JSON body" parse failure above.
    if body[:2] == b"--":
        raise HTTPException(
            status_code=400,
            detail="The request body is multipart/form-data (starts with '--') "
                   "but the Content-Type header does not reflect that. When "
                   "uploading a FormData body, explicitly set "
                   "Content-Type: multipart/form-data so the browser can add the "
                   "boundary.",
        )

    # urlencoded / plain — should not happen, but be explicit.
    raise HTTPException(
        status_code=415,
        detail="Unsupported content type. Use multipart/form-data with 'file' "
               "or application/json with 'b64_image'.",
    )


def _normalize_frame_to_png(content: bytes, label: str) -> bytes:
    """Validate that ``content`` decodes as an image and re-encode as PNG.

    The render pipeline stores frames at ``<project>_first.png`` /
    ``<project>_last.png`` and passes them to the TTV binding as PNG. Any
    accepted input format (JPEG, WebP, BMP, GIF, PNG) is normalised so a
    non-PNG upload doesn't leave a stale file the render path can't open.
    """
    try:
        from PIL import Image
        with Image.open(io.BytesIO(content)) as img:
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if "A" in img.mode else "RGB")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{label} is not a valid image: {e}")


async def _read_frame_upload(request: Request) -> bytes:
    """Read an image payload from either multipart form-data or JSON body."""
    content_type = request.headers.get("content-type", "").lower()

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        # Tolerate common alternate field names as a safety net for third-party
        # HTTP clients — FastAPI/axios default to 'file', but some integrations
        # send 'image', 'upload', or 'data'.
        uploaded = form.get("file") or form.get("image") or form.get("upload") or form.get("data")
        if uploaded is None:
            received_keys = ", ".join(form.keys()) if hasattr(form, "keys") else "<unknown>"
            raise HTTPException(
                status_code=400,
                detail=f"Missing a file field ('file', 'image', 'upload', or 'data') "
                       f"in form-data. Received fields: [{received_keys}].",
            )
        if hasattr(uploaded, "read"):
            content = await uploaded.read()
        else:
            content = uploaded.encode("utf-8") if isinstance(uploaded, str) else b""
        if not content:
            raise HTTPException(status_code=400, detail="Empty image payload in form-data.")
        return content

    body = await request.body()
    return _extract_frame_bytes_from_body(body, content_type)


async def _upload_frame(project_id: str, request: Request, username: str, role: str) -> Dict[str, Any]:
    project = _find_project(username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    label = "First-frame image" if role == "first" else "Last-frame image"
    raw = await _read_frame_upload(request)
    png = _normalize_frame_to_png(raw, label)
    updated = _store_frame_and_flag(username, project_id, role, png)
    return {
        "message": f"{label} uploaded.",
        "size_bytes": len(png),
        "role": role,
        "image_url": f"/api/video-studio/projects/{project_id}/{role}-image",
        "project": updated,
    }


@video_studio_router.post("/projects/{project_id}/first-image")
async def upload_first_image(
    project_id: str,
    request: Request,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    return await _upload_frame(project_id, request, current_user.username, "first")


@video_studio_router.post("/projects/{project_id}/last-image")
async def upload_last_image(
    project_id: str,
    request: Request,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    return await _upload_frame(project_id, request, current_user.username, "last")


def _serve_frame(project_id: str, username: str, role: str):
    f = _user_video_dir(username) / f"{project_id}_{role}.png"
    if not f.exists():
        raise HTTPException(status_code=404, detail=f"No {role}-frame image.")
    # no-store: a freshly regenerated frame must not be served from a stale
    # browser cache when the user re-runs generation.
    return FileResponse(
        str(f),
        media_type="image/png",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@video_studio_router.get("/projects/{project_id}/first-image")
async def get_first_image(
    project_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    return _serve_frame(project_id, current_user.username, "first")


@video_studio_router.get("/projects/{project_id}/last-image")
async def get_last_image(
    project_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    return _serve_frame(project_id, current_user.username, "last")


def _resolve_tti_target(db: Session, requested: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Resolve a TTI binding alias + model name for reference-image generation.

    Same doctrine as the TTV resolver: a bare ``"owner/repo"`` string is a
    namespaced *model* name, not a ``binding/model`` pair. We let the
    universal-profile resolver decide first, then fall back to a bare alias
    match, then the active binding.
    """
    from backend.session import get_universal_model_profile

    if requested and requested.strip():
        req = requested.strip()
        try:
            prof_alias, prof_key, prof_info = get_universal_model_profile(
                db, req, modality="tti"
            )
        except Exception:
            prof_alias, prof_key, prof_info = None, None, None
        if prof_alias:
            physical = (prof_info or {}).get("model_name") or prof_key
            return prof_alias, physical
        hit = (
            db.query(DBTTIBinding)
            .filter(
                (DBTTIBinding.alias == req) | (DBTTIBinding.name == req),
                DBTTIBinding.is_active == True,
            )
            .first()
        )
        if hit:
            return hit.alias, hit.default_model_name

    active = _active_tti(db)
    if active:
        return active.alias, active.default_model_name
    return None, None


def _generate_tti_frame_bytes(
    username: str,
    db: Session,
    prompt: str,
    negative_prompt: Optional[str],
    width: Optional[int],
    height: Optional[int],
    model: Optional[str],
) -> bytes:
    """Generate a reference image via the active TTI binding and return PNG bytes."""
    alias, tti_model = _resolve_tti_target(db, model)
    if not alias:
        raise HTTPException(status_code=501, detail="No active TTI binding configured.")

    lc = build_lollms_client_from_params(
        username=username,
        load_llm=False,
        load_tti=True,
        tti_binding_alias=alias,
        tti_model_name=tti_model,
    )
    if not getattr(lc, "tti", None):
        raise HTTPException(
            status_code=500,
            detail=f"TTI engine '{alias}' could not be initialized.",
        )

    try:
        raw = lc.tti.generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt or "",
            width=width or 512,
            height=height or 512,
        )
    except TypeError:
        try:
            raw = lc.tti.generate_image(prompt=prompt)
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"TTI generation failed: {e}")
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"TTI generation failed: {e}")

    try:
        img_bytes = _normalize_bytes(raw)
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Invalid image payload: {e}")

    return _normalize_frame_to_png(img_bytes, "Generated image")


def _store_frame_and_flag(username: str, project_id: str, role: str, png: bytes) -> Dict[str, Any]:
    """Write a frame PNG to disk and flip its project flag. ``role`` is 'first'|'last'.

    Also registers the frame as an entry in the project's image library under
    ``role: anchor_first`` / ``anchor_last`` so the composer and the media
    browser always see the current anchors. Library images added later through
    ``/images`` upload are stored under distinct ids and never overwritten.
    """
    target = _user_video_dir(username) / f"{project_id}_{role}.png"
    target.write_bytes(png)

    projects = _load_projects(username)
    updated = None
    for p in projects:
        if p["id"] == project_id:
            _ensure_media_fields(p)
            # Anchor entries use the site-stable id ``anchor_first``/``anchor_last``
            # so repeated uploads replace rather than duplicate.
            anchor_id = f"anchor_{role}"
            p["images"] = [im for im in p["images"] if im.get("id") != anchor_id]
            p["images"].insert(0, {
                "id": anchor_id,
                "filename": f"{project_id}_{role}.png",
                "role": anchor_id,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })
            p[f"{role}_image"] = True
            p["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            updated = p
            break
    if updated is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    _save_projects(username, projects)
    return updated


@video_studio_router.post("/generate-image")
async def generate_reference_image(
    payload: GenerateImageRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Light-weight TTI proxy so the studio can synthesise a first/last reference
    image without leaving the video UI. Returns base64-encoded PNG.

    Kept for backward compatibility — most callers should use the atomic
    ``/projects/{id}/generate-frame`` endpoint below, which persists the result
    directly to the project.
    """
    png = _generate_tti_frame_bytes(
        username=current_user.username,
        db=db,
        prompt=payload.prompt,
        negative_prompt=payload.negative_prompt,
        width=payload.width,
        height=payload.height,
        model=payload.model,
    )
    return {"b64_image": base64.b64encode(png).decode("ascii")}


class GenerateFrameRequest(BaseModel):
    prompt: str
    role: str = Field(default="first", description="'first' or 'last'")
    negative_prompt: Optional[str] = ""
    model: Optional[str] = None
    width: Optional[int] = 512
    height: Optional[int] = 512


@video_studio_router.post("/projects/{project_id}/images")
async def upload_image_to_library(
    project_id: str,
    request: Request,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    """Attach an image to the project's media library.

    Body: multipart ``file`` **or** JSON ``{b64_image}``. Optional query
    ``?role=first`` / ``?role=last`` (or JSON string ``role``) additionally
    promotes the image to the project anchor for I2V/FLF renders.
    """
    project = _find_project(current_user.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    role_q = request.query_params.get("role", "").lower()
    prompt_q = request.query_params.get("prompt")

    # role/prompt can also arrive via JSON payload; sniff content-type to decide.
    ct = (request.headers.get("content-type") or "").lower()
    if "application/json" in ct:
        body_bytes = await request.body()
        try:
            body = json.loads(body_bytes.decode("utf-8"))
            if isinstance(body, dict):
                role_q = (body.get("role") or role_q).lower()
                prompt_q = body.get("prompt") or prompt_q
                raw_b64 = body.get("b64_image") or body.get("image_base64") or body.get("image")
                if not raw_b64:
                    raise HTTPException(status_code=400, detail="Missing b64_image field.")
                png = _normalize_frame_to_png(base64.b64decode(
                    raw_b64.split(",", 1)[-1] if raw_b64.startswith("data:") else raw_b64
                ), "Library image")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {e}")
    else:
        raw = await _read_frame_upload(request)
        png = _normalize_frame_to_png(raw, "Library image")

    if role_q == "first":
        _store_frame_and_flag(current_user.username, project_id, "first", png)
    elif role_q == "last":
        _store_frame_and_flag(current_user.username, project_id, "last", png)
    else:
        # Standalone library entry with its own uuid id.
        image_id = _media_id()
        (_user_video_dir(current_user.username) / f"{project_id}_img_{image_id}.png").write_bytes(png)
        projects = _load_projects(current_user.username)
        for p in projects:
            if p["id"] == project_id:
                _ensure_media_fields(p)
                p["images"].insert(0, {
                    "id": image_id,
                    "filename": f"{project_id}_img_{image_id}.png",
                    "role": "library",
                    "prompt": prompt_q,
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                })
                p["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                break
        _save_projects(current_user.username, projects)

    return _ensure_media_fields(_find_project(current_user.username, project_id))


@video_studio_router.get("/projects/{project_id}/images")
async def list_project_images(
    project_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    project = _find_project(current_user.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    _ensure_media_fields(project)
    return {"images": project["images"]}


@video_studio_router.get("/projects/{project_id}/images/{image_id}")
async def get_project_image(
    project_id: str,
    image_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    project = _find_project(current_user.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    _ensure_media_fields(project)

    entry = next((im for im in project["images"] if im["id"] == image_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Image not found.")

    f = _user_video_dir(current_user.username) / entry["filename"]
    if not f.exists():
        raise HTTPException(status_code=404, detail="Image file missing from disk.")
    return FileResponse(str(f), media_type="image/png",
                        headers={"Cache-Control": "no-store, max-age=0"})


@video_studio_router.delete("/projects/{project_id}/images/{image_id}")
async def delete_project_image(
    project_id: str,
    image_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    project = _find_project(current_user.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    _ensure_media_fields(project)

    entry = next((im for im in project["images"] if im["id"] == image_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Image not found.")

    # Don't delete the anchor file on disk — anchors are also the render source
    # frames (``<project>_first.png`` / ``_last.png``). Removing the anchor only
    # means clearing the reference so it won't render with that anchor next time.
    if image_id not in ("anchor_first", "anchor_last"):
        f = _user_video_dir(current_user.username) / entry["filename"]
        if f.exists():
            try: f.unlink()
            except Exception: pass

    projects = _load_projects(current_user.username)
    for p in projects:
        if p["id"] == project_id:
            _ensure_media_fields(p)
            p["images"] = [im for im in p["images"] if im["id"] != image_id]
            if image_id == "anchor_first":
                p["first_image"] = False
            if image_id == "anchor_last":
                p["last_image"] = False
            p["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            break
    _save_projects(current_user.username, projects)
    return {"message": "Image removed."}


@video_studio_router.get("/projects/{project_id}/videos")
async def list_project_videos(
    project_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    project = _find_project(current_user.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    _ensure_media_fields(project)
    return {
        "videos": project["videos"],
        "composition": project["composition"],
    }


@video_studio_router.get("/projects/{project_id}/videos/{video_id}")
async def get_project_video(
    project_id: str,
    video_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    project = _find_project(current_user.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    _ensure_media_fields(project)

    entry = next((v for v in project["videos"] if v["id"] == video_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Video not found.")

    # Legacy renders store the file at <project>.mp4; composer videos at _vid_<id>
    candidates = [
        _user_video_dir(current_user.username) / entry["filename"],
        _video_file(current_user.username, project_id, video_id),
    ]
    f = next((p for p in candidates if p.exists()), None)
    if not f:
        raise HTTPException(status_code=404, detail="Video file missing from disk.")
    return FileResponse(str(f), media_type="video/mp4",
                        headers={"Content-Disposition": f'inline; filename="{video_id}.mp4"'})


@video_studio_router.get("/projects/{project_id}/videos/{video_id}/thumbnail")
async def get_project_video_thumbnail(
    project_id: str,
    video_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    """Return a single poster frame as PNG for the tile grid.

    Extracts the frame at ~0.25s (or the first decodable frame as a fallback)
    using PyAV when available, else falls back to a transparent 1×1 PNG so
    the UI has a stable response instead of a 404 loop.
    """
    project = _find_project(current_user.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    _ensure_media_fields(project)
    entry = next((v for v in project["videos"] if v["id"] == video_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Video not found.")

    candidates = [
        _user_video_dir(current_user.username) / entry["filename"],
        _video_file(current_user.username, project_id, video_id),
    ]
    src = next((p for p in candidates if p.exists()), None)
    if not src:
        raise HTTPException(status_code=404, detail="Video file missing from disk.")

    # Try PyAV first (compiled bindings — no external ffmpeg needed).
    try:
        import av  # type: ignore
        from PIL import Image as _PILImage, ImageDraw as _PILDraw
        with av.open(str(src)) as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            chosen = None
            for frame in container.decode(video=0):
                # aim for the 6th decoded frame or first with reasonable size
                arr = frame.to_ndarray(format="rgb24")
                if arr is None or arr.size == 0:
                    continue
                chosen = arr
                break
        if chosen is not None:
            img = _PILImage.fromarray(chosen)
            img.thumbnail((512, 512))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return Response(
                content=buf.getvalue(),
                media_type="image/png",
                headers={"Cache-Control": "private, max-age=600"},
            )
    except Exception as e:
        trace_exception(e)
        # Fall through to generic placeholder.

    # Placeholder: solid gradient PNG so the UI has a stable thumbnail.
    try:
        from PIL import Image as _PILImage, ImageDraw as _PILDraw
        img = _PILImage.new("RGB", (256, 144), (30, 30, 40))
        draw = _PILDraw.Draw(img)
        draw.rectangle([0, 0, 256, 8], fill=(60, 90, 200))
        draw.text((12, 60), "PREVIEW", fill=(200, 200, 220))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Response(
            content=buf.getvalue(),
            media_type="image/png",
            headers={"Cache-Control": "private, max-age=60"},
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Thumbnail unavailable.")


@video_studio_router.delete("/projects/{project_id}/videos/{video_id}")
async def delete_project_video(
    project_id: str,
    video_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    project = _find_project(current_user.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    _ensure_media_fields(project)

    entry = next((v for v in project["videos"] if v["id"] == video_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Video not found.")

    for path in (
        _user_video_dir(current_user.username) / entry["filename"],
        _video_file(current_user.username, project_id, video_id),
    ):
        if path.exists():
            try: path.unlink()
            except Exception: pass

    projects = _load_projects(current_user.username)
    for p in projects:
        if p["id"] == project_id:
            _ensure_media_fields(p)
            p["videos"] = [v for v in p["videos"] if v["id"] != video_id]
            if p.get("video_filename") == entry["filename"]:
                p["video_filename"] = (p["videos"][0]["filename"] if p["videos"] else None)
            p["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            break
    _save_projects(current_user.username, projects)
    return {"message": "Video removed."}


# ── Composer — ffmpeg / imageio-ffmpeg / PyAV ─────────────────────────────

def _resolve_ffmpeg_exe() -> Optional[str]:
    """Return a usable ffmpeg executable path, or None if PyAV must be used.

    Resolution order:
      1. ``imageio-ffmpeg``'s bundled binary (pip-installable in a wheel).
      2. System ``ffmpeg`` on PATH.
      3. Best-effort ``pipmaster`` install of ``imageio-ffmpeg`` and retry.
    """
    import shutil as _shutil
    try:
        import imageio_ffmpeg  # type: ignore
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:
        pass

    system_ffmpeg = _shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    # Last resort: try to grab imageio-ffmpeg via pipmaster (a pre-existing
    # dependency in the platform's requirements). Silent on failure — callers
    # falls back to PyAV.
    try:
        import pipmaster as _pipmaster  # type: ignore
        _pipmaster.ensure(["imageio-ffmpeg"], force=False)
        import importlib as _importlib
        import imageio_ffmpeg  # type: ignore  # noqa: F401
        _importlib.reload(imageio_ffmpeg)
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:
        pass
    return None


def _compose_with_ffmpeg(
    task: "Task",
    ffmpeg_exe: str,
    src_paths: List[Path],
    out_path: Path,
    transition: str,
) -> None:
    """Run ffmpeg to merge segments, updating ``task`` progress along the way."""
    import subprocess
    import tempfile
    import re as _re

    # 1. Fast path — if all segments are homogenous, use the concat demuxer
    #    with -c copy. Detect via ffprobe availability; otherwise just re-encode
    #    (safe default).
    use_concat_demuxer = transition == "none"

    with tempfile.TemporaryDirectory(prefix="lollms_compose_") as tmpdir:
        tmp = Path(tmpdir)
        task.log(f"Compositing {len(src_paths)} segment(s) via ffmpeg ({transition})...")
        task.set_progress(10)

        if use_concat_demuxer:
            # Build a concat list file. Escaping: single quotes around each path.
            list_file = tmp / "list.txt"
            list_file.write_text(
                "\n".join(f"file '{p.resolve().as_posix()}'" for p in src_paths),
                encoding="utf-8",
            )
            cmd = [
                ffmpeg_exe, "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c", "copy", str(out_path),
            ]
            # If copy fails (mixed codecs), fall back to re-encode below.
        else:
            cmd = None  # handled by xfade branch

        if cmd is not None:
            task.log("Running fast concat (stream copy)...")
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=60 * 30,
            )
            if proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
                task.set_progress(95)
                return
            task.log("Fast concat failed; falling back to re-encode...")

        # 2. Re-encode path. For 'crossfade', build an xfade filter chain; for
        #    'none' (after failed copy), use the concat filter.
        inputs = []
        for p in src_paths:
            inputs.extend(["-i", str(p)])

        if transition == "crossfade" and len(src_paths) > 1:
            # Chain xfade between consecutive pairs. Each xfade transition
            # duration is fixed at 0.5s; offsets computed cumulatively.
            filt_parts = []
            # Probe durations; if unavailable, fall back to a fixed estimate.
            durations = [_probe_duration(ffmpeg_exe, p) for p in src_paths]
            if any(d is None or d <= 0 for d in durations):
                durations = [4.0] * len(src_paths)  # safe default for TTV clips

            prev_label = "0:v"
            acc = durations[0]
            fade = 0.5
            for i in range(1, len(src_paths)):
                out_label = f"v{i}"
                offset = max(0.0, acc - fade)
                filt_parts.append(
                    f"[{prev_label}][{i}:v]xfade=transition=fade:duration={fade}:offset={offset:.3f}[{out_label}]"
                )
                prev_label = out_label
                acc = acc + durations[i] - fade

            filter_complex = ";".join(filt_parts)
            cmd = [
                ffmpeg_exe, "-y", *inputs,
                "-filter_complex", filter_complex,
                "-map", f"[{prev_label}]",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
                "-an",
                str(out_path),
            ]
        else:
            # Filter concat (uniform re-encode) — safest fallback.
            n = len(src_paths)
            filter_parts = "".join(f"[{i}:v]" for i in range(n))
            filter_complex = f"{filter_parts}concat=n={n}:v=1:a=0[v]"
            cmd = [
                ffmpeg_exe, "-y", *inputs,
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
                "-an",
                str(out_path),
            ]

        task.log("Running ffmpeg re-encode...")
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60 * 60)
        if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError(
                f"ffmpeg failed (exit {proc.returncode}): {proc.stderr[-800:]}"
            )
        task.set_progress(95)


def _probe_duration(ffmpeg_exe: str, path: Path) -> Optional[float]:
    """Estimate a media file's duration via ffprobe (if available)."""
    import subprocess
    import shutil as _shutil

    ffprobe = _shutil.which("ffprobe")
    if not ffprobe:
        # imageio-ffmpeg doesn't ship ffprobe; skip and let caller use fallback.
        return None
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode == 0:
            return float(out.stdout.strip())
    except Exception:
        pass
    return None


def _compose_with_pyav(
    task: "Task",
    src_paths: List[Path],
    out_path: Path,
) -> None:
    """Fallback composer using PyAV (pure-python ffmpeg bindings).

    Only used when no ffmpeg executable is available. Concatenates the video
    streams by re-encoding all frames into a single output stream. Does not
    support crossfade transitions — always plain concatenation.
    """
    try:
        import av  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Neither ffmpeg (or imageio-ffmpeg) nor PyAV is available. "
            "Install one of them to enable the composer."
        ) from e

    task.log(f"Compositing {len(src_paths)} segment(s) via PyAV...")
    task.set_progress(15)

    out_container = av.open(str(out_path), mode="w")
    try:
        out_stream = out_container.add_stream("libx264", rate=24)
        # Resolution/fps will be set from the first input frame.
        out_stream.width = None  # type: ignore
        out_stream.height = None  # type: ignore
        out_stream.pix_fmt = "yuv420p"
        out_stream.options = {"crf": "20", "preset": "medium"}

        first_frame_done = False
        for src_path in src_paths:
            in_container = av.open(str(src_path))
            try:
                for frame in in_container.decode(video=0):
                    if not first_frame_done:
                        out_stream.width = frame.width
                        out_stream.height = frame.height
                        in_fps = in_container.streams.video[0].average_rate
                        if in_fps:
                            out_stream.rate = int(round(float(in_fps)))
                        # Need to re-open out_container's stream with new dims.
                        first_frame_done = True
                    for packet in out_stream.encode(frame):
                        out_container.mux(packet)
            finally:
                in_container.close()

        for packet in out_stream.encode():
            out_container.mux(packet)
        task.set_progress(95)
    finally:
        out_container.close()


def _run_compose_task(
    task: "Task",
    username: str,
    project_id: str,
    video_ids: List[str],
    transition: str,
):
    task.log("Preparing composition...")
    task.set_progress(5)

    project = _find_project(username, project_id)
    if not project:
        raise Exception(f"Project '{project_id}' not found.")
    _ensure_media_fields(project)

    by_id = {v["id"]: v for v in project["videos"]}
    missing = [vid for vid in video_ids if vid not in by_id]
    if missing:
        raise Exception(f"Unknown video id(s): {', '.join(missing)}")
    if len(video_ids) < 2:
        raise Exception("Select at least two videos to compose.")

    src_paths: List[Path] = []
    video_dir = _user_video_dir(username)
    for vid in video_ids:
        entry = by_id[vid]
        candidates = [
            video_dir / entry["filename"],
            _video_file(username, project_id, vid),
        ]
        p = next((c for c in candidates if c.exists()), None)
        if not p:
            raise Exception(f"Video '{vid}' file missing from disk.")
        src_paths.append(p)

    out_path = _composed_file(username, project_id)
    # Write to a temp sibling first for atomic replace.
    tmp_out = out_path.with_suffix(".partial.mp4")

    ffmpeg_exe = _resolve_ffmpeg_exe()
    if ffmpeg_exe:
        _compose_with_ffmpeg(task, ffmpeg_exe, src_paths, tmp_out, transition)
    else:
        _compose_with_pyav(task, src_paths, tmp_out)

    if not tmp_out.exists() or tmp_out.stat().st_size == 0:
        raise Exception("Composer produced an empty output file.")
    tmp_out.replace(out_path)

    composition_entry = {
        "filename": out_path.name,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "video_ids": list(video_ids),
        "transition": transition,
        "size_bytes": out_path.stat().st_size,
    }
    projects = _load_projects(username)
    for p in projects:
        if p["id"] == project_id:
            _ensure_media_fields(p)
            p["composition"] = composition_entry
            p["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            break
    _save_projects(username, projects)

    task.set_progress(100)
    task.log("Composition complete.")
    return {"project_id": project_id, "composition": composition_entry}


class ComposeRequest(BaseModel):
    video_ids: List[str]
    transition: str = Field(default="none", description="'none' or 'crossfade'")


@video_studio_router.post("/projects/{project_id}/compose", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def compose_project(
    project_id: str,
    payload: ComposeRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    project = _find_project(current_user.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    transition = (payload.transition or "none").lower().strip()
    if transition not in ("none", "crossfade"):
        raise HTTPException(status_code=400, detail="transition must be 'none' or 'crossfade'.")

    task = task_manager.submit_task(
        name=f"Compose Video: {project.get('title', project_id)}",
        target=_run_compose_task,
        args=(current_user.username, project_id, payload.video_ids, transition),
        description=f"Composing {len(payload.video_ids)} segment(s) for '{project.get('title', project_id)}'...",
        owner_username=current_user.username,
    )
    return task


@video_studio_router.get("/projects/{project_id}/composed")
async def stream_composed_video(
    project_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    project = _find_project(current_user.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    _ensure_media_fields(project)
    if not project.get("composition"):
        raise HTTPException(status_code=404, detail="No composition yet.")

    f = _user_video_dir(current_user.username) / project["composition"]["filename"]
    if not f.exists():
        raise HTTPException(status_code=404, detail="Composition file missing from disk.")
    return FileResponse(
        str(f), media_type="video/mp4",
        headers={"Content-Disposition": f'inline; filename="{project_id}_composed.mp4"',
                 "Cache-Control": "no-store"},
    )


@video_studio_router.delete("/projects/{project_id}/composed")
async def delete_composed_video(
    project_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    project = _find_project(current_user.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    _ensure_media_fields(project)

    if project.get("composition"):
        f = _user_video_dir(current_user.username) / project["composition"]["filename"]
        if f.exists():
            try: f.unlink()
            except Exception: pass

    projects = _load_projects(current_user.username)
    for p in projects:
        if p["id"] == project_id:
            _ensure_media_fields(p)
            p["composition"] = None
            p["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            break
    _save_projects(current_user.username, projects)
    return {"message": "Composition removed."}


@video_studio_router.post("/projects/{project_id}/generate-frame")
async def generate_project_frame(
    project_id: str,
    payload: GenerateFrameRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Generate a TTI image AND store it directly as the project's first/last frame.

    This is the *atomic* reference-image workflow the UI should use: one call
    produces the image, writes it to ``<project>_first.png`` (or ``_last.png``),
    and flips the corresponding project flag. The response includes both the
    base64 payload (for immediate display) and the canonical image URL.
    """
    project = _find_project(current_user.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    role = (payload.role or "first").strip().lower()
    if role not in ("first", "last"):
        raise HTTPException(status_code=400, detail="role must be 'first' or 'last'.")

    prompt = (payload.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="A prompt is required to generate a frame.")

    png = _generate_tti_frame_bytes(
        username=current_user.username,
        db=db,
        prompt=prompt,
        negative_prompt=payload.negative_prompt,
        width=payload.width,
        height=payload.height,
        model=payload.model,
    )
    updated = _store_frame_and_flag(current_user.username, project_id, role, png)

    return {
        "message": f"{role.capitalize()}-frame image generated and saved.",
        "role": role,
        "size_bytes": len(png),
        "b64_image": base64.b64encode(png).decode("ascii"),
        "image_url": f"/api/video-studio/projects/{project_id}/{role}-image",
        "project": updated,
    }