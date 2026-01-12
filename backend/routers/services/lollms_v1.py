# [UPDATE] backend/routers/services/lollms_v1.py
import time
import datetime
import json
import base64
import uuid
from typing import List, Optional, Dict, Any, Union

from fastapi import APIRouter, Depends, HTTPException, Request
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
from backend.security import verify_api_key
from backend.session import user_sessions, build_lollms_client_from_params, get_safe_store_instance
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

async def get_user_for_lollms_service(
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> DBUser:
    if not settings.get("lollms_services_enabled", True):
        raise HTTPException(status_code=403, detail="LoLLMs exclusive services are disabled.")

    require_key = settings.get("lollms_services_require_key", True)
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
    active_bindings: Dict[str, List[str]] # e.g. {"llm": ["ollama", "bs"], "tti": [...]}

# --- Endpoints ---

@lollms_v1_router.get("/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities(user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
    """Returns a list of active platform capabilities and bindings."""
    caps = ["tokenize", "detokenize", "long_context_processing"]
    
    # Check RAG
    from backend.session import safe_store
    if safe_store is not None:
        caps.append("rag_query")
    
    # Check TTI (Image Generation & Editing)
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

@lollms_v1_router.get("/personalities", response_model=PersonalityListResponse)
async def list_personalities(user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
    personalities_db = db.query(DBPersonality).options(joinedload(DBPersonality.owner)).filter(
        or_(DBPersonality.is_public == True, DBPersonality.owner_user_id == user.id)
    ).all()
    return PersonalityListResponse(data=[PersonalityInfo.from_orm(p) for p in personalities_db])

@lollms_v1_router.post("/tokenize", response_model=TokenizeResponse)
async def tokenize_text(request: TokenizeRequest, user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
    binding_alias, model_name = resolve_model_name(db, request.model)
    lc = build_lollms_client_from_params(user.username, binding_alias, model_name)
    tokens = lc.tokenize(request.text)
    return TokenizeResponse(tokens=tokens, count=len(tokens))

@lollms_v1_router.post("/detokenize", response_model=DetokenizeResponse)
async def detokenize_tokens(request: DetokenizeRequest, user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
    binding_alias, model_name = resolve_model_name(db, request.model)
    lc = build_lollms_client_from_params(user.username, binding_alias, model_name)
    text = lc.detokenize(request.tokens)
    return DetokenizeResponse(text=text)

@lollms_v1_router.post("/context_size", response_model=ContextSizeResponse)
async def get_context_size(request: ContextSizeRequest, user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
    alias, name = resolve_model_name(db, request.model)
    lc = build_lollms_client_from_params(user.username, alias, name, load_llm=True)
    context_size = lc.get_ctx_size(name)
    return ContextSizeResponse(context_size=context_size if context_size else lc.llm.default_ctx_size)

@lollms_v1_router.post("/long_context_process")
async def process_long_context(request: LongContextRequest, user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
    binding_alias, model_name = None, None
    if request.model:
        binding_alias, model_name = resolve_model_name(db, request.model)
    lc = build_lollms_client_from_params(user.username, binding_alias, model_name)
    result = lc.long_context_processing(text_to_process=request.text, contextual_prompt=request.prompt, expected_generation_tokens=request.max_generation_tokens)
    return {"result": result}

@lollms_v1_router.post("/rag/query")
async def query_user_datastore(request: RagQueryRequest, user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
    try:
        ss = get_safe_store_instance(user.username, request.datastore_id, db, permission_level="read_query")
        with ss:
            results = ss.query(request.query, top_k=request.top_k, min_similarity_percent=request.min_similarity)
        from backend.routers.stores import _sanitize_numpy
        return _sanitize_numpy(results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {str(e)}")

@lollms_v1_router.post("/images/edit", response_model=ImageGenerationResponse)
async def edit_image_lollms(request: ImageEditRequest, user: DBUser = Depends(get_user_for_lollms_service), db: Session = Depends(get_db)):
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
