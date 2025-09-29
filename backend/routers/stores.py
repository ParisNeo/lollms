import shutil
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Any
import traceback
from ascii_colors import trace_exception

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
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError


from werkzeug.utils import secure_filename


# Local Application Imports
from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.datastore import DataStore as DBDataStore, SharedDataStoreLink as DBSharedDataStoreLink
from backend.models import (
    UserAuthDetails,
    DataStoreCreate,
    DataStoreEdit,
    DataStoreShareRequest,
    DataStorePublic,
    DataStoreBase,
    SharedWithUserPublic,
    SafeStoreDocumentInfo,
    TaskInfo
)
from backend.session import get_datastore_db_path, build_lollms_client_from_params
from backend.db.models.db_task import DBTask
# safe_store is expected to be installed
try:
    import safe_store
    from safe_store import GraphStore
except ImportError:
    print(
        "WARNING: safe_store library not found. RAG features will be disabled. Install with: pip install safe_store[all]"
    )
    safe_store = None
    GraphStore = None
    SafeStoreLogLevel = None

from backend.session import (
    get_current_active_user,
    get_safe_store_instance,
    get_user_datastore_root_path,
    user_sessions
)
from backend.task_manager import task_manager, Task

# --- NEW Pydantic Models for Graph Operations ---
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

class NodeData(BaseModel):
    label: str
    properties: Dict[str, Any] = {}

class EdgeData(BaseModel):
    source_id: int
    target_id: int
    label: str
    properties: Dict[str, Any] = {}


# --- Task Functions ---
def _to_task_info(db_task: DBTask) -> TaskInfo:
    """Converts a DBTask SQLAlchemy model to a TaskInfo Pydantic model."""
    if not db_task:
        return None
    return TaskInfo(
        id=db_task.id, name=db_task.name, description=db_task.description,
        status=db_task.status, progress=db_task.progress,
        logs=[log for log in (db_task.logs or [])], result=db_task.result, error=db_task.error,
        created_at=db_task.created_at, started_at=db_task.started_at, completed_at=db_task.completed_at,
        file_name=db_task.file_name, total_files=db_task.total_files,
        owner_username=db_task.owner.username if db_task.owner else "System"
    )


def _upload_rag_files_task(task: Task, username: str, datastore_id: str, file_paths: List[str], vectorizer_name: str):
    db = next(get_db())
    ss = None
    try:
        ss = get_safe_store_instance(username, datastore_id, db, permission_level="read_write")
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
                    ss.add_document(str(file_path), vectorizer_name=vectorizer_name)
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

def _revectorize_datastore_task(task: Task, username: str, datastore_id: str, vectorizer_name: str):
    db = next(get_db())
    ss = None
    try:
        ss = get_safe_store_instance(username, datastore_id, db, permission_level="revectorize")
        
        task.log(f"Starting revectorization of datastore '{datastore_id}' with vectorizer '{vectorizer_name}'.")
        task.set_progress(10)
        
        with ss:
            ss.revectorize(vectorizer_name)
        
        task.set_progress(100)
        task.result = {"message": f"Datastore '{datastore_id}' successfully revectorized with '{vectorizer_name}'."}
        task.log("Revectorization completed successfully.")

    except Exception as e:
        task.log(f"Error during revectorization: {e}", level="CRITICAL")
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
        gs = GraphStore(ss, llm_executor_callback=llm_executor_callback)
        
        with ss:
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
        gs = GraphStore(ss, llm_executor_callback=llm_executor_callback)
        
        with ss:
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

