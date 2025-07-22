# Expert User Documentation: Mastering LoLLMs Chat

You've reached the expert level! This comprehensive guide covers advanced administration, customization, and integration features of LoLLMs Chat, designed for power users and administrators.

---

## 1. Administrator Panel Overview

If you possess administrator privileges, the Admin Panel (`/admin`) is your central hub for managing the entire LoLLMs instance, its users, and its core functionalities.

### Accessing the Admin Panel:

1.  Click on your **user icon / username** in the bottom-left of the sidebar.
    *   *(Imagine an image here: A screenshot showing the user icon in the sidebar.)*
2.  Select **"Admin Panel"** from the pop-up menu.
    *   *(Imagine an image here: A screenshot of the user menu with "Admin Panel" highlighted.)*

### Key Sections of the Admin Panel:

*   **Dashboard:** Provides vital statistics on your application's usage:
    *   Total Users
    *   Active Users (last 24h)
    *   New Users (last 7 days)
    *   Pending Registrations (if admin approval is enabled)
    *   Pending Password Resets
    *   *(Imagine an image here: A screenshot of the Admin Dashboard showing various user stats and a "Refresh" button.)*
*   **User Management:** Comprehensive control over user accounts:
    *   **Manage Users:** View a sortable and searchable list of all registered users. You can edit user details, toggle their `is_admin` status, activate/deactivate accounts, and delete them.
    *   **Force Settings:** Apply specific LLM (model, context size) or RAG (vectorizer) settings to multiple selected users, or even all users, at once. This is powerful for enforcing defaults or migration.
    *   **Email Users:** Send direct emails to individual or selected groups of users (requires SMTP configuration). You can even use AI to help enhance your email content.
    *   *(Imagine an image here: A screenshot of the User Management table with options for editing, activating, and deleting users.)*
*   **LLM Bindings:** Configure connections to various AI inference engines:
    *   **Add/Edit Bindings:** Set up connections to local models (e.g., Llama.cpp, private Ollama instances) or remote services (e.g., OpenAI-compatible APIs).
    *   Specify `Host Address`, `Models Path`, `Service API Key`, `Default Model Name`, and toggle `Active` status.
    *   *(Imagine an image here: A screenshot of the LLM Bindings table showing different configured bindings.)*
*   **Services:** Manage various external integrations and core API features:
    *   **MCP Servers (Multi-Computer Protocol):** Configure connections to external tool servers. MCPs enable advanced functionalities like web search, code interpretation, image generation, etc., through plugins.
        *   You can add `user-defined` (personal) or `system-wide` MCPs.
    *   **Applications:** Manage general web applications that can be integrated into LoLLMs.
    *   **OpenAI-Compatible API:** Enable or disable the built-in OpenAI API endpoint. When enabled, users can generate API keys to interact with your LoLLMs instance using external tools designed for OpenAI.
    *   *(Imagine an image here: A screenshot of the Services tab, showing lists of MCPs and Apps.)*
*   **Apps Management:** A dedicated section for managing installable LoLLMs applications:
    *   **App Zoo Repositories:** Add and pull external "App Zoo" repositories (Git URLs). These repositories contain a collection of ready-to-install LoLLMs applications.
    *   **Available Apps:** Browse apps discovered from your configured repositories. View details (description, author, version) and initiate installation.
    *   **Installed Apps:** Manage applications already installed on your server. You can start, stop, uninstall, view their logs, and configure their port/autostart settings.
    *   *(Imagine an image here: A screenshot of the Apps Management section, showing repository list and available apps.)*
*   **Global Settings:** Control application-wide defaults and behaviors:
    *   `Host` and `Port` for the main server.
    *   `HTTPS` configuration (SSL certificate and key paths).
    *   `allow_new_registrations` and `registration_mode` (direct vs. admin approval).
    *   `access_token_expire_minutes`
    *   `password_recovery_mode` (manual, SMTP, system mail).
    *   Default `LLM Model`, `Context Size`, `Temperature`, and `Vectorizer` for new users.
    *   Global `LLM Overrides` (force a specific model/context size on all users).
    *   *(Imagine an image here: A screenshot of the Global Settings form.)*
*   **Email Settings:** Detailed configuration for how the server sends emails (SMTP host, port, credentials, TLS).
*   **Import Tools:** Utility to import user data and discussions from other compatible platforms (e.g., Open-WebUI) by uploading their database files.
*   **Tasks:** Monitor and manage all long-running background processes initiated by the server (e.g., app installations, repository pulls, email sending, RAG revectorization).
    *   View status, progress, and detailed logs for each task. You can also cancel running tasks.
    *   *(Imagine an image here: A screenshot of the Task Manager showing task progress and logs.)*

---

## 2. LLM Bindings: Connecting to AI Models

LLM Bindings are the bridge between LoLLMs Chat and the actual AI models. They define how LoLLMs communicates with your chosen AI backend.

### Understanding Bindings:

