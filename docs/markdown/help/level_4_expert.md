# Expert & Developer Guide

For power users, developers, and prompt engineers.

## 1. Managing Bindings

Bindings connect LoLLMs to the underlying AI engines.
*   **Changing Models**: Go to **Settings > Bindings**. You can switch the active model for a binding (e.g., change from `llama3-8b` to `mistral-7b`).
*   **Parameters**: Fine-tune generation parameters like `Temperature`, `Top-K`, `Top-P`, and `Context Size`.

## 2. The Zoos

The "Zoo" system allows installing new capabilities.
*   **Models Zoo**: Download generic GGUF models from HuggingFace or other sources.
*   **Personalities Zoo**: Install community-created personalities with specialized prompts and tools.
*   **Apps Zoo**: Install server-side extensions (e.g., a simplified UI, a specific workflow tool).

## 3. API Access

LoLLMs provides a REST API compatible with OpenAI libraries.
1.  Go to **Settings > API Keys**.
2.  Generate a new API Key.
3.  Endpoint: `http://your-server:9642/v1`.
4.  You can use this with tools like AutoGen, LangChain, or standard OpenAI client libraries.

## 4. Scripting & Tools

*   **Python Code Execution**: Some personalities (like "Lollms Coder") can write and execute Python code in a sandboxed environment on the server.
*   **MCPs (Model Context Protocol)**: LoLLMs supports MCP, allowing you to connect external tools (like database access, web search) that the AI can invoke autonomously.

## 5. Custom Personalities

You can create your own personality:
1.  Go to **Settings > Personalities**.
2.  Click **+** to create new.
3.  Define the `System Prompt`, initial message, and even attach python scripts for complex logic.
