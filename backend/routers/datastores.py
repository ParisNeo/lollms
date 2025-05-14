# backend/routers/datastores.py
from pathlib import Path
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from backend.models.api_models import (
    DataStoreCreate, DataStorePublic, DataStoreShareRequest, UserPublic
)
from backend.database.setup import (
    User as DBUser, DataStore as DBDataStore, 
    SharedDataStoreLink as DBSharedDataStoreLink, Friendship as DBFriendship, get_db
)
from backend.services.auth_service import get_current_active_user, UserAuthDetails
from backend.services.rag_service import get_safe_store_instance # For initial creation
from backend.utils.path_helpers import get_datastore_db_path
from backend.core.global_state import user_sessions

datastore_router = APIRouter(prefix="/api/datastores", tags=["RAG DataStores"])

@datastore_router.post("", response_model=DataStorePublic, status_code=201)
async def create_datastore(
    ds_create: DataStoreCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> DataStorePublic:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: # Should be caught by auth
        raise HTTPException(status_code=404, detail="User not found.")

    # Check for existing datastore with the same name for this user
    if db.query(DBDataStore).filter_by(owner_user_id=user_db_record.id, name=ds_create.name).first():
        raise HTTPException(status_code=400, detail=f"DataStore with name '{ds_create.name}' already exists for this user.")

    new_ds_db_obj = DBDataStore(
        owner_user_id=user_db_record.id,
        name=ds_create.name,
        description=ds_create.description,
        is_public_in_store=ds_create.is_public_in_store
    )
    try:
        db.add(new_ds_db_obj)
        db.commit()
        db.refresh(new_ds_db_obj)
        
        # Initialize SafeStore file on creation
        get_safe_store_instance(current_user.username, new_ds_db_obj.id, db) # This will create the .db file
        
        return DataStorePublic(
            id=new_ds_db_obj.id,
            name=new_ds_db_obj.name,
            description=new_ds_db_obj.description,
            is_public_in_store=new_ds_db_obj.is_public_in_store,
            owner_username=current_user.username, # Owner is the current user
            created_at=new_ds_db_obj.created_at,
            updated_at=new_ds_db_obj.updated_at
        )
    except IntegrityError: # Should be caught by the name check above, but as a fallback
        db.rollback()
        raise HTTPException(status_code=400, detail="DataStore name conflict (race condition or other).")
    except Exception as e:
        db.rollback()
        # traceback.print_exc() # For server logs
        raise HTTPException(status_code=500, detail=f"Database error creating datastore: {e}")


@datastore_router.get("", response_model=List[DataStorePublic])
async def list_my_datastores(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[DataStorePublic]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User database record not found.")

    response_list: List[DataStorePublic] = []
    
    # Owned datastores
    owned_ds_db = db.query(DBDataStore).filter(
        DBDataStore.owner_user_id == user_db_record.id
    ).order_by(DBDataStore.name).all()
    
    for ds_db in owned_ds_db:
        response_list.append(
            DataStorePublic.model_validate(ds_db, context={"owner_username": current_user.username})
        )

    # Datastores shared with the user
    shared_links_query = db.query(DBSharedDataStoreLink).join(
        DBDataStore, DBSharedDataStoreLink.datastore_id == DBDataStore.id
    ).filter(
        DBSharedDataStoreLink.shared_with_user_id == user_db_record.id
    ).options(
        joinedload(DBSharedDataStoreLink.datastore).joinedload(DBDataStore.owner)
    ).order_by(DBDataStore.name) # Order by datastore name
    
    shared_links_and_ds_db = shared_links_query.all()

    for link in shared_links_and_ds_db:
        ds_db = link.datastore
        # Avoid adding duplicates if a datastore is somehow listed as owned and shared (should not happen with current logic)
        if not any(r.id == ds_db.id for r in response_list):
             response_list.append(
                 DataStorePublic.model_validate(ds_db, context={"owner_username": ds_db.owner.username})
             )
    
    return response_list


@datastore_router.get("/store", response_model=List[DataStorePublic])
async def list_public_datastores(
    current_user: UserAuthDetails = Depends(get_current_active_user), # Auth still needed to know who is asking
    db: Session = Depends(get_db)
) -> List[DataStorePublic]:
    public_ds_db = db.query(DBDataStore).options(
        joinedload(DBDataStore.owner) # Eager load owner to get username
    ).filter(
        DBDataStore.is_public_in_store == True
    ).order_by(DBDataStore.name).all()
    
    return [
        DataStorePublic.model_validate(ds_db, context={"owner_username": ds_db.owner.username})
        for ds_db in public_ds_db
    ]


@datastore_router.put("/{datastore_id}", response_model=DataStorePublic)
async def update_datastore(
    datastore_id: str,
    ds_update: DataStoreCreate, # Uses DataStoreCreate as it contains all updatable fields
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> DataStorePublic:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.")

    ds_db_obj = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    if not ds_db_obj:
        raise HTTPException(status_code=404, detail="DataStore not found.")
    
    if ds_db_obj.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner can update this DataStore.")

    # Check for name conflict if name is being changed
    if ds_update.name != ds_db_obj.name:
        if db.query(DBDataStore).filter(
            DBDataStore.owner_user_id == user_db_record.id,
            DBDataStore.name == ds_update.name,
            DBDataStore.id != datastore_id # Exclude current datastore from check
        ).first():
            raise HTTPException(status_code=400, detail=f"Another DataStore with name '{ds_update.name}' already exists.")

    # Update fields
    ds_db_obj.name = ds_update.name
    ds_db_obj.description = ds_update.description
    ds_db_obj.is_public_in_store = ds_update.is_public_in_store
    
    try:
        db.commit()
        db.refresh(ds_db_obj)
        return DataStorePublic.model_validate(ds_db_obj, context={"owner_username": current_user.username})
    except Exception as e:
        db.rollback()
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error updating datastore: {e}")

@datastore_router.delete("/{datastore_id}", status_code=200)
async def delete_datastore(
    datastore_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> Dict[str, str]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.")

    ds_db_obj = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    if not ds_db_obj:
        raise HTTPException(status_code=404, detail="DataStore not found.")

    if ds_db_obj.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete this DataStore.")

    ds_name_for_message = ds_db_obj.name # Get name before deleting object
    
    # Path to the SafeStore .db file and .lock file
    ds_file_path = get_datastore_db_path(current_user.username, datastore_id)
    ds_lock_file_path = Path(f"{ds_file_path}.lock")

    try:
        # Delete sharing links first due to foreign key constraints
        db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id).delete(synchronize_session=False)
        
        # Then delete the datastore record
        db.delete(ds_db_obj)
        db.commit()

        # Remove from user's active session if loaded
        if current_user.username in user_sessions and \
           datastore_id in user_sessions[current_user.username].get("safe_store_instances", {}):
            del user_sessions[current_user.username]["safe_store_instances"][datastore_id]

        # Schedule file deletion in background
        if ds_file_path.exists():
            background_tasks.add_task(ds_file_path.unlink, missing_ok=True)
        if ds_lock_file_path.exists():
            background_tasks.add_task(ds_lock_file_path.unlink, missing_ok=True)
            
        return {"message": f"DataStore '{ds_name_for_message}' and its associated files scheduled for deletion."}
    except Exception as e:
        db.rollback()
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database or file system error during datastore deletion: {e}")


@datastore_router.post("/{datastore_id}/add_to_my_interface", status_code=201)
async def add_public_datastore_to_interface(
    datastore_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.")
    
    # Find the public datastore
    public_ds = db.query(DBDataStore).filter(
        DBDataStore.id == datastore_id,
        DBDataStore.is_public_in_store == True # Must be public
    ).first()
    
    if not public_ds:
        raise HTTPException(status_code=404, detail="Public DataStore not found or it is not marked as public.")
    
    if public_ds.owner_user_id == user_db_record.id:
        raise HTTPException(status_code=400, detail="Cannot add your own datastore to your interface this way; you already own it.")

    # Check if already linked (shared)
    existing_link = db.query(DBSharedDataStoreLink).filter_by(
        datastore_id=datastore_id,
        shared_with_user_id=user_db_record.id
    ).first()
    if existing_link:
        return {"message": f"DataStore '{public_ds.name}' is already in your interface."}
    
    # Create a share link with "read_query" permission
    new_link = DBSharedDataStoreLink(
        datastore_id=datastore_id,
        shared_with_user_id=user_db_record.id,
        permission_level="read_query" # Default permission for adding from store
    )
    try:
        db.add(new_link)
        db.commit()
        return {"message": f"Public DataStore '{public_ds.name}' added to your interface."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error adding datastore link: {e}")


@datastore_router.post("/{datastore_id}/share_with_friend", status_code=201)
async def share_datastore_with_friend(
    datastore_id: str,
    share_request: DataStoreShareRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db:
        raise HTTPException(status_code=404, detail="Owner user not found.")

    ds_to_share = db.query(DBDataStore).filter(
        DBDataStore.id == datastore_id,
        DBDataStore.owner_user_id == owner_user_db.id # Must be owner to share
    ).first()
    if not ds_to_share:
        raise HTTPException(status_code=404, detail="DataStore not found or you are not the owner.")

    target_user_db = db.query(DBUser).filter(DBUser.username == share_request.target_username).first()
    if not target_user_db:
        raise HTTPException(status_code=404, detail=f"Target user '{share_request.target_username}' not found.")
    
    if owner_user_db.id == target_user_db.id:
        raise HTTPException(status_code=400, detail="Cannot share a datastore with yourself.")
    
    # Check friendship status
    friendship = db.query(DBFriendship).filter(
        ((DBFriendship.requester_id == owner_user_db.id) & (DBFriendship.addressee_id == target_user_db.id)) |
        ((DBFriendship.requester_id == target_user_db.id) & (DBFriendship.addressee_id == owner_user_db.id)),
        DBFriendship.status == 'accepted'
    ).first()
    if not friendship:
        raise HTTPException(status_code=403, detail=f"You are not friends with '{target_user_db.username}'. Cannot share datastore.")
        
    # Check if already shared
    existing_link = db.query(DBSharedDataStoreLink).filter_by(
        datastore_id=datastore_id,
        shared_with_user_id=target_user_db.id
    ).first()

    if existing_link:
        if existing_link.permission_level != share_request.permission_level:
            existing_link.permission_level = share_request.permission_level # Update permission
            db.commit()
            return {"message": f"Permission level updated for DataStore '{ds_to_share.name}' shared with friend '{target_user_db.username}'."}
        return {"message": f"DataStore '{ds_to_share.name}' is already shared with friend '{target_user_db.username}' with this permission."}

    # Create new share link
    new_link = DBSharedDataStoreLink(
        datastore_id=datastore_id,
        shared_with_user_id=target_user_db.id,
        permission_level=share_request.permission_level
    )
    try:
        db.add(new_link)
        db.commit()
        return {"message": f"DataStore '{ds_to_share.name}' shared with friend '{target_user_db.username}'."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error creating share link: {e}")


@datastore_router.delete("/{datastore_id}/unshare_from_friend/{friend_username}", status_code=200)
async def unshare_datastore_from_friend(
    datastore_id: str,
    friend_username: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db:
        raise HTTPException(status_code=404, detail="Owner user not found.")

    # Verify current user owns the datastore
    ds_to_unshare = db.query(DBDataStore).filter(
        DBDataStore.id == datastore_id,
        DBDataStore.owner_user_id == owner_user_db.id
    ).first()
    if not ds_to_unshare:
        raise HTTPException(status_code=404, detail="DataStore not found or you are not the owner.")

    friend_user_db = db.query(DBUser).filter(DBUser.username == friend_username).first()
    if not friend_user_db:
        raise HTTPException(status_code=404, detail=f"Friend user '{friend_username}' not found.")

    link_to_delete = db.query(DBSharedDataStoreLink).filter_by(
        datastore_id=datastore_id,
        shared_with_user_id=friend_user_db.id
    ).first()
    
    if not link_to_delete:
        raise HTTPException(status_code=404, detail=f"DataStore '{ds_to_unshare.name}' is not currently shared with '{friend_username}'.")

    try:
        db.delete(link_to_delete)
        db.commit()
        return {"message": f"DataStore '{ds_to_unshare.name}' unshared from friend '{friend_username}'."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error removing share link: {e}")

@datastore_router.get("/{datastore_id}/shared_with", response_model=List[UserPublic])
async def get_datastore_shared_with_users(
    datastore_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[UserPublic]:
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db:
        raise HTTPException(status_code=404, detail="Owner user not found.")

    ds_record = db.query(DBDataStore).filter(
        DBDataStore.id == datastore_id,
        DBDataStore.owner_user_id == owner_user_db.id # Only owner can see who it's shared with
    ).first()
    if not ds_record:
        raise HTTPException(status_code=404, detail="DataStore not found or you are not the owner.")
    
    # Get all links for this datastore and eager load the user it's shared with
    links = db.query(DBSharedDataStoreLink).options(
        joinedload(DBSharedDataStoreLink.shared_with_user)
    ).filter(
        DBSharedDataStoreLink.datastore_id == datastore_id
    ).all()
    
    # Convert DBUser objects (shared_with_user) to UserPublic Pydantic models
    shared_users_public_info = []
    for link in links:
        if link.shared_with_user: # Make sure the user object is loaded
            shared_users_public_info.append(UserPublic.model_validate(link.shared_with_user))
            
    return shared_users_public_info
