# backend/routers/services/lollms_v1.py
from pathlib import Path
import time
import datetime
import json
import base64
import uuid
import asyncio
import os
import tempfile
import re
import io
from typing import List, Optional, Dict, Any, Union
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from pydantic import BaseModel, Field, ConfigDict

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.api_key import OpenAIAPIKey as DBAPIKey
from backend.db.models.personality import Personality as DBPersonality
from backend.db.models.config import (
    LLMBinding as DBLLMBinding, 
    TTIBinding as DBTTIBinding, 
    TTSBinding as DBTTSBinding, 
    STTBinding as DBSTTBinding, 
    TTVBinding as DBTTVBinding,
    TTMBinding as DBTTMBinding,
    RAGBinding as DBRAGBinding
)
from backend.db.models.datastore import DataStore as DBDataStore
from backend.db.models.voice import UserVoice as DBUserVoice
from backend.security import verify_api_key
from backend.session import user_sessions, build_lollms_client_from_params, get_safe_store_instance, get_user_data_root
from backend.settings import settings

try:
    from lollms_client.lollms_llm_binding import list_binding_models as list_llm_binding_models
except ImportError:
    list_llm_binding_models = None

try:
    from lollms_client.lollms_tti_binding import list_binding_models as list_tti_binding_models
except ImportError:
    list_tti_binding_models = None

try:
    from lollms_client.lollms_tts_binding import list_binding_models as list_tts_binding_models
except ImportError:
    list_tts_binding_models = None

try:
    from lollms_client.lollms_stt_binding import list_binding_models as list_stt_binding_models
except ImportError:
    list_stt_binding_models = None
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
    loop = asyncio.get_running_loop()

    # Offload potentially blocking database operations entirely
    def _authenticate():
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
        return user

    user = await loop.run_in_executor(executor, _authenticate)

    identifier = authorization.credentials if authorization else "anonymous"
    if not check_rate_limit(identifier, "lollms"): raise HTTPException(status_code=429)

    # Wrap usage tracking
    await loop.run_in_executor(executor, lambda: track_service_usage("lollms", user.id))
    return user

# --- Lollms Specific Feature Models ---

class LongContextRequest(BaseModel):
    text: str
    prompt: Optional[str] = None
    model: Optional[str] = None
    max_generation_tokens: Optional[int] = 32000

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

# --- Multimodal Audio, Speech, Music & Video Models ---

class TTSRequest(BaseModel):
    input: str = Field(..., description="The text to generate audio for.")
    voice: Optional[str] = Field(default=None, description="The voice to use (binding voice name, 'alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer', a user custom voice ID, or a path to a voice file)")
    audio_sample: Optional[str] = Field(default=None, description="Optional base64-encoded audio sample to use as the voice (for instant zero-shot voice cloning).")
    model: Optional[str] = Field(default=None, description="The TTS model to use (format: 'binding_alias/model_name' or just model name)")
    response_format: Optional[str] = Field(default="mp3", description="The format of the audio output ('mp3', 'wav', 'ogg', 'opus', 'flac', 'aac', 'b64_json')")
    speed: Optional[float] = Field(default=1.0, ge=0.25, le=4.0, description="The speed/rate of the generated speech")
    pitch: Optional[float] = Field(default=1.0, description="Optional pitch adjustment multiplier")
    language: Optional[str] = Field(default="en", description="Language code (e.g., 'en', 'fr', 'es', 'de')")
    return_json: Optional[bool] = Field(default=False, description="If true, returns a JSON object with base64 encoded audio instead of binary stream")

class TTSJsonResponse(BaseModel):
    object: str = "audio.speech"
    audio_format: str
    b64_audio: str
    text_length: int
    duration_seconds: Optional[float] = None

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

# --- Speech to Text (STT) Models ---
class STTRequest(BaseModel):
    audio: Optional[str] = Field(default=None, description="Base64 encoded audio string (if not uploading as multipart form)")
    file_path: Optional[str] = Field(default=None, description="Optional local file path to an audio file")
    model: Optional[str] = Field(default=None, description="STT model to use ('binding_alias/model' or model name)")
    language: Optional[str] = Field(default=None, description="Language hint (e.g. 'en', 'fr')")
    prompt: Optional[str] = Field(default=None, description="Optional prompt or vocabulary hint")
    response_format: Optional[str] = Field(default="json", description="'json', 'text', or 'verbose_json'")
    temperature: Optional[float] = Field(default=0.0, description="Sampling temperature")

