# backend/routers/store_files.py
import shutil
import uuid
import traceback
from pathlib import Path
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload

try:
    import safe_store
except ImportError:
    safe_store = None

from backend.models.api_models import SafeStoreDocumentInfo, UserAuthDetails
from backend.database.setup import User as DBUser, DataStore as DBDataStore, get_db
from backend.services.auth_service import get_current_active_user
from backend.services.rag_service import get_safe_store_instance
from backend.utils.path_helpers import get_user_datastore_root_path, secure_filename

# This router is prefixed with /api/store/{datastore_id}
# So all paths here are relative to that.
store_files_router = APIRouter(
    prefix="/api/store/{datastore_id}", 
    tags=["SafeStore RAG & File Management"]
)

@store_files_router.get("/vectorizers", response_model=List[Dict[str, str]])
async def list_datastore_vectorizers(
    datastore_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, str]]:
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore library is not available.")
    
    # get_safe_store_instance also validates user's access to the datastore
    ss = get_safe_store_instance(current_user.username, datastore_id, db)
    
    try:
        with ss: # Ensure SafeStore connection is managed
            methods_in_db = ss.list_vectorization_methods()
            possible_names = ss.list_possible_vectorizer_names()
        
        formatted_vectorizers = []
        existing_method_names = set()

        for method_info in methods_in_db:
            name = method_info.get("method_name")
            if name:
                display_text = f"{name} (dim: {method_info.get('vector_dim', 'N/A')})"
                formatted_vectorizers.append({"name": name, "method_name": display_text})
                existing_method_names.add(name)
        
        for possible_name in possible_names:
            if possible_name not in existing_method_names:
                display_text = possible_name
                # Add more descriptive text based on prefix, similar to original code
                if possible_name.startswith("tfidf:"):
                    display_text = f"{possible_name} (TF-IDF based)"
                elif possible_name.startswith("st:"):
                    display_text = f"{possible_name} (Sentence Transformer)"
                # Add other known prefixes if any
                formatted_vectorizers.append({"name": possible_name, "method_name": display_text})
        
        # Sort and remove duplicates if any (though set logic should prevent most)
        # This sorting might be complex if names are diverse. Simple alphabetical for now.
        final_list = sorted(
            [dict(t) for t in {tuple(d.items()) for d in formatted_vectorizers}], 
            key=lambda x: x["name"]
        )
        return final_list

    except Exception as e:
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error listing vectorizers for datastore '{datastore_id}': {e}")


@store_files_router.post("/upload-files")
async def upload_rag_documents_to_datastore(
    datastore_id: str,
    files: List[UploadFile] = File(...),
    vectorizer_name: str = Form(...), # Vectorizer to use for these documents
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> JSONResponse: # Using JSONResponse for detailed success/error messages
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore library is not available.")

    # Verify user owns the datastore before allowing uploads
    ds_record = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first() # Should exist

    if not ds_record:
        raise HTTPException(status_code=404, detail=f"Datastore '{datastore_id}' not found.")
    if not user_db_record or ds_record.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner of the datastore can upload documents.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db) # Gets owner's instance

    # Path where documents for this datastore will be stored (owned by datastore owner)
    # Ensure this path uses the datastore owner's username
    datastore_owner_username = ds_record.owner.username # Get owner from DB record
    datastore_docs_physical_path = get_user_datastore_root_path(datastore_owner_username) / "safestore_docs" / datastore_id
    datastore_docs_physical_path.mkdir(parents=True, exist_ok=True)

    # Validate vectorizer_name
    try:
        with ss: # Manage SafeStore connection
            all_vectorizers = {m['method_name'] for m in ss.list_vectorization_methods()} | \
                              set(ss.list_possible_vectorizer_names())
        if not (vectorizer_name in all_vectorizers or 
                vectorizer_name.startswith("st:") or # Allow dynamic SentenceTransformer models
                vectorizer_name.startswith("tfidf:")): # Allow dynamic TF-IDF
            raise HTTPException(status_code=400, detail=f"Vectorizer '{vectorizer_name}' is invalid or not available for this datastore.")
    except Exception as e_vec_check:
        raise HTTPException(status_code=500, detail=f"Error checking vectorizer availability: {e_vec_check}")

    processed_files = []
    errors_list = []

    for file_upload in files:
        s_filename = secure_filename(file_upload.filename or f"upload_{uuid.uuid4().hex[:8]}")
        target_file_physical_path = datastore_docs_physical_path / s_filename
        
        try:
            # Save the uploaded file to the datastore's document directory
            with open(target_file_physical_path, "wb") as buffer:
                shutil.copyfileobj(file_upload.file, buffer)
            
            # Add document to SafeStore (this will handle chunking and vectorization)
            with ss: # Manage SafeStore connection for each doc addition
                # The path stored in SafeStore should be the physical path on the server
                ss.add_document(str(target_file_physical_path), vectorizer_name=vectorizer_name)
            
            processed_files.append(s_filename)
        except Exception as e_process:
            errors_list.append({"filename": s_filename, "error": str(e_process)})
            # Clean up the partially saved file if processing failed
            if target_file_physical_path.exists():
                target_file_physical_path.unlink(missing_ok=True)
            traceback.print_exc() # For server logs
        finally:
            await file_upload.close()

    status_code = 200
    message = "All files processed successfully."
    if errors_list:
        if processed_files:
            status_code = 207 # Multi-Status: some succeeded, some failed
            message = "Some files processed with errors."
        else:
            status_code = 400 # All files failed
            message = "Failed to process any files."
            
    return JSONResponse(
        status_code=status_code,
        content={"message": message, "processed_files": processed_files, "errors": errors_list}
    )


