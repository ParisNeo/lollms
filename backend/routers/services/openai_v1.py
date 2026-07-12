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
from pydantic import BaseModel, Field

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.api_key import OpenAIAPIKey as DBAPIKey
from backend.db.models.config import LLMBinding as DBLLMBinding, TTIBinding as DBTTIBinding
from backend.db.models.config import GlobalConfig
from backend.db.models.personality import Personality as DBPersonality
from backend.security import verify_api_key
from backend.session import user_sessions, build_lollms_client_from_params, get_user_data_root, find_model_by_alias, resolve_model_name, invalidate_model_cache
from backend.settings import settings
from lollms_client import LollmsPersonality, MSG_TYPE
from ascii_colors import ASCIIColors, trace_exception
from backend.routers.files import extract_text_from_file_bytes 
from backend.utils import track_service_usage, check_rate_limit, get_system_cache, set_system_cache

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

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    personality: Optional[str] = None 
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    reasoning_effort: Optional[str] = None

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
    tool_calls: Optional[List[ToolCall]] = None

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





def _prepare_generation(lc) -> None:
    """Call before every generation to arm a clean cancellation state."""
    if hasattr(lc, 'llm') and lc.llm is not None and hasattr(lc.llm, 'reset_cancel'):
        lc.llm.reset_cancel()


