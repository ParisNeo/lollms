# Administrator Documentation

Welcome to the **LoLLMs Admin Panel**. This guide covers the advanced tools and settings available to administrators for managing the server, users, and AI infrastructure.

## 1. Dashboard Overview

The revamped Dashboard provides a real-time command center for your LoLLMs instance.

### Key Metrics
*   **Total Users**: The count of all registered accounts.
*   **Active (24h)**: Users who have interacted with the system in the last 24 hours.
*   **Pending Approval**: If "Admin Approval" registration mode is on, this shows how many users are waiting for activation. Click the card to open the approval manager.

### System Health
*   **Global Activity**: A chart showing AI generation usage over time.
*   **Hardware Status**:
    *   **CPU & RAM**: Monitor system load.
    *   **Disks**: Visual indicators for "Code" (application) and "Data" (user files) storage drives.
    *   **GPU Monitoring**: For NVIDIA GPUs, view VRAM usage, Compute Load, and a list of active processes. You can terminate stuck processes directly from the dashboard.

### Quick Actions
*   **Secure Backup**: Creates an AES-encrypted ZIP archive of your entire `data/` folder. You must provide a password for encryption.
*   **Purge Temp Files**: Frees up disk space by deleting temporary uploads and generated assets older than 24 hours.
*   **Broadcast**: Send a system-wide popup message to all currently connected users.

### Log Analysis
An AI-powered diagnostic tool. Click **"Analyze Logs"** to have the system's default LLM scan recent error logs and generate a report with potential root causes and recommended fixes.

---

## 2. Server Configuration

Located under **Settings > Server Settings**.

### Connectivity
*   **Host/Port**: Define the listening address (e.g., `0.0.0.0` for network access) and port.
*   **HTTPS (SSL)**:
    *   **Generate**: Create a self-signed certificate instantly to secure your connection.
    *   **Upload**: Use your own `.pem` certificate and key files.
    *   **Download**: Download the active certificate for verification.

### User Access
*   **Registration Mode**:
    *   *Direct*: New users can log in immediately.
    *   *Admin Approval*: New accounts remain inactive until an admin approves them.
*   **Default Settings**: Set the default model, context size, and UI level for new users.

---

## 3. User Management

Located under the **Users** tab.

*   **User Table**: Search and filter users by status (Online, Active/Inactive).
*   **Edit User**: Promote users to Moderators/Admins, reset passwords, or change their allocated resources (e.g., context size limits).
*   **Batch Actions**: Select multiple users to send bulk emails or apply settings presets.

---

## 4. Models & Bindings

The core of LoLLMs is its bindings system.

*   **LLM Bindings**: Connect to text generation engines (Llama.cpp, Ollama, OpenAI, vLLM, etc.).
*   **TTI Bindings**: Configure Text-to-Image engines (Stable Diffusion, Flux, Dall-E).
*   **TTS/STT**: Configure Voice interaction services.
*   **RAG Bindings**: Manage Vectorizers for the retrieval-augmented generation system.

Use the **Zoos** tabs to download new models, personalities, or extensions directly from the central repository.
