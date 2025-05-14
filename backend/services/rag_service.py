# backend/services/rag_service.py
import traceback
from typing import cast
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

try:
    import safe_store
    from safe_store import LogLevel as SafeStoreLogLevel, ConfigurationError as SafeStoreConfigurationError
except ImportError:
    safe_store = None
    SafeStoreLogLevel = None
    SafeStoreConfigurationError = None # type: ignore

from backend.core.global_state import user_sessions
from backend.config import SAFE_STORE_DEFAULTS
from backend.utils.path_helpers import get_datastore_db_path
from backend.database.setup import DataStore as DBDataStore, User as DBUser, SharedDataStoreLink as DBSharedDataStoreLink


def get_safe_store_instance(requesting_user_username: str, datastore_id: str, db: Session) -> safe_store.SafeStore: # type: ignore
    if safe_store is None:
        raise HTTPException(status_code=501, detail="SafeStore library not installed.")

    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record:
        raise HTTPException(status_code=404, detail=f"DataStore '{datastore_id}' not found.")
    
    owner_username = datastore_record.owner.username
    
    requesting_user_record = db.query(DBUser).filter(DBUser.username == requesting_user_username).first()
    if not requesting_user_record: # Should not happen if user is authenticated
        raise HTTPException(status_code=404, detail="Requesting user not found.")

    is_owner = (owner_username == requesting_user_username)
    is_shared_with_requester = False

    if not is_owner:
        link = db.query(DBSharedDataStoreLink).filter_by(
            datastore_id=datastore_id,
            shared_with_user_id=requesting_user_record.id
        ).first()
        if link and link.permission_level == "read_query": # Check permissions
            is_shared_with_requester = True
            
    if not is_owner and not is_shared_with_requester:
        raise HTTPException(status_code=403, detail="Access denied to this DataStore.")

    # Use requesting user's session to store their instance handle
    session = user_sessions.get(requesting_user_username)
    if not session: # Should be initialized by auth
        raise HTTPException(status_code=500, detail="User session not found for SafeStore access.")

    if datastore_id not in session["safe_store_instances"]:
        ss_db_path = get_datastore_db_path(owner_username, datastore_id) # Path is based on owner
        encryption_key = SAFE_STORE_DEFAULTS.get("encryption_key") # Global key for now
        log_level_str = SAFE_STORE_DEFAULTS.get("log_level", "INFO").upper()
        ss_log_level = getattr(SafeStoreLogLevel, log_level_str, SafeStoreLogLevel.INFO) if SafeStoreLogLevel else None
        
        try:
            ss_params = {"db_path": ss_db_path, "encryption_key": encryption_key}
            if ss_log_level is not None:
                 ss_params["log_level"] = ss_log_level # type: ignore
            
            session["safe_store_instances"][datastore_id] = safe_store.SafeStore(**ss_params) # type: ignore
        except SafeStoreConfigurationError as e: # type: ignore
             raise HTTPException(status_code=500, detail=f"SafeStore config error for {datastore_id}: {str(e)}.")
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not init SafeStore for {datastore_id}: {str(e)}")
            
    return cast(safe_store.SafeStore, session["safe_store_instances"][datastore_id]) # type: ignore