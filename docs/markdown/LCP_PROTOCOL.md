# 🧊 Lollms Communication Protocol (LCP) v1.0

## 1. Overview
The Lollms Communication Protocol (LCP) defines the interaction contract between a **Smart Chat Agent** (Backend/Library) and a **Client Application** (Frontend). It is designed to support complex, multi-step agentic workflows while maintaining a clean, human-readable chat interface.

## 2. Operational Modes

### 2.1 Non-Streaming Mode
The agent processes the entire request and returns a final `LollmsMessage` object containing the complete content, metadata, and any affected artefacts.

### 2.2 Streaming Mode (Real-time)
Content is delivered as a series of typed packets via WebSockets or Server-Sent Events (SSE). 
- **Standard Text**: Delivered via `MSG_TYPE_CHUNK` (0).
- **Internal Operations**: Intercepted by the agent's state machine.
- **Secondary Streams**: Dedicated channels for raw data building (Artefacts, Widgets).

---

## 3. The Interception Contract (Streaming)

LCP enforces a strict distinction between **Internal Storage** (Artefacts) and **External Rendering** (UI Components).

### 3.1 Intercepted Tags (Summary Only)
The following tags are captured by the Agent. Their raw content is **NEVER** sent to the app via the main text stream.
- `<artifact>` / `<artefact>`
- `<note>`
- `<skill>`

**Protocol behavior:**
1. Upon detection of a tag opening, the agent emits `<processing type="..." title="...">` via `MSG_TYPE_CHUNK`.
2. While the LLM generates the content, the agent sends status updates (e.g., `* Creating file...`) inside the processing block.
3. When the tag closes, the agent processes the content (versioning, patching, or saving), emits a final status, and closes the `</processing>` tag.
4. **The UI never receives the raw code/text of these items in the chat bubble.**

### 3.2 Passthrough Tags (Full Rendering)
The following tags are intended for direct user interaction and are **passed through** to the application once fully buffered/validated:
- `<lollms_inline type="html">`: Interactive widgets.
- `<lollms_form>`: Structured data gathering forms.

**Protocol behavior:**
1. These tags are buffered internally to ensure validity.
2. Once the tag is closed, the **complete validated XML tag** is injected into the `MSG_TYPE_CHUNK` stream.
3. The frontend is responsible for mounting and rendering these components.

---

## 4. Message Types (`MSG_TYPE`)

| ID | Name | Description |
|----|------|-------------|
| 0 | `MSG_TYPE_CHUNK` | Standard visible text or passthrough UI tags. |
| 8 | `MSG_TYPE_INFO` | Out-of-band information (e.g., Memory updates). |
| 28 | `MSG_TYPE_INIT_PROGRESS` | Initialization status. |
| 29 | `MSG_TYPE_ARTEFACTS_STATE_CHANGED` | Notification that an internal artefact was modified. |
| 38-45 | `MSG_TYPE_*_CHUNK/DONE` | Secondary raw content streams for background sync. |
| 46 | `MSG_TYPE_FORM_READY` | Form descriptor is ready for rendering. |

---

## 5. Memory System
Memory operations are performed by the agent but reported to the UI for transparency:
- `<mem_tag>`, `<mem_new>`, `<mem_update>`, `<mem_delete>`.
- The agent strips these from the final message.
- A report is sent via `MSG_TYPE_INFO` with `meta: { type: "memory_update" }`.

---

## 6. Extensibility
Applications may inject custom instructions into the `LollmsDiscussion.system_prompt`. The agent will treat any unknown tag according to the **Standard Buffer Rule**:
- If the tag is not in the "Intercept" list, it is treated as text and flushed to the UI after validation.