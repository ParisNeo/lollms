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

1. **Title**: Create a descriptive title for the report
2. **Introduction**: Briefly introduce the topic and purpose of the analysis
3. **Methodology**: Explain what data sources were used and how the analysis was conducted
4. **Key Findings**: Present the most important insights in bullet points or numbered lists
5. **Detailed Analysis**: Provide in-depth analysis with proper headings and subheadings
6. **Visualizations**: Suggest appropriate visualizations (charts, graphs, tables) that would help illustrate the findings
7. **Conclusion**: Summarize the main takeaways and potential implications
8. **References**: List all data sources used in the analysis

Use proper Markdown formatting including:
- Headers (#, ##, ###)
- Lists (-, 1.)
- Bold and italic text for emphasis
- Code blocks for any technical details
- Tables for structured data
- Citations in the format [1], [2] with references at the end
"""

        user_prompt = f"""Analyze the following research data and generate a comprehensive report:

[Context Data]
{context[:50000]} # Truncate if too large

[User Request]
{prompt}

[Task]
Create a well-structured research report in Markdown format following the guidelines above.
Make sure to:
- Organize information logically
- Use appropriate headings and subheadings
- Include citations to source documents where relevant
- Suggest visualizations that would enhance understanding
- Keep the language professional but accessible
"""

        try:
            # Stream the generation to the tab content if possible, or just generate
            response = lc.generate_text(user_prompt, system_prompt=system_prompt)
            target_tab['content'] = response
            task.log("Report generated successfully.")
        except Exception as e:
            task.log(f"Generation failed: {e}", "ERROR")
            target_tab['content'] = f"# Error Generating Report\n\nAn error occurred while generating the report: {str(e)}"

        return target_tab['id']

    elif action == 'generate_html':
        task.log("Generating HTML visualization...")
        task.set_progress(10)

        system_prompt = """You are a data visualization expert. Create an HTML visualization based on the provided data and user request.
        Return only the HTML code wrapped in a <div> container with appropriate styling.
        Use charts, graphs, or other visual elements to best represent the data.
        Include comments in the code to explain key parts."""

        user_prompt = f"""Create an HTML visualization based on the following data and request:

[Context Data]
{context[:20000]}

[User Request]
{prompt}

[Task]
Generate an HTML visualization that effectively represents the data.
Include appropriate:
- Charts (using Chart.js or similar)
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