@store_files_router.get("/files", response_model=List[SafeStoreDocumentInfo])
async def list_rag_documents_in_datastore(
    datastore_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[SafeStoreDocumentInfo]:
    if not safe_store:
        return [] # Or raise 501 if SafeStore is mandatory

    # get_safe_store_instance validates user access
    ss = get_safe_store_instance(current_user.username, datastore_id, db)
    
    managed_docs_info = []
    try:
        with ss: # Manage SafeStore connection
            stored_document_metadata_list = ss.list_documents() # Gets list of dicts

        # To get the correct physical path root, we need the datastore owner's username
        ds_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
        if not ds_record: # Should be caught by get_safe_store_instance if datastore doesn't exist
            raise HTTPException(status_code=404, detail="Datastore metadata not found in main DB.")
        
        datastore_owner_username = ds_record.owner.username
        expected_docs_physical_root = (
            get_user_datastore_root_path(datastore_owner_username) / "safestore_docs" / datastore_id
        ).resolve()

        for doc_meta in stored_document_metadata_list:
            original_path_str = doc_meta.get("file_path")
            if original_path_str:
                try:
                    # Check if the document path is within the expected physical directory for this datastore
                    # This is a sanity check; SafeStore should manage its paths correctly.
                    resolved_doc_path = Path(original_path_str).resolve()
                    if resolved_doc_path.parent == expected_docs_physical_root:
                        managed_docs_info.append(SafeStoreDocumentInfo(filename=resolved_doc_path.name))
                    else:
                        print(f"WARN: Document path '{original_path_str}' for datastore '{datastore_id}' is outside expected root '{expected_docs_physical_root}'. Skipping.")
                except Exception as e_path:
                    print(f"WARN: Error processing document path '{original_path_str}' for datastore '{datastore_id}': {e_path}")
                    
    except Exception as e_list_docs:
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error listing RAG documents for datastore '{datastore_id}': {e_list_docs}")
        
    return sorted(managed_docs_info, key=lambda x: x.filename.lower())


@store_files_router.delete("/files/{filename}")
async def delete_rag_document_from_datastore(
    datastore_id: str,
    filename: str, # Filename as served to the client (e.g., from list_rag_documents)
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore library is not available.")

    # Verify user owns the datastore
    ds_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()

    if not ds_record:
        raise HTTPException(status_code=404, detail=f"Datastore '{datastore_id}' not found.")
    if not user_db_record or ds_record.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner of the datastore can delete documents.")

    s_filename = secure_filename(filename)
    if not s_filename or s_filename != filename: # Basic validation
        raise HTTPException(status_code=400, detail="Invalid filename format.")

    datastore_owner_username = ds_record.owner.username
    file_to_delete_physical_path = (
        get_user_datastore_root_path(datastore_owner_username) / "safestore_docs" / datastore_id / s_filename
    )

    if not file_to_delete_physical_path.is_file():
        raise HTTPException(status_code=404, detail=f"Document '{s_filename}' not found in datastore '{datastore_id}'s document directory.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db) # Gets owner's instance

    try:
        with ss: # Manage SafeStore connection
            # SafeStore deletes based on the path it has stored, which should match this physical path.
            ss.delete_document_by_path(str(file_to_delete_physical_path))
        
        # After successful deletion from SafeStore's database, delete the physical file.
        file_to_delete_physical_path.unlink()
        return {"message": f"Document '{s_filename}' deleted successfully from datastore '{datastore_id}'."}
    except Exception as e_delete:
        # traceback.print_exc()
        # Check if file still exists; if SafeStore failed but file is there, it's an issue.
        # If SafeStore succeeded but unlink failed, also an issue.
        if file_to_delete_physical_path.exists():
            raise HTTPException(status_code=500, detail=f"Could not delete document '{s_filename}' from datastore '{datastore_id}': {e_delete}")
        else:
            # File might be gone, but SafeStore DB operation might have failed.
            # Or SafeStore deleted DB entry, then unlinking the file failed before this check.
            return {"message": f"Document '{s_filename}' file deleted, but there might have been an issue with SafeStore database cleanup. Please verify."}

