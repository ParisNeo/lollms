# Simplified LoLLMs API Documentation

**Version:** 1.6.0

Welcome to the official API documentation for the Simplified LoLLMs Chat application. This document provides developers with all the information needed to interact with the powerful, multi-user, OpenAI-compatible API endpoints.

## Introduction

The Simplified LoLLMs API provides a robust backend service that bridges the gap between the versatile LoLLMs (Lollms-Client) ecosystem and applications built for the OpenAI API standard. It allows multiple users to interact with various language model bindings, manage personalities, and perform core LLM tasks through a familiar RESTful interface.

### Key Features

*   **OpenAI Compatibility:** Leverage the widespread adoption of the OpenAI API format for chat completions, making it easy to integrate with existing tools and clients.
*   **Multi-User & Multi-Binding:** The API supports multiple registered users, each with their own settings and API keys. It can connect to and manage multiple LoLLMs bindings simultaneously.
*   **API Key Authentication:** Secure your endpoints with a straightforward bearer token authentication system. Users can generate and manage their own keys through the web interface.
*   **Personality Integration:** Go beyond standard system prompts with LoLLMs Personalities. List available personalities and use them directly in your chat completion requests to easily invoke complex instruction sets.
*   **Streaming and Non-Streaming:** Supports both standard request-response and real-time streaming (Server-Sent Events) for chat completions.
*   **Tokenizer Utilities:** Provides endpoints to tokenize, detokenize, and count tokens, allowing for precise prompt engineering and cost estimation.

## Authentication

All requests to the `/v1/` API endpoints must be authenticated using a Bearer Token.

### 1. Generating an API Key

API keys cannot be generated via the API itself. A user must:

1.  Log in to the Simplified LoLLMs web interface.
2.  Navigate to **Settings -> API Keys**.
3.  Click "Generate New API Key", provide an alias (a memorable name), and click "Create".
4.  The full API key (e.g., `lollms_aBcDeF12_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`) will be displayed **only once**. Copy and store it securely. Only the prefix (e.g., `lollms_aBcDeF12`) will be visible later.

### 2. Using the API Key

To authenticate an API request, include an `Authorization` header with your API key as a Bearer token.

**Header Format:**

```
Authorization: Bearer YOUR_API_KEY
```

**Example `curl` Request:**

```bash
curl -X GET "http://localhost:9642/v1/models" \
     -H "Authorization: Bearer lollms_aBcDeF12_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

Any request made to a `/v1/` endpoint without a valid key will result in a `401 Unauthorized` error.

---

## API Endpoints

All endpoints are prefixed with `/v1`.

### Models

#### List Models

Retrieves a list of all available models from all active LoLLMs bindings. The model ID is formatted as `binding_alias/model_name`.

*   **Endpoint:** `GET /v1/models`
*   **Method:** `GET`
*   **Success Response:** `200 OK`

**Response Body:**

```json
{
  "object": "list",
  "data": [
    {
      "id": "ollama/llama3",
      "object": "model",
      "created": 1715888888,
      "owned_by": "lollms"
    },
    {
      "id": "ollama/mistral",
      "object": "model",
      "created": 1715888888,
      "owned_by": "lollms"
    },
    {
      "id": "another_binding/gpt-4",
      "object": "model",
      "created": 1715888888,
      "owned_by": "lollms"
    }
  ]
}
```

### Personalities

#### List Personalities

Retrieves a list of all personalities that are either public or owned by the authenticated user.

*   **Endpoint:** `GET /v1/personalities`
*   **Method:** `GET`
*   **Success Response:** `200 OK`

**Response Body:**

```json
{
  "object": "list",
  "data": [
    {
      "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
      "object": "personality",
      "name": "Creative Writer",
      "category": "Writing",
      "author": "System",
      "description": "A personality that helps with creative writing.",
      "is_public": true,
      "owner_username": "System",
      "created_at": "2025-07-14T22:00:00Z"
    },
    {
      "id": "f0e9d8c7-b6a5-4321-fedc-ba9876543210",
      "object": "personality",
      "name": "My Private Coder",
      "category": "Development",
      "author": "john_doe",
      "description": "A custom personality for Python code generation.",
      "is_public": false,
      "owner_username": "john_doe",
      "created_at": "2025-07-15T10:30:00Z"
    }
  ]
}
```

### Chat Completions

#### Create Chat Completion

Generates a model response for a given conversation.

*   **Endpoint:** `POST /v1/chat/completions`
*   **Method:** `POST`
*   **Success Response:** `200 OK`

**Request Body:**

| Field         | Type              | Required | Description                                                                                                                                                                                                  |
| ------------- | ----------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `model`       | `string`          | Yes      | The ID of the model to use, in `binding_alias/model_name` format (e.g., `ollama/llama3`).                                                                                                                      |
| `messages`    | `array[object]`   | Yes      | A list of message objects representing the conversation history. See [Message Object](#message-object).                                                                                                      |
| `personality` | `string`          | No       | The ID of a LoLLMs personality to use. If provided, its prompt text will be used as the system prompt, overriding any `system` role messages in the `messages` array.                                         |
| `temperature` | `float`           | No       | The generation temperature. Defaults to `0.7`.                                                                                                                                                               |
| `max_tokens`  | `integer`         | No       | The maximum number of tokens to generate in the completion.                                                                                                                                                  |
| `stream`      | `boolean`         | No       | If `true`, the response will be streamed as Server-Sent Events. If `false` (default), the full response will be returned after generation is complete.                                                         |

**<a name="message-object"></a>Message Object:**

| Field     | Type     | Required | Description                                    |
| --------- | -------- | -------- | ---------------------------------------------- |
| `role`    | `string` | Yes      | The role of the author: `system`, `user`, or `assistant`. |
| `content` | `string` | Yes      | The content of the message.                    |

---

**Example 1: Standard (Non-Streaming) Request**

This example asks the model a question and waits for the full response.

**Request:**

```json
{
  "model": "ollama/llama3",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "What is the capital of France?"
    }
  ]
}
```

**Response (`200 OK`):**

```json
{
  "id": "chatcmpl-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "object": "chat.completion",
  "created": 1715890000,
  "model": "ollama/llama3",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The capital of France is Paris."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 8,
    "total_tokens": 33
  }
}
```

---

**Example 2: Streaming Request**

This example makes the same request but receives the response as a stream of events.

**Request:**

```json
{
  "model": "ollama/llama3",
  "messages": [
    {
      "role": "user",
      "content": "Tell me a short story about a robot."
    }
  ],
  "stream": true
}
```

**Response (`200 OK`, `Content-Type: text/event-stream`):**

The server will send a sequence of Server-Sent Events (SSE). Each event is a JSON object prefixed with `data: ` and ending with `\n\n`.

```
data: {"id":"chatcmpl-zzzzzzzz","object":"chat.completion.chunk","created":1715890100,"model":"ollama/llama3","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-zzzzzzzz","object":"chat.completion.chunk","created":1715890100,"model":"ollama/llama3","choices":[{"index":0,"delta":{"content":"Unit"},"finish_reason":null}]}

