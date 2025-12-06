# backend/routers/services/ollama_v1.py
import time
import datetime
import json
import asyncio
import threading
import uuid
from typing import List, Optional, Dict, Any, Union, Tuple

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
from backend.session import user_sessions, build_lollms_client_from_params
from backend.settings import settings
from lollms_client import LollmsPersonality, MSG_TYPE
from ascii_colors import ASCIIColors
from backend.routers.services.openai_v1 import (
    ChatMessage, ChatCompletionRequest, UsageInfo,
    ChatCompletionResponseChoice, ChatCompletionResponse, DeltaMessage,
    ChatCompletionResponseStreamChoice, ChatCompletionStreamResponse,
    preprocess_messages, find_model_by_alias, resolve_model_name,
    handle_tools_injection, parse_tool_calls_from_text # Added imports
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

    if not require_key:
        admin_user = db.query(DBUser).filter(DBUser.is_admin == True).order_by(DBUser.id).first()
        if not admin_user:
            raise HTTPException(status_code=503, detail="Ollama API is enabled without a key, but no admin user is configured.")
        
        if admin_user.username not in user_sessions:
            session_llm_params = {
                "ctx_size": admin_user.llm_ctx_size, "temperature": admin_user.llm_temperature,
                "top_k": admin_user.llm_top_k, "top_p": admin_user.llm_top_p,
                "repeat_penalty": admin_user.llm_repeat_penalty, "repeat_last_n": admin_user.llm_repeat_last_n
            }
            user_sessions[admin_user.username] = {
                "safe_store_instances": {}, "discussions": {},
                "active_vectorizer": admin_user.safe_store_vectorizer,
                "lollms_model_name": admin_user.lollms_model_name,
                "llm_params": {k: v for k, v in session_llm_params.items() if v is not None},
                "active_personality_id": admin_user.active_personality_id,
            }
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
        session_llm_params = {
            "ctx_size": user.llm_ctx_size, "temperature": user.llm_temperature,
            "top_k": user.llm_top_k, "top_p": user.llm_top_p,
            "repeat_penalty": user.llm_repeat_penalty, "repeat_last_n": user.llm_repeat_last_n
        }
        user_sessions[user.username] = {
            "safe_store_instances": {}, "discussions": {},
            "active_vectorizer": user.safe_store_vectorizer,
            "lollms_model_name": user.lollms_model_name,
            "llm_params": {k: v for k, v in session_llm_params.items() if v is not None},
            "active_personality_id": user.active_personality_id,
        }

    db_key.last_used_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    return user

@ollama_v1_router.get("/models")
async def list_models(
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    all_models = []
    active_bindings = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()
    model_display_mode = settings.get("model_display_mode", "mixed")

    for binding in active_bindings:
        try:
            lc = build_lollms_client_from_params(user.username, binding_alias=binding.alias, load_llm=True)
            models = lc.list_models()
            
            model_aliases = binding.model_aliases or {}
            if isinstance(model_aliases, str):
                try:
                    model_aliases = json.loads(model_aliases)
                except Exception:
                    model_aliases = {}

            if isinstance(models, list):
                for item in models:
                    model_id = item if isinstance(item, str) else (item.get("name") or item.get("id") or item.get("model_name"))
                    if not model_id:
                        continue

                    alias_data = model_aliases.get(model_id)

                    if model_display_mode == 'aliased' and not alias_data:
                        continue

                    id_to_send = f"{binding.alias}/{model_id}"
                    name_to_send = id_to_send
                    if model_display_mode != 'original' and alias_data and alias_data.get('title'):
                        name_to_send = alias_data.get('title')

                    all_models.append({
                        "id": id_to_send,
                        "name": name_to_send,
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "lollms"
                    })
        except Exception as e:
            print(f"Could not fetch models from binding '{binding.alias}' for user '{user.username}': {e}")
            continue

    unique_models = {m["id"]: m for m in all_models}
    return {"object": "list", "data": sorted(list(unique_models.values()), key=lambda x: x['id'])}

@ollama_v1_router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    binding_alias, model_name = resolve_model_name(db, request.model)

    try:
        lc = build_lollms_client_from_params(
            username=user.username, binding_alias=binding_alias, model_name=model_name,
            llm_params={"temperature": request.temperature, "max_output_tokens": request.max_tokens},
            load_llm=True
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build LLM client: {str(e)}")

    messages = list(request.messages)
    openai_messages, images = preprocess_messages(messages)

    if request.tools:
        openai_messages = handle_tools_injection(openai_messages, request.tools)

    generation_kwargs = {}
    if request.reasoning_effort:
        generation_kwargs["reasoning_effort"] = request.reasoning_effort

    if request.stream:
        async def stream_generator():
            main_loop = asyncio.get_running_loop()
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
                    lc.generate_from_messages(
                        openai_messages, 
                        streaming_callback=llm_callback, 
                        images=images, 
                        temperature=request.temperature, 
                        #n_predict=request.max_tokens, 
                        **generation_kwargs)
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
            result_content = lc.generate_from_messages(openai_messages, images=images, temperature=request.temperature, n_predict=request.max_tokens, **generation_kwargs)
            
            content = result_content
            finish_reason = "stop"
            
            if request.tools:
                content, tool_calls = parse_tool_calls_from_text(result_content)
                if tool_calls:
                    finish_reason = "tool_calls"
                    # Create dict for choice as manual creation
                    choice_dict = {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": content,
                            "tool_calls": tool_calls
                        },
                        "finish_reason": finish_reason
                    }
                else:
                    choice_dict = {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": result_content
                        },
                        "finish_reason": "stop"
                    }
            else:
                 choice_dict = {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result_content
                    },
                    "finish_reason": "stop"
                }
            
            prompt_tokens = lc.count_tokens(str(openai_messages))
            completion_tokens = lc.count_tokens(result_content)

            return {
                "id": f"chatcmpl-{uuid.uuid4().hex}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.model,
                "choices": [choice_dict],
                "usage": UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=prompt_tokens + completion_tokens)
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Generation error: {e}")