*   **Local Bindings (e.g., Llama.cpp, Exllama, GPTQForLLaMa):** These bindings communicate with AI models stored directly on your server's file system. You'll specify a `models_path`.
*   **Remote Bindings (e.g., Ollama, OpenAI, Azure OpenAI):** These bindings connect to AI services running elsewhere, either locally on another port or on a remote server. You'll specify a `host_address`.

### Key Configuration Points:

*   **Alias:** A user-friendly name for your binding (e.g., "local_ollama", "my_gpt_api").
*   **Name:** The specific type of binding (e.g., `ollama`, `llama_cpp`, `openai`). This determines which underlying library LoLLMs uses.
*   **Host Address:** The URL/IP and port of the AI server (e.g., `http://localhost:11434` for Ollama).
*   **Models Path:** The local file system path where your models are stored (e.g., `/home/user/models/llama_cpp`).
*   **Service Key:** API key for commercial services like OpenAI or custom authenticated endpoints.
*   **Default Model Name:** The specific model within this binding that should be used by default (e.g., `llama3:8b`, `gpt-4o-mini`).
*   **Verify SSL Certificate:** Important for security when connecting to remote HTTPS endpoints. Set to `false` only if you know your server uses self-signed certificates or you are on a private, trusted network.
*   **Is Active:** Toggle to enable/disable a binding without deleting its configuration. Inactive bindings and their models will not be available to users.

### Best Practices:

*   **Separate Bindings:** Use different bindings for different model types or services, even if they run on the same host (e.g., one for local Ollama, another for a remote OpenAI API).
*   **Testing:** After configuring a new binding, try setting it as your default model in your user settings and initiating a new chat to confirm it's working.
*   **Restart Required:** Changes to LLM Bindings (especially host/path) often require a server restart to take full effect.

---

## 3. Integrating External Services (MCPs & Apps)

LoLLMs can integrate with external tools and applications to extend its capabilities.

### Multi-Computer Protocol (MCP) Servers:

MCPs are specialized servers that expose "tools" (functions) that your AI can call to perform actions or access real-world information.

*   **Examples:** A web search tool, a code execution environment, an image generation API.
*   **Configuration:**
    *   **Name & URL:** A unique name and the endpoint URL for the MCP server.
    *   **Authentication:** MCPs can use various authentication types (`None`, `Bearer Token`, `LoLLMs Chat Auth`, `LoLLMs SSO`). `LoLLMs Chat Auth` is often simplest as it leverages the user's existing LoLLMs session.
    *   **Discovering Tools:** Once an MCP is configured and active, LoLLMs will automatically discover the tools it provides. These tools can then be enabled in individual discussions via "Discussion Settings" (`/chat > wrench icon`).
    *   *(Imagine an image here: A screenshot of MCP settings showing authentication options.)*
*   **Reload MCPs:** After adding or updating MCP servers, click the "Reload All Servers" button (in **Settings > Services > MCP Servers** or **Admin Panel > Services > MCP Servers**) to force LoLLMs to refresh its connection and re-discover tools. This is essential for newly added MCPs to appear.

### Integrated Applications (Apps):

Beyond MCPs, you can add general web applications into your LoLLMs interface, allowing users to access them directly from the user menu.

*   **Types:** Can be simple web links or more complex applications with SSO integration.
*   **Configuration:** Similar to MCPs, you define a `Name`, `URL`, `Icon`, and `Authentication Type`.
*   **SSO (Single Sign-On):** For a seamless user experience, apps can be configured to use LoLLMs SSO. This allows users to log into LoLLMs once and then be automatically authenticated into the integrated app.
    *   **SSO Redirect URI:** The specific endpoint on your app where LoLLMs will redirect after successful authentication.
    *   **User Info to Share:** Select which user data (email, name, etc.) LoLLMs should send to the app during SSO.
    *   **SSO Secret:** A shared secret key used to secure the SSO communication between LoLLMs and your app. You can generate or regenerate this secret.
    *   *(Imagine an image here: A screenshot of the SSO configuration options for an App.)*

---

## 4. The App Zoo: Installing New Applications

The App Zoo (`/admin?tab=apps`) provides a curated collection of installable applications that extend the functionality of your LoLLMs instance.

### App Zoo Repositories:

*   **Adding Repositories:** Add Git URLs of App Zoo repositories to your instance. These repositories act as sources for discoverable applications.
*   **Pulling Repositories:** Periodically "pull" (refresh) repositories to get the latest list of available applications and updates. You can pull individual repositories or all at once.

### Installing and Managing Apps:

*   **Available Apps:** Browse apps from all configured and pulled repositories. Each app has a `description.yaml` that defines its metadata (description, author, version, etc.).
*   **Installation:**
    *   Select an app and click "Install." You'll choose a `Port` for the app to run on and whether it should `Autostart` with the LoLLMs server.
    *   Installation involves: copying files, creating a Python virtual environment, installing dependencies (from `requirements.txt`), and starting the app.
    *   Installation is a background task; monitor its progress in the **Admin Panel > Tasks** section.
    *   *(Imagine an image here: A screenshot of the App Installation modal.)*
