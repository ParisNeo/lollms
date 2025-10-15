# Intermediate Concepts

Ready to unlock more of LoLLMs' power? This section covers key features that enhance your interaction with the AI.

<h2 id="personalities">Understanding Personalities</h2>

A **Personality** is a pre-defined set of instructions that tells the AI how to behave. It's more than just a system prompt; it can include:

-   A core system prompt defining its role, tone, and rules.
-   A custom icon and description.
-   Pre-activated MCPs (Tools).
-   A dedicated knowledge base using a Data Store.

You can switch personalities at any time from the dropdown in the global header. You can also create your own in **Settings -> Personalities**.

<h2 id="data-stores">Data Stores and RAG</h2>

**Retrieval-Augmented Generation (RAG)** allows the AI to use information from your own documents to answer questions. In LoLLMs, this is managed through **Data Stores**.

1.  **Create a Store:** Go to the "Data Stores" page from the user menu. Create a new store and give it a name.
2.  **Upload Documents:** Upload files (`.pdf`, `.docx`, `.txt`, etc.) to your store. The system will automatically chunk and index them.
3.  **Use in Chat:** In the chat view, open the **Data Zone**, select the "Discussion" tab, and use the RAG dropdown to attach one or more Data Stores to your current conversation.

The AI will now automatically search the selected stores for relevant information when you ask a question.

<h2 id="mcp-tools">MCPs (Tools)</h2>

**Modular Communication Protocols (MCPs)** are tools that extend the AI's capabilities, allowing it to interact with external services or perform complex tasks.

You can enable specific tools for your conversation from the chat input bar. When a tool is active, the AI can decide to use it to answer your prompt.

Examples include:
- A `Web Search` tool to get live information from the internet.
- A `Code Interpreter` to execute Python code.

Administrators can add and configure new MCPs from the Admin Panel.