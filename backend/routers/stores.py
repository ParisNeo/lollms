# backend/routers/stores.py
import re
import shutil
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Any
import traceback
import zipfile
import tempfile
from datetime import datetime
from ascii_colors import trace_exception
import os
from pydantic import BaseModel
from sqlalchemy.orm import joinedload
import json
import time

# Third-Party Imports
from fastapi import (
    HTTPException,
    Depends,
    File,
    UploadFile,
    Form,
    APIRouter,
    status,
    Body
)
from fastapi.responses import (
    Response
)
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
    SharedWithUserPublic,
    SafeStoreDocumentInfo,
    ScrapeRequest,
    DataStoreQueryRequest,
    SparqlQueryRequest,
    GraphHybridQueryRequest,
    DataStoreAnswerRequest,
    DataStoreAnswerResponse    
)

from backend.session import get_datastore_db_path, build_lollms_client_from_params
from backend.settings import settings
from backend.ws_manager import manager

# safe_store is expected to be installed
try:
    import safe_store
    from safe_store import GraphStore
    import numpy as np
except ImportError:
    safe_store = None
    GraphStore = None
    np = None

# ScrapeMaster Import
try:
    from scrapemaster import ScrapeMaster
except ImportError:
    try:
        import pipmaster as pm
        pm.install("ScrapeMaster")
        from scrapemaster import ScrapeMaster
    except Exception:
        ScrapeMaster = None

from backend.session import (
    get_current_active_user,
    get_safe_store_instance,
    get_user_datastore_root_path,
    user_sessions
)
from backend.task_manager import task_manager, Task
from backend.db.models.config import RAGBinding as DBRAGBinding
from backend.routers.files import extract_text_from_file_bytes

class DataStoreDetails(BaseModel):
    size_bytes: int
    chunk_count: int
    graph_nodes_count: int
    graph_edges_count: int
    
class GraphGenerationRequest(BaseModel):
    graph_type: str = "knowledge_graph"
    model_binding: Optional[str] = None
    model_name: Optional[str] = None
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

class DeleteFilesRequest(BaseModel):
    filenames: List[str]

class DataLakeChunkPoint(BaseModel):
    id: str
    document_id: str
    document_name: str
    chunk_index: int
    text_snippet: str
    full_text: str
    x: float
    y: float
    metadata: Optional[Dict[str, Any]] = None
    color: str

class DataLakeDocumentLegend(BaseModel):
    id: str
    name: str
    chunk_count: int
    color: str
    centroid: Dict[str, float]

class DataLakeResponse(BaseModel):
    points: List[DataLakeChunkPoint]
    documents: List[DataLakeDocumentLegend]
    total_chunks: int
    dimensions: int = 2
    reduction_method: str = "PCA"

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
    if isinstance(data, (np.float64, np.float16, np.float32, np.float64)):
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

                    stats = ss.add_document(
                        str(file_path),
                        metadata=metadata,
                        vectorize_with_metadata=vectorize_with_metadata if metadata else False,
                    )
                    
                    num_added = stats.get('num_chunks_added', 0) if isinstance(stats, dict) else 1
                    num_ignored = stats.get('num_chunks_ignored', 0) if isinstance(stats, dict) else 0

                    if num_added > 0:
                        processed_count += 1
                        msg = f"Successfully added {num_added} chunks from {file_path.name}."
                        if num_ignored > 0:
                            msg += f" (Ignored {num_ignored} invalid/empty chunks)"
                        task.log(msg)
                    else:
                        error_count += 1
                        task.log(f"Skipped {file_path.name}: No valid text chunks extracted.", level="WARNING")

                except Exception as e:
                    error_count += 1
                    task.log(f"Error processing {file_path.name}: {e}", level="ERROR")

                progress = int(100 * (i + 1) / total_files)
                task.set_progress(progress)

        # Invalidate in-memory cached instance so subsequent queries/file listings reload fresh state
        if username in user_sessions and datastore_id in user_sessions[username].get("safe_store_instances", {}):
            del user_sessions[username]["safe_store_instances"][datastore_id]

        manager.broadcast_sync({"type": "datastore_updated", "datastore_id": datastore_id})
        task.result = {"message": f"Processing complete. Added {processed_count} files. Encountered {error_count} issues."}

    except Exception as e:
        traceback.print_exc()
        raise e
    finally:
        db.close()

def _scrape_url_task(task: Task, username: str, datastore_id: str, url: str, depth: int):
    from backend.security import validate_url
    validate_url(url)
    
    if not ScrapeMaster:
        raise ImportError("ScrapeMaster is not installed.")

    db = next(get_db())
    target_file_path = None 
    
    try:
        datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
        if not datastore_record:
            raise Exception(f"Datastore with ID {datastore_id} not found.")

        ss = get_safe_store_instance(username, datastore_id, db, permission_level="read_write")
        task.log(f"Initializing scraper for URL: {url} (Depth: {depth})")
        
        results = None
        try:
            scraper = ScrapeMaster(url, strategy=["selenium", "beautifulsoup"], headless=True)
            results = scraper.scrape_all(max_depth=depth, convert_to_markdown=True)
        except Exception as e:
            task.log(f"Selenium scraping failed: {e}. Falling back to BeautifulSoup strategy.", level="WARNING")
            scraper = ScrapeMaster(url, strategy=["beautifulsoup"], headless=True)
            results = scraper.scrape_all(max_depth=depth, convert_to_markdown=True)

        if not results:
            error_msg = getattr(scraper, "get_last_error", lambda: "Unknown scraping error.")() or "Unknown scraping error."
            task.log(f"Scraping returned no results: {error_msg}", level="ERROR")
            raise Exception(error_msg)
            
        markdown_content = results.get('markdown')
        if not markdown_content:
             texts = results.get('texts', [])
             markdown_content = "\n\n".join(texts)
        
        if not markdown_content:
             task.log("No content found at the given URL.", level="WARNING")
             return

        safe_url_name = "".join(c for c in url if c.isalnum() or c in ('-', '_')).rstrip()[:50]
        timestamp = int(time.time())
        filename = f"scraped_{safe_url_name}_{timestamp}.md"
        
        datastore_docs_path = get_user_datastore_root_path(datastore_record.owner.username) / "safestore_docs" / datastore_id
        datastore_docs_path.mkdir(parents=True, exist_ok=True)
        
        target_file_path = datastore_docs_path / filename
        with open(target_file_path, "w", encoding="utf-8") as f:
            f.write(f"# Scraped from {url}\n\n")
            f.write(markdown_content)
            
        task.log(f"Content saved to {filename}. Indexing to SafeStore...")
        
        with ss:
            stats = ss.add_document(str(target_file_path))
            num_added = stats.get('num_chunks_added', 0) if isinstance(stats, dict) else 1
            task.log(f"Successfully indexed {num_added} chunks from scraped content.")
            
        visited_urls = results.get('visited_urls', [])
        task.result = {"message": f"Scraping complete. Indexed content from {len(visited_urls)} page(s)."}

        try:
            if target_file_path and target_file_path.exists():
                target_file_path.unlink()
        except Exception as e:
            task.log(f"Warning: Could not delete scraped file: {e}", level="WARNING")

    except Exception as e:
        trace_exception(e)
        task.log(f"Error during scraping task: {e}", level="ERROR")
        if target_file_path and target_file_path.exists():
            try: target_file_path.unlink()
            except Exception: pass
        raise e
    finally:
        db.close()

