from backend.task_manager import Task
from backend.db.models.notebook import Notebook as DBNotebook
from sqlalchemy.orm.attributes import flag_modified

# Import the specialized processors
from .generic import process_generic
from .book_building import process_book_building
from .slides_making import process_slides_making
from .youtube_video import process_youtube_video

# Import the ingestion tasks to export them
from .ingestion import _ingest_notebook_sources_task, _convert_file_with_docling_task

def _process_notebook_task(task: Task, username: str, notebook_id: str, prompt: str, input_tab_ids: list, action: str, target_tab_id: str = None, skip_llm: bool = False, generate_speech: bool = False, selected_artefacts: list = None):
    """Entry point and dispatcher for all notebook AI tasks."""
    try:
        with task.db_session_factory() as db:
            notebook = db.query(DBNotebook).filter(DBNotebook.id == notebook_id).first()
            if not notebook:
                raise Exception("Notebook record not found.")

            result_tab_id = None
            nb_type = notebook.type or 'generic'

            # Dispatch based on type and action
            
            # YouTube Video Logic
            if nb_type == 'youtube_video' or action in ['generate_script', 'generate_animation', 'generate_personalities', 'regenerate_personality', 'generate_scene_image']:
                result_tab_id = process_youtube_video(task, notebook, username, prompt, input_tab_ids, action, target_tab_id, selected_artefacts)

            # Book Building Logic
            elif nb_type == 'book_building' or action in ['generate_book_plan', 'write_book_chapter']:
                # Pass target_tab_id to book building
                result_tab_id = process_book_building(task, notebook, username, prompt, input_tab_ids, action, target_tab_id)
            
            # Slides Making Logic
            elif nb_type == 'slides_making' or action in ['generate_slides_text', 'images', 'refine_image', 'generate_notes', 'generate_slide_title', 'add_full_slide', 'initial_process', 'generate_slide_html', 'generate_audio']:
                result_tab_id = process_slides_making(task, notebook, username, prompt, input_tab_ids, action, target_tab_id, selected_artefacts)
            
            # Default / Generic Logic
            else:
                result_tab_id = process_generic(task, notebook, username, prompt, input_tab_ids, action, target_tab_id, selected_artefacts)

            # Ensure changes to JSON fields are tracked
            flag_modified(notebook, "tabs")
            db.commit()
            
            return {
                "notebook_id": notebook_id,
                "new_tab_id": result_tab_id,
                "status": "success"
            }
    except Exception as e:
        task.log(f"Task Dispatcher Error: {e}", "ERROR")
        raise e
