# backend/routers/discussion/generation/tts.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import Optional, Any
from pydantic import BaseModel, Field
from pathlib import Path
from werkzeug.utils import secure_filename
import re
import io
import base64

from backend.db import get_db
from backend.session import get_current_active_user, build_lollms_client_from_params, get_user_data_root
from backend.models import UserAuthDetails
from backend.db.models.user import User as DBUser
from backend.db.models.voice import UserVoice as DBUserVoice

# Create a thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=50)

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    model: Optional[str] = None
    language: Optional[str] = Field(default="en", description="The language code for the text (e.g., 'en', 'fr', 'de')")

def _clean_text_for_tts(text: str) -> str:
    if not text:
        return ""
    # Strip markdown formatting
    cleaned = re.sub(r'[*#_`~>\[\]()]', '', text)
    # Strip emojis
    cleaned = re.sub(r'[\U00010000-\U0010ffff]', '', cleaned)
    # Normalize whitespaces
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def _normalize_raw_tts_output(raw_output: Any) -> bytes:
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
    raise ValueError("TTS engine did not produce valid audio data.")

def build_tts_router(router: APIRouter):
    @router.post("/generate_tts")
    async def generate_tts(
        request_data: TTSRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Generates text-to-speech audio from the provided text using the user's configured TTS binding.
        Prioritizes the active custom voice if configured.
        """
        loop = asyncio.get_running_loop()
        try:
            lc = await loop.run_in_executor(
                executor,
                lambda: build_lollms_client_from_params(username=current_user.username, load_llm=False, load_tts=True)
            )

            if not lc.tts:
                raise HTTPException(status_code=400, detail="Text-to-Speech (TTS) is not configured or active.")

            voice_to_use = request_data.voice
            language_to_use = request_data.language
            db_user = db.query(DBUser).filter(DBUser.id == current_user.id).first()

            if db_user and db_user.active_voice_id and not voice_to_use:
                active_voice = db.query(DBUserVoice).filter(DBUserVoice.id == db_user.active_voice_id).first()
                if active_voice:
                    user_voices_path = get_user_data_root(current_user.username) / "voices"
                    voice_file_path = user_voices_path / Path(secure_filename(active_voice.file_path))
                    if voice_file_path.exists():
                        voice_to_use = str(voice_file_path.resolve())
                        if not language_to_use:
                            language_to_use = active_voice.language

            if not language_to_use and db_user and db_user.ai_response_language and db_user.ai_response_language.lower() != "auto":
                language_to_use = db_user.ai_response_language

            if not language_to_use:
                language_to_use = 'en'

            model_to_use = request_data.model
            if not model_to_use:
                user_tts_model_full = current_user.tts_binding_model_name
                if user_tts_model_full and '/' in user_tts_model_full:
                    _, model_name = user_tts_model_full.split('/', 1)
                    model_to_use = model_name

            cleaned_text = _clean_text_for_tts(request_data.text)
            if not cleaned_text:
                raise HTTPException(status_code=400, detail="Input text for speech generation is empty.")

            def _generate():
                return lc.tts.generate_audio(
                    text=cleaned_text,
                    voice=voice_to_use,
                    model=model_to_use,
                    language=language_to_use
                )

            raw_audio = await loop.run_in_executor(executor, _generate)
            audio_bytes = _normalize_raw_tts_output(raw_audio)

            return Response(
                content=audio_bytes,
                media_type="audio/wav",
                headers={"Content-Disposition": "attachment; filename=generated_audio.wav"}
            )

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {str(e)}")