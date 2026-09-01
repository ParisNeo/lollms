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
from urllib.parse import unquote
import json
import time
import asyncio

# Third-Party Imports
from fastapi import (
    HTTPException,
    Depends,
    File,
    UploadFile,
    Form,
    APIRouter,
    status,
    Body,
    Query
)
from fastapi.responses import (
    Response,
    HTMLResponse
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
    DataStoreAnswerResponse,
    FullDocumentQueryRequest,
    DocumentWindowQueryRequest,
    DocumentChunksPaginatedResponse,
    DataStoreRevectorizeRequest
)

from backend.session import (
    get_datastore_db_path,
    build_lollms_client_from_params,
    get_current_active_user,
    get_safe_store_instance,
    get_user_datastore_root_path,
    get_user_lollms_client,
    user_sessions
)
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

from backend.task_manager import task_manager, Task
from backend.db.models.config import RAGBinding as DBRAGBinding, LLMBinding as DBLLMBinding
from backend.routers.files import extract_text_from_file_bytes

class DataStoreDetails(BaseModel):
    size_bytes: int
    chunk_count: int
    graph_nodes_count: int
    graph_edges_count: int
    
class GraphGenerationRequest(BaseModel):
    graph_type: str = "knowledge_graph"
    mode: str = "fast_hybrid"
    model_binding: Optional[str] = None
    model_name: Optional[str] = None
    mapping_rules: Optional[Dict[str, Any]] = None
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

class YoutubeImportRequest(BaseModel):
    video_url: str
    language: str = "en"

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

_data_lake_cache: Dict[str, Dict[str, Any]] = {}

DOCUMENT_PALETTE = [
    "#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ef4444",
    "#06b6d4", "#ec4899", "#14b8a6", "#f97316", "#6366f1",
    "#84cc16", "#a855f7", "#0ea5e9", "#eab308", "#d946ef"
]