*   **Installed Apps:** View and manage your installed applications:
    *   **Status:** See if an app is `running`, `stopped`, or in `error` state.
    *   **Start/Stop:** Manually control the running state of an app.
    *   **Logs:** View the application's logs for debugging.
    *   **Uninstall:** Remove an installed app, which deletes its files and virtual environment.
    *   **Update:** If a newer version is available in the zoo, an "Update" button will appear.

---

## 5. User & System Settings

Beyond the Admin Panel, certain settings are accessible from user profiles (`/settings`) that impact individual user experience or global system behavior.

### General Settings (`/settings?tab=general`):

*   **UI Level:** Adjusts the complexity of the user interface, showing more or fewer advanced options.
*   **Default Home Page:** Sets the first view after login (Social Feed, Discussions, New Discussion, Last Discussion).
*   **AI Response Language:** Instructs the AI to respond in a specific language by default.
*   **Auto Generate Discussion Titles:** Automatically creates a title for new discussions.
*   **Show Token Counter:** Displays token usage in the chat input.
*   **Fun Mode:** Enables more playful AI responses.
*   **Include AI Thoughts in Context:** (Advanced) Determines if the AI's internal "thought" process is sent back into the context for the next turn.

### LLM Configuration (`/settings?tab=llm`):

*   Allows individual users to set their preferred default model and generation parameters (Temperature, Top K, Top P, etc.), unless a global override is active.

### RAG Parameters (`/settings?tab=rag`):

*   Users can customize how RAG works for them:
    *   `RAG Top K`: Number of top-matching document chunks to retrieve.
    *   `Max RAG Length`: Maximum characters of retrieved content to include.
    *   `RAG N Hops`: Number of iterative RAG steps.
    *   `RAG Min Similarity %`: Minimum similarity score for a chunk.
    *   `Use Graph for RAG`: Leverage knowledge graphs for RAG.

---

## 6. API Key Management (OpenAI Compatibility)

The LoLLMs backend can act as an OpenAI-compatible API endpoint, allowing you to use other applications (like custom scripts, IDE plugins, or other chat clients) with your LoLLMs models.

### Accessing API Keys:

1.  Go to **Settings** (via your user menu).
2.  Select the **"API Keys"** tab.
    *   *(Imagine an image here: A screenshot of the API Keys settings page.)*

### How to Use:

*   **Generate New Key:** Provide an `Alias` (a descriptive name for your key) and click "Create New Key."
*   **Copy the Key:** The full API key will be displayed *only once*. Copy it immediately.
*   **Use in External Apps:** In your external application, configure the API endpoint to point to your LoLLMs server's `/v1` endpoint (e.g., `http://your-lollms-ip:9642/v1`) and use the generated key.

---

## 7. Troubleshooting & Maintenance

### Common Issues & Solutions:

*   **AI doesn't respond/gives errors:**
    *   **Check LLM Binding:** Ensure your chosen LLM Binding in **Admin Panel > LLM Bindings** (or your user settings) is active and its `Host Address` and `Models Path` (if applicable) are correct.
    *   **Check Model Name:** Confirm the `Default Model Name` in the binding matches an actual model available on that server.
    *   **Server Logs:** Check the console where your LoLLMs server is running for error messages.
    *   **Restart Server:** Sometimes, a full server restart resolves underlying issues.
*   **Installed App won't start:**
    *   **Check Port:** Ensure the app's configured port is not in use by another application. Verify in **Admin Panel > Apps Management**.
    *   **View App Logs:** Use the "View App Logs" button in **Admin Panel > Apps Management** to see startup errors.
    *   **Dependencies:** Confirm the app's `requirements.txt` was installed correctly.
*   **RAG not working:**
    *   **SafeStore Installed:** Ensure the `safe_store` library is installed on your server (`pip install safe_store[all]`).
    *   **Data Store Status:** Check that the data store itself is accessible and contains documents.
    *   **Vectorizer:** Verify the vectorizer used by the data store is correct and the necessary models (for sentence transformers, etc.) are downloaded.
*   **Email not sending:**
    *   **Email Settings:** Double-check your SMTP configuration (host, port, username, password, TLS) in **Admin Panel > Email Settings**.
    *   **Firewall:** Ensure your server's firewall allows outgoing connections on the SMTP port.

### Maintenance Tasks:

*   **Purge Unused Uploads:** In **Admin Panel > Import Tools**, click "Start Purge Task" to delete old temporary files, freeing up disk space.
*   **Clear Completed Tasks:** In **Admin Panel > Tasks**, remove old completed/failed task entries to keep the task list clean.
*   **Regular Repository Pulls:** For App Zoo and potentially other repositories, regularly pull updates to get new apps or bug fixes.

---

**Remember:** The `user_ui_level` setting in your `General Settings` tab (`/settings`) controls how much detail and how many advanced options are visible in the interface. Adjust this to match your comfort level.

This comprehensive guide should provide you with all the knowledge needed to manage and utilize LoLLMs Chat effectively!