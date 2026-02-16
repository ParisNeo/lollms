# 📚 LoLLMs API Documentation

LoLLMs provides three distinct interface layers to ensure compatibility with existing tools while providing access to advanced, platform-specific features.

## 🔑 1. Authentication: Generating Your API Key

To interact with any of the services, you must provide a valid API key (unless the administrator has disabled the requirement for keys).

1.  **Log in** to your LoLLMs WebUI account.
2.  Navigate to **Settings** (bottom left or via User Profile).
3.  Select the **API Keys** tab.
4.  Enter an **Alias** for your key (e.g., "My Python Script" or "LiteLLM").
5.  Click **Create New Key**.
6.  **CRITICAL:** Copy the key immediately. For security reasons, it will only be displayed once.

**Usage:**
Pass the key in the HTTP Authorization header for all requests:
```http
Authorization: Bearer YOUR_API_KEY
```

---

## 🟢 Service 1: OpenAI Compatible API
**Base URL Path:** `/v1`

This service implements the standard OpenAI V1 specification. It allows you to use LoLLMs as a drop-in replacement for any tool that supports OpenAI (e.g., AutoGPT, LangChain, Continue.dev).

### Endpoints:
*   **`GET /v1/models`**: Lists all available models across your active LLM bindings.
*   **`POST /v1/chat/completions`**: Standard chat completion endpoint. Supports streaming, tool calls (function calling), and vision if the underlying model supports it.
*   **`POST /v1/embeddings`**: Generates vector embeddings for a given input string or list of strings.
*   **`POST /v1/images/generations`**: Generates images using the platform's active Text-to-Image (TTI) engine.

---

## 🟠 Service 2: Ollama Compatible API
**Base URL Path:** `/ollama/v1`

This service provides an interface compatible with the Ollama API structure. It is ideal for tools that specifically look for an Ollama-style endpoint or use the Ollama SDK.

### Endpoints:
*   **`GET /ollama/v1/models`**: Returns active models in the Ollama JSON format.
*   **`POST /ollama/v1/chat/completions`**: Standard chat interface. Requests are internally routed through the LoLLMs generation engine.

---

## 🔵 Service 3: LoLLMs Exclusive Services
**Base URL Path:** `/lollms/v1`

These endpoints provide access to features unique to the LoLLMs architecture that are not covered by standard OpenAI or Ollama specs.

### 🧩 Tokenizer & Utilities
*   **`POST /lollms/v1/tokenize`**: Returns the integer token IDs for a given string.
    *   *Payload:* `{"model": "binding/model", "text": "Hello world"}`
*   **`POST /lollms/v1/detokenize`**: Converts token IDs back into string text.
    *   *Payload:* `{"model": "binding/model", "tokens": [1, 2, 3]}`

### 🎙️ Text-to-Speech (TTS)
*   **`POST /lollms/v1/audio/speech`**: Generates audio from text using the configured TTS engine. Compatible with OpenAI's `/audio/speech` endpoint.
    *   *Payload:* `{"input": "Hello, this is a test", "voice": "alloy", "model": "binding/model", "response_format": "mp3", "speed": 1.0}`
    *   *Response:* Raw audio bytes (content-type depends on `response_format`)
*   **`GET /lollms/v1/audio/voices`**: Lists all available voices including user custom voices, binding voices, and OpenAI-compatible aliases (alloy, echo, fable, onyx, nova, shimmer).

### 📄 Long Context Processing
*   **`POST /lollms/v1/long_context_process`**: This is the "Special Sauce." It allows you to send massive amounts of text that exceed the model's context window. LoLLMs will automatically chunk, summarize, and synthesize the information to provide a coherent result.
    *   *Payload:* `{"text": "...", "prompt": "Summarize this entire 500-page document", "max_generation_tokens": 4096}`

### 🗄️ RAG (Retrieval Augmented Generation)
*   **`GET /lollms/v1/rag/databases`**: Lists all RAG databases (datastores) available to your user account. This includes your own datastores (both private and public) plus any public datastores from other users. Use this to discover `datastore_id` values for the query endpoint.
    *   *Response:* `{"object": "list", "data": [{"id": "uuid", "name": "My Docs", "description": "...", "vectorizer": "openai", "is_public": false, "owner_username": "you"}, ...]}`
*   **`POST /lollms/v1/rag/query`**: Directly query one of your private Data Stores via the API. This returns relevant text chunks based on semantic similarity.
    *   *Payload:* `{"datastore_id": "uuid", "query": "What are our Q3 targets?", "top_k": 5}`

### 🎨 Advanced Image Editing
*   **`POST /lollms/v1/images/edit`**: An Image-to-Image (ITI) service. Upload a base image and a text prompt to perform AI-driven edits or in-painting.
    *   *Payload:* `{"image": "base64_data", "prompt": "Change the cat to a tiger", "mask": "optional_base64_mask"}`

---

## ⚠️ Rate Limiting
If enabled by the administrator, your requests may be limited. If you exceed the allowed threshold, the server will return a `429 Too Many Requests` status code. You can view your current usage stats in the **Admin Dashboard** (Admins only).

## 💻 Example: Calling LoLLMs Service via cURL

### List Available RAG Databases
```bash
curl http://localhost:9642/lollms/v1/rag/databases \
  -H "Authorization: Bearer lollms_xxxx_xxxx"
```

### Query a RAG Database
```bash
curl http://localhost:9642/lollms/v1/rag/query \
  -H "Authorization: Bearer lollms_xxxx_xxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "datastore_id": "550e8400-e29b-41d4-a716-446655440000",
    "query": "What is the company vacation policy?",
    "top_k": 3,
    "min_similarity": 60.0
  }'
```

### Tokenize Text
```bash
curl http://localhost:9642/lollms/v1/tokenize \
  -H "Authorization: Bearer lollms_xxxx_xxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ollama/llama3",
    "text": "Hello, how are you today?"
  }'
```

### Generate Speech
```bash
curl http://localhost:9642/lollms/v1/audio/speech \
  -H "Authorization: Bearer lollms_xxxx_xxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Welcome to LoLLMs, the Lord of Large Language and Multimodal Systems!",
    "voice": "alloy",
    "response_format": "mp3"
  }' \
  --output welcome.mp3
```

### Generate Speech with Custom Voice Sample
You can provide a base64-encoded audio sample directly in the request for instant voice cloning. This is useful for one-off voice generation without pre-registering a voice:
```bash
# First, encode your voice sample to base64 (e.g., a 10-30 second WAV file)
VOICE_SAMPLE=$(base64 -w 0 /path/to/your_voice_sample.wav)

curl http://localhost:9642/lollms/v1/audio/speech \
  -H "Authorization: Bearer lollms_xxxx_xxxx" \
  -H "Content-Type: application/json" \
  -d "{
    \"input\": \"Hello, this is my cloned voice speaking!\",
    \"audio_sample\": \"$VOICE_SAMPLE\",
    \"response_format\": \"wav\"
  }" \
  --output cloned_speech.wav
```
**Note:** The `audio_sample` parameter takes precedence over `voice`. The audio sample should be clear and ideally 10-30 seconds long for best results.

### List Available Voices
```bash
curl http://localhost:9642/lollms/v1/audio/voices \
  -H "Authorization: Bearer lollms_xxxx_xxxx"
```