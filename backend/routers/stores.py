# [UPDATE] backend/routers/stores.py
import shutil
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Any
import traceback
from ascii_colors import trace_exception
import os
from pydantic import BaseModel
from sqlalchemy.orm import joinedload
import json

# Third-Party Imports
from fastapi import (
    HTTPException,
    Depends,
    File,
    UploadFile,
    Form,
    APIRouter,
    status
)
from fastapi.responses import (
    JSONResponse,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError


from werkzeug.utils import secure_filename


# Local Application Imports
from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.datastore import DataStore as DBDataStore, SharedDataStoreLink as DBSharedDataStoreLink
from backend.models import (
    UserAuthDetails,
    TaskInfo
)
from backend.models.datastore import (
    DataStoreCreate,
    DataStoreEdit,
    DataStoreShareRequest,
    DataStorePublic,
    DataStoreBase,
    SharedWithUserPublic,
    SafeStoreDocumentInfo,
)

from backend.session import get_datastore_db_path, build_lollms_client_from_params
from backend.db.models.db_task import DBTask
from backend.settings import settings
from backend.tasks.utils import _to_task_info
# safe_store is expected to be installed
try:
    import safe_store
    from safe_store import GraphStore
    import numpy as np
except ImportError:
    print(
        "WARNING: safe_store library not found. RAG features will be disabled. Install with: pip install safe_store[all]"
    )
    safe_store = None
    GraphStore = None
    SafeStoreLogLevel = None
    np = None

from backend.session import (
    get_current_active_user,
    get_safe_store_instance,
    get_user_datastore_root_path,
    user_sessions
)
from backend.task_manager import task_manager, Task
from backend.db.models.config import RAGBinding as DBRAGBinding
from backend.routers.files import extract_text_from_file_bytes

# --- NEW Pydantic Models for Graph Operations ---
class DataStoreDetails(BaseModel):
    size_bytes: int
    chunk_count: int
    graph_nodes_count: int
    graph_edges_count: int
    
class GraphGenerationRequest(BaseModel):
    graph_type: str = "knowledge_graph"
    model_binding: str
    model_name: str
    chunk_size: int = 2048
    overlap_size: int = 256
    ontology: Optional[str] = None

class GraphQueryRequest(BaseModel):
    query: str
    max_k: int = 10

class DataStoreQueryRequest(BaseModel):
    query: str
    top_k: int = 10
    min_similarity_percent: float = 50.0

class NodeData(BaseModel):
    label: str
    properties: Dict[str, Any] = {}

class EdgeData(BaseModel):
    source_id: int
    target_id: int
    label: str
    properties: Dict[str, Any] = {}

class DeleteFilesRequest(BaseModel):
    filenames: List[str]

def _sanitize_numpy(data: Any) -> Any:
    """Recursively convert numpy types to standard Python types."""
    if np is None:
        return data
        
    if isinstance(data, dict):
        return {k: _sanitize_numpy(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_sanitize_numpy(item) for item in data]
    if isinstance(data, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64,
                      np.uint8, np.uint16, np.uint32, np.uint64)):
        return int(data)
    if isinstance(data, (np.float_, np.float16, np.float32, np.float64)):
        return float(data)
    if isinstance(data, np.ndarray):
        return data.tolist()
    return data

# --- Task Functions ---
def _upload_rag_files_task(task: Task, username: str, datastore_id: str, file_paths: List[str], metadata_option: str, manual_metadata_json: str, vectorize_with_metadata: bool):
    db = next(get_db())
    try:
        datastore_record = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
        if not datastore_record:
            raise Exception(f"Datastore with ID {datastore_id} not found.")

        ss = get_safe_store_instance(username, datastore_id, db, permission_level="read_write")
        
        lc = None
        if metadata_option in ['auto-generate', 'rewrite-chunk']:
            from backend.session import build_lollms_client_from_params
            lc = build_lollms_client_from_params(username=username)

        manual_metadata = json.loads(manual_metadata_json) if manual_metadata_json else {}

        processed_count = 0
        error_count = 0
        total_files = len(file_paths)
        
        with ss:
            for i, file_path_str in enumerate(file_paths):
                if task.cancellation_event.is_set():
                    task.log("Upload task cancelled.", level="WARNING")
                    break
                
                file_path = Path(file_path_str)
                task.set_file_info(file_name=file_path.name, total_files=total_files)
                task.log(f"Processing file {i+1}/{total_files}: {file_path.name}")
                
                try:
                    metadata = None
                    if metadata_option == 'manual':
                        metadata = manual_metadata.get(file_path.name)
                        if metadata:
                            task.log(f"Using manual metadata: {metadata}")

                    elif metadata_option == 'auto-generate' and lc:
                        task.log(f"Generating metadata for {file_path.name}")
                        file_bytes = file_path.read_bytes()
                        text_content, _ = extract_text_from_file_bytes(file_bytes, file_path.name)

                        if text_content.strip():
                            metadata_prompt = "Generate short metadata for this document. Extract the title, a brief subject, and any authors mentioned. Present this as a JSON object with keys 'title', 'subject', and 'authors' (as a list of strings)."
                            schema = {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string", "description": "A concise and descriptive title for the document."},
                                    "subject": {"type": "string", "description": "The main subject or topic of the document."},
                                    "authors": {"type": "array", "items": {"type": "string"}, "description": "A list of authors, if any are mentioned."}
                                },
                                "required": ["title", "subject"]
                            }
                            truncated_text = text_content[:12000]
                            metadata = lc.generate_structured_content(truncated_text, schema=schema, system_prompt=metadata_prompt)
                            task.log(f"Generated metadata: {metadata}")
                        else:
                            task.log(f"Skipping metadata generation for empty file {file_path.name}", "WARNING")

                    ss.add_document(
                        str(file_path),
                        metadata=metadata,
                        vectorize_with_metadata=vectorize_with_metadata if metadata else False,
                    )
                    processed_count += 1
                    try:
                        file_path.unlink()
                        task.log(f"Successfully processed and removed temporary file: {file_path.name}")
                    except Exception as del_err:
                        task.log(f"Warning: Could not delete temporary file {file_path.name}: {del_err}", level="WARNING")
                except Exception as e:
                    error_count += 1
                    task.log(f"Error processing {file_path.name}: {e}", level="ERROR")
                
                progress = int(100 * (i + 1) / total_files)
                task.set_progress(progress)
        
        task.result = {"message": f"Processing complete. Added {processed_count} files. Encountered {error_count} errors."}

    except Exception as e:
        traceback.print_exc()
        raise e
    finally:
        db.close()

