# backend/routers/voices_studio.py
import shutil
import uuid
import io
import json
import base64
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename
from ascii_colors import trace_exception

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.voice import UserVoice as DBUserVoice
from backend.models import UserAuthDetails
from backend.models.voice import UserVoicePublic, UserVoiceCreate, UserVoiceUpdate, TestTTSRequest, ApplyEffectsRequest
from backend.session import get_current_active_user, get_user_data_root, build_lollms_client_from_params
from backend.generation.tts import _clean_text_for_tts

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

class SynthesizeTTSRequest(TestTTSRequest):
    voice_id: Optional[str] = None
    model: Optional[str] = None

def get_user_voices_path(username: str) -> Path:
    safe_uname = secure_filename(username)
    path = get_user_data_root(safe_uname) / "voices"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _normalize_audio_bytes(raw_output: Any) -> bytes:
    if isinstance(raw_output, bytes):
        return raw_output
    if hasattr(raw_output, 'read') and callable(raw_output.read):
        return raw_output.read()
    if isinstance(raw_output, io.BytesIO):
        return raw_output.getvalue()
    if isinstance(raw_output, str):
        if raw_output.startswith("data:audio"):
            b64_part = raw_output.split(",", 1)[1] if "," in raw_output else raw_output
            return base64.b64decode(b64_part)
        file_p = Path(raw_output)
        if file_p.exists() and file_p.is_file():
            return file_p.read_bytes()
        try:
            return base64.b64decode(raw_output)
        except Exception:
            pass
    raise ValueError("TTS engine did not return valid audio data.")

