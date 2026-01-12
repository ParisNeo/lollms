from backend.db.models.notebook import Notebook as DBNotebook
from backend.task_manager import Task
from sqlalchemy.orm import Session
from ascii_colors import trace_exception

# Import Handlers
from .slides_making import process_slides_making, generate_deck_summary_task
from .youtube_video import process_youtube_video
from .book_building import process_book_building
from .generic import process_generic
from .ingestion import _ingest_notebook_sources_task, _convert_file_with_docling_task
from .image_gen import _regenerate_slide_image_task

def _process_notebook_task(
    task: Task, 
    username: str, 
    notebook_id: str, 
    prompt: str, 
    input_tab_ids: list, 
    action: str, 
    target_tab_id: str = None, 
    skip_llm: bool = False,
    generate_speech: bool = False,
    selected_artefacts: list = None
):
    with task.db_session_factory() as db:
        notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
        if not notebook:
            task.log("Notebook not found", "ERROR")
            return

        try:
            result_tab_id = None
            
            # Dispatch based on Notebook Type
            if notebook.type == 'slides_making':
                result_tab_id = process_slides_making(task, notebook, username, prompt, input_tab_ids, action, target_tab_id, selected_artefacts)
            
            elif notebook.type == 'youtube_video':
                result_tab_id = process_youtube_video(task, notebook, username, prompt, input_tab_ids, action, target_tab_id, selected_artefacts)
            
            elif notebook.type == 'book_building':
                # Assuming book_building handler exists, if not, fallback to generic for text
                if 'process_book_building' in globals():
                    result_tab_id = process_book_building(task, notebook, username, prompt, input_tab_ids, action, target_tab_id, selected_artefacts)
                else:
                    result_tab_id = process_generic(task, notebook, username, prompt, input_tab_ids, action, target_tab_id, selected_artefacts)

            else: # generic, research, etc.
                result_tab_id = process_generic(task, notebook, username, prompt, input_tab_ids, action, target_tab_id, selected_artefacts)

            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(notebook, "tabs")
            db.commit()
            
            task.log(f"Task '{action}' completed.")
            return {"status": "success", "tab_id": result_tab_id}

        except Exception as e:
            trace_exception(e)
            task.log(f"Error processing notebook task: {str(e)}", "ERROR")
            raise e
