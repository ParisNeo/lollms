# Standard Library Imports
import os
import shutil
import uuid
import json
from pathlib import Path
from typing import List, Dict, Optional, Any, cast, Union, Tuple, AsyncGenerator
import datetime
import asyncio
import threading
import traceback
import io

# Third-Party Imports
import toml
import yaml
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
    File,
    UploadFile,
    Form,
    APIRouter,
    Response,
    Query,
    BackgroundTasks
)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import (
    HTMLResponse,
    StreamingResponse,
    JSONResponse,
    FileResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, constr, field_validator, validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import (
    or_, and_ # Add this line
)
from dataclasses import dataclass, field as dataclass_field
from werkzeug.utils import secure_filename
from pydantic import BaseModel, Field, constr, field_validator, validator # Ensure these are imported
import datetime # Ensure datetime is imported

from backend.database_setup import Personality as DBPersonality # Add this import at the top of main.py

# Local Application Imports
from backend.database_setup import (
    User as DBUser,
    UserStarredDiscussion,
    UserMessageGrade,
    FriendshipStatus,Friendship, 
    DataStore as DBDataStore,
    SharedDataStoreLink as DBSharedDataStoreLink,
    init_database,
    get_db,
    hash_password,
    DATABASE_URL_CONFIG_KEY,
)
from lollms_client import (
    LollmsClient,
    MSG_TYPE,
    LollmsDiscussion as LollmsClientDiscussion,
    ELF_COMPLETION_FORMAT, # For client params
)

# safe_store is expected to be installed
try:
    import safe_store
    from safe_store import (
        LogLevel as SafeStoreLogLevel,
    )
except ImportError:
    print(
        "WARNING: safe_store library not found. RAG features will be disabled. Install with: pip install safe_store[all]"
    )
    safe_store = None
    SafeStoreLogLevel = None

# --- Pydantic Models for API ---
from backend.models import (
UserAuthDetails,
SafeStoreDocumentInfo,
)
from backend.session import (
    get_current_active_user,
    get_db, get_safe_store_instance,
    get_user_datastore_root_path,
    )



# --- SafeStore File Management API (now per-datastore) ---
store_files_router = APIRouter(prefix="/api/store/{datastore_id}", tags=["SafeStore RAG & File Management"])

@store_files_router.get("/vectorizers", response_model=List[Dict[str,str]])
async def list_datastore_vectorizers(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[Dict[str,str]]:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    ss = get_safe_store_instance(current_user.username, datastore_id, db) 
    try:
        with ss: methods_in_db = ss.list_vectorization_methods(); possible_names = ss.list_possible_vectorizer_names()
        formatted = []; existing_names = set()
        for method_info in methods_in_db:
            name = method_info.get("method_name")
            if name: formatted.append({"name": name, "method_name": f"{name} (dim: {method_info.get('vector_dim', 'N/A')})"}); existing_names.add(name)
        for possible_name in possible_names:
            if possible_name not in existing_names:
                display_text = possible_name
                if possible_name.startswith("tfidf:"): display_text = f"{possible_name} (TF-IDF)"
                elif possible_name.startswith("st:"): display_text = f"{possible_name} (Sentence Transformer)"
                formatted.append({"name": possible_name, "method_name": display_text})
        final_list = []; seen_names = set()
        for fv in formatted:
            if fv["name"] not in seen_names: final_list.append(fv); seen_names.add(fv["name"])
        final_list.sort(key=lambda x: x["name"]); return final_list
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error listing vectorizers for datastore {datastore_id}: {e}")


@store_files_router.post("/upload-files") 
async def upload_rag_documents_to_datastore(
    datastore_id: str, files: List[UploadFile] = File(...), vectorizer_name: str = Form(...),
    current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)
) -> JSONResponse:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    ds_record = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not ds_record or not user_db_record or ds_record.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner can upload files to this DataStore.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db) 
    
    datastore_docs_path = get_user_datastore_root_path(current_user.username) / "safestore_docs" / datastore_id
    datastore_docs_path.mkdir(parents=True, exist_ok=True)

    processed, errors_list = [], []
    try:
        with ss: all_vectorizers = {m['method_name'] for m in ss.list_vectorization_methods()} | set(ss.list_possible_vectorizer_names())
        if not (vectorizer_name in all_vectorizers or vectorizer_name.startswith("st:") or vectorizer_name.startswith("tfidf:")):
             raise HTTPException(status_code=400, detail=f"Vectorizer '{vectorizer_name}' not found or invalid format for datastore {datastore_id}.")
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error checking vectorizer for datastore {datastore_id}: {e}")

    for file_upload in files:
        s_filename = secure_filename(file_upload.filename or f"upload_{uuid.uuid4().hex[:8]}")
        target_file_path = datastore_docs_path / s_filename
        try:
            with open(target_file_path, "wb") as buffer: shutil.copyfileobj(file_upload.file, buffer)
            with ss: ss.add_document(str(target_file_path), vectorizer_name=vectorizer_name)
            processed.append(s_filename)
        except Exception as e:
            errors_list.append({"filename": s_filename, "error": str(e)}); target_file_path.unlink(missing_ok=True); traceback.print_exc()
        finally: await file_upload.close()
    status_code, msg = (207, "Some files processed with errors.") if errors_list and processed else \
                       (400, "Failed to process uploaded files.") if errors_list else \
                       (200, "All files uploaded and processed successfully.")
    return JSONResponse(status_code=status_code, content={"message": msg, "processed_files": processed, "errors": errors_list})

