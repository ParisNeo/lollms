# LoLLMs Platform Services & External API Reference

This directory houses the external HTTP API gateway services for the LoLLMs platform, allowing third-party applications, SDKs, agent frameworks, and OpenAI/Ollama-compatible clients to interact directly with LoLLMs.

The server provides three distinct service interfaces:
1. **LoLLMs Native Service API (`/lollms/v1`)** — Exclusive platform capabilities (per-binding-type model discovery, long-context processing, multi-source RAG datastores, speech synthesis with instant voice cloning, and deep token diagnostics).
2. **OpenAI Compatibility API (`/v1`)** — Drop-in replacement for OpenAI endpoints (Chat completions with streaming, function calling, reasoning tokens, multi-modal vision, DALL-E style image generation and editing, and embeddings).
3. **Ollama Compatibility API (`/ollama/v1`)** — Standard Ollama `/v1` endpoint replacement for developer tools that connect to local models.

---

## Table of Contents

- [Authentication & Configuration](#authentication--configuration)
  - [API Keys](#api-keys)
  - [Service Toggles & Permissions](#service-toggles--permissions)
  - [Rate Limiting](#rate-limiting)
- [1. LoLLMs Native Services (`/lollms/v1`)](#1-lollms-native-services-lollmsv1)
  - [System Capabilities (`GET /capabilities`)](#system-capabilities-get-capabilities)
  - [Per-Binding Model Listing (`GET /{binding_type}/models`)](#per-binding-model-listing-get-binding_typemodels)
  - [Tokenization & Diagnostics (`POST /tokenize`, `POST /detokenize`, `POST /context_size`)](#tokenization--diagnostics)
  - [Long-Context Processing (`POST /long_context_process`)](#long-context-processing-post-long_context_process)
  - [RAG Knowledge Bases (`GET /rag/databases`, `POST /rag/query`)](#rag-knowledge-bases)
  - [Text-to-Speech & Voice Synthesis (`POST /audio/speech`, `GET /audio/voices`)](#text-to-speech--voice-synthesis)
  - [Image Editing & Inpainting (`POST /images/edit`)](#image-editing--inpainting-post-imagesedit)
  - [Personalities Catalog (`GET /personalities`)](#personalities-catalog-get-personalities)
- [2. OpenAI v1 Compatibility Suite (`/v1`)](#2-openai-v1-compatibility-suite-v1)
  - [List Models (`GET /v1/models`)](#list-models-get-v1models)
  - [Chat Completions (`POST /v1/chat/completions`)](#chat-completions-post-v1chatcompletions)
  - [Responses API (`POST /v1/responses`)](#responses-api-post-v1responses)
  - [Audio Speech (`POST /v1/audio/speech`)](#audio-speech-post-v1audiospeech)
  - [Audio Transcriptions (`POST /v1/audio/transcriptions`)](#audio-transcriptions-post-v1audiotranscriptions)
  - [Audio Translations (`POST /v1/audio/translations`)](#audio-translations-post-v1audiotranslations)
  - [Image Generation (`POST /v1/images/generations`)](#image-generation-post-v1imagesgenerations)
  - [Image Edits (`POST /v1/images/edits`)](#image-edits-post-v1imagesedits)
  - [Embeddings (`POST /v1/embeddings`)](#embeddings-post-v1embeddings)
  - [Utility & Extraction Endpoints (`/tokenize`, `/context_size`, `/extract_text`)](#utility--extraction-endpoints)
- [3. Ollama Compatibility Suite (`/ollama/v1`)](#3-ollama-compatibility-suite-ollamav1)
  - [List Models (`GET /ollama/v1/models`)](#list-models-get-ollamav1models)
  - [Chat Completions (`POST /ollama/v1/chat/completions`)](#chat-completions-post-ollamav1chatcompletions)

---

## Authentication & Configuration

### API Keys
All requests against `/lollms/v1`, `/v1`, and `/ollama/v1` require authorization unless the administrator disabled the key requirement in the Admin Control Center.

Send your API key using the HTTP `Authorization` header with a `Bearer` token:
```http
Authorization: Bearer lollms_abcdef_0123456789abcdef0123456789abcdef
```

*Note: LoLLMs API keys follow the format `lollms_<prefix>_<secret>`.*

### Service Toggles & Permissions
Administrators can independently enable or disable services in **Admin Panel > Global Settings**:
- `lollms_services_enabled` (`true`/`false`)
- `lollms_services_require_key` (`true`/`false` — when `false`, keyless requests default to the superadmin user)
- `openai_api_service_enabled` (`true`/`false`)
- `openai_api_require_key` (`true`/`false`)
- `ollama_service_enabled` (`true`/`false`)
- `ollama_require_key` (`true`/`false`)

### Rate Limiting
When `rate_limit_enabled` is active, requests that exceed `rate_limit_max_requests` per `rate_limit_window_seconds` receive an HTTP `429 Too Many Requests` status code.

---

## 1. LoLLMs Native Services (`/lollms/v1`)

Base Path: `/lollms/v1`

### System Capabilities (`GET /capabilities`)
Inspects active bindings and capabilities configured on the server.

**Request**:
```bash
curl -X GET "http://localhost:9642/lollms/v1/capabilities" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

**Response (`200 OK`)**:
```json
{
  "capabilities": [
    "tokenize",
    "detokenize",
    "long_context_processing",
    "rag_query",
    "image_generation",
    "image_editing",
    "text_to_speech",
    "speech_to_text"
  ],
  "active_bindings": {
    "llm": ["ollama_main", "vllm_cluster"],
    "tti": ["diffusers_local"],
    "tts": ["xtts_v2"],
    "stt": ["whisper_cpp"],
    "rag": ["safe_store_minilm"]
  }
}
```

---

### Per-Binding Model Listing (`GET /{binding_type}/models`)
Lists all models available for a specific modality binding type.

#### Path Parameters
| Parameter | Type | Allowed Values | Description |
|---|---|---|---|
| `binding_type` | `string` | `llm`, `tti`, `tts`, `stt`, `ttv`, `ttm`, `rag` | The modality to enumerate. Also accepts aliases: `text`, `image`, `speech`, `audio`, `video`, `music`, `embeddings`. |

#### Query Parameters
| Parameter | Type | Required | Description |
|---|---|---|---|
| `binding_alias` | `string` | No | Optional filter to restrict results to a specific binding alias (e.g. `?binding_alias=ollama_main`). |

**Request**:
```bash
curl -X GET "http://localhost:9642/lollms/v1/tti/models" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

**Response (`200 OK`)**:
```json
{
  "object": "list",
  "binding_type": "tti",
  "total": 2,
  "data": [
    {
      "id": "diffusers_local/sdxl_turbo",
      "name": "SDXL Turbo Fast",
      "binding": "diffusers_local",
      "model_name": "sdxl_turbo",
      "alias": {
        "title": "SDXL Turbo Fast",
        "description": "Ultra fast single-step diffusion",
        "allow_parameters_override": true
      },
      "created": 1725382000,
      "owned_by": "lollms"
    },
    {
      "id": "diffusers_local/flux_schnell",
      "name": "FLUX.1 Schnell",
      "binding": "diffusers_local",
      "model_name": "flux_schnell",
      "alias": null,
      "created": 1725382000,
      "owned_by": "lollms"
    }
  ]
}
```

#### Convenience Root Endpoint (`GET /lollms/v1/models`)
Supports query parameters `?binding_type=llm` and `?binding_alias=...`.

---

### Tokenization & Diagnostics

#### Tokenize Text (`POST /tokenize`)
Converts raw string into integer token IDs using the specified model profile.

**Request Body**:
```json
{
  "model": "ollama_main/llama3.1:latest",
  "text": "Universal Intelligence Orchestration"
}
```

**Response (`200 OK`)**:
```json
{
  "tokens": [128000, 34502, 10839, 44211],
  "count": 4
}
```

#### Detokenize Tokens (`POST /detokenize`)
Reconstructs string text from integer token IDs.

**Request Body**:
```json
{
  "model": "ollama_main/llama3.1:latest",
  "tokens": [128000, 34502, 10839, 44211]
}
```

**Response (`200 OK`)**:
```json
{
  "text": "Universal Intelligence Orchestration"
}
```

#### Context Window Size (`POST /context_size`)
Queries the maximum context window capacity (in tokens) for a given model.

**Request Body**:
```json
{
  "model": "ollama_main/llama3.1:latest"
}
```

**Response (`200 OK`)**:
```json
{
  "context_size": 32768
}
```

---

### Long-Context Processing (`POST /long_context_process`)
Splits, processes, and synthesizes long documents using the configured sliding window and long-context processing algorithms.

**Request Body**:
```json
{
  "text": "Full text of a 200-page report or book...",
  "prompt": "Summarize the primary conclusions, risks, and recommended actions.",
  "model": "ollama_main/llama3.1:latest",
  "max_generation_tokens": 4096
}
```

**Response (`200 OK`)**:
```json
{
  "result": "Structured synthesis of the document..."
}
```

---

### RAG Knowledge Bases

#### List Accessible Databases (`GET /rag/databases`)
Returns all personal and public SafeStore vector databases available for querying.

**Request**:
```bash
curl -X GET "http://localhost:9642/lollms/v1/rag/databases" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

**Response (`200 OK`)**:
```json
{
  "object": "list",
  "data": [
    {
      "id": "e4b6c891-1234-4a5b-b999-0123456789ab",
      "name": "Project Documentation",
      "description": "Source code documentation and API contracts",
      "vectorizer": "safe_store_minilm",
      "is_public": false,
      "owner_username": "parisneo",
      "created_at": "2026-08-15T14:30:00Z"
    }
  ]
}
```

#### Query Knowledge Base (`POST /rag/query`)
Executes dense semantic or hybrid search directly against a SafeStore database.

**Request Body**:
```json
{
  "datastore_id": "e4b6c891-1234-4a5b-b999-0123456789ab",
  "query": "How does user authentication work?",
  "top_k": 5,
  "min_similarity": 50.0
}
```

**Response (`200 OK`)**:
```json
[
  {
    "id": "chunk_12",
    "document_title": "architecture.md",
    "chunk_text": "Authentication relies on JWT bearer tokens issued upon validation...",
    "similarity_percent": 88.4,
    "metadata": { "author": "dev-team" }
  }
]
```

---

### Text-to-Speech & Voice Synthesis

#### Generate Speech (`POST /audio/speech`)
Synthesizes speech audio from text. Supports binding voices, custom cloned voices, and zero-shot voice cloning from raw base64 samples.

**Request Body**:
```json
{
  "input": "Welcome to LoLLMs. Your Universal Intelligence platform is ready.",
  "voice": "alloy",
  "model": "xtts_v2/xtts",
  "response_format": "mp3",
  "speed": 1.0,
  "language": "en"
}
```

*For Zero-Shot Cloning without pre-registering a voice, pass a base64 encoded audio sample via `audio_sample`:*
```json
{
  "input": "This speech is generated in my voice.",
  "audio_sample": "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA...",
  "response_format": "wav"
}
```

**Response (`200 OK`)**:
- Binary stream containing the synthesized audio with `Content-Type: audio/mpeg` or `audio/wav`.

#### List Available Voices (`GET /audio/voices`)
Returns all voices (system presets, engine binding voices, and user custom cloned voices).

**Response (`200 OK`)**:
```json
{
  "object": "list",
  "data": [
    {
      "voice_id": "alloy",
      "name": "Alloy",
      "category": "system",
      "description": "OpenAI-compatible alias for alloy"
    },
    {
      "voice_id": "custom-voice-uuid-1",
      "name": "Personal Studio Voice",
      "category": "user_custom",
      "language": "en"
    }
  ]
}
```

---

### Image Editing & Inpainting (`POST /images/edit`)
Applies inpainting or prompt-based edits to an existing image.

**Request Body**:
```json
{
  "prompt": "Add a glowing blue neon sign saying LoLLMs",
  "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "mask": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "model": "diffusers_local/instruct_pix2pix"
}
```

**Response (`200 OK`)**:
```json
{
  "created": 1725382100,
  "data": [
    {
      "b64_json": "iVBORw0KGgoAAAANSUhEUgAA..."
    }
  ]
}
```

---

### Personalities Catalog (`GET /personalities`)
Lists all accessible AI personalities (system public conditionings and user-owned personas).

**Response (`200 OK`)**:
```json
{
  "object": "list",
  "data": [
    {
      "id": "c8b411-personality-uuid",
      "name": "Code Architect",
      "category": "Coding",
      "author": "ParisNeo",
      "description": "Senior system architect focused on clean, secure code",
      "is_public": true,
      "owner_username": "System",
      "created_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

---

## 2. OpenAI v1 Compatibility Suite (`/v1`)

Base Path: `/v1`

Fully compatible with official OpenAI SDKs (`openai` Python package, `openai-node`, LangChain, AutoGen, CrewAI, LiteLLM, and OpenWebUI).

To use with the official OpenAI Python library:
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:9642/v1",
    api_key="lollms_your_api_key_here"
)
```

---

### List Models (`GET /v1/models`)
Returns the model catalog formatted according to OpenAI specs.

**Request**:
```bash
curl -X GET "http://localhost:9642/v1/models" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

---

### Chat Completions (`POST /v1/chat/completions`)
Unified generation endpoint supporting streaming, functions/tools, multi-modal vision, and reasoning tokens.

#### Parameters
| Parameter | Type | Required | Description |
|---|---|---|---|
| `model` | `string` | Yes | Model identifier in `binding_alias/model_name` or configured profile alias. |
| `messages` | `array` | Yes | List of message objects (`role`: `system`, `user`, `assistant`, `tool`). |
| `temperature` | `float` | No | Sampling temperature (0.0 to 2.0). |
| `max_tokens` | `integer` | No | Maximum tokens to generate. |
| `max_completion_tokens` | `integer` | No | Preferred OpenAI parameter for maximum generated completion tokens (including reasoning). |
| `stream` | `boolean` | No | If `true`, returns Server-Sent Events (`text/event-stream`). |
| `tools` | `array` | No | List of tools / functions available to the model. |
| `tool_choice` | `string` or `object` | No | `"none"`, `"auto"`, `"required"`, or `{"type": "function", "function": {"name": "..."}}`. |
| `response_format` | `object` or `string` | No | Structured output configuration. Supports `{"type": "json_schema", "json_schema": {...}}` and `{"type": "json_object"}`. |
| `reasoning_effort`| `string` | No | `"low"`, `"medium"`, or `"high"` for reasoning/thinking models. |
| `personality` | `string` | No | Optional UUID of a LoLLMs personality conditioning to prepend. |

#### Standard Request (Non-Streaming)
```bash
curl -X POST "http://localhost:9642/v1/chat/completions" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "ollama_main/llama3.1:latest",
       "messages": [
         {"role": "system", "content": "You are a concise engineering assistant."},
         {"role": "user", "content": "What is Zero-Trust Architecture?"}
       ],
       "temperature": 0.2
     }'
```

#### Multimodal Vision Request
Pass images as base64 URLs or standard image URLs in user content:
```json
{
  "model": "ollama_main/llava:latest",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe what is shown in this diagram:"},
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
          }
        }
      ]
    }
  ]
}
```

#### Structured Outputs (`response_format: json_schema`)
Guarantees the model response strictly follows a provided JSON schema (compatible with `client.beta.chat.completions.parse`):

```json
{
  "model": "ollama_main/llama3.1:latest",
  "messages": [
    {"role": "user", "content": "Extract research metrics from: The algorithm achieved 98.2% accuracy with 14ms latency."}
  ],
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "BenchmarkResult",
      "schema": {
        "type": "object",
        "properties": {
          "accuracy_percent": {"type": "number"},
          "latency_ms": {"type": "number"}
        },
        "required": ["accuracy_percent", "latency_ms"],
        "additionalProperties": false
      },
      "strict": true
    }
  }
}
```

#### Reasoning Models & Chain of Thought
When interacting with reasoning models (o1, o3, DeepSeek-R1, QwQ):
- Non-streaming responses return thinking tokens in `message.reasoning_content` and final answers in `message.content`.
- Streaming responses emit delta events with `delta.reasoning_content` followed by `delta.content`.
- Token breakdown includes `usage.completion_tokens_details.reasoning_tokens`.

---

### Responses API (`POST /v1/responses`)
OpenAI's modern agentic primitive unifying instructions, multi-turn inputs, tools, and reasoning tokens.

**Request**:
```json
{
  "model": "ollama_main/llama3.1:latest",
  "instructions": "You are a research analyst. Be concise.",
  "input": "Summarize recent breakthroughs in quantum computing."
}
```

**Response (`200 OK`)**:
```json
{
  "id": "resp_0123456789abcdef",
  "object": "response",
  "created_at": 1725382250,
  "model": "ollama_main/llama3.1:latest",
  "status": "completed",
  "output": [
    {
      "id": "msg_0123456789ab",
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "text",
          "text": "Recent breakthroughs in quantum computing focus on topological qubits..."
        }
      ]
    }
  ],
  "usage": {
    "prompt_tokens": 18,
    "completion_tokens": 64,
    "total_tokens": 82
  }
}
```

---

### Audio Speech (`POST /v1/audio/speech`)
Official OpenAI text-to-speech endpoint (`client.audio.speech.create(...)`).

**Request**:
```json
{
  "model": "tts-1",
  "input": "The OpenAI audio speech endpoint is now live on LoLLMs.",
  "voice": "alloy",
  "response_format": "mp3"
}
```

**Response (`200 OK`)**:
- Binary audio stream (`Content-Type: audio/mpeg`).

---

### Audio Transcriptions (`POST /v1/audio/transcriptions`)
Official OpenAI speech-to-text endpoint (`client.audio.transcriptions.create(...)`).

**Form Data**:
- `file`: Audio file (`.mp3`, `.wav`, `.m4a`, `.webm`)
- `model`: `"whisper-1"` (or configured STT binding)
- `language` (optional): ISO code (e.g. `"en"`)
- `response_format` (optional): `"json"`

**Response (`200 OK`)**:
```json
{
  "text": "The audio file was transcribed accurately."
}
```

---

### Audio Translations (`POST /v1/audio/translations`)
Transcribes audio in any supported language and translates the transcript directly into English.

**Tool Call Response (`200 OK`)**:
```json
{
  "id": "chatcmpl-a1b2c3d4e5",
  "object": "chat.completion",
  "created": 1725382200,
  "model": "ollama_main/llama3.1:latest",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "abc123XYZ",
            "type": "function",
            "function": {
              "name": "get_current_weather",
              "arguments": "{\"city\": \"Paris\"}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ],
  "usage": {
    "prompt_tokens": 120,
    "completion_tokens": 30,
    "total_tokens": 150
  }
}
```

---

### Image Generation (`POST /v1/images/generations`)
Generates images using the configured Text-to-Image (TTI) engine.

**Request Body**:
```json
{
  "prompt": "A modern cybernetic robotic owl sitting on an ancient leather book, dramatic studio lighting, 8k",
  "model": "diffusers_local/sdxl_turbo",
  "n": 1,
  "size": "1024x1024",
  "response_format": "b64_json"
}
```

---

### Image Edits (`POST /v1/images/edits`)
OpenAI-compatible multipart image editing and inpainting.

**Form Data Fields**:
- `image`: File (PNG/JPEG/WEBP source image)
- `prompt`: String describing the modification
- `mask` (optional): File (PNG mask with transparency defining edit areas)
- `model` (optional): TTI model alias
- `size` (optional): `"1024x1024"`
- `response_format`: `"b64_json"` or `"url"`

---

### Embeddings (`POST /v1/embeddings`)
Calculates dense semantic embedding vectors for text strings.

**Request Body**:
```json
{
  "model": "ollama_main/nomic-embed-text:latest",
  "input": [
    "Secure computation in distributed environments.",
    "Kernel memory management protocols."
  ]
}
```

**Response (`200 OK`)**:
```json
{
  "object": "list",
  "model": "ollama_main/nomic-embed-text:latest",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.0124, -0.0452, 0.0891, "..."]
    },
    {
      "object": "embedding",
      "index": 1,
      "embedding": [-0.0341, 0.0112, 0.0543, "..."]
    }
  ],
  "usage": {
    "prompt_tokens": 18,
    "completion_tokens": 0,
    "total_tokens": 18
  }
}
```

---

### Utility & Extraction Endpoints

#### Document Text Extraction (`POST /v1/extract_text`)
Extracts plain text from base64 document files (PDF, DOCX, XLSX, PPTX, MSG, code files).

**Request Body**:
```json
{
  "filename": "specification.pdf",
  "file": "JVBERi0xLjQKJcTl8uXr..."
}
```

**Response (`200 OK`)**:
```json
{
  "text": "Full extracted textual content from the document..."
}
```

---

## 3. Ollama Compatibility Suite (`/ollama/v1`)

Base Path: `/ollama/v1`

For local tools configured with `OLLAMA_HOST="http://localhost:9642/ollama"`.

### List Models (`GET /ollama/v1/models`)
Returns active models in standard Ollama `/v1` format.

### Chat Completions (`POST /ollama/v1/chat/completions`)
Accepts standard Ollama/OpenAI chat payloads with streaming SSE responses, function calling, and images.

---

## Error Handling & HTTP Status Codes

| Code | Status | Meaning |
|---|---|---|
| `200` | OK | Request processed successfully. |
| `201` | Created | Resource (post, message, key) successfully created. |
| `400` | Bad Request | Missing mandatory parameters or invalid JSON schema. |
| `401` | Unauthorized | API key missing, invalid prefix, or expired token. |
| `403` | Forbidden | Requested service or resource is disabled by administrator policy. |
| `404` | Not Found | Requested model, database, or voice profile does not exist. |
| `413` | Payload Too Large | Uploaded media exceeds size limits (15MB image / 60MB video / 25MB audio). |
| `429` | Rate Limited | Request threshold exceeded for current time window. |
| `499` | Client Disconnected | Client terminated connection mid-generation; backend safely aborted engine execution. |
| `500` | Internal Error | Backend engine exception or execution failure. |
| `501` | Not Implemented | Requested modality binding (e.g. TTI/TTS/RAG) is not installed on host. |