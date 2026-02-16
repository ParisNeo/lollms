# backend/routers/services/lollms_v1.py
from pathlib import Path
import time
import datetime
import json
import base64
import uuid
import asyncio
from typing import List, Optional, Dict, Any, Union
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from pydantic import BaseModel, Field

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.api_key import OpenAIAPIKey as DBAPIKey
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.config import LLMBinding as DBLLMBinding, TTIBinding as DBTTIBinding, TTSBinding as DBTTSBinding, STTBinding as DBSTTBinding, RAGBinding as DBRAGBinding
from backend.db.models.datastore import DataStore as DBDataStore
from backend.db.models.voice import UserVoice as DBUserVoice
from backend.security import verify_api_key
from backend.session import user_sessions, build_lollms_client_from_params, get_safe_store_instance, get_user_data_root
from backend.settings import settings
from backend.utils import track_service_usage, check_rate_limit
from backend.routers.services.openai_v1 import (
    PersonalityListResponse, PersonalityInfo,
    TokenizeRequest, TokenizeResponse, DetokenizeRequest, DetokenizeResponse,
    ContextSizeRequest, ContextSizeResponse,
    resolve_model_name, ImageGenerationRequest, ImageGenerationResponse, ImageObject
)

lollms_v1_router = APIRouter(prefix="/lollms/v1")
bearer_scheme = HTTPBearer(auto_error=False)

# Create a thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=50)

