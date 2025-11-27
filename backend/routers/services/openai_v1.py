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

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from pydantic import BaseModel, Field

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.api_key import OpenAIAPIKey as DBAPIKey
from backend.db.models.config import LLMBinding as DBLLMBinding, TTIBinding as DBTTIBinding
from backend.db.models.personality import Personality as DBPersonality
from backend.security import verify_api_key
from backend.session import user_sessions, build_lollms_client_from_params, get_user_data_root
from backend.settings import settings
from lollms_client import LollmsPersonality, MSG_TYPE
from ascii_colors import ASCIIColors, trace_exception
from backend.routers.files import extract_text_from_file_bytes 

# --- Router Definition ---
openai_v1_router = APIRouter(prefix="/v1")
bearer_scheme = HTTPBearer(auto_error=False) 

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
    temperature: Optional[float] = 0.7
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

# --- NEW HELPER FUNCTIONS for model resolution ---
def find_model_by_alias(db: Session, alias_title: str) -> Optional[Tuple[str, str]]:
    all_bindings = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()
    for binding in all_bindings:
        model_aliases = binding.model_aliases or {}
        if isinstance(model_aliases, str):
            try: model_aliases = json.loads(model_aliases)
            except Exception: continue
        
        for original_name, alias_data in model_aliases.items():
            if alias_data and alias_data.get('title') == alias_title:
                return binding.alias, original_name
    return None, None

def resolve_model_name(db: Session, requested_model: str) -> Tuple[str, str]:
    if '/' in requested_model:
        parts = requested_model.split('/', 1)
        binding = db.query(DBLLMBinding).filter(DBLLMBinding.alias == parts[0], DBLLMBinding.is_active == True).first()
        if binding:
            return parts[0], parts[1]
    
    binding_alias, model_name = find_model_by_alias(db, requested_model)
    if binding_alias:
        return binding_alias, model_name

    raise HTTPException(status_code=400, detail=f"Model '{requested_model}' not found. Please use 'binding/model_name' format or a valid alias.")