def _clean_llm_json_response(raw: str) -> str:
    """Strips thinking blocks and isolates the first balanced JSON object/array to prevent JSONDecodeError."""
    if not raw:
        return "{}"
    text = re.sub(r'<think>[\s\S]*?</think>', '', raw, flags=re.IGNORECASE)
    text = re.sub(r'<thought>[\s\S]*?</thought>', '', text, flags=re.IGNORECASE).strip()

    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()

    first_brace = text.find('{')
    first_bracket = text.find('[')

    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        depth = 0
        in_string = False
        escape = False
        start = first_brace
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == '\\':
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if not in_string:
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        return text[start:i+1].strip()
    elif first_bracket != -1:
        depth = 0
        in_string = False
        escape = False
        start = first_bracket
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == '\\':
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if not in_string:
                if c == '[':
                    depth += 1
                elif c == ']':
                    depth -= 1
                    if depth == 0:
                        return text[start:i+1].strip()

    return text.strip()

def _make_llm_graph_executor(llm_client):
    """Creates a resilient LLM executor callback for safe_store's GraphStore."""
    def llm_executor_callback(prompt: str) -> str:
        try:
            raw = llm_client.generate_text(prompt, n_predict=2048, temperature=0.1)
        except TypeError:
            try:
                raw = llm_client.generate_text(prompt, max_new_tokens=2048, temperature=0.1)
            except TypeError:
                raw = llm_client.generate_text(prompt)

        # If prompt asks for JSON/decision/format, clean and extract strict JSON
        if any(keyword in prompt.lower() for keyword in ["json", "format:", "schema", "decision", "extract_entities", "merge"]):
            return _clean_llm_json_response(raw)

        cleaned = re.sub(r'<think>[\s\S]*?</think>', '', raw, flags=re.IGNORECASE)
        cleaned = re.sub(r'<thought>[\s\S]*?</thought>', '', cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    return llm_executor_callback

def _resolve_user_llm_client(username: str, db: Session, request_data: dict):
    """Resolves a valid LollmsClient for the user using explicitly passed or active model preferences."""
    user_db = db.query(DBUser).filter(DBUser.username == username).first()
    model_binding = request_data.get("model_binding")
    model_name = request_data.get("model_name")

    if not model_binding or not model_name:
        user_model_full = user_db.lollms_model_name if user_db else None
        if user_model_full and '/' in user_model_full:
            model_binding, model_name = user_model_full.split('/', 1)
        elif user_model_full:
            from backend.session import resolve_model_name
            try:
                model_binding, model_name = resolve_model_name(db, user_model_full)
            except Exception:
                pass

    if not model_binding or not model_name:
        active_binding = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).first()
        if active_binding:
            model_binding = active_binding.alias
            model_name = active_binding.default_model_name

    return build_lollms_client_from_params(
        username=username,
        binding_alias=model_binding,
        model_name=model_name,
        load_llm=True
    )

def _generate_graph_task(task: Task, username: str, datastore_id: str, request_data: dict):
    if not GraphStore:
        raise ImportError("GraphStore is not available.")

    db = next(get_db())
    try:
        llm_client = _resolve_user_llm_client(username, db, request_data)
        llm_executor_callback = _make_llm_graph_executor(llm_client)

        ss = get_safe_store_instance(username, datastore_id, db, permission_level="revectorize")

        with ss:
            gs = GraphStore(store=ss, llm_executor_callback=llm_executor_callback)
            guidance = request_data.get("ontology")

            if not guidance or not guidance.strip():
                task.log("No custom ontology provided. Analyzing documents to extract schema...")
                docs_sample = ss.list_documents()[:5]
                sample_texts = []
                for d in docs_sample:
                    fpath = d.get("file_path")
                    if fpath:
                        try:
                            text_sample = ss.reconstruct_document_text(fpath)
                            if text_sample:
                                sample_texts.append(text_sample[:2500])
                        except Exception:
                            pass

                if sample_texts:
                    prompt_synth = (
                        "You are an expert Ontologist. Extract a concise domain schema for knowledge graph construction from these text samples.\n"
                        "Define the core Classes, Object Properties, and domain/range rules.\n"
                        f"Samples:\n{chr(10).join(sample_texts)}\n\n"
                        "Output the schema in clean Turtle (.ttl) format starting with @prefix :"
                    )
                    try:
                        raw_guidance = llm_executor_callback(prompt_synth)
                        guidance = raw_guidance
                        task.log("Domain ontology successfully synthesized.")
                    except Exception as e:
                        task.log(f"Auto-ontology generation skipped: {e}", level="WARNING")

            docs = ss.list_documents()
            total_docs = len(docs)
            task.log(f"Found {total_docs} documents to process for graph generation.")

            for i, doc in enumerate(docs):
                if task.cancellation_event.is_set():
                    task.log("Graph generation cancelled.", level="WARNING")
                    break

                doc_id = doc.get("doc_id") or doc.get("id")
                doc_name = Path(doc.get("file_path", "Unknown")).name
                task.set_file_info(file_name=doc_name, total_files=total_docs)
                task.log(f"Building knowledge graph for document {i+1}/{total_docs}: {doc_name}")

                try:
                    if hasattr(gs, "build_graph_for_document"):
                        gs.build_graph_for_document(doc_id, guidance=guidance)
                    elif hasattr(gs, "build_graph"):
                        gs.build_graph(doc_id, guidance=guidance)
                except Exception as doc_err:
                    task.log(f"Warning: Document '{doc_name}' encountered extraction issue: {doc_err}", level="WARNING")

                task.set_progress(int(100 * (i + 1) / max(total_docs, 1)))

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
        llm_client = _resolve_user_llm_client(username, db, request_data)
        llm_executor_callback = _make_llm_graph_executor(llm_client)

        ss = get_safe_store_instance(username, datastore_id, db, permission_level="revectorize")

        with ss:
            gs = GraphStore(store=ss, llm_executor_callback=llm_executor_callback)
            guidance = request_data.get("ontology")
            docs = ss.list_documents()
            total_docs = len(docs)
            task.log(f"Checking {total_docs} documents for graph updates.")

            for i, doc in enumerate(docs):
                if task.cancellation_event.is_set():
                    break
                doc_id = doc.get("doc_id") or doc.get("id")
                doc_name = Path(doc.get("file_path", "Unknown")).name
                task.set_file_info(file_name=doc_name, total_files=total_docs)

                try:
                    if hasattr(gs, "build_graph_for_document"):
                        gs.build_graph_for_document(doc_id, guidance=guidance)
                    elif hasattr(gs, "build_graph"):
                        gs.build_graph(doc_id, guidance=guidance)
                except Exception as doc_err:
                    task.log(f"Warning: Document '{doc_name}' encountered update issue: {doc_err}", level="WARNING")

                task.set_progress(int(100 * (i + 1) / max(total_docs, 1)))

        task.result = {"message": "Graph update completed successfully."}
        task.log("Graph update finished.")

    except Exception as e:
        task.log(f"Error during graph update: {e}", level="CRITICAL")
        trace_exception(e)
        raise e
    finally:
        db.close()


# --- SafeStore File Management API (per-datastore) ---
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
            if hasattr(ss, 'count_chunks'):
                chunk_count = ss.count_chunks()
            elif hasattr(ss, 'db') and hasattr(ss.db, 'count'):
                chunk_count = ss.db.count('chunks')
            if GraphStore:
                try:
                    gs = GraphStore(store=ss)
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

