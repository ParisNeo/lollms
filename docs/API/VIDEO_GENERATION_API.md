# 🎬 Video Generation API — vLLM-Omni Compatible Endpoints

LoLLMS exposes an OpenAI/vLLM-Omni compatible video generation API under `/lollms/v1/videos`. These endpoints support asynchronous job submission, status polling, MP4 content download, and a synchronous blocking mode — enabling clients built for vLLM-Omni diffusion servers (Wan2.2, MiniMax H3, LTX-2.5, Cosmos3, …) to interact with LoLLMS without code changes.

> **Endpoints only activate when at least one Text-to-Video (TTV) binding is configured and active** (`DBTTVBinding.is_active == True`). Requests otherwise return **`501 Not Implemented`**.

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Capability Gating](#2-capability-gating)
3. [Core Endpoints](#3-core-endpoints)
   - [POST /lollms/v1/videos — Async Submission](#31-post-lollmsv1videos--async-submission)
   - [GET /lollms/v1/videos/{video_id} — Poll Status](#32-get-lollmsv1videosvideo_id--poll-status)
   - [GET /lollms/v1/videos/{video_id}/content — Download MP4](#33-get-lollmsv1videosvideo_idcontent--download-mp4)
   - [POST /lollms/v1/videos/sync — Blocking Sync](#34-post-lollmsv1videossync--blocking-sync)
4. [Request Parameters](#4-request-parameters)
5. [Reference Fields](#5-reference-fields)
6. [API Recipes](#6-api-recipes)
   - [Text-to-Video (T2V)](#a-text-to-video-t2v)
   - [Image-to-Video / First Frame (I2V)](#b-image-to-video--first-frame-i2v)
   - [First-Last Frame Interpolation (FLF2V)](#c-first-last-frame-interpolation-flf2v)
   - [Video Editing & Inpainting](#d-video-editing--inpainting)
   - [Lip-Sync / Audio-Driven](#e-lip-sync--audio-driven)
7. [Job States & Error Handling](#7-job-states--error-handling)
8. [Concurrency & Storage](#8-concurrency--storage)
9. [End-to-End Workflow](#9-end-to-end-workflow)
10. [Integration Examples](#10-integration-examples)

---

## 1. Authentication

All endpoints require an API key via `Authorization: Bearer <key>` unless the server administrator has disabled key enforcement (`lollms_services_require_key=false`).

```bash
curl -H "Authorization: Bearer <your_api_key>" \
     http://localhost:9600/lollms/v1/capabilities
```

Rate limiting is applied per-key, and usage is tracked per user.

---

## 2. Capability Gating

Before describing the video endpoints, verify the server has a TTV binding active:

```bash
curl -s -H "Authorization: Bearer $LOLLMS_KEY" \
     http://localhost:9600/lollms/v1/capabilities | jq
```

Expected response includes:

```json
{
  "capabilities": [
    "tokenize",
    "detokenize",
    "long_context_processing",
    "text_to_video",
    "image_to_video",
    "video_generation_jobs"
  ],
  "active_bindings": {
    "ttv": ["vllm_omni", "diffusers"]
  }
}
```

If `"ttv"` is empty or missing, video endpoints will return **`501`**.

---

## 3. Core Endpoints

### 3.1 `POST /lollms/v1/videos` — Async Submission

Submit an asynchronous video generation job. Returns a `202 Accepted` response with a job descriptor containing an `id`.

**Content Types accepted:** `application/json` **or** `multipart/form-data` (matching the vLLM-Omni reference).

```bash
curl -s -X POST http://localhost:9600/lollms/v1/videos \
  -H "Authorization: Bearer $LOLLMS_KEY" \
  -F "prompt=A cinematic tracking shot of a mountain lake at sunrise" \
  -F "width=1280" \
  -F "height=720" \
  -F "num_frames=80" \
  -F "fps=16" \
  -F "num_inference_steps=40"
```

**Response (`202`):**

```json
{
  "id": "vid_abc123xyz",
  "object": "video.job",
  "status": "queued",
  "created_at": 1773360000,
  "completed_at": null,
  "model": "vllm_omni/wan2.2-t2v",
  "prompt": "A cinematic tracking shot of a mountain lake at sunrise",
  "error": null,
  "width": 1280,
  "height": 720,
  "num_frames": 80,
  "fps": 16,
  "num_inference_steps": 40,
  "guidance_scale": null,
  "seed": null
}
```

---

### 3.2 `GET /lollms/v1/videos/{video_id}` — Poll Status

Poll the current state of a video job. Status moves through: `queued` → `running` → `completed` (or `failed`).

```bash
curl -s -H "Authorization: Bearer $LOLLMS_KEY" \
     http://localhost:9600/lollms/v1/videos/vid_abc123xyz
```

**Response when complete:**

```json
{
  "id": "vid_abc123xyz",
  "object": "video.job",
  "status": "completed",
  "created_at": 1773360000,
  "completed_at": 1773360087,
  "model": "vllm_omni/wan2.2-t2v",
  "prompt": "A cinematic tracking shot of a mountain lake at sunrise",
  "error": null,
  "width": 1280,
  "height": 720,
  "num_frames": 80,
  "fps": 16,
  "num_inference_steps": 40,
  "guidance_scale": null,
  "seed": null
}
```

**Response on failure:**

```json
{
  "id": "vid_abc123xyz",
  "object": "video.job",
  "status": "failed",
  "created_at": 1773360000,
  "completed_at": 1773360012,
  "error": "TTV binding returned an empty or invalid video stream.",
  ...
}
```

**Status codes:**

| Code | Meaning |
| --- | --- |
| `200` | Job found, descriptor returned |
| `404` | Unknown job ID (or expired) |

---

### 3.3 `GET /lollms/v1/videos/{video_id}/content` — Download MP4

Retrieve the finished video as binary `video/mp4` content. Only valid once `status == "completed"`.

```bash
curl -s -H "Authorization: Bearer $LOLLMS_KEY" \
     -o video.mp4 \
     http://localhost:9600/lollms/v1/videos/vid_abc123xyz/content
```

**Response headers:**

```
Content-Type: video/mp4
Content-Disposition: inline; filename="vid_abc123xyz.mp4"
Cache-Control: no-store
```

**Status codes:**

| Code | Meaning |
| --- | --- |
| `200` | MP4 bytes returned |
| `404` | Unknown job ID |
| `409` | Job is not complete yet (`queued` or `running`) |
| `500` | Job `failed`, or completed with no bytes |

---

### 3.4 `POST /lollms/v1/videos/sync` — Blocking Sync

Runs the generation **inline** and returns raw `video/mp4` bytes directly. Ideal for benchmarks, CI scripts, and quick interactive tests where installing a polling loop is overkill.

```bash
curl -s -X POST http://localhost:9600/lollms/v1/videos/sync \
  -H "Authorization: Bearer $LOLLMS_KEY" \
  -F "prompt=A hummingbird hovering near a flower, macro, 4k" \
  -F "width=832" \
  -F "height=480" \
  -F "num_frames=48" \
  -F "fps=16" \
  -F "num_inference_steps=30" \
  -o hummingbird.mp4
```

**Response:** Binary `video/mp4` with `Content-Disposition: attachment; filename="clip_<random>.mp4"`.

**Status codes:**

| Code | Meaning |
| --- | --- |
| `200` | Video bytes returned |
| `400` | Missing `prompt` in body |
| `500` | Generation error |
| `501` | No active TTV binding configured |

---

## 4. Request Parameters

All fields are **optional except `prompt`** and may be sent as either JSON fields or multipart form fields.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `prompt` | `string` | **required** | Text description of the desired video or action. |
| `negative_prompt` | `string` | `null` | Elements to discourage/avoid. |
| `width` | `integer` | model default | Video output width in pixels. |
| `height` | `integer` | model default | Video output height in pixels. |
| `num_frames` | `integer` | model default | Total frames to generate. |
| `fps` | `integer` | model default | Frames per second for the output. |
| `num_inference_steps` | `integer` | model default | Denoising / diffusion steps. |
| `guidance_scale` | `number` | model default | Classifier-free guidance (CFG) scale. |
| `seed` | `integer` | `null` | Random seed for reproducibility. |
| `model` | `string` | user / server default | `binding_alias/model_name` or just `binding_alias` to select the target engine. |
| `control_type` | `string` | `null` | One of `canny`, `depth`, `hed`, `mlsd`, `pose`, `inpaint`. Used for video-to-video editing (see §6.D). |

Fields are passed through verbatim to the active TTV binding — unknown kwargs are ignored per the binding contract.

---

## 5. Reference Fields

Reference fields carry images, videos, audio, or masks used to condition generation. They are dispatched based on the recipe in §6.

| Field | Used for | Accepted formats |
| --- | --- | --- |
| `image_reference` | T2I first frame, lip-sync portrait, edit source | `UploadFile`, base64 data URL, `{"image_url": "..."}`, or plain `http(s)://` URL |
| `video_reference` | First/last-frame interpolation, video editing | `UploadFile`, base64 data URL, `{"video_url": "..."}`, or `http(s)://` URL |
| `mask_reference` | Inpainting region mask | `UploadFile`, base64 data URL, `{"mask_url": "..."}`, or `http(s)://` URL |
| `audio_reference` | Lip-sync speech audio | `UploadFile`, base64 data URL, `{"audio_url": "..."}`, or `http(s)://` URL |

**Detection order** — the parser tries, in sequence:
1. **`UploadFile`** (multipart only) → raw bytes + magic-byte derived extension hint (`image_ext`, `audio_ext`, …).
2. **JSON envelope** `{"image_url": "..."}` string → URL extracted and passed through verbatim.
3. **`http(s)://` URL** → passed through; binding fetches over HTTP.
4. **Base64 data URL** `data:image/png;base64,...` → decoded to bytes + extension hint.
5. **Bare base64** (no prefix) → decoded if the payload looks like base64 and is > 128 chars.
6. **Anything else** → forwarded as-is; binding ignores unknown types.

> **Bindings with optional capabilities:** The binding must advertise `supports_lipsync()` or `supports_first_last_frame()` via the `get_capabilities()` method. If it doesn't, the request gracefully falls through to standard text-to-video, forwarding all references as kwargs.

**Conflicting references:** Do not send mixtures that don't correspond to a valid recipe. For example, sending both `image_reference` and `audio_reference` will route through the **lip-sync** recipe, not T2V.

---

## 6. API Recipes

### A. Text-to-Video (T2V)

Pure text → video. No references.

```bash
curl -s -X POST http://localhost:9600/lollms/v1/videos \
  -H "Authorization: Bearer $LOLLMS_KEY" \
  -F "prompt=A cinematic tracking shot of a mountain lake at sunrise" \
  -F "width=1280" \
  -F "height=720" \
  -F "num_frames=80" \
  -F "fps=16" \
  -F "num_inference_steps=40"
```

---

### B. Image-to-Video / First Frame (I2V)

Use `image_reference` as the starting frame, animated by the prompt.

```bash
curl -s -X POST http://localhost:9600/lollms/v1/videos \
  -H "Authorization: Bearer $LOLLMS_KEY" \
  -F "prompt=An astronaut emerging from a cracked otherworldly egg on the moon" \
  -F "image_reference=@astronaut.jpg" \
  -F "width=832" \
  -F "height=480" \
  -F "num_frames=81" \
  -F "num_inference_steps=30" \
  -F "guidance_scale=5.0"
```

**URL envelope variant:**

```bash
-F 'image_reference={"image_url": "https://example.com/astronaut.jpg"}'
```

**Base64 data URL variant:**

```bash
-F 'image_reference=data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...'
```

---

### C. First-Last Frame Interpolation (FLF2V)

Anchor both the starting and ending frames to let the model interpolate between them. This is dispatched when both `image_reference` **and** `video_reference` are present and `control_type != "inpaint"`.

```bash
curl -s -X POST http://localhost:9600/lollms/v1/videos \
  -H "Authorization: Bearer $LOLLMS_KEY" \
  -F "prompt=A small blue bird takes off from a branch and lands on another branch" \
  -F "image_reference=@first_frame.png" \
  -F "video_reference=@last_frame.mp4" \
  -F "width=512" \
  -F "height=512" \
  -F "num_frames=81" \
  -F "num_inference_steps=30"
```

> Requires the binding to implement `generate_video_first_and_last_frame()`. If not advertised via `supports_first_last_frame()`, this request falls back to standard text-to-video.

---

### D. Video Editing & Inpainting

Structural edits, inpainting, or control-net-guided generation.

```bash
curl -s -X POST http://localhost:9600/lollms/v1/videos \
  -H "Authorization: Bearer $LOLLMS_KEY" \
  -F "prompt=Transform the style into a vibrant cyberpunk neon street scene" \
  -F "video_reference=@source_video.mp4" \
  -F "control_type=inpaint" \
  -F "mask_reference=@mask_frame.png" \
  -F "num_frames=48" \
  -F "num_inference_steps=35"
```

**`control_type` values:** `canny`, `depth`, `hed`, `mlsd`, `pose`, `inpaint`.

`mask_reference` is a static mask image or temporal mask video marking the region to modify.

---

### E. Lip-Sync / Audio-Driven

Animate a portrait to match a speech track. Dispatched when both `image_reference` and `audio_reference` are present **and** the binding advertises `supports_lipsync()`.

```bash
curl -s -X POST http://localhost:9600/lollms/v1/videos \
  -H "Authorization: Bearer $LOLLMS_KEY" \
  -F "prompt=A person singing expressively with natural head movement" \
  -F 'image_reference={"image_url": "https://example.com/face.png"}' \
  -F 'audio_reference={"audio_url": "https://example.com/speech.mp3"}' \
  -F "width=832" \
  -F "height=480" \
  -F "num_inference_steps=40" \
  -F "guidance_scale=4.5" \
  -F "fps=16"
```

> If the binding does not advertise lip-sync support, the references are forwarded to `generate_video`, which may either honor or ignore them.

---

## 7. Job States & Error Handling

### State Transitions

```
queued ──► running ──► completed ──► (janitor eviction after 1h)
                │
                └────► failed ──► (janitor eviction after 1h)
```

### Error Surface

| Scenario | Code | Response |
| --- | --- | --- |
| No active TTV binding (POST) | `501` | `{"detail": "No active Text-to-Video (TTV) binding configured..."}` |
| Missing `prompt` | `400` | `{"detail": "The 'prompt' field is required."}` |
| Unknown job ID | `404` | `{"detail": "Video job 'vid_xxx' not found."}` |
| Content requested before completion | `409` | `{"detail": "Video job is not ready (status: running). Poll the job first."}` |
| `GET .../content` on failed job | `500` | `{"detail": "Video job failed: <error>"}` |
| Sync generation crash | `500` | `{"detail": "Video generation failed: <error>"}` |

The polling endpoint is the **single authority** for job outcome — clients should always check `status` and `error` before requesting content.

---

## 8. Concurrency & Storage

- **Executor**: All blocking binding calls run inside a shared `ThreadPoolExecutor` (max 50 workers for `lollms_v1`). This is the same executor used by the `/video/generations` and `/audio/*` endpoints.
- **Job registry**: In-memory, per-process, keyed `vid_<uuid>`. Survives requests but not process restarts.
- **Eviction policy**:
  - **TTL**: terminal jobs (`completed` / `failed`) are pruned **1 hour** after `completed_at`.
  - **Hard cap**: at most **256** jobs are retained. When full, the oldest terminal job is evicted first.
  - Pruning happens on each `POST /videos` submission.
- **Result bytes**: MP4 bytes are held in memory until the job is evicted. For very large videos, wait for `GET .../content` to download promptly.
- **Multi-worker deployments**: each worker process has its own registry. Point polling requests at the same worker that received the submit (sticky sessions), or use the synchronous `/videos/sync` endpoint which is worker-agnostic.

---

## 9. End-to-End Workflow

Complete async flow in Python:

```python
import time
import requests

BASE = "http://localhost:9600/lollms/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# 1. Submit the job
resp = requests.post(
    f"{BASE}/videos",
    headers=HEADERS,
    data={
        "prompt": "A hummingbird hovering near a flower, macro, 4k",
        "width": 832,
        "height": 480,
        "num_frames": 48,
        "fps": 16,
        "num_inference_steps": 30,
    },
)
resp.raise_for_status()
job = resp.json()
video_id = job["id"]
print(f"Submitted job {video_id} (status={job['status']})")

# 2. Poll until terminal
while job["status"] in ("queued", "running"):
    time.sleep(3)
    job = requests.get(f"{BASE}/videos/{video_id}", headers=HEADERS).json()
    print(f"  status={job['status']}")

# 3. Handle outcome
if job["status"] == "failed":
    raise RuntimeError(f"Video job failed: {job.get('error')}")

# 4. Download
video_bytes = requests.get(
    f"{BASE}/videos/{video_id}/content", headers=HEADERS
).content
with open("hummingbird.mp4", "wb") as f:
    f.write(video_bytes)
print(f"✅ Saved {len(video_bytes)} bytes")
```

---

## 10. Integration Examples

### 10.1 Drop-in replacement for vLLM-Omni clients

If you already use a vLLM-Omni SDK that targets `http://localhost:8091/v1/videos`, simply swap the base URL and add your LoLLMS API key:

```diff
- BASE_URL = "http://localhost:8091/v1"
+ BASE_URL = "http://localhost:9600/lollms/v1"
+ HEADERS = {"Authorization": f"Bearer {LOLLMS_KEY}"}
```

Everything else (multipart fields, polling, content download) works unchanged.

### 10.2 Sync benchmark (single-call)

```bash
time curl -s -X POST http://localhost:9600/lollms/v1/videos/sync \
  -H "Authorization: Bearer $LOLLMS_KEY" \
  -F "prompt=A drifting cloud, timelapse" \
  -F "num_frames=24" \
  -F "fps=8" \
  -o bench.mp4
```

### 10.3 curl + jq workflow (shell-native)

```bash
# Submit
JOB_ID=$(curl -s -X POST http://localhost:9600/lollms/v1/videos \
  -H "Authorization: Bearer $LOLLMS_KEY" \
  -F "prompt=A cat walking through a sunlit garden" \
  -F "num_frames=48" | jq -r .id)

# Poll
while true; do
  STATUS=$(curl -s -H "Authorization: Bearer $LOLLMS_KEY" \
    http://localhost:9600/lollms/v1/videos/$JOB_ID | jq -r .status)
  echo "status=$STATUS"
  [ "$STATUS" = "completed" ] && break
  [ "$STATUS" = "failed" ] && { echo "failed"; exit 1; }
  sleep 2
done

# Download
curl -s -H "Authorization: Bearer $LOLLMS_KEY" \
  -o cat.mp4 http://localhost:9600/lollms/v1/videos/$JOB_ID/content
```

---

## Related Documentation

- [`LOLLMS_CLIENT_DOC.md`](../markdown/tools/LOLLMS_CLIENT_DOC.md) — TTV binding guide (writing custom TTV bindings, profile configuration).
- [`Simplified_lollms_api_documentation.md`](../markdown/tools/Simplified_lollms_api_documentation.md) — General LoLLMS API reference.

---

## See Also

- **Legacy endpoint**: `POST /lollms/v1/video/generations` — pre-existing single-shot T2V endpoint using a fixed Pydantic schema (`TTVRequest`/`TTVResponse`). Still supported for backward compatibility; prefer the `/videos*` family for new integrations.
- **OpenAI-compatible image generation**: `POST /v1/images/generations` — see `openai_v1.py`.
- **Capability discovery**: `GET /lollms/v1/capabilities` — first call for server-side TTV availability.