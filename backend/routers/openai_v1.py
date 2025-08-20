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


openai_v1_router = APIRouter(prefix="/v1")
bearer_scheme = HTTPBearer()

# --- Pydantic Models for OpenAI Compatibility ---

class ChatMessage(BaseModel):
    role: str
    content: str|List[Dict]

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    personality: Optional[str] = None # New field for personality
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

# --- NEW: Models for Embeddings ---
class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: str
    encoding_format: Optional[str] = "float"
    user: Optional[str] = None # Not used by us, but part of OpenAI spec

class EmbeddingObject(BaseModel):
    object: str = "embedding"
    embedding: List[float]
    index: int

class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingObject]
    model: str
    usage: UsageInfo

# Models for Tokenizer Endpoints
class TokenizeRequest(BaseModel):
    model: str
    text: str = Field(..., description="The text to be tokenized.")

class TokenizeResponse(BaseModel):
    tokens: List[int] = Field(..., description="The list of token IDs.")
    count: int = Field(..., description="The total number of tokens.")

class DetokenizeRequest(BaseModel):
    model: str
    tokens: List[int] = Field(..., description="The list of token IDs to be detokenized.")

class DetokenizeResponse(BaseModel):
    text: str = Field(..., description="The detokenized text.")

class CountTokensRequest(BaseModel):
    model: str
    text: str = Field(..., description="The text for which to count tokens.")

class CountTokensResponse(BaseModel):
    count: int = Field(..., description="The total number of tokens.")

# Models for Context Size Endpoint
class ContextSizeRequest(BaseModel):
    model: str = Field(..., description="The model name in 'binding_alias/model_name' format.")

class ContextSizeResponse(BaseModel):
    context_size: int = Field(..., description="The context window size of the model.")

# --- NEW: Models for Personality Endpoints ---
class PersonalityInfo(BaseModel):
    id: str
    object: str = "personality"
    name: str
    category: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    is_public: bool
    owner_username: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class PersonalityListResponse(BaseModel):
    object: str = "list"
    data: List[PersonalityInfo]


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
    
    parts = api_key.split('_')
    key_prefix = parts[0]+"_"+parts[1]

    db_key = db.query(DBAPIKey).filter(DBAPIKey.key_prefix == key_prefix).first()

    if not db_key:
        raise HTTPException(status_code=401, detail="Invalid API Key prefix.")
    
    if not verify_api_key(api_key, db_key.key_hash):
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
                    model_id = item.get("model_name") if isinstance(item, dict) else item
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


@openai_v1_router.get("/personalities", response_model=PersonalityListResponse)
async def list_personalities(
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    """
    Lists all personalities available to the authenticated user (owned and public).
    """
    personalities_db = db.query(DBPersonality).options(joinedload(DBPersonality.owner)).filter(
        or_(
            DBPersonality.is_public == True,
            DBPersonality.owner_user_id == user.id
        )
    ).order_by(DBPersonality.category, DBPersonality.name).all()
    
    response_data = []
    for p in personalities_db:
        owner_username = p.owner.username if p.owner else "System"
        p_info = PersonalityInfo.from_orm(p)
        p_info.owner_username = owner_username
        response_data.append(p_info)
        
    return PersonalityListResponse(data=response_data)


# --- Helper to Extract Images and Convert Messages ---
def preprocess_messages(messages: List[ChatMessage], image_list: List[str]) -> List[Dict]:
    processed = []

    for msg in messages:
        content = msg.content
        if isinstance(content, str):
            processed.append({"role": msg.role, "content": content})
        elif isinstance(content, list):
            text_parts = []
            for item in content:
                if item.get("type") == "image_url":
                    base64_img = item["image_url"].get("base64")
                    if base64_img:
                        image_list.append(base64_img)
                elif item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                else:
                    text_parts.append(str(item))
            processed.append({"role": msg.role, "content": "\n".join(text_parts)})
        else:
            processed.append({"role": msg.role, "content": str(content)})

    return processed


# --- Main Route ---
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
        lc = build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name,
            llm_params={
                "temperature": request.temperature,
                "max_output_tokens": request.max_tokens
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build LLM client: {str(e)}")

    # Handle personality as a system message if provided
    messages = list(request.messages)
    if request.personality:
        personality = db.query(DBPersonality).filter(DBPersonality.id == request.personality).first()
        if not personality:
            raise HTTPException(status_code=404, detail="Personality not found.")
        if not personality.is_public and personality.owner_user_id != user.id:
            raise HTTPException(status_code=403, detail="You cannot use this personality.")
        messages.insert(0, ChatMessage(role="system", content=personality.prompt_text))

    # Preprocess messages and extract images
    images: List[str] = []
    openai_messages = preprocess_messages(messages, images)

    # Streaming or regular completion
    if request.stream:
        async def stream_generator(lc, openai_messages, images, request):
            main_loop = asyncio.get_event_loop()
            stream_queue = asyncio.Queue()
            stop_event = threading.Event()

            completion_id = f"chatcmpl-{uuid.uuid4().hex}"
            created_ts = int(time.time())

            # Premier chunk = rôle assistant
            first_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": request.model,
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant"},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(first_chunk)}\n\n"

            def llm_callback(chunk: str, msg_type, params=None):
                if stop_event.is_set():
                    return False
                if msg_type == MSG_TYPE.MSG_TYPE_CHUNK:
                    response_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": request.model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": chunk},
                            "finish_reason": None
                        }]
                    }
                    main_loop.call_soon_threadsafe(
                        stream_queue.put_nowait, json.dumps(response_chunk)
                    )
                return True

            def blocking_call():
                try:
                    lc.generate_from_messages(
                        openai_messages,
                        streaming_callback=llm_callback,
                        images=images,
                        temperature=request.temperature,
                        n_predict=request.max_tokens
                    )
                except Exception as e:
                    print(f"Streaming error: {e}")
                finally:
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)

            threading.Thread(target=blocking_call, daemon=True).start()

            while True:
                item = await stream_queue.get()
                if item is None:
                    break
                yield f"data: {item}\n\n"

            # Dernier chunk = stop
            last_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": request.model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(last_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return EventSourceResponse(stream_generator(), media_type="text/event-stream")

    else:
        try:
            result = lc.generate_from_messages(
                openai_messages,
                images=images,
                temperature=request.temperature,
                n_predict=request.max_tokens
            )
            prompt_tokens = lc.count_tokens(str(openai_messages))
            completion_tokens = lc.count_tokens(result)
            return ChatCompletionResponse(
                model=request.model,
                choices=[ChatCompletionResponseChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=result),
                    finish_reason="stop"
                )],
                usage=UsageInfo(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens
                )
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Generation error: {e}")