class STTResponse(BaseModel):
    text: str
    language: Optional[str] = None
    duration: Optional[float] = None

class STTVerboseResponse(BaseModel):
    task: str = "transcribe"
    language: Optional[str] = None
    duration: Optional[float] = None
    text: str
    segments: List[Dict[str, Any]] = Field(default_factory=list)

# --- Text to Music (TTM) Models ---
class TTMRequest(BaseModel):
    prompt: str = Field(..., description="Description of the music or audio track to generate")
    negative_prompt: Optional[str] = Field(default="", description="Negative prompt for unwanted acoustic elements")
    duration: Optional[int] = Field(default=15, ge=1, le=300, description="Duration in seconds")
    bpm: Optional[int] = Field(default=None, ge=40, le=240, description="Beats per minute")
    genre: Optional[str] = Field(default=None, description="Musical genre or style tag")
    model: Optional[str] = Field(default=None, description="TTM model to use ('binding_alias/model_name' or model name)")
    response_format: Optional[str] = Field(default="audio", description="'audio' (binary stream), 'b64_json', or 'url'")

class TTMResponse(BaseModel):
    object: str = "audio.music"
    b64_audio: Optional[str] = None
    url: Optional[str] = None
    duration: int
    prompt: str

# --- Text to Video (TTV) Models ---
class TTVRequest(BaseModel):
    prompt: str = Field(..., description="Description of the video clip to generate")
    negative_prompt: Optional[str] = Field(default="", description="Negative prompt")
    image: Optional[str] = Field(default=None, description="Optional initial frame (base64 or URL) for Image-to-Video generation")
    model: Optional[str] = Field(default=None, description="TTV model ('binding_alias/model_name' or model name)")
    width: Optional[int] = Field(default=512, ge=128, le=1920)
    height: Optional[int] = Field(default=512, ge=128, le=1080)
    num_frames: Optional[int] = Field(default=24, ge=8, le=240, description="Total frame count")
    fps: Optional[int] = Field(default=12, ge=1, le=60, description="Frames per second")
    response_format: Optional[str] = Field(default="url", description="'url', 'b64_json', or 'video' (binary stream)")
    seed: Optional[int] = Field(default=-1)

class TTVResponse(BaseModel):
    object: str = "video.generation"
    b64_video: Optional[str] = None
    url: Optional[str] = None
    width: int
    height: int
    num_frames: int
    prompt: str

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

# --- NEW: Per-Binding Model Listing Models ---

