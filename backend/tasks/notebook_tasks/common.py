import json
from typing import List, Dict, Any
from backend.db.models.notebook import Notebook as DBNotebook

def gather_context(notebook: DBNotebook, input_tab_ids: List[str]) -> str:
    """Combines selected tabs and loaded artefacts into a single context string."""
    context = ""
    # Process Tabs
    if notebook.tabs:
        for tab in notebook.tabs:
            if tab['id'] in input_tab_ids:
                context += f"\n\n--- Source Tab: {tab['title']} ---\n{tab.get('content', '')}\n"
    
    # Process Artefacts (Files)
    if notebook.artefacts:
        for art in notebook.artefacts:
            if art.get('is_loaded') and art.get('content'):
                context += f"\n\n--- Source File: {art['filename']} ---\n{art['content']}\n"
    
    return context

def get_notebook_metadata(notebook: DBNotebook) -> Dict[str, Any]:
    """Safely extracts metadata from the notebook content string."""
    try:
        if notebook.content and notebook.content.startswith('{'):
            data = json.loads(notebook.content)
            return data.get('metadata', {})
    except:
        pass
    return {}
