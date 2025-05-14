# backend/routers/lollms_config.py
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session

from backend.models.api_models import UserLLMParams, UserAuthDetails
from backend.database.setup import User as DBUser, get_db
from backend.services.auth_service import get_current_active_user
from backend.services.lollms_service import get_user_lollms_client
from backend.core.global_state import user_sessions
from backend.config import LOLLMS_CLIENT_DEFAULTS

lollms_config_router = APIRouter(prefix="/api/config", tags=["LoLLMs Configuration"])

@lollms_config_router.get("/lollms-models", response_model=List[Dict[str, str]])
async def get_available_lollms_models(
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> List[Dict[str, str]]:
    lc = get_user_lollms_client(current_user.username)
    models_set: set[str] = set()
    try:
        # This call might be blocking or raise an exception if client is not well-configured
        binding_models = lc.listModels() 
        if isinstance(binding_models, list):
            for item in binding_models:
                if isinstance(item, str):
                    models_set.add(item)
                elif isinstance(item, dict): # LollmsClient might return list of dicts
                    name = item.get("name", item.get("id", item.get("model_name")))
                    if name: models_set.add(name)
    except Exception as e:
        print(f"WARNING: Could not list models from LollmsClient for user {current_user.username}: {e}")
        # Optionally, return an error response or an empty list with a message
        # For now, continue and add defaults.

    # Add user's current model and global default to ensure they are in the list
    user_current_model = user_sessions[current_user.username].get("lollms_model_name")
    if user_current_model: models_set.add(user_current_model)
    
    global_default_model = LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
    if global_default_model: models_set.add(global_default_model)

    models_set.discard("") # Remove empty string if any
    models_set.discard(None) # Remove None if any

    # Fallback for OpenAI-like bindings if list is empty
    if not models_set and lc.binding is not None and "openai" in lc.binding.binding_name.lower(): # type: ignore
        models_set.update(["gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4"]) # Common models
        print(f"INFO: No models listed from binding, providing OpenAI defaults for user {current_user.username}")


    if not models_set:
        return [{"name": "No models found or LollmsClient not configured"}]
        
    return [{"name": name} for name in sorted(list(models_set))]


@lollms_config_router.post("/lollms-model")
async def set_user_lollms_model(
    model_name: str = Form(...),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    username = current_user.username
    
    # Update in-memory session first
    user_sessions[username]["lollms_model_name"] = model_name
    user_sessions[username]["lollms_client"] = None # Force re-initialization on next use
    
    # Persist to database
    db_user_record = db.query(DBUser).filter(DBUser.username == username).first()
    if db_user_record:
        db_user_record.lollms_model_name = model_name
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            # Revert in-memory change? Or let client retry?
            # For now, if DB fails, session change might persist until next login.
            raise HTTPException(status_code=500, detail=f"Database error: {e}")
    else:
        # This should not happen if user is authenticated
        raise HTTPException(status_code=404, detail="User not found in database.")
        
    return {"message": f"Default LoLLMs model set to '{model_name}'. Client will re-initialize on next use."}


@lollms_config_router.get("/llm-params", response_model=UserLLMParams)
async def get_user_llm_params(
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> UserLLMParams:
    # UserAuthDetails already contains these from the session state
    return UserLLMParams(
        llm_temperature=current_user.llm_temperature,
        llm_top_k=current_user.llm_top_k,
        llm_top_p=current_user.llm_top_p,
        llm_repeat_penalty=current_user.llm_repeat_penalty,
        llm_repeat_last_n=current_user.llm_repeat_last_n
    )


@lollms_config_router.post("/llm-params")
async def set_user_llm_params(
    params: UserLLMParams, # Pydantic model from request body
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    username = current_user.username
    db_user_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not db_user_record:
        raise HTTPException(status_code=404, detail="User not found.")

    updated_fields_db = {}
    updated_fields_session = {}
    
    # Compare and update each parameter
    if params.llm_temperature is not None and db_user_record.llm_temperature != params.llm_temperature:
        updated_fields_db["llm_temperature"] = params.llm_temperature
        updated_fields_session["temperature"] = params.llm_temperature
    if params.llm_top_k is not None and db_user_record.llm_top_k != params.llm_top_k:
        updated_fields_db["llm_top_k"] = params.llm_top_k
        updated_fields_session["top_k"] = params.llm_top_k
    if params.llm_top_p is not None and db_user_record.llm_top_p != params.llm_top_p:
        updated_fields_db["llm_top_p"] = params.llm_top_p
        updated_fields_session["top_p"] = params.llm_top_p
    if params.llm_repeat_penalty is not None and db_user_record.llm_repeat_penalty != params.llm_repeat_penalty:
        updated_fields_db["llm_repeat_penalty"] = params.llm_repeat_penalty
        updated_fields_session["repeat_penalty"] = params.llm_repeat_penalty
    if params.llm_repeat_last_n is not None and db_user_record.llm_repeat_last_n != params.llm_repeat_last_n:
        updated_fields_db["llm_repeat_last_n"] = params.llm_repeat_last_n
        updated_fields_session["repeat_last_n"] = params.llm_repeat_last_n

    if updated_fields_db: # If any changes were made for DB
        for field, value in updated_fields_db.items():
            setattr(db_user_record, field, value)
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {e}")

        # Update session state only after successful DB commit
        session_llm_params = user_sessions[username].get("llm_params", {})
        session_llm_params.update(updated_fields_session) # Update with session-key names
        user_sessions[username]["llm_params"] = session_llm_params
        user_sessions[username]["lollms_client"] = None # Force re-init of LollmsClient
        
        return {"message": "LLM parameters updated successfully. Client will re-initialize."}
    
    return {"message": "No changes to LLM parameters."}

