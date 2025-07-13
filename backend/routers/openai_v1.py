# backend/routers/openai_v1.py
import time
import datetime
import json
import asyncio
import threading
import uuid
from typing import List, Optional, Dict, Any, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field

from backend.database_setup import get_db, User as DBUser, OpenAIAPIKey as DBAPIKey, LLMBinding as DBLLMBinding
from backend.security import verify_api_key
from backend.session import get_user_lollms_client, user_sessions
from backend.settings import settings
from lollms_client import LollmsPersonality, MSG_TYPE

openai_v1_router = APIRouter(prefix="/v1")
bearer_scheme = HTTPBearer()

# --- Pydantic Models for OpenAI Compatibility ---

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    # Other parameters can be added here if needed

class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = "stop"

class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: UsageInfo

# Models for Streaming
class DeltaMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None

class ChatCompletionResponseStreamChoice(BaseModel):
    index: int
    delta: DeltaMessage
    finish_reason: Optional[str] = None

class ChatCompletionStreamResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionResponseStreamChoice]


# --- Dependencies ---

async def get_user_from_api_key(
    authorization: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> DBUser:
    """
    Authenticates a user based on a given API key and ensures a session exists.
    """
    if not settings.get("openai_api_service_enabled", False):
        raise HTTPException(status_code=403, detail="OpenAI API service is not enabled by the administrator.")

    api_key = authorization.credentials
    if '_' not in api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key format.")
    
    key_prefix = api_key.split('_')[0] + '_'

    db_key = db.query(DBAPIKey).filter(DBAPIKey.key_prefix == key_prefix).first()

    if not db_key:
        raise HTTPException(status_code=401, detail="Invalid API Key prefix.")
    
    if not verify_api_key(api_key, db_key.key_hash):
        raise HTTPException(status_code=401, detail="Invalid API Key.")
        
    user = db.query(DBUser).filter(DBUser.id == db_key.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive.")

    # --- Ensure a session exists for the user ---
    # This is crucial for get_user_lollms_client to work correctly
    if user.username not in user_sessions:
        session_llm_params = {
            "ctx_size": user.llm_ctx_size, "temperature": user.llm_temperature,
            "top_k": user.llm_top_k, "top_p": user.llm_top_p,
            "repeat_penalty": user.llm_repeat_penalty, "repeat_last_n": user.llm_repeat_last_n
        }
        user_sessions[user.username] = {
            "lollms_clients": {}, "safe_store_instances": {}, "discussions": {},
            "active_vectorizer": user.safe_store_vectorizer,
            "lollms_model_name": user.lollms_model_name,
            "llm_params": {k: v for k, v in session_llm_params.items() if v is not None},
            "active_personality_id": user.active_personality_id,
        }

    db_key.last_used_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    return user

# --- Routes ---

@openai_v1_router.get("/models")
async def list_models(
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    all_models = []
    active_bindings = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()

    for binding in active_bindings:
        try:
            lc = get_user_lollms_client(user.username, binding.alias)
            models = lc.listModels()
            if isinstance(models, list):
                for item in models:
                    model_id = item.get("name") if isinstance(item, dict) else item
                    if model_id:
                        full_model_id = f"{binding.alias}/{model_id}"
                        all_models.append({
                            "id": full_model_id, "object": "model",
                            "created": int(time.time()), "owned_by": "lollms"
                        })
        except Exception as e:
            print(f"Could not fetch models from binding '{binding.alias}' for user '{user.username}': {e}")
            continue

    if not all_models:
        raise HTTPException(status_code=404, detail="No models found from any active bindings.")
    
    unique_models = {m["id"]: m for m in all_models}
    return {"object": "list", "data": sorted(list(unique_models.values()), key=lambda x: x['id'])}

@openai_v1_router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    if not request.model or '/' not in request.model:
        raise HTTPException(status_code=400, detail="Invalid model name. Must be in 'binding_alias/model_name' format.")
    
    binding_alias, model_name = request.model.split('/', 1)

    try:
        lc = get_user_lollms_client(user.username, binding_alias)
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"Failed to get LLM client for binding '{binding_alias}': {e.detail}")

    # Construct prompt from messages
    prompt = ""
    system_prompt = ""
    for message in request.messages:
        if message.role == "system":
            system_prompt += f"{message.content}\n"
        elif message.role == "user":
            prompt += f"\n!@>user\n{message.content}"
        elif message.role == "assistant":
            prompt += f"\n!@>assistant\n{message.content}"
    
    # Use user's active personality if no system prompt is provided in the request
    personality = LollmsPersonality(system_prompt=system_prompt) if system_prompt else None
    if not personality:
        if user.active_personality_id:
            db_pers = db.query(LollmsPersonality).get(user.active_personality_id)
            if db_pers:
                personality = LollmsPersonality(system_prompt=db_pers.prompt_text, script=db_pers.script_code)

    # Use user's LLM params and override with request params if provided
    llm_params = user_sessions.get(user.username, {}).get("llm_params", {}).copy()
    if request.temperature is not None:
        llm_params['temperature'] = request.temperature
    if request.max_tokens is not None:
        llm_params['max_output_tokens'] = request.max_tokens

    if request.stream:
        # --- Streaming Response ---
        async def stream_generator():
            main_loop = asyncio.get_event_loop()
            stream_queue = asyncio.Queue()
            stop_event = threading.Event()
            
            completion_id = f"chatcmpl-{uuid.uuid4().hex}"
            created_ts = int(time.time())

            # First chunk with role
            first_chunk_response = ChatCompletionStreamResponse(
                id=completion_id, model=request.model, created=created_ts,
                choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(role="assistant"), finish_reason=None)]
            )
            yield f"data: {first_chunk_response.model_dump_json()}\n\n"

            def llm_callback(chunk: str, msg_type: MSG_TYPE, params: Optional[Dict] = None):
                if stop_event.is_set(): return False
                
                if msg_type == MSG_TYPE.MSG_TYPE_CHUNK:
                    response_chunk = ChatCompletionStreamResponse(
                        id=completion_id, model=request.model, created=created_ts,
                        choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(content=chunk))]
                    )
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, response_chunk.model_dump_json())
                return True

            def blocking_call():
                try:
                    lc.generate(prompt, personality=personality, streaming_callback=llm_callback, **llm_params)
                except Exception as e:
                    print(f"Error during OpenAI API generation: {e}")
                finally:
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)

            threading.Thread(target=blocking_call, daemon=True).start()

            while True:
                item = await stream_queue.get()
                if item is None:
                    break
                yield f"data: {item}\n\n"
            
            # Final chunk
            final_chunk = ChatCompletionStreamResponse(
                id=completion_id, model=request.model, created=created_ts,
                choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(), finish_reason="stop")]
            )
            yield f"data: {final_chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"

        return EventSourceResponse(stream_generator(), media_type="text/event-stream")
    else:
        # --- Non-streaming Response ---
        try:
            full_response = lc.generate(prompt, personality=personality, **llm_params)
            
            prompt_tokens = len(lc.tokenize(prompt))
            completion_tokens = len(lc.tokenize(full_response))
            total_tokens = prompt_tokens + completion_tokens

            return ChatCompletionResponse(
                model=request.model,
                choices=[ChatCompletionResponseChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=full_response),
                    finish_reason="stop"
                )],
                usage=UsageInfo(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens
                )
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error during generation: {str(e)}")