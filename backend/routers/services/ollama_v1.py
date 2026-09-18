# backend/routers/services/ollama_v1.py
import time
import datetime
import json
import asyncio
import threading
import uuid
from typing import List, Optional, Dict, Any, Union
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.api_key import OpenAIAPIKey as DBAPIKey
from backend.db.models.config import LLMBinding as DBLLMBinding
from backend.security import verify_api_key
from backend.session import (
    user_sessions, build_lollms_client_from_params,
    _build_universal_profiles_for_modality
)
from backend.settings import settings
from backend.utils import track_service_usage, check_rate_limit
from lollms_client import MSG_TYPE
from ascii_colors import ASCIIColors, trace_exception
from backend.routers.services.openai_v1 import (
    ChatCompletionRequest, UsageInfo, DeltaMessage, 
    ChatCompletionResponseStreamChoice, ChatCompletionStreamResponse,
    preprocess_openai_messages, resolve_model_name, handle_tools_injection,
    parse_tool_calls_from_text, ChatCompletionResponse, ChatCompletionResponseChoice, ChatMessage
)

ollama_v1_router = APIRouter(prefix="/ollama/v1")
bearer_scheme = HTTPBearer(auto_error=False) 

# Create a thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=50)

async def get_user_from_api_key(authorization: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme), db: Session = Depends(get_db)) -> DBUser:
    if not settings.get("ollama_service_enabled", False):
        raise HTTPException(status_code=403, detail="Ollama API service disabled.")

    require_key = settings.get("ollama_require_key", True)
    if not require_key:
        user = db.query(DBUser).filter(DBUser.is_admin == True).first()
    else:
        if not authorization: raise HTTPException(status_code=401, detail="API Key required.")
        api_key = authorization.credentials
        if '_' not in api_key: raise HTTPException(status_code=401)
        key_parts = api_key.split('_')
        if len(key_parts) < 2: raise HTTPException(status_code=401)
        key_prefix = key_parts[0] + "_" + key_parts[1]
        db_key = db.query(DBAPIKey).filter(DBAPIKey.key_prefix == key_prefix).first()
        if not db_key or not verify_api_key(api_key, db_key.key_hash): raise HTTPException(status_code=401)
        user = db.query(DBUser).filter(DBUser.id == db_key.user_id).first()

    if not user or not user.is_active: raise HTTPException(status_code=401)
    
    identifier = authorization.credentials if authorization else "anonymous"
    if not check_rate_limit(identifier, "ollama"): raise HTTPException(status_code=429)

    track_service_usage("ollama", user.id)
    return user

@ollama_v1_router.get("/models")
async def list_models(user: DBUser = Depends(get_user_from_api_key), db: Session = Depends(get_db)):
    # --- FORCE MODEL MODE FOR LISTING ---
    force_model_mode = settings.get("force_model_mode", "disabled")
    forced_model = settings.get("force_model_name")
    if force_model_mode == "force_always" and forced_model:
        return {
            "object": "list",
            "data": [{
                "id": forced_model,
                "name": forced_model,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "lollms"
            }]
        }

    loop = asyncio.get_running_loop()

    def _list():
        all_models = []
        created_time = int(time.time())

        try:
            from backend.routers.admin.bindings_management import get_all_universal_profiles
            profiles_dict = asyncio.run(get_all_universal_profiles(modality="llm", db=db))
            model_profiles = profiles_dict.get("profiles", {})
        except Exception:
            try:
                _, model_profiles, _ = _build_universal_profiles_for_modality(
                    db=db,
                    binding_model_cls=DBLLMBinding,
                    active_binding_alias=None,
                    active_model_name=None,
                    user_overrides={}
                )
            except Exception as e:
                trace_exception(e)
                model_profiles = {}

        for prof_id, prof_info in model_profiles.items():
            if prof_info.get("is_available") is False:
                continue

            title = prof_info.get("title") or prof_info.get("name") or prof_id
            binding_alias = prof_info.get("binding_alias") or prof_info.get("binding_profile_name", "lollms")

            all_models.append({
                "id": prof_id,
                "name": title,
                "object": "model",
                "created": created_time,
                "owned_by": binding_alias
            })

        unique_models = {m["id"]: m for m in all_models}
        return {"object": "list", "data": sorted(list(unique_models.values()), key=lambda x: x['id'])}

    return await loop.run_in_executor(executor, _list)

