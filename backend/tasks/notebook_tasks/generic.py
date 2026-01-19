import json
import uuid
from typing import List
from backend.task_manager import Task
from backend.db.models.notebook import Notebook as DBNotebook
from backend.session import get_user_lollms_client
from .common import gather_context, get_notebook_metadata

def process_generic(task: Task, notebook: DBNotebook, username: str, prompt: str, input_tab_ids: List[str], action: str, target_tab_id: str = None, selected_artefacts: List[str] = None):
    lc = get_user_lollms_client(username)
    context = gather_context(notebook, input_tab_ids)

    # Add selected artefacts to context if any
    if selected_artefacts:
        for art in notebook.artefacts:
            if art['filename'] in selected_artefacts:
                context += f"\n\n--- Source: {art['filename']} ---\n{art['content']}\n"

    # Identify target tab
    target_tab = None
    if target_tab_id:
        target_tab = next((t for t in notebook.tabs if t['id'] == target_tab_id), None)

    if not target_tab:
        # Check if we have a main markdown tab, else create one
        target_tab = next((t for t in notebook.tabs if t['type'] == 'markdown'), None)
        if not target_tab:
            target_tab = {
                "id": str(uuid.uuid4()),
                "title": "Research Report",
                "type": "markdown",
                "content": "",
                "images": []
            }
            notebook.tabs.append(target_tab)

    if action in ['initial_process', 'generate_report', 'text_processing', 'summarize']:
        task.log("Generating research report...")
        task.set_progress(10)

        system_prompt = """You are a professional research assistant. Organize the information into a well-structured Markdown report with the following sections:

1. **Executive Summary**: Brief overview of the main findings
2. **Introduction**: Context and purpose of the analysis
3. **Key Findings**: Most important insights in bullet points or numbered lists
4. **Detailed Analysis**: In-depth analysis with proper headings and subheadings
5. **Methodology**: Sources used and approach taken
6. **Conclusion**: Main takeaways and implications
7. **References**: List all data sources

Use proper Markdown formatting including:
- Headers (#, ##, ###)
- Lists (-, 1.)
- Bold and italic text for emphasis
- Code blocks for technical details
- Tables for structured data
- Citations in the format [1], [2] with references at the end
"""

        # Build the user prompt with context
        user_prompt = f"""Analyze the following research data and generate a comprehensive report:

[Context Data]
{context[:50000]}

[User Request]
{prompt}

[Task]
Create a well-structured research report in Markdown format following the guidelines above.
Make sure to:
- Organize information logically
- Use appropriate headings and subheadings
- Include citations to source documents where relevant
- Keep the language professional but accessible
"""

        try:
            task.set_progress(30)
            # Use long_context_processing for better handling of large contexts
            response = lc.long_context_processing(
                text_to_process=context,
                contextual_prompt=f"User request: {prompt}\n\nGenerate a comprehensive research report based on the sources.",
                system_prompt=system_prompt
            )
            
            # Handle dict response from LCP
            if isinstance(response, dict):
                if 'error' in response:
                    task.log(f"LCP Error: {response['error']}", "ERROR")
                    response = f"# Error Generating Report\n\nAn error occurred: {response['error']}"
                else:
                    response = response.get('content', response.get('text', str(response)))
            
            if not isinstance(response, str):
                response = str(response)
            
            task.set_progress(90)
            target_tab['content'] = response
            task.log("Report generated successfully.")
        except Exception as e:
            task.log(f"Generation failed: {e}", "ERROR")
            target_tab['content'] = f"# Error Generating Report\n\nAn error occurred while generating the report: {str(e)}"

        return target_tab['id']

    elif action == 'generate_outline':
        task.log("Generating structured outline...")
        system_prompt = "You are a research analyst. Create a hierarchical outline with sections and subsections in Markdown format."
        user_prompt = f"""Analyze these sources and create a detailed outline:

{context[:30000]}

User instruction: {prompt}

Create a structured outline with:
- Main sections (## headers)
- Subsections (### headers)  
- Key points under each section
"""
        response = lc.generate_text(user_prompt, system_prompt=system_prompt)
        target_tab['content'] = response
        return target_tab['id']

    elif action == 'extract_key_points':
        task.log("Extracting key insights...")
        system_prompt = "Extract the most important points, findings, and insights from the research material."
        user_prompt = f"""Sources:
{context[:30000]}

Extract 10-15 key points in bullet format. Focus on the most significant findings, facts, and insights.
"""
        response = lc.generate_text(user_prompt, system_prompt=system_prompt)
        target_tab['content'] = response
        return target_tab['id']

    elif action == 'generate_timeline':
        task.log("Creating timeline...")
        system_prompt = "You are a chronology expert. Extract and organize events/developments into a timeline."
        user_prompt = f"""From these sources, create a chronological timeline in Markdown format:

{context[:30000]}

Format as:
## Timeline

- **Date/Period**: Event description
- **Date/Period**: Event description
"""
        response = lc.generate_text(user_prompt, system_prompt=system_prompt)
        target_tab['content'] = response
        return target_tab['id']

    elif action == 'compare_sources':
        task.log("Performing comparative analysis...")
        system_prompt = "You are a comparative analyst. Identify similarities, differences, and patterns across sources."
        user_prompt = f"""Compare and contrast these sources:

{context[:30000]}

Focus on: {prompt}

Structure the comparison with:
- Similarities
- Differences
- Unique insights from each source
- Overall synthesis
"""
        response = lc.generate_text(user_prompt, system_prompt=system_prompt)
        target_tab['content'] = response
        return target_tab['id']

    elif action == 'generate_html':
        task.log("Generating HTML visualization...")
        task.set_progress(10)

        system_prompt = """You are a data visualization expert. Create an HTML visualization based on the provided data and user request.
        Return only the HTML code wrapped in a complete HTML document with appropriate styling.
        Use charts, graphs, or other visual elements to best represent the data.
        Include comments in the code to explain key parts."""

        user_prompt = f"""Create an HTML visualization based on the following data and request:

[Context Data]
{context[:20000]}

[User Request]
{prompt}

[Task]
Generate a complete HTML document with visualization that effectively represents the data.
Include appropriate:
- Charts (using Chart.js or similar from CDN)
- Tables with styling
- Text explanations
- Responsive design
- Comments explaining the code
"""

        try:
            html_response = lc.generate_text(user_prompt, system_prompt=system_prompt)
            # Extract HTML content
            html_content = html_response

            # Create a new HTML tab
            html_tab = {
                "id": str(uuid.uuid4()),
                "title": "Visualization",
                "type": "html",
                "content": html_content,
                "images": []
            }
            notebook.tabs.append(html_tab)
            task.log("HTML visualization generated successfully.")
            return html_tab['id']

        except Exception as e:
            task.log(f"HTML generation failed: {e}", "ERROR")
            return None

    elif action == 'generate_code':
        task.log("Generating code...")
        task.set_progress(10)

        system_prompt = """You are a coding assistant. Generate code based on the user's request and provided data.
        Return only the code, properly formatted with comments explaining key parts."""

        user_prompt = f"""Generate code based on the following data and request:

[Context Data]
{context[:20000]}

[User Request]
{prompt}

[Task]
Generate appropriate code that:
- Solves the problem described in the request
- Is properly commented
- Includes error handling where appropriate
- Follows best practices for the language
"""

        try:
            code_response = lc.generate_text(user_prompt, system_prompt=system_prompt)

            # Create a new code tab
            code_tab = {
                "id": str(uuid.uuid4()),
                "title": "Generated Code",
                "type": "code",
                "content": code_response,
                "images": []
            }
            notebook.tabs.append(code_tab)
            task.log("Code generated successfully.")
            return code_tab['id']

        except Exception as e:
            task.log(f"Code generation failed: {e}", "ERROR")
            return None

    return None
