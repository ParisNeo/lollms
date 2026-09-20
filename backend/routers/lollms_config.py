# backend/routers/lollms_config.py
import json
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from lollms_client import get_binding_desc
from ascii_colors import trace_exception
from lollms_client.lollms_llm_binding import list_binding_models as list_llm_binding_models
from lollms_client.lollms_tti_binding import list_binding_models as list_tti_binding_models
from lollms_client.lollms_tts_binding import list_binding_models as list_tts_binding_models
from lollms_client.lollms_stt_binding import list_binding_models as list_stt_binding_models


from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.config import LLMBinding as DBLLMBinding, TTIBinding as DBTTIBinding, TTSBinding as DBTTSBinding, STTBinding as DBSTTBinding
from backend.session import get_current_active_user, get_user_lollms_client, user_sessions, build_lollms_client_from_params
from backend.models import UserLLMParams, UserAuthDetails
from backend.models.shared import ModelInfo
from backend.settings import settings

lollms_config_router = APIRouter(prefix="/api/config", tags=["LoLLMs Configuration"])

class ModelInfo(BaseModel):
    id: str
    name: str
    alias: Optional[Dict[str, Any]] = None
    binding_params: Optional[Dict[str, List[Dict[str, Any]]]] = None

@lollms_config_router.get("/llm-models", response_model=List[ModelInfo])
async def get_lollms_models(
    db: Session = Depends(get_db)
):
    """
    Returns only verified active Universal Profiles where the connection server is online
    and the underlying model is present.
    """
    from backend.routers.admin.bindings_management import get_all_universal_profiles
    profiles_dict = await get_all_universal_profiles(modality="llm", db=db)
    model_profiles = profiles_dict.get("profiles", {})

    all_models = []
    for prof_id, prof_info in model_profiles.items():
        if prof_info.get("is_available") is False:
            continue
        title = prof_info.get("title") or prof_info.get("name") or prof_id
        all_models.append({
            "id": prof_id,
            "name": title,
            "alias": prof_info
        })

    return sorted(all_models, key=lambda x: x['name'])

@lollms_config_router.get("/tti-models", response_model=List[ModelInfo])
async def get_lollms_tti_models(
    db: Session = Depends(get_db)
):
    """
    Returns only verified active Universal TTI Image Profiles where the connection server is online
    and the underlying diffusion model is present.
    """
    from backend.routers.admin.bindings_management import get_all_universal_profiles
    profiles_dict = await get_all_universal_profiles(modality="tti", db=db)
    model_profiles = profiles_dict.get("profiles", {})

    all_models = []
    for prof_id, prof_info in model_profiles.items():
        if prof_info.get("is_available") is False:
            continue
        title = prof_info.get("title") or prof_info.get("name") or prof_id
        all_models.append({
            "id": prof_id,
            "name": title,
            "alias": prof_info
        })

    return sorted(all_models, key=lambda x: x['name'])


@lollms_config_router.post("/lollms-model")
async def set_user_lollms_model(model_name: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    db_user_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user_record:
        raise HTTPException(status_code=404, detail="User not found.")
    user_sessions[current_user.username]["lollms_model_name"] = model_name
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
        return {"message": "LLM parameters updated. Client will re-initialize."}
    return {"message": "No changes to LLM parameters."}


@lollms_config_router.get("/tts-models", response_model=List[ModelInfo])
async def get_tts_models(
    db: Session = Depends(get_db)
):
    from backend.routers.admin.bindings_management import get_all_universal_profiles
    profiles_dict = await get_all_universal_profiles(modality="tts", db=db)
    model_profiles = profiles_dict.get("profiles", {})

    all_models = []
    for prof_id, prof_info in model_profiles.items():
        if prof_info.get("is_available") is False:
            continue
        title = prof_info.get("title") or prof_info.get("name") or prof_id
        all_models.append({
            "id": prof_id,
            "name": title,
            "alias": prof_info
        })

    return sorted(all_models, key=lambda x: x['name'])

@lollms_config_router.get("/stt-models", response_model=List[ModelInfo])
async def get_stt_models(
    db: Session = Depends(get_db)
):
    from backend.routers.admin.bindings_management import get_all_universal_profiles
    profiles_dict = await get_all_universal_profiles(modality="stt", db=db)
    model_profiles = profiles_dict.get("profiles", {})

    all_models = []
    for prof_id, prof_info in model_profiles.items():
        if prof_info.get("is_available") is False:
            continue
        title = prof_info.get("title") or prof_info.get("name") or prof_id
        all_models.append({
            "id": prof_id,
            "name": title,
            "alias": prof_info
        })

    return sorted(all_models, key=lambda x: x['name'])
