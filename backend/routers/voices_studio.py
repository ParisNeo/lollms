# backend/routers/voices_studio.py
import shutil
import uuid
import io
import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form, Response
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.voice import UserVoice as DBUserVoice
from backend.models import UserAuthDetails
from backend.models.voice import UserVoicePublic, UserVoiceCreate, UserVoiceUpdate, TestTTSRequest
from backend.session import get_current_active_user, get_user_data_root, get_user_lollms_client
from ascii_colors import trace_exception

try:
    from pydub import AudioSegment
    from pydub.effects import speedup
    pydub_available = True
except ImportError:
    pydub_available = False

voices_studio_router = APIRouter(
    prefix="/api/voices-studio",
    tags=["Voices Studio"],
    dependencies=[Depends(get_current_active_user)]
)

def get_user_voices_path(username: str) -> Path:
    path = get_user_data_root(username) / "voices"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _process_audio_effects(input_path: Path, output_path: Path, pitch: float, speed: float, gain: float, reverb_params: Optional[dict]):
    if not pydub_available:
        raise HTTPException(status_code=501, detail="Audio processing library (pydub) is not installed.")
    try:
        sound = AudioSegment.from_file(input_path)

        # 1. Apply Gain (Volume)
        if gain != 0.0:
            sound = sound + gain

        # 2. Apply Speed Change
        if speed != 1.0:
            sound = speedup(sound, playback_speed=speed)

        # 3. Apply Pitch Shift
        if pitch != 1.0:
            octaves = (pitch - 1.0) * 1.0
            new_sample_rate = int(sound.frame_rate * (2.0 ** octaves))
            sound = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
            sound = sound.set_frame_rate(sound.frame_rate)
        
        # 4. Apply Reverb (Simple Delay-based)
        if reverb_params and reverb_params.get("delay", 0) > 0 and reverb_params.get("attenuation", 0.0) > 0.0:
            delay_ms = reverb_params["delay"]
            attenuation_db = reverb_params["attenuation"]
            
            # Create a delayed (quieter) version of the sound
            reverb = sound - attenuation_db
            
            # Overlay it with a delay
            sound = sound.overlay(reverb, position=delay_ms)


        sound.export(output_path, format="wav")
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to apply audio effects: {e}")


