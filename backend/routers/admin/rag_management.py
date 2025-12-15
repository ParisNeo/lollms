# [UPDATE] backend/routers/admin/rag_management.py
import json
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import IntegrityError
import safe_store 

from backend.db import get_db
from backend.db.models.config import RAGBinding as DBRAGBinding
from backend.models.admin import (
    RAGBindingCreate, RAGBindingUpdate, RAGBindingPublicAdmin,
    RagModelAliasUpdate, ModelAliasDelete, BindingModel
)
from backend.ws_manager import manager
from ascii_colors import trace_exception

rag_management_router = APIRouter()

@rag_management_router.get("/rag-bindings/available_types", response_model=List[Dict])
async def get_available_rag_binding_types():
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore (RAG) functionality is not available.")
    try:
        return safe_store.SafeStore.list_available_vectorizers()
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=str(e))

@rag_management_router.get("/rag-bindings", response_model=List[RAGBindingPublicAdmin])
async def get_all_rag_bindings(db: Session = Depends(get_db)):
    return db.query(DBRAGBinding).all()

@rag_management_router.post("/rag-bindings", response_model=RAGBindingPublicAdmin, status_code=201)
async def create_rag_binding(binding_data: RAGBindingCreate, db: Session = Depends(get_db)):
    if db.query(DBRAGBinding).filter(DBRAGBinding.alias == binding_data.alias).first():
        raise HTTPException(status_code=400, detail="A RAG binding with this alias already exists.")
    
    # Ensure 'model' is not stored in the binding config, as it should be selected per datastore
    if binding_data.config and "model" in binding_data.config:
        del binding_data.config["model"]

    new_binding = DBRAGBinding(**binding_data.model_dump())
    try:
        db.add(new_binding)
        db.commit()
        db.refresh(new_binding)
        manager.broadcast_sync({"type": "bindings_updated"})
        return new_binding
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="A RAG binding with this alias already exists.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@rag_management_router.put("/rag-bindings/{binding_id}", response_model=RAGBindingPublicAdmin)
async def update_rag_binding(binding_id: int, update_data: RAGBindingUpdate, db: Session = Depends(get_db)):
    binding_to_update = db.query(DBRAGBinding).filter(DBRAGBinding.id == binding_id).first()
    if not binding_to_update:
        raise HTTPException(status_code=404, detail="RAG Binding not found.")
    
    if update_data.alias and update_data.alias != binding_to_update.alias:
        if db.query(DBRAGBinding).filter(DBRAGBinding.alias == update_data.alias).first():
            raise HTTPException(status_code=400, detail="A RAG binding with the new alias already exists.")

    update_dict = update_data.model_dump(exclude_unset=True)
    
    # Ensure 'model' is not stored in the binding config
    if 'config' in update_dict and update_dict['config']:
        if 'model' in update_dict['config']:
            del update_dict['config']['model']

    for key, value in update_dict.items():
        setattr(binding_to_update, key, value)
    
    try:
        db.commit()
        db.refresh(binding_to_update)
        manager.broadcast_sync({"type": "bindings_updated"})
        return binding_to_update
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@rag_management_router.delete("/rag-bindings/{binding_id}", response_model=Dict[str, str])
async def delete_rag_binding(binding_id: int, db: Session = Depends(get_db)):
    binding_to_delete = db.query(DBRAGBinding).filter(DBRAGBinding.id == binding_id).first()
    if not binding_to_delete:
        raise HTTPException(status_code=404, detail="RAG Binding not found.")
    try:
        db.delete(binding_to_delete)
        db.commit()
        manager.broadcast_sync({"type": "bindings_updated"})
        return {"message": "RAG Binding deleted successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
        
@rag_management_router.get("/rag-bindings/{binding_id}/models", response_model=List[BindingModel])
async def get_rag_binding_models(binding_id: int, db: Session = Depends(get_db)):
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore (RAG) functionality is not available.")
    
    binding = db.query(DBRAGBinding).filter(DBRAGBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="RAG Binding not found.")
    
    try:
        config = binding.config or {}
        # Clean model from config just in case, though it shouldn't be there
        if 'model' in config:
            config = config.copy()
            del config['model']

        # CORRECTED: Use keyword arguments for the call
        raw_models = safe_store.SafeStore.list_models(
            vectorizer_name=binding.name, 
            vectorizer_config=config
        )
        
        models_list = [item if isinstance(item, str) else item.get("model_name") for item in raw_models if (isinstance(item, str) or item.get("model_name"))]

        model_aliases = binding.model_aliases or {}
        if isinstance(model_aliases, str):
            try: model_aliases = json.loads(model_aliases)
            except (json.JSONDecodeError, TypeError): model_aliases = {}
        
        return [BindingModel(original_model_name=model_name, alias=model_aliases.get(model_name)) for model_name in sorted(models_list)]
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Could not fetch models from RAG binding '{binding.alias}': {e}")

@rag_management_router.put("/rag-bindings/{binding_id}/alias", response_model=RAGBindingPublicAdmin)
async def update_rag_model_alias(binding_id: int, payload: RagModelAliasUpdate, db: Session = Depends(get_db)):
    binding = db.query(DBRAGBinding).filter(DBRAGBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="RAG Binding not found.")
    
    if binding.model_aliases is None:
        binding.model_aliases = {}
    
    binding.model_aliases[payload.original_model_name] = payload.alias.model_dump()
    flag_modified(binding, "model_aliases")
    
    db.commit()
    db.refresh(binding)
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding

@rag_management_router.delete("/rag-bindings/{binding_id}/alias", response_model=RAGBindingPublicAdmin)
async def delete_rag_model_alias(binding_id: int, payload: ModelAliasDelete, db: Session = Depends(get_db)):
    binding = db.query(DBRAGBinding).filter(DBRAGBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="RAG Binding not found.")
        
    if binding.model_aliases and payload.original_model_name in binding.model_aliases:
        del binding.model_aliases[payload.original_model_name]
        flag_modified(binding, "model_aliases")
    
    db.commit()
    db.refresh(binding)
    manager.broadcast_sync({"type": "bindings_updated"})
    return binding

@rag_management_router.get("/rag-bindings/models-for-type/{vectorizer_type}")
async def get_models_for_vectorizer_type(vectorizer_type: str, db: Session = Depends(get_db)):
    if not safe_store:
        raise HTTPException(status_code=501, detail="SafeStore (RAG) functionality is not available.")
    try:
        # Note: This endpoint might be deprecated in favor of binding-based model listing
        # It relies on generic vectorizer instantiation
        models = safe_store.SafeStore.list_models(
            vectorizer_name=vectorizer_type
        )
        return [m for m in models]
    except Exception as e:
        trace_exception(e)
        raise HTTPException(status_code=500, detail=f"Could not list models for '{vectorizer_type}': {e}")
