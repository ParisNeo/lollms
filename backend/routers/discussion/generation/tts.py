from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional, Dict
from pydantic import BaseModel
import io

from backend.db import get_db
from backend.session import get_current_active_user, get_user_lollms_client
from backend.models import UserAuthDetails

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    model: Optional[str] = None # For bindings that support multiple models
def build_tts_router(router: APIRouter):
    @router.post("/generate_tts")
    async def generate_tts(
        request_data: TTSRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user)
    ):
        """
        Generates text-to-speech audio from the provided text using the user's configured TTS binding.
        """
        try:
            lc = get_user_lollms_client(current_user.username)
            if not lc.tts:
                raise HTTPException(status_code=400, detail="Text-to-Speech (TTS) is not configured for this user.")
            
            # Use user's default TTS model if not specified in request
            model_to_use = request_data.model
            if not model_to_use:
                user_tts_model_full = current_user.tts_binding_model_name
                if user_tts_model_full and '/' in user_tts_model_full:
                    _, model_name = user_tts_model_full.split('/', 1)
                    model_to_use = model_name

            # Generate audio bytes directly (not streaming)
            audio_bytes = lc.tts.generate_audio(
                text=request_data.text,
                voice=request_data.voice,
                model=model_to_use
            )

            # Return the audio bytes as a response
            return Response(
                content=audio_bytes,
                media_type="audio/wav",  # Or determine the actual format
                headers={
                    "Content-Disposition": "attachment; filename=generated_audio.wav"
                }
            )

        except HTTPException as e:
            raise e
        except Exception as e:
            print(f"TTS generation failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
