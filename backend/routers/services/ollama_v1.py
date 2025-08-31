# backend/routers/ollama_v1.py
import time
import datetime
import json
import asyncio
import threading
import uuid
from typing import List, Optional, Dict, Any, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.api_key import OpenAIAPIKey as DBAPIKey
from backend.db.models.config import LLMBinding as DBLLMBinding
from backend.db.models.personality import Personality as DBPersonality
from backend.security import verify_api_key
from backend.session import get_user_lollms_client, user_sessions, build_lollms_client_from_params
from backend.settings import settings
from lollms_client import LollmsPersonality, MSG_TYPE
from ascii_colors import ASCIIColors
from backend.routers.services.openai_v1 import (
    ChatMessage, ChatCompletionRequest, UsageInfo,
    ChatCompletionResponseChoice, ChatCompletionResponse, DeltaMessage,
    ChatCompletionResponseStreamChoice, ChatCompletionStreamResponse,
    preprocess_messages
)

ollama_v1_router = APIRouter(prefix="/ollama/v1")
bearer_scheme = HTTPBearer(auto_error=False) 

async def get_user_from_api_key(
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> DBUser:
    """
    Authenticates a user for the Ollama service based on an API key or falls back to admin.
    """
    if not settings.get("ollama_service_enabled", False):
        raise HTTPException(status_code=403, detail="Ollama API service is not enabled by the administrator.")

    require_key = settings.get("ollama_require_key", True)

    if not require_key and not authorization:
        admin_user = db.query(DBUser).filter(DBUser.is_admin == True).order_by(DBUser.id).first()
        if not admin_user:
            raise HTTPException(status_code=503, detail="Ollama API is enabled without a key, but no admin user is configured.")
        
        if admin_user.username not in user_sessions:
            user_sessions[admin_user.username] = { "lollms_clients": {}, "lollms_model_name": admin_user.lollms_model_name, "llm_params": {}}
        return admin_user

    if not authorization:
        raise HTTPException(status_code=401, detail="API Key is required for the Ollama service.", headers={"WWW-Authenticate": "Bearer"})

    api_key = authorization.credentials
    if '_' not in api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key format.")
    
    parts = api_key.split('_')
    key_prefix = parts[0]+"_"+parts[1]

    db_key = db.query(DBAPIKey).filter(DBAPIKey.key_prefix == key_prefix).first()

    if not db_key or not verify_api_key(api_key, db_key.key_hash):
        raise HTTPException(status_code=401, detail="Invalid API Key.")
        
    user = db.query(DBUser).filter(DBUser.id == db_key.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive.")

    if user.username not in user_sessions:
        user_sessions[user.username] = { "lollms_clients": {}, "lollms_model_name": user.lollms_model_name, "llm_params": {}}

    db_key.last_used_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    return user

@ollama_v1_router.get("/models")
async def list_models(
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    # This mirrors the openai_v1 endpoint, as the keys grant access to the user's models.
    all_models = []
    active_bindings = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()
    for binding in active_bindings:
        try:
            lc = get_user_lollms_client(user.username, binding.alias)
            models = lc.listModels()
            if isinstance(models, list):
                for item in models:
                    model_id = item.get("model_name") if isinstance(item, dict) else item
                    if model_id:
                        full_model_id = f"{binding.alias}/{model_id}"
                        all_models.append({ "id": full_model_id, "object": "model", "created": int(time.time()), "owned_by": "lollms"})
        except Exception as e:
            print(f"Could not fetch models from binding '{binding.alias}' for user '{user.username}': {e}")
            continue
    return {"object": "list", "data": sorted(all_models, key=lambda x: x['id'])}

@ollama_v1_router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    if not request.model or '/' not in request.model:
        raise HTTPException(status_code=400, detail="Invalid model name. Must be in 'binding_alias/model_name' format.")
    binding_alias, model_name = request.model.split('/', 1)

    try:
        lc = build_lollms_client_from_params(
            username=user.username, binding_alias=binding_alias, model_name=model_name,
            llm_params={"temperature": request.temperature, "max_output_tokens": request.max_tokens}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build LLM client: {str(e)}")

    messages = list(request.messages)
    images: List[str] = []
    openai_messages = preprocess_messages(messages, images)

    if request.stream:
        async def stream_generator():
            main_loop = asyncio.get_event_loop()
            stream_queue = asyncio.Queue()
            stop_event = threading.Event()
            completion_id = f"chatcmpl-{uuid.uuid4().hex}"
            created_ts = int(time.time())
            yield f"data: {ChatCompletionStreamResponse(id=completion_id, model=request.model, created=created_ts, choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(role='assistant'), finish_reason=None)]).model_dump_json()}\n\n".encode("utf-8")
            def llm_callback(chunk: str, msg_type: MSG_TYPE, params: Optional[Dict] = None):
                if stop_event.is_set(): return False
                if msg_type == MSG_TYPE.MSG_TYPE_CHUNK:
                    response_chunk = ChatCompletionStreamResponse(id=completion_id, model=request.model, created=created_ts, choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(content=chunk))])
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, response_chunk.model_dump_json())
                return True
            def blocking_call():
                try:
                    lc.generate_from_messages(openai_messages, streaming_callback=llm_callback, images=images, temperature=request.temperature, n_predict=request.max_tokens)
                finally:
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)
            threading.Thread(target=blocking_call, daemon=True).start()
            while True:
                item = await stream_queue.get()
                if item is None: break
                yield f"data: {item}\n\n".encode("utf-8")
            yield f"data: {ChatCompletionStreamResponse(id=completion_id, model=request.model, created=created_ts, choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(), finish_reason='stop')]).model_dump_json()}\n\n".encode("utf-8")
            yield "data: [DONE]\n\n".encode("utf-8")
        return EventSourceResponse(stream_generator(), media_type="text/event-stream")
    else:
        try:
            result = lc.generate_from_messages(openai_messages, images=images, temperature=request.temperature, n_predict=request.max_tokens)
            prompt_tokens = lc.count_tokens(str(openai_messages))
            completion_tokens = lc.count_tokens(result)
            return ChatCompletionResponse(model=request.model, choices=[ChatCompletionResponseChoice(index=0, message=ChatMessage(role="assistant", content=result), finish_reason="stop")], usage=UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=prompt_tokens + completion_tokens))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Generation error: {e}")