@ollama_v1_router.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest, user: DBUser = Depends(get_user_from_api_key), db: Session = Depends(get_db)):
    loop = asyncio.get_running_loop()

    # Offload potentially blocking database model resolution
    binding_alias, model_name = await loop.run_in_executor(
        executor,
        lambda: resolve_model_name(db, request.model)
    )

    # Wrap client build
    lc = await loop.run_in_executor(
        executor, 
        lambda: build_lollms_client_from_params(user.username, binding_alias, model_name, llm_params={"temperature": request.temperature}, load_llm=True)
    )

    messages = list(request.messages)
    if request.personality:
        from backend.db.models.personality import Personality as DBPersonality
        def _fetch_personality():
            personality = db.query(DBPersonality).filter(DBPersonality.id == request.personality).first()
            return personality

        personality = await loop.run_in_executor(executor, _fetch_personality)
        if personality:
             messages.insert(0, ChatMessage(role="system", content=personality.prompt_text))

    openai_messages, images = preprocess_openai_messages(messages)
    if request.tools: openai_messages = handle_tools_injection(openai_messages, request.tools)

    generation_kwargs = {}
    if request.reasoning_effort: generation_kwargs["reasoning_effort"] = request.reasoning_effort

    if request.stream:
        async def stream_generator():
            try:
                if request.tools:
                    # Blocking generation for tools
                    result_content = await loop.run_in_executor(
                        executor,
                        lambda: lc.generate_from_messages(openai_messages, temperature=request.temperature, n_predict=request.max_tokens, images=images, **generation_kwargs)
                    )
                    content, tool_calls = parse_tool_calls_from_text(result_content)
                    completion_id, created_ts = f"chatcmpl-{uuid.uuid4().hex}", int(time.time())
                    yield f"data: {ChatCompletionStreamResponse(id=completion_id, model=request.model, created=created_ts, choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(role='assistant'))]).model_dump_json()}\n\n"
                    if content: yield f"data: {ChatCompletionStreamResponse(id=completion_id, model=request.model, created=created_ts, choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(content=content))]).model_dump_json()}\n\n"
                    if tool_calls:
                        for i, tc in enumerate(tool_calls):
                            tc.index = i
                            yield f"data: {ChatCompletionStreamResponse(id=completion_id, model=request.model, created=created_ts, choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(tool_calls=[tc]))]).model_dump_json()}\n\n"
                    yield f"data: {ChatCompletionStreamResponse(id=completion_id, model=request.model, created=created_ts, choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(), finish_reason='tool_calls' if tool_calls else 'stop')]).model_dump_json()}\n\n"
                    yield "data: [DONE]\n\n"
                else:
                    main_loop, stream_queue = asyncio.get_running_loop(), asyncio.Queue()
                    completion_id, created_ts = f"chatcmpl-{uuid.uuid4().hex}", int(time.time())
                    def llm_cb(chunk, msg_type, **kwargs):
                        if msg_type == MSG_TYPE.MSG_TYPE_CHUNK:
                            main_loop.call_soon_threadsafe(stream_queue.put_nowait, f"data: {ChatCompletionStreamResponse(id=completion_id, model=request.model, created=created_ts, choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(content=chunk))]).model_dump_json()}\n\n")
                        return True
                    def bg_gen():
                        try: lc.generate_from_messages(openai_messages, streaming_callback=llm_cb, images=images, n_predict=request.max_tokens, **generation_kwargs)
                        finally: main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)
                    
                    # Replace explicit threading with run_in_executor
                    main_loop.run_in_executor(executor, bg_gen)
                    
                    yield f"data: {ChatCompletionStreamResponse(id=completion_id, model=request.model, created=created_ts, choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(role='assistant'))]).model_dump_json()}\n\n"
                    while True:
                        item = await stream_queue.get()
                        if item is None: break
                        yield item
                    yield f"data: {ChatCompletionStreamResponse(id=completion_id, model=request.model, created=created_ts, choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(), finish_reason='stop')]).model_dump_json()}\n\n"
                    yield "data: [DONE]\n\n"
            except Exception:
                yield "data: [DONE]\n\n"
        return EventSourceResponse(stream_generator(), media_type="text/event-stream")
    else:
        loop = asyncio.get_running_loop()
        res_content = await loop.run_in_executor(
            executor,
            lambda: lc.generate_from_messages(openai_messages, images=images, n_predict=request.max_tokens, **generation_kwargs)
        )
        content, tool_calls = parse_tool_calls_from_text(res_content)
        prompt_tokens = await loop.run_in_executor(executor, lambda: lc.count_tokens(str(openai_messages)))
        completion_tokens = await loop.run_in_executor(executor, lambda: lc.count_tokens(res_content))
        
        return ChatCompletionResponse(model=request.model, choices=[ChatCompletionResponseChoice(index=0, message=ChatMessage(role="assistant", content=content, tool_calls=tool_calls), finish_reason="tool_calls" if tool_calls else "stop")], usage=UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=prompt_tokens + completion_tokens))