@store_files_router.post("/scrape-url", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def scrape_url_to_datastore(
    datastore_id: str,
    request: ScrapeRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> TaskInfo:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    if not ScrapeMaster: raise HTTPException(status_code=501, detail="ScrapeMaster not installed.")

    get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_write")
    datastore_record = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record: raise HTTPException(status_code=404, detail="Datastore not found.")

    db_task = task_manager.submit_task(
        name=f"Scrape URL to DataStore: {datastore_record.name}",
        target=_scrape_url_task,
        args=(current_user.username, datastore_id, request.url, request.depth),
        description=f"Scraping {request.url} (Depth: {request.depth}) into '{datastore_record.name}'.",
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

@store_files_router.get("/files/content")
async def get_rag_file_content(
    datastore_id: str,
    filename: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_query")
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    
    datastore_docs_path = get_user_datastore_root_path(datastore_record.owner.username) / "safestore_docs" / datastore_id
    file_path = datastore_docs_path / secure_filename(filename)
    
    try:
        with ss:
            content = ss.reconstruct_document_text(str(file_path))
        if content is None:
             raise HTTPException(status_code=404, detail="Content not found or could not be reconstructed.")
        return {"content": content}
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Error retrieving file content: {e}")

@store_files_router.delete("/files/{filename}") 
async def delete_rag_document_from_datastore(datastore_id: str, filename: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_write")
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    s_filename = secure_filename(filename)
    if not s_filename or s_filename != filename: raise HTTPException(status_code=400, detail="Invalid filename.")
    
    datastore_docs_path = get_user_datastore_root_path(datastore_record.owner.username) / "safestore_docs" / datastore_id
    file_to_delete_path = datastore_docs_path / s_filename
    
    try:
        with ss: ss.delete_document_by_path(str(file_to_delete_path))
        file_to_delete_path.unlink(missing_ok=True)
        return {"message": f"Document '{s_filename}' deleted successfully from datastore {datastore_id}."}
    except Exception as e:
        if file_to_delete_path.exists(): raise HTTPException(status_code=500, detail=f"Could not delete '{s_filename}' from datastore {datastore_id}: {e}")
        else: return {"message": f"Document '{s_filename}' file deleted, potential DB cleanup issue in datastore {datastore_id}."}

def _project_vectors_to_2d(vectors: np.ndarray, method: str = "pca") -> np.ndarray:
    """Projects high-dimensional vector embeddings down to 2D coordinates normalized in [-1, 1]."""
    if len(vectors) == 0:
        return np.zeros((0, 2))
    if len(vectors) == 1:
        return np.zeros((1, 2))

    if method == "tsne" and len(vectors) >= 5:
        try:
            from sklearn.manifold import TSNE
            perplexity = min(30.0, max(2.0, float(len(vectors) - 1) / 3.0))
            tsne = TSNE(n_components=2, perplexity=perplexity, random_state=42, init='pca', learning_rate='auto')
            projected = tsne.fit_transform(vectors)
            max_abs = np.max(np.abs(projected))
            if max_abs > 0:
                projected = projected / max_abs
            return projected
        except Exception as e:
            print(f"t-SNE projection fallback to PCA: {e}")

    # Default robust PCA / SVD Projection
    try:
        centered = vectors - np.mean(vectors, axis=0)
        _, _, Vt = np.linalg.svd(centered, full_matrices=False)
        projected = np.dot(centered, Vt[:2].T)
        max_abs = np.max(np.abs(projected))
        if max_abs > 0:
            projected = projected / max_abs
        return projected
    except Exception as e:
        print(f"PCA SVD failed, using random projection fallback: {e}")
        rng = np.random.default_rng(42)
        proj_matrix = rng.standard_normal((vectors.shape[1], 2))
        projected = np.dot(vectors, proj_matrix)
        max_abs = np.max(np.abs(projected))
        if max_abs > 0:
            projected = projected / max_abs
        return projected

DOCUMENT_PALETTE = [
    "#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ef4444",
    "#06b6d4", "#ec4899", "#14b8a6", "#f97316", "#6366f1",
    "#84cc16", "#a855f7", "#0ea5e9", "#eab308", "#d946ef"
]

@store_files_router.get("/data-lake", response_model=DataLakeResponse)
async def get_datastore_data_lake_projection(
    datastore_id: str,
    method: str = "pca",
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Computes 2D vector embedding projections for all chunks in the DataStore,
    colored and grouped by source document.
    """
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_query")
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record:
        raise HTTPException(status_code=404, detail="Datastore not found")

    import sqlite3
    db_path = get_datastore_db_path(datastore_record.owner.username, datastore_id)
    if not db_path.exists():
        return DataLakeResponse(points=[], documents=[], total_chunks=0, reduction_method=method)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        if "chunks" not in tables:
            conn.close()
            return DataLakeResponse(points=[], documents=[], total_chunks=0, reduction_method=method)

        # Inspect chunks table columns
        cursor.execute("PRAGMA table_info(chunks)")
        chunk_cols = {row[1] for row in cursor.fetchall()}

        doc_col = "document_id" if "document_id" in chunk_cols else ("doc_id" if "doc_id" in chunk_cols else "file_path")
        text_col = "chunk_text" if "chunk_text" in chunk_cols else ("text" if "text" in chunk_cols else "content")
        idx_col = "chunk_index" if "chunk_index" in chunk_cols else "id"
        vec_col = "vector" if "vector" in chunk_cols else ("embedding" if "embedding" in chunk_cols else ("embeddings" if "embeddings" in chunk_cols else None))
        meta_col = "metadata" if "metadata" in chunk_cols else None

        # Build Document map
        doc_titles = {}
        if "documents" in tables:
            cursor.execute("PRAGMA table_info(documents)")
            d_cols = {row[1] for row in cursor.fetchall()}
            d_id_col = "id" if "id" in d_cols else "file_path"
            d_path_col = "file_path" if "file_path" in d_cols else "title"

            cursor.execute(f"SELECT {d_id_col}, {d_path_col} FROM documents")
            for r in cursor.fetchall():
                doc_id_val = str(r[0])
                raw_path = str(r[1] or f"Doc {doc_id_val}")
                doc_titles[doc_id_val] = Path(raw_path).name

        select_cols = [f"id", f"{doc_col} AS doc_id", f"{text_col} AS text", f"{idx_col} AS chunk_idx"]
        if vec_col:
            select_cols.append(f"{vec_col} AS vector_data")
        if meta_col:
            select_cols.append(f"{meta_col} AS metadata_data")

        cursor.execute(f"SELECT {', '.join(select_cols)} FROM chunks")
        raw_rows = cursor.fetchall()
        conn.close()

        if not raw_rows:
            return DataLakeResponse(points=[], documents=[], total_chunks=0, reduction_method=method)

        extracted_vectors = []
        chunk_records = []
        document_chunks_count = {}

        for row in raw_rows:
            cid = str(row["id"])
            doc_id = str(row["doc_id"] or "default_doc")
            text_content = str(row["text"] or "")
            c_idx = int(row["chunk_idx"]) if isinstance(row["chunk_idx"], (int, float)) else 0
            doc_name = doc_titles.get(doc_id) or Path(doc_id).name or f"Document {doc_id[:8]}"

            document_chunks_count[doc_id] = document_chunks_count.get(doc_id, 0) + 1

            meta = {}
            if meta_col and row["metadata_data"]:
                try:
                    meta = json.loads(row["metadata_data"]) if isinstance(row["metadata_data"], str) else dict(row["metadata_data"])
                except Exception:
                    pass

            vec = None
            if vec_col and row["vector_data"] is not None:
                raw_vec = row["vector_data"]
                if isinstance(raw_vec, bytes):
                    # Check if float32 or float64
                    if len(raw_vec) % 4 == 0:
                        vec = np.frombuffer(raw_vec, dtype=np.float32)
                    elif len(raw_vec) % 8 == 0:
                        vec = np.frombuffer(raw_vec, dtype=np.float64)
                elif isinstance(raw_vec, str):
                    try:
                        parsed_v = json.loads(raw_vec)
                        if isinstance(parsed_v, list):
                            vec = np.array(parsed_v, dtype=np.float32)
                    except Exception:
                        pass
                elif isinstance(raw_vec, (list, np.ndarray)):
                    vec = np.array(raw_vec, dtype=np.float32)

            if vec is None or len(vec) == 0:
                # Deterministic TF-IDF / Hash projection for unvectorized text
                import hashlib
                h = hashlib.sha256(text_content.encode('utf-8')).digest()
                pseudo_vec = np.frombuffer(h[:32], dtype=np.float32)
                vec = pseudo_vec

            extracted_vectors.append(vec)
            chunk_records.append({
                "id": cid,
                "document_id": doc_id,
                "document_name": doc_name,
                "chunk_index": c_idx,
                "full_text": text_content,
                "text_snippet": text_content[:180] + ("..." if len(text_content) > 180 else ""),
                "metadata": meta
            })

        # Ensure all vectors match the maximum dimension
        if extracted_vectors:
            max_dim = max(len(v) for v in extracted_vectors)
            padded_vectors = []
            for v in extracted_vectors:
                if len(v) < max_dim:
                    padded = np.pad(v, (0, max_dim - len(v)), 'constant')
                    padded_vectors.append(padded)
                else:
                    padded_vectors.append(v[:max_dim])
            vector_matrix = np.array(padded_vectors, dtype=np.float32)
        else:
            vector_matrix = np.zeros((len(chunk_records), 2), dtype=np.float32)

        # Compute 2D coordinates
        coords_2d = _project_vectors_to_2d(vector_matrix, method=method.lower())

        # Map document colors
        doc_color_map = {}
        unique_docs = sorted(list(document_chunks_count.keys()))
        for idx, doc_id in enumerate(unique_docs):
            doc_color_map[doc_id] = DOCUMENT_PALETTE[idx % len(DOCUMENT_PALETTE)]

        points = []
        doc_coords_accumulator = {}

        for idx, item in enumerate(chunk_records):
            x_val = float(coords_2d[idx, 0])
            y_val = float(coords_2d[idx, 1])
            doc_id = item["document_id"]
            color = doc_color_map.get(doc_id, "#3b82f6")

            points.append(DataLakeChunkPoint(
                id=item["id"],
                document_id=doc_id,
                document_name=item["document_name"],
                chunk_index=item["chunk_index"],
                text_snippet=item["text_snippet"],
                full_text=item["full_text"],
                x=x_val,
                y=y_val,
                metadata=item["metadata"],
                color=color
            ))

            doc_coords_accumulator.setdefault(doc_id, []).append((x_val, y_val))

        # Compute document centroids for the legend
        doc_legends = []
        for doc_id in unique_docs:
            d_name = doc_titles.get(doc_id) or Path(doc_id).name or f"Document {doc_id[:8]}"
            d_coords = doc_coords_accumulator.get(doc_id, [(0.0, 0.0)])
            c_x = float(np.mean([pt[0] for pt in d_coords]))
            c_y = float(np.mean([pt[1] for pt in d_coords]))

            doc_legends.append(DataLakeDocumentLegend(
                id=doc_id,
                name=d_name,
                chunk_count=document_chunks_count.get(doc_id, 0),
                color=doc_color_map.get(doc_id, "#3b82f6"),
                centroid={"x": c_x, "y": c_y}
            ))

        return DataLakeResponse(
            points=points,
            documents=doc_legends,
            total_chunks=len(points),
            dimensions=2,
            reduction_method=method.upper()
        )

    except Exception as e:
        trace_exception(e)
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=f"Error generating data lake visualization: {str(e)}")

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
                ss.delete_document_by_path(str(file_to_delete_path))
                file_to_delete_path.unlink(missing_ok=True)
                deleted_count += 1
            except Exception as e:
                print(f"Error during deletion of {filename}: {e}")
                failed_files.append(filename)

    return {
        "message": f"Deleted {deleted_count} documents. Failed to delete {len(failed_files)} documents.",
        "deleted_count": deleted_count,
        "failed_files": failed_files
    }

def _generate_llm_answer(llm_client, full_prompt: str, max_tokens: int, temperature: float) -> str:
    """Invokes the LLM client defensively handling different lollms-client parameter signatures."""
    try:
        return llm_client.generate_text(full_prompt, n_predict=max_tokens, temperature=temperature)
    except TypeError:
        try:
            return llm_client.generate_text(full_prompt, max_new_tokens=max_tokens, temperature=temperature)
        except TypeError:
            return llm_client.generate_text(full_prompt)

@store_files_router.post("/query-answer", response_model=DataStoreAnswerResponse)
async def query_datastore_and_answer(
    datastore_id: str,
    request_data: DataStoreAnswerRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> DataStoreAnswerResponse:
    """
    Queries the DataStore and uses an active LLM to synthesize a grounded answer citing the retrieved chunks.
    """
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")

    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db)
        with ss:
            if request_data.mode == "hybrid" and hasattr(ss, "hybrid_query"):
                results = ss.hybrid_query(
                    query_text=request_data.query,
                    top_k=request_data.top_k,
                    dense_weight=request_data.dense_weight,
                    bm25_weight=request_data.bm25_weight,
                    rrf_k=request_data.rrf_k
                )
            else:
                results = ss.query(
                    request_data.query, 
                    top_k=request_data.top_k, 
                    min_similarity_percent=request_data.min_similarity_percent
                )

        sanitized_results = _sanitize_numpy(results)

        if not sanitized_results:
            return DataStoreAnswerResponse(
                answer="No relevant documents or information were found in the data store matching your query criteria.",
                chunks=[],
                model_name=None
            )

        context_blocks = []
        for i, chunk in enumerate(sanitized_results):
            fpath = chunk.get("file_path", "unknown")
            fname = Path(fpath).name if fpath else f"Doc {i+1}"
            ctext = chunk.get("chunk_text", chunk.get("content", ""))
            score = chunk.get("similarity_percent", chunk.get("fused_score", ""))
            score_str = f" (Similarity: {score:.1f}%)" if isinstance(score, (int, float)) and score > 1 else (f" (Score: {score:.4f})" if isinstance(score, (int, float)) else "")
            context_blocks.append(f"--- Evidence [{i+1}] Source: {fname}{score_str} ---\n{ctext}\n--- End Evidence [{i+1}] ---")

        context_text = "\n\n".join(context_blocks)

        system_prompt = request_data.system_prompt or (
            "You are an expert AI knowledge analyst analyzing documents from a verified data store.\n"
            "Answer the user's question accurately using ONLY the provided evidence.\n"
            "Rules:\n"
            "1. Ground all claims directly in the evidence.\n"
            "2. Cite your sources using [1], [2], etc., corresponding to the evidence indices.\n"
            "3. If the evidence is insufficient to answer the question, explicitly state what is missing."
        )

        full_prompt = (
            f"{system_prompt}\n\n"
            f"=== VERIFIED EVIDENCE ===\n\n{context_text}\n\n"
            f"=== QUESTION ===\n{request_data.query}\n\n"
            "=== GROUNDED ANSWER ==="
        )

        try:
            llm_client = get_user_lollms_client(current_user.username)
        except Exception:
            llm_client = _resolve_user_llm_client(current_user.username, db, {})

        max_tokens_val = request_data.max_tokens or 2048
        temp_val = request_data.temperature if request_data.temperature is not None else 0.2

        answer = await asyncio.to_thread(
            _generate_llm_answer,
            llm_client,
            full_prompt,
            max_tokens_val,
            temp_val
        )

        model_name = getattr(llm_client, "model_name", None) or getattr(llm_client, "llm_binding_name", "LLM")

        return DataStoreAnswerResponse(
            answer=answer,
            chunks=sanitized_results,
            model_name=model_name
        )
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Error generating answer from datastore: {e}")

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
            if request_data.mode == "hybrid" and hasattr(ss, "hybrid_query"):
                results = ss.hybrid_query(
                    query_text=request_data.query,
                    top_k=request_data.top_k,
                    dense_weight=request_data.dense_weight,
                    bm25_weight=request_data.bm25_weight,
                    rrf_k=request_data.rrf_k
                )
            else:
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
    request_data: GraphGenerationRequest = Body(default_factory=GraphGenerationRequest),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> TaskInfo:
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")

    get_safe_store_instance(current_user.username, datastore_id, db, permission_level="revectorize")
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record:
        raise HTTPException(status_code=404, detail="Datastore metadata not found in main DB.")

    try:
        req_dict = request_data.model_dump() if request_data else {}
        db_task = task_manager.submit_task(
            name=f"Generate Graph for: {datastore_record.name}",
            target=_generate_graph_task,
            args=(current_user.username, datastore_id, req_dict),
            description=f"Generating knowledge graph for '{datastore_record.name}'. This may take a while.",
            owner_username=current_user.username
        )
        return db_task
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"An error occurred during graph generation: {e}")

@store_files_router.post("/graph/update", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def update_datastore_graph(
    datastore_id: str,
    request_data: GraphGenerationRequest = Body(default_factory=GraphGenerationRequest),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> TaskInfo:
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")

    get_safe_store_instance(current_user.username, datastore_id, db, permission_level="revectorize")
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record:
        raise HTTPException(status_code=404, detail="Datastore metadata not found in main DB.")

    try:
        req_dict = request_data.model_dump() if request_data else {}
        db_task = task_manager.submit_task(
            name=f"Update Graph for: {datastore_record.name}",
            target=_update_graph_task,
            args=(current_user.username, datastore_id, req_dict),
            description=f"Updating knowledge graph for '{datastore_record.name}'.",
            owner_username=current_user.username
        )
        return db_task
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"An error occurred during graph update: {e}")

class GraphViewRequest(BaseModel):
    mode: str = "tbox_summary" # "tbox_summary" | "tbox" | "abox"

class ExpandClassRequest(BaseModel):
    class_uri: str
    offset: int = 0
    limit: int = 150

class ShortestPathRequest(BaseModel):
    source_uri: str
    target_uri: str

class TripleMutationRequest(BaseModel):
    subject: str
    predicate: str
    object: str
    object_kind: str = "uri" # "uri" | "literal" | "any"
    datatype: Optional[str] = None
    lang: Optional[str] = None

class NodeRenamePayload(BaseModel):
    old_uri: str
    new_name: str

@store_files_router.get("/graph", response_model=Dict)
async def get_datastore_graph(
    datastore_id: str,
    mode: str = "tbox_summary",
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict:
    if not GraphStore:
        raise HTTPException(status_code=501, detail="GraphStore is not available.")

    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_query")
        with ss:
            gs = GraphStore(store=ss, llm_executor_callback=None)

            raw_nodes = []
            raw_edges = []

            if hasattr(gs, "get_all_nodes_for_visualization"):
                raw_nodes = gs.get_all_nodes_for_visualization(limit=5000)
            elif hasattr(gs, "get_all_nodes"):
                raw_nodes = gs.get_all_nodes()

            if hasattr(gs, "get_all_relationships_for_visualization"):
                raw_edges = gs.get_all_relationships_for_visualization(limit=10000)
            elif hasattr(gs, "get_all_relationships"):
                raw_edges = gs.get_all_relationships()

        sanitized_nodes = _sanitize_numpy(raw_nodes)
        sanitized_edges = _sanitize_numpy(raw_edges)

        # Build TBox summary / ABox classification
        nodes_out = []
        type_counts = {}
        for n in sanitized_nodes:
            lbl = n.get("label") or "Entity"
            type_counts[lbl] = type_counts.get(lbl, 0) + 1

        if mode == "tbox_summary":
            # Synthesize class schema overview with instance counts
            for type_name, count in type_counts.items():
                nodes_out.append({
                    "data": {
                        "id": f"class__{type_name}",
                        "label": type_name,
                        "type": "class",
                        "box": "tbox",
                        "group": type_name,
                        "uri": f"http://example.org/onto#{type_name}",
                        "instance_count": count,
                        "expandable": count > 0
                    }
                })

            # Derive class-to-class aggregated edges
            edge_aggs = {}
            node_type_map = {str(n.get("id")): n.get("label") for n in sanitized_nodes}

            for e in sanitized_edges:
                src_id = str(e.get("from") or e.get("source") or e.get("source_id"))
                tgt_id = str(e.get("to") or e.get("target") or e.get("target_id"))
                src_type = node_type_map.get(src_id)
                tgt_type = node_type_map.get(tgt_id)
                pred = e.get("label") or e.get("type") or "relatedTo"

                if src_type and tgt_type:
                    key = (f"class__{src_type}", pred, f"class__{tgt_type}")
                    edge_aggs[key] = edge_aggs.get(key, 0) + 1

            edges_out = []
            for idx, ((s, p, o), count) in enumerate(edge_aggs.items()):
                edges_out.append({
                    "data": {
                        "id": f"agg_e_{idx}",
                        "source": s,
                        "target": o,
                        "label": p,
                        "count": count,
                        "box": "tbox",
                        "kind": "hierarchy" if p in ("subClassOf", "type") else "data"
                    }
                })
        else:
            # Full individual / entity graph (ABox or raw TBox)
            for n in sanitized_nodes:
                nid = str(n.get("id"))
                nlabel = String = str(n.get("properties", {}).get("identifying_value") or n.get("properties", {}).get("name") or n.get("properties", {}).get("label") or n.get("label") or nid)
                ntype = n.get("label") or "Entity"
                nodes_out.append({
                    "data": {
                        "id": nid,
                        "label": nlabel,
                        "type": "class" if mode == "tbox" else "individual",
                        "box": "tbox" if mode == "tbox" else "abox",
                        "group": ntype,
                        "uri": f"http://example.org/onto#{nlabel}",
                        "properties": n.get("properties", {})
                    }
                })

            edges_out = []
            for idx, e in enumerate(sanitized_edges):
                src_id = str(e.get("from") or e.get("source") or e.get("source_id"))
                tgt_id = str(e.get("to") or e.get("target") or e.get("target_id"))
                edges_out.append({
                    "data": {
                        "id": str(e.get("id") or f"e_{idx}"),
                        "source": src_id,
                        "target": tgt_id,
                        "label": e.get("label") or e.get("type") or "relates_to",
                        "box": "tbox" if mode == "tbox" else "abox",
                        "predicate": e.get("label") or e.get("type") or "relates_to"
                    }
                })

        return {
            "nodes": nodes_out,
            "edges": edges_out,
            "mode": mode,
            "stats": {
                "nodes_shown": len(nodes_out),
                "edges_shown": len(edges_out),
                "total_entities": len(sanitized_nodes),
                "total_relationships": len(sanitized_edges)
            }
        }
    except Exception as e:
        trace_exception(e)
        return {"nodes": [], "edges": [], "stats": {"nodes_shown": 0, "edges_shown": 0}}

@store_files_router.post("/graph/expand", response_model=Dict)
async def expand_class_instances(
    datastore_id: str,
    req: ExpandClassRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Lazily loads individuals belonging to a specific class for smooth, paginated exploration."""
    if not GraphStore:
        raise HTTPException(status_code=501, detail="GraphStore not available.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_query")
    with ss:
        gs = GraphStore(store=ss, llm_executor_callback=None)
        raw_nodes = gs.get_all_nodes_for_visualization(limit=5000) if hasattr(gs, "get_all_nodes_for_visualization") else []
        raw_edges = gs.get_all_relationships_for_visualization(limit=10000) if hasattr(gs, "get_all_relationships_for_visualization") else []

    target_class = re.split(r'[#/]', req.class_uri)[-1] if req.class_uri else ""
    matched_nodes = [n for n in raw_nodes if (n.get("label") == target_class or not target_class)]
    page_nodes = matched_nodes[req.offset : req.offset + req.limit]
    page_node_ids = {str(n.get("id")) for n in page_nodes}

    matched_edges = [
        e for e in raw_edges
        if str(e.get("from") or e.get("source") or e.get("source_id")) in page_node_ids
        or str(e.get("to") or e.get("target") or e.get("target_id")) in page_node_ids
    ]

    nodes_out = [{
        "data": {
            "id": str(n.get("id")),
            "label": str(n.get("properties", {}).get("identifying_value") or n.get("properties", {}).get("name") or n.get("label") or n.get("id")),
            "type": "individual",
            "box": "abox",
            "group": n.get("label") or "Entity",
            "uri": f"http://example.org/onto#{n.get('id')}",
            "properties": n.get("properties", {})
        }
    } for n in page_nodes]

    edges_out = [{
        "data": {
            "id": str(e.get("id")),
            "source": str(e.get("from") or e.get("source") or e.get("source_id")),
            "target": str(e.get("to") or e.get("target") or e.get("target_id")),
            "label": e.get("label") or e.get("type") or "relates_to",
            "box": "abox"
        }
    } for e in matched_edges]

    return {
        "nodes": nodes_out,
        "edges": edges_out,
        "returned": len(page_nodes),
        "total_members": len(matched_nodes),
        "has_more": (req.offset + len(page_nodes)) < len(matched_nodes)
    }

@store_files_router.post("/graph/path", response_model=Dict)
async def find_shortest_graph_path(
    datastore_id: str,
    req: ShortestPathRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Executes an undirected BFS between two resources to find and trace the shortest semantic path."""
    if not GraphStore:
        raise HTTPException(status_code=501, detail="GraphStore not available.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_query")
    with ss:
        gs = GraphStore(store=ss, llm_executor_callback=None)
        raw_nodes = gs.get_all_nodes_for_visualization(limit=10000) if hasattr(gs, "get_all_nodes_for_visualization") else []
        raw_edges = gs.get_all_relationships_for_visualization(limit=20000) if hasattr(gs, "get_all_relationships_for_visualization") else []

    # Map labels/URIs to IDs
    uri_map = {}
    for n in raw_nodes:
        nid = str(n.get("id"))
        nlabel = str(n.get("properties", {}).get("name") or n.get("label") or nid)
        uri_map[nid] = nid
        uri_map[nlabel] = nid
        uri_map[f"http://example.org/onto#{nlabel}"] = nid

    src_id = uri_map.get(req.source_uri) or req.source_uri
    tgt_id = uri_map.get(req.target_uri) or req.target_uri

    if not src_id or not tgt_id:
        raise HTTPException(status_code=404, detail="Source or target resource not found in graph.")

    # Build adjacency
    from collections import deque
    adj = {}
    for e in raw_edges:
        s = str(e.get("from") or e.get("source") or e.get("source_id"))
        t = str(e.get("to") or e.get("target") or e.get("target_id"))
        p = e.get("label") or e.get("type") or "relates_to"
        adj.setdefault(s, []).append((t, p))
        adj.setdefault(t, []).append((s, p))

    came_from = {src_id: None}
    queue = deque([src_id])
    found = src_id == tgt_id

    while queue and not found:
        curr = queue.popleft()
        for neighbor, pred in adj.get(curr, []):
            if neighbor not in came_from:
                came_from[neighbor] = (curr, pred)
                if neighbor == tgt_id:
                    found = True
                    break
                queue.append(neighbor)

    if not found:
        raise HTTPException(status_code=404, detail="No semantic path found between the specified entities.")

    path_nodes = [tgt_id]
    path_edges = []
    curr = tgt_id
    while curr != src_id:
        prev, pred = came_from[curr]
        path_edges.append({"source": prev, "target": curr, "label": pred})
        curr = prev
        path_nodes.append(curr)

    path_nodes.reverse()
    path_edges.reverse()

    return {
        "path_length": len(path_edges),
        "nodes": [{"data": {"id": nid, "label": nid, "box": "abox"}} for nid in path_nodes],
        "edges": [{"data": {"id": f"path_e_{i}", "source": e["source"], "target": e["target"], "label": e["label"], "box": "abox"}} for i, e in enumerate(path_edges)]
    }


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
            gs = GraphStore(store=ss, llm_executor_callback=llm_executor_callback)
            results = gs.query_graph(request_data.query, output_mode="chunks_summary")
        sanitized_results = _sanitize_numpy(results)
        return sanitized_results
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Error querying graph: {e}")

@store_files_router.post("/graph/query-hybrid", response_model=Dict)
async def query_datastore_graph_hybrid(
    datastore_id: str,
    request_data: GraphHybridQueryRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict:
    if not GraphStore:
        raise HTTPException(status_code=501, detail="GraphStore is not available.")
    
    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db)
        with ss:
            gs = GraphStore(store=ss)
            if hasattr(gs, "query_graph_hybrid"):
                results = gs.query_graph_hybrid(
                    query_text=request_data.query,
                    top_k=request_data.top_k,
                    dense_weight=request_data.dense_weight,
                    bm25_weight=request_data.bm25_weight,
                    graph_weight=request_data.graph_weight
                )
            else:
                raw_results = gs.query_graph(request_data.query, output_mode="chunks_summary")
                results = {"ranked_chunks": raw_results, "subgraph": {"nodes": [], "relationships": []}}

        return _sanitize_numpy(results)
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Error running hybrid graph query: {e}")

@store_files_router.post("/graph/extract-ontology", response_model=Dict[str, Any])
async def extract_ontology_from_store_documents(
    datastore_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Analyzes indexed datastore documents and automatically synthesizes a domain ontology schema."""
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_query")
    llm_client = _resolve_user_llm_client(current_user.username, db, {})

    with ss:
        docs = ss.list_documents()
        if not docs:
            raise HTTPException(status_code=400, detail="No documents found in this data store to extract ontology from.")

        sample_texts = []
        for d in docs[:6]:
            fpath = d.get("file_path")
            if fpath:
                try:
                    text_sample = ss.reconstruct_document_text(fpath)
                    if text_sample:
                        sample_texts.append(f"--- Document: {Path(fpath).name} ---\n{text_sample[:2500]}")
                except Exception:
                    pass

    if not sample_texts:
        raise HTTPException(status_code=400, detail="Could not read text content from documents.")

    system_prompt = (
        "You are an expert Semantic Ontologist. Analyze the provided document excerpts and create a comprehensive domain ontology schema.\n"
        "You MUST return ONLY a strictly valid JSON object inside a single markdown code block ```json ... ``` with this exact structure:\n"
        "{\n"
        '  "nodes": [\n'
        '    { "type": "class|property|dataprop|concept|individual", "name": "PascalCaseName", "rdfsLabel": "Human Label", "comment": "Definition" }\n'
        "  ],\n"
        '  "edges": [\n'
        '    { "source": "SourceClassName", "target": "TargetClassName", "relType": "subClassOf|domain|range|equivalentClass|disjointWith" }\n'
        "  ]\n"
        "}"
    )

    prompt = f"Document excerpts:\n\n" + "\n\n".join(sample_texts) + "\n\nSynthesize the complete domain ontology schema now."

    try:
        response_text = llm_client.generate_text(
            prompt=f"{system_prompt}\n\n{prompt}",
            max_new_tokens=2048,
            temperature=0.2
        )
        json_match = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', response_text)
        if json_match:
            data = json.loads(json_match.group(1).strip())
            return {
                "nodes": data.get("nodes", []),
                "edges": data.get("edges", []),
                "raw_response": response_text
            }
        else:
            raise ValueError("LLM did not return a valid JSON block.")
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Failed to auto-extract ontology: {str(e)}")

@store_files_router.post("/graph/sparql", response_model=Dict)
async def query_datastore_sparql(
    datastore_id: str,
    request_data: SparqlQueryRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict:
    """Executes a standards-compliant W3C SPARQL 1.1 query (SELECT, ASK, CONSTRUCT, DESCRIBE) on the knowledge graph."""
    if not GraphStore:
        raise HTTPException(status_code=501, detail="GraphStore is not available.")
    
    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_query")
        with ss:
            gs = GraphStore(store=ss)
            if hasattr(gs, "query_sparql"):
                result = gs.query_sparql(request_data.query)
            else:
                raise HTTPException(status_code=501, detail="Installed safe_store GraphStore does not support query_sparql.")
                
        return _sanitize_numpy(result)
    except HTTPException:
        raise
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=400, detail=f"SPARQL Execution Error: {e}")

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
            gs = GraphStore(store=ss, llm_executor_callback=None)
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
            gs = GraphStore(store=ss)
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
            gs = GraphStore(store=ss)
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
            gs = GraphStore(store=ss)
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
            gs = GraphStore(store=ss)
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
            gs = GraphStore(store=ss)
            gs.delete_relationship(edge_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

datastore_router = APIRouter(prefix="/api/datastores", tags=["RAG DataStores"])

@datastore_router.get("/available-vectorizers", response_model=List[Dict[str, Any]])
async def list_available_vectorizers(db: Session = Depends(get_db)):
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")

    try:
        mode_setting = settings.get("rag_model_display_mode", "mixed")
        rag_bindings = db.query(DBRAGBinding).filter(DBRAGBinding.is_active == True).all()
        results = []

        for binding in rag_bindings:
            try:
                binding_config = binding.config
                if isinstance(binding_config, str):
                    try:
                        binding_config = json.loads(binding_config)
                    except Exception:
                        binding_config = {}
                if not isinstance(binding_config, dict):
                    binding_config = {}

                clean_config = binding_config.copy()
                if 'model' in clean_config:
                    del clean_config['model']

                raw_models_list = safe_store.SafeStore.list_models(
                    vectorizer_name=binding.name,
                    vectorizer_config=clean_config
                )
                
                raw_names = set()
                if raw_models_list:
                    for m in raw_models_list:
                        if isinstance(m, str):
                            raw_names.add(m)
                        elif isinstance(m, dict):
                            name = m.get("model_name") or m.get("name")
                            if name:
                                raw_names.add(name)
                        else:
                            if hasattr(m, "model_name"):
                                raw_names.add(m.model_name)
                            elif hasattr(m, "name"):
                                raw_names.add(m.name)
                
                sorted_raw_names = sorted(list(raw_names))
                
                aliases = {}
                if binding.model_aliases:
                    try:
                        if isinstance(binding.model_aliases, str):
                            aliases = json.loads(binding.model_aliases)
                        else:
                            aliases = binding.model_aliases
                    except Exception:
                        pass

                processed_models = []
                
                if not sorted_raw_names:
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
                        else:
                            entry["name"] = alias_name or raw_name
                            processed_models.append(entry)
                
                    processed_models.sort(key=lambda x: x['name'])

                    if not processed_models and sorted_raw_names:
                         for raw_name in sorted_raw_names:
                            processed_models.append({"name": raw_name, "value": raw_name})
                         processed_models.sort(key=lambda x: x['name'])

                results.append({
                    "id": binding.id,
                    "alias": binding.alias,
                    "vectorizer_name": binding.name,
                    "vectorizer_config": clean_config,
                    "models": processed_models
                })

            except Exception as e:
                trace_exception(e)
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
        config = binding.config or {}
        if 'model' in config:
            config = config.copy()
            del config['model']
            
        raw_models = safe_store.SafeStore.list_models(
            vectorizer_name=binding.name, 
            vectorizer_config=config
        )
        
        models_list = [item if isinstance(item, str) else item.get("model_name") for item in raw_models if (isinstance(item, str) or item.get("model_name"))]
        return sorted(list(set(models_list)))
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
            chunking_strategy=getattr(ds_db, "chunking_strategy", "recursive") or "recursive",
            chunking_kwargs=getattr(ds_db, "chunking_kwargs", {}) or {},
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
                chunking_strategy=getattr(ds_db, "chunking_strategy", "recursive") or "recursive",
                chunking_kwargs=getattr(ds_db, "chunking_kwargs", {}) or {},
                created_at=ds_db.created_at, updated_at=ds_db.updated_at
            ))
    return response_list

@datastore_router.post("", response_model=DataStorePublic, status_code=status.HTTP_201_CREATED)
async def create_datastore(ds_create: DataStoreCreate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DataStorePublic:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if db.query(DBDataStore).filter_by(owner_user_id=user_db_record.id, name=ds_create.name).first(): 
        raise HTTPException(status_code=400, detail=f"DataStore '{ds_create.name}' already exists.")
    
    new_ds_db_obj = DBDataStore(
        owner_user_id=user_db_record.id, 
        name=ds_create.name, 
        description=ds_create.description,
        vectorizer_name=ds_create.vectorizer_name,
        vectorizer_config=ds_create.vectorizer_config,
        chunk_size=ds_create.chunk_size if ds_create.chunk_size is not None else settings.get("default_chunk_size", 2048),
        chunk_overlap=ds_create.chunk_overlap if ds_create.chunk_overlap is not None else settings.get("default_chunk_overlap", 256),
        chunking_strategy=ds_create.chunking_strategy or settings.get("default_rag_chunking_strategy", "recursive"),
        chunking_kwargs=ds_create.chunking_kwargs or {}
    )
    try:
        db.add(new_ds_db_obj)
        db.commit()
        db.refresh(new_ds_db_obj)
        get_safe_store_instance(current_user.username, new_ds_db_obj.id, db)
        
        return DataStorePublic(
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
            chunk_overlap=new_ds_db_obj.chunk_overlap,
            chunking_strategy=new_ds_db_obj.chunking_strategy,
            chunking_kwargs=new_ds_db_obj.chunking_kwargs or {}
        )
    except Exception as e: 
        trace_exception(e)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

@datastore_router.put("/{datastore_id}", response_model=DataStorePublic)
async def update_datastore(datastore_id: str, ds_update: DataStoreEdit, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DataStorePublic:
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
        db.commit()
        db.refresh(ds_db_obj)
        permission_level = 'owner' if ds_db_obj.owner_user_id == user_db_record.id else 'read_write'
        
        return DataStorePublic(
             id=ds_db_obj.id, name=ds_db_obj.name, description=ds_db_obj.description,
             owner_username=ds_db.owner.username, permission_level=permission_level,
             created_at=ds_db_obj.created_at, updated_at=ds_db_obj.updated_at,
             vectorizer_name=ds_db_obj.vectorizer_name,
             vectorizer_config=ds_db_obj.vectorizer_config or {},
             chunk_size=ds_db_obj.chunk_size,
             chunk_overlap=ds_db_obj.chunk_overlap
        )
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"DB error updating datastore: {e}")

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
        
        shutil.rmtree(ds_docs_path, ignore_errors=True)
        ds_file_path.unlink(missing_ok=True)
        ds_lock_file_path.unlink(missing_ok=True)
            
        return {"message": f"DataStore '{ds_db_obj.name}' and its associated files are deleted."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"DB error deleting datastore: {e}")

@datastore_router.get("/{datastore_id}/shared-with", response_model=List[SharedWithUserPublic])
async def get_datastore_shared_with_list(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db: raise HTTPException(status_code=404, detail="Owner user not found.")

    ds_to_check = db.query(DBDataStore).filter(DBDataStore.id == datastore_id, DBDataStore.owner_user_id == owner_user_db.id).first()
    if not ds_to_check: raise HTTPException(status_code=404, detail="DataStore not found or you are not the owner.")

    shared_links = db.query(DBSharedDataStoreLink).options(joinedload(DBSharedDataStoreLink.shared_with_user)).filter(DBSharedDataStoreLink.datastore_id == datastore_id).all()
    
    return [
        SharedWithUserPublic(
            user_id=link.shared_with_user.id,
            username=link.shared_with_user.username,
            icon=link.shared_with_user.icon,
            permission_level=link.permission_level
        ) for link in shared_links
    ]

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
        db.add(new_link)
        db.commit()
        manager.send_personal_message_sync({
            "type": "datastore_shared",
            "data": {
                "message": f"🎁 {current_user.username} shared Data Store: {ds_to_share.name}",
                "sender_username": current_user.username,
                "sender_icon": current_user.icon,
                "datastore_id": datastore_id,
                "datastore_name": ds_to_share.name,
                "permission_level": share_request.permission_level,
                "type": "success",
                "duration": 6000
            }
        }, target_user_db.id)
        return {"message": f"DataStore '{ds_to_share.name}' shared successfully with user '{target_user_db.username}'."}
    except IntegrityError: 
        db.rollback()
        raise HTTPException(status_code=400, detail="Sharing conflict.")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"DB error sharing datastore: {e}")

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
        db.delete(link_to_delete)
        db.commit()
        return {"message": f"Sharing for DataStore '{ds_to_unshare.name}' has been revoked from user '{target_user_db.username}'."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"DB error revoking share link: {e}")

@datastore_router.delete("/{datastore_id}/leave", status_code=status.HTTP_200_OK)
async def leave_datastore(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db: raise HTTPException(status_code=404, detail="User not found.")

    link_to_delete = db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id, shared_with_user_id=user_db.id).first()
    if not link_to_delete:
        ds = db.query(DBDataStore).filter_by(id=datastore_id).first()
        if ds and ds.owner_user_id == user_db.id:
             raise HTTPException(status_code=400, detail="Owner cannot leave the datastore. Delete it instead.")
        raise HTTPException(status_code=404, detail="Shared link not found.")

    try:
        db.delete(link_to_delete)
        db.commit()
        return {"message": "You have left the DataStore."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"DB error leaving datastore: {e}")

@datastore_router.get("/{datastore_id}/export")
async def export_datastore(
    datastore_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="revectorize")
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record:
        raise HTTPException(status_code=404, detail="Datastore not found.")

    owner_username = datastore_record.owner.username
    db_path = get_datastore_db_path(owner_username, datastore_id)
    docs_path = get_user_datastore_root_path(owner_username) / "safestore_docs" / datastore_id

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        export_dir = temp_dir_path / f"datastore_export_{datastore_id}"
        export_dir.mkdir()

        metadata = {
            "id": datastore_record.id,
            "name": datastore_record.name,
            "description": datastore_record.description,
            "owner_username": owner_username,
            "vectorizer_name": datastore_record.vectorizer_name,
            "vectorizer_config": datastore_record.vectorizer_config,
            "chunk_size": datastore_record.chunk_size,
            "chunk_overlap": datastore_record.chunk_overlap,
            "chunking_strategy": getattr(datastore_record, "chunking_strategy", "recursive") or "recursive",
            "chunking_kwargs": getattr(datastore_record, "chunking_kwargs", {}) or {},
            "created_at": datastore_record.created_at.isoformat() if datastore_record.created_at else None,
            "exported_at": datetime.utcnow().isoformat(),
            "version": "2.0"
        }
        
        with open(export_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        with ss:
            docs_list = ss.list_documents()
        
        with open(export_dir / "documents.json", "w", encoding="utf-8") as f:
            json.dump(docs_list, f, indent=2)

        if db_path.exists():
            shutil.copy2(db_path, export_dir / "datastore.db")

        if docs_path.exists() and docs_path.is_dir():
            shutil.copytree(docs_path, export_dir / "documents")
        else:
            (export_dir / "documents").mkdir()

        safe_store_name = secure_filename(datastore_record.name) or "datastore"
        zip_filename = f"{safe_store_name}_export.zip"
        zip_path = temp_dir_path / zip_filename
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in export_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(export_dir)
                    zipf.write(file_path, arcname)

        with open(zip_path, 'rb') as f:
            zip_content = f.read()

        return Response(
            content=zip_content,
            media_type='application/zip',
            headers={'Content-Disposition': f'attachment; filename="{zip_filename}"'}
        )

@datastore_router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_datastore(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> DataStorePublic:
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    if not file.filename or not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Please upload a .zip file.")

    user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found.")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        zip_path = temp_dir_path / "upload.zip"
        
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        extract_dir = temp_dir_path / "extracted"
        resolved_extract_dir = extract_dir.resolve()
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                for member in zipf.infolist():
                    target_member_path = (extract_dir / member.filename).resolve()
                    if not target_member_path.is_relative_to(resolved_extract_dir):
                        raise HTTPException(status_code=400, detail="Malicious ZIP archive: Path traversal detected.")
                zipf.extractall(extract_dir)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Invalid ZIP file.")

        metadata_file = next(extract_dir.rglob("metadata.json"), None)
        if not metadata_file:
            raise HTTPException(status_code=400, detail="Invalid export archive: metadata.json not found.")

        export_root = metadata_file.parent

        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        new_name = name or metadata.get("name", "Imported Datastore")
        
        base_name = new_name
        counter = 1
        while db.query(DBDataStore).filter_by(owner_user_id=user_db.id, name=new_name).first():
            new_name = f"{base_name} ({counter})"
            counter += 1

        new_ds = DBDataStore(
            owner_user_id=user_db.id,
            name=new_name,
            description=metadata.get("description", f"Imported from {file.filename}"),
            vectorizer_name=metadata.get("vectorizer_name", "st"),
            vectorizer_config=metadata.get("vectorizer_config", {}),
            chunk_size=metadata.get("chunk_size", 2048),
            chunk_overlap=metadata.get("chunk_overlap", 256),
            chunking_strategy=metadata.get("chunking_strategy", "recursive") or "recursive",
            chunking_kwargs=metadata.get("chunking_kwargs", {}) or {}
        )
        
        try:
            db.add(new_ds)
            db.commit()
            db.refresh(new_ds)
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=400, detail="Datastore with this name already exists.")
        except Exception as e:
            db.rollback()
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Database error: {e}")

        new_db_path = get_datastore_db_path(current_user.username, new_ds.id)
        new_docs_path = get_user_datastore_root_path(current_user.username) / "safestore_docs" / new_ds.id
        new_docs_path.mkdir(parents=True, exist_ok=True)

        imported_db = export_root / "datastore.db"
        if imported_db.exists():
            get_safe_store_instance(current_user.username, new_ds.id, db, permission_level="revectorize")
            shutil.copy2(imported_db, new_db_path)

        imported_docs = export_root / "documents"
        if imported_docs.exists() and imported_docs.is_dir():
            if new_docs_path.exists():
                shutil.rmtree(new_docs_path)
            shutil.copytree(imported_docs, new_docs_path)

        if current_user.username in user_sessions and new_ds.id in user_sessions[current_user.username].get("safe_store_instances", {}):
            del user_sessions[current_user.username]["safe_store_instances"][new_ds.id]

        return DataStorePublic(
            id=new_ds.id,
            name=new_ds.name,
            description=new_ds.description,
            owner_username=current_user.username,
            permission_level="owner",
            vectorizer_name=new_ds.vectorizer_name,
            vectorizer_config=new_ds.vectorizer_config or {},
            chunk_size=new_ds.chunk_size,
            chunk_overlap=new_ds.chunk_overlap,
            chunking_strategy=new_ds.chunking_strategy,
            chunking_kwargs=new_ds.chunking_kwargs or {},
            created_at=new_ds.created_at,
            updated_at=new_ds.updated_at
        )