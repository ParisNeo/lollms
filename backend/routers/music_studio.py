# backend/routers/music_studio.py
import os
import json
import uuid
import datetime
import io
import re
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from werkzeug.utils import secure_filename
from ascii_colors import trace_exception, ASCIIColors

from backend.db import get_db
from backend.models import UserAuthDetails, TaskInfo
from backend.session import (
    get_current_active_user, get_user_data_root, 
    build_lollms_client_from_params, get_universal_model_profile
)

music_studio_router = APIRouter(
    prefix="/api/music-studio",
    tags=["Music Studio"],
    dependencies=[Depends(get_current_active_user)]
)
router = music_studio_router

__all__ = ["music_studio_router", "router"]

from backend.task_manager import task_manager, Task

def get_user_music_path(username: str) -> Path:
    safe_uname = secure_filename(username)
    path = get_user_data_root(safe_uname) / "music"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _load_tracks_metadata(username: str) -> List[Dict[str, Any]]:
    meta_path = get_user_music_path(username) / "tracks.json"
    if not meta_path.exists():
        return []
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def _save_tracks_metadata(username: str, tracks: List[Dict[str, Any]]):
    meta_path = get_user_music_path(username) / "tracks.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(tracks, f, indent=2, ensure_ascii=False)

# --- Pydantic Schemas ---

class SongGenerateRequest(BaseModel):
    title: Optional[str] = "Untitled Song"
    prompt: Optional[str] = ""
    lyrics: Optional[str] = ""
    duration: int = Field(default=60, ge=5, le=300)
    instrumental: bool = False
    global_metadata: Optional[str] = ""
    vocal_details: Optional[str] = ""
    arrangement: Optional[str] = ""
    model: Optional[str] = None

class WriteLyricsRequest(BaseModel):
    description: str
    current_lyrics: Optional[str] = None
    genre: Optional[str] = None

class WritePromptRequest(BaseModel):
    description: str
    lyrics: Optional[str] = None

class ExpandIdeaRequest(BaseModel):
    idea: str
    instrumental: bool = False

# --- Background Task Worker ---