def _sanitize_numpy(data: Any) -> Any:
    """Recursively converts numpy numbers and arrays to native Python types."""
    if np is None:
        return data
    if isinstance(data, dict):
        return {k: _sanitize_numpy(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_sanitize_numpy(item) for item in data]
    if isinstance(data, np.ndarray):
        return data.tolist()
    if isinstance(data, (np.number, np.bool_)):
        return data.item()
    return data

def _clean_llm_json_response(raw: str) -> str:
    """Strips thinking blocks and isolates balanced JSON."""
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
    def llm_executor_callback(prompt: str) -> str:
        try:
            raw = llm_client.generate_text(prompt, n_predict=2048, temperature=0.1)
        except TypeError:
            try:
                raw = llm_client.generate_text(prompt, max_new_tokens=2048, temperature=0.1)
            except TypeError:
                raw = llm_client.generate_text(prompt)

        if any(keyword in prompt.lower() for keyword in ["json", "format:", "schema", "decision", "extract_entities", "merge"]):
            return _clean_llm_json_response(raw)

        cleaned = re.sub(r'<think>[\s\S]*?</think>', '', raw, flags=re.IGNORECASE)
        cleaned = re.sub(r'<thought>[\s\S]*?</thought>', '', cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    return llm_executor_callback

def _resolve_user_llm_client(username: str, db: Session, request_data: dict = None):
    """Resolves a valid LollmsClient for the user using their active model preferences."""
    request_data = request_data or {}
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

def _generate_llm_answer(llm_client, full_prompt: str, max_tokens: int, temperature: float) -> str:
    """Invokes the LLM client defensively handling parameter signatures."""
    if not llm_client:
        raise ValueError("No active LLM client could be established. Please check your LLM binding connection.")

    try:
        res = llm_client.generate_text(full_prompt, n_predict=max_tokens, temperature=temperature)
        if res and isinstance(res, str) and res.strip():
            return res.strip()
    except TypeError:
        try:
            res = llm_client.generate_text(full_prompt, max_new_tokens=max_tokens, temperature=temperature)
            if res and isinstance(res, str) and res.strip():
                return res.strip()
        except TypeError:
            res = llm_client.generate_text(full_prompt)
            if res and isinstance(res, str) and res.strip():
                return res.strip()
    except Exception as e:
        raise ValueError(f"LLM generation failed: {e}")

    return "No response generated from the model."

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
                    elif metadata_option == 'auto-generate' and lc:
                        file_bytes = file_path.read_bytes()
                        text_content, _ = extract_text_from_file_bytes(file_bytes, file_path.name)
                        if text_content.strip():
                            metadata_prompt = "Generate short metadata for this document. Return a JSON object with 'title', 'subject', and 'authors'."
                            schema = {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "subject": {"type": "string"},
                                    "authors": {"type": "array", "items": {"type": "string"}}
                                },
                                "required": ["title", "subject"]
                            }
                            metadata = lc.generate_structured_content(text_content[:12000], schema=schema, system_prompt=metadata_prompt)

                    stats = ss.add_document(
                        str(file_path),
                        metadata=metadata,
                        vectorize_with_metadata=vectorize_with_metadata if metadata else False,
                    )
                    
                    num_added = stats.get('num_chunks_added', 0) if isinstance(stats, dict) else 1
                    if num_added > 0:
                        processed_count += 1
                        task.log(f"Successfully added {num_added} chunks from {file_path.name}.")
                    else:
                        error_count += 1
                        task.log(f"Skipped {file_path.name}: No valid text chunks extracted.", level="WARNING")

                except Exception as e:
                    error_count += 1
                    task.log(f"Error processing {file_path.name}: {e}", level="ERROR")

                progress = int(100 * (i + 1) / total_files)
                task.set_progress(progress)

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
        
        scraper = ScrapeMaster(url, strategy=["selenium", "beautifulsoup"], headless=True)
        results = scraper.scrape_all(max_depth=depth, convert_to_markdown=True)
            
        markdown_content = results.get('markdown') or "\n\n".join(results.get('texts', []))
        if not markdown_content:
             task.log("No content found at the given URL.", level="WARNING")
             return

        safe_url_name = "".join(c for c in url if c.isalnum() or c in ('-', '_')).rstrip()[:50]
        timestamp = int(time.time())
        filename = f"scraped_{safe_url_name}_{timestamp}.md"
        
        datastore_docs_path = get_user_datastore_root_path(datastore_record.owner.username) / "safestore_docs" / datastore_id
        datastore_docs_path.mkdir(parents=True, exist_ok=True)
        
        target_file_path = datastore_docs_path / filename
        target_file_path.write_text(f"# Scraped from {url}\n\n{markdown_content}", encoding="utf-8")
        
        task.log(f"Content saved to {filename}. Indexing to SafeStore...")
        
        with ss:
            stats = ss.add_document(str(target_file_path))
            num_added = stats.get('num_chunks_added', 0) if isinstance(stats, dict) else 1
            task.log(f"Successfully indexed {num_added} chunks from scraped content.")
            
        visited_urls = results.get('visited_urls', [])
        task.result = {"message": f"Scraping complete. Indexed content from {len(visited_urls)} page(s)."}

    except Exception as e:
        trace_exception(e)
        task.log(f"Error during scraping task: {e}", level="ERROR")
        raise e
    finally:
        db.close()

def _generate_graph_task(task: Task, username: str, datastore_id: str, request_data: dict):
    if not GraphStore:
        raise ImportError("GraphStore is not available.")

    build_mode = request_data.get("mode", "fast_hybrid")
    task.log(f"Starting knowledge graph build (Mode: {build_mode})...")
    task.set_progress(5)

    db = next(get_db())
    try:
        ss = get_safe_store_instance(username, datastore_id, db, permission_level="revectorize")

        from safe_store import TabularMapper, TBoxManager
        tbox = TBoxManager()
        custom_ontology = request_data.get("ontology")
        if custom_ontology and custom_ontology.strip():
            try:
                tbox.load_ontology(custom_ontology, format="turtle")
            except Exception as te:
                task.log(f"Ontology load notice: {te}", level="WARNING")

        docs = []
        with ss:
            docs = ss.list_documents()

        tabular_docs = []
        text_docs = []
        for d in docs:
            fpath = d.get("file_path", "")
            ext = Path(fpath).suffix.lower()
            if ext in [".csv", ".tsv", ".xlsx", ".xls", ".db", ".sqlite"]:
                tabular_docs.append(d)
            else:
                text_docs.append(d)

        if tabular_docs and hasattr(safe_store, 'TabularMapper'):
            task.log(f"Processing {len(tabular_docs)} structured table(s) via TabularMapper...")
            mapper = TabularMapper(store=ss, tbox=tbox)
            for td in tabular_docs:
                tf_path = td.get("file_path")
                if tf_path and Path(tf_path).exists():
                    ext = Path(tf_path).suffix.lower()
                    try:
                        if ext in [".csv", ".tsv"]:
                            mapper.map_csv(tf_path, mapping_rules=request_data.get("mapping_rules"))
                        elif ext in [".xlsx", ".xls"]:
                            mapper.map_excel(tf_path, mapping_rules=request_data.get("mapping_rules"))
                    except Exception as me:
                        task.log(f"Table mapping notice for {Path(tf_path).name}: {me}", level="WARNING")

        task.set_progress(40)

        if text_docs and build_mode != "declarative":
            llm_client = _resolve_user_llm_client(username, db, request_data)
            llm_executor_callback = _make_llm_graph_executor(llm_client)

            with ss:
                gs = GraphStore(store=ss, llm_executor_callback=llm_executor_callback)
                for i, doc in enumerate(text_docs):
                    if task.cancellation_event.is_set():
                        break
                    doc_id = doc.get("doc_id") or doc.get("id")
                    doc_name = Path(doc.get("file_path", "Unknown")).name
                    task.set_file_info(file_name=doc_name, total_files=len(text_docs))
                    try:
                        if hasattr(gs, "build_graph_for_document"):
                            gs.build_graph_for_document(doc_id, guidance=custom_ontology)
                        elif hasattr(gs, "build_graph"):
                            gs.build_graph(doc_id, guidance=custom_ontology)
                    except Exception as doc_err:
                        task.log(f"Entity notice for {doc_name}: {doc_err}", level="WARNING")

                    task.set_progress(int(40 + 55 * (i + 1) / max(len(text_docs), 1)))

        task.set_progress(100)
        task.result = {"message": "Knowledge graph construction complete."}
        task.log("Graph build complete.")

    except Exception as e:
        task.log(f"Error during graph build: {e}", level="CRITICAL")
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
                    task.log(f"Warning for '{doc_name}': {doc_err}", level="WARNING")

                task.set_progress(int(100 * (i + 1) / max(total_docs, 1)))

        task.result = {"message": "Graph update completed successfully."}
    except Exception as e:
        task.log(f"Error during graph update: {e}", level="CRITICAL")
        trace_exception(e)
        raise e
    finally:
        db.close()

def _revectorize_datastore_task(task: Task, username: str, datastore_id: str, new_vec_name: str, new_vec_config: dict):
    task.log(f"Starting revectorization of DataStore '{datastore_id}' with '{new_vec_name}'...")
    task.set_progress(10)
    db = next(get_db())
    try:
        ds_rec = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
        if not ds_rec:
            raise Exception("DataStore not found.")

        ss = get_safe_store_instance(username, datastore_id, db, permission_level="revectorize")
        task.set_progress(30)

        with ss:
            if hasattr(ss, "revectorize_database"):
                ss.revectorize_database(
                    new_vectorizer_name=new_vec_name,
                    new_vectorizer_config=new_vec_config
                )
            else:
                raise Exception("Installed safe_store version does not support revectorize_database.")

        ds_rec.vectorizer_name = new_vec_name
        ds_rec.vectorizer_config = new_vec_config
        db.commit()

        _data_lake_cache.clear()
        if username in user_sessions and datastore_id in user_sessions[username].get("safe_store_instances", {}):
            del user_sessions[username]["safe_store_instances"][datastore_id]

        task.set_progress(100)
        manager.broadcast_sync({"type": "datastore_updated", "datastore_id": datastore_id})
        return {"message": f"Successfully revectorized '{ds_rec.name}'."}
    except Exception as e:
        task.log(f"Revectorization failed: {e}", level="ERROR")
        trace_exception(e)
        raise e
    finally:
        db.close()

def _import_youtube_datastore_task(task: Task, username: str, datastore_id: str, video_url: str, language: str):
    task.log(f"Fetching YouTube transcript for {video_url}...")
    task.set_progress(15)

    pm.ensure_packages(["youtube-transcript-api"])
    from youtube_transcript_api import YouTubeTranscriptApi

    video_id_match = re.search(r'(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})', video_url)
    if not video_id_match:
        raise ValueError("Invalid YouTube URL.")
    video_id = video_id_match.group(1)

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = None
        try:
            transcript = transcript_list.find_transcript([language])
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript([language])
            except Exception:
                for t in transcript_list:
                    transcript = t.translate(language)
                    break

        if not transcript:
            raise Exception("No suitable transcript found.")

        data = transcript.fetch()
        lines = [f"[{int(entry.get('start', 0)) // 60:02d}:{int(entry.get('start', 0)) % 60:02d}] {entry.get('text', '')}" for entry in data]
        full_transcript = "\n".join(lines)

        db = next(get_db())
        try:
            datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
            docs_dir = get_user_datastore_root_path(datastore_record.owner.username) / "safestore_docs" / datastore_id
            docs_dir.mkdir(parents=True, exist_ok=True)

            safe_filename_val = f"YouTube_Transcript_{video_id}.md"
            file_path = docs_dir / safe_filename_val
            file_path.write_text(f"# YouTube Transcript ({video_id})\nSource: {video_url}\n\n{full_transcript}", encoding="utf-8")

            ss = get_safe_store_instance(username, datastore_id, db, permission_level="read_write")
            with ss:
                ss.add_document(str(file_path))

            task.set_progress(100)
            task.result = {"message": f"Successfully indexed YouTube transcript ({video_id})."}
        finally:
            db.close()
    except Exception as e:
        task.log(f"YouTube transcript ingestion failed: {e}", "ERROR")
        trace_exception(e)
        raise e

# --- SafeStore File Management API (per-datastore) ---
store_files_router = APIRouter(prefix="/api/store/{datastore_id}", tags=["SafeStore RAG & File Management"])

@store_files_router.get("/info", response_model=Dict[str, Any])
async def get_datastore_diagnostic_info(
    datastore_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Returns full database diagnostic introspection using SafeStore's native get_database_info() method.
    """
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")

    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_query")
        datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
        if not datastore_record:
            raise HTTPException(status_code=404, detail="Datastore not found.")

        owner_username = datastore_record.owner.username
        db_path = get_datastore_db_path(owner_username, datastore_id)

        info_payload = {}
        with ss:
            if hasattr(ss, "get_database_info"):
                info_payload = ss.get_database_info()
            else:
                chunk_cnt = ss.count_chunks() if hasattr(ss, 'count_chunks') else 0
                doc_list = ss.list_documents() if hasattr(ss, 'list_documents') else []
                info_payload = {
                    "database_path": str(db_path),
                    "vectorizer": {"name": datastore_record.vectorizer_name, "config": datastore_record.vectorizer_config},
                    "chunking": {"chunk_size": datastore_record.chunk_size, "chunk_overlap": datastore_record.chunk_overlap},
                    "documents": {"total_documents": len(doc_list), "list": doc_list},
                    "chunks": {"total_chunks": chunk_cnt}
                }

        info_payload["size_bytes"] = os.path.getsize(db_path) if db_path.exists() else 0
        info_payload["datastore_id"] = datastore_id
        info_payload["name"] = datastore_record.name
        info_payload["description"] = datastore_record.description

        return _sanitize_numpy(info_payload)
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Error getting diagnostic info: {e}")

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

        size_bytes = os.path.getsize(db_path) if db_path.exists() else 0
        chunk_count = 0
        nodes_count = 0
        edges_count = 0

        with ss:
            if hasattr(ss, 'get_database_info'):
                db_info = ss.get_database_info()
                chunk_count = db_info.get('chunks', {}).get('total_chunks', 0)
                nodes_count = db_info.get('knowledge_graph', {}).get('total_nodes', 0)
                edges_count = db_info.get('knowledge_graph', {}).get('total_relationships', 0)
            else:
                if hasattr(ss, 'count_chunks'):
                    chunk_count = ss.count_chunks()
                elif hasattr(ss, 'db') and hasattr(ss.db, 'count'):
                    chunk_count = ss.db.count('chunks')
                if GraphStore:
                    try:
                        gs = GraphStore(store=ss)
                        nodes_count = gs.count_nodes()
                        edges_count = gs.count_relationships()
                    except Exception:
                        pass

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
        with open(target_file_path, "wb") as buffer:
            shutil.copyfileobj(file_upload.file, buffer)
        saved_file_paths.append(str(target_file_path))
        await file_upload.close()

    db_task = task_manager.submit_task(
        name=f"Add files to DataStore: {datastore_record.name}",
        target=_upload_rag_files_task,
        args=(current_user.username, datastore_id, saved_file_paths, metadata_option, manual_metadata_json, vectorize_with_metadata),
        description=f"Adding {len(files)} files to '{datastore_record.name}'.",
        owner_username=current_user.username
    )
    return db_task

@store_files_router.post("/revectorize", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def revectorize_single_datastore(
    datastore_id: str,
    payload: DataStoreRevectorizeRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> TaskInfo:
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")

    get_safe_store_instance(current_user.username, datastore_id, db, permission_level="revectorize")
    ds_rec = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    if not ds_rec:
        raise HTTPException(status_code=404, detail="DataStore not found.")

    db_task = task_manager.submit_task(
        name=f"Revectorize DataStore: {ds_rec.name}",
        target=_revectorize_datastore_task,
        args=(current_user.username, datastore_id, payload.vectorizer_name, payload.vectorizer_config),
        description=f"Migrating embeddings of '{ds_rec.name}' to '{payload.vectorizer_name}'.",
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
    if not safe_store or not ScrapeMaster: raise HTTPException(status_code=501, detail="SafeStore / ScrapeMaster not available.")

    get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_write")
    datastore_record = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record: raise HTTPException(status_code=404, detail="Datastore not found.")

    db_task = task_manager.submit_task(
        name=f"Scrape URL to DataStore: {datastore_record.name}",
        target=_scrape_url_task,
        args=(current_user.username, datastore_id, request.url, request.depth),
        description=f"Scraping {request.url} into '{datastore_record.name}'.",
        owner_username=current_user.username
    )
    return db_task

@store_files_router.post("/import-youtube", response_model=TaskInfo, status_code=status.HTTP_202_ACCEPTED)
async def import_youtube_to_datastore(
    datastore_id: str,
    request: YoutubeImportRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> TaskInfo:
    get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_write")
    datastore_record = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record: raise HTTPException(status_code=404, detail="Datastore not found.")

    db_task = task_manager.submit_task(
        name=f"Add YouTube to DataStore: {datastore_record.name}",
        target=_import_youtube_datastore_task,
        args=(current_user.username, datastore_id, request.video_url, request.language),
        description=f"Fetching & vectorizing YouTube transcript ({request.video_url}).",
        owner_username=current_user.username
    )
    return db_task

@store_files_router.get("/files", response_model=List[SafeStoreDocumentInfo])
async def list_rag_documents_in_datastore(
    datastore_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[SafeStoreDocumentInfo]:
    if not safe_store: 
        return []
    ss = get_safe_store_instance(current_user.username, datastore_id, db) 
    managed_docs = []
    try:
        with ss: 
            stored_meta = ss.list_documents()

            doc_chunk_counts = {}
            doc_char_counts = {}
            if hasattr(ss, "get_database_info"):
                try:
                    db_diag = ss.get_database_info()
                    for d_entry in db_diag.get("documents", {}).get("list", []):
                        d_name = d_entry.get("document_title") or Path(d_entry.get("file_path", "")).name
                        if d_name:
                            doc_chunk_counts[d_name] = d_entry.get("chunk_count", 0)
                            doc_char_counts[d_name] = d_entry.get("char_count", 0)
                except Exception:
                    pass

        for doc_meta in stored_meta:
            original_path_str = doc_meta.get("file_path")
            if original_path_str:
                filename = Path(original_path_str).name
                chunk_cnt = doc_chunk_counts.get(filename, doc_meta.get("chunk_count"))
                char_cnt = doc_char_counts.get(filename, doc_meta.get("char_count"))
                managed_docs.append(SafeStoreDocumentInfo(
                    filename=filename, 
                    metadata=doc_meta.get("metadata"),
                    chunk_count=chunk_cnt,
                    char_count=char_cnt
                ))
    except Exception as e: 
        raise HTTPException(status_code=500, detail=f"Error listing RAG docs: {e}")

    unique_docs = {doc.filename: doc for doc in managed_docs}
    return sorted(list(unique_docs.values()), key=lambda x: x.filename)

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
async def delete_rag_document_from_datastore(
    datastore_id: str,
    filename: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
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
        return {"message": f"Document '{s_filename}' deleted successfully."}
    except Exception as e:
        if file_to_delete_path.exists(): raise HTTPException(status_code=500, detail=f"Could not delete '{s_filename}': {e}")
        return {"message": f"Document '{s_filename}' deleted."}

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
            except Exception:
                failed_files.append(filename)

    return {
        "message": f"Deleted {deleted_count} documents.",
        "deleted_count": deleted_count,
        "failed_files": failed_files
    }

@store_files_router.get("/data-lake", response_model=DataLakeResponse)
async def get_datastore_data_lake_projection(
    datastore_id: str,
    method: str = "pca",
    dimensions: int = 2,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_query")
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record:
        raise HTTPException(status_code=404, detail="Datastore not found")

    owner_username = datastore_record.owner.username
    db_path = get_datastore_db_path(owner_username, datastore_id)
    if not db_path.exists():
        return DataLakeResponse(points=[], documents=[], total_chunks=0, reduction_method=method)

    mtime = db_path.stat().st_mtime
    cache_key = f"{datastore_id}_{method.lower()}_{dimensions}d"

    if cache_key in _data_lake_cache and _data_lake_cache[cache_key]["mtime"] == mtime:
        return _data_lake_cache[cache_key]["response"]

    try:
        with ss:
            raw_view = ss.get_datalake_view(
                method=method.lower(),
                n_components=dimensions,
                output_format='dict'
            )

        if not raw_view:
            return DataLakeResponse(points=[], documents=[], total_chunks=0, reduction_method=method)

        document_chunks_count = {}
        doc_titles = {}
        doc_color_map = {}
        doc_coords_accumulator = {}

        for p in raw_view:
            doc_id = str(p.get("document_id") or p.get("doc_id") or p.get("file_path") or "doc_1")
            raw_title = str(p.get("document_title") or p.get("title") or Path(doc_id).name or "Document")
            doc_titles[doc_id] = raw_title
            document_chunks_count[doc_id] = document_chunks_count.get(doc_id, 0) + 1

        unique_docs = sorted(list(document_chunks_count.keys()))
        for idx, doc_id in enumerate(unique_docs):
            doc_color_map[doc_id] = DOCUMENT_PALETTE[idx % len(DOCUMENT_PALETTE)]

        points = []
        for idx, p in enumerate(raw_view):
            doc_id = str(p.get("document_id") or p.get("doc_id") or p.get("file_path") or "doc_1")
            x_val = float(p.get("x", 0.0))
            y_val = float(p.get("y", 0.0))
            if np.isnan(x_val) or np.isinf(x_val): x_val = 0.0
            if np.isnan(y_val) or np.isinf(y_val): y_val = 0.0

            text_content = str(p.get("chunk_text") or p.get("content") or p.get("text") or "")
            snippet = text_content[:180] + ("..." if len(text_content) > 180 else "")

            points.append(DataLakeChunkPoint(
                id=str(p.get("id") or p.get("chunk_id") or f"c_{idx}"),
                document_id=doc_id,
                document_name=doc_titles.get(doc_id, "Document"),
                chunk_index=int(p.get("chunk_index", idx)),
                text_snippet=snippet,
                full_text=text_content,
                x=round(x_val, 5),
                y=round(y_val, 5),
                metadata=p.get("metadata") or p.get("document_metadata") or {},
                color=doc_color_map.get(doc_id, "#3b82f6")
            ))
            doc_coords_accumulator.setdefault(doc_id, []).append((x_val, y_val))

        doc_legends = []
        for doc_id in unique_docs:
            d_name = doc_titles.get(doc_id, "Document")
            d_coords = doc_coords_accumulator.get(doc_id, [(0.0, 0.0)])
            c_x = float(np.mean([pt[0] for pt in d_coords]))
            c_y = float(np.mean([pt[1] for pt in d_coords]))
            if np.isnan(c_x) or np.isinf(c_x): c_x = 0.0
            if np.isnan(c_y) or np.isinf(c_y): c_y = 0.0

            doc_legends.append(DataLakeDocumentLegend(
                id=doc_id,
                name=d_name,
                chunk_count=document_chunks_count.get(doc_id, 0),
                color=doc_color_map.get(doc_id, "#3b82f6"),
                centroid={"x": round(c_x, 5), "y": round(c_y, 5)}
            ))

        response_obj = DataLakeResponse(
            points=points,
            documents=doc_legends,
            total_chunks=len(points),
            dimensions=dimensions,
            reduction_method=method.upper()
        )
        _data_lake_cache[cache_key] = {"mtime": mtime, "response": response_obj}
        return response_obj

    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Point cloud projection failed: {str(e)}")

@store_files_router.get("/data-lake/export-html", response_class=HTMLResponse)
async def export_datastore_datalake_html(
    datastore_id: str,
    method: str = "pca",
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_query")
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record:
        raise HTTPException(status_code=404, detail="Datastore not found")

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tf:
        tmp_html_path = tf.name

    try:
        with ss:
            if hasattr(ss, "export_datalake_html"):
                try:
                    ss.export_datalake_html(
                        output_file=tmp_html_path,
                        title=f"{datastore_record.name} · Semantic Data Lake",
                        method=method.lower(),
                        n_components=3
                    )
                except TypeError:
                    ss.export_datalake_html(tmp_html_path)
                with open(tmp_html_path, "r", encoding="utf-8") as f:
                    html_content = f.read()
                return HTMLResponse(content=html_content)
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"HTML visualizer generation failed: {e}")
    finally:
        if os.path.exists(tmp_html_path):
            try: os.unlink(tmp_html_path)
            except Exception: pass

@store_files_router.post("/query-answer", response_model=DataStoreAnswerResponse)
async def query_datastore_and_answer(
    datastore_id: str,
    request_data: DataStoreAnswerRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> DataStoreAnswerResponse:
    """
    Queries the DataStore and uses the user's active LLM model profile to synthesize a grounded answer citing the retrieved chunks.
    """
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db)
    min_threshold = float(request_data.min_similarity_percent)
    results = []

    # 1. Retrieve Evidence Chunks
    with ss:
        if request_data.mode in ("hybrid", "graph_hybrid") and hasattr(ss, "hybrid_query"):
            try:
                raw_hybrid = ss.hybrid_query(
                    query_text=request_data.query,
                    top_k=request_data.top_k,
                    dense_weight=request_data.dense_weight,
                    bm25_weight=request_data.bm25_weight,
                    rrf_k=request_data.rrf_k,
                    min_relevance_percent=min_threshold
                )
            except TypeError:
                try:
                    raw_hybrid = ss.hybrid_query(
                        query_text=request_data.query,
                        top_k=request_data.top_k,
                        dense_weight=request_data.dense_weight,
                        bm25_weight=request_data.bm25_weight,
                        rrf_k=request_data.rrf_k
                    )
                except Exception:
                    raw_hybrid = ss.query(request_data.query, top_k=request_data.top_k, min_similarity_percent=min_threshold)

            results = raw_hybrid if raw_hybrid else []
        else:
            results = ss.query(
                request_data.query, 
                top_k=request_data.top_k, 
                min_similarity_percent=min_threshold
            )

    sanitized_results = _sanitize_numpy(results)

    if not sanitized_results:
        return DataStoreAnswerResponse(
            answer="No relevant documents or information were found in the data store matching your query criteria.",
            chunks=[],
            model_name=None
        )

    # 2. Build Grounded Prompt Context
    context_blocks = []
    for i, chunk in enumerate(sanitized_results):
        fpath = chunk.get("file_path") or chunk.get("document_title") or chunk.get("title") or "Document"
        fname = Path(fpath).name if fpath else f"Doc {i+1}"
        ctext = chunk.get("chunk_text") or chunk.get("content") or chunk.get("text") or ""
        score = chunk.get("relevance_score") or chunk.get("similarity_percent") or chunk.get("fused_score") or ""
        score_str = f" (Similarity: {score:.1f}%)" if isinstance(score, (int, float)) and score > 1 else (f" (Score: {score:.4f})" if isinstance(score, (int, float)) else "")
        context_blocks.append(f"--- Evidence [{i+1}] Source: {fname}{score_str} ---\n{ctext}\n--- End Evidence [{i+1}] ---")

    context_text = "\n\n".join(context_blocks)

    system_prompt = request_data.system_prompt or (
        "You are an expert AI knowledge analyst analyzing verified documents.\n"
        "Answer the question accurately using ONLY the provided evidence.\n"
        "Rules:\n"
        "1. Ground all claims directly in the evidence.\n"
        "2. Cite sources using [1], [2], etc., corresponding to the evidence indices.\n"
        "3. If evidence is insufficient, explicitly state what is missing."
    )

    full_prompt = (
        f"{system_prompt}\n\n"
        f"=== VERIFIED EVIDENCE ===\n\n{context_text}\n\n"
        f"=== QUESTION ===\n{request_data.query}\n\n"
        "=== GROUNDED ANSWER ==="
    )

    # 3. Resolve Active User LLM Client
    llm_client = None
    try:
        user_model_full = current_user.lollms_model_name
        binding_alias = None
        model_name = None
        if user_model_full and '/' in user_model_full:
            binding_alias, model_name = user_model_full.split('/', 1)

        llm_client = build_lollms_client_from_params(
            username=current_user.username,
            binding_alias=binding_alias,
            model_name=model_name,
            load_llm=True
        )
    except Exception as e:
        try:
            llm_client = _resolve_user_llm_client(current_user.username, db, {})
        except Exception as resolve_err:
            print(f"Failed to resolve LLM client: {resolve_err}")

    max_tokens_val = request_data.max_tokens or 2048
    temp_val = request_data.temperature if request_data.temperature is not None else 0.2

    # 4. Synthesize Answer
    try:
        answer = await asyncio.to_thread(
            _generate_llm_answer,
            llm_client,
            full_prompt,
            max_tokens_val,
            temp_val
        )
    except Exception as gen_err:
        trace_exception(gen_err)
        answer = f"⚠️ Could not synthesize answer with the LLM: {gen_err}\n\nHowever, {len(sanitized_results)} relevant evidence chunk(s) were successfully retrieved and are listed below."

    model_name = (
        getattr(llm_client, "model_name", None) or 
        getattr(llm_client, "llm_binding_name", None) or 
        current_user.lollms_model_name or 
        "LLM"
    )

    return DataStoreAnswerResponse(
        answer=answer,
        chunks=sanitized_results,
        model_name=model_name
    )

@store_files_router.post("/query-full-documents", response_model=List[Dict])
async def query_full_documents(
    datastore_id: str,
    request_data: FullDocumentQueryRequest,
    min_relevance_percent: float = Query(50.0, ge=0.0, le=100.0),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[Dict]:
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")
    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db)
        results = []
        with ss:
            if hasattr(ss, "query_full_documents"):
                try:
                    results = ss.query_full_documents(
                        query_text=request_data.query,
                        top_k_docs=request_data.top_k_docs,
                        search_mode=request_data.search_mode,
                        min_relevance_percent=min_relevance_percent
                    )
                except TypeError:
                    results = ss.query_full_documents(
                        query_text=request_data.query,
                        top_k_docs=request_data.top_k_docs,
                        search_mode=request_data.search_mode
                    )
            else:
                raw = ss.query(request_data.query, top_k=request_data.top_k_docs, min_similarity_percent=min_relevance_percent)
                seen = set()
                for r in raw:
                    fpath = r.get("file_path")
                    if fpath and fpath not in seen:
                        seen.add(fpath)
                        txt = ss.reconstruct_document_text(fpath) if hasattr(ss, "reconstruct_document_text") else r.get("chunk_text", "")
                        results.append({
                            "document_title": Path(fpath).name,
                            "file_path": fpath,
                            "full_text": txt,
                            "relevance_score": r.get("similarity_percent", 100.0),
                            "metadata": r.get("document_metadata", {})
                        })

        filtered = [
            doc for doc in results
            if doc.get("relevance_score", doc.get("score", 100.0)) >= min_relevance_percent
        ]
        return _sanitize_numpy(filtered)
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Error in full document retrieval: {e}")

@store_files_router.post("/query-window", response_model=List[Dict])
async def query_document_window(
    datastore_id: str,
    request_data: DocumentWindowQueryRequest,
    min_relevance_percent: float = Query(50.0, ge=0.0, le=100.0),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[Dict]:
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")
    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db)
        results = []
        with ss:
            if hasattr(ss, "query_document_content_window"):
                try:
                    results = ss.query_document_content_window(
                        query_text=request_data.query,
                        top_k_hits=request_data.top_k_hits,
                        window_before=request_data.window_before,
                        window_after=request_data.window_after,
                        min_relevance_percent=min_relevance_percent
                    )
                except TypeError:
                    results = ss.query_document_content_window(
                        query_text=request_data.query,
                        top_k_hits=request_data.top_k_hits,
                        window_before=request_data.window_before,
                        window_after=request_data.window_after
                    )
            else:
                results = ss.query(request_data.query, top_k=request_data.top_k_hits, min_similarity_percent=min_relevance_percent)
                for r in results:
                    r["stitched_window_text"] = r.get("chunk_text", "")

        filtered = [
            w for w in results
            if w.get("relevance_score", w.get("similarity_percent", w.get("score", 100.0))) >= min_relevance_percent
        ]
        return _sanitize_numpy(filtered)
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Error in window retrieval: {e}")

@store_files_router.get("/documents/{document_identifier:path}/chunks-paginated", response_model=DocumentChunksPaginatedResponse)
async def get_document_chunks_paginated(
    datastore_id: str,
    document_identifier: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore not available.")
    try:
        ss = get_safe_store_instance(current_user.username, datastore_id, db)
        decoded = unquote(document_identifier)
        with ss:
            if hasattr(ss, "get_document_content_paginated"):
                res = ss.get_document_content_paginated(
                    document_id=decoded,
                    page=page,
                    page_size=page_size
                )
                return _sanitize_numpy(res)

        datastore_record = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
        db_path = get_datastore_db_path(datastore_record.owner.username, datastore_id)
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT rowid, * FROM chunks WHERE document_id LIKE ? OR file_path LIKE ? ORDER BY chunk_index ASC", (f"%{decoded}%", f"%{decoded}%"))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        total = len(rows)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        paged = rows[start:start + page_size]

        formatted = []
        for r in paged:
            formatted.append({
                "id": str(r.get("id") or r.get("rowid") or r.get("chunk_id")),
                "chunk_index": int(r.get("chunk_index") or 0),
                "text": str(r.get("chunk_text") or r.get("text") or r.get("content") or ""),
                "metadata": json.loads(r["metadata"]) if r.get("metadata") and isinstance(r["metadata"], str) else (r.get("metadata") or {})
            })

        return DocumentChunksPaginatedResponse(
            document_id=decoded,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_chunks=total,
            chunks=formatted
        )
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Error paginating document chunks: {e}")

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
        min_threshold = float(request_data.min_similarity_percent)
        results = []
        with ss:
            if request_data.retrieval_target == "full_documents" and hasattr(ss, "query_full_documents"):
                try:
                    results = ss.query_full_documents(
                        query_text=request_data.query,
                        top_k_docs=request_data.top_k,
                        search_mode=request_data.mode,
                        min_relevance_percent=min_threshold
                    )
                except TypeError:
                    results = ss.query_full_documents(
                        query_text=request_data.query,
                        top_k_docs=request_data.top_k,
                        search_mode=request_data.mode
                    )
                results = [r for r in results if r.get("relevance_score", r.get("score", 100.0)) >= min_threshold]

            elif request_data.retrieval_target == "window" and hasattr(ss, "query_document_content_window"):
                try:
                    results = ss.query_document_content_window(
                        query_text=request_data.query,
                        top_k_hits=request_data.top_k,
                        window_before=request_data.window_before,
                        window_after=request_data.window_after,
                        min_relevance_percent=min_threshold
                    )
                except TypeError:
                    results = ss.query_document_content_window(
                        query_text=request_data.query,
                        top_k_hits=request_data.top_k,
                        window_before=request_data.window_before,
                        window_after=request_data.window_after
                    )
                results = [r for r in results if r.get("relevance_score", r.get("similarity_percent", r.get("score", 100.0))) >= min_threshold]

            elif request_data.mode == "hybrid" and hasattr(ss, "hybrid_query"):
                try:
                    raw_hybrid = ss.hybrid_query(
                        query_text=request_data.query,
                        top_k=request_data.top_k,
                        dense_weight=request_data.dense_weight,
                        bm25_weight=request_data.bm25_weight,
                        rrf_k=request_data.rrf_k,
                        min_similarity_percent=min_threshold
                    )
                except TypeError:
                    raw_hybrid = ss.hybrid_query(
                        query_text=request_data.query,
                        top_k=request_data.top_k,
                        dense_weight=request_data.dense_weight,
                        bm25_weight=request_data.bm25_weight,
                        rrf_k=request_data.rrf_k
                    )
                results = raw_hybrid if raw_hybrid else []
            else:
                results = ss.query(
                    request_data.query, 
                    top_k=request_data.top_k, 
                    min_similarity_percent=min_threshold
                )
        return _sanitize_numpy(results)
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
        raise HTTPException(status_code=404, detail="Datastore metadata not found.")

    req_dict = request_data.model_dump() if request_data else {}
    db_task = task_manager.submit_task(
        name=f"Generate Graph for: {datastore_record.name}",
        target=_generate_graph_task,
        args=(current_user.username, datastore_id, req_dict),
        description=f"Generating knowledge graph for '{datastore_record.name}'.",
        owner_username=current_user.username
    )
    return db_task

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
        raise HTTPException(status_code=404, detail="Datastore metadata not found.")

    req_dict = request_data.model_dump() if request_data else {}
    db_task = task_manager.submit_task(
        name=f"Update Graph for: {datastore_record.name}",
        target=_update_graph_task,
        args=(current_user.username, datastore_id, req_dict),
        description=f"Updating knowledge graph for '{datastore_record.name}'.",
        owner_username=current_user.username
    )
    return db_task

class ExpandClassRequest(BaseModel):
    class_uri: str
    offset: int = 0
    limit: int = 150

class ShortestPathRequest(BaseModel):
    source_uri: str
    target_uri: str

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

        nodes_out = []
        type_counts = {}
        for n in sanitized_nodes:
            lbl = n.get("label") or "Entity"
            type_counts[lbl] = type_counts.get(lbl, 0) + 1

        if mode == "tbox_summary":
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
            for n in sanitized_nodes:
                nid = str(n.get("id"))
                nlabel = str(n.get("properties", {}).get("identifying_value") or n.get("properties", {}).get("name") or n.get("properties", {}).get("label") or n.get("label") or nid)
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
    if not GraphStore:
        raise HTTPException(status_code=501, detail="GraphStore not available.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db, permission_level="read_query")
    with ss:
        gs = GraphStore(store=ss, llm_executor_callback=None)
        raw_nodes = gs.get_all_nodes_for_visualization(limit=10000) if hasattr(gs, "get_all_nodes_for_visualization") else []
        raw_edges = gs.get_all_relationships_for_visualization(limit=20000) if hasattr(gs, "get_all_relationships_for_visualization") else []

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
        llm_client = _resolve_user_llm_client(current_user.username, db, {})
        def llm_executor_callback(prompt: str) -> str:
            return llm_client.generate_text(prompt, max_new_tokens=2048)
            
        ss = get_safe_store_instance(current_user.username, datastore_id, db)
        with ss:
            gs = GraphStore(store=ss, llm_executor_callback=llm_executor_callback)
            results = gs.query_graph(request_data.query, output_mode="chunks_summary")
        return _sanitize_numpy(results)
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
        "You are an expert Semantic Ontologist. Analyze document excerpts and create a domain ontology schema.\n"
        "Return ONLY a strictly valid JSON object inside ```json ... ``` with structure:\n"
        "{\n"
        '  "nodes": [{ "type": "class|property", "name": "PascalCaseName", "rdfsLabel": "Human Label", "comment": "Definition" }],\n'
        '  "edges": [{ "source": "SourceClass", "target": "TargetClass", "relType": "subClassOf|domain|range" }]\n'
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
                        aliases = json.loads(binding.model_aliases) if isinstance(binding.model_aliases, str) else binding.model_aliases
                    except Exception:
                        pass

                processed_models = []
                if not sorted_raw_names:
                    processed_models.append({"name": binding.alias, "value": ""})
                else:
                    for raw_name in sorted_raw_names:
                        alias_info = aliases.get(raw_name)
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
        raise HTTPException(status_code=404, detail="User record not found.") 

    owned_datastores_db = db.query(DBDataStore).filter(DBDataStore.owner_user_id == user_db_record.id).order_by(DBDataStore.name).all()
    
    shared_links_and_datastores_db = db.query(
        DBSharedDataStoreLink, DBDataStore
    ).join(
        DBDataStore, DBSharedDataStoreLink.datastore_id == DBDataStore.id
    ).filter(
        DBSharedDataStoreLink.shared_with_user_id == user_db_record.id 
    ).order_by(
        DBDataStore.name
    ).options(
        joinedload(DBSharedDataStoreLink.datastore).joinedload(DBDataStore.owner)
    ).all()

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

    active_bindings = db.query(DBRAGBinding).filter(DBRAGBinding.is_active == True).count()
    if active_bindings == 0:
        raise HTTPException(status_code=400, detail="Cannot create DataStore: No active RAG vectorizers are configured in the system.")

    force_rag = settings.get("force_rag_settings_mode") == "force_always"
    forced_vec = settings.get("force_rag_vectorizer")

    effective_vec_name = (forced_vec if force_rag and forced_vec else ds_create.vectorizer_name) or "default_st"
    effective_vec_config = ds_create.vectorizer_config or {}

    new_ds_db_obj = DBDataStore(
        owner_user_id=user_db_record.id, 
        name=ds_create.name, 
        description=ds_create.description,
        vectorizer_name=effective_vec_name,
        vectorizer_config=effective_vec_config,
        chunk_size=(settings.get("force_rag_chunk_size", 2048) if force_rag else (ds_create.chunk_size or settings.get("default_chunk_size", 2048))),
        chunk_overlap=(settings.get("force_rag_chunk_overlap", 256) if force_rag else (ds_create.chunk_overlap or settings.get("default_chunk_overlap", 256))),
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
        if existing_ds: raise HTTPException(status_code=400, detail=f"A DataStore with the name '{ds_update.name}' already exists.")

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
            
        return {"message": f"DataStore '{ds_db_obj.name}' deleted."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"DB error deleting datastore: {e}")

@datastore_router.get("/{datastore_id}/shared-with", response_model=List[SharedWithUserPublic])
async def get_datastore_shared_with_list(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db: raise HTTPException(status_code=404, detail="User not found.")

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
    if not owner_user_db: raise HTTPException(status_code=404, detail="User not found.")

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
            return {"message": f"DataStore '{ds_to_share.name}' permission updated."}
        return {"message": f"DataStore '{ds_to_share.name}' already shared."}

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
        return {"message": f"DataStore '{ds_to_share.name}' shared successfully."}
    except IntegrityError: 
        db.rollback()
        raise HTTPException(status_code=400, detail="Sharing conflict.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB error sharing datastore: {e}")

@datastore_router.delete("/{datastore_id}/share/{target_user_id}", status_code=status.HTTP_200_OK)
async def unshare_datastore(datastore_id: str, target_user_id: int, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db: raise HTTPException(status_code=404, detail="User not found.")

    ds_to_unshare = db.query(DBDataStore).filter(DBDataStore.id == datastore_id, DBDataStore.owner_user_id == owner_user_db.id).first()
    if not ds_to_unshare: raise HTTPException(status_code=404, detail="DataStore not found.")
        
    target_user_db = db.query(DBUser).filter(DBUser.id == target_user_id).first()
    if not target_user_db: raise HTTPException(status_code=404, detail="Target user not found.")

    link_to_delete = db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id, shared_with_user_id=target_user_db.id).first()
    if not link_to_delete:
        raise HTTPException(status_code=404, detail="DataStore was not shared with user.")

    try:
        db.delete(link_to_delete)
        db.commit()
        return {"message": f"Sharing revoked."}
    except Exception as e:
        db.rollback()
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