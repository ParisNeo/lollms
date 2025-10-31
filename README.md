# LoLLMs - v1.0.2 "Nebula"

One tool to rule them all!

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
![Version](https://img.shields.io/badge/Version-1.7.0-brightgreen)

A multi-user FastAPI backend and responsive Vue/Tailwind CSS frontend application designed to provide a chat interface powered by the [`lollms_client`](https://github.com/ParisNeo/lollms_client) library. It features integrated Retrieval-Augmented Generation (RAG) using [`safe_store`](https://github.com/ParisNeo/safe_store), a versatile personality system, multimodal chat, user management, a friend system with direct messaging, and enhanced sharing capabilities.

**Live Project:** [https://github.com/ParisNeo/lollms](https://github.com/ParisNeo/lollms)

## ✨ Features

*   **Multi-User Support:** Secure token-based authentication. Each user has their own isolated data.
*   **Simplified Installation:** Get started quickly with simple `run.sh` or `run_windows.bat` scripts.
*   **Environment-Based Configuration:** Easy setup using a `.env` file, automatically generated from `.env.example`.
*   **Persistent Discussions:** Chat histories are saved per user and can be revisited, renamed, starred, and deleted.
*   **LLM Integration:** Uses `lollms-client` to interact with various LLM backends.
*   **Streaming Responses:** AI responses are streamed for a real-time experience.
*   **Multimodal Chat:** Upload images with text prompts for vision-capable models.
*   **Advanced Personality System:** Create, edit, and delete custom personalities with unique system prompts, scripts, and data sources.
*   **Retrieval-Augmented Generation (RAG):**
    *   Organize documents into multiple **DataStores** per user.
    *   Upload various file types (`.txt`, `.pdf`, `.docx`, etc.).
    *   Toggle RAG usage per discussion and select specific DataStores.
    *   Share DataStores with friends with configurable permissions.
*   **Friend System & Direct Messaging (DM):**
    *   Send, accept, and reject friend requests.
    *   Engage in real-time direct messaging with friends.
*   **Admin Panel:**
    *   Manage users (Add, List, Delete, Reset Password).
    *   Configure global settings and manage LLM/TTI/TTS bindings.
*   **Data Export/Import:** Users can export/import their discussions and settings.
*   **Responsive UI:** Built with Vue.js and Tailwind CSS, featuring Markdown rendering, code highlighting, and math rendering with KaTeX.

## 🚀 Getting Started

### Prerequisites

*   Python 3.10+
*   Git

### Installation

The easiest way to get started is by using the provided run scripts, which handle setup and execution.

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/ParisNeo/lollms.git
    cd lollms
    ```

2.  **Run the Installer:**
    *   **On Windows:** Double-click `run_windows.bat`.
    *   **On macOS or Linux:**
        ```bash
        chmod +x run.sh
        ./run.sh
        ```
    The first time you run the script, it will create a Python virtual environment, install all required dependencies, and create a default `.env` file from `.env.example`. Subsequent runs will just start the application.

### Usage

1.  **Access the UI:** Once the server is running, open your web browser and go to `http://localhost:9642` (or the host and port you configured).
2.  **Create an Admin Account:** On the first launch, you will be prompted to create an administrator account.
3.  **Login:** Use your newly created credentials to log in.
4.  **Explore:**
    *   Start a new chat.
    *   Go to **Settings** to configure your profile and select an LLM model.
    *   Visit the **Admin Panel** to configure LLM bindings and other global settings.

## ⚙️ Configuration (`.env` file)

Configuration is managed through the `.env` file in the project's root directory. When you first run the application, this file is created for you from `.env.example`.

*   `SERVER_HOST` & `SERVER_PORT`: The host and port the application will run on.
*   `DATABASE_URL`: The location of the main SQLite database file.
*   `SECRET_KEY`: **Change this to a long, random string for production.**
*   `ALLOW_NEW_REGISTRATIONS`: Set to `false` to disable public sign-ups.
*   `INITIAL_ADMIN_USERNAME` & `INITIAL_ADMIN_PASSWORD`: Used on first startup if no admin exists.

For detailed information on all available settings, please refer to the comments within the `.env.example` file.

## 📚 API Documentation

*   **Swagger UI:** `http://localhost:9642/docs`
*   **ReDoc:** `http://localhost:9642/redoc`

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## 📜 License

Apache License 2.0. See [LICENSE](LICENSE).