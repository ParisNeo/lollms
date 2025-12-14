# [UPDATE] backend/routers/voices_studio.py
# backend/routers/voices_studio.py
import shutil
import uuid
import io
import json
import base64
from pathlib import Path
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.voice import UserVoice as DBUserVoice
from backend.models import UserAuthDetails
from backend.models.voice import UserVoicePublic, UserVoiceCreate, UserVoiceUpdate, TestTTSRequest, ApplyEffectsRequest
from backend.session import get_current_active_user, get_user_data_root, build_lollms_client_from_params
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

def _process_audio_effects(input_path: Path, output_path: Path, pitch: float, speed: float, gain: float, reverb_params: Optional[dict], trim_start: Optional[float] = None, trim_end: Optional[float] = None):
    if not pydub_available:
        raise HTTPException(status_code=501, detail="Audio processing library (pydub) is not installed.")
    try:
        sound = AudioSegment.from_file(input_path)

        # 1. Apply Trim
        if trim_start is not None and trim_end is not None:
            start_ms = int(trim_start * 1000)
            end_ms = int(trim_end * 1000)
            sound = sound[start_ms:end_ms]

        # 2. Apply Gain (Volume)
        if gain != 0.0:
            sound = sound + gain

        # 3. Apply Speed Change
        if speed != 1.0:
            if abs(pitch - 1.0) < 0.01:
                sound = speedup(sound, playback_speed=speed)
            else:
                octaves = (pitch - 1.0) * 1.0
                new_sample_rate = int(sound.frame_rate * (2.0 ** octaves) * speed)
                sound = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
                sound = sound.set_frame_rate(sound.frame_rate)
        elif pitch != 1.0:
            octaves = (pitch - 1.0) * 1.0
            new_sample_rate = int(sound.frame_rate * (2.0 ** octaves))
            sound = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
            sound = sound.set_frame_rate(sound.frame_rate)


        # 4. Apply Reverb (simplified, as pydub lacks a proper reverb effect)
        if reverb_params and reverb_params.get("delay", 0) > 0 and reverb_params.get("attenuation", 0.0) > 0.0:
            delay_ms = reverb_params["delay"]
            attenuation_db = reverb_params["attenuation"]
            reverb = sound - attenuation_db
            sound = sound.overlay(reverb, position=delay_ms)

        sound.export(output_path, format="wav")
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to apply audio effects: {e}")

