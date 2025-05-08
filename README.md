# Simplified LoLLMs Chat

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
![Version](https://img.shields.io/badge/Version-1.2.3-brightgreen)
<!-- Add build status badge if CI is set up -->
<!-- [![Build Status](https://img.shields.io/your_ci_badge_url)](your_ci_link) -->

A simple, multi-user FastAPI backend and responsive HTML/Tailwind CSS frontend application designed to provide a chat interface powered by the [`lollms-client`](https://github.com/ParisNeo/lollms-client) library, with integrated Retrieval-Augmented Generation (RAG) capabilities using [`safe_store`](https://github.com/ParisNeo/safe_store).

**Live Project:** [https://github.com/ParisNeo/simplified_lollms](https://github.com/ParisNeo/simplified_lollms)

## Overview

This project aims to provide a self-hostable, user-friendly chat interface that can connect to various Large Language Models (LLMs) supported by `lollms-client` (like Ollama, OpenAI, native LoLLMs). It features multi-user support with basic authentication, persistent discussions, RAG functionality for chatting with your documents, and an administrative interface for user management.

## ✨ Features

*   **Multi-User Support:** Secure login via HTTP Basic Authentication. Each user has their own isolated discussions and RAG document store.
*   **Persistent Discussions:** Chat histories are saved per user and can be revisited. Discussions are stored as YAML files.
*   **LLM Integration:** Uses `lollms-client` to interact with various LLM backends (configurable).
*   **Streaming Responses:** AI responses are streamed back to the user interface for a real-time experience.
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
*   **Data Export:** Users can export their discussions and SafeStore metadata as a JSON file.
*   **Responsive UI:** Clean interface built with Tailwind CSS, suitable for desktop and mobile.
*   **Dark/Light Theme:** Toggle between themes.
*   **Internationalization (i18n):** Basic support for English (`en`) and French (`fr`). Easily extensible.
*   **SQLite Backend:** User accounts and settings are stored in a central SQLite database (`app_main.db`). SafeStore uses its own SQLite DB per user (`vector_store.db`).

## 🏗️ Architecture

*   **Backend:** FastAPI (Python web framework)
*   **LLM Communication:** `lollms-client` library
*   **RAG/Vector Store:** `safe_store` library (SQLite based)
*   **User Database:** SQLAlchemy with SQLite
*   **Authentication:** HTTP Basic Auth + Passlib for password hashing
*   **Frontend:** Plain HTML, Tailwind CSS, Vanilla JavaScript (with Marked.js for Markdown rendering)
*   **Configuration:** TOML (`config.toml`)
*   **Discussion Storage:** YAML files per user
*   **Concurrency:** `filelock` used by `safe_store` for process-safe writes.

## 📸 Screenshots

*(Add screenshots of the login screen, main chat interface, settings modal, file manager, and admin panel here)*

**Login Screen:**
`![Login Screen](placeholder_login.png)`

**Main Chat UI:**
`![Chat UI](placeholder_chat.png)`

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
    # On Windows:
    # venv\Scripts\activate
    # On macOS/Linux:
    # source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(This installs FastAPI, Uvicorn, lollms-client, safe_store[all], SQLAlchemy, Passlib, and other necessary packages.)*

4.  **Configure the application:**
    *   Copy the example configuration file:
        ```bash
        cp config_example.toml config.toml
        ```
    *   **Edit `config.toml`:**
        *   **Crucially:** Change the `password` under `[initial_admin_user]` to a strong password. This will be the password for the first admin account (`superadmin` by default).
        *   Review `[lollms_client_defaults]` and set the appropriate `binding_name` (e.g., "ollama", "openai") and `default_model_name` based on your LLM setup. If using OpenAI or similar, set the `service_key_env_var` and ensure the corresponding environment variable (e.g., `OPENAI_API_KEY`) is set in your system.
        *   Review `[safe_store_defaults]`, especially `global_default_vectorizer` if you plan to use RAG heavily from the start.
        *   Adjust `[app_settings]` like `data_dir` or `database_url` if needed.
        *   Adjust `[server]` host/port if needed.

5.  **Run the application:**
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 9642
    ```
    *(Replace `0.0.0.0` with `127.0.0.1` if you only want local access. The default port is `9642` but can be changed in `config.toml`.)*

### Usage

1.  **Access the UI:** Open your web browser and navigate to `http://localhost:9642` (or the host/port you configured).
2.  **Login:** Use the initial admin credentials you set in `config.toml` (e.g., `superadmin` / `YourStrongPassword`).
3.  **Chat:**
    *   Click "New Discussion" to start.
    *   Select a discussion from the sidebar to continue.
    *   Type your message and press Enter or click the Send button.
    *   Use the "Use RAG" checkbox (visible if a vectorizer is active in Settings) to enable RAG for your next message.
4.  **Settings:**
    *   Click the "Settings" button in the sidebar.
    *   Change your preferred Language, default LLM Model, and active RAG Vectorizer.
    *   New vectorizers (e.g., `st:sentence-transformers/all-MiniLM-L6-v2` or `tfidf:my_custom_name`) can be entered in the text box.
5.  **RAG File Manager:**
    *   Click the "File Manager" button.
    *   Upload `.txt`, `.pdf`, `.docx`, `.html` files or entire folders. Files will be processed using the currently active RAG vectorizer.
    *   View and delete uploaded documents from the RAG store.
6.  **Admin Panel (Admins Only):**
    *   Navigate to `http://localhost:9642/admin`.
    *   Log in with admin credentials if prompted again.
    *   Add new users, view existing users, reset passwords, or delete users (cannot delete initial superadmin or self).
7.  **Data Export:**
    *   Click the "Export Data" button in the sidebar.
    *   Select the discussions you want to export (or use Select All/None).
    *   Click "Export Selected" to download a JSON file containing your selected discussions, current settings, and SafeStore metadata.

## ⚙️ Configuration (`config.toml`)

The `config.toml` file controls the application's behavior:

*   **`[app_settings]`**:
    *   `data_dir`: Directory to store user data (discussions, SafeStore DBs). Defaults to `"data"`.
    *   `database_url`: Connection string for the central user database. Defaults to `"sqlite:///./app_main.db"`.
    *   `secret_key`: Used for session security (future use).

*   **`[initial_admin_user]`**:
    *   `username`: Username for the first admin account created on startup if it doesn't exist.
    *   `password`: **Plain text password** for the initial admin. This is **hashed** on first startup. **Change this immediately.**

*   **`[lollms_client_defaults]`**: Global defaults for `lollms-client`. Users can override `default_model_name` in their settings.
    *   `binding_name`: e.g., `"ollama"`, `"openai"`, `"lollms"`.
    *   `default_model_name`: e.g., `"phi3:latest"`, `"gpt-4o-mini"`.
    *   `host_address`: URL for the LLM service (if not default).
    *   `service_key_env_var`: Environment variable name holding the API key (e.g., `"OPENAI_API_KEY"`).
    *   `ctx_size`, `user_name`, `ai_name`, `temperature`, `top_k`, `top_p`: Standard LLM parameters.

*   **`[safe_store_defaults]`**: Global defaults for `safe_store` (RAG). Users can override `global_default_vectorizer` in their settings.
    *   `chunk_size`, `chunk_overlap`: Parameters for splitting documents.
    *   `global_default_vectorizer`: Default vectorizer (e.g., `"st:all-MiniLM-L6-v2"`).
    *   `encryption_key`: Password to encrypt RAG document text at rest. Requires `safe_store[encryption]`. If `null` or missing, encryption is disabled. **Manage this key securely!**

*   **`[server]`**:
    *   `host`: Host address to bind the server to. Defaults to `"127.0.0.1"`. Use `"0.0.0.0"` for network access.
    *   `port`: Port number for the server. Defaults to `9642`.

## 📚 API Documentation

FastAPI automatically generates interactive API documentation. Once the server is running, you can access it at:

*   **Swagger UI:** `http://localhost:9642/docs`
*   **ReDoc:** `http://localhost:9642/redoc`

## 📁 Folder Structure

```text
📁 simplified_lollms/
├─ 📁 data/                  # User data (created automatically)
│  ├─ 📁 user1/
│  │  ├─ 📁 discussions/     # User1's discussion YAML files
│  │  ├─ 📁 safestore_documents/ # User1's uploaded RAG documents
│  │  └─ 📄 vector_store.db  # User1's SafeStore DB
│  └─ 📁 superadmin/         # Example admin user data
│     └─ ...
├─ 📁 locales/               # Translation files
│  ├─ 📄 en.json
│  └─ 📄 fr.json
├─ 📄 .gitignore
├─ 📄 admin.html             # Admin panel UI
├─ 📄 config.toml            # Main application configuration (user creates from example)
├─ 📄 config_example.toml    # Example configuration file
├─ 📄 database_setup.py      # SQLAlchemy models and DB setup
├─ 📄 index.html             # Main chat UI
├─ 📄 LICENSE                # Apache 2.0 License file
├─ 📄 LOLLMS_CLIENT_DOC.md   # Included documentation for lollms-client dependency
├─ 📄 main.py                # FastAPI application core logic and endpoints
├─ 📄 README.md              # This file
├─ 📄 requirements.txt       # Python dependencies
└─ 📄 SAFESTORE_DOC.md       # Included documentation for safe_store dependency
```

## 🤝 Contributing

Contributions are welcome! Please feel free to:

*   Report bugs or suggest features by opening an issue.
*   Submit pull requests with improvements or fixes.

Please try to follow existing code style and add tests if applicable.

## 📜 License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.