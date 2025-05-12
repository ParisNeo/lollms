# Simplified LoLLMs Chat

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
![Version](https://img.shields.io/badge/Version-1.3.0-brightgreen) <!-- Updated Version -->
<!-- Add build status badge if CI is set up -->
<!-- [![Build Status](https://img.shields.io/your_ci_badge_url)](your_ci_link) -->

A simple, multi-user FastAPI backend and responsive HTML/Tailwind CSS frontend application designed to provide a chat interface powered by the [`lollms-client`](https://github.com/ParisNeo/lollms-client) library, with integrated Retrieval-Augmented Generation (RAG) capabilities using [`safe_store`](https://github.com/ParisNeo/safe_store). Now with multimodal chat support!

**Live Project:** [https://github.com/ParisNeo/simplified_lollms](https://github.com/ParisNeo/simplified_lollms)

## Overview

This project aims to provide a self-hostable, user-friendly chat interface that can connect to various Large Language Models (LLMs) supported by `lollms-client` (like Ollama, OpenAI, native LoLLMs). It features multi-user support with basic authentication, persistent discussions, RAG functionality for chatting with your documents, **multimodal chat (image input)**, and an administrative interface for user management.

## ✨ Features

*   **Multi-User Support:** Secure login via HTTP Basic Authentication. Each user has their own isolated discussions and RAG document store.
*   **Persistent Discussions:** Chat histories are saved per user and can be revisited. Discussions are stored as YAML files.
*   **LLM Integration:** Uses `lollms-client` to interact with various LLM backends (configurable).
*   **Streaming Responses:** AI responses are streamed back to the user interface for a real-time experience.
*   **Multimodal Chat:** Upload images along with your text prompts to interact with vision-capable models (like LLaVA via Ollama, GPT-4 Vision via OpenAI). The backend handles passing image data appropriately.
*   **Retrieval-Augmented Generation (RAG):**
    *   Upload documents (`.txt`, `.pdf`, `.docx`, `.html`, entire folders) via the UI.
    *   Documents are processed, chunked, and vectorized using `safe_store`.
    *   Toggle RAG usage during chat to inject relevant context from your documents into the LLM prompt.
    *   Manage uploaded RAG documents (list, delete).
*   **Configurable Models & Vectorizers:**
    *   Set global default LLM models and RAG vectorizers in `config.toml`.
    *   Users can override these defaults via the Settings UI (settings stored in the user database).
    *   Supports Sentence Transformer (`st:`) and TF-IDF (`tfidf:`) vectorizers via `safe_store`.
*   **Admin Panel:**
    *   Manage users (Add, List, Delete, Reset Password). Accessible via `/admin`.
    *   Initial superadmin user created from `config.toml`.
    *   **Admin button in sidebar** visible only to logged-in administrators.
*   **Data Export:** Users can export their discussions and SafeStore metadata as a JSON file.
*   **Responsive UI:** Refined interface built with Tailwind CSS, suitable for desktop and mobile. Includes image upload previews.
*   **Dark/Light Theme:** Toggle between themes.
*   **Internationalization (i18n):** Basic support for English (`en`) and French (`fr`). Easily extensible.
*   **SQLite Backend:** User accounts and settings are stored in a central SQLite database (`app_main.db`). SafeStore uses its own SQLite DB per user (`vector_store.db`).
*   **Bug Fixes:** Corrected SafeStore document deletion logic.

## 🏗️ Architecture

*   **Backend:** FastAPI (Python web framework)
*   **LLM Communication:** `lollms-client` library (handles text and image data)
*   **RAG/Vector Store:** `safe_store` library (SQLite based)
*   **User Database:** SQLAlchemy with SQLite
*   **Authentication:** HTTP Basic Auth + Passlib for password hashing
*   **Frontend:** Plain HTML, Tailwind CSS, Vanilla JavaScript (with Marked.js for Markdown rendering)
*   **Configuration:** TOML (`config.toml`)
*   **Discussion Storage:** YAML files per user
*   **Concurrency:** `filelock` used by `safe_store` for process-safe writes.

## 📸 Screenshots

*(Add updated screenshots showing the image upload button, image previews in chat, and the admin button)*

**Login Screen:**
`![Login Screen](placeholder_login.png)`

**Main Chat UI (with Image Upload):**
`![Chat UI](placeholder_chat_multimodal.png)`

**Settings Modal:**
`![Settings Modal](placeholder_settings.png)`

**RAG File Manager:**
`![RAG File Manager](placeholder_rag.png)`

**Admin Panel:**
`![Admin Panel](placeholder_admin.png)`

## 🚀 Getting Started

### Prerequisites

*   Python 3.8 or higher
*   Git
*   Pip (Python package installer)
*   An LLM backend accessible via `lollms-client` (e.g., Ollama running locally, OpenAI API key). **For image input, ensure the configured model supports vision.**

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/ParisNeo/simplified_lollms.git
    cd simplified_lollms
    ```

2.  **Set up a virtual environment (Recommended):**
    ```bash
    python -m venv venv
    # Activate the environment
    # On Windows: venv\Scripts\activate
    # On macOS/Linux: source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(This installs FastAPI, Uvicorn, lollms-client, safe_store[all], SQLAlchemy, Passlib, etc.)*

4.  **Configure the application:**
    *   Copy the example configuration file:
        ```bash
        cp config_example.toml config.toml
        ```
    *   **Edit `config.toml`:**
        *   **Crucially:** Change the `password` under `[initial_admin_user]` to a strong password.
        *   Review `[lollms_client_defaults]` and set the `binding_name` (e.g., `"ollama"`, `"openai"`) and `default_model_name`. **Choose a model that supports image input if you want to use the image upload feature** (e.g., `"llava:latest"` for Ollama, `"gpt-4-turbo"` or `"gpt-4o-mini"` for OpenAI).
        *   Set API keys/environment variables as needed for your chosen binding.
        *   Review `[safe_store_defaults]` and other sections.

5.  **Run the application:**
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 9642
    ```
    *(Adjust host/port as needed.)*

### Usage

1.  **Access the UI:** `http://localhost:9642` (or your host/port).
2.  **Login:** Use the initial admin credentials or credentials for other users created via the admin panel.
3.  **Chat:**
    *   Click "New Discussion".
    *   Select a discussion from the sidebar.
    *   **(New)** Click the image icon next to the text input to attach images (up to 5). Previews are shown.
    *   Type your message.
    *   Use the "Use RAG" checkbox if desired.
    *   Click Send or press Enter.
4.  **Settings:** Configure Language, LLM Model, RAG Vectorizer.
5.  **RAG File Manager:** Upload/manage documents for RAG.
6.  **Admin Panel (Admins Only):**
    *   Access via the "Admin Panel" button in the sidebar (visible only if logged in as admin) or go to `/admin`.
    *   Manage users.
7.  **Data Export:** Export discussions and metadata.

## ⚙️ Configuration (`config.toml`)

*(No changes to the structure, but ensure `default_model_name` under `[lollms_client_defaults]` is set to a model appropriate for your needs, including vision capabilities if desired.)*

*   **`[app_settings]`**: `data_dir`, `database_url`, `secret_key`.
*   **`[initial_admin_user]`**: `username`, `password` (**hashed** after first run).
*   **`[lollms_client_defaults]`**: `binding_name`, `default_model_name` (choose vision model for image support), `host_address`, `service_key_env_var`, etc.
*   **`[safe_store_defaults]`**: `chunk_size`, `chunk_overlap`, `global_default_vectorizer`, `encryption_key`.
*   **`[server]`**: `host`, `port`.

## 📚 API Documentation

Access interactive API docs via the running server:

*   **Swagger UI:** `http://localhost:9642/docs`
*   **ReDoc:** `http://localhost:9642/redoc`

## 📁 Folder Structure

*(No significant changes to the folder structure itself)*

```text
📁 simplified_lollms/
├─ 📁 data/                  # User data (created automatically)
│  ├─ 📁 user1/
│  │  ├─ 📁 discussions/
│  │  ├─ 📁 safestore_documents/
│  │  ├─ 📁 temp_uploads/      # Temporary image storage
│  │  └─ 📄 vector_store.db
│  └─ ...
├─ 📁 locales/
│  └─ ...
├─ 📄 .gitignore
├─ 📄 admin.html
├─ 📄 config.toml
├─ 📄 config_example.toml
├─ 📄 database_setup.py
├─ 📄 index.html             # Main chat UI (updated)
├─ 📄 LICENSE
├─ 📄 LOLLMS_CLIENT_DOC.md
├─ 📄 main.py                # FastAPI app (updated)
├─ 📄 README.md              # This file (updated)
├─ 📄 requirements.txt
└─ 📄 SAFESTORE_DOC.md
```

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## 📜 License

Apache License 2.0. See [LICENSE](LICENSE).
