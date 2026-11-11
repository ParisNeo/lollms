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


def _active_ttv(db: Session) -> Optional[DBTTVBinding]:
    return db.query(DBTTVBinding).filter(DBTTVBinding.is_active == True).order_by(DBTTVBinding.id).first()


def _active_tti(db: Session) -> Optional[DBTTIBinding]:
    return db.query(DBTTIBinding).filter(DBTTIBinding.is_active == True).order_by(DBTTIBinding.id).first()


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

    # Resolve binding + model. Explicit `model_override` wins (alias/model format).
    ttv_alias = ttv_model = None
    requested = model_override or project.get("model")
    if requested:
        if "/" in requested:
            ttv_alias, ttv_model = requested.split("/", 1)
        else:
            ttv_model = requested

    task.log("Connecting to Text-to-Video engine...")
    task.set_progress(15)

    lc = build_lollms_client_from_params(
        username=username,
        load_llm=False,
        load_ttv=True,
        ttv_binding_alias=ttv_alias,
        ttv_model_name=ttv_model,
    )
    if not getattr(lc, "ttv", None):
        raise Exception("Text-to-Video service is not configured or failed to load.")

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

    try:
        if source_type == "i2v":
            if not first_path or not first_path.exists():
                raise Exception("First-frame image is missing — upload one before rendering.")
            if hasattr(lc.ttv, "generate_video") and callable(lc.ttv.generate_video):
                raw = lc.ttv.generate_video(
                    prompt=prompt,
                    image=str(first_path.resolve()),
                    image_ext="png",
                    **kwargs,
                )
            else:
                raise Exception("Binding does not expose `generate_video`.")

        elif source_type == "flf":
            if not first_path or not last_path or not first_path.exists() or not last_path.exists():
                raise Exception("Both first and last frame images are required for FLF generation.")
            if hasattr(lc.ttv, "supports_first_last_frame") and callable(lc.ttv.supports_first_last_frame):
                if not lc.ttv.supports_first_last_frame():
                    raise Exception(
                        "The active TTV binding does not advertise first-last-frame support."
                    )
            raw = lc.ttv.generate_video_first_and_last_frame(
                prompt=prompt,
                start_image=str(first_path.resolve()),
                end_image=str(last_path.resolve()),
                **kwargs,
            )

        else:  # t2v (default)
            raw = lc.ttv.generate_video(prompt=prompt, **kwargs)

    except HTTPException:
        raise
    except Exception as e:
        trace_exception(e)
        raise Exception(f"Video generation failed: {e}")

    task.log("Encoding finished video file...")
    task.set_progress(90)

    video_bytes = _normalize_bytes(raw)
    if not video_bytes:
        raise Exception("TTV engine returned an empty video stream.")

    video_filename = f"{project_id}.mp4"
    (video_dir / video_filename).write_bytes(video_bytes)

    # Update project metadata (persist the filename + updated timestamp).
    for p in projects:
        if p["id"] == project_id:
            p["video_filename"] = video_filename
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
        "first_image": bool(payload.source_type in ("i2v", "flf")),
        "last_image": bool(payload.source_type == "flf"),
        "video_filename": None,
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
    for suffix in (".mp4", "_first.png", "_last.png"):
        f = video_dir / f"{project_id}{suffix}"
        if f.exists():
            try:
                f.unlink()
            except Exception:
                pass

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


@video_studio_router.post("/projects/{project_id}/first-image")
async def upload_first_image(
    project_id: str,
    file: UploadFile = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    project = _find_project(current_user.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty image.")

    ( _user_video_dir(current_user.username) / f"{project_id}_first.png").write_bytes(content)
    return {"message": "First-frame image uploaded."}


@video_studio_router.post("/projects/{project_id}/last-image")
async def upload_last_image(
    project_id: str,
    file: UploadFile = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    project = _find_project(current_user.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty image.")

    (_user_video_dir(current_user.username) / f"{project_id}_last.png").write_bytes(content)
    return {"message": "Last-frame image uploaded."}


@video_studio_router.get("/projects/{project_id}/first-image")
async def get_first_image(
    project_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    f = _user_video_dir(current_user.username) / f"{project_id}_first.png"
    if not f.exists():
        raise HTTPException(status_code=404, detail="No first-frame image.")
    return FileResponse(str(f), media_type="image/png")


@video_studio_router.get("/projects/{project_id}/last-image")
async def get_last_image(
    project_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
):
    f = _user_video_dir(current_user.username) / f"{project_id}_last.png"
    if not f.exists():
        raise HTTPException(status_code=404, detail="No last-frame image.")
    return FileResponse(str(f), media_type="image/png")


@video_studio_router.post("/generate-image")
async def generate_reference_image(
    payload: GenerateImageRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Light-weight TTI proxy so the studio can synthesise a first/last reference
    image without leaving the video UI. Returns base64-encoded PNG.
    """
    active = _active_tti(db)
    if not active:
        raise HTTPException(status_code=501, detail="No active TTI binding configured.")

    alias = model = None
    if payload.model and "/" in payload.model:
        alias, model = payload.model.split("/", 1)

    lc = build_lollms_client_from_params(
        username=current_user.username,
        load_llm=False,
        load_tti=True,
        tti_binding_alias=alias,
        tti_model_name=model,
    )
    if not getattr(lc, "tti", None):
        raise HTTPException(status_code=500, detail="TTI engine could not be initialized.")

    try:
        raw = lc.tti.generate_image(
            prompt=payload.prompt,
            negative_prompt=payload.negative_prompt or "",
            width=payload.width or 512,
            height=payload.height or 512,
        )
    except TypeError:
        raw = lc.tti.generate_image(prompt=payload.prompt)

    try:
        img_bytes = _normalize_bytes(raw)
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Invalid image payload: {e}")

    return {"b64_image": base64.b64encode(img_bytes).decode("ascii")}