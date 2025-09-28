# backend/routers/discussion/generation/tts.py
from fastapi import APIRouter, Depends, HTTPException, Body, Response
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from pathlib import Path

from backend.db import get_db
from backend.session import get_current_active_user, get_user_lollms_client, get_user_data_root
from backend.models import UserAuthDetails
from backend.db.models.user import User as DBUser
from backend.db.models.voice import UserVoice as DBUserVoice

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    model: Optional[str] = None # For bindings that support multiple models

def build_tts_router(router: APIRouter):
    @router.post("/generate_tts")
    async def generate_tts(
        request_data: TTSRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Generates text-to-speech audio from the provided text using the user's configured TTS binding.
        It prioritizes the user's active custom voice if one is set.
        """
        try:
            lc = get_user_lollms_client(current_user.username)
            if not lc.tts:
                raise HTTPException(status_code=400, detail="Text-to-Speech (TTS) is not configured for this user.")
            
            # --- NEW LOGIC for custom voice ---
            voice_to_use = request_data.voice
            db_user = db.query(DBUser).filter(DBUser.id == current_user.id).first()
            
            if db_user and db_user.active_voice_id and not voice_to_use:
                active_voice = db.query(DBUserVoice).filter(DBUserVoice.id == db_user.active_voice_id).first()
                if active_voice:
                    user_voices_path = get_user_data_root(current_user.username) / "voices"
                    voice_file_path = user_voices_path / Path(active_voice.file_path)
                    if voice_file_path.exists():
                        voice_to_use = str(voice_file_path.resolve())
                        print(f"INFO: Using active voice for user {current_user.username}: {voice_to_use}")
                    else:
                        print(f"WARNING: Active voice file not found for user {current_user.username}: {voice_file_path}")
            # --- END NEW LOGIC ---

            model_to_use = request_data.model
            if not model_to_use:
                user_tts_model_full = current_user.tts_binding_model_name
                if user_tts_model_full and '/' in user_tts_model_full:
                    _, model_name = user_tts_model_full.split('/', 1)
                    model_to_use = model_name

            audio_bytes = lc.tts.generate_audio(
                text=request_data.text,
                voice=voice_to_use,
                model=model_to_use
            )

            return Response(
                content=audio_bytes,
                media_type="audio/wav",
                headers={"Content-Disposition": "attachment; filename=generated_audio.wav"}
            )

        except HTTPException as e:
            raise e
        except Exception as e:
            print(f"TTS generation failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))