def generate_mistral_compatible_id() -> str:
    """Generates a 9-character alphanumeric ID required by Mistral/LiteLLM."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=9))

# --- END HELPER FUNCTIONS ---


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
    
    # Strategy 2: Fallback to scanning raw text for JSON objects
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
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    ASCIIColors.info(f"---------------> {user.username} is listing the models")
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

    if not all_models:
        raise HTTPException(status_code=404, detail="No models found from any active bindings.")
    
    unique_models = {m["id"]: m for m in all_models}
    return {"object": "list", "data": sorted(list(unique_models.values()), key=lambda x: x['id'])}


@openai_v1_router.get("/personalities", response_model=PersonalityListResponse)
async def list_personalities(
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
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

@openai_v1_router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    ASCIIColors.bold(f"Received Chat Completion Request. Model: {request.model}, Stream: {request.stream}")

    binding_alias, model_name = resolve_model_name(db, request.model)

    try:
        lc = build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name,
            llm_params={
                "temperature": request.temperature,
                "max_output_tokens": request.max_tokens
            },
            load_llm=True
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build LLM client: {str(e)}")

    messages = list(request.messages)
    if request.personality:
        personality = db.query(DBPersonality).filter(DBPersonality.id == request.personality).first()
        if not personality:
            raise HTTPException(status_code=404, detail="Personality not found.")
        if not personality.is_public and personality.owner_user_id != user.id:
            raise HTTPException(status_code=403, detail="You cannot use this personality.")
        messages.insert(0, ChatMessage(role="system", content=personality.prompt_text))

    openai_messages, images = preprocess_openai_messages(messages)
    
    if request.tools:
        openai_messages = handle_tools_injection(openai_messages, request.tools, request.tool_choice)

    generation_kwargs = {}
    if request.reasoning_effort:
        generation_kwargs["reasoning_effort"] = request.reasoning_effort

    ASCIIColors.info(f"Received images: {len(images)}")

    if request.stream:
        async def stream_generator():
            try:
                if request.tools:
                    ASCIIColors.info("Tools requested in stream mode. Buffering generation for safe parsing...")
                    
                    result_content = await asyncio.to_thread(
                        lc.generate_from_messages,
                        openai_messages,
                        temperature=request.temperature,
                        n_predict=request.max_tokens,
                        images=images,
                        **generation_kwargs
                    )

                    content, tool_calls = parse_tool_calls_from_text(result_content)

                    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
                    created_ts = int(time.time())

                    chunk = ChatCompletionStreamResponse(
                        id=completion_id,
                        model=request.model,
                        created=created_ts,
                        choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(role="assistant"))]
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"

                    if content:
                        chunk = ChatCompletionStreamResponse(
                            id=completion_id,
                            model=request.model,
                            created=created_ts,
                            choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(content=content))]
                        )
                        yield f"data: {chunk.model_dump_json()}\n\n"

                    if tool_calls:
                        for i, tc in enumerate(tool_calls):
                            tc.index = i
                            chunk = ChatCompletionStreamResponse(
                                id=completion_id,
                                model=request.model,
                                created=created_ts,
                                choices=[ChatCompletionResponseStreamChoice(
                                    index=0,
                                    delta=DeltaMessage(tool_calls=[tc])
                                )]
                            )
                            yield f"data: {chunk.model_dump_json()}\n\n"
                    
                    finish_reason = "tool_calls" if tool_calls else "stop"
                    chunk = ChatCompletionStreamResponse(
                        id=completion_id,
                        model=request.model,
                        created=created_ts,
                        choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(), finish_reason=finish_reason)]
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"
                    yield "data: [DONE]\n\n"

                else:
                    main_loop = asyncio.get_running_loop()
                    stream_queue = asyncio.Queue()
                    stop_event = threading.Event()
                    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
                    created_ts = int(time.time())

                    def llm_callback(chunk_text: str, msg_type: MSG_TYPE, **kwargs) -> bool:
                        if stop_event.is_set(): return False
                        if msg_type == MSG_TYPE.MSG_TYPE_CHUNK and chunk_text:
                            response_chunk = ChatCompletionStreamResponse(
                                id=completion_id,
                                model=request.model,
                                created=created_ts,
                                choices=[ChatCompletionResponseStreamChoice(
                                    index=0,
                                    delta=DeltaMessage(content=chunk_text)
                                )]
                            )
                            main_loop.call_soon_threadsafe(
                                stream_queue.put_nowait,
                                f"data: {response_chunk.model_dump_json()}\n\n"
                            )
                        return True

                    def blocking_gen():
                        try:
                            lc.generate_from_messages(
                                openai_messages,
                                streaming_callback=llm_callback,
                                images=images,
                                temperature=request.temperature,
                                n_predict=request.max_tokens,
                                stream=True,
                                **generation_kwargs
                            )
                        except Exception as ex:
                            ASCIIColors.error(f"Streaming Generation Error: {ex}")
                        finally:
                            main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)

                    threading.Thread(target=blocking_gen, daemon=True).start()

                    start_chunk = ChatCompletionStreamResponse(
                        id=completion_id,
                        model=request.model,
                        created=created_ts,
                        choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(role="assistant"))]
                    )
                    yield f"data: {start_chunk.model_dump_json()}\n\n"

                    while True:
                        item = await stream_queue.get()
                        if item is None:
                            break
                        yield item

                    end_chunk = ChatCompletionStreamResponse(
                        id=completion_id,
                        model=request.model,
                        created=created_ts,
                        choices=[ChatCompletionResponseStreamChoice(index=0, delta=DeltaMessage(), finish_reason="stop")]
                    )
                    yield f"data: {end_chunk.model_dump_json()}\n\n"
                    yield "data: [DONE]\n\n"

            except Exception as e:
                ASCIIColors.error(f"Stream Generator Crash: {e}")
                yield "data: [DONE]\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    else:
        try:
            ASCIIColors.info("Generating non-streaming response...")
            result_content = lc.generate_from_messages(
                openai_messages,
                temperature=request.temperature,
                n_predict=request.max_tokens,
                images=images,
                **generation_kwargs
            )
            
            content = result_content
            finish_reason = "stop"
            tool_calls = None

            if request.tools:
                content, tool_calls = parse_tool_calls_from_text(result_content)
                if tool_calls:
                    finish_reason = "tool_calls"
                    ASCIIColors.success(f"Parsed {len(tool_calls)} tool calls.")
            
            if tool_calls and not content:
                content = None

            msg_obj = ChatMessage(
                role="assistant", 
                content=content,
                tool_calls=tool_calls
            )

            choice = ChatCompletionResponseChoice(
                index=0,
                message=msg_obj,
                finish_reason=finish_reason
            )

            prompt_tokens = lc.count_tokens(str(openai_messages))
            completion_tokens = lc.count_tokens(result_content)
            
            return ChatCompletionResponse(
                id=f"chatcmpl-{uuid.uuid4().hex}",
                model=request.model,
                choices=[choice],
                usage=UsageInfo(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens
                )
            )
            
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

    try:
        lc = build_lollms_client_from_params(
            username=user.username,
            tti_binding_alias=tti_binding_alias,
            tti_model_name=tti_model_name,
            load_llm=False,
            load_tti=True
        )
        
        if not hasattr(lc, 'tti') or not lc.tti:
            raise HTTPException(status_code=500, detail=f"TTI functionality is not available for binding '{tti_binding_alias}'.")
        
        generated_images_data = []
        for i in range(request_data.n):
            image_bytes = lc.tti.generate_image(
                prompt=request_data.prompt,
                size=request_data.size, 
                quality=request_data.quality, 
                style=request_data.style
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


@openai_v1_router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(
    request: EmbeddingRequest,
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    binding_alias, model_name = resolve_model_name(db, request.model)

    try:
        lc = build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name,
            load_llm=True
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
            embedding_vector = lc.embed(text) 
            if not isinstance(embedding_vector, list) or not all(isinstance(f, (float, int)) for f in embedding_vector):
                print(f"Warning: Binding '{binding_alias}' embed function returned an unexpected type for input '{text[:50]}...': {type(embedding_vector)}")
                raise HTTPException(status_code=500, detail=f"The embedding model for binding '{binding_alias}' returned an invalid data format.")

            embeddings_data.append(EmbeddingObject(embedding=embedding_vector, index=i))
            total_tokens += lc.count_tokens(text)
            
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
    
    try:
        lc = build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name,
            load_llm=True
        )
        tokens = lc.tokenize(request.text)
        return TokenizeResponse(tokens=tokens, count=len(tokens))
    except AttributeError:
        lc = build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name,
            load_llm=True
        )
        count = lc.count_tokens(request.text)
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
    
    try:
        lc = build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name,
            load_llm=True
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
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    binding_alias, model_name = resolve_model_name(db, request.model)
    
    try:
        lc = build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name,
            load_llm=True
        )
        count = lc.count_tokens(request.text)
        return CountTokensResponse(count=count)
    except AttributeError:
        lc = build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name,
            load_llm=True
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
    user: DBUser = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    binding_alias, model_name = resolve_model_name(db, request.model)
    
    try:
        lc = build_lollms_client_from_params(
            username=user.username,
            binding_alias=binding_alias,
            model_name=model_name,
            load_llm=True
        )
        ctx_size = lc.get_ctx_size(model_name)
        return ContextSizeResponse(context_size=ctx_size)
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
        extracted_text, _ = extract_text_from_file_bytes(file_bytes, request.filename)
        return FileExtractionResponse(text=extracted_text)
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid base64 encoding.")
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"File extraction failed: {str(e)}")

  
   
# KEEP THISE FUNCTIONS FOR COMPATIBILITY
# --- Helper to Extract Images and Convert Messages ---
def preprocess_messages(messages: List[ChatMessage]) -> List[Dict]:
    processed = []
    image_list = []

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
                    url_img = item["image_url"].get("url")
                    if url_img:
                        image_list.append(url_img)
                elif item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                else:
                    text_parts.append(str(item))
            processed.append({"role": msg.role, "content": "\n".join(text_parts)})
        else:
            processed.append({"role": msg.role, "content": str(content)})

    return processed, image_list

def to_image_block(img, default_mime="image/jpeg"):
    # img can be: https URL, data URL, or raw base64
    if isinstance(img, dict):
        # Optional pattern: {'data': '<base64>', 'mime': 'image/png'} or {'url': 'https://...'}
        if "url" in img:
            url = img["url"]
            return {"type": "image_url", "image_url": {"url": url}}
        if "data" in img:
            mime = img.get("mime", default_mime)
            return {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{img['data']}"}
            }

    if isinstance(img, str):
        s = img.strip()
        if s.startswith("http://") or s.startswith("https://"):
            return {"type": "image_url", "image_url": {"url": s}}
        if s.startswith("data:"):
            return {"type": "image_url", "image_url": {"url": s}}
        # raw base64: add data URL prefix
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{default_mime};base64,{s}"}
        }

    raise ValueError("Unsupported image input format")