def _generate_graph_task(task: Task, username: str, datastore_id: str, request_data: dict):
    if not GraphStore:
        raise ImportError("GraphStore is not available.")
    
    db = next(get_db())
    try:
        llm_client = build_lollms_client_from_params(
            username=username,
            binding_alias=request_data.get("model_binding"),
            model_name=request_data.get("model_name")
        )

        def llm_executor_callback(prompt: str) -> str:
            return llm_client.generate_text(prompt, max_new_tokens=2048)

        ss = get_safe_store_instance(username, datastore_id, db, permission_level="revectorize")
        
        with ss:
            gs = GraphStore(ss, llm_executor_callback=llm_executor_callback)
            docs = ss.list_documents()
            total_docs = len(docs)
            task.log(f"Found {total_docs} documents to process for graph generation.")

            for i, doc in enumerate(docs):
                if task.cancellation_event.is_set():
                    task.log("Graph generation cancelled.", level="WARNING")
                    break
                
                doc_id = doc.get("doc_id")
                doc_name = Path(doc.get("file_path", "Unknown")).name
                task.set_file_info(file_name=doc_name, total_files=total_docs)
                task.log(f"Building graph for document {i+1}/{total_docs}: {doc_name}")
                
                gs.build_graph_for_document(doc_id, guidance=request_data.get("ontology"))
                task.set_progress(int(100 * (i + 1) / total_docs))
        
        if task.cancellation_event.is_set():
            task.result = {"message": "Graph generation cancelled."}
        else:
            task.result = {"message": "Graph generation completed successfully."}
            task.log("Graph generation finished.")

    except Exception as e:
        task.log(f"Error during graph generation: {e}", level="CRITICAL")
        trace_exception(e)
        raise e
    finally:
        db.close()


def _update_graph_task(task: Task, username: str, datastore_id: str, request_data: dict):
    if not GraphStore:
        raise ImportError("GraphStore is not available.")
        
    db = next(get_db())
    try:
        llm_client = build_lollms_client_from_params(
            username=username,
            binding_alias=request_data.get("model_binding"),
            model_name=request_data.get("model_name")
        )
        def llm_executor_callback(prompt: str) -> str:
            return llm_client.generate_text(prompt, max_new_tokens=2048)
        
        ss = get_safe_store_instance(username, datastore_id, db, permission_level="revectorize")
        
        with ss:
            gs = GraphStore(ss, llm_executor_callback=llm_executor_callback)
            docs = ss.list_documents()
            total_docs = len(docs)
            task.log(f"Checking {total_docs} documents for graph updates.")

            for i, doc in enumerate(docs):
                if task.cancellation_event.is_set():
                    break
                doc_id = doc.get("doc_id")
                gs.build_graph_for_document(doc_id, guidance=request_data.get("ontology"))
                task.set_progress(int(100 * (i + 1) / total_docs))

        if task.cancellation_event.is_set():
            task.result = {"message": "Graph update cancelled."}
        else:
            task.result = {"message": "Graph update completed successfully."}
            task.log("Graph update finished.")

    except Exception as e:
        task.log(f"Error during graph update: {e}", level="CRITICAL")
        trace_exception(e)
        raise e
    finally:
        db.close()

