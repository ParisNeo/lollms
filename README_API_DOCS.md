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

### 📄 Long Context Processing
*   **`POST /lollms/v1/long_context_process`**: This is the "Special Sauce." It allows you to send massive amounts of text that exceed the model's context window. LoLLMs will automatically chunk, summarize, and synthesize the information to provide a coherent result.
    *   *Payload:* `{"text": "...", "prompt": "Summarize this entire 500-page document", "max_generation_tokens": 4096}`

### 🗄️ RAG (Retrieval Augmented Generation)
*   **`POST /lollms/v1/rag/query`**: Directly query one of your private Data Stores via the API. This returns relevant text chunks based on semantic similarity.
    *   *Payload:* `{"datastore_id": "uuid", "query": "What are our Q3 targets?", "top_k": 5}`

### 🎨 Advanced Image Editing
*   **`POST /lollms/v1/images/edit`**: An Image-to-Image (ITI) service. Upload a base image and a text prompt to perform AI-driven edits or in-painting.
    *   *Payload:* `{"image": "base64_data", "prompt": "Change the cat to a tiger", "mask": "optional_base64_mask"}`

---

## ⚠️ Rate Limiting
If enabled by the administrator, your requests may be limited. If you exceed the allowed threshold, the server will return a `429 Too Many Requests` status code. You can view your current usage stats in the **Admin Dashboard** (Admins only).

## 💻 Example: Calling LoLLMs Service via cURL

```bash
curl http://localhost:9642/lollms/v1/tokenize \
  -H "Authorization: Bearer lollms_xxxx_xxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ollama/llama3",
    "text": "Hello, how are you today?"
  }'
```