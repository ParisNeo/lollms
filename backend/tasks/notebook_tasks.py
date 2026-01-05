# Entry point maintained for compatibility with existing router imports
from .notebook_tasks.__init__ import _process_notebook_task
from .notebook_tasks.common import _ingest_notebook_sources_task, _convert_file_with_docling_task

# Add stubs for missing common tasks if not moved yet
def _ingest_notebook_sources_task(*args, **kwargs):
    from .notebook_tasks.common_ingestion import _ingest_notebook_sources_task as impl
    return impl(*args, **kwargs)

def _convert_file_with_docling_task(*args, **kwargs):
    from .notebook_tasks.common_ingestion import _convert_file_with_docling_task as impl
    return impl(*args, **kwargs)
