# Expert & Developer Guide

This section is for power users, developers, and prompt engineers who want to unlock the full potential of LoLLMs through bindings, APIs, and custom scripting.

## 1. Advanced Binding Configuration
Bindings are the core connectivity layer of LoLLMs.

- **Context Size Optimization**: Increasing context size allows the AI to remember more of a long conversation but consumes significantly more VRAM. 
    - *Expert Tip*: Use **Quantized Models (GGUF)** with llama.cpp to fit larger contexts into consumer hardware.
- **Stop Sequences**: Define custom strings (like `User:`) to prevent the AI from generating both sides of a conversation.
- **Repeat Penalty**: Fine-tune the `Penalty Alpha` and `Repeat Last N` to prevent the AI from becoming repetitive in long creative writing sessions.

## 2. The Zoos & Package Management
The "Zoo" system is LoLLMs' built-in package manager.

- **Personality Zoo**: Beyond simple personas, many "personalities" are full Python scripts.
    - **Lollms Coder**: Can execute code to verify its own solutions.
    - **Internet Researcher**: Uses DuckDuckGo and Scraper tools autonomously.
- **Apps Zoo**: These are independent web applications that run on top of LoLLMs. For example, a dedicated "Resume Reviewer" or "Email Drafter".
- **MCP Zoo**: Connect to **Model Context Protocol** servers. This allows models to access your local file system, run shell commands, or query external databases safely.

## 3. Professional API Access
LoLLMs serves a professional-grade REST API.

### Authentication
Every request must include your API Key:
`Authorization: Bearer lollms_your_key_here`

### Compatibility Layers
1.  **OpenAI V1**: Reachable at `/v1`. Compatible with standard OpenAI libraries.
2.  **Ollama**: Reachable at `/ollama/v1`.
3.  **LoLLMs Native**: Reachable at `/api/lollms/v1`. Use this for advanced features like:
    - `tokenize`: Get precise token counts.
    - `long_context_process`: Automatically handle documents larger than the model's window.

## 4. Custom Personalities & Scripting
You can create your own personality by defining a `config.yaml` and an optional `processor.py`.

- **System Prompt**: Ground the model in a specific set of rules.
- **Processors**: Use Python to intercept the user's message before it reaches the LLM, or post-process the LLM's output to format it into JSON, CSV, or code.

---
*Visit the [GitHub Wiki](https://github.com/ParisNeo/lollms/wiki) for deep-dive technical documentation and community scripts.*
