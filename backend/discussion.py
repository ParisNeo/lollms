# backend/discussion.py
from pathlib import Path
import platform
import json
from typing import List, Optional, Any, Dict
from lollms_client import LollmsClient, LollmsDataManager, LollmsDiscussion
from lollms_client.lollms_discussion import ArtefactType
from backend.session import user_sessions, get_user_lollms_client
from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.config import LLMBinding as DBLLMBinding
from backend.discussion_manager import get_user_discussion_manager

# --- Register Custom Artefact Types for LoLLMs Platform ---
ArtefactType.register_custom_type("note", label="Research Note")
ArtefactType.register_custom_type("skill", label="AI Capability")
ArtefactType.register_custom_type("file", label="External Document")
ArtefactType.register_custom_type("book", label="Digital Book")

def get_user_discussion(
    username: str, 
    discussion_id: str, 
    create_if_missing: bool = False, 
    lollms_client: Optional[LollmsClient] = None, 
    load_memory: bool = True
) -> Optional[LollmsDiscussion]:
    """
    Retrieves or creates a LollmsDiscussion object for a user using universal profiles.
    """
    lc = lollms_client

    if not lc:
        if username in user_sessions:
            lc = get_user_lollms_client(username)
        else:
            db = next(get_db())
            try:
                owner_db = db.query(DBUser).filter(DBUser.username == username).first()
                if not owner_db:
                    return None

                binding_to_use = None
                user_model_full = owner_db.lollms_model_name

                if user_model_full and '/' in user_model_full:
                    binding_alias, _ = user_model_full.split('/', 1)
                    binding_to_use = db.query(DBLLMBinding).filter(DBLLMBinding.alias == binding_alias, DBLLMBinding.is_active == True).first()

                if not binding_to_use:
                    binding_to_use = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).order_by(DBLLMBinding.id).first()

                if not binding_to_use:
                    return None
                
                lc = get_user_lollms_client(username)
            finally:
                db.close()

    if not lc:
        return None

    dm = get_user_discussion_manager(username)
    
    # Priority-based Context Size Resolution via Universal Profile Architecture
    max_context_size = None
    try:
        max_context_size = lc.get_ctx_size()
    except Exception:
        pass

    if not max_context_size:
        max_context_size = getattr(lc, 'llm_binding_config', {}).get('ctx_size') or 4096

    discussion = dm.get_discussion(
        lollms_client=lc,
        discussion_id=discussion_id,
        max_context_size=max_context_size,
        autosave=True
    )

    if discussion:
        if hasattr(discussion, 'load_messages'):
            discussion.load_messages()

        discussion.lollms_client = lc
        discussion.max_context_size = max_context_size
        
        if load_memory:
            db = next(get_db())
            try:
                user_db = db.query(DBUser).filter(DBUser.username == username).first()
                if user_db:
                    from backend.routers.memories import get_user_memory_manager
                    mm = get_user_memory_manager(username)
                    discussion.memory_manager = mm
                    discussion.memory = mm.build_working_zone()

                    preferences_lines = []

                if user_db.share_dynamic_info_with_llm:
                    preferences_lines.extend([
                        "date: {{date}}",
                        "time: {{time}}",
                        "datetime: {{datetime}}",
                        "user name: {{user_name}}",
                    ])

                if user_db.tell_llm_os:
                    preferences_lines.append(f"Operating System: {platform.system()}")
                
                user_data_zone_parts = []
                if preferences_lines:
                    user_data_zone_parts.append("--- User Preferences ---")
                    user_data_zone_parts.extend(preferences_lines)
                    user_data_zone_parts.append("--- End User Preferences ---")

                if user_db.coding_style_constraints and user_db.coding_style_constraints.strip():
                    user_data_zone_parts.append("\n--- Coding Style Constraints ---")
                    user_data_zone_parts.append(user_db.coding_style_constraints)

                if user_db.programming_language_preferences and user_db.programming_language_preferences.strip():
                    user_data_zone_parts.append("\n--- Programming Language & Library Preferences ---")
                    user_data_zone_parts.append(user_db.programming_language_preferences)
                
                if user_db.data_zone and user_db.data_zone.strip():
                    user_data_zone_parts.append("\n--- User General Information ---")
                    user_data_zone_parts.append(user_db.data_zone)

                    discussion.user_data_zone = "\n".join(user_data_zone_parts)
            finally:
                db.close()

        try:
            discussion.get_discussion_images()
        except Exception as e:
            print(f"Warning: Discussion image check: {e}")

        return discussion
    elif create_if_missing:
        new_discussion = LollmsDiscussion.create_new(
            lollms_client=lc,
            db_manager=dm,
            id=discussion_id,
            max_context_size=max_context_size,
            autosave=True,
            discussion_metadata={"title": f"New Discussion {discussion_id[:8]}"},
        )
        if load_memory:
            db = next(get_db())
            try:
                user_db = db.query(DBUser).filter(DBUser.username == username).first()
                if user_db:
                    from backend.routers.memories import get_user_memory_manager
                    mm = get_user_memory_manager(username)
                    new_discussion.memory_manager = mm
                    new_discussion.memory = mm.build_working_zone()
            finally:
                db.close()
        return new_discussion
    return None