def _process_audio_effects(
    input_path: Path,
    output_path: Path,
    pitch: float,
    speed: float,
    gain: float,
    reverb_params: Optional[dict],
    trim_start: Optional[float] = None,
    trim_end: Optional[float] = None
):
    if not pydub_available:
        if (trim_start is None and trim_end is None and abs(pitch - 1.0) < 0.01 and abs(speed - 1.0) < 0.01 and abs(gain) < 0.01 and not reverb_params):
            shutil.copyfile(input_path, output_path)
            return
        raise HTTPException(status_code=501, detail="Audio processing library (pydub) is not installed.")
    try:
        sound = AudioSegment.from_file(input_path)

        if trim_start is not None and trim_end is not None and trim_end > trim_start:
            start_ms = int(trim_start * 1000)
            end_ms = int(trim_end * 1000)
            sound = sound[start_ms:end_ms]

        if gain != 0.0:
            sound = sound + gain

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

        if reverb_params and reverb_params.get("delay", 0) > 0 and reverb_params.get("attenuation", 0.0) > 0.0:
            delay_ms = int(reverb_params["delay"])
            attenuation_db = float(reverb_params["attenuation"])
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
    safe_fn = secure_filename(voice.file_path)
    file_path = (user_voices_path / safe_fn).resolve()
    if not file_path.is_relative_to(user_voices_path) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found on disk.")

    try:
        with open(file_path, "rb") as f:
            audio_content = f.read()
        return Response(content=audio_content, media_type="audio/wav", headers={"Cache-Control": "no-cache"})
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
    clean_alias = alias.strip()
    if not clean_alias:
        raise HTTPException(status_code=400, detail="Voice alias cannot be empty.")

    is_temp_file = False
    temp_id = str(uuid.uuid4())
    temp_original_path = user_voices_path / f"upload_temp_{temp_id}.wav"

    try:
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

        new_voice = DBUserVoice(
            owner_user_id=current_user.id,
            alias=clean_alias,
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
    finally:
        if is_temp_file and temp_original_path.exists():
            temp_original_path.unlink(missing_ok=True)
        file.file.close()

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
    safe_fn = secure_filename(voice_to_update.file_path)
    original_file_path = user_voices_path / safe_fn

    if not original_file_path.exists():
        raise HTTPException(status_code=404, detail="Original audio file not found. Cannot apply effects.")

    try:
        reverb_params = json.loads(reverb_params_json)
    except json.JSONDecodeError:
        reverb_params = {}

    temp_output_path = user_voices_path / f"temp_{uuid.uuid4().hex}.wav"
    try:
        _process_audio_effects(original_file_path, temp_output_path, pitch, speed, gain, reverb_params)
        shutil.move(str(temp_output_path), str(original_file_path))
    finally:
        temp_output_path.unlink(missing_ok=True)

    voice_to_update.alias = alias.strip()
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

    user_voices_path = get_user_voices_path(current_user.username)
    safe_fn = secure_filename(voice_to_update.file_path)
    target_path = user_voices_path / safe_fn

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        db.commit()
        db.refresh(voice_to_update)
        return voice_to_update
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to replace audio file: {e}")
    finally:
        file.file.close()

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
    safe_fn = secure_filename(voice_to_delete.file_path)
    file_path = user_voices_path / safe_fn
    if file_path.exists():
        file_path.unlink(missing_ok=True)

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
    request: SynthesizeTTSRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Synthesizes speech from text using the active TTS service and optionally applies custom voice reference & effects.
    """
    clean_prompt = _clean_text_for_tts(request.text)
    if not clean_prompt:
        raise HTTPException(status_code=400, detail="Text to synthesize cannot be empty.")

    lc = build_lollms_client_from_params(username=current_user.username, load_llm=False, load_tts=True)
    if not lc.tts:
        raise HTTPException(status_code=400, detail="Text-to-Speech (TTS) service is not configured or active.")

    user_voices_path = get_user_voices_path(current_user.username)
    voice_file_path = None
    language_to_use = request.language or "en"

    if request.voice_id:
        voice = db.query(DBUserVoice).filter(DBUserVoice.id == request.voice_id, DBUserVoice.owner_user_id == current_user.id).first()
        if voice:
            safe_fn = secure_filename(voice.file_path)
            candidate = user_voices_path / safe_fn
            if candidate.exists():
                voice_file_path = candidate
                if not request.language:
                    language_to_use = voice.language

    temp_test_file_path = None
    effective_voice_path_str = None

    try:
        if voice_file_path:
            reverb_params_dict = request.reverb_params.model_dump() if request.reverb_params else {}
            needs_fx = (
                abs((request.pitch or 1.0) - 1.0) > 0.01 or
                abs((request.speed or 1.0) - 1.0) > 0.01 or
                abs(request.gain or 0.0) > 0.01 or
                bool(reverb_params_dict)
            )

            if needs_fx and pydub_available:
                temp_test_file_path = user_voices_path / f"test_{uuid.uuid4().hex}.wav"
                _process_audio_effects(
                    voice_file_path, temp_test_file_path,
                    request.pitch or 1.0, request.speed or 1.0, request.gain or 0.0,
                    reverb_params_dict
                )
                effective_voice_path_str = str(temp_test_file_path.resolve())
            else:
                effective_voice_path_str = str(voice_file_path.resolve())

        # Generate audio via active TTS engine
        raw_audio = lc.tts.generate_audio(
            text=clean_prompt,
            voice=effective_voice_path_str,
            language=language_to_use
        )

        audio_bytes = _normalize_audio_bytes(raw_audio)
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        return {"audio_b64": audio_b64}

    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {str(e)}")
    finally:
        if temp_test_file_path and temp_test_file_path.exists():
            temp_test_file_path.unlink(missing_ok=True)

@voices_studio_router.post("/test", response_model=Dict[str, str])
async def test_voice(
    request: SynthesizeTTSRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Synthesizes speech from text using the active TTS service and optionally applies custom voice reference & effects.
    """
    clean_prompt = _clean_text_for_tts(request.text)
    if not clean_prompt:
        raise HTTPException(status_code=400, detail="Text to synthesize cannot be empty.")

    lc = build_lollms_client_from_params(username=current_user.username, load_llm=False, load_tts=True)
    if not lc.tts:
        raise HTTPException(status_code=400, detail="Text-to-Speech (TTS) service is not configured or active.")

    user_voices_path = get_user_voices_path(current_user.username)
    voice_file_path = None
    language_to_use = request.language or "en"

    if request.voice_id:
        voice = db.query(DBUserVoice).filter(DBUserVoice.id == request.voice_id, DBUserVoice.owner_user_id == current_user.id).first()
        if voice:
            safe_fn = secure_filename(voice.file_path)
            candidate = user_voices_path / safe_fn
            if candidate.exists():
                voice_file_path = candidate
                if not request.language:
                    language_to_use = voice.language

    temp_test_file_path = None
    effective_voice_path_str = None

    try:
        if voice_file_path:
            reverb_params_dict = request.reverb_params.model_dump() if request.reverb_params else {}
            needs_fx = (
                abs((request.pitch or 1.0) - 1.0) > 0.01 or
                abs((request.speed or 1.0) - 1.0) > 0.01 or
                abs(request.gain or 0.0) > 0.01 or
                bool(reverb_params_dict)
            )

            if needs_fx and pydub_available:
                temp_test_file_path = user_voices_path / f"test_{uuid.uuid4().hex}.wav"
                _process_audio_effects(
                    voice_file_path, temp_test_file_path,
                    request.pitch or 1.0, request.speed or 1.0, request.gain or 0.0,
                    reverb_params_dict
                )
                effective_voice_path_str = str(temp_test_file_path.resolve())
            else:
                effective_voice_path_str = str(voice_file_path.resolve())

        # Generate audio via active TTS engine
        raw_audio = lc.tts.generate_audio(
            text=clean_prompt,
            voice=effective_voice_path_str,
            language=language_to_use
        )

        audio_bytes = _normalize_audio_bytes(raw_audio)
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        return {"audio_b64": audio_b64}

    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {str(e)}")
    finally:
        if temp_test_file_path and temp_test_file_path.exists():
            temp_test_file_path.unlink(missing_ok=True)

@voices_studio_router.post("/synthesize", response_model=Dict[str, str])
async def direct_synthesize_speech(
    request: SynthesizeTTSRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return await test_voice(request, current_user, db)

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

@voices_studio_router.post("/audio-to-audio", response_model=Dict[str, Any])
async def audio_to_audio_translation(
    file: UploadFile = File(...),
    voice_id: Optional[str] = Form(None),
    source_language: Optional[str] = Form(None),
    target_language: Optional[str] = Form("en"),
    translate: bool = Form(True),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    user_db = db.query(DBUser).filter(DBUser.id == current_user.id).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found.")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file provided.")

    # 1. Speech-to-Text (STT)
    lc_stt = build_lollms_client_from_params(username=current_user.username, load_llm=False, load_stt=True)
    if not lc_stt.stt:
        raise HTTPException(status_code=400, detail="Speech-to-Text (STT) service is not configured.")

    try:
        from backend.generation.stt import _execute_transcription
        source_text = _execute_transcription(lc_stt.stt, audio_bytes)
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Speech transcription failed: {e}")

    if not source_text or not source_text.strip():
        raise HTTPException(status_code=400, detail="Could not transcribe any speech from the provided audio.")

    source_text = source_text.strip()
    translated_text = source_text

    # 2. Translation via LLM if requested
    if translate and target_language:
        try:
            lc_llm = build_lollms_client_from_params(username=current_user.username, load_llm=True)
            system_prompt = (
                "You are an expert real-time audio translator. Translate the given text accurately and naturally "
                f"into the target language code '{target_language}'. Preserve emotion, tone, and formatting. "
                "Output ONLY the translated text without commentary or quotes."
            )
            user_prompt = f"Source Text:\n{source_text}"
            translated_text = lc_llm.generate_text(user_prompt, system_prompt=system_prompt, max_new_tokens=1024).strip()
        except Exception as e:
            trace_exception(e)
            translated_text = source_text

    # 3. Text-to-Speech (TTS) Synthesis
    lc_tts = build_lollms_client_from_params(username=current_user.username, load_llm=False, load_tts=True)
    if not lc_tts.tts:
        raise HTTPException(status_code=400, detail="Text-to-Speech (TTS) service is not configured.")

    voice_path = None
    language_to_use = target_language or "en"

    if voice_id:
        voice = db.query(DBUserVoice).filter(DBUserVoice.id == voice_id, DBUserVoice.owner_user_id == current_user.id).first()
        if voice:
            user_voices_path = get_user_voices_path(current_user.username)
            file_path = user_voices_path / secure_filename(voice.file_path)
            if file_path.exists():
                voice_path = str(file_path.resolve())
    elif user_db.active_voice_id:
        active_voice = db.query(DBUserVoice).filter(DBUserVoice.id == user_db.active_voice_id).first()
        if active_voice:
            user_voices_path = get_user_voices_path(current_user.username)
            file_path = user_voices_path / secure_filename(active_voice.file_path)
            if file_path.exists():
                voice_path = str(file_path.resolve())

    try:
        raw_synth = lc_tts.tts.generate_audio(
            text=_clean_text_for_tts(translated_text),
            voice=voice_path,
            language=language_to_use
        )
        synthesized_bytes = _normalize_audio_bytes(raw_synth)
        audio_b64 = base64.b64encode(synthesized_bytes).decode('utf-8')
        return {
            "source_text": source_text,
            "translated_text": translated_text,
            "target_language": language_to_use,
            "audio_b64": audio_b64
        }
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Audio synthesis failed: {e}")

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
    safe_fn = secure_filename(original_voice.file_path)
    original_file_path = user_voices_path / safe_fn
    if not original_file_path.exists():
        raise HTTPException(status_code=404, detail="Original voice file not found on disk.")

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