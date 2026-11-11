# 📡 LoLLMS API Documentation

High-level index of the LoLLMS HTTP API surface, organized by modality and target audience.

| Document | Modality | Audience |
| --- | --- | --- |
| [VIDEO_GENERATION_API.md](./VIDEO_GENERATION_API.md) | Text-to-Video (vLLM-Omni compatible) | Integrators, benchmark scripts, film/animation pipelines |

---

## Quick Reference — Base URLs

| Surface | Prefix | Env flag |
| --- | --- | --- |
| LoLLMS exclusive services | `/lollms/v1` | `lollms_services_enabled` |
| OpenAI compatibility layer | `/v1` | `openai_api_service_enabled` |
| Ollama compatibility layer | `/api` | `ollama_api_service_enabled` |
| Internal UI/WebUI API | `/api/...` | n/a |

Authentication is via `Authorization: Bearer <api_key>` for the service endpoints. API keys can be created from the LoLLMS WebUI (`Settings → API Keys`).

---

## Modalities Exposed

| Modality | Endpoint family | Availability gate |
| --- | --- | --- |
| Chat / Completions | `/v1/chat/completions`, `/lollms/v1/...` | Active **LLM** binding |
| Text-to-Image (TTI) | `/v1/images/generations`, `/lollms/v1/images/edit` | Active **TTI** binding |
| Speech-to-Text (STT) | `/v1/audio/transcriptions`, `/lollms/v1/audio/transcriptions` | Active **STT** binding |
| Text-to-Speech (TTS) | `/v1/audio/speech`, `/lollms/v1/audio/speech` | Active **TTS** binding |
| Text-to-Music (TTM) | `/lollms/v1/audio/music` | Active **TTM** binding |
| **Text-to-Video (TTV)** | `/lollms/v1/videos`, `/lollms/v1/videos/sync` | Active **TTV** binding |
| Embeddings | `/v1/embeddings` | Active **LLM** binding with embedding support |
| RAG / Datastores | `/lollms/v1/rag/...` | Active **RAG** vectorizer |

The `GET /lollms/v1/capabilities` endpoint is the authoritative server-side capability probe — always call it first when integrating.

---

## Adding New Documentation

When a new endpoint family is added:

1. Create a new `<MODALITY>_API.md` file in this folder.
2. Register it in the table above with a modality + audience hint.
3. Follow the structure of `VIDEO_GENERATION_API.md`: overview → auth → capability gating → endpoint reference → recipes → error handling → end-to-end example.

---

## See Also

- [`../markdown/tools/LOLLMS_CLIENT_DOC.md`](../markdown/tools/LOLLMS_CLIENT_DOC.md) — Python client (`LollmsClient`) binding guide.
- [`../markdown/tools/Simplified_lollms_api_documentation.md`](../markdown/tools/Simplified_lollms_api_documentation.md) — Legacy comprehensive API reference.
- [`../../backend/routers/services/README.md`](../../backend/routers/services/README.md) — Service router internals.