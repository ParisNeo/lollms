# backend/routers/services/openai_v1.py
import time
import datetime
import json
import asyncio
import threading
import uuid
import base64
import re
import io
import random
import string
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Union, Any
from concurrent.futures import ThreadPoolExecutor
from fastapi import File, Form, UploadFile
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from pydantic import BaseModel, Field, ConfigDict
import os
import tempfile
from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.api_key import OpenAIAPIKey as DBAPIKey
from backend.db.models.config import (
    LLMBinding as DBLLMBinding, 
    TTIBinding as DBTTIBinding,
    TTSBinding as DBTTSBinding,
    STTBinding as DBSTTBinding,
    GlobalConfig
)
from backend.db.models.voice import UserVoice as DBUserVoice
from backend.db.models.personality import Personality as DBPersonality
from backend.security import verify_api_key
from backend.session import (
    user_sessions, build_lollms_client_from_params, get_user_data_root, 
    find_model_by_alias, resolve_model_name, invalidate_model_cache,
    get_universal_model_profile, _build_universal_profiles_for_modality, reset_client_state,
    cancel_client_generation, evict_client_from_registry
)
from backend.settings import settings
from lollms_client import LollmsPersonality, MSG_TYPE
from ascii_colors import ASCIIColors, trace_exception
from backend.routers.files import extract_text_from_file_bytes 
from backend.utils import track_service_usage, check_rate_limit, get_system_cache, set_system_cache
from backend.db.models.generation_metric import record_generation_metric

# --- Router Definition ---
openai_v1_router = APIRouter(prefix="/v1")
bearer_scheme = HTTPBearer(auto_error=False) 

# Create a thread pool for blocking operations
# Increased to handle high concurrency for OpenAI API requests
executor = ThreadPoolExecutor(max_workers=200)


#Constants
TTFT_TIMEOUT  = float(settings.get("stream_ttft_timeout",  300.0))   # 5 min default
CHUNK_TIMEOUT = float(settings.get("stream_chunk_timeout",  60.0))   # 60s default


# --- Pydantic Models for OpenAI Compatibility ---

class FunctionCall(BaseModel):
    name: Optional[str] = None
    arguments: Optional[str] = None

class ToolCall(BaseModel):
    index: Optional[int] = None
    id: Optional[str] = None
    type: str = "function"
    function: FunctionCall

class ChatMessage(BaseModel):
    role: str
    content: Optional[Union[str, List[Dict]]] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    reasoning_content: Optional[str] = None
    refusal: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str
    messages: List[ChatMessage]
    personality: Optional[str] = None 
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    max_completion_tokens: Optional[int] = None
    stream: Optional[bool] = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    response_format: Optional[Union[Dict[str, Any], str]] = None
    reasoning_effort: Optional[str] = None
    thinking: Optional[Union[bool, Dict[str, Any], str]] = None
    reasoning: Optional[Dict[str, Any]] = None
    stop: Optional[Union[str, List[str]]] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    user: Optional[str] = None

class CompletionTokensDetails(BaseModel):
    reasoning_tokens: Optional[int] = 0
    accepted_prediction_tokens: Optional[int] = 0
    rejected_prediction_tokens: Optional[int] = 0

class PromptTokensDetails(BaseModel):
    cached_tokens: Optional[int] = 0

class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    completion_tokens_details: Optional[CompletionTokensDetails] = None
    prompt_tokens_details: Optional[PromptTokensDetails] = None

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
    tool_calls: Optional[List[ToolCall]] = None
    reasoning_content: Optional[str] = None
    refusal: Optional[str] = None

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

# --- NEW: Models for Image Generation ---
class ImageGenerationRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    n: Optional[int] = Field(default=1, ge=1, le=10)
    quality: Optional[str] = "standard"
    response_format: Optional[str] = "url"
    size: Optional[str] = "1024x1024"
    style: Optional[str] = "vivid"
    user: Optional[str] = None

class ImageObject(BaseModel):
    b64_json: Optional[str] = None
    url: Optional[str] = None
    revised_prompt: Optional[str] = None

class ImageGenerationResponse(BaseModel):
    created: int = Field(default_factory=lambda: int(time.time()))
    data: List[ImageObject]

# --- NEW: Models for Embeddings ---
class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: str
    encoding_format: Optional[str] = "float"
    user: Optional[str] = None

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

# --- NEW: Models for File Extraction Endpoint ---
class FileExtractionRequest(BaseModel):
    file: str = Field(..., description="Base64 encoded file content.")
    filename: str = Field(..., description="Original filename with extension (e.g., my_doc.pdf).")

class FileExtractionResponse(BaseModel):
    text: str = Field(..., description="The extracted text content.")

# --- NEW: Models for OpenAI Audio Suite ---
class OpenAITTSRequest(BaseModel):
    input: str = Field(..., description="The text to generate audio for.")
    model: Optional[str] = Field(default="tts-1", description="The model to use ('tts-1', 'tts-1-hd', or 'binding_alias/model').")
    voice: Optional[str] = Field(default="alloy", description="Voice to use (alloy, echo, fable, onyx, nova, shimmer, or custom voice ID).")
    response_format: Optional[str] = Field(default="mp3", description="Audio format (mp3, opus, aac, flac, wav, pcm).")
    speed: Optional[float] = Field(default=1.0, ge=0.25, le=4.0, description="Audio speed.")

class AudioTranscriptionResponse(BaseModel):
    text: str

# --- NEW: Models for OpenAI Responses API ---
class ResponseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str
    input: Union[str, List[Any]]
    instructions: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    temperature: Optional[float] = None
    max_output_tokens: Optional[int] = None
    stream: Optional[bool] = False
    reasoning: Optional[Dict[str, Any]] = None
    reasoning_effort: Optional[str] = None
    thinking: Optional[Union[bool, Dict[str, Any], str]] = None

class ResponseOutputContent(BaseModel):
    type: str = "text"
    text: str

class ResponseOutputMessage(BaseModel):
    id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    type: str = "message"
    role: str = "assistant"
    content: List[ResponseOutputContent]

class ResponseObject(BaseModel):
    id: str = Field(default_factory=lambda: f"resp_{uuid.uuid4().hex}")
    object: str = "response"
    created_at: int = Field(default_factory=lambda: int(time.time()))
    model: str
    status: str = "completed"
    output: List[ResponseOutputMessage]
    usage: UsageInfo





def _prepare_generation(lc) -> None:
    """Call before every generation to arm a clean cancellation state."""
    reset_client_state(lc)


def _cancel_generation(lc) -> None:
    """Signals cancellation to client and closes connection to free backend server slots."""
    cancel_client_generation(lc)

def generate_mistral_compatible_id() -> str:
    """Generates a 9-character alphanumeric ID required by Mistral/LiteLLM."""
    import random
    import string
    return ''.join(random.choices(string.ascii_letters + string.digits, k=9))

_global_model_cache = None
_last_cache_time = 0
CACHE_TTL = 300 # 5 minutes

def get_cached_models(db: Session):
    global _global_model_cache, _last_cache_time
    
    # Try memory cache first for ultra-fast UI loading
    #if _global_model_cache and (time.time() - _last_cache_time < CACHE_TTL):
    #    return _global_model_cache

    config = db.query(GlobalConfig).filter(GlobalConfig.key == "cache_available_models").first()
    if config:
        try:
            data = json.loads(config.value).get("value")
            _global_model_cache = data
            _last_cache_time = time.time()
            return data
        except: return None
    return None

def set_cached_models(db: Session, models_list: list):
    config = db.query(GlobalConfig).filter(GlobalConfig.key == "cache_available_models").first()
    val = json.dumps({"value": models_list, "type": "cache"})
    if config:
        config.value = val
    else:
        config = GlobalConfig(key="cache_available_models", value=val, category="System Cache")
        db.add(config)
    db.commit()


# --- Dependencies ---