@store_files_router.get("/files", response_model=List[SafeStoreDocumentInfo])
async def list_rag_documents_in_datastore(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[SafeStoreDocumentInfo]:
    if not safe_store: return []
    ss = get_safe_store_instance(current_user.username, datastore_id, db) 
    managed_docs = []
    try:
        with ss: stored_meta = ss.list_documents()
        ds_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
        if not ds_record: raise HTTPException(status_code=404, detail="Datastore metadata not found in main DB.")
        
        expected_docs_root = get_user_datastore_root_path(ds_record.owner.username) / "safestore_docs" / datastore_id
        expected_docs_root_resolved = expected_docs_root.resolve()

        for doc_meta in stored_meta:
            original_path_str = doc_meta.get("file_path")
            if original_path_str:
                try:
                    if Path(original_path_str).resolve().parent == expected_docs_root_resolved:
                        managed_docs.append(SafeStoreDocumentInfo(filename=Path(original_path_str).name))
                except Exception: pass 
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error listing RAG docs for datastore {datastore_id}: {e}")
    managed_docs.sort(key=lambda x: x.filename); return managed_docs


@store_files_router.delete("/files/{filename}") 
async def delete_rag_document_from_datastore(datastore_id: str, filename: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    ds_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not ds_record or not user_db_record or ds_record.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete files from this DataStore.")

    s_filename = secure_filename(filename)
    if not s_filename or s_filename != filename: raise HTTPException(status_code=400, detail="Invalid filename.")
    
    datastore_docs_path = get_user_datastore_root_path(current_user.username) / "safestore_docs" / datastore_id
    file_to_delete_path = datastore_docs_path / s_filename
    if not file_to_delete_path.is_file(): raise HTTPException(status_code=404, detail=f"Document '{s_filename}' not found in datastore {datastore_id}.")
    
    ss = get_safe_store_instance(current_user.username, datastore_id, db)
    try:
        with ss: ss.delete_document_by_path(str(file_to_delete_path))
        file_to_delete_path.unlink()
        return {"message": f"Document '{s_filename}' deleted successfully from datastore {datastore_id}."}
    except Exception as e:
        if file_to_delete_path.exists(): raise HTTPException(status_code=500, detail=f"Could not delete '{s_filename}' from datastore {datastore_id}: {e}")
        else: return {"message": f"Document '{s_filename}' file deleted, potential DB cleanup issue in datastore {datastore_id}."}