def _generate_song_task(task: Task, username: str, request_data: dict):
    task.log(f"Initializing Music Studio generation for '{request_data.get('title', 'Untitled')}'...")
    task.set_progress(10)

    title = request_data.get("title", "Untitled Song").strip() or "Untitled Song"
    lyrics = request_data.get("lyrics", "").strip()
    duration = int(request_data.get("duration", 60))
    instrumental = bool(request_data.get("instrumental", False))
    user_prompt = request_data.get("prompt", "").strip()

    prompt_parts = []
    if user_prompt:
        prompt_parts.append(user_prompt)
    if request_data.get("global_metadata"):
        prompt_parts.append(f"Global Metadata: {request_data.get('global_metadata').strip()}")
    if not instrumental and request_data.get("vocal_details"):
        prompt_parts.append(f"Vocal Details: {request_data.get('vocal_details').strip()}")
    if request_data.get("arrangement"):
        prompt_parts.append(f"Arrangement: {request_data.get('arrangement').strip()}")

    final_prompt = "\n".join(prompt_parts).strip()
    if not final_prompt:
        final_prompt = "A high-fidelity musical track"

    ttm_alias = None
    ttm_model = None
    requested_model = request_data.get("model")
    if requested_model and "/" in requested_model:
        ttm_alias, ttm_model = requested_model.split("/", 1)
    elif requested_model:
        ttm_model = requested_model

    task.log("Connecting to Text-to-Music engine...")
    task.set_progress(25)

    lc = build_lollms_client_from_params(
        username=username,
        load_llm=False,
        load_ttm=True,
        ttm_binding_alias=ttm_alias,
        ttm_model_name=ttm_model
    )

    if not hasattr(lc, "ttm") or not lc.ttm:
        raise Exception("Text-to-Music (TTM) service is not configured or engine failed to load.")

    task.log("Synthesizing audio stems and vocals (this can take 30-90s depending on GPU)...")
    task.set_progress(45)

    audio_bytes = None
    if not instrumental and lyrics:
        if hasattr(lc, "generate_song_from_lyrics") and callable(lc.generate_song_from_lyrics):
            audio_bytes = lc.generate_song_from_lyrics(
                prompt=final_prompt,
                lyrics=lyrics,
                duration=duration
            )
        elif hasattr(lc.ttm, "generate_song_from_lyrics") and callable(lc.ttm.generate_song_from_lyrics):
            audio_bytes = lc.ttm.generate_song_from_lyrics(
                prompt=final_prompt,
                lyrics=lyrics,
                duration=duration
            )

    if not audio_bytes:
        if hasattr(lc, "generate_music") and callable(lc.generate_music):
            audio_bytes = lc.generate_music(prompt=final_prompt, duration=duration)
        elif hasattr(lc.ttm, "generate_music") and callable(lc.ttm.generate_music):
            audio_bytes = lc.ttm.generate_music(prompt=final_prompt, duration=duration)
        elif hasattr(lc.ttm, "generate_audio") and callable(lc.ttm.generate_audio):
            audio_bytes = lc.ttm.generate_audio(prompt=final_prompt, duration=duration)
        elif hasattr(lc.ttm, "generate") and callable(lc.ttm.generate):
            audio_bytes = lc.ttm.generate(prompt=final_prompt, duration=duration)

    if not audio_bytes:
        raise Exception("TTM generator returned empty audio data.")

    if isinstance(audio_bytes, io.BytesIO):
        audio_bytes = audio_bytes.getvalue()
    elif isinstance(audio_bytes, str):
        import base64
        if audio_bytes.startswith("data:"):
            audio_bytes = audio_bytes.split(",", 1)[1]
        audio_bytes = base64.b64decode(audio_bytes)

    task.set_progress(85)
    task.log("Saving audio track to user storage...")

    user_music_dir = get_user_music_path(username)
    track_id = str(uuid.uuid4())
    audio_filename = f"{track_id}.wav"
    audio_path = user_music_dir / audio_filename
    audio_path.write_bytes(audio_bytes)

    new_track = {
        "id": track_id,
        "title": title,
        "prompt": final_prompt,
        "lyrics": lyrics if not instrumental else "",
        "duration": duration,
        "instrumental": instrumental,
        "global_metadata": request_data.get("global_metadata", ""),
        "vocal_details": request_data.get("vocal_details", ""),
        "arrangement": request_data.get("arrangement", ""),
        "audio_url": f"/api/music-studio/tracks/{track_id}/audio",
        "audio_filename": audio_filename,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

    tracks = _load_tracks_metadata(username)
    tracks.insert(0, new_track)
    _save_tracks_metadata(username, tracks)

    task.set_progress(100)
    task.log("Track generation complete!")
    return new_track

# --- Endpoints ---

@music_studio_router.get("/tracks", response_model=List[Dict[str, Any]])
async def get_user_tracks(current_user: UserAuthDetails = Depends(get_current_active_user)):
    """Returns all saved music tracks for the active user."""
    return _load_tracks_metadata(current_user.username)

@music_studio_router.get("/tracks/{track_id}/audio")
async def get_track_audio(
    track_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """Streams the audio waveform file for playback."""
    tracks = _load_tracks_metadata(current_user.username)
    target = next((t for t in tracks if t["id"] == track_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Track not found.")

    audio_path = get_user_music_path(current_user.username) / target.get("audio_filename", f"{track_id}.wav")
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file missing from storage.")

    return FileResponse(
        str(audio_path),
        media_type="audio/wav",
        headers={"Content-Disposition": f'inline; filename="{target["title"]}.wav"'}
    )

@music_studio_router.delete("/tracks/{track_id}")
async def delete_track(
    track_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """Deletes a generated track from user's storage."""
    tracks = _load_tracks_metadata(current_user.username)
    target = next((t for t in tracks if t["id"] == track_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Track not found.")

    audio_path = get_user_music_path(current_user.username) / target.get("audio_filename", f"{track_id}.wav")
    if audio_path.exists():
        try:
            audio_path.unlink()
        except Exception:
            pass

    updated = [t for t in tracks if t["id"] != track_id]
    _save_tracks_metadata(current_user.username, updated)
    return {"message": "Track deleted successfully."}

@music_studio_router.post("/generate", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def generate_song_endpoint(
    payload: SongGenerateRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """Initiates an asynchronous background task to synthesize a song."""
    task = task_manager.submit_task(
        name=f"Generate Song: {payload.title}",
        target=_generate_song_task,
        args=(current_user.username, payload.model_dump()),
        description=f"Synthesizing song '{payload.title}' ({payload.duration}s)...",
        owner_username=current_user.username
    )
    return task

@music_studio_router.post("/write-lyrics", response_model=Dict[str, str])
async def write_lyrics_with_ai(
    payload: WriteLyricsRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """Uses LLM to author complete structured lyrics formatted for MiniMax Music 3."""
    lc = build_lollms_client_from_params(username=current_user.username, load_llm=True)
    if not lc:
        raise HTTPException(status_code=500, detail="LLM engine could not be initialized.")

    system_prompt = """You are a professional songwriter and lyricist specializing in AI song generation (MiniMax Music 3).
Rules:
1. Every section tag MUST sit alone on its own line: [intro], [verse], [pre-chorus], [chorus], [post-chorus], [bridge], [instrumental], [solo], [outro].
2. Words on a tag line are dropped by the audio engine, so never put lyrics or directions on the same line as a tag.
3. Musical directions (tempo, instruments, dynamics) belong in the arrangement, NEVER inside the lyrics.
4. Write expressive, rhythmic, rhyming lyrics that flow naturally across the song progression.
5. Output ONLY the raw lyrics with section tags. No conversational pleasantries or markdown blocks."""

    user_prompt = f"Description/Idea: {payload.description}"
    if payload.genre:
        user_prompt += f"\nGenre/Style: {payload.genre}"
    if payload.current_lyrics:
        user_prompt += f"\nExisting Draft to expand or refine:\n{payload.current_lyrics}"

    try:
        lyrics = lc.generate_text(user_prompt, system_prompt=system_prompt, max_new_tokens=1024, temperature=0.7).strip()
        lyrics = re.sub(r'^```(?:\w+)?\n', '', lyrics)
        lyrics = re.sub(r'\n```$', '', lyrics).strip()
        return {"lyrics": lyrics}
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to generate lyrics: {e}")

@music_studio_router.post("/write-prompt", response_model=Dict[str, str])
async def write_prompt_with_ai(
    payload: WritePromptRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """Uses LLM to architect structured prompt sections matching MiniMax Music 3 guidelines."""
    lc = build_lollms_client_from_params(username=current_user.username, load_llm=True)
    if not lc:
        raise HTTPException(status_code=500, detail="LLM engine could not be initialized.")

    system_prompt = """You are an expert audio producer and prompt engineer for MiniMax Music 3.
Given an idea and optional lyrics, generate three structured prompt fields:
1. GLOBAL_METADATA: genre, BPM (number), key & scale, mood arc, scenario, production quality. (e.g., 'Basic Attributes: bpm is 92. key is F, and scale is major. Contemporary Rap / Hip-Hop Love Ballad. Global Emotional Progression: Opens reflective...')
2. VOCAL_DETAILS: gender, timbre, style per section, harmonies, vocal effects. (e.g., 'Vocal Gender & Timbre: Singer A (Male), smooth tenor with slight rasp. Vocal Style: Conversational in verses...')
3. ARRANGEMENT: instruments per section, groove, bass, textures, spatial fx. (e.g., 'Primary: drum machine, bass synth, electric piano. Secondary: pads in pre-chorus...')

Output strictly valid JSON with keys: 'global_metadata', 'vocal_details', 'arrangement'. No extra text."""

    user_prompt = f"Music Concept: {payload.description}"
    if payload.lyrics:
        user_prompt += f"\nLyrics context:\n{payload.lyrics[:600]}"

    try:
        raw_json = lc.generate_code(user_prompt, system_prompt=system_prompt, language="json").strip()
        if raw_json.startswith("```"):
            raw_json = raw_json.split("\n", 1)[1]
            if raw_json.endswith("```"):
                raw_json = raw_json.rsplit("\n", 1)[0]
        data = json.loads(raw_json)
        return {
            "global_metadata": data.get("global_metadata", ""),
            "vocal_details": data.get("vocal_details", ""),
            "arrangement": data.get("arrangement", "")
        }
    except Exception as e:
        trace_exception(e)
        return {
            "global_metadata": f"Genre: {payload.description}. Tempo: 110 BPM. Key: C Major. Modern polished production.",
            "vocal_details": "Lead expressive vocal with gentle reverb and warm presence.",
            "arrangement": "Drums, bassline, rhythm guitar, atmospheric synth pads."
        }

@music_studio_router.post("/expand-idea", response_model=Dict[str, Any])
async def expand_idea_endpoint(
    payload: ExpandIdeaRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """One-shot helper for Simple Mode: turns a one-line idea into lyrics and complete audio directions."""
    lyrics_res = {"lyrics": ""}
    if not payload.instrumental:
        lyrics_res = await write_lyrics_with_ai(WriteLyricsRequest(description=payload.idea), current_user)
    
    prompt_res = await write_prompt_with_ai(
        WritePromptRequest(description=payload.idea, lyrics=lyrics_res.get("lyrics")), 
        current_user
    )

    return {
        "idea": payload.idea,
        "lyrics": lyrics_res.get("lyrics", ""),
        "global_metadata": prompt_res.get("global_metadata", ""),
        "vocal_details": prompt_res.get("vocal_details", ""),
        "arrangement": prompt_res.get("arrangement", "")
    }