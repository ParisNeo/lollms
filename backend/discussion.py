# backend/discussion.py
from pathlib import Path
import platform
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


def get_user_discussion(username: str, discussion_id: str, create_if_missing: bool = False, lollms_client: Optional[LollmsClient] = None) -> Optional[LollmsDiscussion]:
    """
    Retrieves or creates a LollmsDiscussion object for a user.
    This function now relies on the lollms-client's native LollmsDiscussion class.
    """
    lc = lollms_client

    if not lc:
        if username in user_sessions:
            lc = get_user_lollms_client(username)
        else:
            # User is not logged in on this worker (e.g., owner of a shared discussion).
            # We must build a temporary client from their DB settings.
            db = next(get_db())
            try:
                owner_db = db.query(DBUser).filter(DBUser.username == username).first()
                if not owner_db:
                    return None  # Owner not found

                binding_to_use = None
                user_model_full = owner_db.lollms_model_name

                if user_model_full and '/' in user_model_full:
                    binding_alias, _ = user_model_full.split('/', 1)
                    binding_to_use = db.query(DBLLMBinding).filter(DBLLMBinding.alias == binding_alias, DBLLMBinding.is_active == True).first()

                if not binding_to_use:
                    binding_to_use = db.query(DBLLMBinding).filter(DBLLMBinding.is_active == True).order_by(DBLLMBinding.id).first()

                if not binding_to_use:
                    # No bindings available, cannot create a client.
                    return None
                
                # Simplified client build from DB user settings
                lc = LollmsClient(
                    llm_binding_name=binding_to_use.name,
                    llm_binding_config={
                        **binding_to_use.config,
                        "model_name": owner_db.lollms_model_name.split('/')[-1] if user_model_full else binding_to_use.default_model_name
                    }
                )

            finally:
                db.close()

    if not lc:
        return None

    dm = get_user_discussion_manager(username)
    
    # Context size resolution
    # 1. Try to get it from the client config (where admin overrides are injected)
    # 2. Fallback to manual DB lookup using the user's selected model path (alias/model)
    # 3. Fallback to model introspection or 4096
    max_context_size = getattr(lc, 'llm_binding_config', {}).get('ctx_size')
    
    if not max_context_size:
        db = next(get_db())
        try:
            user_db = db.query(DBUser).filter(DBUser.username == username).first()
            user_model_full = user_db.lollms_model_name if user_db else None
            
            if user_model_full and '/' in user_model_full:
                binding_alias_key, model_key = user_model_full.split('/', 1)
                # Look for the binding record by alias to find the correct model definitions
                binding_rec = db.query(DBLLMBinding).filter(DBLLMBinding.alias == binding_alias_key).first()
                if binding_rec and binding_rec.model_aliases:
                    aliases = binding_rec.model_aliases
                    if isinstance(aliases, str):
                        aliases = json.loads(aliases)
                    
                    alias_info = aliases.get(model_key)
                    if alias_info and alias_info.get('ctx_size'):
                        max_context_size = int(alias_info['ctx_size'])
        except Exception:
            pass
        finally:
            db.close()

    if not max_context_size:
        max_context_size = lc.get_ctx_size() or 4096

    discussion = dm.get_discussion(
        lollms_client=lc,
        discussion_id=discussion_id,
        max_context_size=max_context_size,
        autosave=True
    )
    
    if discussion:
        discussion.lollms_client = lc
        discussion.max_context_size = max_context_size
        
        # --- NEW MEMORY & USER DATA ZONE LOGIC ---
        db = next(get_db())
        try:
            user_db = db.query(DBUser).filter(DBUser.username == username).first()
            if user_db:
                # Memory
                memory_parts = []
                for mem in user_db.memories:
                    date_str = f" (Created on: {mem.created_at.strftime('%Y-%d-%m')})" if user_db.include_memory_date_in_context else ""
                    memory_parts.append(f"--- Memory: {mem.title}{date_str} ---\n{mem.content}\n--- End Memory: {mem.title} ---")
                discussion.memory = "\n\n".join(memory_parts)

                # User Data Zone construction
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
        # --- END NEW LOGIC ---

        try:
            discussion.get_discussion_images()
        except Exception as e:
            print(f"Warning: A non-critical error occurred during discussion image check. Trusting library. Error: {e}")

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
        return new_discussion
    return None