import random
from pathlib import Path
from fastapi import FastAPI, Request, APIRouter
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# This router will handle the API endpoint for fun facts.
ui_router = APIRouter()

# --- Fun Facts ---
FUN_FACTS = [
    "From text generation to coding assistance, LoLLMs aims to be a versatile AI tool.",
    "The name LoLLMs stands for 'Lord of Large Language Models', a nod to its goal of managing multiple AI models.",
    "Personalities in LoLLMs allow you to tailor the AI's responses to specific tasks or characters.",
    "You can run LoLLMs entirely on your local machine, ensuring your data remains private.",
    "The RAG (Retrieval-Augmented Generation) system lets your AI access and cite information from your own documents.",
    "LoLLMs supports a wide variety of model backends, including llama.cpp, Ollama, and OpenAI.",
    "The 'One tool to rule them all' slogan reflects the project's ambition to unify many AI functionalities in a single interface.",
    "The project is open-source, meaning anyone can contribute to its development and see how it works.",
]

@ui_router.get("/api/fun-fact", include_in_schema=True)
async def get_fun_fact():
    """
    Returns a random fun fact about LoLLMs.
    """
    return {"fun_fact": random.choice(FUN_FACTS)}
# --- End Fun Facts ---


# This part remains for serving the static files
STATIC_DIR = Path(__file__).parent.parent.parent / "frontend/dist"

def add_ui_routes(app):
    @app.get("/{full_path:path}", response_class=FileResponse, include_in_schema=False)
    async def serve_vue_app(full_path: str):
        path = STATIC_DIR/ full_path
        if path.exists() and not path.is_dir():
            return FileResponse(path)
        
        index_path = STATIC_DIR/ "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        
        return FileResponse(STATIC_DIR/ "index.html")