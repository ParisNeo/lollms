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