@store_files_router.get("/vectorizers", response_model=Dict[str, List[Dict[str, str]]])
async def list_datastore_vectorizers(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, List[Dict[str, str]]]:
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    ss = get_safe_store_instance(current_user.username, datastore_id, db)
    
    try:
        with ss:
            methods_in_db = ss.list_vectorization_methods()
            in_store_formatted = [{"name": m.get("method_name"), "method_name": f"{m.get('method_name')} (dim: {m.get('vector_dim', 'N/A')})"} for m in methods_in_db if m.get("method_name")]
            in_store_formatted.sort(key=lambda x: x["name"])

            possible_names = ss.list_possible_vectorizer_names()
            all_possible_formatted = []
            for name in possible_names:
                display_text = name
                if name.startswith("tfidf:"): display_text = f"{name} (TF-IDF)"
                elif name.startswith("st:"): display_text = f"{name} (Sentence Transformer)"
                all_possible_formatted.append({"name": name, "method_name": display_text})
            all_possible_formatted.sort(key=lambda x: x["name"])

        return {
            "in_store": in_store_formatted,
            "all_possible": all_possible_formatted
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing vectorizers: {e}")

@store_files_router.post("/revectorize", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def revectorize_datastore(
    datastore_id: str,
    vectorizer_name: str = Form(...),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> TaskInfo:
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="revectorize")
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record: raise HTTPException(status_code=404, detail="Datastore metadata not found in main DB.")
    
    try:
        with ss: 
            all_vectorizers = {m['method_name'] for m in ss.list_vectorization_methods()} | set(ss.list_possible_vectorizer_names())
            if not (vectorizer_name in all_vectorizers or vectorizer_name.startswith("st:") or vectorizer_name.startswith("tfidf:")):
                 raise HTTPException(status_code=400, detail=f"Vectorizer '{vectorizer_name}' not found or invalid format.")
            
            db_task = task_manager.submit_task(
                name=f"Revectorize DataStore: {datastore_record.name}",
                target=_revectorize_datastore_task,
                args=(current_user.username, datastore_id, vectorizer_name),
                description=f"Revectorizing all documents in '{datastore_record.name}' with '{vectorizer_name}'.",
                owner_username=current_user.username
            )
            return _to_task_info(db_task)

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"An error occurred during revectorization: {e}")

@store_files_router.post("/upload-files", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED) 
async def upload_rag_documents_to_datastore(
    datastore_id: str,
    files: List[UploadFile] = File(...),
    vectorizer_name: str = Form(...),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> TaskInfo:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_write")
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    datastore_docs_path = get_user_datastore_root_path(datastore_record.owner.username) / "safestore_docs" / datastore_id
    datastore_docs_path.mkdir(parents=True, exist_ok=True)
    
    try:
        with ss: all_vectorizers = {m['method_name'] for m in ss.list_vectorization_methods()} | set(ss.list_possible_vectorizer_names())
        if not (vectorizer_name in all_vectorizers or vectorizer_name.startswith("st:") or vectorizer_name.startswith("tfidf:")):
             raise HTTPException(status_code=400, detail=f"Vectorizer '{vectorizer_name}' not found or invalid format for datastore {datastore_id}.")
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error checking vectorizer for datastore {datastore_id}: {e}")

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
        args=(current_user.username, datastore_id, saved_file_paths, vectorizer_name),
        description=f"Vectorizing and adding {len(files)} files to the '{datastore_record.name}' DataStore.",
        owner_username=current_user.username
    )
    return _to_task_info(db_task)

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
                managed_docs.append(SafeStoreDocumentInfo(filename=filename))

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
        return _to_task_info(db_task)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
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
        return _to_task_info(db_task)
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
        gs = GraphStore(ss, llm_executor_callback=None)
        nodes = gs.get_all_nodes_for_visualization(limit=5000)
        edges = gs.get_all_relationships_for_visualization(limit=10000)
        return {"nodes": nodes, "edges": edges}
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
        gs = GraphStore(ss, llm_executor_callback=llm_executor_callback)
        results = gs.query_graph(request_data.query, output_mode="chunks_summary")
        return results
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
        raise HTTPException(status_code=501, detail="GraphStore not available.")
    
    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="revectorize")
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
        gs = GraphStore(ss)
        node_id = gs.add_node(node_data.label, node_data.properties)
        return {"id": node_id, "label": node_data.label, "properties": node_data.properties}
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
        gs = GraphStore(ss)
        gs.update_node(node_id, node_data.label, node_data.properties)
        return {"id": node_id, "label": node_data.label, "properties": node_data.properties}
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
        gs = GraphStore(ss)
        edge_id = gs.add_relationship(edge_data.source_id, edge_data.target_id, edge_data.label, edge_data.properties)
        return {"id": edge_id, **edge_data.model_dump()}
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
        gs = GraphStore(ss)
        gs.delete_relationship(edge_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

datastore_router = APIRouter(prefix="/api/datastores", tags=["RAG DataStores"])

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
            created_at=ds_db.created_at, updated_at=ds_db.updated_at
        ))
    for link, ds_db in shared_links_and_datastores_db: 
        if not any(r.id == ds_db.id for r in response_list):
             response_list.append(DataStorePublic(
                id=ds_db.id, name=ds_db.name, description=ds_db.description,
                owner_username=ds_db.owner.username, 
                permission_level=link.permission_level,
                created_at=ds_db.created_at, updated_at=ds_db.updated_at
            ))
    return response_list

@datastore_router.post("", response_model=DataStorePublic, status_code=status.HTTP_201_CREATED)
async def create_datastore(ds_create: DataStoreCreate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DBDataStore:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if db.query(DBDataStore).filter_by(owner_user_id=user_db_record.id, name=ds_create.name).first(): 
        raise HTTPException(status_code=400, detail=f"DataStore '{ds_create.name}' already exists.")
    new_ds_db_obj = DBDataStore(owner_user_id=user_db_record.id, name=ds_create.name, description=ds_create.description)
    try:
        db.add(new_ds_db_obj)
        db.commit()
        db.refresh(new_ds_db_obj)
        get_safe_store_instance(current_user.username, new_ds_db_obj.id, db)
        
        data_store_public = DataStorePublic(
            name=new_ds_db_obj.name,
            description=new_ds_db_obj.description,
            id=new_ds_db_obj.id,
            owner_username=current_user.username,
            created_at=new_ds_db_obj.created_at,
            updated_at=new_ds_db_obj.updated_at,
            permission_level='owner'
        )
        return data_store_public
    except Exception as e: 
        trace_exception(e)
        db.rollback(); 
        raise HTTPException(status_code=500, detail=f"DB error: {e}")


@datastore_router.put("/{datastore_id}", response_model=DataStorePublic)
async def update_datastore(datastore_id: str, ds_update: DataStoreBase, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DBDataStore:
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
             created_at=ds_db_obj.created_at, updated_at=ds_db_obj.updated_at
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