# --- SafeStore File Management API (now per-datastore) ---
store_files_router = APIRouter(prefix="/api/store/{datastore_id}", tags=["SafeStore RAG & File Management"])

@store_files_router.get("/details", response_model=DataStoreDetails)
async def get_datastore_details(
    datastore_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    try:
        # This will also handle permission checks
        ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_query")
        
        datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
        if not datastore_record:
             raise HTTPException(status_code=404, detail="Datastore not found")

        owner_username = datastore_record.owner.username

        db_path = get_datastore_db_path(owner_username, datastore_id)
        
        size_bytes = 0
        if db_path.exists():
            size_bytes = os.path.getsize(db_path)
        
        chunk_count = 0
        nodes_count = 0
        edges_count = 0
        with ss:
            chunk_count = ss.db.count('chunks')
            if GraphStore:
                try:
                    gs = GraphStore(ss)
                    nodes_count = gs.count_nodes()
                    edges_count = gs.count_relationships()
                except Exception as graph_err:
                    print(f"Could not get graph stats for datastore {datastore_id}: {graph_err}")

        return DataStoreDetails(
            size_bytes=size_bytes, 
            chunk_count=chunk_count,
            graph_nodes_count=nodes_count,
            graph_edges_count=edges_count
        )
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Error getting datastore details: {e}")

@store_files_router.post("/upload-files", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED) 
async def upload_rag_documents_to_datastore(
    datastore_id: str,
    files: List[UploadFile] = File(...),
    metadata_option: str = Form("none"),
    manual_metadata_json: str = Form("null"),
    vectorize_with_metadata: bool = Form(True),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> TaskInfo:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_write")
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    datastore_docs_path = get_user_datastore_root_path(datastore_record.owner.username) / "safestore_docs" / datastore_id
    datastore_docs_path.mkdir(parents=True, exist_ok=True)
    
    saved_file_paths = []
    for file_upload in files:
        s_filename = secure_filename(file_upload.filename or f"upload_{uuid.uuid4().hex[:8]}")
        target_file_path = datastore_docs_path / s_filename
        try:
            with open(target_file_path, "wb") as buffer: shutil.copyfileobj(file_upload.file, buffer)
            saved_file_paths.append(str(target_file_path))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file {s_filename}: {e}")
        finally: await file_upload.close()

    db_task = task_manager.submit_task(
        name=f"Add files to DataStore: {datastore_record.name}",
        target=_upload_rag_files_task,
        args=(current_user.username, datastore_id, saved_file_paths, metadata_option, manual_metadata_json, vectorize_with_metadata),
        description=f"Adding {len(files)} files to the '{datastore_record.name}' DataStore.",
        owner_username=current_user.username
    )
    return db_task

@store_files_router.get("/files", response_model=List[SafeStoreDocumentInfo])
async def list_rag_documents_in_datastore(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[SafeStoreDocumentInfo]:
    if not safe_store: 
        return []
    ss = get_safe_store_instance(current_user.username, datastore_id, db) 
    managed_docs = []
    try:
        with ss: 
            stored_meta = ss.list_documents()
        
        for doc_meta in stored_meta:
            original_path_str = doc_meta.get("file_path")
            if original_path_str:
                filename = Path(original_path_str).name
                managed_docs.append(SafeStoreDocumentInfo(filename=filename, metadata=doc_meta.get("metadata")))

    except Exception as e: 
        raise HTTPException(status_code=500, detail=f"Error listing RAG docs for datastore {datastore_id}: {e}")
    
    unique_docs = {doc.filename: doc for doc in managed_docs}
    sorted_unique_docs = sorted(list(unique_docs.values()), key=lambda x: x.filename)
    
    return sorted_unique_docs


@store_files_router.delete("/files/{filename}") 
async def delete_rag_document_from_datastore(datastore_id: str, filename: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_write")
    
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    s_filename = secure_filename(filename)
    if not s_filename or s_filename != filename: raise HTTPException(status_code=400, detail="Invalid filename.")
    
    datastore_docs_path = get_user_datastore_root_path(datastore_record.owner.username) / "safestore_docs" / datastore_id
    file_to_delete_path = datastore_docs_path / s_filename
    if not file_to_delete_path.is_file(): raise HTTPException(status_code=404, detail=f"Document '{s_filename}' not found in datastore {datastore_id}.")
    
    try:
        with ss: ss.delete_document_by_path(str(file_to_delete_path))
        file_to_delete_path.unlink()
        return {"message": f"Document '{s_filename}' deleted successfully from datastore {datastore_id}."}
    except Exception as e:
        if file_to_delete_path.exists(): raise HTTPException(status_code=500, detail=f"Could not delete '{s_filename}' from datastore {datastore_id}: {e}")
        else: return {"message": f"Document '{s_filename}' file deleted, potential DB cleanup issue in datastore {datastore_id}."}

@store_files_router.post("/files/batch-delete")
async def batch_delete_rag_documents_from_datastore(
    datastore_id: str, 
    request: DeleteFilesRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user), 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_write")
    
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    datastore_docs_path = get_user_datastore_root_path(datastore_record.owner.username) / "safestore_docs" / datastore_id

    deleted_count = 0
    failed_files = []

    with ss:
        for filename in request.filenames:
            s_filename = secure_filename(filename)
            if not s_filename or s_filename != filename:
                failed_files.append(filename)
                continue
            
            file_to_delete_path = datastore_docs_path / s_filename
            
            try:
                # This will remove embeddings from the DB.
                # It doesn't raise an error if the document doesn't exist in the DB.
                ss.delete_document_by_path(str(file_to_delete_path))

                # If file exists on disk, delete it. If it doesn't, that's fine too.
                if file_to_delete_path.is_file():
                    file_to_delete_path.unlink()
                
                deleted_count += 1
            except Exception as e:
                # This will catch file permission errors etc.
                print(f"Error during deletion of {filename}: {e}")
                failed_files.append(filename)

    return {
        "message": f"Deleted {deleted_count} documents. Failed to delete {len(failed_files)} documents.",
        "deleted_count": deleted_count,
        "failed_files": failed_files
    }

@store_files_router.post("/query", response_model=List[Dict])
async def query_datastore(
    datastore_id: str,
    request_data: DataStoreQueryRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[Dict]:
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db)
        with ss:
            results = ss.query(
                request_data.query, 
                top_k=request_data.top_k, 
                min_similarity_percent=request_data.min_similarity_percent
            )
        sanitized_results = _sanitize_numpy(results)
        return sanitized_results
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Error querying datastore: {e}")

@store_files_router.post("/graph/generate", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def generate_datastore_graph(
    datastore_id: str,
    request_data: GraphGenerationRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> TaskInfo:
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="revectorize")
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record:
        raise HTTPException(status_code=404, detail="Datastore metadata not found in main DB.")

    try:
        db_task = task_manager.submit_task(
            name=f"Generate Graph for: {datastore_record.name}",
            target=_generate_graph_task,
            args=(current_user.username, datastore_id, request_data.model_dump()),
            description=f"Generating knowledge graph for '{datastore_record.name}'. This may take a while.",
            owner_username=current_user.username
        )
        return db_task
    except PermissionError as e:
        raise HTTPException(status_code=430, detail=str(e))
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"An error occurred during graph generation: {e}")

@store_files_router.post("/graph/update", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def update_datastore_graph(
    datastore_id: str,
    request_data: GraphGenerationRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> TaskInfo:
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="revectorize")
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record:
        raise HTTPException(status_code=404, detail="Datastore metadata not found in main DB.")

    try:
        db_task = task_manager.submit_task(
            name=f"Update Graph for: {datastore_record.name}",
            target=_update_graph_task,
            args=(current_user.username, datastore_id, request_data.model_dump()),
            description=f"Updating knowledge graph for '{datastore_record.name}'.",
            owner_username=current_user.username
        )
        return db_task
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"An error occurred during graph update: {e}")

@store_files_router.get("/graph", response_model=Dict)
async def get_datastore_graph(
    datastore_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict:
    if not GraphStore:
        raise HTTPException(status_code=501, detail="GraphStore is not available.")
    
    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db)
        with ss:
            gs = GraphStore(ss, llm_executor_callback=None)
            nodes = gs.get_all_nodes_for_visualization(limit=5000)
            edges = gs.get_all_relationships_for_visualization(limit=10000)
        
        sanitized_nodes = _sanitize_numpy(nodes)
        sanitized_edges = _sanitize_numpy(edges)

        return {"nodes": sanitized_nodes, "edges": sanitized_edges}
    except Exception as e:
        trace_exception(e)
        return {"nodes": [], "edges": []}


@store_files_router.post("/graph/query", response_model=List[Dict])
async def query_datastore_graph(
    datastore_id: str,
    request_data: GraphQueryRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[Dict]:
    if not GraphStore:
        raise HTTPException(status_code=501, detail="GraphStore is not available.")
    
    try:
        llm_client = build_lollms_client_from_params(username=current_user.username)
        def llm_executor_callback(prompt: str) -> str:
            return llm_client.generate_text(prompt, max_new_tokens=2048)
            
        ss = get_safe_store_instance(current_user.username, datastore_id, db)
        with ss:
            gs = GraphStore(ss, llm_executor_callback=llm_executor_callback)
            results = gs.query_graph(request_data.query, output_mode="chunks_summary")
        sanitized_results = _sanitize_numpy(results)
        return sanitized_results
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Error querying graph: {e}")
    
@store_files_router.delete("/graph", status_code=status.HTTP_200_OK)
async def wipe_datastore_graph(
    datastore_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not GraphStore:
        raise HTTPException(status_code=501, detail="GraphStore is not available.")
    
    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="revectorize")
        with ss:
            gs = GraphStore(ss)
            gs.delete_all_graph_data()
        return {"message": "Graph data has been successfully wiped."}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"An error occurred while wiping the graph: {e}")

@store_files_router.post("/graph/nodes", response_model=Dict)
async def add_graph_node(
    datastore_id: str,
    node_data: NodeData,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not GraphStore: raise HTTPException(status_code=501, detail="GraphStore not available.")
    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_write")
        with ss:
            gs = GraphStore(ss)
            node_id = gs.add_node(node_data.label, node_data.properties)
        return _sanitize_numpy({"id": node_id, "label": node_data.label, "properties": node_data.properties})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@store_files_router.put("/graph/nodes/{node_id}", response_model=Dict)
async def update_graph_node(
    datastore_id: str,
    node_id: int,
    node_data: NodeData,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not GraphStore: raise HTTPException(status_code=501, detail="GraphStore not available.")
    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_write")
        with ss:
            gs = GraphStore(ss)
            gs.update_node(node_id, node_data.label, node_data.properties)
        return _sanitize_numpy({"id": node_id, "label": node_data.label, "properties": node_data.properties})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@store_files_router.delete("/graph/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_graph_node(
    datastore_id: str,
    node_id: int,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not GraphStore: raise HTTPException(status_code=501, detail="GraphStore not available.")
    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_write")
        with ss:
            gs = GraphStore(ss)
            gs.delete_node(node_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@store_files_router.post("/graph/edges", response_model=Dict)
async def add_graph_edge(
    datastore_id: str,
    edge_data: EdgeData,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not GraphStore: raise HTTPException(status_code=501, detail="GraphStore not available.")
    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_write")
        with ss:
            gs = GraphStore(ss)
            edge_id = gs.add_relationship(edge_data.source_id, edge_data.target_id, edge_data.label, edge_data.properties)
        return _sanitize_numpy({"id": edge_id, **edge_data.model_dump()})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@store_files_router.delete("/graph/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_graph_edge(
    datastore_id: str,
    edge_id: int,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not GraphStore: raise HTTPException(status_code=501, detail="GraphStore not available.")
    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_write")
        with ss:
            gs = GraphStore(ss)
            gs.delete_relationship(edge_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

datastore_router = APIRouter(prefix="/api/datastores", tags=["RAG DataStores"])

@datastore_router.get("/available-vectorizers", response_model=List[Dict[str, Any]])
async def list_available_vectorizers(db: Session = Depends(get_db)):
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    try:
        # Get Display Mode
        mode_setting = settings.get("rag_model_display_mode", "mixed") # 'original', 'aliased', 'mixed'
        
        # Query active bindings only
        rag_bindings = db.query(DBRAGBinding).filter(DBRAGBinding.is_active == True).all()
        results = []

        for binding in rag_bindings:
            try:
                # Ensure config is a dict (handle potential DB string/json issues)
                binding_config = binding.config
                if isinstance(binding_config, str):
                    try:
                        binding_config = json.loads(binding_config)
                    except Exception:
                        binding_config = {}
                if not isinstance(binding_config, dict):
                    binding_config = {}

                # Fetch raw models from safe_store
                raw_models_list = safe_store.SafeStore.list_models(
                    vectorizer_name=binding.name,
                    vectorizer_config=binding_config
                )
                
                # Normalize raw model names and ensure uniqueness
                raw_names = set()
                if raw_models_list:
                    for m in raw_models_list:
                        if isinstance(m, str):
                            raw_names.add(m)
                        elif isinstance(m, dict):
                            # Try 'model_name' then 'name'
                            name = m.get("model_name") or m.get("name")
                            if name:
                                raw_names.add(name)
                        else:
                            # Try attribute access for objects
                            if hasattr(m, "model_name"):
                                raw_names.add(m.model_name)
                            elif hasattr(m, "name"):
                                raw_names.add(m.name)
                
                sorted_raw_names = sorted(list(raw_names))
                
                # Apply Aliasing Logic
                aliases = {}
                if binding.model_aliases:
                    try:
                        if isinstance(binding.model_aliases, str):
                            aliases = json.loads(binding.model_aliases)
                        else:
                            aliases = binding.model_aliases
                    except Exception as e:
                        print(f"Error parsing aliases for binding {binding.alias}: {e}")
                        pass

                processed_models = []
                
                if not sorted_raw_names:
                    # If no models returned (e.g. TF-IDF or just failed), provide a default option representing the binding itself
                    processed_models.append({"name": binding.alias, "value": ""})
                else:
                    for raw_name in sorted_raw_names:
                        alias_info = aliases.get(raw_name)
                        alias_name = None
                        if alias_info:
                            alias_name = alias_info.get("name") if isinstance(alias_info, dict) else alias_info
                        
                        entry = {"value": raw_name}
                        
                        if mode_setting == 'aliased':
                            if alias_name:
                                entry["name"] = alias_name
                                processed_models.append(entry)
                        elif mode_setting == 'original':
                            entry["name"] = raw_name
                            processed_models.append(entry)
                        else: # mixed
                            entry["name"] = alias_name or raw_name
                            processed_models.append(entry)
                
                    # Sort models by name
                    processed_models.sort(key=lambda x: x['name'])

                    # [FIX] Fallback: If filtering resulted in empty list (e.g. aliased mode but no aliases set), 
                    # show original names so the user is not left with an empty list.
                    if not processed_models and sorted_raw_names:
                         for raw_name in sorted_raw_names:
                            processed_models.append({"name": raw_name, "value": raw_name})
                         processed_models.sort(key=lambda x: x['name'])

                results.append({
                    "id": binding.id,
                    "alias": binding.alias, # The binding name shown to user
                    "vectorizer_name": binding.name, # The raw type (ollama, etc)
                    "vectorizer_config": binding_config,
                    "models": processed_models
                })

            except Exception as e:
                print(f"Error listing models for binding {binding.alias}: {e}")
                trace_exception(e)
                # Include binding even if model listing fails, so user can potentially configure manually
                results.append({
                    "id": binding.id,
                    "alias": binding.alias,
                    "vectorizer_name": binding.name,
                    "vectorizer_config": binding.config or {},
                    "models": [{"name": f"{binding.alias} (Error loading models)", "value": ""}],
                    "error": str(e)
                })

        return results

    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=str(e))

@datastore_router.get("/bindings/{binding_id}/models", response_model=List[str])
async def get_rag_binding_models_public(binding_id: int, db: Session = Depends(get_db)):
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    binding = db.query(DBRAGBinding).filter(DBRAGBinding.id == binding_id, DBRAGBinding.is_active == True).first()
    if not binding:
        raise HTTPException(status_code=404, detail="RAG Binding not found.")
    
    try:
        raw_models = safe_store.SafeStore.list_models(
            vectorizer_name=binding.name, 
            vectorizer_config=binding.config or {}
        )
        
        models_list = [item if isinstance(item, str) else item.get("model_name") for item in raw_models if (isinstance(item, str) or item.get("model_name"))]
        
        return sorted(list(set(models_list))) # Unique and sorted
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Could not list models: {e}")

@datastore_router.get("", response_model=List[DataStorePublic])
async def list_my_datastores(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[DataStorePublic]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first() 
    if not user_db_record: 
        raise HTTPException(status_code=404, detail="User database record not found for authenticated user.") 

    owned_datastores_db = db.query(DBDataStore).filter(DBDataStore.owner_user_id == user_db_record.id).order_by(DBDataStore.name).all()
    
    shared_links_query = db.query(
        DBSharedDataStoreLink, DBDataStore
    ).join(
        DBDataStore, DBSharedDataStoreLink.datastore_id == DBDataStore.id
    ).filter(
        DBSharedDataStoreLink.shared_with_user_id == user_db_record.id 
    ).order_by(
        DBDataStore.name
    )
    shared_links_query = shared_links_query.options(
        joinedload(DBSharedDataStoreLink.datastore).joinedload(DBDataStore.owner)
    )
    
    shared_links_and_datastores_db = shared_links_query.all() 

    response_list = []
    for ds_db in owned_datastores_db:
        response_list.append(DataStorePublic(
            id=ds_db.id, name=ds_db.name, description=ds_db.description,
            owner_username=current_user.username, 
            permission_level='owner',
            vectorizer_name=ds_db.vectorizer_name,
            vectorizer_config=ds_db.vectorizer_config or {},
            chunk_size=ds_db.chunk_size,
            chunk_overlap=ds_db.chunk_overlap,
            created_at=ds_db.created_at, updated_at=ds_db.updated_at
        ))
    for link, ds_db in shared_links_and_datastores_db: 
        if not any(r.id == ds_db.id for r in response_list):
             response_list.append(DataStorePublic(
                id=ds_db.id, name=ds_db.name, description=ds_db.description,
                owner_username=ds_db.owner.username, 
                permission_level=link.permission_level,
                vectorizer_name=ds_db.vectorizer_name,
                vectorizer_config=ds_db.vectorizer_config or {},
                chunk_size=ds_db.chunk_size,
                chunk_overlap=ds_db.chunk_overlap,
                created_at=ds_db.created_at, updated_at=ds_db.updated_at
            ))
    return response_list

@datastore_router.post("", response_model=DataStorePublic, status_code=status.HTTP_201_CREATED)
async def create_datastore(ds_create: DataStoreCreate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DBDataStore:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if db.query(DBDataStore).filter_by(owner_user_id=user_db_record.id, name=ds_create.name).first(): 
        raise HTTPException(status_code=400, detail=f"DataStore '{ds_create.name}' already exists.")
    
    new_ds_db_obj = DBDataStore(
        owner_user_id=user_db_record.id, 
        name=ds_create.name, 
        description=ds_create.description,
        vectorizer_name=ds_create.vectorizer_name,
        vectorizer_config=ds_create.vectorizer_config,
        chunk_size=ds_create.chunk_size if ds_create.chunk_size is not None else settings.get("default_chunk_size"),
        chunk_overlap=ds_create.chunk_overlap if ds_create.chunk_overlap is not None else settings.get("default_chunk_overlap")
    )
    try:
        db.add(new_ds_db_obj)
        db.commit()
        db.refresh(new_ds_db_obj)
        # This initializes the .db file on creation
        get_safe_store_instance(current_user.username, new_ds_db_obj.id, db)
        
        data_store_public = DataStorePublic(
            name=new_ds_db_obj.name,
            description=new_ds_db_obj.description,
            id=new_ds_db_obj.id,
            owner_username=current_user.username,
            created_at=new_ds_db_obj.created_at,
            updated_at=new_ds_db_obj.updated_at,
            permission_level='owner',
            vectorizer_name=new_ds_db_obj.vectorizer_name,
            vectorizer_config=new_ds_db_obj.vectorizer_config or {},
            chunk_size=new_ds_db_obj.chunk_size,
            chunk_overlap=new_ds_db_obj.chunk_overlap
        )
        return data_store_public
    except Exception as e: 
        trace_exception(e)
        db.rollback(); 
        raise HTTPException(status_code=500, detail=f"DB error: {e}")


@datastore_router.put("/{datastore_id}", response_model=DataStorePublic)
async def update_datastore(datastore_id: str, ds_update: DataStoreEdit, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DBDataStore:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    
    ds_db_obj = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not ds_db_obj: raise HTTPException(status_code=404, detail="DataStore not found.")
    
    get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_write")

    if ds_update.name != ds_db_obj.name:
        existing_ds = db.query(DBDataStore).filter(DBDataStore.owner_user_id == ds_db_obj.owner_user_id, DBDataStore.name == ds_update.name, DBDataStore.id != datastore_id).first()
        if existing_ds: raise HTTPException(status_code=400, detail=f"A DataStore with the name '{ds_update.name}' already exists for the owner.")

    ds_db_obj.name = ds_update.name
    ds_db_obj.description = ds_update.description
    try:
        db.commit(); db.refresh(ds_db_obj)
        
        permission_level = 'owner' if ds_db_obj.owner_user_id == user_db_record.id else 'read_write'
        
        return DataStorePublic(
             id=ds_db_obj.id, name=ds_db_obj.name, description=ds_db_obj.description,
             owner_username=ds_db_obj.owner.username, permission_level=permission_level,
             created_at=ds_db_obj.created_at, updated_at=ds_db_obj.updated_at,
             vectorizer_name=ds_db_obj.vectorizer_name,
             vectorizer_config=ds_db_obj.vectorizer_config or {},
             chunk_size=ds_db.chunk_size,
             chunk_overlap=ds_db.chunk_overlap
        )
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error updating datastore: {e}")


@datastore_router.delete("/{datastore_id}", status_code=status.HTTP_200_OK)
async def delete_datastore(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    
    ds_db_obj = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not ds_db_obj: raise HTTPException(status_code=404, detail="DataStore not found.")
    if ds_db_obj.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete a DataStore.")
    
    owner_username = ds_db_obj.owner.username
    ds_file_path = get_datastore_db_path(owner_username, datastore_id)
    ds_lock_file_path = Path(f"{ds_file_path}.lock")
    ds_docs_path = get_user_datastore_root_path(owner_username) / "safestore_docs" / datastore_id

    try:
        db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id).delete(synchronize_session=False)
        db.delete(ds_db_obj)
        db.commit()
        
        if owner_username in user_sessions and datastore_id in user_sessions[owner_username].get("safe_store_instances", {}):
            del user_sessions[owner_username]["safe_store_instances"][datastore_id]
        
        # Using background tasks for file deletion is safer for responsiveness
        from fastapi import BackgroundTasks
        background_tasks = BackgroundTasks()
        background_tasks.add_task(shutil.rmtree, ds_docs_path, ignore_errors=True)
        background_tasks.add_task(ds_file_path.unlink, missing_ok=True)
        background_tasks.add_task(ds_lock_file_path.unlink, missing_ok=True)
            
        return {"message": f"DataStore '{ds_db_obj.name}' and its associated files are being deleted."}
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error deleting datastore: {e}")

@datastore_router.get("/{datastore_id}/shared-with", response_model=List[SharedWithUserPublic])
async def get_datastore_shared_with_list(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db: raise HTTPException(status_code=404, detail="Owner user not found.")

    ds_to_check = db.query(DBDataStore).filter(DBDataStore.id == datastore_id, DBDataStore.owner_user_id == owner_user_db.id).first()
    if not ds_to_check: raise HTTPException(status_code=404, detail="DataStore not found or you are not the owner.")

    shared_links = db.query(DBSharedDataStoreLink).options(joinedload(DBSharedDataStoreLink.shared_with_user)).filter(DBSharedDataStoreLink.datastore_id == datastore_id).all()
    
    response = [
        SharedWithUserPublic(
            user_id=link.shared_with_user.id,
            username=link.shared_with_user.username,
            icon=link.shared_with_user.icon,
            permission_level=link.permission_level
        ) for link in shared_links
    ]
    return response


@datastore_router.post("/{datastore_id}/share", status_code=status.HTTP_201_CREATED)
async def share_datastore(datastore_id: str, share_request: DataStoreShareRequest, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db: raise HTTPException(status_code=404, detail="Owner user not found.")

    ds_to_share = db.query(DBDataStore).filter(DBDataStore.id == datastore_id, DBDataStore.owner_user_id == owner_user_db.id).first()
    if not ds_to_share: raise HTTPException(status_code=404, detail="DataStore not found or you are not the owner.")

    target_user_db = db.query(DBUser).filter(DBUser.username == share_request.target_username).first()
    if not target_user_db: raise HTTPException(status_code=404, detail=f"Target user '{share_request.target_username}' not found.")
    
    if owner_user_db.id == target_user_db.id:
        raise HTTPException(status_code=400, detail="Cannot share a datastore with yourself.")

    existing_link = db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id, shared_with_user_id=target_user_db.id).first()
    if existing_link:
        if existing_link.permission_level != share_request.permission_level:
            existing_link.permission_level = share_request.permission_level
            db.commit()
            return {"message": f"DataStore '{ds_to_share.name}' sharing permission updated for user '{target_user_db.username}'."}
        return {"message": f"DataStore '{ds_to_share.name}' already shared with user '{target_user_db.username}' with this permission."}

    new_link = DBSharedDataStoreLink(
        datastore_id=datastore_id,
        shared_with_user_id=target_user_db.id,
        permission_level=share_request.permission_level
    )
    try:
        db.add(new_link); db.commit()
        return {"message": f"DataStore '{ds_to_share.name}' shared successfully with user '{target_user_db.username}'."}
    except IntegrityError: 
        db.rollback(); raise HTTPException(status_code=400, detail="Sharing conflict (race condition).")
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error sharing datastore: {e}")

@datastore_router.delete("/{datastore_id}/share/{target_user_id}", status_code=status.HTTP_200_OK)
async def unshare_datastore(datastore_id: str, target_user_id: int, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db: raise HTTPException(status_code=404, detail="Owner user not found.")

    ds_to_unshare = db.query(DBDataStore).filter(DBDataStore.id == datastore_id, DBDataStore.owner_user_id == owner_user_db.id).first()
    if not ds_to_unshare: raise HTTPException(status_code=404, detail="DataStore not found or you are not the owner.")
        
    target_user_db = db.query(DBUser).filter(DBUser.id == target_user_id).first()
    if not target_user_db: raise HTTPException(status_code=404, detail=f"Target user with ID '{target_user_id}' not found.")

    link_to_delete = db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id, shared_with_user_id=target_user_db.id).first()
    if not link_to_delete:
        raise HTTPException(status_code=404, detail=f"DataStore was not shared with user '{target_user_db.username}'.")

    try:
        db.delete(link_to_delete); db.commit()
        return {"message": f"Sharing for DataStore '{ds_to_unshare.name}' has been revoked from user '{target_user_db.username}'."}
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error revoking share link: {e}")