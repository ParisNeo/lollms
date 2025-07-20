from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import List

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.config import LLMBinding as DBLLMBinding
from backend.session import get_current_active_user, get_user_lollms_client, user_sessions
from backend.models import UserLLMParams, ModelInfo, UserAuthDetails

lollms_config_router = APIRouter(prefix="/api/config", tags=["LoLLMs Configuration"])

@lollms_config_router.get("/lollms-models", response_model=List[ModelInfo])
async def get_available_lollms_models(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    all_models = []
    active_bindings = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).all()

    for binding in active_bindings:
        try:
            lc = get_user_lollms_client(current_user.username, binding.alias)
            models = lc.listModels()
            
            if isinstance(models, list):
                for item in models:
                    model_name = None
                    if isinstance(item, str):
                        model_name = item
                    elif isinstance(item, dict):
                        model_name = item.get("name") or item.get("id") or item.get("model_name")
                    
                    if model_name:
                        all_models.append({
                            "id": f"{binding.alias}/{model_name}",
                            "name": model_name
                        })
        except Exception as e:
            print(f"WARNING: Could not fetch models from binding '{binding.alias}': {e}")
            continue

    if not all_models:
        raise HTTPException(status_code=404, detail="No models found from any active bindings.")
    
    unique_models = {m["id"]: m for m in all_models}
    return sorted(list(unique_models.values()), key=lambda x: x['id'])


@lollms_config_router.post("/lollms-model")
async def set_user_lollms_model(model_name: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    db_user_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user_record:
        raise HTTPException(status_code=404, detail="User not found.")
    user_sessions[current_user.username]["lollms_model_name"] = model_name
    user_sessions[current_user.username]["lollms_clients"] = {}
    db_user_record.lollms_model_name = model_name
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    return {"message": f"Default LoLLMs model set to '{model_name}'. Client will re-initialize."}

@lollms_config_router.post("/llm-params")
async def set_user_llm_params(params: UserLLMParams, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    db_user_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user_record:
        raise HTTPException(status_code=404, detail="User not found.")
    session_llm_params = user_sessions[current_user.username].get("llm_params", {})
    db_updated = session_updated = False
    for key, value in params.model_dump(exclude_unset=True).items():
        db_key = key
        session_key = key.replace('llm_', '')
        if getattr(db_user_record, db_key) != value:
            setattr(db_user_record, db_key, value)
            db_updated = True
        if session_llm_params.get(session_key) != value:
            session_llm_params[session_key] = value
            session_updated = True
    if db_updated:
        try:
            db.commit()
        except:
            db.rollback()
            raise
    if session_updated:
        user_sessions[current_user.username]["llm_params"] = {k: v for k, v in session_llm_params.items() if v is not None}
        user_sessions[current_user.username]["lollms_clients"] = {}
        return {"message": "LLM parameters updated. Client will re-initialize."}
    return {"message": "No changes to LLM parameters."}