@voices_studio_router.get("", response_model=List[UserVoicePublic])
async def get_user_voices(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return db.query(DBUserVoice).filter(DBUserVoice.owner_user_id == current_user.id).order_by(DBUserVoice.alias).all()

@voices_studio_router.get("/{voice_id}/audio")
async def get_voice_audio(voice_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    voice = db.query(DBUserVoice).filter(DBUserVoice.id == voice_id, DBUserVoice.owner_user_id == current_user.id).first()
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found.")
    
    user_voices_path = get_user_voices_path(current_user.username)
    file_path = user_voices_path / voice.file_path
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found on disk.")
    
    # FIX: Return raw binary content with the correct MIME type
    try:
        with open(file_path, "rb") as f:
            audio_content = f.read()
        return Response(content=audio_content, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read audio file: {e}")


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
    user_voices_path = get_user_voices_path(current_user.username)
    
    is_temp_file = False
    if file.filename == 'blob' and file.content_type == 'audio/wav':
        temp_original_path = user_voices_path / f"{uuid.uuid4()}_editor_upload.wav"
        with open(temp_original_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        is_temp_file = True
    else:
        if not file.content_type in ["audio/wav", "audio/mpeg", "audio/x-wav"]:
            raise HTTPException(status_code=400, detail="Invalid file type.")
        
        temp_id = str(uuid.uuid4())
        original_suffix = Path(file.filename).suffix if file.filename else '.wav'
        temp_original_path = user_voices_path / f"{temp_id}_original{original_suffix}"
        with open(temp_original_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        is_temp_file = True

    final_filename = f"{uuid.uuid4().hex}.wav"
    final_path = user_voices_path / final_filename
    
    try:
        reverb_params = json.loads(reverb_params_json)
    except json.JSONDecodeError:
        reverb_params = {}

    _process_audio_effects(temp_original_path, final_path, pitch, speed, gain, reverb_params)
    if is_temp_file:
        temp_original_path.unlink()

    new_voice = DBUserVoice(
        owner_user_id=current_user.id, alias=alias, language=language,
        pitch=pitch, speed=speed, gain=gain, reverb_params=reverb_params,
        file_path=final_filename
    )
    db.add(new_voice); db.commit(); db.refresh(new_voice)
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
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    voice_to_update = db.query(DBUserVoice).filter(DBUserVoice.id == voice_id, DBUserVoice.owner_user_id == current_user.id).first()
    if not voice_to_update:
        raise HTTPException(status_code=404, detail="Voice not found.")

    user_voices_path = get_user_voices_path(current_user.username)
    original_file_path = user_voices_path / voice_to_update.file_path
    
    if not original_file_path.exists():
        raise HTTPException(status_code=404, detail="Original audio file not found. Cannot apply effects.")

    try:
        reverb_params = json.loads(reverb_params_json)
    except json.JSONDecodeError:
        reverb_params = {}
    
    temp_output_path = user_voices_path / f"temp_{voice_to_update.file_path}"
    _process_audio_effects(original_file_path, temp_output_path, pitch, speed, gain, reverb_params)
    shutil.move(str(temp_output_path), str(original_file_path))

    voice_to_update.alias = alias
    voice_to_update.language = language
    voice_to_update.pitch = pitch
    voice_to_update.speed = speed
    voice_to_update.gain = gain
    voice_to_update.reverb_params = reverb_params
    db.commit()
    db.refresh(voice_to_update)
    return voice_to_update

@voices_studio_router.post("/{voice_id}/replace_audio", response_model=UserVoicePublic)
async def replace_voice_audio(
    voice_id: str,
    file: UploadFile = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    voice_to_update = db.query(DBUserVoice).filter(DBUserVoice.id == voice_id, DBUserVoice.owner_user_id == current_user.id).first()
    if not voice_to_update:
        raise HTTPException(status_code=404, detail="Voice not found.")

    if not file.content_type in ["audio/wav", "audio/mpeg", "audio/x-wav"]:
        raise HTTPException(status_code=400, detail="Invalid file type.")

    user_voices_path = get_user_voices_path(current_user.username)
    target_path = user_voices_path / voice_to_update.file_path
    
    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        db.commit()
        db.refresh(voice_to_update)
        return voice_to_update
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to replace audio file: {e}")


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


@voices_studio_router.post("/test", response_model=Dict[str, str])
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
         
    lc = build_lollms_client_from_params(username=current_user.username, load_llm=False, load_tts=True)
    if not lc.tts:
        raise HTTPException(status_code=400, detail="TTS service is not configured for your account.")

    try:
        temp_test_file_path = user_voices_path / f"test_{uuid.uuid4().hex}.wav"
        
        reverb_params_dict = request.reverb_params.model_dump() if request.reverb_params else {}
        
        _process_audio_effects(
            voice_file_path, temp_test_file_path, 
            request.pitch, request.speed, request.gain, 
            reverb_params_dict
        )

        language_to_use = request.language or voice.language 
        
        audio_bytes = lc.tts.generate_audio(
            text=request.text, 
            voice=str(temp_test_file_path.resolve()),
            language=language_to_use
        )
        
        temp_test_file_path.unlink()

        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        return {"audio_b64": audio_b64}

    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {e}")

@voices_studio_router.post("/apply-effects", response_model=Dict[str, str])
async def apply_effects_to_audio(
    request: ApplyEffectsRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    user_voices_path = get_user_voices_path(current_user.username)
    temp_input_path = user_voices_path / f"temp_in_{uuid.uuid4().hex}.wav"
    temp_output_path = user_voices_path / f"temp_out_{uuid.uuid4().hex}.wav"

    try:
        audio_data = base64.b64decode(request.audio_b64)
        with open(temp_input_path, "wb") as f:
            f.write(audio_data)

        _process_audio_effects(
            temp_input_path, temp_output_path, request.pitch, request.speed, request.gain, 
            request.reverb_params.model_dump() if request.reverb_params else None, request.trim_start, request.trim_end
        )

        with open(temp_output_path, "rb") as f:
            processed_audio_bytes = f.read()
        
        processed_audio_b64 = base64.b64encode(processed_audio_bytes).decode('utf-8')
        return {"audio_b64": processed_audio_b64}
    finally:
        temp_input_path.unlink(missing_ok=True)
        temp_output_path.unlink(missing_ok=True)


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
