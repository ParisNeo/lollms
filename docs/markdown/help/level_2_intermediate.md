# Intermediate User Guide: Unleash More Power

You've mastered the basics of LoLLMs Chat. Now, let's unlock more advanced features to customize your AI experience and make it even more powerful!

---

## 1. Advanced LLM Settings: Fine-Tuning AI Behavior

The way AI models generate responses can be precisely controlled using various parameters. Adjusting these can significantly impact creativity, coherence, and factual relevance.

### Accessing LLM Settings:

1.  Click on your **user icon / username** in the bottom-left of the sidebar.
    *   *(Imagine an image here: A screenshot showing the user icon in the sidebar.)*
2.  Select **"Settings"** from the pop-up menu.
    *   *(Imagine an image here: A screenshot of the user menu with "Settings" highlighted.)*
3.  Navigate to the **"LLM Configuration"** tab in the settings view.
    *   *(Imagine an image here: A screenshot of the settings page with "LLM Configuration" tab highlighted.)*

### Key LLM Parameters:

*   **Default LLM Model:**
    *   **What it does:** This sets the specific AI model you want to use by default for all new discussions. Models vary greatly in size, capability, and performance. Some are general-purpose, while others are optimized for specific tasks.
    *   **Recommendation:** Experiment with different models available to you. Models from `ollama/` are often good local choices.
    *   *(Imagine an image here: A screenshot of the model selection dropdown in LLM settings.)*
*   **Context Size (tokens):**
    *   **What it does:** Determines how much of the previous conversation (in "tokens," roughly words) the AI "remembers" or can see at any given time. A larger context size allows for longer, more coherent, and context-aware discussions.
    *   **Tip:** If the AI seems to "forget" earlier parts of your chat, increase this value. Be aware that larger contexts consume more computing resources and can slow down responses.
    *   *(Imagine an image here: A screenshot of the context size input field.)*
*   **Temperature:**
    *   **What it does:** Controls the randomness and "creativity" of the AI's responses.
        *   **Lower values (e.g., 0.1-0.5):** Produce more predictable, focused, and factual responses. Ideal for tasks requiring precision, like coding or data extraction.
        *   **Higher values (e.g., 0.7-1.0):** Lead to more creative, diverse, and sometimes surprising responses. Excellent for brainstorming, creative writing, or generating varied ideas.
    *   **Recommendation:** Start with a value around `0.7` and adjust based on whether you need more consistency or more originality.
    *   *(Imagine an image here: A screenshot of the temperature slider or input field.)*
*   **Top K:**
    *   **What it does:** The AI considers only the `K` most probable next tokens. A lower `K` restricts choices, making output more focused; a higher `K` offers more diversity.
*   **Top P:**
    *   **What it does:** The AI selects from the smallest set of most probable tokens whose cumulative probability exceeds `P`. A lower `P` makes responses more deterministic; a higher `P` allows for more exploration.
    *   **Tip:** `Top K` and `Top P` are often used together. Defaults (`50` and `0.95` respectively) are usually good starting points. Only adjust if you're experiencing specific issues with response quality or diversity.
*   **Repeat Penalty & Repeat Last N:**
    *   **What they do:** These parameters help prevent the AI from generating repetitive phrases, words, or ideas, which is common in unconstrained generation. `Repeat Last N` specifies how many recent tokens to consider for the penalty.
    *   **Tip:** If the AI gets stuck in loops or repeats itself frequently, slightly increase `Repeat Penalty` (e.g., to `1.15` or `1.2`).

---

## 2. Using Data Stores (RAG): AI with Your Knowledge

Retrieval-Augmented Generation (RAG) is a powerful feature that allows the AI to "read" and understand your own documents or data before generating its response. This is incredibly useful for improving factual accuracy and ensuring the AI can answer questions based on specific, private information.

### How RAG Works:

1.  **Create Data Stores:** Think of a data store as a private library for your AI. You can create multiple data stores for different topics or projects (e.g., "Project X Docs," "My Research Papers," "Company Policies").
2.  **Upload Documents:** You add various file types (PDFs, text files, markdown, code, etc.) to your data stores. The system processes and "vectorizes" them, which means it converts their content into a format that the AI can quickly search and understand for relevance.
3.  **Activate for Discussion:** In any specific discussion, you can choose which of your data stores the AI should "consult" when generating responses.

### Accessing and Managing Data Stores:

1.  From the main chat view, click your **user icon / username** in the bottom-left of the sidebar.
2.  Select **"Data Stores"** from the pop-up menu.
    *   *(Imagine an image here: A screenshot of the user menu with "Data Stores" highlighted.)*
3.  In the Data Stores view, you can:
    *   **Create New Data Store:** Give it a name and description.
    *   **Manage Files:** For each data store, you can upload new documents (`+ Upload Files`), view existing ones, or delete them.
    *   **Re-vectorize:** If you change your default vectorizer or if there are issues, you can re-process all documents in a store.
    *   **Share:** Share your data stores with other users, granting them read or read/write permissions.
    *   *(Imagine an image here: A screenshot of the Data Stores view showing options to create, manage files, and share.)*

### Using RAG in Your Discussions:

1.  While in any active discussion, look for the **RAG settings** (often an icon like a database or a document stack) in the chat header or discussion options.
    *   *(Imagine an image here: A screenshot of the chat header or discussion settings showing the RAG activation button/dropdown.)*
2.  Click on it to open a menu where you can:
    *   **Select Active Data Store(s):** Choose one or more of your data stores. The AI will now attempt to retrieve relevant information from these sources whenever you ask a question.
    *   **Configure RAG Parameters (via Settings):** You can adjust default RAG parameters like `RAG Top K` (how many relevant chunks to retrieve) or `RAG Min Similarity %` (how similar a chunk needs to be to be considered). These are found under **Settings > RAG Parameters**.
        *   *(Imagine an image here: A screenshot of the dropdown or modal for selecting active RAG data stores.)*

---

## 3. Managing Your Personalities

Beyond just selecting them, you can customize or even create your own AI personalities.

### Accessing Personality Settings:

1.  Go to **Settings** (via your user menu).
2.  Select the **"Personalities"** tab.
    *   *(Imagine an image here: A screenshot of the settings page with "Personalities" tab highlighted.)*

### Actions You Can Perform:

*   **Create New Personality:**
    *   Click the **"+ Create New"** button in the "Your Personalities" section.
    *   Fill in details like `Name`, `Category`, `Description`, and most importantly, the **`System Prompt`**. This prompt defines the core behavior and instructions for your AI.
    *   *(Imagine an image here: A screenshot of the Personality Editor modal.)*
*   **Edit Your Personalities:**
    *   For any personality listed under "Your Personalities," click the **"Edit"** button. You can modify its name, description, and prompt.
*   **Clone Public Personalities:**
    *   If you find a public personality you like but want to modify it, click **"Clone & Edit."** This creates a copy in your personal list that you can customize without affecting the original.
*   **Set Active Personality:**
    *   Click on any personality card to make it your active personality. This will affect new discussions you create. You can also deselect all to use the default AI behavior.
    *   *(Imagine an image here: A screenshot of a personality card being selected.)*

---

**Troubleshooting Tips for Intermediate Users:**

*   **Slow Responses:** If responses are slow, check your `Context Size` in LLM settings. Reduce it if you're not seeing specific context-related issues.
*   **AI misinterprets context:** Increase `Context Size` or ensure relevant RAG data stores are active.
*   **"Error" in response:** Check the server logs (if you have access) or try switching to a different LLM model or personality.

---

**What's Next?**

Practice adjusting these settings and integrating data stores and custom personalities into your workflow. As you become more comfortable, you'll find that LoLLMs Chat can become an even more indispensable tool for your tasks.