async def get_user_from_api_key(
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> DBUser:
    if not settings.get("openai_api_service_enabled", False):
        raise HTTPException(status_code=403, detail="OpenAI API service is not enabled by the administrator.")

    require_key = settings.get("openai_api_require_key", True)

    loop = asyncio.get_running_loop()

    if not require_key:
        # Offload the database queries to a thread to keep the primary event loop unblocked
        admin_user = await loop.run_in_executor(
            executor,
            lambda: db.query(DBUser).filter(DBUser.is_admin == True).order_by(DBUser.id).first()
        )
        if not admin_user:
            raise HTTPException(status_code=503, detail="OpenAI API is enabled without a key, but no admin user is configured to handle requests.")

        if admin_user.username not in user_sessions:
            session_llm_params = {
                "temperature": admin_user.llm_temperature,
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
        raise HTTPException(status_code=401, detail="API Key is required.", headers={"WWW-Authenticate": "Bearer"})

    api_key = authorization.credentials
    if '_' not in api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key format.")

    parts = api_key.split('_')
    key_prefix = parts[0] + "_" + parts[1]

    # Offload key verification and lookup transactions to prevent thread pools starvation
    db_key = await loop.run_in_executor(
        executor,
        lambda: db.query(DBAPIKey).filter(DBAPIKey.key_prefix == key_prefix).first()
    )

    if not db_key:
        raise HTTPException(status_code=401, detail="Invalid API Key prefix.")

    is_valid = await loop.run_in_executor(
        executor,
        lambda: verify_api_key(api_key, db_key.key_hash)
    )
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid API Key.")

    user = await loop.run_in_executor(
        executor,
        lambda: db.query(DBUser).filter(DBUser.id == db_key.user_id).first()
    )
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive.")

    if user.username not in user_sessions:
        # Use defensive getattr to map database parameters without triggering AttributeErrors
        session_llm_params = {
            "temperature": getattr(user, "llm_temperature", None),
            "top_k": getattr(user, "llm_top_k", None),
            "top_p": getattr(user, "llm_top_p", None),
            "repeat_penalty": getattr(user, "llm_repeat_penalty", None),
            "repeat_last_n": getattr(user, "llm_repeat_last_n", None)
        }
        user_sessions[user.username] = {
            "safe_store_instances": {}, "discussions": {},
            "active_vectorizer": getattr(user, "safe_store_vectorizer", None),
            "lollms_model_name": getattr(user, "lollms_model_name", None),
            "llm_params": {k: v for k, v in session_llm_params.items() if v is not None},
            "active_personality_id": getattr(user, "active_personality_id", None),
        }

    # Asynchronously update usage telemetry
    await loop.run_in_executor(
        executor,
        lambda: setattr(db_key, 'last_used_at', datetime.datetime.now(datetime.timezone.utc))
    )

    # Rate Limit Check
    is_rate_limited = await loop.run_in_executor(
        executor,
        lambda: check_rate_limit(api_key, "openai")
    )
    if not is_rate_limited:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

    await loop.run_in_executor(
        executor,
        lambda: track_service_usage("openai", user.id)
    )
    return user

# --- Helper to Extract Images and Convert Messages ---
def preprocess_openai_messages(messages: List[ChatMessage]) -> Tuple[List[Dict], List[str]]:
    processed = []
    image_list = []

    for msg in messages:
        msg_dict = {
            "role": msg.role,
            "content": msg.content
        }

        if msg.tool_call_id:
            msg_dict["tool_call_id"] = msg.tool_call_id

        if msg.name:
            msg_dict["name"] = msg.name

        if msg.tool_calls:
            msg_dict["tool_calls"] = [
                tc.model_dump() if hasattr(tc, 'model_dump') else tc
                for tc in msg.tool_calls
            ]

        if isinstance(msg.content, list):
            for item in msg.content:
                if item.get("type") == "input_image":
                    base64_img = item["image_url"]
                    if base64_img:
                        image_list.append(base64_img)
                elif item.get("type") == "image_url":
                    base64_img = item["image_url"]
                    if isinstance(base64_img, dict):
                        if "url" in base64_img.keys():
                            base64_img = base64_img["url"]
                    if base64_img:
                        image_list.append(base64_img)

        processed.append(msg_dict)

    return processed, image_list


def handle_response_format_injection(messages: List[Dict], response_format: Any) -> List[Dict]:
    """
    Enforces OpenAI Structured Outputs.
    If response_format is 'json_schema' or 'json_object', injects strict grammar and schema instructions.
    """
    if not response_format:
        return messages

    format_prompt = ""
    if isinstance(response_format, dict):
        fmt_type = response_format.get("type", "").lower()
        if fmt_type == "json_schema":
            json_schema = response_format.get("json_schema", {})
            schema_name = json_schema.get("name", "response")
            schema_desc = json_schema.get("description", "")
            schema_def = json_schema.get("schema", {})
            format_prompt = (
                f"\n\n### STRUCTURED OUTPUT JSON SCHEMA REQUIREMENTS\n"
                f"You MUST generate a response that strictly adheres to the following JSON schema.\n"
                f"Do NOT include markdown formatting, code block fences, explanations, or text outside the JSON object.\n"
                f"Schema Name: {schema_name}\n"
            )
            if schema_desc:
                format_prompt += f"Schema Description: {schema_desc}\n"
            format_prompt += f"JSON Schema:\n{json.dumps(schema_def, indent=2)}\n"
        elif fmt_type == "json_object":
            format_prompt = (
                "\n\n### OUTPUT FORMAT\n"
                "You MUST respond with a valid, well-formed JSON object. "
                "Do NOT include conversational text or explanations outside the JSON."
            )
    elif isinstance(response_format, str) and response_format.lower() in ("json", "json_object"):
        format_prompt = (
            "\n\n### OUTPUT FORMAT\n"
            "You MUST respond with a valid, well-formed JSON object."
        )

    if not format_prompt:
        return messages

    for msg in messages:
        if msg.get("role") == "system":
            msg["content"] = (msg.get("content") or "") + format_prompt
            return messages

    messages.insert(0, {"role": "system", "content": format_prompt.strip()})
    return messages

def extract_reasoning_parameters(request_obj: Any) -> Tuple[Optional[str], Optional[bool], Dict[str, Any]]:
    """
    Extracts reasoning effort and thinking activation from any API request object or dict.
    Supports OpenAI (reasoning_effort), Anthropic (thinking: {type, budget_tokens}),
    DeepSeek/vLLM (chat_template_kwargs, reasoning, think), and Ollama (options: {thinking}).
    Returns (reasoning_effort, reasoning_activation, extra_thinking_kwargs).
    """
    extra = getattr(request_obj, '__pydantic_extra__', {}) or {}
    if not isinstance(extra, dict):
        extra = {}

    def _get(key, default=None):
        val = getattr(request_obj, key, None)
        if val is not None:
            return val
        return extra.get(key, default)

    effort = _get("reasoning_effort") or _get("thinking_effort")
    thinking_val = _get("thinking")
    reasoning_val = _get("reasoning")
    think_val = _get("think")
    options_val = _get("options")
    chat_kwargs = _get("chat_template_kwargs")

    # Options fallback (Ollama style)
    if isinstance(options_val, dict):
        if effort is None:
            effort = options_val.get("reasoning_effort") or options_val.get("effort")
        if thinking_val is None:
            thinking_val = options_val.get("thinking") if "thinking" in options_val else options_val.get("think")

    # Chat template kwargs (vLLM / HuggingFace style)
    if isinstance(chat_kwargs, dict):
        if thinking_val is None:
            thinking_val = chat_kwargs.get("thinking")

    # Reasoning dict (OpenAI Responses / custom style)
    if isinstance(reasoning_val, dict):
        if effort is None:
            effort = reasoning_val.get("effort") or reasoning_val.get("reasoning_effort")
        if thinking_val is None and "enabled" in reasoning_val:
            thinking_val = reasoning_val.get("enabled")

    # Direct think flag
    if thinking_val is None and think_val is not None:
        thinking_val = think_val

    resolved_effort = None
    if effort is not None:
        c_eff = str(effort).strip().lower()
        if c_eff in ["none", "off", "disabled", "false", "0"]:
            resolved_effort = None
            if thinking_val is None:
                thinking_val = False
        elif c_eff in ["low", "medium", "high", "max"]:
            resolved_effort = c_eff
            if thinking_val is None:
                thinking_val = True
        else:
            resolved_effort = c_eff
            if thinking_val is None:
                thinking_val = True

    resolved_activation = None
    extra_thinking_kwargs = {}

    if isinstance(thinking_val, dict):
        t_type = str(thinking_val.get("type", "")).lower()
        if t_type == "enabled":
            resolved_activation = True
            if not resolved_effort:
                resolved_effort = thinking_val.get("effort") or "low"
        elif t_type == "disabled":
            resolved_activation = False
            resolved_effort = None

        if "budget_tokens" in thinking_val:
            extra_thinking_kwargs["budget_tokens"] = thinking_val["budget_tokens"]
            extra_thinking_kwargs["thinking_budget"] = thinking_val["budget_tokens"]
    elif isinstance(thinking_val, bool):
        resolved_activation = thinking_val
        if thinking_val and not resolved_effort:
            resolved_effort = "low"
        elif not thinking_val:
            resolved_effort = None
    elif isinstance(thinking_val, str):
        c_t = thinking_val.strip().lower()
        if c_t in ["true", "1", "enabled", "on", "yes"]:
            resolved_activation = True
            if not resolved_effort:
                resolved_effort = "low"
        elif c_t in ["false", "0", "disabled", "off", "no"]:
            resolved_activation = False
            resolved_effort = None

    if resolved_effort is not None and resolved_activation is None:
        resolved_activation = True

    return resolved_effort, resolved_activation, extra_thinking_kwargs

def parse_reasoning_and_content(text: Any) -> Tuple[str, Optional[str]]:
    """
    Separates chain-of-thought thinking blocks (<think>...</think> or <thought>...</thought>)
    from the final response content according to the OpenAI / DeepSeek standard.
    Returns: (cleaned_content, reasoning_content)
    """
    if not text:
        return "", None
    if not isinstance(text, str):
        text = str(text)

    think_match = re.search(r'<(?:think|thought)>([\s\S]*?)</(?:think|thought)>', text, re.IGNORECASE)
    if think_match:
        reasoning = think_match.group(1).strip()
        cleaned_content = re.sub(r'<(?:think|thought)>[\s\S]*?</(?:think|thought)>', '', text, flags=re.IGNORECASE).strip()
        return cleaned_content, (reasoning if reasoning else None)

    unclosed_match = re.search(r'<(?:think|thought)>([\s\S]*)$', text, re.IGNORECASE)
    if unclosed_match:
        reasoning = unclosed_match.group(1).strip()
        cleaned_content = text[:unclosed_match.start()].strip()
        return cleaned_content, (reasoning if reasoning else None)

    return text, None

def handle_tools_injection(messages: List[Dict], tools: List[Dict], tool_choice: Union[str, Dict] = None) -> List[Dict]:
    """
    Injects tool definitions into the system prompt.
    Explicitly instructs the model to use multiline JSON in markdown blocks.
    """
    ASCIIColors.yellow("--- TOOL INJECTION START ---")
    
    if isinstance(tool_choice, str) and tool_choice == "none":
        ASCIIColors.yellow("Tool choice is 'none'. Skipping injection.")
        return messages

    if not tools:
        ASCIIColors.yellow("No tools provided in request.")
        return messages

    ASCIIColors.info(f"Processing {len(tools)} tools...")

    tools_prompt = "\n\n### FUNCTION CALLING INSTRUCTIONS\n"
    tools_prompt += "You are an AI assistant capable of calling external functions.\n"
    tools_prompt += "To call a function, you MUST output a JSON object wrapped in a markdown code block.\n"
    tools_prompt += "Please write the JSON on multiple lines inside the code block for clarity.\n\n"
    tools_prompt += "Example:\n"
    tools_prompt += "```json\n"
    tools_prompt += "{\n"
    tools_prompt += '  "tool_calls": [\n'
    tools_prompt += '    {\n'
    tools_prompt += '      "name": "my_func",\n'
    tools_prompt += '      "arguments": {\n'
    tools_prompt += '        "arg": "value"\n'
    tools_prompt += '      }\n'
    tools_prompt += '    }\n'
    tools_prompt += '  ]\n'
    tools_prompt += "}\n"
    tools_prompt += "```\n"
    
    tools_prompt += "### AVAILABLE TOOLS:\n"
    for tool in tools:
        t_type = tool.get("type", "function")
        if t_type == "function":
            func = tool.get("function", {})
            name = func.get("name")
            desc = func.get("description", "No description provided.")
            params = json.dumps(func.get("parameters", {}))
            tools_prompt += f"- Function: {name}\n  Description: {desc}\n  Parameters: {params}\n\n"

    if isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
        forced_name = tool_choice.get("function", {}).get("name")
        tools_prompt += f"IMPORTANT: You MUST choose to call the function '{forced_name}' in your response.\n"
        ASCIIColors.cyan(f"Forcing tool usage: {forced_name}")
    elif tool_choice == "required":
        tools_prompt += "IMPORTANT: You MUST call one of the available functions in your response.\n"
        ASCIIColors.cyan("Forcing required tool usage.")
    else:
        tools_prompt += "If the user input requires a tool, output the markdown wrapped JSON. If not, respond normally with text.\n"

    system_found = False
    for msg in messages:
        if msg.get('role') == 'system':
            msg['content'] = (msg.get('content') or "") + tools_prompt
            system_found = True
            break
    
    if not system_found:
        messages.insert(0, {"role": "system", "content": tools_prompt})
    
    ASCIIColors.yellow("--- TOOL INJECTION END ---")
    return messages


def extract_json_candidates(text: str) -> List[str]:
    """
    Scans the text for valid top-level JSON objects by matching braces.
    """
    candidates = []
    brace_count = 0
    start_index = -1
    in_string = False
    escape = False

    for i, char in enumerate(text):
        if char == '"' and not escape:
            in_string = not in_string
        
        if not in_string:
            if char == '{':
                if brace_count == 0:
                    start_index = i
                brace_count += 1
            elif char == '}':
                if brace_count > 0:
                    brace_count -= 1
                    if brace_count == 0:
                        candidates.append(text[start_index : i+1])
                        start_index = -1
        
        if char == '\\':
            escape = not escape
        else:
            escape = False
            
    return candidates


# ── Lollms modern tool-call XML contract: <tool>{"name":..,"parameters":..}</tool>
# The lollms_client (>= new) emits tool calls to the streaming callback as
# MSG_TYPE_CHUNK payloads of the form ``<tool>{"name":..., "parameters":{...}}</tool>``
# and appends the same XML to the final text when non-streaming. This is a
# distinct wire format from the older ``<tool_call><function=...>`` blocks.
_LOLLMS_TOOL_XML_PATTERN = re.compile(
    r"<tool>\s*(\{.*?\})\s*</tool>",
    re.DOTALL,
)


def _parse_lollms_tool_xml(content: str) -> Tuple[Optional[str], Optional[List[ToolCall]]]:
    """
    Extracts modern lollms_client ``<tool>{"name":...,"parameters":{...}}</tool>``
    blocks. Returns (text_without_blocks_or_None, tool_calls_or_None).
    """
    if not content:
        return None, None

    matches = list(_LOLLMS_TOOL_XML_PATTERN.finditer(content))
    if not matches:
        return None, None

    tool_calls: List[ToolCall] = []
    for m in matches:
        raw = m.group(1).strip()
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            ASCIIColors.warning(
                f"[lollms tool xml] Dropped malformed JSON block: {raw[:120]}..."
            )
            continue
        if not isinstance(payload, dict):
            continue
        name = payload.get("name")
        if not name:
            continue
        params = payload.get("parameters")
        if isinstance(params, dict):
            args_str = json.dumps(params)
        elif params is None:
            args_str = "{}"
        else:
            args_str = str(params)
        tool_calls.append(
            ToolCall(
                id=generate_mistral_compatible_id(),
                type="function",
                function=FunctionCall(name=name, arguments=args_str),
            )
        )

    if not tool_calls:
        return None, None

    cleaned = _LOLLMS_TOOL_XML_PATTERN.sub("", content).strip()
    ASCIIColors.success(
        f"Parsed {len(tool_calls)} lollms-spec tool call(s) from <tool> XML."
    )
    return (cleaned if cleaned else None), tool_calls


def _parse_xml_tool_calls(content: str) -> Tuple[Optional[str], Optional[List[ToolCall]]]:
    """
    Parses XML-style tool calls emitted by opencode / Qwen / DeepSeek native formats:

        <tool_call>
        <function=NAME>
        <parameter=KEY>VALUE</parameter>
        ...
        </function>
        </tool_call>

    Values are JSON-decoded when possible, otherwise kept as raw strings.
    Returns (content_before_first_tool_call_or_None, tool_calls_or_None).
    """
    tool_call_pattern = re.compile(
        r"<tool_call>\s*<function=([^>\s]+)>(.*?)</function>\s*</tool_call>",
        re.DOTALL | re.IGNORECASE,
    )
    param_pattern = re.compile(
        r"<parameter=([^>\s]+)>(.*?)</parameter>",
        re.DOTALL | re.IGNORECASE,
    )

    matches = list(tool_call_pattern.finditer(content))
    if not matches:
        return None, None

    tool_calls: List[ToolCall] = []
    for match in matches:
        func_name = match.group(1).strip()
        body = match.group(2)

        arguments: Dict[str, Any] = {}
        for p_match in param_pattern.finditer(body):
            key = p_match.group(1).strip()
            raw_value = p_match.group(2).strip()
            try:
                arguments[key] = json.loads(raw_value)
            except (json.JSONDecodeError, ValueError):
                arguments[key] = raw_value

        tool_calls.append(
            ToolCall(
                id=generate_mistral_compatible_id(),
                type="function",
                function=FunctionCall(
                    name=func_name,
                    arguments=json.dumps(arguments),
                ),
            )
        )

    if not tool_calls:
        return None, None

    first_start = matches[0].start()
    text_before = content[:first_start].strip()
    final_content = text_before if text_before else None

    ASCIIColors.success(f"Parsed {len(tool_calls)} XML tool call(s).")
    return final_content, tool_calls


def parse_tool_calls_from_text(content: Any) -> Tuple[Optional[str], Optional[List[ToolCall]]]:
    """
    Parses the LLM output to find tool calls.
    Strategy -1: Modern lollms_client <tool>{"name":..,"parameters":..}</tool> XML.
    Strategy 0:  XML <tool_call><function=..>..</function></tool_call> blocks.
    Strategy 1:  JSON inside ```json code blocks.
    Strategy 2:  Raw JSON scanning fallback.
    """
    ASCIIColors.yellow("--- TOOL PARSING START ---")
    
    if not content:
        return None, None
    
    # Ensure content is a string before processing to avoid TypeErrors
    if not isinstance(content, str):
        content = str(content)

    ASCIIColors.cyan(f"Raw LLM Output (First 500 chars):\n{content[:500]}...")

    # Strategy -1: modern lollms_client <tool>JSON</tool> wrapper (highest priority).
    lollms_content, lollms_tool_calls = _parse_lollms_tool_xml(content)
    if lollms_tool_calls:
        ASCIIColors.yellow("--- TOOL PARSING END (Success - lollms <tool>) ---")
        return lollms_content, lollms_tool_calls

    # Strategy 0: XML-style tool calls (opencode / Qwen / DeepSeek native).
    xml_content, xml_tool_calls = _parse_xml_tool_calls(content)
    if xml_tool_calls:
        ASCIIColors.yellow("--- TOOL PARSING END (Success - XML) ---")
        return xml_content, xml_tool_calls

    valid_tool_call_data = None
    matched_text_segment = None

    # Strategy 1: Look for Markdown Code Blocks (Most Reliable)
    code_block_pattern = r"```(?:json|JSON)?\s*(.*?)\s*```"
    code_blocks = re.findall(code_block_pattern, content, re.DOTALL | re.IGNORECASE)
    
    if code_blocks:
        ASCIIColors.info(f"Found {len(code_blocks)} code blocks.")
        for block in code_blocks:
            clean_block = block.strip()
            if "tool_calls" in clean_block:
                try:
                    data = json.loads(clean_block)
                    if isinstance(data, dict) and "tool_calls" in data:
                        valid_tool_call_data = data
                        matched_text_segment = block
                        break
                except json.JSONDecodeError:
                    try:
                        repaired = clean_block.replace("'", '"').replace("True", "true").replace("False", "false")
                        data = json.loads(repaired)
                        if isinstance(data, dict) and "tool_calls" in data:
                            valid_tool_call_data = data
                            matched_text_segment = block
                            break
                    except: pass
    
    # Strategy 2: Fallback to scanning raw text for JSON candidates
    if not valid_tool_call_data:
        ASCIIColors.info("Scanning raw text for JSON candidates (Fallback)...")
        candidates = extract_json_candidates(content)
        for candidate in candidates:
            if "tool_calls" in candidate:
                try:
                    data = json.loads(candidate)
                    if isinstance(data, dict) and "tool_calls" in data:
                        valid_tool_call_data = data
                        matched_text_segment = candidate
                        break
                except json.JSONDecodeError:
                    try:
                        repaired = candidate.replace("'", '"').replace("True", "true").replace("False", "false")
                        data = json.loads(repaired)
                        if isinstance(data, dict) and "tool_calls" in data:
                            valid_tool_call_data = data
                            matched_text_segment = candidate
                            break
                    except: pass

    if valid_tool_call_data:
        openai_tool_calls = []
        if isinstance(valid_tool_call_data.get("tool_calls"), list):
            for tc in valid_tool_call_data["tool_calls"]:
                try:
                    args = tc.get("arguments", {})
                    if isinstance(args, dict):
                        args_str = json.dumps(args)
                    else:
                        args_str = str(args)

                    # Generate ID compliant with strict Mistral/LiteLLM requirements (9 alphanum chars)
                    t_id = generate_mistral_compatible_id()

                    tool_call = ToolCall(
                        id=t_id,
                        type="function",
                        function=FunctionCall(
                            name=tc.get("name"),
                            arguments=args_str
                        )
                    )
                    openai_tool_calls.append(tool_call)
                except Exception as e:
                    ASCIIColors.warning(f"Skipping malformed tool call: {e}")

        if openai_tool_calls:
            ASCIIColors.success(f"Successfully parsed {len(openai_tool_calls)} tool calls.")
            
            final_content = None
            if matched_text_segment:
                idx = content.find(matched_text_segment)
                if idx > 0:
                    text_before = content[:idx]
                    text_before = re.sub(r'```(?:json|JSON)?\s*$', '', text_before, flags=re.IGNORECASE).strip()
                    if text_before:
                        final_content = text_before
            
            ASCIIColors.yellow("--- TOOL PARSING END (Success) ---")
            return final_content, openai_tool_calls

    ASCIIColors.red("No valid 'tool_calls' structure found.")
    ASCIIColors.yellow("--- TOOL PARSING END (No Tools) ---")
    return content, None


# --- Routes ---

@openai_v1_router.get("/models")
async def list_models(
    mode: Optional[str] = Query(None, description="Listing mode: 'profiles_only' (default) or 'all_models'"),
    force_refresh: bool = Query(False, description="Force refresh of the model cache"),
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    ASCIIColors.panel(f"{user.username} is listing the models", f"Open AI V1")

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

    # Resolution of listing mode: query parameter overrides setting; checks modality setting first
    listing_mode = (mode or settings.get("llm_models_advertisement_mode") or settings.get("openai_models_mode", "profiles_only")).lower().strip()

    from backend.routers.admin.bindings_management import get_all_universal_profiles
    try:
        profiles_dict = await get_all_universal_profiles(modality="llm", db=db)
        model_profiles = profiles_dict.get("profiles", {})
    except Exception as e:
        ASCIIColors.warning(f"Error retrieving universal profiles for /v1/models: {e}")
        model_profiles = {}

    all_models = []
    created_time = int(time.time())

    if listing_mode in ["all_models", "binding_model", "all"]:
        # Mode B: Forward all available models across active bindings in binding/model format
        active_bindings = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()
        seen_ids = set()

        for prof_id, prof_info in model_profiles.items():
            if prof_info.get("is_available") is False or prof_info.get("is_online") is False:
                continue
            binding_alias = prof_info.get("binding_alias") or prof_info.get("binding_profile_name", "lollms")
            title = prof_info.get("title") or prof_info.get("name") or prof_id

            if prof_id not in seen_ids:
                seen_ids.add(prof_id)
                all_models.append({
                    "id": prof_id,
                    "name": title,
                    "object": "model",
                    "created": created_time,
                    "owned_by": binding_alias
                })

        for binding in active_bindings:
            if binding.name == 'smart_router' or binding.alias == 'smart_router':
                continue
            try:
                from lollms_client.lollms_llm_binding import list_binding_models as list_llm_binding_models
                raw_list = list_llm_binding_models(llm_binding_name=binding.name, llm_binding_config=binding.config or {})
                if isinstance(raw_list, list):
                    for r in raw_list:
                        m_name = r if isinstance(r, str) else (r.get("name") or r.get("id") or r.get("model_name"))
                        if m_name:
                            full_id = f"{binding.alias}/{m_name}"
                            if full_id not in seen_ids:
                                seen_ids.add(full_id)
                                all_models.append({
                                    "id": full_id,
                                    "name": m_name,
                                    "object": "model",
                                    "created": created_time,
                                    "owned_by": binding.alias
                                })
            except Exception:
                pass
    else:
        # Mode A (DEFAULT): Profiles Only with actual profile names as ID
        seen_ids = set()
        for prof_id, prof_info in model_profiles.items():
            if prof_info.get("is_available") is False or prof_info.get("is_online") is False:
                continue

            profile_name = prof_info.get("name") or prof_info.get("title") or prof_info.get("original_model_name") or prof_id.split("/")[-1]
            binding_alias = prof_info.get("binding_alias") or prof_info.get("binding_profile_name", "lollms")

            target_id = profile_name
            if target_id in seen_ids:
                target_id = f"{binding_alias}/{profile_name}"

            if target_id not in seen_ids:
                seen_ids.add(target_id)
                all_models.append({
                    "id": target_id,
                    "name": profile_name,
                    "object": "model",
                    "created": created_time,
                    "owned_by": binding_alias
                })

    final_list = sorted(all_models, key=lambda x: x['id'])
    return {"object": "list", "data": final_list}


@openai_v1_router.get("/personalities", response_model=PersonalityListResponse)
async def list_personalities(
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    loop = asyncio.get_running_loop()

    def _fetch():
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
        return response_data

    data = await loop.run_in_executor(executor, _fetch)

    text ="\n".join([
        "✅ Personalities fetched successfully!\n",
        f"   📊 Total: {len(data)} personalities\n",
        f"   👤 User: {user.username}"])

    ASCIIColors.panel(
        text,
        title="🎭 Lollms Personalities",
        border_style="green"
    )

    return PersonalityListResponse(data=data)

@openai_v1_router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    fastapi_request: Request,  
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    loop = asyncio.get_running_loop()
    # Offload potentially blocking database model resolution (without triggering broadcast storms)
    binding_alias, model_name = await loop.run_in_executor(
        executor,
        lambda: resolve_model_name(db, request.model)
    )

    # Extract reasoning effort and thinking parameters from client request
    client_effort, client_thinking, extra_thinking_kwargs = extract_reasoning_parameters(request)

    effective_max_tokens = request.max_completion_tokens if request.max_completion_tokens is not None else request.max_tokens

    llm_runtime_params = {
        "temperature": request.temperature,
        "max_output_tokens": effective_max_tokens
    }

    if client_effort is None or str(client_effort).lower() in ("none", "null", "off", "disabled", "false"):
        llm_runtime_params["think"] = None
        llm_runtime_params["thinking_effort"] = None
        llm_runtime_params["reasoning_effort"] = None
        llm_runtime_params["thinking"] = False
        llm_runtime_params["reasoning_activation"] = False
    else:
        llm_runtime_params["think"] = True
        llm_runtime_params["thinking"] = True
        llm_runtime_params["thinking_effort"] = client_effort
        llm_runtime_params["reasoning_effort"] = client_effort
        llm_runtime_params["reasoning_activation"] = True

    # Client building can be slow, might involve model loading.
    # Only load MCP when the request actually declares tools — avoids
    # expensive MCP discovery/handshake for plain chat completions.
    try:
        lc = await loop.run_in_executor(
            executor,
            lambda: build_lollms_client_from_params(
                username=user.username,
                binding_alias=binding_alias,
                model_name=model_name,
                llm_params=llm_runtime_params,
                load_llm=True,
                load_mcp=bool(request.tools)
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build LLM client: {str(e)}")

    # Offload personality database lookup to the thread pool
    messages = list(request.messages)
    if request.personality:
        def _fetch_personality():
            personality = db.query(DBPersonality).filter(DBPersonality.id == request.personality).first()
            if not personality:
                raise HTTPException(status_code=404, detail="Personality not found.")
            if not personality.is_public and personality.owner_user_id != user.id:
                raise HTTPException(status_code=403, detail="You cannot use this personality.")
            return personality

        personality = await loop.run_in_executor(executor, _fetch_personality)
        messages.insert(0, ChatMessage(role="system", content=personality.prompt_text))

    openai_messages, images = preprocess_openai_messages(messages)

    # Tools are forwarded verbatim to the binding (native OpenAI tool-calling).
    # handle_tools_injection() is a LEGACY fallback used only when the binding
    # rejects `tools=` as an unexpected keyword — see the generation calls below.
    tools_for_binding: Optional[List[Dict[str, Any]]] = request.tools or None
    tool_choice_for_binding: Optional[Union[str, Dict[str, Any]]] = (
        request.tool_choice if tools_for_binding else None
    )

    if request.response_format:
        openai_messages = handle_response_format_injection(openai_messages, request.response_format)

    generation_kwargs = {}
    if client_effort is None or str(client_effort).lower() in ("none", "null", "off", "disabled", "false") or client_thinking is False:
        generation_kwargs["think"] = None
        generation_kwargs["thinking_effort"] = None
        generation_kwargs["reasoning_effort"] = None
        generation_kwargs["thinking"] = False
        generation_kwargs["reasoning_activation"] = False
        generation_kwargs["chat_template_kwargs"] = {"thinking": False}
        generation_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    else:
        generation_kwargs["think"] = True
        generation_kwargs["thinking"] = True
        generation_kwargs["thinking_effort"] = client_effort
        generation_kwargs["reasoning_effort"] = client_effort
        generation_kwargs["reasoning_activation"] = True
    generation_kwargs.update(extra_thinking_kwargs)

    if request.top_p is not None:
        generation_kwargs["top_p"] = request.top_p
    if request.stop is not None:
        generation_kwargs["stop"] = [request.stop] if isinstance(request.stop, str) else request.stop

    stream_style = '\nTools requested in stream mode.' if request.tools else ""

    # Extract client network information safely
    client_ip = fastapi_request.client.host if fastapi_request.client else "unknown"
    client_port = fastapi_request.client.port if fastapi_request.client else "unknown"

    # Safely extract first 10 words of the final user prompt
    last_prompt = ""
    if request.messages:
        last_msg = request.messages[-1]
        if isinstance(last_msg.content, str):
            last_prompt = last_msg.content
        elif isinstance(last_msg.content, list):
            for item in last_msg.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    last_prompt = item.get("text", "")
                    break
                elif isinstance(item, dict) and "text" in item:
                    last_prompt = item["text"]
                    break

    prompt_words = (last_prompt or "").split()
    first_10_words = " ".join(prompt_words[:10]) + ("..." if len(prompt_words) > 10 else "")

    # Extract first 10 words of the system prompt if present
    system_prompt = ""
    for msg in messages:
        if msg.role == "system" and msg.content:
            if isinstance(msg.content, str):
                system_prompt = msg.content
                break
            elif isinstance(msg.content, list):
                for item in msg.content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        system_prompt = item.get("text", "")
                        break
                    elif isinstance(item, dict) and "text" in item:
                        system_prompt = item["text"]
                        break
                if system_prompt:
                    break

    sys_words = (system_prompt or "").split()
    sys_prompt_snippet = " ".join(sys_words[:10]) + ("..." if len(sys_words) > 10 else "") if sys_words else "None"

    ASCIIColors.panel(f"""[bold]Request:[/bold]Open AI V1
[bold]User:[/bold] {user.username}
[bold]Client IP:[/bold] {client_ip}
[bold]Client Port:[/bold] {client_port}
[bold]Model:[/bold] {request.model}
[bold]Bonding alias:[/bold] {binding_alias}
[bold]Model name:[/bold] {model_name}
[bold]Stream:[/bold] {request.stream}{stream_style}
[bold]Temperature:[/bold] {request.temperature}
[bold]Thinking:[/bold] {'active (' + str(client_effort or 'low') + ')' if client_thinking else 'inactive'}
[bold]Received images:[/bold] {len(images)}
[bold]Max Tokens:[/bold] {request.max_tokens}
[bold]Number of Messages:[/bold] {len(request.messages)}
[bold]System Prompt Snippet:[/bold] "{sys_prompt_snippet}"
[bold]Prompt Snippet:[/bold] "{first_10_words}""", title="Chat Completion Request", border_style="cyan")    # for message in request.messages:
    if request.stream:
            async def stream_generator():
                main_loop = asyncio.get_running_loop()
                stream_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
                completion_id = f"chatcmpl-{uuid.uuid4().hex}"
                created_ts = int(time.time())
                watcher_task: Optional[asyncio.Task] = None

                def make_chunk(delta: DeltaMessage, finish_reason=None) -> str:
                    chunk = ChatCompletionStreamResponse(
                        id=completion_id, model=request.model, created=created_ts,
                        choices=[ChatCompletionResponseStreamChoice(
                            index=0, delta=delta, finish_reason=finish_reason
                        )]
                    )
                    return f"data: {chunk.model_dump_json()}\n\n"

                def make_error_chunk(message: str) -> str:
                    """Emit an OpenAI-compatible error event before [DONE]."""
                    payload = json.dumps({"error": {"message": message, "type": "server_error"}})
                    return f"data: {payload}\n\n"

                async def watch_disconnect() -> None:
                    try:
                        receive = (
                            fastapi_request.scope.get("_receive")
                            or getattr(fastapi_request, "_receive", None)
                        )
                        if receive:
                            while True:
                                msg = await receive()
                                if msg.get("type") == "http.disconnect":
                                    break
                        else:
                            while not await fastapi_request.is_disconnected():
                                await asyncio.sleep(0.25)
                    except asyncio.CancelledError:
                        return
                    except Exception as e:
                        ASCIIColors.warning(f"[watch_disconnect] {e}")
                        return

                    ASCIIColors.warning(
                        f"[stream] Client '{user.username}' disconnected — cancelling."
                    )
                    nonlocal client_aborted
                    client_aborted = True
                    cancel_client_generation(lc)
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)

                generation_error = False
                client_aborted = False
                try:
                    _prepare_generation(lc)
                    watcher_task = asyncio.ensure_future(watch_disconnect())

                    # ── TOOLS PATH ────────────────────────────────────────────────────────
                    if request.tools:
                        # Some bindings reject unsupported reasoning kwargs. Build a safe
                        # kwargs set: only pass temperature + n_predict by default, and
                        # attempt to forward reasoning kwargs optimistically with fallback.
                        safe_kwargs = {"temperature": request.temperature, "n_predict": effective_max_tokens}

                        # Buffer accumulated text so we can parse tool_calls at the end while
                        # still streaming progressive content to the client.
                        buffered_text_parts: List[str] = []

                        # Modern lollms_client emits tool calls via the streaming
                        # callback as ``<tool>{"name":..,"parameters":..}</tool>``
                        # CHUNKs. We strip those from the delivered content stream
                        # and accumulate structured ToolCall objects to emit as
                        # native OpenAI tool_call deltas at stream end. We disable
                        # buffering when the client clearly can't consume them.
                        lollms_stream_tool_calls: List[ToolCall] = []
                        lollms_stream_pending = ""  # cross-chunk buffer for split <tool> blocks

                        def _flush_pending_as_content() -> None:
                            nonlocal lollms_stream_pending
                            if not lollms_stream_pending:
                                return
                            chunk = lollms_stream_pending
                            lollms_stream_pending = ""
                            buffered_text_parts.append(chunk)
                            main_loop.call_soon_threadsafe(
                                stream_queue.put_nowait,
                                make_chunk(DeltaMessage(content=chunk))
                            )

                        def _extract_stream_tools(chunk_text: str) -> str:
                            """
                            Extracts complete <tool>..</tool> blocks from the
                            incoming CHUNK. Incomplete trailing block is kept in
                            ``lollms_stream_pending`` for the next call. Returns
                            the visible content fragment to forward downstream.
                            """
                            nonlocal lollms_stream_pending
                            text = lollms_stream_pending + chunk_text
                            lollms_stream_pending = ""

                            visible_pieces: List[str] = []
                            cursor = 0
                            while True:
                                open_idx = text.find("<tool>", cursor)
                                if open_idx < 0:
                                    visible_pieces.append(text[cursor:])
                                    break
                                # Emit whatever text precedes the <tool> block
                                if open_idx > cursor:
                                    visible_pieces.append(text[cursor:open_idx])
                                close_idx = text.find("</tool>", open_idx)
                                if close_idx < 0:
                                    # Incomplete block; keep for next chunk.
                                    lollms_stream_pending = text[open_idx:]
                                    break
                                block = text[open_idx:close_idx + len("</tool>")]
                                _content, parsed = _parse_lollms_tool_xml(block)
                                if parsed:
                                    lollms_stream_tool_calls.extend(parsed)
                                else:
                                    # Unparseable — forward verbatim, never swallow.
                                    visible_pieces.append(block)
                                cursor = close_idx + len("</tool>")

                            return "".join(visible_pieces)

                        def tools_callback(chunk_text: str, msg_type: MSG_TYPE, **kwargs) -> bool:
                            if client_aborted or (lc and lc.cancel_generation):
                                return False
                            if lc and hasattr(lc, 'llm') and lc.llm:
                                if getattr(lc.llm, 'cancelled', False):
                                    return False
                                if hasattr(lc.llm, 'is_cancelled') and lc.llm.is_cancelled():
                                    return False

                            if msg_type == MSG_TYPE.MSG_TYPE_THOUGHT_CHUNK and chunk_text:
                                main_loop.call_soon_threadsafe(
                                    stream_queue.put_nowait,
                                    make_chunk(DeltaMessage(reasoning_content=chunk_text))
                                )
                                return True

                            # Native MSG_TYPE_TOOL_CALL — lollms bindings may
                            # invoke the callback with this type. Coerce to
                            # tool_calls; the payload is typically a dict.
                            if msg_type == MSG_TYPE.MSG_TYPE_TOOL_CALL and chunk_text:
                                payload = chunk_text
                                if isinstance(payload, str):
                                    try:
                                        payload = json.loads(payload)
                                    except (json.JSONDecodeError, ValueError):
                                        payload = None
                                if isinstance(payload, dict):
                                    name = payload.get("name") or payload.get("tool_name")
                                    raw_params = payload.get("parameters")
                                    if raw_params is None:
                                        raw_params = payload.get("arguments")
                                    if name:
                                        args_str = (
                                            json.dumps(raw_params)
                                            if isinstance(raw_params, (dict, list))
                                            else (raw_params if isinstance(raw_params, str) else "{}")
                                        )
                                        tc_id = (
                                            payload.get("id")
                                            or payload.get("tool_call_id")
                                            or generate_mistral_compatible_id()
                                        )
                                        lollms_stream_tool_calls.append(
                                            ToolCall(
                                                id=tc_id,
                                                type="function",
                                                function=FunctionCall(name=name, arguments=args_str),
                                            )
                                        )
                                        return True
                                ASCIIColors.warning(
                                    f"[tools_callback] Unhandled MSG_TYPE_TOOL_CALL payload: {str(payload)[:200]}"
                                )
                                return True

                            if msg_type == MSG_TYPE.MSG_TYPE_CHUNK and chunk_text:
                                visible = _extract_stream_tools(chunk_text)
                                if visible:
                                    buffered_text_parts.append(visible)
                                    main_loop.call_soon_threadsafe(
                                        stream_queue.put_nowait,
                                        make_chunk(DeltaMessage(content=visible))
                                    )
                            return True

                        def _is_unsupported_kwarg(ex: Exception) -> bool:
                            """Detects bindings that reject reasoning kwargs (TypeError, ValueError, or kwarg-related Exception)."""
                            if isinstance(ex, (TypeError, ValueError)):
                                return True
                            msg = str(ex).lower()
                            return (
                                "unexpected keyword" in msg
                                or "got an unexpected" in msg
                                or "invalid keyword" in msg
                                or "unexpected argument" in msg
                            )

                        # Capture native tool_calls emitted directly by the binding (dict /
                        # object / list shape depending on binding implementation).
                        native_tool_calls: List[ToolCall] = []
                        native_result_container: Dict[str, Any] = {}

                        def _collect_native_tool_calls(result: Any) -> None:
                            """Extracts native OpenAI wire-format tool_calls from a binding return value."""
                            candidates: List[Any] = []
                            if result is None:
                                return
                            if isinstance(result, dict):
                                if result.get("tool_calls"):
                                    candidates = result["tool_calls"]
                                elif isinstance(result.get("message"), dict) and result["message"].get("tool_calls"):
                                    candidates = result["message"]["tool_calls"]
                                else:
                                    native_result_container["raw"] = result
                                    return
                            elif isinstance(result, list):
                                candidates = result
                            elif hasattr(result, "tool_calls") and getattr(result, "tool_calls"):
                                candidates = list(result.tool_calls)
                            else:
                                native_result_container["raw"] = result
                                return

                            for tc in candidates:
                                try:
                                    if isinstance(tc, ToolCall):
                                        native_tool_calls.append(tc)
                                    elif isinstance(tc, dict):
                                        fn = tc.get("function", {}) or {}
                                        args = fn.get("arguments")
                                        if isinstance(args, dict):
                                            args = json.dumps(args)
                                        native_tool_calls.append(
                                            ToolCall(
                                                id=tc.get("id") or generate_mistral_compatible_id(),
                                                type=tc.get("type", "function"),
                                                function=FunctionCall(
                                                    name=fn.get("name"),
                                                    arguments=args if args is not None else "{}",
                                                ),
                                            )
                                        )
                                    elif hasattr(tc, "function"):
                                        fn = tc.function
                                        args = getattr(fn, "arguments", None)
                                        if isinstance(args, dict):
                                            args = json.dumps(args)
                                        native_tool_calls.append(
                                            ToolCall(
                                                id=getattr(tc, "id", None) or generate_mistral_compatible_id(),
                                                type=getattr(tc, "type", "function"),
                                                function=FunctionCall(
                                                    name=getattr(fn, "name", None),
                                                    arguments=args if args is not None else "{}",
                                                ),
                                            )
                                        )
                                except Exception as _tc_ex:
                                    ASCIIColors.warning(
                                        f"[tools_blocking_gen] Skipping malformed native tool_call: {_tc_ex}"
                                    )

                        # Track whether we fell back to prompt-injection so that the final
                        # buffer-parse step is only used for the legacy path (native
                        # responses are trusted as authoritative).
                        used_injection_fallback = False

                        def _call_binding_with_tools() -> Any:
                            """Call the binding forwarding native tools/tool_choice. Falls
                            back to prompt-injection if the binding rejects `tools=`."""
                            nonlocal used_injection_fallback
                            try:
                                return lc.generate_from_messages(
                                    openai_messages,
                                    streaming_callback=tools_callback,
                                    stream=True,
                                    tools=tools_for_binding,
                                    tool_choice=tool_choice_for_binding,
                                    **safe_kwargs,
                                    **generation_kwargs,
                                )
                            except Exception as native_ex:
                                if not _is_unsupported_kwarg(native_ex):
                                    raise
                                ASCIIColors.warning(
                                    f"[tools_blocking_gen] tools kwarg rejected ({native_ex}); "
                                    f"falling back to prompt-injection."
                                )
                            except TypeError:
                                pass  # fall through to injection fallback

                            # ── Legacy prompt-injection fallback ─────────────────────
                            used_injection_fallback = True
                            injected_messages = handle_tools_injection(
                                [dict(m) for m in openai_messages],
                                tools_for_binding or [],
                                tool_choice_for_binding,
                            )
                            try:
                                return lc.generate_from_messages(
                                    injected_messages,
                                    streaming_callback=tools_callback,
                                    stream=True,
                                    **safe_kwargs,
                                    **generation_kwargs,
                                )
                            except Exception as second_ex:
                                if not _is_unsupported_kwarg(second_ex):
                                    raise
                                ASCIIColors.warning(
                                    f"[tools_blocking_gen] kwarg rejected again ({second_ex}); "
                                    f"retrying without reasoning kwargs."
                                )
                                return lc.generate_from_messages(
                                    injected_messages,
                                    streaming_callback=tools_callback,
                                    stream=True,
                                    **safe_kwargs,
                                )

                        def tools_blocking_gen() -> None:
                            nonlocal generation_error
                            try:
                                result = _call_binding_with_tools()
                                _collect_native_tool_calls(result)
                            except Exception as ex:
                                generation_error = True
                                err_str = str(ex).lower()
                                ASCIIColors.error(f"[tools_blocking_gen] {ex}")
                                if "connection" in err_str or "disconnected" in err_str or "broken pipe" in err_str:
                                    evict_client_from_registry(lc, user.username)
                                main_loop.call_soon_threadsafe(
                                    stream_queue.put_nowait,
                                    make_error_chunk(str(ex))
                                )
                            finally:
                                main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)

                        gen_task_tools = loop.run_in_executor(executor, tools_blocking_gen)
                        yield make_chunk(DeltaMessage(role="assistant"))

                        # Drain the stream until sentinel
                        first_token_received_tools = False
                        tools_timed_out = False
                        while True:
                            timeout = CHUNK_TIMEOUT if first_token_received_tools else TTFT_TIMEOUT
                            try:
                                item = await asyncio.wait_for(stream_queue.get(), timeout=timeout)
                            except asyncio.TimeoutError:
                                tools_timed_out = True
                                if not first_token_received_tools:
                                    ASCIIColors.warning(
                                        f"[stream][tools] TTFT timeout ({TTFT_TIMEOUT}s) for user '{user.username}'. Cancelling."
                                    )
                                    await loop.run_in_executor(None, lambda: _cancel_generation(lc))
                                    yield make_error_chunk(
                                        f"Generation timed out waiting for first token ({TTFT_TIMEOUT:.0f}s)."
                                    )
                                else:
                                    ASCIIColors.warning(
                                        f"[stream][tools] Inter-chunk timeout ({CHUNK_TIMEOUT}s) for user '{user.username}'. Cancelling."
                                    )
                                    await loop.run_in_executor(None, lambda: _cancel_generation(lc))
                                    yield make_error_chunk(
                                        f"Generation stalled mid-stream ({CHUNK_TIMEOUT:.0f}s between tokens)."
                                    )
                                break
                            if item is None:
                                break
                            if not first_token_received_tools:
                                first_token_received_tools = True
                            yield item

                        # Flush any pending partial <tool> block before parsing so
                        # that no in-flight block is silently dropped.
                        if lollms_stream_pending:
                            _flush_pending_as_content()

                        # Parse buffered text for tool calls and emit final delta.
                        # Precedence: (1) native tool_calls from binding return,
                        # (2) lollms_stream_tool_calls accumulated from the
                        # streaming callback (modern lollms_client contract),
                        # (3) text-parsed fake tool calls (injection fallback).
                        full_text = "".join(buffered_text_parts)
                        parsed_tool_calls: Optional[List[ToolCall]] = None
                        if not native_tool_calls and not lollms_stream_tool_calls:
                            # Always run the text parser when tools were requested
                            # — modern lollms_client may emit <tool> blocks in
                            # the final text even when the streaming callback is
                            # not used (e.g. non-stream-internal fallbacks).
                            if used_injection_fallback or lollms_stream_tool_calls == []:
                                _parsed_content, parsed_tool_calls = parse_tool_calls_from_text(full_text)

                        tool_calls: List[ToolCall] = (
                            native_tool_calls
                            or lollms_stream_tool_calls
                            or parsed_tool_calls
                            or []
                        )

                        # If no text at all AND no tool calls AND no generation error -> empty output
                        if (
                            not generation_error
                            and not tool_calls
                            and not full_text.strip()
                            and not tools_timed_out
                        ):
                            ASCIIColors.warning(
                                f"[stream][tools] Empty generation result for user '{user.username}' "
                                f"(no content, no tool_calls)."
                            )
                            yield make_error_chunk(
                                "Model returned an empty response with tools enabled. "
                                "Check that the selected model supports tool/function calling."
                            )

                        # If tool calls were present, emit them as final deltas
                        if tool_calls:
                            for i, tc in enumerate(tool_calls):
                                tc.index = i
                                yield make_chunk(DeltaMessage(tool_calls=[tc]))

                        if lc.llm and not lc.llm.is_cancelled():
                            yield make_chunk(
                                DeltaMessage(),
                                finish_reason="tool_calls" if tool_calls else "stop"
                            )
                        yield "data: [DONE]\n\n"
                        return

                     # ── STREAMING PATH ────────────────────────────────────────────────────
                    in_reasoning = False

                    def llm_callback(chunk_text: str, msg_type: MSG_TYPE, **kwargs) -> bool:
                        nonlocal in_reasoning
                        if client_aborted or (lc and lc.cancel_generation):
                            return False
                        if lc and hasattr(lc, 'llm') and lc.llm:
                            if getattr(lc.llm, 'cancelled', False):
                                return False
                            if hasattr(lc.llm, 'is_cancelled') and lc.llm.is_cancelled():
                                return False

                        if msg_type == MSG_TYPE.MSG_TYPE_THOUGHT_CHUNK and chunk_text:
                            main_loop.call_soon_threadsafe(
                                stream_queue.put_nowait,
                                make_chunk(DeltaMessage(reasoning_content=chunk_text))
                            )
                            return True

                        if msg_type == MSG_TYPE.MSG_TYPE_CHUNK and chunk_text:
                            # Detect inline <think> tags for models emitting raw tokens
                            if "<think>" in chunk_text:
                                in_reasoning = True
                                parts = chunk_text.split("<think>", 1)
                                if parts[0]:
                                    main_loop.call_soon_threadsafe(
                                        stream_queue.put_nowait,
                                        make_chunk(DeltaMessage(content=parts[0]))
                                    )
                                chunk_text = parts[1]

                            if in_reasoning:
                                if "</think>" in chunk_text:
                                    parts = chunk_text.split("</think>", 1)
                                    if parts[0]:
                                        main_loop.call_soon_threadsafe(
                                            stream_queue.put_nowait,
                                            make_chunk(DeltaMessage(reasoning_content=parts[0]))
                                        )
                                    in_reasoning = False
                                    if parts[1]:
                                        main_loop.call_soon_threadsafe(
                                            stream_queue.put_nowait,
                                            make_chunk(DeltaMessage(content=parts[1]))
                                        )
                                else:
                                    main_loop.call_soon_threadsafe(
                                        stream_queue.put_nowait,
                                        make_chunk(DeltaMessage(reasoning_content=chunk_text))
                                    )
                            else:
                                main_loop.call_soon_threadsafe(
                                    stream_queue.put_nowait,
                                    make_chunk(DeltaMessage(content=chunk_text))
                                )
                        return True

                    # Use a dedicated thread for generation to prevent event loop starvation
                    def blocking_gen() -> None:
                        nonlocal generation_error
                        try:
                            lc.generate_from_messages(
                                openai_messages,
                                streaming_callback=llm_callback,
                                temperature=request.temperature,
                                n_predict=effective_max_tokens,
                                stream=True,
                                **generation_kwargs
                            )
                        except Exception as ex:
                            generation_error = True
                            err_str = str(ex).lower()
                            ASCIIColors.error(f"[blocking_gen] {ex}")
                            if "connection" in err_str or "disconnected" in err_str or "broken pipe" in err_str:
                                evict_client_from_registry(lc, user.username)
                            main_loop.call_soon_threadsafe(
                                stream_queue.put_nowait,
                                make_error_chunk(str(ex))
                            )
                        finally:
                            main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)

                    # Run in executor to isolate execution and prevent blocking
                    gen_task = loop.run_in_executor(executor, blocking_gen)
                    yield make_chunk(DeltaMessage(role="assistant"))

                    first_token_received = False

                    while True:
                        # Use a longer timeout until we get the first token (TTFT),
                        # then switch to the shorter inter-chunk timeout.
                        timeout = CHUNK_TIMEOUT if first_token_received else TTFT_TIMEOUT

                        try:
                            item = await asyncio.wait_for(
                                stream_queue.get(), timeout=timeout
                            )
                        except asyncio.TimeoutError:
                            if not first_token_received:
                                ASCIIColors.warning(
                                    f"[stream] TTFT timeout ({TTFT_TIMEOUT}s) — "
                                    f"no first token received for user '{user.username}'. Cancelling."
                                )
                                await loop.run_in_executor(None, lambda: _cancel_generation(lc))
                                yield make_error_chunk(
                                    f"Generation timed out waiting for first token "
                                    f"({TTFT_TIMEOUT:.0f}s). "
                                    f"The model may be overloaded or the context is too large."
                                )
                            else:
                                ASCIIColors.warning(
                                    f"[stream] Inter-chunk timeout ({CHUNK_TIMEOUT}s) — "
                                    f"stalled mid-stream for user '{user.username}'. Cancelling."
                                )
                                await loop.run_in_executor(None, lambda: _cancel_generation(lc))
                                yield make_error_chunk(
                                    f"Generation stalled mid-stream ({CHUNK_TIMEOUT:.0f}s "
                                    f"between tokens). Partial response may have been received."
                                )
                            break

                        if item is None:
                            # None is the sentinel from blocking_gen or watch_disconnect
                            break

                        # Mark first token received before yielding
                        if not first_token_received:
                            first_token_received = True

                        yield item

                    if lc.llm and not lc.llm.is_cancelled():
                        yield make_chunk(DeltaMessage(), finish_reason="stop")
                    yield "data: [DONE]\n\n"

                except Exception as e:
                    generation_error = True
                    err_msg = str(e)
                    ASCIIColors.error(f"[stream_generator] Crash: {e}")
                    trace_exception(e)
                    if "connection" in err_msg.lower() or "disconnected" in err_msg.lower():
                        evict_client_from_registry(lc, user.username)
                    yield make_error_chunk(err_msg)
                    yield "data: [DONE]\n\n"
                finally:
                    if client_aborted or generation_error:
                        cancel_client_generation(lc)
                    else:
                        reset_client_state(lc)

                    if watcher_task and not watcher_task.done():
                        watcher_task.cancel()
                        try:
                            await watcher_task
                        except asyncio.CancelledError:
                            pass

            return StreamingResponse(stream_generator(), media_type="text/event-stream")

    else:
        async def wait_for_disconnect() -> None:
            try:
                receive = (
                    fastapi_request.scope.get("_receive")
                    or getattr(fastapi_request, "_receive", None)
                )
                if receive:
                    while True:
                        msg = await receive()
                        if msg.get("type") == "http.disconnect":
                            return
                else:
                    while not await fastapi_request.is_disconnected():
                        await asyncio.sleep(0.25)
            except (asyncio.CancelledError, Exception):
                pass

        _prepare_generation(lc)

        def _non_stream_generate() -> Any:
            """Forward native tools when possible; fall back to prompt-injection otherwise."""
            if tools_for_binding:
                try:
                    return lc.generate_from_messages(
                        openai_messages,
                        temperature=request.temperature,
                        n_predict=effective_max_tokens,
                        tools=tools_for_binding,
                        tool_choice=tool_choice_for_binding,
                        **generation_kwargs,
                    )
                except Exception as native_ex:
                    msg = str(native_ex).lower()
                    is_kwarg_reject = isinstance(native_ex, TypeError) or any(
                        tok in msg for tok in (
                            "unexpected keyword", "got an unexpected",
                            "invalid keyword", "unexpected argument",
                        )
                    )
                    if not is_kwarg_reject:
                        raise
                    ASCIIColors.warning(
                        f"[non_stream] tools kwarg rejected ({native_ex}); "
                        f"falling back to prompt-injection."
                    )
                    injected = handle_tools_injection(
                        [dict(m) for m in openai_messages],
                        tools_for_binding,
                        tool_choice_for_binding,
                    )
                    try:
                        return lc.generate_from_messages(
                            injected,
                            temperature=request.temperature,
                            n_predict=effective_max_tokens,
                            **generation_kwargs,
                        )
                    except Exception as second_ex:
                        if not (
                            isinstance(second_ex, TypeError)
                            or "unexpected keyword" in str(second_ex).lower()
                        ):
                            raise
                        return lc.generate_from_messages(
                            injected,
                            temperature=request.temperature,
                            n_predict=effective_max_tokens,
                        )

            return lc.generate_from_messages(
                openai_messages,
                temperature=request.temperature,
                n_predict=effective_max_tokens,
                **generation_kwargs,
            )

        gen_future = loop.run_in_executor(executor, _non_stream_generate)
        disconnect_task = asyncio.ensure_future(wait_for_disconnect())
        gen_task = asyncio.ensure_future(gen_future)

        try:
            done, _ = await asyncio.wait(
                {gen_task, disconnect_task},
                return_when=asyncio.FIRST_COMPLETED
            )

            if disconnect_task in done and gen_task not in done:
                ASCIIColors.warning(
                    f"[non-stream] Client '{user.username}' disconnected — cancelling."
                )
                # Cancel at the binding level first (fast for HTTP bindings)
                await loop.run_in_executor(None, lambda: _cancel_generation(lc))
                raise HTTPException(status_code=499, detail="Client disconnected.")

            result_content = await gen_task

        except Exception as e:
            if "connection" in str(e).lower() or "disconnected" in str(e).lower() or "broken pipe" in str(e).lower():
                evict_client_from_registry(lc, user.username)
            raise
        finally:
            # Only signal cancellation if the client actually disconnected prematurely
            if disconnect_task in done and gen_task not in done:
                cancel_client_generation(lc)
            else:
                reset_client_state(lc)

            for t in [gen_task, disconnect_task]:
                if not t.done():
                    t.cancel()
                    try:
                        await t
                    except (asyncio.CancelledError, Exception):
                        pass

        try:
            # Fix: lollms_client returns {"status": "error", "message": err_msg}
            # We need to check for string "error" as well as boolean False
            if isinstance(result_content, dict) and (
                result_content.get("status") == "error" or 
                result_content.get("status") is False or
                "error" in result_content
            ):
                error_detail = result_content.get("message") or result_content.get("error", "LLM Binding error.")
                raise HTTPException(
                    status_code=result_content.get("status_code", 500),
                    detail=error_detail
                )

            clean_content = ""
            reasoning_content: Optional[str] = None
            finish_reason = "stop"
            tool_calls: Optional[List[ToolCall]] = None

            # Native tool_calls detection — the OpenAI-compatible transport contract.
            # lollms bindings can return tool_calls as either a dict key or attribute.
            native_tool_calls_ns: List[ToolCall] = []

            def _collect_from_result(result: Any) -> None:
                candidates: List[Any] = []
                if not result:
                    return
                if isinstance(result, dict):
                    if result.get("tool_calls"):
                        candidates = result["tool_calls"]
                    elif isinstance(result.get("message"), dict) and result["message"].get("tool_calls"):
                        candidates = result["message"]["tool_calls"]
                elif hasattr(result, "tool_calls") and getattr(result, "tool_calls"):
                    candidates = list(result.tool_calls)

                for tc in candidates:
                    try:
                        if isinstance(tc, ToolCall):
                            native_tool_calls_ns.append(tc)
                            continue
                        if isinstance(tc, dict):
                            fn = tc.get("function", {}) or {}
                            args = fn.get("arguments")
                            if isinstance(args, dict):
                                args = json.dumps(args)
                            native_tool_calls_ns.append(ToolCall(
                                id=tc.get("id") or generate_mistral_compatible_id(),
                                type=tc.get("type", "function"),
                                function=FunctionCall(
                                    name=fn.get("name"),
                                    arguments=args if args is not None else "{}",
                                ),
                            ))
                            continue
                        if hasattr(tc, "function"):
                            fn = tc.function
                            args = getattr(fn, "arguments", None)
                            if isinstance(args, dict):
                                args = json.dumps(args)
                            native_tool_calls_ns.append(ToolCall(
                                id=getattr(tc, "id", None) or generate_mistral_compatible_id(),
                                type=getattr(tc, "type", "function"),
                                function=FunctionCall(
                                    name=getattr(fn, "name", None),
                                    arguments=args if args is not None else "{}",
                                ),
                            ))
                    except Exception as _tc_ex:
                        ASCIIColors.warning(
                            f"[non_stream] Skipping malformed native tool_call: {_tc_ex}"
                        )

            _collect_from_result(result_content)

            if native_tool_calls_ns:
                # Native path: content is whatever text accompanied the calls (usually "").
                raw_assistant_text = ""
                if isinstance(result_content, dict):
                    raw_assistant_text = (
                        result_content.get("content")
                        or (result_content.get("message") or {}).get("content")
                        or ""
                    )
                elif hasattr(result_content, "content"):
                    raw_assistant_text = getattr(result_content, "content") or ""
                else:
                    raw_assistant_text = str(result_content or "")
                clean_content, reasoning_content = parse_reasoning_and_content(raw_assistant_text)
                tool_calls = native_tool_calls_ns
                finish_reason = "tool_calls"
                raw_text_for_tokens = raw_assistant_text
            else:
                # Text path: no native tool_calls came back. Parse for the
                # modern lollms_client ``<tool>JSON</tool>`` blocks and the
                # legacy injection-format output — but only when tools were
                # requested.
                raw_text = str(result_content) if result_content is not None else ""
                raw_text_for_tokens = raw_text
                # Extract modern lollms tool XML from raw_text FIRST so the
                # reasoning/content splitter doesn't scramble braces inside
                # the JSON payload.
                if request.tools:
                    _lollms_cleaned, _lollms_tcs = _parse_lollms_tool_xml(raw_text)
                    if _lollms_tcs:
                        tool_calls = _lollms_tcs
                        finish_reason = "tool_calls"
                        raw_text_for_parsing = _lollms_cleaned or ""
                    else:
                        raw_text_for_parsing = raw_text
                else:
                    raw_text_for_parsing = raw_text

                clean_content, reasoning_content = parse_reasoning_and_content(raw_text_for_parsing)

                if request.tools and not tool_calls:
                    parsed_content, parsed_tool_calls = parse_tool_calls_from_text(clean_content)
                    if parsed_tool_calls:
                        tool_calls = parsed_tool_calls
                        finish_reason = "tool_calls"
                    if parsed_content is not None:
                        clean_content = parsed_content

                # Surface unsupported tool-calling models instead of silently returning empty.
                if request.tools and not tool_calls and not (clean_content or "").strip():
                    ASCIIColors.warning(
                        f"[non_stream][tools] Empty response for user '{user.username}' — model likely "
                        f"does not support tool/function calling."
                    )
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Model returned an empty response with tools enabled. "
                            "Verify the upstream model supports tool/function calling, "
                            "or disable `tools` for this request."
                        ),
                    )

            msg_obj = ChatMessage(
                role="assistant",
                content=clean_content,
                tool_calls=tool_calls,
                reasoning_content=reasoning_content
            )
            choice = ChatCompletionResponseChoice(index=0, message=msg_obj, finish_reason=finish_reason)

            prompt_tokens = await loop.run_in_executor(executor, lambda: lc.count_tokens(str(openai_messages)))
            completion_tokens = await loop.run_in_executor(executor, lambda: lc.count_tokens(raw_text_for_tokens))
            reasoning_tokens = 0
            if reasoning_content:
                reasoning_tokens = await loop.run_in_executor(executor, lambda: lc.count_tokens(reasoning_content))

            # Record generation telemetry
            record_generation_metric(
                db=db,
                user_id=user.id,
                username=user.username,
                model_name=request.model,
                binding_name=binding_alias,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                source="openai_v1"
            )

            return ChatCompletionResponse(
                id=f"chatcmpl-{uuid.uuid4().hex}",
                model=request.model,
                choices=[choice],
                usage=UsageInfo(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    completion_tokens_details=CompletionTokensDetails(reasoning_tokens=reasoning_tokens),
                    prompt_tokens_details=PromptTokensDetails(cached_tokens=0)
                ),
            )
        except HTTPException:
            raise
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Generation error: {e}")
        
        
def resolve_tti_model(db: Session, user: DBUser, requested_model: Optional[str]) -> Tuple[str, str]:
    """Resolves an incoming TTI model name, universal profile, alias, or active system default."""
    if requested_model and requested_model.strip():
        req_clean = requested_model.strip()
        if '/' in req_clean:
            alias, model_part = req_clean.split('/', 1)
            return alias, model_part

        b_alias, p_key, _ = get_universal_model_profile(db, req_clean, modality="tti")
        if b_alias:
            return b_alias, p_key or ""

        target_b = db.query(DBTTIBinding).filter(
            (DBTTIBinding.alias == req_clean) | (DBTTIBinding.name == req_clean),
            DBTTIBinding.is_active == True
        ).first()
        if target_b:
            return target_b.alias, target_b.default_model_name or req_clean

    if user.tti_binding_model_name:
        if '/' in user.tti_binding_model_name:
            return user.tti_binding_model_name.split('/', 1)
        return user.tti_binding_model_name, ""

    default_tti = db.query(DBTTIBinding).filter(DBTTIBinding.is_active == True).order_by(DBTTIBinding.id).first()
    if default_tti:
        return default_tti.alias, default_tti.default_model_name or "default"

    raise HTTPException(status_code=501, detail="No active Text-to-Image (TTI) binding configured on the server.")

def _normalize_image_bytes(raw_output: Any) -> bytes:
    if isinstance(raw_output, bytes):
        return raw_output
    if isinstance(raw_output, (list, tuple)) and raw_output:
        return _normalize_image_bytes(raw_output[0])
    if hasattr(raw_output, 'read') and callable(raw_output.read):
        return raw_output.read()
    if isinstance(raw_output, io.BytesIO):
        return raw_output.getvalue()
    if isinstance(raw_output, str):
        if raw_output.startswith("data:image"):
            b64_part = raw_output.split(",", 1)[1] if "," in raw_output else raw_output
            return base64.b64decode(b64_part)
        file_p = Path(raw_output)
        if file_p.exists() and file_p.is_file():
            return file_p.read_bytes()
        try:
            return base64.b64decode(raw_output)
        except Exception:
            pass
    raise ValueError("TTI binding returned empty or invalid image data.")

@openai_v1_router.post("/images/generations", response_model=ImageGenerationResponse)
async def create_image_generation(
    request_data: ImageGenerationRequest,
    fastapi_request: Request,
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    """
    OpenAI-compatible Image Generation endpoint (POST /v1/images/generations).
    Generates images from text descriptions.
    """
    tti_binding_alias, tti_model_name = resolve_tti_model(db, user, request_data.model)
    loop = asyncio.get_running_loop()

    width, height = 1024, 1024
    if request_data.size and "x" in request_data.size:
        try:
            w_str, h_str = request_data.size.split("x", 1)
            width, height = int(w_str), int(h_str)
        except ValueError:
            pass

    try:
        lc = await loop.run_in_executor(
            executor,
            lambda: build_lollms_client_from_params(
                username=user.username,
                tti_binding_alias=tti_binding_alias,
                tti_model_name=tti_model_name,
                load_llm=False,
                load_tti=True,
                load_mcp=False
            )
        )

        if not hasattr(lc, 'tti') or not lc.tti:
            raise HTTPException(status_code=500, detail=f"TTI functionality is not available for binding '{tti_binding_alias}'.")

        generated_images_data = []
        user_generated_path = get_user_data_root(user.username) / "generated_images"

        for _ in range(request_data.n or 1):
            def _generate():
                try:
                    return lc.tti.generate_image(
                        prompt=request_data.prompt,
                        width=width,
                        height=height,
                        quality=request_data.quality,
                        style=request_data.style
                    )
                except TypeError:
                    try:
                        return lc.tti.generate_image(
                            prompt=request_data.prompt,
                            size=request_data.size,
                            quality=request_data.quality,
                            style=request_data.style
                        )
                    except TypeError:
                        return lc.tti.generate_image(prompt=request_data.prompt)

            raw_img = await loop.run_in_executor(executor, _generate)
            image_bytes = _normalize_image_bytes(raw_img)

            fmt_clean = (request_data.response_format or "url").lower().strip()
            if fmt_clean in ("b64_json", "json"):
                b64_json = base64.b64encode(image_bytes).decode('utf-8')
                generated_images_data.append(ImageObject(b64_json=b64_json))
            else:
                user_generated_path.mkdir(parents=True, exist_ok=True)
                filename = f"{uuid.uuid4().hex}.png"
                file_path = user_generated_path / filename
                with open(file_path, "wb") as f:
                    f.write(image_bytes)

                base_url = str(fastapi_request.base_url).rstrip('/')
                image_url = f"{base_url}/api/files/generated/{filename}"
                generated_images_data.append(ImageObject(url=image_url))

        return ImageGenerationResponse(data=generated_images_data)

    except HTTPException:
        raise
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")

@openai_v1_router.post("/images/variations", response_model=ImageGenerationResponse)
async def create_image_variation(
    fastapi_request: Request,
    image: List[UploadFile] = File(..., description="The source image (PNG/JPEG/WEBP) to generate variations of."),
    model: Optional[str] = Form(None),
    n: int = Form(1, ge=1, le=10),
    size: Optional[str] = Form("1024x1024"),
    response_format: Optional[str] = Form("b64_json"),
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    """
    OpenAI-compatible Image Variations endpoint (POST /v1/images/variations).
    Creates variations of a supplied image.
    """
    tti_binding_alias, tti_model_name = resolve_tti_model(db, user, model)
    loop = asyncio.get_running_loop()

    width, height = 1024, 1024
    if size and "x" in size:
        try:
            w_str, h_str = size.split("x", 1)
            width, height = int(w_str), int(h_str)
        except ValueError:
            pass

    async def _read(upload: UploadFile) -> bytes:
        try:
            return await upload.read()
        finally:
            await upload.close()

    source_bytes_list = [await _read(img) for img in image]
    images_b64 = [base64.b64encode(b).decode("utf-8") for b in source_bytes_list]

    try:
        lc = await loop.run_in_executor(
            executor,
            lambda: build_lollms_client_from_params(
                username=user.username,
                tti_binding_alias=tti_binding_alias,
                tti_model_name=tti_model_name,
                load_llm=False,
                load_tti=True,
                load_mcp=False,
            )
        )

        if not hasattr(lc, "tti") or not lc.tti:
            raise HTTPException(status_code=500, detail=f"TTI functionality is not available for binding '{tti_binding_alias}'.")

        generated = []
        user_generated_path = get_user_data_root(user.username) / "generated_images"

        for _ in range(n):
            def _make_variation():
                if hasattr(lc.tti, 'edit_image'):
                    try:
                        return lc.tti.edit_image(
                            images=images_b64,
                            prompt="Create a high-quality creative variation of this image",
                            width=width,
                            height=height
                        )
                    except Exception:
                        pass
                if hasattr(lc.tti, 'generate_image'):
                    try:
                        return lc.tti.generate_image(
                            image=images_b64[0],
                            prompt="Create a variation of this image",
                            width=width,
                            height=height
                        )
                    except TypeError:
                        return lc.tti.generate_image(prompt="Create a variation of this image")
                raise ValueError("Configured TTI binding does not support image variation or img2img.")

            raw_res = await loop.run_in_executor(executor, _make_variation)
            result_bytes = _normalize_image_bytes(raw_res)

            fmt_clean = (response_format or "b64_json").lower().strip()
            if fmt_clean == "url":
                user_generated_path.mkdir(parents=True, exist_ok=True)
                filename = f"{uuid.uuid4().hex}.png"
                (user_generated_path / filename).write_bytes(result_bytes)
                base_url = str(fastapi_request.base_url).rstrip("/")
                generated.append(ImageObject(url=f"{base_url}/api/files/generated/{filename}"))
            else:
                b64 = base64.b64encode(result_bytes).decode("utf-8")
                generated.append(ImageObject(b64_json=b64))

        return ImageGenerationResponse(data=generated)

    except HTTPException:
        raise
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Image variation failed: {e}")


@openai_v1_router.post("/images/edits", response_model=ImageGenerationResponse)
async def create_image_edit(
    fastapi_request: Request,
    # ── Required ──────────────────────────────────────────────────────────────
    prompt: str = Form(...),
    image: List[UploadFile] = File(..., description="One or more source images (PNG/JPEG/WEBP, max 4 MB each)."),
    # ── Optional ──────────────────────────────────────────────────────────────
    mask: Optional[UploadFile] = File(None, description="Mask PNG — transparent areas mark where to edit."),
    model: Optional[str] = Form(None),
    n: int = Form(1, ge=1, le=10),
    size: Optional[str] = Form("1024x1024"),
    quality: Optional[str] = Form("standard"),
    response_format: Optional[str] = Form("b64_json"),
    background: Optional[str] = Form(None),
    output_format: Optional[str] = Form("png"),
    output_compression: Optional[int] = Form(None, ge=0, le=100),
    input_fidelity: Optional[str] = Form(None),
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db),
):
    """
    POST /v1/images/edits — OpenAI-compatible image edit endpoint.
    Delegates to lc.tti.edit_image(images, prompt, mask, **kwargs).
    """
    # ── Resolve model / binding ────────────────────────────────────────────────
    if model is None:
        if user.tti_binding_model_name:
            model = user.tti_binding_model_name
        else:
            default_binding = (
                db.query(DBTTIBinding)
                .filter(DBTTIBinding.is_active == True)
                .order_by(DBTTIBinding.id)
                .first()
            )
            if not default_binding:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "No TTI model specified and no default TTI binding "
                        "configured for this user or system."
                    ),
                )
            model = f"{default_binding.alias}/{default_binding.default_model_name or ''}"

    if "/" not in model:
        raise HTTPException(
            status_code=400,
            detail="Invalid model name. Use 'tti_binding_alias/model_name' format.",
        )

    tti_binding_alias, tti_model_name = model.split("/", 1)

    ASCIIColors.panel(
        f"[bold]Open AI V1 — Image Edit[/bold]\n"
        f"[bold]User:[/bold] {user.username}\n"
        f"[bold]Model alias:[/bold] {model}\n"
        f"[bold]Images:[/bold] {len(image)}\n"
        f"[bold]Mask:[/bold] {'yes' if mask else 'no'}\n"
        f"[bold]n:[/bold] {n}  [bold]Size:[/bold] {size}  "
        f"[bold]Quality:[/bold] {quality}",
        title="Image Edit Request",
        border_style="magenta",
    )

    # ── Read uploaded file bytes (must happen in async context) ───────────────
    async def _read(upload: UploadFile) -> bytes:
        try:
            return await upload.read()
        finally:
            await upload.close()

    source_bytes_list: List[bytes] = [await _read(img) for img in image]
    mask_bytes: Optional[bytes] = await _read(mask) if mask else None

    # ── Convert to base64 strings — the format edit_image() expects ───────────
    images_b64: List[str] = [
        base64.b64encode(b).decode("utf-8") for b in source_bytes_list
    ]
    mask_b64: Optional[str] = (
        base64.b64encode(mask_bytes).decode("utf-8") if mask_bytes else None
    )

    # ── Parse size into width/height ──────────────────────────────────────────
    width, height = 1024, 1024
    if size and "x" in size:
        try:
            w_str, h_str = size.split("x", 1)
            width, height = int(w_str), int(h_str)
        except ValueError:
            pass  # keep defaults

    # ── Build TTI client ───────────────────────────────────────────────────────
    loop = asyncio.get_running_loop()
    try:
        lc = await loop.run_in_executor(
            executor,
            lambda: build_lollms_client_from_params(
                username=user.username,
                tti_binding_alias=tti_binding_alias,
                tti_model_name=tti_model_name,
                load_llm=False,
                load_tti=True,
                load_mcp=False,
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build TTI client: {e}")

    if not hasattr(lc, "tti") or not lc.tti:
        raise HTTPException(
            status_code=500,
            detail=f"TTI functionality is not available for binding '{tti_binding_alias}'.",
        )

    # ── Build extra kwargs forwarded to edit_image() ──────────────────────────
    edit_kwargs: Dict[str, Any] = {"quality": quality}
    if background is not None:
        edit_kwargs["background"] = background
    if output_format is not None:
        edit_kwargs["output_format"] = output_format
    if output_compression is not None:
        edit_kwargs["output_compression"] = output_compression
    if input_fidelity is not None:
        edit_kwargs["input_fidelity"] = input_fidelity

    # ── Generate n edited images ───────────────────────────────────────────────
    generated: List[ImageObject] = []
    user_generated_path = get_user_data_root(user.username) / "generated_images"

    for i in range(n):
        try:
            # edit_image(images, prompt, negative_prompt, mask, width, height, **kwargs) → bytes
            result_bytes: bytes = await loop.run_in_executor(
                executor,
                lambda: lc.tti.edit_image(
                    images=images_b64,
                    prompt=prompt,
                    negative_prompt="",
                    mask=mask_b64,
                    width=width,
                    height=height,
                    **edit_kwargs,
                ),
            )

            if not result_bytes:
                raise ValueError("edit_image() returned empty data.")

            if response_format == "url":
                result_bytes_final = (
                    result_bytes
                    if isinstance(result_bytes, bytes)
                    else base64.b64decode(result_bytes)
                )
                user_generated_path.mkdir(parents=True, exist_ok=True)
                ext = output_format or "png"
                filename = f"{uuid.uuid4().hex}.{ext}"
                (user_generated_path / filename).write_bytes(result_bytes_final)
                base_url = str(fastapi_request.base_url).rstrip("/")
                generated.append(
                    ImageObject(url=f"{base_url}/api/files/generated/{filename}")
                )
            else:
                # edit_image() returns raw bytes per the abstract base class
                b64 = base64.b64encode(result_bytes).decode("utf-8")
                generated.append(ImageObject(b64_json=b64))

        except Exception as e:
            trace_exception(e)
            raise HTTPException(
                status_code=500,
                detail=f"Image edit failed (image {i + 1}/{n}): {e}",
            )

    return ImageGenerationResponse(data=generated)

@openai_v1_router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(
    request: EmbeddingRequest,
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    binding_alias, model_name = resolve_model_name(db, request.model)
    loop = asyncio.get_running_loop()

    try:
        lc = await loop.run_in_executor(
            executor,
            lambda: build_lollms_client_from_params(
                username=user.username,
                binding_alias=binding_alias,
                model_name=model_name,
                load_llm=True,
                load_mcp=False
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build LLM client: {str(e)}")

    if request.encoding_format != "float":
        ASCIIColors.warning(f"The request encoding format {request.encoding_format} is not supported. Only 'float' encoding_format is supported.")
        request.encoding_format = 'float'
    input_texts = [request.input] if isinstance(request.input, str) else request.input
    if not input_texts or not all(isinstance(t, str) for t in input_texts):
        raise HTTPException(status_code=400, detail="Invalid 'input' format. Must be a non-empty string or a list of non-empty strings.")

    embeddings_data = []
    total_tokens = 0
    
    try:
        for i, text in enumerate(input_texts):
            # Use executor for embedding (blocking)
            embedding_vector = await loop.run_in_executor(
                executor, 
                lambda: lc.embed(text)
            )

            if not isinstance(embedding_vector, list) or not all(isinstance(f, (float, int)) for f in embedding_vector):
                print(f"Warning: Binding '{binding_alias}' embed function returned an unexpected type for input '{text[:50]}...': {type(embedding_vector)}")
                raise HTTPException(status_code=500, detail=f"The embedding model for binding '{binding_alias}' returned an invalid data format.")

            embeddings_data.append(EmbeddingObject(embedding=embedding_vector, index=i))
            count = await loop.run_in_executor(executor, lambda: lc.count_tokens(text))
            total_tokens += count
            
    except Exception as e:
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
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    binding_alias, model_name = resolve_model_name(db, request.model)
    loop = asyncio.get_running_loop()
    
    try:
        lc = await loop.run_in_executor(
            executor,
            lambda: build_lollms_client_from_params(
                username=user.username,
                binding_alias=binding_alias,
                model_name=model_name,
                load_llm=True,
                load_mcp=False
            )
        )
        tokens = await loop.run_in_executor(executor, lambda: lc.tokenize(request.text))
        return TokenizeResponse(tokens=tokens, count=len(tokens))
    except AttributeError:
        # Fallback if tokenize not available
        count = await loop.run_in_executor(executor, lambda: lc.count_tokens(request.text))
        return TokenizeResponse(count=count, tokens=count)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to tokenize text: {e}")

@openai_v1_router.post("/detokenize", response_model=DetokenizeResponse)
async def detokenize_tokens(
    request: DetokenizeRequest,
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    binding_alias, model_name = resolve_model_name(db, request.model)
    loop = asyncio.get_running_loop()
    
    try:
        lc = await loop.run_in_executor(
            executor,
            lambda: build_lollms_client_from_params(
                username=user.username,
                binding_alias=binding_alias,
                model_name=model_name,
                load_llm=True,
                load_mcp=False
            )
        )
        text = await loop.run_in_executor(executor, lambda: lc.detokenize(request.tokens))
        return DetokenizeResponse(text=text)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to detokenize tokens: {e}")

@openai_v1_router.post("/count_tokens", response_model=CountTokensResponse)
async def count_tokens(
    request: CountTokensRequest,
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    binding_alias, model_name = resolve_model_name(db, request.model)
    loop = asyncio.get_running_loop()

    try:
        lc = await loop.run_in_executor(
            executor,
            lambda: build_lollms_client_from_params(
                username=user.username,
                binding_alias=binding_alias,
                model_name=model_name,
                load_llm=True,
                load_mcp=False
            )
        )
        count = await loop.run_in_executor(executor, lambda: lc.count_tokens(request.text))
        return CountTokensResponse(count=count)
    except AttributeError:
        count = await loop.run_in_executor(executor, lambda: lc.count_tokens(request.text))
        return CountTokensResponse(count=count)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to count tokens: {e}")

@openai_v1_router.post("/context_size", response_model=ContextSizeResponse)
async def get_model_context_size(
    request: ContextSizeRequest,
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    loop = asyncio.get_running_loop()

    # 1. Check global forced context size
    force_mode = settings.get("force_model_mode", "disabled")
    if force_mode == "force_always" and settings.get("force_context_size"):
        return ContextSizeResponse(context_size=int(settings.get("force_context_size")))

    # 2. Check Universal Model Profile
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

    # 4. Engine Probe Fallback
    try:
        resolved_binding = binding_alias
        resolved_model = profile_key or request.model
        if not resolved_binding:
            resolved_binding, resolved_model = await loop.run_in_executor(
                executor,
                lambda: resolve_model_name(db, request.model)
            )

        lc = await loop.run_in_executor(
            executor,
            lambda: build_lollms_client_from_params(
                username=user.username,
                binding_alias=resolved_binding,
                model_name=resolved_model,
                load_llm=True,
                load_mcp=False
            )
        )
        ctx_size = await loop.run_in_executor(executor, lambda: lc.get_ctx_size(resolved_model) or lc.get_ctx_size())
        return ContextSizeResponse(context_size=ctx_size or getattr(lc.llm, 'default_ctx_size', 32000))
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve context size: {e}")

@openai_v1_router.post("/extract_text", response_model=FileExtractionResponse)
async def extract_text_from_file(
    request: FileExtractionRequest,
    user: DBUser = Depends(get_user_from_api_key)
):
    try:
        file_bytes = base64.b64decode(request.file)
        loop = asyncio.get_running_loop()
        extracted_text, _ = await loop.run_in_executor(
            executor, 
            lambda: extract_text_from_file_bytes(file_bytes, request.filename)
        )
        return FileExtractionResponse(text=extracted_text)
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid base64 encoding.")
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"File extraction failed: {str(e)}")

# --- Official OpenAI Audio Endpoints ---

@openai_v1_router.post("/audio/speech")
async def create_speech_openai(
    request: OpenAITTSRequest,
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    """
    OpenAI-compatible Text-to-Speech endpoint (POST /v1/audio/speech).
    Compatible with `openai.audio.speech.create(...)`.
    """
    loop = asyncio.get_running_loop()
    tts_binding_alias = None
    tts_model_name = None

    if request.model and "/" in request.model:
        tts_binding_alias, tts_model_name = request.model.split("/", 1)
    else:
        active_binding = db.query(DBTTSBinding).filter(DBTTSBinding.is_active == True).order_by(DBTTSBinding.id).first()
        if not active_binding:
            raise HTTPException(status_code=501, detail="No active TTS binding configured.")
        tts_binding_alias = active_binding.alias
        tts_model_name = active_binding.default_model_name or request.model

    try:
        lc = await loop.run_in_executor(
            executor,
            lambda: build_lollms_client_from_params(
                username=user.username,
                load_llm=False,
                load_tts=True,
                tts_binding_alias=tts_binding_alias,
                tts_model_name=tts_model_name,
                load_mcp=False
            )
        )
        if not hasattr(lc, "tts") or not lc.tts:
            raise HTTPException(status_code=500, detail="TTS service is unavailable for this binding.")

        # Clean markdown / emojis from text
        clean_input = re.sub(r'[*#]', '', request.input)
        clean_input = re.sub(r'[\U00010000-\U0010ffff]', '', clean_input)

        audio_bytes = await loop.run_in_executor(
            executor,
            lambda: lc.tts.generate_audio(
                text=clean_input,
                voice=request.voice,
                model=tts_model_name,
                speed=request.speed
            )
        )

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
    except HTTPException:
        raise
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Speech synthesis failed: {e}")

@openai_v1_router.post("/audio/transcriptions", response_model=AudioTranscriptionResponse)
async def create_transcription_openai(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    response_format: Optional[str] = Form("json"),
    temperature: Optional[float] = Form(0.0),
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    """
    OpenAI-compatible Speech-to-Text endpoint (POST /v1/audio/transcriptions).
    Compatible with `openai.audio.transcriptions.create(...)`.
    """
    stt_binding_alias = None
    stt_model_name = None

    if "/" in model:
        stt_binding_alias, stt_model_name = model.split("/", 1)
    else:
        active_stt = db.query(DBSTTBinding).filter(DBSTTBinding.is_active == True).order_by(DBSTTBinding.id).first()
        if not active_stt:
            raise HTTPException(status_code=501, detail="No active STT binding configured.")
        stt_binding_alias = active_stt.alias
        stt_model_name = active_stt.default_model_name or model

    loop = asyncio.get_running_loop()
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or "audio.wav").suffix) as tf:
        content = await file.read()
        tf.write(content)
        temp_path = tf.name

    try:
        lc = await loop.run_in_executor(
            executor,
            lambda: build_lollms_client_from_params(
                username=user.username,
                load_llm=False,
                load_stt=True,
                stt_binding_alias=stt_binding_alias,
                stt_model_name=stt_model_name,
                load_mcp=False
            )
        )
        if not hasattr(lc, "stt") or not lc.stt:
            raise HTTPException(status_code=500, detail="STT service is unavailable.")

        def _transcribe():
            if hasattr(lc.stt, "transcribe_audio"):
                return lc.stt.transcribe_audio(temp_path)
            elif hasattr(lc.stt, "transcribe_file"):
                return lc.stt.transcribe_file(temp_path)
            elif hasattr(lc.stt, "transcribe"):
                return lc.stt.transcribe(temp_path)
            raise ValueError("STT binding lacks audio transcription method.")

        transcript = await loop.run_in_executor(executor, _transcribe)
        return AudioTranscriptionResponse(text=str(transcript).strip())
    except HTTPException:
        raise
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Audio transcription failed: {e}")
    finally:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass

@openai_v1_router.post("/audio/translations", response_model=AudioTranscriptionResponse)
async def create_translation_openai(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    prompt: Optional[str] = Form(None),
    response_format: Optional[str] = Form("json"),
    temperature: Optional[float] = Form(0.0),
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    """
    OpenAI-compatible Audio translation endpoint (POST /v1/audio/translations).
    Transcribes and translates audio to English.
    """
    return await create_transcription_openai(
        file=file,
        model=model,
        language="en",
        prompt=prompt,
        response_format=response_format,
        temperature=temperature,
        user=user,
        db=db
    )

# --- OpenAI Responses API (Modern Agentic Primitive) ---

@openai_v1_router.post("/responses", response_model=ResponseObject)
async def create_response_openai(
    request: ResponseCreateRequest,
    fastapi_request: Request,
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    """
    OpenAI Responses API (POST /v1/responses).
    The modern agentic primitive unifying instructions, tools, reasoning, and multi-part outputs.
    Compatible with `openai.responses.create(...)`.
    """
    loop = asyncio.get_running_loop()
    binding_alias, model_name = await loop.run_in_executor(
        executor,
        lambda: resolve_model_name(db, request.model)
    )

    # Convert Responses API inputs to message sequence
    messages = []
    if request.instructions:
        messages.append({"role": "system", "content": request.instructions})

    if isinstance(request.input, str):
        messages.append({"role": "user", "content": request.input})
    elif isinstance(request.input, list):
        for item in request.input:
            if isinstance(item, dict):
                role = item.get("role", "user")
                content = item.get("content") or item.get("text") or str(item)
                messages.append({"role": role, "content": content})
            else:
                messages.append({"role": "user", "content": str(item)})

    if request.tools:
        messages = handle_tools_injection(messages, request.tools)

    resp_effort, resp_thinking, resp_extra_thinking = extract_reasoning_parameters(request)

    llm_runtime_params = {
        "temperature": request.temperature,
        "max_output_tokens": request.max_output_tokens
    }

    if resp_effort is None or str(resp_effort).lower() in ("none", "null", "off", "disabled", "false"):
        llm_runtime_params["think"] = None
        llm_runtime_params["thinking_effort"] = None
        llm_runtime_params["reasoning_effort"] = None
        llm_runtime_params["thinking"] = False
        llm_runtime_params["reasoning_activation"] = False
    else:
        llm_runtime_params["think"] = True
        llm_runtime_params["thinking"] = True
        llm_runtime_params["thinking_effort"] = resp_effort
        llm_runtime_params["reasoning_effort"] = resp_effort
        llm_runtime_params["reasoning_activation"] = True

    lc = await loop.run_in_executor(
        executor,
        lambda: build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name,
            llm_params=llm_runtime_params,
            load_llm=True,
            load_mcp=bool(request.tools)
        )
    )

    generation_kwargs = {}
    if resp_effort is None or str(resp_effort).lower() in ("none", "null", "off", "disabled", "false") or resp_thinking is False:
        generation_kwargs["think"] = None
        generation_kwargs["thinking_effort"] = None
        generation_kwargs["reasoning_effort"] = None
        generation_kwargs["thinking"] = False
        generation_kwargs["reasoning_activation"] = False
        generation_kwargs["chat_template_kwargs"] = {"thinking": False}
        generation_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    else:
        generation_kwargs["think"] = True
        generation_kwargs["thinking"] = True
        generation_kwargs["thinking_effort"] = resp_effort
        generation_kwargs["reasoning_effort"] = resp_effort
        generation_kwargs["reasoning_activation"] = True
    generation_kwargs.update(resp_extra_thinking)

    _prepare_generation(lc)
    try:
        raw_res = await loop.run_in_executor(
            executor,
            lambda: lc.generate_from_messages(
                messages,
                temperature=request.temperature,
                n_predict=request.max_output_tokens or 2048,
                **generation_kwargs
            )
        )
    finally:
        _cancel_generation(lc)

    clean_content, reasoning_content = parse_reasoning_and_content(str(raw_res))

    prompt_tokens = await loop.run_in_executor(executor, lambda: lc.count_tokens(str(messages)))
    completion_tokens = await loop.run_in_executor(executor, lambda: lc.count_tokens(str(raw_res)))
    reasoning_tokens = 0
    if reasoning_content:
        reasoning_tokens = await loop.run_in_executor(executor, lambda: lc.count_tokens(reasoning_content))

    return ResponseObject(
        model=request.model,
        output=[
            ResponseOutputMessage(
                content=[ResponseOutputContent(text=clean_content)]
            )
        ],
        usage=UsageInfo(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            completion_tokens_details=CompletionTokensDetails(reasoning_tokens=reasoning_tokens),
            prompt_tokens_details=PromptTokensDetails(cached_tokens=0)
        )
    )