@voices_studio_router.get("", response_model=List[UserVoicePublic])
async def get_user_voices(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return db.query(DBUserVoice).filter(DBUserVoice.owner_user_id == current_user.id).order_by(DBUserVoice.alias).all()


@voices_studio_router.post("/upload", response_model=UserVoicePublic)
async def upload_voice(
    alias: str = Form(...),
    language: str = Form("en"),
    pitch: float = Form(1.0),
    speed: float = Form(1.0),
    gain: float = Form(0.0),
    reverb_params_json: str = Form("{}"),
    file: UploadFile = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not file.content_type in ["audio/wav", "audio/mpeg", "audio/x-wav"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a WAV or MP3 file.")

    user_voices_path = get_user_voices_path(current_user.username)
    
    temp_id = str(uuid.uuid4())
    original_suffix = Path(file.filename).suffix if file.filename else '.wav'
    temp_original_path = user_voices_path / f"{temp_id}_original{original_suffix}"
    
    with open(temp_original_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    final_filename = f"{uuid.uuid4().hex}.wav"
    final_path = user_voices_path / final_filename
    
    try:
        reverb_params = json.loads(reverb_params_json)
    except json.JSONDecodeError:
        reverb_params = {}

    _process_audio_effects(temp_original_path, final_path, pitch, speed, gain, reverb_params)
    
    temp_original_path.unlink()

    new_voice = DBUserVoice(
        owner_user_id=current_user.id,
        alias=alias,
        language=language,
        pitch=pitch,
        speed=speed,
        gain=gain,
        reverb_params=reverb_params,
        file_path=final_filename
    )
    db.add(new_voice)
    db.commit()
    db.refresh(new_voice)
    return new_voice


@voices_studio_router.put("/{voice_id}", response_model=UserVoicePublic)
async def update_voice(
    voice_id: str,
    alias: str = Form(...),
    language: str = Form(...),
    pitch: float = Form(...),
    speed: float = Form(1.0),
    gain: float = Form(0.0),
    reverb_params_json: str = Form("{}"),
    file: Optional[UploadFile] = File(None),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    voice_to_update = db.query(DBUserVoice).filter(DBUserVoice.id == voice_id, DBUserVoice.owner_user_id == current_user.id).first()
    if not voice_to_update:
        raise HTTPException(status_code=404, detail="Voice not found.")

    user_voices_path = get_user_voices_path(current_user.username)

    try:
        reverb_params = json.loads(reverb_params_json)
    except json.JSONDecodeError:
        reverb_params = {}

    if file:
        if not file.content_type in ["audio/wav", "audio/mpeg", "audio/x-wav"]:
            raise HTTPException(status_code=400, detail="Invalid file type for update.")
        
        temp_id = str(uuid.uuid4())
        original_suffix = Path(file.filename).suffix
        temp_original_path = user_voices_path / f"{temp_id}_original{original_suffix}"
        
        with open(temp_original_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        final_path = user_voices_path / voice_to_update.file_path
        _process_audio_effects(temp_original_path, final_path, pitch, speed, gain, reverb_params)
        temp_original_path.unlink()
    else:
        # Re-process is needed if any audio parameter changed.
        # This implementation requires storing and re-processing the original.
        # For simplicity, we block this if the original file isn't found.
        # A robust implementation would store original uploads separately.
        raise HTTPException(status_code=400, detail="To change audio effects, you must re-upload the original audio file.")

    voice_to_update.alias = alias
    voice_to_update.language = language
    voice_to_update.pitch = pitch
    voice_to_update.speed = speed
    voice_to_update.gain = gain
    voice_to_update.reverb_params = reverb_params
    db.commit()
    db.refresh(voice_to_update)
    return voice_to_update


@voices_studio_router.delete("/{voice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voice(
    voice_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    voice_to_delete = db.query(DBUserVoice).filter(DBUserVoice.id == voice_id, DBUserVoice.owner_user_id == current_user.id).first()
    if not voice_to_delete:
        raise HTTPException(status_code=404, detail="Voice not found.")
    
    user_voices_path = get_user_voices_path(current_user.username)
    file_path = user_voices_path / voice_to_delete.file_path
    if file_path.exists():
        file_path.unlink()
        
    db.delete(voice_to_delete)
    db.commit()


@voices_studio_router.post("/set-active/{voice_id}", response_model=UserAuthDetails)
async def set_active_voice(
    voice_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    voice_to_set = db.query(DBUserVoice).filter(DBUserVoice.id == voice_id, DBUserVoice.owner_user_id == current_user.id).first()
    if not voice_to_set:
        raise HTTPException(status_code=404, detail="Voice not found.")
        
    user_db = db.query(DBUser).filter(DBUser.id == current_user.id).first()
    user_db.active_voice_id = voice_id
    db.commit()
    db.refresh(user_db)
    
    current_user.active_voice_id = voice_id
    return current_user


@voices_studio_router.post("/test")
async def test_voice(
    request: TestTTSRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    voice = db.query(DBUserVoice).filter(DBUserVoice.id == request.voice_id, DBUserVoice.owner_user_id == current_user.id).first()
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found.")

    user_voices_path = get_user_voices_path(current_user.username)
    voice_file_path = user_voices_path / voice.file_path
    
    if not voice_file_path.exists():
         raise HTTPException(status_code=404, detail="Voice file not found on disk.")
         
    lc = get_user_lollms_client(current_user.username)
    if not lc.tts:
        raise HTTPException(status_code=400, detail="TTS service is not configured for your account.")

    try:
        temp_test_file_path = user_voices_path / f"test_{uuid.uuid4().hex}.wav"
        
        reverb_params = {
            "delay": request.reverb_delay,
            "attenuation": request.reverb_attenuation
        }
        
        _process_audio_effects(voice_file_path, temp_test_file_path, request.pitch, request.speed, request.gain, reverb_params)

        audio_bytes = lc.tts.generate_audio(text=request.text, voice=str(temp_test_file_path.resolve()))
        
        temp_test_file_path.unlink()

        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {e}")


@voices_studio_router.post("/{voice_id}/duplicate", response_model=UserVoicePublic)
async def duplicate_voice(
    voice_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    original_voice = db.query(DBUserVoice).filter(DBUserVoice.id == voice_id, DBUserVoice.owner_user_id == current_user.id).first()
    if not original_voice:
        raise HTTPException(status_code=404, detail="Voice to duplicate not found.")
        
    user_voices_path = get_user_voices_path(current_user.username)
    original_file_path = user_voices_path / original_voice.file_path
    if not original_file_path.exists():
        raise HTTPException(status_code=404, detail="Original voice file not found on disk, cannot duplicate.")
        
    new_filename = f"{uuid.uuid4().hex}.wav"
    new_file_path = user_voices_path / new_filename
    shutil.copy(original_file_path, new_file_path)

    new_voice = DBUserVoice(
        owner_user_id=current_user.id,
        alias=f"{original_voice.alias} (Copy)",
        language=original_voice.language,
        file_path=new_filename,
        pitch=original_voice.pitch,
        speed=original_voice.speed,
        gain=original_voice.gain,
        reverb_params=original_voice.reverb_params
    )
    db.add(new_voice)
    db.commit()
    db.refresh(new_voice)
    return new_voice