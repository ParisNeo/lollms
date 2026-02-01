import json
import uuid
import re
from typing import List, Optional
from backend.task_manager import Task
from backend.db.models.notebook import Notebook as DBNotebook
from backend.session import get_user_lollms_client
from .common import gather_context, get_notebook_metadata

def process_generic(
    task: Task, 
    notebook: DBNotebook, 
    username: str, 
    prompt: str, 
    input_tab_ids: List[str], 
    action: str, 
    target_tab_id: Optional[str] = None, 
    selected_artefacts: Optional[List[str]] = None, 
    use_rlm: bool = False
):
    """
    Primary processor for generic, research, and technical notebooks.
    Handles standard LLM synthesis and RLM (Recursive Language Model) deep-reasoning modes.
    """
    lc = get_user_lollms_client(username)
    
    # 1. Context Gathering
    # Combines text from selected tabs and loaded files (artefacts)
    context = gather_context(notebook, input_tab_ids)

    # Add specifically selected artefacts to the context
    if selected_artefacts:
        for art in notebook.artefacts:
            if art['filename'] in selected_artefacts:
                context += f"\n\n--- Source: {art['filename']} ---\n{art.get('content', '')}\n"

    # 2. Identify Target Tab
    # If a specific ID was passed (usually for 'Update Active'), use it.
    # Otherwise, the system defaults to a new tab creation logic within the action branches.
    target_tab = None
    if target_tab_id:
        target_tab = next((t for t in notebook.tabs if t['id'] == target_tab_id), None)

    # 3. Action Dispatcher
    
    # --- Group A: General Research, Synthesis, and RLM Mode ---
    if action in ['initial_process', 'generate_report', 'text_processing', 'summarize']:
        task.log(f"Initializing Processing (RLM Mode: {'ON' if use_rlm else 'OFF'})...")
        task.set_progress(10)

        # Ensure we have a target tab for these general actions
        if not target_tab:
            target_tab = {
                "id": str(uuid.uuid4()),
                "title": prompt[:25] + "..." if prompt else "Research Report",
                "type": "markdown",
                "content": "",
                "images": []
            }
            notebook.tabs.append(target_tab)

        if use_rlm:
            # --- RLM STRATEGY ---
            # Treats context as an external variable for decomposition and recursive reasoning
            system_prompt = """You are acting as a Recursive Language Model (RLM). 
            Your goal is to perform deep reasoning over a massive context by treating it as a programmable variable.
            
            RLM STRATEGY:
            1. INSPECT: Identify logical boundaries, entities, and key evidence.
            2. DECOMPOSE: Break the request into atomic sub-questions.
            3. RECURSIVE SYNTHESIS: Process data in logical chunks without losing fine-grained detail.
            4. FINAL VERIFICATION: Ensure the synthesized answer is grounded in the provided context variable.
            
            You have access to a symbolic Python REPL. You can use regex or indexing to slice the 'context'.
            Your output must be high-density, technical Markdown."""
            
            user_prompt = f"""
            [CONTEXT_DATA_INFO]
            Estimated Tokens: {len(context) // 4}
            Snippet: {context[:5000]}... [Full context accessible via recursive reasoning]

            [USER_REQUEST]
            {prompt}

            [TASK]
            Apply RLM inference. Decompose, chunk, and synthesize a comprehensive answer. 
            Do not provide a shallow summary; provide a deep, grounded technical report.
            """
            
            try:
                task.log("Decomposing request using Recursive strategy...")
                task.set_progress(30)
                response = lc.long_context_processing(
                    text_to_process=context,
                    contextual_prompt=f"Apply RLM logic to answer: {prompt}",
                    system_prompt=system_prompt
                )
            except Exception as e:
                task.log(f"RLM Engine failure: {e}. Falling back to standard LCP.", "WARNING")
                use_rlm = False

        if not use_rlm:
            # --- STANDARD LCP STRATEGY ---
            system_prompt = """You are a professional research assistant. Organize information into a well-structured Markdown report.
            Include Executive Summary, Key Findings, Detailed Analysis, and References.
            Use headers, bold text, and lists for readability."""

            user_prompt = f"""Analyze the research data and fulfill the request:

            [Context]
            {context[:60000]}

            [Request]
            {prompt}
            """
            
            task.set_progress(40)
            response = lc.long_context_processing(
                text_to_process=context,
                contextual_prompt=prompt,
                system_prompt=system_prompt
            )

        # Handle potential dictionary responses from LollmsClient
        if isinstance(response, dict):
            response = response.get('content', response.get('text', str(response)))
        
        target_tab['content'] = str(response)
        task.set_progress(100)
        return target_tab['id']

    # --- Group B: Targeted Analysis (Timeline, Key Points, Comparisons) ---
    elif action in ['generate_outline', 'extract_key_points', 'generate_timeline', 'compare_sources']:
        task.log(f"Running Analysis Tool: {action.replace('_', ' ').title()}")
        
        if not target_tab:
            titles = {
                'generate_outline': 'Outline',
                'extract_key_points': 'Key Insights',
                'generate_timeline': 'Timeline',
                'compare_sources': 'Comparison'
            }
            target_tab = {
                "id": str(uuid.uuid4()),
                "title": titles.get(action, "Analysis"),
                "type": "markdown",
                "content": "",
                "images": []
            }
            notebook.tabs.append(target_tab)

        if action == 'generate_outline':
            system_p = "You are a research analyst. Create a hierarchical Markdown outline."
            user_p = f"Create a detailed outline from these sources:\n\n{context[:30000]}\n\nUser instructions: {prompt}"
        
        elif action == 'extract_key_points':
            system_p = "Extract the most significant findings and data points."
            user_p = f"Extract 10-15 key points in bullet format from:\n\n{context[:30000]}"
            
        elif action == 'generate_timeline':
            system_p = "You are a chronology expert. Organize events into a vertical Markdown timeline."
            user_p = f"Create a timeline of events found in these sources:\n\n{context[:30000]}"
            
        elif action == 'compare_sources':
            system_p = "You are a comparative analyst. Identify similarities and contradictions."
            user_p = f"Perform a comparative analysis of the provided sources focusing on: {prompt}\n\nSources:\n{context[:30000]}"

        response = lc.generate_text(user_p, system_prompt=system_p)
        target_tab['content'] = response
        task.set_progress(100)
        return target_tab['id']

    # --- Group C: Data Visualizations (HTML) ---
    elif action == 'generate_html':
        task.log("Generating dynamic HTML visualization...")
        task.set_progress(20)

        system_prompt = """You are a web visualization expert. Create a responsive HTML document.
        Use CDN-hosted libraries (Chart.js, Tailwind, D3.js) if necessary.
        Return ONLY the HTML code block. Do not include markdown wrappers."""

        user_prompt = f"""Generate an interactive HTML visualization based on this data:
        
        [Data]
        {context[:25000]}
        
        [Goal]
        {prompt}
        """

        try:
            html_response = lc.generate_text(user_prompt, system_prompt=system_prompt)
            # Remove markdown code fences if LLM added them
            html_clean = re.sub(r'```html|```', '', html_response).strip()

            if not target_tab:
                target_tab = {
                    "id": str(uuid.uuid4()),
                    "title": "Visualization",
                    "type": "html",
                    "content": "",
                    "images": []
                }
                notebook.tabs.append(target_tab)
            else:
                target_tab['type'] = 'html'

            target_tab['content'] = html_clean
            task.log("Visualization generated.")
            task.set_progress(100)
            return target_tab['id']
        except Exception as e:
            task.log(f"HTML Generation Error: {e}", "ERROR")
            return None

    # --- Group D: Technical Logic (Code) ---
    elif action == 'generate_code':
        task.log("Generating technical code implementation...")
        task.set_progress(20)

        system_prompt = "You are a senior software engineer. Generate production-ready, commented code."
        user_prompt = f"""Generate code based on the provided research context:
        
        [Context]
        {context[:20000]}
        
        [Requirements]
        {prompt}
        """

        try:
            code_response = lc.generate_text(user_prompt, system_prompt=system_prompt)
            
            if not target_tab:
                target_tab = {
                    "id": str(uuid.uuid4()),
                    "title": "Code Logic",
                    "type": "code",
                    "content": "",
                    "images": []
                }
                notebook.tabs.append(target_tab)
            else:
                target_tab['type'] = 'code'

            target_tab['content'] = code_response
            task.log("Code generation complete.")
            task.set_progress(100)
            return target_tab['id']
        except Exception as e:
            task.log(f"Code Generation Error: {e}", "ERROR")
            return None

    task.log(f"Unknown action requested: {action}", "ERROR")
    return None
