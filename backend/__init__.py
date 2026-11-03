import threading
from fastapi import FastAPI

app = FastAPI()

@app.on_event("startup")
async def prewarm_heavy_imports():
    """Fire off a background daemon thread to prewarm heavy imports without blocking the loop."""
    from backend.routers.stores import _prewarm_sentence_transformer
    threading.Thread(
        target=_prewarm_sentence_transformer, 
        daemon=True, 
        name="sentence_transformers_prewarm"
    ).start()

    # Filesystem personalities bootstrap: guarantee handbag roots exist and
    # the data folder is writable (fail fast with a clear log otherwise).
    from backend.personalities import ensure_personality_roots
    ensure_personality_roots()