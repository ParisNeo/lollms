# [UPDATE] backend/routers/discussion/generation/stt.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.session import get_current_active_user, build_lollms_client_from_params
from backend.models import UserAuthDetails

def build_stt_router(router: APIRouter):
    @router.post("/stt")
    async def speech_to_text(
        file: UploadFile = File(...),
        current_user: UserAuthDetails = Depends(get_current_active_user)
    ):
        """
        Transcribes audio to text using the user's configured STT binding.
        """
        try:
            lc = build_lollms_client_from_params(username=current_user.username, load_llm=False, load_stt=True)
            if not lc.stt:
                raise HTTPException(status_code=400, detail="Speech-to-Text (STT) is not configured for this user.")

            audio_bytes = await file.read()
            
            # The transcribe_audio method should handle various audio formats
            transcription = lc.stt.transcribe_audio(audio_bytes)

            return {"text": transcription}

        except HTTPException as e:
            raise e
        except Exception as e:
            print(f"STT transcription failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
