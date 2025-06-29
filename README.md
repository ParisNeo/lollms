# Simplified LoLLMs Chat

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
![Version](https://img.shields.io/badge/Version-1.6.0-brightgreen) <!-- Updated Version -->
<!-- Add build status badge if CI is set up -->
<!-- [![Build Status](https://img.shields.io/your_ci_badge_url)](your_ci_link) -->

A multi-user FastAPI backend and responsive HTML/Tailwind CSS frontend application designed to provide a chat interface powered by the [`lollms-client`](https://github.com/ParisNeo/lollms-client) library. It features integrated Retrieval-Augmented Generation (RAG) using [`safe_store`](https://github.com/ParisNeo/safe_store), multimodal chat, user personalities, a friend system, direct messaging, and enhanced sharing capabilities.

**Live Project:** [https://github.com/ParisNeo/lollms_chat](https://github.com/ParisNeo/lollms_chat)

## Overview

This project aims to provide a self-hostable, user-friendly chat interface that can connect to various Large Language Models (LLMs) supported by `lollms-client`. It features multi-user support with basic authentication, persistent discussions, RAG functionality, multimodal chat (image input), customizable user personalities, a friend system with direct messaging, administrative user management, and sharing of datastores and personalities.

## ✨ Features

*   **Multi-User Support:** Secure login via Token based authentication. Each user has their own isolated data.
*   **Persistent Discussions:** Chat histories are saved per user (YAML files) and can be revisited, renamed, starred, and deleted.
*   **LLM Integration:** Uses `lollms-client` to interact with various LLM backends.
*   **Streaming Responses:** AI responses are streamed for a real-time experience.
*   **Multimodal Chat:** Upload images with text prompts for vision-capable models.
*   **User Personalities (System Prompts):**
    *   Create, edit, and delete custom personalities (system prompts with name, category, author, icon, etc.).
    *   Select an active personality to guide LLM responses.
    *   View and use public (system-provided) personalities.
    *   Share (send a copy of) owned personalities with friends.
*   **Retrieval-Augmented Generation (RAG):**
    *   Multiple **DataStores** per user for organizing RAG documents.
    *   Upload documents (`.txt`, `.pdf`, `.docx`, `.html`, etc.) to specific DataStores.
    *   Toggle RAG usage per discussion, selecting a specific DataStore.
    *   Manage DataStores (create, rename, delete) and their indexed documents.
    *   **Share DataStores with friends** (read-only query access).
*   **Friend System & Direct Messaging (DM):**
    *   Send, accept, and reject friend requests.
    *   View friends list and manage friendships (unfriend, block/unblock - *block/unblock WIP*).
    *   **Send and receive direct messages** with accepted friends.
    *   View conversation history with friends.
*   **Configurable Settings:**
    *   Users can set their default LLM model, RAG vectorizer, LLM generation parameters (temperature, top_k, etc.), RAG parameters, and personal profile information.
*   **Admin Panel:**
    *   Manage users (Add, List, Delete, Reset Password).
    *   Initial superadmin user created from `config.toml`.
*   **Data Export/Import:** Users can export/import their discussions, settings, and metadata.
*   **Responsive UI:** Built with Tailwind CSS, including image previews, Markdown rendering with code highlighting (Highlight.js) and math (KaTeX).
*   **Dark/Light Theme & Internationalization (i18n).**
*   **SQLite Backend:** Central database for users, settings, personalities, friendships, DMs. SafeStore uses its own DBs per DataStore.

## 🏗️ Architecture

*   **Backend:** FastAPI (Python)
*   **LLM Communication:** `lollms-client`
*   **RAG/Vector Store:** `safe_store` (SQLite based per DataStore)
*   **Main Database:** SQLAlchemy with SQLite (users, personalities, friendships, DMs, etc.)
*   **Authentication:** HTTP Basic Auth + Passlib
*   **Frontend:** HTML, Tailwind CSS, Vanilla JavaScript
*   **Configuration:** TOML (`config.toml`)
*   **Discussion Storage:** YAML files per user

## 📸 Screenshots

*(Add updated screenshots showing the new Friends & Messages modal, DM interface, personality editor, and sharing options)*

**Login Screen:**
`![Login Screen](placeholder_login.png)`

**Main Chat UI (with Personality Selector & RAG):**
`![Chat UI](placeholder_chat_main.png)`

**Friends & Messages Modal:**
`![Friends & Messages Modal](placeholder_friends_dm.png)`

**Personality Editor Modal:**
`![Personality Editor](placeholder_personality_editor.png)`

**Settings Modal (User Profile, LLM/RAG Params):**
`![Settings Modal](placeholder_settings_new.png)`

**DataStore Management & Sharing:**
`![DataStore Management](placeholder_datastore_manage.png)`

**Admin Panel:**
`![Admin Panel](placeholder_admin.png)`

## 🚀 Getting Started

### Prerequisites

*   Python 3.8+
*   Git, Pip
*   An LLM backend accessible via `lollms-client`.

### Installation

1.  **Clone:**
    ```bash
    git clone https://github.com/ParisNeo/lollms_chat.git
    cd lollms_chat
    ```
2.  **Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # Windows: venv\Scripts\activate
    # macOS/Linux: source venv/bin/activate
    ```
3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure `config.toml`:**
    *   Copy `config_example.toml` to `config.toml`.
    *   **Crucially:** Change `password` under `[initial_admin_user]`.
    *   Set `binding_name` and `default_model_name` in `[lollms_client_defaults]`.
    *   Review other settings.
5.  **Run:**
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 9642
    ```

### Usage

1.  **Access UI:** `http://localhost:9642`
2.  **Login:** Use initial admin or created user credentials.
3.  **Chat:** Create/select discussions, use RAG, upload images.
4.  **Personalities:** Manage and select active personalities via Settings.
5.  **Friends & DMs:** Access via user menu to manage friends and send messages.
6.  **DataStores:** Manage RAG DataStores and share them via user menu.
7.  **Settings:** Configure user profile, LLM/RAG parameters, active personality.
8.  **Admin Panel:** `/admin` for user management (admins only).

## ⚙️ Configuration (`config.toml`)

*   **`[app_settings]`**: `data_dir`, `database_url`.
*   **`[initial_admin_user]`**: `username`, `password`, optional `first_name`, `email`.
*   **`[lollms_client_defaults]`**: `binding_name`, `default_model_name`, LLM parameters, `put_thoughts_in_context`.
*   **`[safe_store_defaults]`**: RAG chunking, `global_default_vectorizer`.
*   **`[server]`**: `host`, `port`.

## 📚 API Documentation

*   **Swagger UI:** `http://localhost:9642/docs`
*   **ReDoc:** `http://localhost:9642/redoc`

## 📁 Folder Structure

```text
📁 lollms_chat/
├─ 📁 data/                  # User data, DBs (created automatically)
│  ├─ 📄 app_main.db         # Central SQLite DB
│  └─ 📁 <username>/         # Per-user data
│     ├─ 📁 discussions/
│     ├─ 📁 discussion_assets/
│     ├─ 📁 safestores/       # RAG DataStore DBs
│     └─ 📁 temp_uploads/
├─ 📁 locales/               # i18n JSON files
├─ 📄 .gitignore
├─ 📄 admin.html
├─ 📄 config.toml
├─ 📄 config_example.toml
├─ 📄 database_setup.py      # SQLAlchemy models & DB init
├─ 📄 index.html             # Main chat UI
├─ 📄 LICENSE
├─ 📄 main.js                # Frontend JavaScript
├─ 📄 main.py                # FastAPI application
├─ 📄 README.md              # This file
├─ 📄 requirements.txt
└─ 📄 style.css              # Custom CSS
```

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## 📜 License

Apache License 2.0. See [LICENSE](LICENSE).