data: {"id":"chatcmpl-zzzzzzzz","object":"chat.completion.chunk","created":1715890100,"model":"ollama/llama3","choices":[{"index":0,"delta":{"content":" 734"},"finish_reason":null}]}

data: {"id":"chatcmpl-zzzzzzzz","object":"chat.completion.chunk","created":1715890100,"model":"ollama/llama3","choices":[{"index":0,"delta":{"content":" whirred"},"finish_reason":null}]}

data: {"id":"chatcmpl-zzzzzzzz","object":"chat.completion.chunk","created":1715890100,"model":"ollama/llama3","choices":[{"index":0,"delta":{"content":" silently."},"finish_reason":null}]}

data: {"id":"chatcmpl-zzzzzzzz","object":"chat.completion.chunk","created":1715890100,"model":"ollama/llama3","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]```

*   The first chunk typically contains the `role`.
*   Subsequent chunks contain `content` deltas.
*   The final chunk before `[DONE]` has an empty `delta` and a `finish_reason`.
*   The stream is terminated by `data: [DONE]\n\n`.

---

**Example 3: Request with a Personality**

This example uses a personality to guide the model's response, which is more powerful than a simple system prompt.

**Request:**

```json
{
  "model": "ollama/llama3",
  "messages": [
    {
      "role": "user",
      "content": "Write a short poem about the sea."
    }
  ],
  "personality": "a1b2c3d4-e5f6-7890-1234-567890abcdef"
}
```

**Behavior:** The system will fetch the personality with the given ID. If its prompt text is `"You are a world-class poet. You respond only in beautiful, rhyming verse."`, this text will be used as the system prompt for the generation, and the model will produce a poem.

### Tokenizer Utilities

#### Tokenize Text

Converts a string of text into a list of token IDs for a specific model.

*   **Endpoint:** `POST /v1/tokenize`
*   **Request Body:**
    *   `model` (`string`, required): Model ID (`binding_alias/model_name`).
    *   `text` (`string`, required): The text to tokenize.
*   **Response (`200 OK`):**
    *   `tokens` (`array[integer]`): The list of token IDs.
    *   `count` (`integer`): The number of tokens.

#### Detokenize Tokens

Converts a list of token IDs back into a string of text.

*   **Endpoint:** `POST /v1/detokenize`
*   **Request Body:**
    *   `model` (`string`, required): Model ID (`binding_alias/model_name`).
    *   `tokens` (`array[integer]`, required): The list of tokens to detokenize.
*   **Response (`200 OK`):**
    *   `text` (`string`): The resulting detokenized text.

#### Count Tokens

Counts the number of tokens in a string of text.

*   **Endpoint:** `POST /v1/count_tokens`
*   **Request Body:**
    *   `model` (`string`, required): Model ID (`binding_alias/model_name`).
    *   `text` (`string`, required): The text to analyze.
*   **Response (`200 OK`):**
    *   `count` (`integer`): The total number of tokens.

### Model Utilities

#### Get Context Size

Retrieves the maximum context window size (in tokens) for a given model.

*   **Endpoint:** `POST /v1/context_size`
*   **Request Body:**
    *   `model` (`string`, required): Model ID (`binding_alias/model_name`).
*   **Response (`200 OK`):**
    *   `context_size` (`integer`): The model's context window size.

---

### Error Codes

The API uses standard HTTP status codes to indicate the success or failure of a request.

| Code | Status                 | Meaning                                                                                                                              |
| ---- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| 200  | OK                     | The request was successful.                                                                                                          |
| 400  | Bad Request            | The request was malformed, such as missing a required parameter or having an invalid `model` name format.                            |
| 401  | Unauthorized           | No API key was provided, or the key is invalid.                                                                                      |
| 403  | Forbidden              | The API key is valid, but the user does not have permission to perform the action (e.g., using a private personality).               |
| 404  | Not Found              | The requested resource (e.g., a specific model, personality, or binding) could not be found.                                         |
| 500  | Internal Server Error  | An unexpected error occurred on the server side, such as a problem with a LoLLMs binding or a database issue.                        |
| 501  | Not Implemented        | A feature is not available (e.g., trying to use RAG features when the `safe_store` library isn't installed).                           |