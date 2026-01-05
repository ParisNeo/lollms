import uuid
import re
import json
from backend.task_manager import Task
from backend.db.models.notebook import Notebook as DBNotebook
from backend.session import get_user_lollms_client
from typing import List
from .common import gather_context

def _extract_html(text: str) -> str:
    """Extracts HTML content from code blocks."""
    match = re.search(r'```html(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text

def _extract_code(text: str) -> str:
    """Extracts Code content from code blocks."""
    match = re.search(r'```(?:\w+)?(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text

def process_generic(task: Task, notebook: DBNotebook, username: str, prompt: str, input_tab_ids: List[str], action: str, target_tab_id: str = None, selected_artefacts: List[str] = None):
    lc = get_user_lollms_client(username)
    
    # Gather context from tabs
    context = gather_context(notebook, input_tab_ids)
    
    # Add selected artefacts to context
    if selected_artefacts:
        for art in notebook.artefacts:
            if art['filename'] in selected_artefacts:
                context += f"\n\n--- Source: {art['filename']} ---\n{art['content']}\n"

    task.log(f"Processing generic action: {action}")
    
    response_content = ""
    tab_type = "markdown"
    tab_title = "AI Output"

    if action == 'summarize':
        task.log("Summarizing content...")
        system_prompt = "You are an expert summarizer. Distill the information into clear, concise markdown."
        contextual_prompt = f"Summarize the following context based on this request: {prompt}"
        if not prompt.strip():
            contextual_prompt = "Summarize the key points of the provided context."
            
        response_content = lc.long_context_processing(
            text_to_process=context,
            contextual_prompt=contextual_prompt,
            system_prompt=system_prompt
        )
        tab_title = "Summary"

    elif action == 'generate_html':
        task.log("Generating HTML graphic...")
        system_prompt = "You are an expert web developer. Create self-contained, responsive HTML5/CSS/JS widgets."
        user_prompt = f"""
        Context:
        {context[:10000]}... [truncated]
        
        Request: {prompt}
        
        Task: Create a single HTML file to visualize or represent this data/request.
        Use internal CSS and JS. Do not assume external internet access for libraries unless using standard CDNs (like d3.js, chart.js, fontawesome) is explicitly requested.
        Output ONLY the HTML code block.
        """
        
        raw_response = lc.generate_text(user_prompt, system_prompt=system_prompt)
        response_content = _extract_html(raw_response)
        tab_type = "html"
        tab_title = "Graphic"

    elif action == 'generate_code':
        task.log("Generating code...")
        system_prompt = "You are an expert software engineer."
        user_prompt = f"""
        Context:
        {context[:10000]}...
        
        Request: {prompt}
        
        Task: Write the requested code. Return ONLY the code block.
        """
        raw_response = lc.generate_text(user_prompt, system_prompt=system_prompt)
        response_content = _extract_code(raw_response)
        tab_type = "code"
        tab_title = "Code"

    else:
        # Default Chat / Text Processing
        task.log("Processing text request...")
        full_prompt = f"{context}\n\n[INSTRUCTION]\n{prompt}\n\nAnswer in Markdown."
        
        def stream_cb(chunk, msg_type=None, **kwargs):
            if task.cancellation_event.is_set(): return False
            return True

        response_content = lc.long_context_processing(
            text_to_process="", # Context embedded if short, or handled by LCP if long
            contextual_prompt=full_prompt,
            streaming_callback=stream_cb
        )
        tab_title = "Response"

    # Update or Create Tab
    if target_tab_id:
        for tab in notebook.tabs:
            if tab['id'] == target_tab_id:
                tab['content'] = response_content
                # Update type if we generated HTML/Code into an existing tab, usually we overwrite or append
                # but if specific type was requested, we might want to switch the view mode in frontend
                if tab_type != 'markdown':
                    tab['type'] = tab_type
                break
    else:
        new_tab = {
            "id": str(uuid.uuid4()),
            "title": tab_title,
            "type": tab_type,
            "content": response_content,
            "images": []
        }
        notebook.tabs.append(new_tab)
        target_tab_id = new_tab['id']

    return target_tab_id