@openai_v1_router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(
    request: EmbeddingRequest,
    user: DBUser = Depends(get_user_from_api_key)
):
    if not request.model or '/' not in request.model:
        raise HTTPException(status_code=400, detail="Invalid model name. Must be in 'binding_alias/model_name' format.")

    binding_alias, model_name = request.model.split('/', 1)

    try:
        # We need a client to access token counting and embedding functions
        lc = build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build LLM client: {str(e)}")

    if request.encoding_format != "float":
        #raise HTTPException(status_code=400, detail="Only 'float' encoding_format is supported.")
        ASCIIColors.warning(f"The request encoding format {request.encoding_format} is not supported. Only 'float' encoding_format is supported.")
        request.encoding_format = 'float'
    input_texts = [request.input] if isinstance(request.input, str) else request.input
    if not input_texts or not all(isinstance(t, str) for t in input_texts):
        raise HTTPException(status_code=400, detail="Invalid 'input' format. Must be a non-empty string or a list of non-empty strings.")

    embeddings_data = []
    total_tokens = 0
    try:
        for i, text in enumerate(input_texts):
            # The LollmsLLMBinding.embed method is expected to return a list of floats.
            embedding_vector = lc.embed(text) 
            if not isinstance(embedding_vector, list) or not all(isinstance(f, (float, int)) for f in embedding_vector):
                # Log the unexpected return type for debugging
                print(f"Warning: Binding '{binding_alias}' embed function returned an unexpected type for input '{text[:50]}...': {type(embedding_vector)}")
                raise HTTPException(status_code=500, detail=f"The embedding model for binding '{binding_alias}' returned an invalid data format.")

            embeddings_data.append(EmbeddingObject(embedding=embedding_vector, index=i))
            total_tokens += lc.count_tokens(text)
            
    except Exception as e:
        # Re-raise HTTP exceptions, wrap others
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to generate embeddings: {str(e)}")

    usage = UsageInfo(prompt_tokens=total_tokens, completion_tokens=0, total_tokens=total_tokens)
    
    return EmbeddingResponse(
        data=embeddings_data,
        model=request.model,
        usage=usage
    )

@openai_v1_router.post("/tokenize", response_model=TokenizeResponse)
async def tokenize_text(
    request: TokenizeRequest,
    user: DBUser = Depends(get_user_from_api_key)
):
    if not request.model or '/' not in request.model:
        raise HTTPException(status_code=400, detail="Invalid model name. Must be in 'binding_alias/model_name' format.")
    
    binding_alias, model_name = request.model.split('/', 1)
    
    try:
        lc = build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name
        )
        tokens = lc.tokenize(request.text)
        return TokenizeResponse(tokens=tokens, count=len(tokens))
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to tokenize text: {e}")

@openai_v1_router.post("/detokenize", response_model=DetokenizeResponse)
async def detokenize_tokens(
    request: DetokenizeRequest,
    user: DBUser = Depends(get_user_from_api_key)
):
    if not request.model or '/' not in request.model:
        raise HTTPException(status_code=400, detail="Invalid model name. Must be in 'binding_alias/model_name' format.")
    
    binding_alias, model_name = request.model.split('/', 1)
    
    try:
        lc = build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name
        )
        text = lc.detokenize(request.tokens)
        return DetokenizeResponse(text=text)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to detokenize tokens: {e}")

@openai_v1_router.post("/count_tokens", response_model=CountTokensResponse)
async def count_tokens(
    request: CountTokensRequest,
    user: DBUser = Depends(get_user_from_api_key)
):
    if not request.model or '/' not in request.model:
        raise HTTPException(status_code=400, detail="Invalid model name. Must be in 'binding_alias/model_name' format.")
    
    binding_alias, model_name = request.model.split('/', 1)
    
    try:
        lc = build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name
        )
        count = lc.count_tokens(request.text)
        return CountTokensResponse(count=count)
    except AttributeError:
        lc = build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name
        )
        count = lc.count_tokens(request.text)
        return CountTokensResponse(count=count)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to count tokens: {e}")

@openai_v1_router.post("/context_size", response_model=ContextSizeResponse)
async def get_model_context_size(
    request: ContextSizeRequest,
    user: DBUser = Depends(get_user_from_api_key)
):
    """
    Retrieves the context window size for a given model.
    """
    if not request.model or '/' not in request.model:
        raise HTTPException(status_code=400, detail="Invalid model name. Must be in 'binding_alias/model_name' format.")
    
    binding_alias, model_name = request.model.split('/', 1)
    
    try:
        lc = build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name
        )
        ctx_size = lc.get_ctx_size(model_name)
        return ContextSizeResponse(context_size=ctx_size)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve context size: {e}")