class BindingModelInfo(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: str
    name: str
    binding: str
    model_name: str
    alias: Optional[Dict[str, Any]] = None
    created: Optional[int] = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "lollms"

class BindingModelListResponse(BaseModel):
    object: str = "list"
    binding_type: str
    total: int = 0
    data: List[BindingModelInfo]

# Supported binding modality configurations
BINDING_TYPE_MAP = {
    "llm": DBLLMBinding,
    "tti": DBTTIBinding,
    "tts": DBTTSBinding,
    "stt": DBSTTBinding,
    "ttv": DBTTVBinding,
    "ttm": DBTTMBinding,
    "rag": DBRAGBinding,
}

BINDING_ALIAS_NORMALIZER = {
    "text": "llm",
    "image": "tti",
    "speech": "tts",
    "audio": "tts",
    "transcription": "stt",
    "video": "ttv",
    "music": "ttm",
    "embedding": "rag",
    "embeddings": "rag",
    "vectorizer": "rag",
    "vectorizers": "rag",
    "safe_store": "rag",
}

def _clean_alias(alias_data: Any) -> Optional[Dict[str, Any]]:
    if not alias_data:
        return None
    if isinstance(alias_data, str):
        try:
            alias_data = json.loads(alias_data)
        except Exception:
            return {"title": alias_data}
    if isinstance(alias_data, dict):
        if "alias" in alias_data and isinstance(alias_data["alias"], dict):
            return alias_data["alias"]
        return alias_data
    return {"title": str(alias_data)}

def _extract_raw_models_for_binding(b_type: str, binding_record: Any) -> List[Any]:
    raw_models = []

    if b_type == "rag":
        from backend.session import safe_store
        if safe_store and hasattr(safe_store, "SafeStore") and hasattr(safe_store.SafeStore, "list_models"):
            clean_config = binding_record.config.copy() if isinstance(binding_record.config, dict) else {}
            clean_config.pop("model", None)
            try:
                raw_models = safe_store.SafeStore.list_models(
                    vectorizer_name=binding_record.name,
                    vectorizer_config=clean_config
                )
            except Exception as e:
                print(f"Warning: Failed to list SafeStore models for {binding_record.alias}: {e}")
        return raw_models if isinstance(raw_models, list) else []

    helper_map = {
        "llm": list_llm_binding_models,
        "tti": list_tti_binding_models,
        "tts": list_tts_binding_models,
        "stt": list_stt_binding_models
    }
    helper = helper_map.get(b_type)
    if helper:
        try:
            b_config = binding_record.config if isinstance(binding_record.config, dict) else {}
            kw = {f"{b_type}_binding_name": binding_record.name, f"{b_type}_binding_config": b_config}
            models_res = helper(**kw)
            if isinstance(models_res, list):
                return models_res
        except Exception:
            pass

    try:
        from backend.routers.admin.bindings_management import _get_binding_instance, _get_effective_config
        config = _get_effective_config(binding_record)
        service = _get_binding_instance(b_type, binding_record.name, config)
        if service and hasattr(service, "list_models") and callable(service.list_models):
            models_res = service.list_models()
            if isinstance(models_res, list):
                return models_res
    except Exception:
        pass

    return raw_models

def _get_models_for_binding_type(
    db: Session,
    b_type: str,
    binding_alias: Optional[str] = None,
    ad_mode: str = "profiles_only"
) -> List[BindingModelInfo]:
    target_cls = BINDING_TYPE_MAP[b_type]
    query = db.query(target_cls).filter(target_cls.is_active == True)
    if binding_alias:
        query = query.filter(target_cls.alias == binding_alias)
    active_bindings = query.all()

    models_out: List[BindingModelInfo] = []
    seen_ids = set()

    for binding in active_bindings:
        raw_models = _extract_raw_models_for_binding(b_type, binding)
        raw_names = []
        if isinstance(raw_models, list):
            for item in raw_models:
                m_id = item if isinstance(item, str) else (item.get("model_name") or item.get("name") or item.get("id"))
                if m_id:
                    raw_names.append(str(m_id))

        aliases = binding.model_aliases or {}
        if isinstance(aliases, str):
            try:
                aliases = json.loads(aliases)
            except Exception:
                aliases = {}
        if not isinstance(aliases, dict):
            aliases = {}

        if ad_mode in ["all_models", "binding_model", "all"]:
            # Forward all available physical models formatted as binding/model
            for model_name in raw_names:
                alias_data = aliases.get(model_name)
                clean_alias = _clean_alias(alias_data)
                display_name = (clean_alias.get("title") or clean_alias.get("name") or model_name) if clean_alias else model_name
                full_id = f"{binding.alias}/{model_name}"

                if full_id not in seen_ids:
                    seen_ids.add(full_id)
                    models_out.append(BindingModelInfo(
                        id=full_id,
                        name=display_name,
                        binding=binding.alias,
                        model_name=model_name,
                        alias=clean_alias
                    ))

            # Also include configured profiles as binding/profile
            for orig_name, alias_data in aliases.items():
                full_id = f"{binding.alias}/{orig_name}"
                if full_id not in seen_ids:
                    clean_alias = _clean_alias(alias_data)
                    display_name = (clean_alias.get("title") or clean_alias.get("name") or orig_name) if clean_alias else orig_name
                    target = clean_alias.get("model_name") or orig_name
                    if not raw_names or target in raw_names or binding.name == 'smart_router':
                        seen_ids.add(full_id)
                        models_out.append(BindingModelInfo(
                            id=full_id,
                            name=display_name,
                            binding=binding.alias,
                            model_name=target,
                            alias=clean_alias
                        ))
        else:
            # Mode: profiles_only (Default) — uses actual profile name as ID
            for orig_name, alias_data in aliases.items():
                clean_alias = _clean_alias(alias_data)
                display_name = (clean_alias.get("title") or clean_alias.get("name") or orig_name) if clean_alias else orig_name
                target = clean_alias.get("model_name") or orig_name

                # Health check: Only advertise if verified present or smart_router
                if raw_names and target not in raw_names and binding.name != 'smart_router':
                    continue

                target_id = display_name
                if target_id in seen_ids:
                    target_id = f"{binding.alias}/{display_name}"

                if target_id not in seen_ids:
                    seen_ids.add(target_id)
                    models_out.append(BindingModelInfo(
                        id=target_id,
                        name=display_name,
                        binding=binding.alias,
                        model_name=target,
                        alias=clean_alias
                    ))

            # If no profiles exist at all for this binding, provide default model or verified raw models
            if not aliases and raw_names:
                for model_name in raw_names:
                    target_id = model_name
                    if target_id in seen_ids:
                        target_id = f"{binding.alias}/{model_name}"
                    if target_id not in seen_ids:
                        seen_ids.add(target_id)
                        models_out.append(BindingModelInfo(
                            id=target_id,
                            name=model_name,
                            binding=binding.alias,
                            model_name=model_name,
                            alias=None
                        ))

    return sorted(models_out, key=lambda x: x.name)

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
        tts_bindings = db.query(DBTTSBinding).filter(DBTTSBinding.is_active == True).all()
        if tts_bindings:
            caps.append("text_to_speech")
        stt_bindings = db.query(DBSTTBinding).filter(DBSTTBinding.is_active == True).all()
        if stt_bindings:
            caps.append("speech_to_text")

        # Check TTV / TTM
        ttv_bindings = db.query(DBTTVBinding).filter(DBTTVBinding.is_active == True).all()
        if ttv_bindings:
            caps.append("text_to_video")
        ttm_bindings = db.query(DBTTMBinding).filter(DBTTMBinding.is_active == True).all()
        if ttm_bindings:
            caps.append("text_to_music")

        active_bindings = {
            "llm": [b.alias for b in db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()],
            "tti": [b.alias for b in tti_bindings],
            "tts": [b.alias for b in tts_bindings],
            "stt": [b.alias for b in stt_bindings],
            "ttv": [b.alias for b in ttv_bindings],
            "ttm": [b.alias for b in ttm_bindings],
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
    loop = asyncio.get_running_loop()

    # 1. Check global forced context size
    force_mode = settings.get("force_model_mode", "disabled")
    if force_mode == "force_always" and settings.get("force_context_size"):
        return ContextSizeResponse(context_size=int(settings.get("force_context_size")))

    # 2. Check Universal Model Profile directly
    from backend.session import get_universal_model_profile
    binding_alias, profile_key, profile_info = await loop.run_in_executor(
        executor,
        lambda: get_universal_model_profile(db, request.model, modality="llm")
    )

    if profile_info:
        forced_ctx = profile_info.get('forced_context_size') or profile_info.get('ctx_size')
        if forced_ctx:
            try:
                parsed = int(forced_ctx)
                if parsed > 1:
                    return ContextSizeResponse(context_size=parsed)
            except (ValueError, TypeError):
                pass

    # 3. Check user preference
    if getattr(user, 'llm_ctx_size', None) and int(user.llm_ctx_size) > 1:
        return ContextSizeResponse(context_size=int(user.llm_ctx_size))

    # 4. Engine probe fallback
    def _get_ctx_size():
        resolved_binding = binding_alias
        resolved_model = profile_key or request.model
        if not resolved_binding:
            resolved_binding, resolved_model = resolve_model_name(db, request.model)

        lc = build_lollms_client_from_params(user.username, resolved_binding, resolved_model, load_llm=True)
        context_size = lc.get_ctx_size(resolved_model) or lc.get_ctx_size()
        return ContextSizeResponse(context_size=context_size if context_size else getattr(lc.llm, 'default_ctx_size', 32000))

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

        # Normalize audio bytes
        final_bytes = audio_bytes
        if isinstance(audio_bytes, str):
            if audio_bytes.startswith("data:audio"):
                audio_bytes = audio_bytes.split(",", 1)[1]
            try:
                final_bytes = base64.b64decode(audio_bytes)
            except Exception:
                final_bytes = audio_bytes.encode('utf-8')
        elif hasattr(audio_bytes, 'getvalue'):
            final_bytes = audio_bytes.getvalue()
        elif hasattr(audio_bytes, 'read'):
            final_bytes = audio_bytes.read()

        fmt_clean = (request.response_format or "mp3").lower().strip()

        # If JSON response requested
        if request.return_json or fmt_clean in ("b64_json", "json"):
            b64_str = base64.b64encode(final_bytes).decode('utf-8')
            return TTSJsonResponse(
                audio_format=fmt_clean if fmt_clean != "b64_json" else "mp3",
                b64_audio=b64_str,
                text_length=len(cleaned_text),
                duration_seconds=None
            )

        # Map response format to content type
        format_to_mime = {
            "mp3": "audio/mpeg",
            "opus": "audio/opus",
            "aac": "audio/aac",
            "flac": "audio/flac",
            "wav": "audio/wav",
            "ogg": "audio/ogg",
            "pcm": "audio/pcm"
        }
        content_type = format_to_mime.get(fmt_clean, "audio/mpeg")

        return Response(
            content=final_bytes,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename=speech.{fmt_clean}"}
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


# --- NEW: Speech to Text (STT) Endpoints ---

def _execute_stt_transcription_raw(stt_engine, audio_data: bytes, **kwargs) -> str:
    """Polymorphic helper that runs transcription across varying STT binding interfaces."""
    if hasattr(stt_engine, 'transcribe_audio'):
        try:
            res = stt_engine.transcribe_audio(audio_data, **kwargs)
            if res is not None:
                return str(res).strip()
        except TypeError:
            try:
                res = stt_engine.transcribe_audio(audio_data)
                if res is not None:
                    return str(res).strip()
            except Exception:
                pass
        except Exception:
            pass

    if hasattr(stt_engine, 'transcribe'):
        try:
            res = stt_engine.transcribe(audio_data, **kwargs)
            if res is not None:
                return str(res).strip()
        except TypeError:
            try:
                res = stt_engine.transcribe(audio_data)
                if res is not None:
                    return str(res).strip()
            except Exception:
                pass
        except Exception:
            pass

    # File-based fallback for subprocesses / whisper CLI
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

@lollms_v1_router.post("/audio/transcriptions")
async def transcribe_speech(
    request: Request,
    user: DBUser = Depends(get_user_for_lollms_service),
    db: Session = Depends(get_db)
):
    """
    Transcribes spoken audio into text. Supports both:
    1. Standard multipart/form-data with file upload ('file', 'model', 'language', 'prompt', 'response_format')
    2. JSON application/json payload with base64 encoded audio ('audio', 'model', etc.)
    """
    loop = asyncio.get_running_loop()
    content_type = request.headers.get("content-type", "").lower()

    audio_bytes = None
    model_param = None
    language_param = None
    prompt_param = None
    response_format = "json"
    temperature_val = 0.0

    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        if not uploaded_file or not hasattr(uploaded_file, "read"):
            raise HTTPException(status_code=400, detail="Missing required 'file' upload in form-data.")
        audio_bytes = await uploaded_file.read()
        model_param = form.get("model")
        language_param = form.get("language")
        prompt_param = form.get("prompt")
        response_format = form.get("response_format", "json")
        try:
            temperature_val = float(form.get("temperature", 0.0))
        except (ValueError, TypeError):
            temperature_val = 0.0
    else:
        try:
            body = await request.json()
            stt_req = STTRequest(**body)
            model_param = stt_req.model
            language_param = stt_req.language
            prompt_param = stt_req.prompt
            response_format = stt_req.response_format or "json"
            temperature_val = stt_req.temperature or 0.0

            if stt_req.audio:
                raw_b64 = stt_req.audio
                if "base64," in raw_b64:
                    raw_b64 = raw_b64.split("base64,")[1]
                audio_bytes = base64.b64decode(raw_b64)
            elif stt_req.file_path and os.path.exists(stt_req.file_path):
                audio_bytes = Path(stt_req.file_path).read_bytes()
            else:
                raise HTTPException(status_code=400, detail="Provide 'audio' (base64) or upload an audio file.")
        except Exception as e:
            if isinstance(e, HTTPException): raise e
            raise HTTPException(status_code=400, detail=f"Invalid request: {e}")

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio content.")

    stt_binding_alias = None
    stt_model_name = None
    if model_param:
        if "/" in str(model_param):
            stt_binding_alias, stt_model_name = str(model_param).split("/", 1)
        else:
            stt_model_name = str(model_param)

    if not stt_binding_alias:
        user_stt = user.stt_binding_model_name
        if user_stt and "/" in user_stt:
            stt_binding_alias, stt_model_name = user_stt.split("/", 1)
        else:
            def_stt = db.query(DBSTTBinding).filter(DBSTTBinding.is_active == True).order_by(DBSTTBinding.id).first()
            if not def_stt:
                raise HTTPException(status_code=400, detail="No active STT binding configured.")
            stt_binding_alias = def_stt.alias
            stt_model_name = def_stt.default_model_name

    lc = await loop.run_in_executor(
        executor,
        lambda: build_lollms_client_from_params(
            username=user.username,
            load_llm=False,
            load_stt=True,
            stt_binding_alias=stt_binding_alias,
            stt_model_name=stt_model_name
        )
    )

    if not hasattr(lc, "stt") or not lc.stt:
        raise HTTPException(status_code=500, detail=f"STT binding '{stt_binding_alias}' could not be initialized.")

    kwargs = {}
    if language_param: kwargs["language"] = language_param
    if prompt_param: kwargs["prompt"] = prompt_param
    if temperature_val: kwargs["temperature"] = temperature_val

    transcript = await loop.run_in_executor(
        executor,
        lambda: _execute_stt_transcription_raw(lc.stt, audio_bytes, **kwargs)
    )

    fmt = str(response_format).lower().strip()
    if fmt == "text":
        return Response(content=transcript, media_type="text/plain")
    elif fmt == "verbose_json":
        return STTVerboseResponse(
            task="transcribe",
            language=language_param or "en",
            duration=None,
            text=transcript,
            segments=[{"id": 0, "text": transcript}]
        )
    else:
        return STTResponse(text=transcript, language=language_param)

@lollms_v1_router.post("/audio/translations")
async def translate_speech(
    request: Request,
    user: DBUser = Depends(get_user_for_lollms_service),
    db: Session = Depends(get_db)
):
    """Translates audio from any spoken language to English text."""
    return await transcribe_speech(request, user, db)


# --- NEW: Text to Music (TTM) Endpoints ---

def _execute_music_generation_raw(ttm_engine, prompt: str, **kwargs) -> bytes:
    """Invokes the configured Text-to-Music engine defensively."""
    for method_name in ('generate_music', 'generate_audio', 'generate', 'text_to_music'):
        if hasattr(ttm_engine, method_name) and callable(getattr(ttm_engine, method_name)):
            fn = getattr(ttm_engine, method_name)
            try:
                res = fn(prompt=prompt, **kwargs)
            except TypeError:
                res = fn(prompt)

            if isinstance(res, bytes):
                return res
            if isinstance(res, io.BytesIO):
                return res.getvalue()
            if isinstance(res, str):
                if res.startswith("data:audio"):
                    return base64.b64decode(res.split(",", 1)[1])
                file_p = Path(res)
                if file_p.exists() and file_p.is_file():
                    return file_p.read_bytes()
                try:
                    return base64.b64decode(res)
                except Exception:
                    pass

    raise AttributeError("Configured TTM engine does not support audio generation or produced an empty track.")

@lollms_v1_router.post("/audio/music")
async def generate_music(
    request: TTMRequest,
    fastapi_request: Request,
    user: DBUser = Depends(get_user_for_lollms_service),
    db: Session = Depends(get_db)
):
    """
    Generates music and audio tracks from text descriptions using active TTM bindings.
    Returns binary audio stream (default), base64 JSON, or server-hosted URL.
    """
    loop = asyncio.get_running_loop()

    ttm_alias = None
    ttm_model = None
    if request.model:
        if "/" in request.model:
            ttm_alias, ttm_model = request.model.split("/", 1)
        else:
            ttm_model = request.model

    if not ttm_alias:
        def_ttm = db.query(DBTTMBinding).filter(DBTTMBinding.is_active == True).order_by(DBTTMBinding.id).first()
        if not def_ttm:
            raise HTTPException(status_code=501, detail="No active Text-to-Music (TTM) binding configured on the server.")
        ttm_alias = def_ttm.alias
        ttm_model = ttm_model or def_ttm.default_model_name

    lc = await loop.run_in_executor(
        executor,
        lambda: build_lollms_client_from_params(
            username=user.username,
            load_llm=False,
            load_ttm=True,
            ttm_binding_alias=ttm_alias,
            ttm_model_name=ttm_model
        )
    )

    if not hasattr(lc, "ttm") or not lc.ttm:
        raise HTTPException(status_code=500, detail=f"TTM binding '{ttm_alias}' is not operational.")

    kwargs = {
        "duration": request.duration,
        "negative_prompt": request.negative_prompt
    }
    if request.bpm: kwargs["bpm"] = request.bpm
    if request.genre: kwargs["genre"] = request.genre

    try:
        audio_bytes = await loop.run_in_executor(
            executor,
            lambda: _execute_music_generation_raw(lc.ttm, request.prompt, **kwargs)
        )
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Music generation error: {e}")

    fmt_clean = (request.response_format or "audio").lower().strip()

    if fmt_clean in ("b64_json", "json"):
        b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
        return TTMResponse(
            b64_audio=b64_audio,
            duration=request.duration or 15,
            prompt=request.prompt
        )
    elif fmt_clean == "url":
        user_music_path = get_user_data_root(user.username) / "generated_audio"
        user_music_path.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.wav"
        (user_music_path / filename).write_bytes(audio_bytes)
        base_url = str(fastapi_request.base_url).rstrip("/")
        return TTMResponse(
            url=f"{base_url}/api/files/generated/{filename}",
            duration=request.duration or 15,
            prompt=request.prompt
        )

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": f"attachment; filename=track_{uuid.uuid4().hex[:8]}.wav"}
    )


# --- NEW: Text to Video (TTV) Endpoints ---

def _execute_video_generation_raw(ttv_engine, prompt: str, **kwargs) -> bytes:
    """Invokes the configured Text-to-Video engine defensively."""
    for method_name in ('generate_video', 'text_to_video', 'image_to_video', 'generate'):
        if hasattr(ttv_engine, method_name) and callable(getattr(ttv_engine, method_name)):
            fn = getattr(ttv_engine, method_name)
            try:
                res = fn(prompt=prompt, **kwargs)
            except TypeError:
                try:
                    res = fn(prompt)
                except Exception:
                    continue

            if isinstance(res, bytes):
                return res
            if isinstance(res, io.BytesIO):
                return res.getvalue()
            if isinstance(res, str):
                if res.startswith("data:video"):
                    return base64.b64decode(res.split(",", 1)[1])
                file_p = Path(res)
                if file_p.exists() and file_p.is_file():
                    return file_p.read_bytes()
                try:
                    return base64.b64decode(res)
                except Exception:
                    pass

    raise AttributeError("Configured TTV engine does not support video generation or produced an empty video stream.")

@lollms_v1_router.post("/video/generations", response_model=Union[TTVResponse, Any])
async def generate_video(
    request: TTVRequest,
    fastapi_request: Request,
    user: DBUser = Depends(get_user_for_lollms_service),
    db: Session = Depends(get_db)
):
    """
    Generates video clips from text prompts or initial image frames using active TTV bindings.
    Returns URL to hosted video file, base64 json, or binary stream.
    """
    loop = asyncio.get_running_loop()

    ttv_alias = None
    ttv_model = None
    if request.model:
        if "/" in request.model:
            ttv_alias, ttv_model = request.model.split("/", 1)
        else:
            ttv_model = request.model

    if not ttv_alias:
        def_ttv = db.query(DBTTVBinding).filter(DBTTVBinding.is_active == True).order_by(DBTTVBinding.id).first()
        if not def_ttv:
            raise HTTPException(status_code=501, detail="No active Text-to-Video (TTV) binding configured on the server.")
        ttv_alias = def_ttv.alias
        ttv_model = ttv_model or def_ttv.default_model_name

    lc = await loop.run_in_executor(
        executor,
        lambda: build_lollms_client_from_params(
            username=user.username,
            load_llm=False,
            load_ttv=True,
            ttv_binding_alias=ttv_alias,
            ttv_model_name=ttv_model
        )
    )

    if not hasattr(lc, "ttv") or not lc.ttv:
        raise HTTPException(status_code=500, detail=f"TTV binding '{ttv_alias}' is not operational.")

    kwargs = {
        "width": request.width or 512,
        "height": request.height or 512,
        "num_frames": request.num_frames or 24,
        "fps": request.fps or 12,
        "negative_prompt": request.negative_prompt,
        "seed": request.seed
    }
    if request.image:
        clean_img = request.image
        if "base64," in clean_img:
            clean_img = clean_img.split("base64,")[1]
        kwargs["image"] = clean_img

    try:
        video_bytes = await loop.run_in_executor(
            executor,
            lambda: _execute_video_generation_raw(lc.ttv, request.prompt, **kwargs)
        )
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Video generation error: {e}")

    fmt_clean = (request.response_format or "url").lower().strip()

    if fmt_clean == "b64_json":
        b64_video = base64.b64encode(video_bytes).decode("utf-8")
        return TTVResponse(
            b64_video=b64_video,
            width=request.width or 512,
            height=request.height or 512,
            num_frames=request.num_frames or 24,
            prompt=request.prompt
        )
    elif fmt_clean == "video":
        return Response(
            content=video_bytes,
            media_type="video/mp4",
            headers={"Content-Disposition": f"attachment; filename=clip_{uuid.uuid4().hex[:8]}.mp4"}
        )
    else:  # Default: URL
        user_video_path = get_user_data_root(user.username) / "generated_videos"
        user_video_path.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.mp4"
        (user_video_path / filename).write_bytes(video_bytes)
        base_url = str(fastapi_request.base_url).rstrip("/")
        return TTVResponse(
            url=f"{base_url}/api/files/generated/{filename}",
            width=request.width or 512,
            height=request.height or 512,
            num_frames=request.num_frames or 24,
            prompt=request.prompt
        )

# --- Per-Binding-Type Model Listing Endpoints ---

@lollms_v1_router.get("/{binding_type}/models", response_model=BindingModelListResponse)
async def list_models_for_binding_type(
    binding_type: str,
    binding_alias: Optional[str] = Query(None, description="Optional filter by specific binding alias"),
    mode: Optional[str] = Query(None, description="Advertisement mode: 'profiles_only' (default) or 'all_models'"),
    user: DBUser = Depends(get_user_for_lollms_service),
    db: Session = Depends(get_db)
):
    """
    Lists all available models for a specific binding modality adhering to the configured advertisement mode.
    Supported types: 'llm', 'tti', 'tts', 'stt', 'ttv', 'ttm', 'rag'.
    """
    normalized_type = binding_type.lower().strip()
    normalized_type = BINDING_ALIAS_NORMALIZER.get(normalized_type, normalized_type)

    if normalized_type not in BINDING_TYPE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported binding type '{binding_type}'. Supported types: {', '.join(BINDING_TYPE_MAP.keys())}"
        )

    setting_key = f"{normalized_type}_models_advertisement_mode"
    ad_mode = (mode or settings.get(setting_key, "profiles_only")).lower().strip()

    loop = asyncio.get_running_loop()
    model_items = await loop.run_in_executor(
        executor,
        lambda: _get_models_for_binding_type(db, normalized_type, binding_alias, ad_mode=ad_mode)
    )

    return BindingModelListResponse(
        object="list",
        binding_type=normalized_type,
        total=len(model_items),
        data=model_items
    )

@lollms_v1_router.get("/models", response_model=BindingModelListResponse)
async def list_all_service_models(
    binding_type: str = Query("llm", description="Binding modality type (llm, tti, tts, stt, ttv, ttm, rag)"),
    binding_alias: Optional[str] = Query(None, description="Optional filter by specific binding alias"),
    mode: Optional[str] = Query(None, description="Advertisement mode: 'profiles_only' (default) or 'all_models'"),
    user: DBUser = Depends(get_user_for_lollms_service),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint listing models for the specified binding type (defaults to 'llm').
    """
    return await list_models_for_binding_type(binding_type, binding_alias, mode, user, db)