def _cancel_generation(lc) -> None:
    """
    Best-effort cancellation:
      1. Call binding.cancel() — closes HTTP sessions, sets the event.
      2. If the binding didn't override cancel() (i.e. it's purely cooperative
         via is_cancelled()), the event alone may not be enough for a hung
         thread.  The caller should still hard-kill the process as a last resort
         if lc lives in a child process (see below).
    """
    if hasattr(lc, 'llm') and lc.llm is not None and hasattr(lc.llm, 'cancel'):
        lc.llm.cancel()

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

    if not require_key:
        admin_user = db.query(DBUser).filter(DBUser.is_admin == True).order_by(DBUser.id).first()
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
            "temperature": user.llm_temperature,
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
    
    # Rate Limit Check
    if not check_rate_limit(api_key, "openai"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

    track_service_usage("openai", user.id)
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


def parse_tool_calls_from_text(content: Any) -> Tuple[Optional[str], Optional[List[ToolCall]]]:
    """
    Parses the LLM output to find JSON tool calls.
    PRIORITIZES content inside ```json code blocks, but falls back to scanning.
    """
    ASCIIColors.yellow("--- TOOL PARSING START ---")
    
    if not content:
        return None, None
    
    # Ensure content is a string before processing to avoid TypeErrors
    if not isinstance(content, str):
        content = str(content)

    ASCIIColors.cyan(f"Raw LLM Output (First 500 chars):\n{content[:500]}...")

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

    # 1. Try DB Cache first (unless forced)
    if not force_refresh:
        # Wrap DB query or cache lookup to keep event loop free
        loop = asyncio.get_running_loop()
        cached = await loop.run_in_executor(executor, lambda: get_system_cache(db, "cache_available_models"))
        if cached:
            ASCIIColors.success("Returning cached model list.")
            return {"object": "list", "data": cached}

    loop = asyncio.get_running_loop()

    def _fetch_models():
        all_models = []
        active_bindings = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()
        model_display_mode = settings.get("model_display_mode", "mixed")

        for binding in active_bindings:
            try:
                ASCIIColors.rich_print(f">[bold green]{binding.alias}[\bold green]")
                # Blocking IO: building client, listing models
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
                        internal_id = f"{binding.alias}/{model_id}"
                        id_to_send = internal_id
                        name_to_send = internal_id

                        if model_display_mode == 'aliased':
                            if not alias_data: continue
                            if alias_data.get('title'):
                                id_to_send = alias_data.get('title')
                                name_to_send = alias_data.get('title')
                        elif model_display_mode == 'mixed':
                            if alias_data and alias_data.get('title'):
                                id_to_send = alias_data.get('title')
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
        return all_models

    all_models = await loop.run_in_executor(executor, _fetch_models)

    if not all_models and not force_refresh:
         raise HTTPException(status_code=404, detail="No models found from any active bindings.")
    
    unique_models = {m["id"]: m for m in all_models}
    final_list = sorted(list(unique_models.values()), key=lambda x: x['id'])
    
    # Update Cache
    await loop.run_in_executor(executor, lambda: set_system_cache(db, "cache_available_models", final_list))
    ASCIIColors.info(f"------------ DONE (Cache Updated) --------------")

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
    try:
        # Offload potentially blocking database model resolution
        binding_alias, model_name = await loop.run_in_executor(
            executor,
            lambda: resolve_model_name(db, request.model)
        )
    except HTTPException as e:
        if e.status_code == 400:
            await loop.run_in_executor(executor, lambda: invalidate_model_cache(db))
        raise e

    # Client building can be slow, might involve model loading.
    try:
        lc = await loop.run_in_executor(
            executor,
            lambda: build_lollms_client_from_params(
                username=user.username,
                binding_alias=binding_alias,
                model_name=model_name,
                llm_params={
                    "temperature": request.temperature,
                    "max_output_tokens": request.max_tokens
                },
                load_llm=True
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

    if request.tools:
        openai_messages = handle_tools_injection(openai_messages, request.tools, request.tool_choice)

    generation_kwargs = {}
    if request.reasoning_effort:
        generation_kwargs["reasoning_effort"] = request.reasoning_effort

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
[bold]Thinking:[/bold] {'active' if request.reasoning_effort else 'inactive'}
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
                    await loop.run_in_executor(None, lambda: _cancel_generation(lc))
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)

                try:
                    _prepare_generation(lc)
                    watcher_task = asyncio.ensure_future(watch_disconnect())

                    # ── TOOLS PATH ────────────────────────────────────────────────────────
                    if request.tools:
                        # Offload to thread pool to avoid blocking the event loop
                        result_content = await asyncio.wait_for(
                            loop.run_in_executor(
                                executor,
                                lambda: lc.generate_from_messages(
                                    openai_messages,
                                    temperature=request.temperature,
                                    n_predict=request.max_tokens,
                                    **generation_kwargs
                                )
                            ),
                            timeout=TTFT_TIMEOUT,   # tools path: single blocking call
                        )
                        if lc.llm and lc.llm.is_cancelled():
                            yield "data: [DONE]\n\n"
                            return
                        if isinstance(result_content, dict) and (
                            "error" in result_content or result_content.get("status") is False
                        ):
                            yield make_error_chunk(result_content.get("error", "LLM error"))
                            yield "data: [DONE]\n\n"
                            return
                        content, tool_calls = parse_tool_calls_from_text(result_content)
                        yield make_chunk(DeltaMessage(role="assistant"))
                        if content:
                            yield make_chunk(DeltaMessage(content=content))
                        if tool_calls:
                            for i, tc in enumerate(tool_calls):
                                tc.index = i
                                yield make_chunk(DeltaMessage(tool_calls=[tc]))
                        yield make_chunk(
                            DeltaMessage(),
                            finish_reason="tool_calls" if tool_calls else "stop"
                        )
                        yield "data: [DONE]\n\n"
                        return

                     # ── STREAMING PATH ────────────────────────────────────────────────────
                    def llm_callback(chunk_text: str, msg_type: MSG_TYPE, **kwargs) -> bool:
                        if lc.llm and lc.llm.is_cancelled():
                            return False
                        if msg_type == MSG_TYPE.MSG_TYPE_CHUNK and chunk_text:
                            main_loop.call_soon_threadsafe(
                                stream_queue.put_nowait,
                                make_chunk(DeltaMessage(content=chunk_text))
                            )
                        return True

                    # Use a dedicated thread for generation to prevent event loop starvation
                    def blocking_gen() -> None:
                        try:
                            lc.generate_from_messages(
                                openai_messages,
                                streaming_callback=llm_callback,
                                temperature=request.temperature,
                                n_predict=request.max_tokens,
                                stream=True,
                                **generation_kwargs
                            )
                        except Exception as ex:
                            ASCIIColors.error(f"[blocking_gen] {ex}")
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
                    ASCIIColors.error(f"[stream_generator] Crash: {e}")
                    trace_exception(e)
                    yield make_error_chunk(str(e))
                    yield "data: [DONE]\n\n"
                finally:
                    _cancel_generation(lc)
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

        gen_future = loop.run_in_executor(
            executor,
            lambda: lc.generate_from_messages(
                openai_messages,
                temperature=request.temperature,
                n_predict=request.max_tokens,
                **generation_kwargs
            )
        )
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

        finally:
            _cancel_generation(lc)   # always reset for next request
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

            content = result_content
            finish_reason = "stop"
            tool_calls = None

            if request.tools:
                content, tool_calls = parse_tool_calls_from_text(result_content)
                if tool_calls:
                    finish_reason = "tool_calls"

            # Safety: Ensure content is a string or list before passing to Pydantic
            if not isinstance(content, (str, list)):
                content = str(content) if content is not None else ""

            msg_obj = ChatMessage(role="assistant", content=content, tool_calls=tool_calls)
            choice = ChatCompletionResponseChoice(index=0, message=msg_obj, finish_reason=finish_reason)

            prompt_tokens = await loop.run_in_executor(executor, lambda: lc.count_tokens(str(openai_messages)))
            completion_tokens = await loop.run_in_executor(executor, lambda: lc.count_tokens(str(result_content)))

            return ChatCompletionResponse(
                id=f"chatcmpl-{uuid.uuid4().hex}",
                model=request.model,
                choices=[choice],
                usage=UsageInfo(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                ),
            )
        except HTTPException:
            raise
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Generation error: {e}")
        
        
@openai_v1_router.post("/images/generations", response_model=ImageGenerationResponse)
async def create_image_generation(
    request_data: ImageGenerationRequest,
    fastapi_request: Request,
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    if request_data.model is None:
        if user.tti_binding_model_name:
            request_data.model = user.tti_binding_model_name
        else:
            default_binding = db.query(DBTTIBinding).filter(DBTTIBinding.is_active == True).order_by(DBTTIBinding.id).first()
            if not default_binding:
                raise HTTPException(status_code=400, detail="No TTI model specified in request and no default TTI binding configured for user or system.")
            request_data.model = f"{default_binding.alias}/{default_binding.default_model_name or ''}"

    if '/' not in request_data.model:
        raise HTTPException(status_code=400, detail="Invalid model name. Must be in 'tti_binding_alias/model_name' format.")

    tti_binding_alias, tti_model_name = request_data.model.split('/', 1)
    loop = asyncio.get_running_loop()

    try:
        lc = await loop.run_in_executor(
            executor,
            lambda: build_lollms_client_from_params(
                username=user.username,
                tti_binding_alias=tti_binding_alias,
                tti_model_name=tti_model_name,
                load_llm=False,
                load_tti=True
            )
        )
        
        if not hasattr(lc, 'tti') or not lc.tti:
            raise HTTPException(status_code=500, detail=f"TTI functionality is not available for binding '{tti_binding_alias}'.")
        
        generated_images_data = []

        for i in range(request_data.n):
            # Use executor for image generation (potentially blocking)
            image_bytes = await loop.run_in_executor(
                executor, 
                lambda: lc.tti.generate_image(
                    prompt=request_data.prompt,
                    size=request_data.size, 
                    quality=request_data.quality, 
                    style=request_data.style
                )
            )

            if not image_bytes:
                raise Exception("TTI binding returned empty image data.")

            if request_data.response_format == "b64_json":
                b64_json = base64.b64encode(image_bytes).decode('utf-8')
                generated_images_data.append(ImageObject(b64_json=b64_json))
            else: # "url"
                user_generated_path = get_user_data_root(user.username) / "generated_images"
                user_generated_path.mkdir(parents=True, exist_ok=True)
                
                filename = f"{uuid.uuid4().hex}.png"
                file_path = user_generated_path / filename
                with open(file_path, "wb") as f:
                    f.write(image_bytes)
                
                base_url = str(fastapi_request.base_url).rstrip('/')
                image_url = f"{base_url}/api/files/generated/{filename}"
                generated_images_data.append(ImageObject(url=image_url))

        return ImageGenerationResponse(data=generated_images_data)

    except HTTPException as e:
        raise e
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")


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
                load_llm=True
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
                load_llm=True
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
                load_llm=True
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
                load_llm=True
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
    binding_alias, model_name = resolve_model_name(db, request.model)
    loop = asyncio.get_running_loop()
    
    # 1. Check alias configuration for context size override (forced by admin)
    binding = db.query(DBLLMBinding).filter(DBLLMBinding.alias == binding_alias).first()
    if binding:
        model_aliases = binding.model_aliases or {}
        if isinstance(model_aliases, str):
            try: model_aliases = json.loads(model_aliases)
            except: model_aliases = {}
        
        alias_info = model_aliases.get(model_name)
        # If alias exists and has a context size set, use it preferentially
        if alias_info:
             alias_config = alias_info.get('alias', {}) if 'alias' in alias_info else alias_info
             ctx_size = alias_config.get('ctx_size')
             if ctx_size:
                  return ContextSizeResponse(context_size=int(ctx_size))

    try:
        lc = await loop.run_in_executor(
            executor,
            lambda: build_lollms_client_from_params(
                username=user.username,
                binding_alias=binding_alias,
                model_name=model_name,
                load_llm=True
            )
        )
        ctx_size = await loop.run_in_executor(executor, lambda: lc.get_ctx_size(model_name))
        return ContextSizeResponse(context_size=ctx_size or lc.llm.default_ctx_size)
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
        # File extraction can be CPU intensive for large docs
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
