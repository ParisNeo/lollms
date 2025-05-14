# backend/services/lollms_service.py
import os
import traceback
from typing import cast
from fastapi import HTTPException

from lollms_client import LollmsClient, ELF_COMPLETION_FORMAT
from backend.core.global_state import user_sessions
from backend.config import LOLLMS_CLIENT_DEFAULTS

def get_user_lollms_client(username: str) -> LollmsClient:
    session = user_sessions.get(username)
    if not session:
        # This case should ideally be handled by auth_service ensuring session exists
        raise HTTPException(status_code=500, detail="User session not found for LollmsClient.")

    force_reinit = session.get("lollms_client") is None
    current_model_name = session["lollms_model_name"]
    
    # Check if client exists and model name matches
    if not force_reinit and hasattr(session["lollms_client"], "model_name") and \
       session["lollms_client"].model_name != current_model_name: # type: ignore
        force_reinit = True

    # TODO: Add check for LLM params if LollmsClient needs re-init for them
    # This depends on how LollmsClient handles dynamic parameter changes.
    # If LollmsClient sets params on each generation call, no re-init needed here.
    # If params are set at init, then need to compare session["llm_params"] with client's current.

    if force_reinit:
        print(f"INFO: Re-initializing LollmsClient for user {username} with model {current_model_name}")
        client_init_params = session.get("llm_params", {}).copy()
        client_init_params.update({
            "binding_name": LOLLMS_CLIENT_DEFAULTS.get("binding_name", "lollms"),
            "model_name": current_model_name,
            "host_address": LOLLMS_CLIENT_DEFAULTS.get("host_address"),
            "ctx_size": LOLLMS_CLIENT_DEFAULTS.get("ctx_size", 4096),
            "service_key": os.getenv(LOLLMS_CLIENT_DEFAULTS.get("service_key_env_var")) if LOLLMS_CLIENT_DEFAULTS.get("service_key_env_var") else None,
            "user_name": LOLLMS_CLIENT_DEFAULTS.get("user_name", "user"), # This should perhaps be the app username
            "ai_name": LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant"),
        })
        
        completion_format_str = LOLLMS_CLIENT_DEFAULTS.get("completion_format")
        if completion_format_str:
            try:
                client_init_params["completion_format"] = ELF_COMPLETION_FORMAT.from_string(completion_format_str)
            except ValueError:
                print(f"WARN: Invalid completion_format '{completion_format_str}' in config.")
        
        try:
            session["lollms_client"] = LollmsClient(**client_init_params)
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not initialize LLM Client: {str(e)}")
            
    return cast(LollmsClient, session["lollms_client"])