async def get_user_for_lollms_service(
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> DBUser:
    if not settings.get("lollms_services_enabled", True):
        raise HTTPException(status_code=403, detail="LoLLMs exclusive services are disabled.")

    require_key = settings.get("lollms_services_require_key", True)
    
    # DB operations can be blocking, but usually fast for single record lookups. 
    # For high throughput auth, we keep it simple here, but could wrap if needed.
    if not require_key:
        user = db.query(DBUser).filter(DBUser.is_admin == True).first()
    else:
        if not authorization: raise HTTPException(status_code=401, detail="API Key required.")
        api_key = authorization.credentials
        parts = api_key.split('_')
        if len(parts) < 2: raise HTTPException(status_code=401)
        key_prefix = parts[0] + "_" + parts[1]
        db_key = db.query(DBAPIKey).filter(DBAPIKey.key_prefix == key_prefix).first()
        if not db_key or not verify_api_key(api_key, db_key.key_hash): raise HTTPException(status_code=401)
        user = db.query(DBUser).filter(DBUser.id == db_key.user_id).first()

    if not user or not user.is_active: raise HTTPException(status_code=401)
    
    identifier = authorization.credentials if authorization else "anonymous"
    if not check_rate_limit(identifier, "lollms"): raise HTTPException(status_code=429)

    track_service_usage("lollms", user.id)
    return user

# --- Lollms Specific Feature Models ---

class LongContextRequest(BaseModel):
    text: str
    prompt: Optional[str] = None
    model: Optional[str] = None
    max_generation_tokens: Optional[int] = 4096

class RagQueryRequest(BaseModel):
    datastore_id: str
    query: str
    top_k: int = 10
    min_similarity: float = 50.0

class ImageEditRequest(BaseModel):
    prompt: str
    image: str 
    mask: Optional[str] = None
    model: Optional[str] = None

class CapabilitiesResponse(BaseModel):
    capabilities: List[str]
    active_bindings: Dict[str, List[str]]

# --- NEW: TTS Models ---
class TTSRequest(BaseModel):
    input: str = Field(..., description="The text to generate audio for.")
    voice: Optional[str] = Field(default=None, description="The voice to use (binding voice name, 'alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer', a user custom voice ID, or a path to a voice file)")
    audio_sample: Optional[str] = Field(default=None, description="Optional base64-encoded audio sample to use as the voice (e.g., a short voice recording for instant voice cloning). If provided, this takes precedence over 'voice'.")
    model: Optional[str] = Field(default=None, description="The TTS model to use (format: 'binding_alias/model_name' or just model name)")
    response_format: Optional[str] = Field(default="mp3", description="The format of the audio output (mp3, opus, aac, flac, wav, pcm)")
    speed: Optional[float] = Field(default=1.0, ge=0.25, le=4.0, description="The speed of the generated audio")
    language: Optional[str] = None

class VoiceInfo(BaseModel):
    voice_id: str
    name: str
    category: Optional[str] = None  # 'system', 'user_custom', 'binding'
    language: Optional[str] = None
    description: Optional[str] = None
    preview_url: Optional[str] = None

class VoicesListResponse(BaseModel):
    object: str = "list"
    data: List[VoiceInfo]

# --- NEW: RAG Database Models ---
class RagDatabaseInfo(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    vectorizer: Optional[str] = None
    vectorizer_index: Optional[str] = None
    binding_used: Optional[str] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    is_public: bool = False
    owner_username: Optional[str] = None

    class Config:
        from_attributes = True

class RagDatabaseListResponse(BaseModel):
    object: str = "list"
    data: List[RagDatabaseInfo]

# --- Endpoints ---

@lollms_v1_router.get("/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities(user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
    """Returns a list of active platform capabilities and bindings."""
    loop = asyncio.get_running_loop()
    
    def _fetch_capabilities():
        caps = ["tokenize", "detokenize", "long_context_processing"]
        
        # Check RAG
        from backend.session import safe_store
        if safe_store is not None:
            caps.append("rag_query")
        
        # Check TTI
        tti_bindings = db.query(DBTTIBinding).filter(DBTTIBinding.is_active == True).all()
        if tti_bindings:
            caps.append("image_generation")
            caps.append("image_editing")
            
        # Check TTS/STT
        if db.query(DBTTSBinding).filter(DBTTSBinding.is_active == True).first():
            caps.append("text_to_speech")
        if db.query(DBSTTBinding).filter(DBSTTBinding.is_active == True).first():
            caps.append("speech_to_text")

        active_bindings = {
            "llm": [b.alias for b in db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()],
            "tti": [b.alias for b in tti_bindings],
            "tts": [b.alias for b in db.query(DBTTSBinding).filter(DBTTSBinding.is_active == True).all()],
            "stt": [b.alias for b in db.query(DBSTTBinding).filter(DBSTTBinding.is_active == True).all()],
            "rag": [b.alias for b in db.query(DBRAGBinding).filter(DBRAGBinding.is_active == True).all()]
        }
        return CapabilitiesResponse(capabilities=caps, active_bindings=active_bindings)

    return await loop.run_in_executor(executor, _fetch_capabilities)

@lollms_v1_router.get("/personalities", response_model=PersonalityListResponse)
async def list_personalities(user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
    loop = asyncio.get_running_loop()
    
    def _fetch_personalities():
        personalities_db = db.query(DBPersonality).options(joinedload(DBPersonality.owner)).filter(
            or_(DBPersonality.is_public == True, DBPersonality.owner_user_id == user.id)
        ).all()
        return PersonalityListResponse(data=[PersonalityInfo.from_orm(p) for p in personalities_db])

    return await loop.run_in_executor(executor, _fetch_personalities)

@lollms_v1_router.post("/tokenize", response_model=TokenizeResponse)
async def tokenize_text(request: TokenizeRequest, user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
    binding_alias, model_name = resolve_model_name(db, request.model)
    loop = asyncio.get_running_loop()
    
    def _tokenize():
        lc = build_lollms_client_from_params(user.username, binding_alias, model_name)
        tokens = lc.tokenize(request.text)
        return TokenizeResponse(tokens=tokens, count=len(tokens))

    return await loop.run_in_executor(executor, _tokenize)

@lollms_v1_router.post("/detokenize", response_model=DetokenizeResponse)
async def detokenize_tokens(request: DetokenizeRequest, user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
    binding_alias, model_name = resolve_model_name(db, request.model)
    loop = asyncio.get_running_loop()
    
    def _detokenize():
        lc = build_lollms_client_from_params(user.username, binding_alias, model_name)
        text = lc.detokenize(request.tokens)
        return DetokenizeResponse(text=text)

    return await loop.run_in_executor(executor, _detokenize)

@lollms_v1_router.post("/context_size", response_model=ContextSizeResponse)
async def get_context_size(request: ContextSizeRequest, user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
    alias, name = resolve_model_name(db, request.model)
    loop = asyncio.get_running_loop()
    
    def _get_ctx_size():
        lc = build_lollms_client_from_params(user.username, alias, name, load_llm=True)
        context_size = lc.get_ctx_size(name)
        return ContextSizeResponse(context_size=context_size if context_size else lc.llm.default_ctx_size)

    return await loop.run_in_executor(executor, _get_ctx_size)

@lollms_v1_router.post("/long_context_process")
async def process_long_context(request: LongContextRequest, user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
    binding_alias, model_name = None, None
    if request.model:
        binding_alias, model_name = resolve_model_name(db, request.model)
    
    loop = asyncio.get_running_loop()
    
    def _process():
        lc = build_lollms_client_from_params(user.username, binding_alias, model_name)
        result = lc.long_context_processing(text_to_process=request.text, contextual_prompt=request.prompt, expected_generation_tokens=request.max_generation_tokens)
        return {"result": result}

    return await loop.run_in_executor(executor, _process)

@lollms_v1_router.get("/rag/databases", response_model=RagDatabaseListResponse)
async def list_rag_databases(
    user: DBUser = Depends(get_user_for_lollms_service),
    db: Session = Depends(get_db)
):
    """
    Lists all RAG databases (datastores) available to the current user.
    Includes user's own datastores and public datastores.
    """
    loop = asyncio.get_running_loop()
    
    def _fetch_databases():
        # Query datastores that belong to user or are public
        datastores = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(
            or_(
                DBDataStore.owner_user_id == user.id,
                DBDataStore.is_public == True
            )
        ).order_by(DBDataStore.name).all()
        
        response_data = []
        for ds in datastores:
            owner_username = ds.owner.username if ds.owner else None
            
            info = RagDatabaseInfo(
                id=str(ds.id),
                name=ds.name,
                description=ds.description,
                vectorizer=ds.vectorizer,
                vectorizer_index=ds.vectorizer_index,
                binding_used=ds.binding_used,
                created_at=ds.created_at,
                updated_at=ds.updated_at,
                is_public=ds.is_public,
                owner_username=owner_username
            )
            response_data.append(info)
        
        return RagDatabaseListResponse(data=response_data)

    return await loop.run_in_executor(executor, _fetch_databases)

@lollms_v1_router.post("/rag/query")
async def query_user_datastore(request: RagQueryRequest, user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
    loop = asyncio.get_running_loop()
    
    def _query():
        try:
            ss = get_safe_store_instance(user.username, request.datastore_id, db, permission_level="read_query")
            with ss:
                results = ss.query(request.query, top_k=request.top_k, min_similarity_percent=request.min_similarity)
            from backend.routers.stores import _sanitize_numpy
            return _sanitize_numpy(results)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"RAG query failed: {str(e)}")

    return await loop.run_in_executor(executor, _query)

@lollms_v1_router.post("/images/edit", response_model=ImageGenerationResponse)
async def edit_image_lollms(request: ImageEditRequest, user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
    loop = asyncio.get_running_loop()
    
    def _edit():
        binding_alias = user.iti_binding_model_name.split('/')[0] if user.iti_binding_model_name else None
        model_name = user.iti_binding_model_name.split('/')[1] if user.iti_binding_model_name else None
        if request.model and '/' in request.model:
            binding_alias, model_name = request.model.split('/', 1)
        
        lc = build_lollms_client_from_params(user.username, load_llm=False, load_tti=True, tti_binding_alias=binding_alias, tti_model_name=model_name)
        if not lc.tti: raise HTTPException(status_code=501, detail="ITI service not configured.")
        try:
            img_b64 = lc.tti.paint(prompt=request.prompt, image=request.image, mask=request.mask)
            return ImageGenerationResponse(data=[ImageObject(b64_json=img_b64)])
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return await loop.run_in_executor(executor, _edit)

# --- NEW: TTS Endpoints ---

@lollms_v1_router.post("/audio/speech")
async def create_speech(
    request: TTSRequest,
    user: DBUser = Depends(get_user_for_lollms_service),
    db: Session = Depends(get_db)
):
    """
    Generates text-to-speech audio from the input text.
    Compatible with OpenAI's /audio/speech endpoint.
    """
    loop = asyncio.get_running_loop()
    
    # Determine model to use
    tts_binding_alias = None
    tts_model_name = None
    
    if request.model:
        if '/' in request.model:
            tts_binding_alias, tts_model_name = request.model.split('/', 1)
        else:
            # Just model name, use default binding
            default_binding = db.query(DBTTSBinding).filter(DBTTSBinding.is_active == True).order_by(DBTTSBinding.id).first()
            if default_binding:
                tts_binding_alias = default_binding.alias
                tts_model_name = request.model
    else:
        # Use user's default
        user_tts_model = user.tts_binding_model_name
        if user_tts_model and '/' in user_tts_model:
            tts_binding_alias, tts_model_name = user_tts_model.split('/', 1)
        else:
            default_binding = db.query(DBTTSBinding).filter(DBTTSBinding.is_active == True).order_by(DBTTSBinding.id).first()
            if not default_binding:
                raise HTTPException(status_code=400, detail="No TTS model specified and no default TTS binding configured.")
            tts_binding_alias = default_binding.alias
            tts_model_name = user_tts_model or default_binding.default_model_name

    try:
        lc = await loop.run_in_executor(
            executor,
            lambda: build_lollms_client_from_params(
                username=user.username,
                load_llm=False,
                load_tts=True,
                tts_binding_alias=tts_binding_alias,
                tts_model_name=tts_model_name
            )
        )
        
        if not hasattr(lc, 'tts') or not lc.tts:
            raise HTTPException(status_code=500, detail=f"TTS functionality is not available for binding '{tts_binding_alias}'.")

        # Resolve voice
        voice_to_use = request.voice
        language_to_use = request.language
        temp_audio_path = None
        
        # Priority 1: Check for inline audio_sample (base64)
        if request.audio_sample:
            try:
                import uuid
                import tempfile
                audio_bytes = base64.b64decode(request.audio_sample)
                # Create temp file with appropriate extension based on content or default to wav
                temp_dir = Path(tempfile.gettempdir()) / "lollms_tts_samples"
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_audio_path = temp_dir / f"{user.username}_{uuid.uuid4().hex[:8]}.wav"
                with open(temp_audio_path, "wb") as f:
                    f.write(audio_bytes)
                voice_to_use = str(temp_audio_path.resolve())
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid audio_sample: {str(e)}")
        
        # Priority 2: Check if it's a user custom voice ID (only if no audio_sample)
        if not voice_to_use:
            if request.voice:
                custom_voice = db.query(DBUserVoice).filter(
                    DBUserVoice.id == request.voice,
                    DBUserVoice.owner_user_id == user.id
                ).first()
                if custom_voice:
                    user_voices_path = get_user_data_root(user.username) / "voices"
                    voice_file_path = user_voices_path / custom_voice.file_path
                    if voice_file_path.exists():
                        voice_to_use = str(voice_file_path.resolve())
                    else:
                        raise HTTPException(status_code=404, detail=f"Custom voice file not found: {custom_voice.file_path}")
            
            # If no voice specified, check for active voice
            if not voice_to_use and user.active_voice_id:
                active_voice = db.query(DBUserVoice).filter(DBUserVoice.id == user.active_voice_id).first()
                if active_voice:
                    user_voices_path = get_user_data_root(user.username) / "voices"
                    voice_file_path = user_voices_path / active_voice.file_path
                    if voice_file_path.exists():
                        voice_to_use = str(voice_file_path.resolve())
                        language_to_use = active_voice.language

        # Clean text for TTS (remove markdown, emojis, etc.)
        import re
        cleaned_text = request.input
        cleaned_text = re.sub(r'[*#]', '', cleaned_text)  # Remove markdown bold/italic/headers
        cleaned_text = re.sub(r'[\U00010000-\U0010ffff]', '', cleaned_text)  # Remove emojis

        try:
            # Generate audio
            def _generate():
                return lc.tts.generate_audio(
                    text=cleaned_text,
                    voice=voice_to_use,
                    model=tts_model_name,
                    language=language_to_use or "en",
                    speed=request.speed
                )

            audio_bytes = await loop.run_in_executor(executor, _generate)

        finally:
            # Clean up temporary audio sample file if we created one
            if temp_audio_path and temp_audio_path.exists():
                try:
                    temp_audio_path.unlink()
                except Exception:
                    pass  # Best effort cleanup

        # Map response format to content type
        format_to_mime = {
            "mp3": "audio/mpeg",
            "opus": "audio/opus",
            "aac": "audio/aac",
            "flac": "audio/flac",
            "wav": "audio/wav",
            "pcm": "audio/pcm"
        }
        content_type = format_to_mime.get(request.response_format, "audio/mpeg")

        return Response(
            content=audio_bytes,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename=speech.{request.response_format}"}
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        from ascii_colors import trace_exception
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")

@lollms_v1_router.get("/audio/voices", response_model=VoicesListResponse)
async def list_voices(
    user: DBUser = Depends(get_user_for_lollms_service),
    db: Session = Depends(get_db)
):
    """
    Lists all available voices for the user, including:
    - System/binding provided voices
    - User's custom cloned voices
    """
    loop = asyncio.get_running_loop()
    
    def _fetch_voices():
        voices = []
        
        # Get user's custom voices
        user_voices = db.query(DBUserVoice).filter(DBUserVoice.owner_user_id == user.id).all()
        for uv in user_voices:
            voices.append(VoiceInfo(
                voice_id=str(uv.id),
                name=uv.alias or uv.name or "Custom Voice",
                category="user_custom",
                language=uv.language,
                description=f"User custom voice created on {uv.created_at.isoformat() if uv.created_at else 'unknown'}"
            ))
        
        # Try to get binding voices if TTS is configured
        try:
            user_tts_model = user.tts_binding_model_name
            tts_binding_alias = None
            tts_model_name = None
            
            if user_tts_model and '/' in user_tts_model:
                tts_binding_alias, tts_model_name = user_tts_model.split('/', 1)
            else:
                default_binding = db.query(DBTTSBinding).filter(DBTTSBinding.is_active == True).first()
                if default_binding:
                    tts_binding_alias = default_binding.alias
            
            if tts_binding_alias:
                lc = build_lollms_client_from_params(
                    user.username,
                    load_llm=False,
                    load_tts=True,
                    tts_binding_alias=tts_binding_alias,
                    tts_model_name=tts_model_name
                )
                if hasattr(lc, 'tts') and lc.tts and hasattr(lc.tts, 'list_voices'):
                    binding_voices = lc.tts.list_voices()
                    if isinstance(binding_voices, list):
                        for bv in binding_voices:
                            if isinstance(bv, dict):
                                voices.append(VoiceInfo(
                                    voice_id=bv.get('voice_id') or bv.get('id') or bv.get('name'),
                                    name=bv.get('name') or bv.get('voice_id') or "Unknown",
                                    category="binding",
                                    language=bv.get('language') or bv.get('locale'),
                                    description=bv.get('description') or bv.get('gender') or "Binding voice"
                                ))
                            elif isinstance(bv, str):
                                voices.append(VoiceInfo(
                                    voice_id=bv,
                                    name=bv,
                                    category="binding"
                                ))
        except Exception as e:
            # Non-fatal: binding voices are optional
            print(f"Could not fetch binding voices: {e}")
        
        # Add OpenAI-compatible aliases if not already present
        openai_aliases = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        existing_ids = {v.voice_id for v in voices}
        for alias in openai_aliases:
            if alias not in existing_ids:
                voices.append(VoiceInfo(
                    voice_id=alias,
                    name=alias.capitalize(),
                    category="system",
                    description=f"OpenAI-compatible alias for {alias}"
                ))
        
        return VoicesListResponse(data=voices)

    return await loop.run_in_executor(executor, _fetch_voices)
