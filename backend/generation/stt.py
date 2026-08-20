# backend/routers/discussion/generation/stt.py
import asyncio
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from ascii_colors import trace_exception, ASCIIColors

from backend.db import get_db
from backend.session import get_current_active_user, build_lollms_client_from_params
from backend.models import UserAuthDetails

# Create a thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=50)

def _execute_transcription(stt_engine, audio_data: bytes) -> str:
    """
    Polymorphic transcriber that supports both in-memory byte streams 
    and bindings that require a temporary filesystem audio file.
    """
    # 1. Try in-memory byte execution first
    if hasattr(stt_engine, 'transcribe_audio'):
        try:
            res = stt_engine.transcribe_audio(audio_data)
            if res is not None:
                return str(res).strip()
        except TypeError:
            pass
        except Exception as ex:
            ASCIIColors.warning(f"In-memory STT byte stream failed, falling back to disk buffer: {ex}")

    if hasattr(stt_engine, 'transcribe'):
        try:
            res = stt_engine.transcribe(audio_data)
            if res is not None:
                return str(res).strip()
        except TypeError:
            pass
        except Exception as ex:
            ASCIIColors.warning(f"Direct transcribe call failed, falling back to disk buffer: {ex}")

    # 2. Disk buffer fallback for bindings that expect a filesystem path (e.g. Whisper subprocess / ffmpeg)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name

    try:
        if hasattr(stt_engine, 'transcribe_audio'):
            res = stt_engine.transcribe_audio(tmp_path)
        elif hasattr(stt_engine, 'transcribe_file'):
            res = stt_engine.transcribe_file(tmp_path)
        elif hasattr(stt_engine, 'transcribe'):
            res = stt_engine.transcribe(tmp_path)
        else:
            raise AttributeError(f"STT binding '{type(stt_engine).__name__}' has no recognized transcription method.")
        return str(res).strip() if res else ""
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

def build_stt_router(router: APIRouter):
    @router.post("/stt")
    async def speech_to_text(
        file: UploadFile = File(...),
        current_user: UserAuthDetails = Depends(get_current_active_user)
    ):
        """
        Transcribes audio to text using the user's configured STT binding.
        """
        loop = asyncio.get_running_loop()
        try:
            lc = await loop.run_in_executor(
                executor,
                lambda: build_lollms_client_from_params(username=current_user.username, load_llm=False, load_stt=True)
            )

            if not lc.stt:
                raise HTTPException(status_code=400, detail="Speech-to-Text (STT) is not configured for this user or no active STT binding exists.")

            audio_bytes = await file.read()
            if not audio_bytes:
                raise HTTPException(status_code=400, detail="Received empty audio file.")

            transcription = await loop.run_in_executor(
                executor, 
                lambda: _execute_transcription(lc.stt, audio_bytes)
            )

            return {"text": transcription}

        except HTTPException as e:
            raise e
        except Exception as e:
            ASCIIColors.error(f"STT transcription failed: {e}")
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to transcribe audio: {e}")