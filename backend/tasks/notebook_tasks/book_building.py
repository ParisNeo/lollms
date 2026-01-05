import uuid
import json
import re
from backend.task_manager import Task
from backend.db.models.notebook import Notebook as DBNotebook
from backend.session import get_user_lollms_client
from typing import List
from .common import gather_context

def process_book_building(task: Task, notebook: DBNotebook, username: str, prompt: str, input_tab_ids: List[str], action: str, target_tab_id: str = None):
    lc = get_user_lollms_client(username)
    context = gather_context(notebook, input_tab_ids)
    
    target_tab = None
    if target_tab_id:
        target_tab = next((t for t in notebook.tabs if t['id'] == target_tab_id), None)

    if action == 'generate_book_plan':
        task.log("Generating book architecture...")
        system_prompt = "You are a Master Book Editor. Create a structured JSON outline."
        contextual_prompt = (
            "Create a detailed chapter-by-chapter plan for a book. "
            "Output MUST be a JSON list: `[{\"title\": \"...\", \"description\": \"...\"}]`.\n"
            f"Topic: {prompt}"
        )
        
        response = lc.long_context_processing(
            text_to_process=context,
            contextual_prompt=contextual_prompt,
            system_prompt=system_prompt
        )
        
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        content = json_match.group(0) if json_match else response
        
        if target_tab:
            target_tab['content'] = content
            # Ensure type is consistent
            target_tab['type'] = 'book_plan'
            target_tab['title'] = "Book Plan" # Optional: update title?
            return target_tab['id']
        else:
            new_tab = {
                "id": str(uuid.uuid4()),
                "title": "Book Plan",
                "type": "book_plan",
                "content": content,
                "images": []
            }
            notebook.tabs.append(new_tab)
            return new_tab['id']

    elif action == 'write_book_chapter':
        task.log("Writing long-form chapter...")
        # Try to find the plan for context
        plan_content = ""
        for t in notebook.tabs:
            if t['type'] == 'book_plan':
                plan_content = f"BOOK PLAN:\n{t['content']}\n\n"
                break
        
        system_prompt = "You are a professional Ghostwriter. Write immersive, high-quality book chapters in Markdown."
        contextual_prompt = f"{plan_content}Write the following chapter in full detail: {prompt}"
        
        response = lc.long_context_processing(
            text_to_process=context,
            contextual_prompt=contextual_prompt,
            system_prompt=system_prompt
        )
        
        if target_tab:
            target_tab['content'] = response
            return target_tab['id']
        else:
            new_tab = {
                "id": str(uuid.uuid4()),
                "title": prompt.split('\n')[0][:30],
                "type": "markdown",
                "content": response,
                "images": []
            }
            notebook.tabs.append(new_tab)
            return new_tab['id']
