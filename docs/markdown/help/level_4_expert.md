# Expert Configuration & Features

This guide is for power users, developers, and administrators who want to leverage the full capabilities of the LoLLMs platform.

<h2 id="api-usage">API Usage</h2>

LoLLMs exposes a comprehensive FastAPI backend. You can access the interactive API documentation (Swagger UI) at the `/docs` endpoint of your instance (e.g., `http://localhost:9642/docs`).

This allows you to programmatically:
- Manage users and discussions.
- Send generation requests.
- Interact with Data Stores.

All API endpoints require a bearer token for authentication, which can be generated from your user settings.

<h2 id="custom-bindings">Custom Bindings</h2>

The power of LoLLMs comes from its modular binding system. A **Binding** is a Python class that acts as a bridge to a specific LLM, TTI (Text-to-Image), or TTS (Text-to-Speech) backend.

As an administrator, you can configure new bindings from the **Admin Panel**. This allows you to connect LoLLMs to:
- Local models running via `Ollama`, `GPT4All`, etc.
- Hosted services like `OpenAI`, `Anthropic`, `Mistral`, etc.
- Custom-built model servers.

Each binding has its own set of configuration parameters, such as API keys, base URLs, and model paths.