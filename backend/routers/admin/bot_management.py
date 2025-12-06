from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import json
from ascii_colors import ASCIIColors

from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.config import GlobalConfig
from backend.task_manager import task_manager
from backend.tasks.social_tasks import _generate_feed_post_task, _batch_moderate_content_task, _full_remoderation_task
from backend.session import get_current_active_user
from backend.models import UserAuthDetails
from backend.settings import settings as lollms_settings

bot_management_router = APIRouter(tags=["Administration", "AI Bot"])

class AiBotSettingsUpdate(BaseModel):
    lollms_model_name: Optional[str] = None
    active_personality_id: Optional[str] = None
    # Global Config Fields
    ai_bot_enabled: Optional[bool] = None
    ai_bot_system_prompt: Optional[str] = None
    ai_bot_auto_post: Optional[bool] = None
    ai_bot_post_interval: Optional[float] = None
    ai_bot_content_mode: Optional[str] = None
    ai_bot_static_content: Optional[str] = None
    ai_bot_file_path: Optional[str] = None
    ai_bot_generation_prompt: Optional[str] = None
    # RAG Support
    ai_bot_rag_datastore_ids: Optional[List[str]] = None
    # Moderation Support
    ai_bot_moderation_enabled: Optional[bool] = None
    ai_bot_moderation_criteria: Optional[str] = None

class AiBotSettingsPublic(BaseModel):
    lollms_model_name: Optional[str] = None
    active_personality_id: Optional[str] = None
    # Global Config Fields
    ai_bot_enabled: bool = False
    ai_bot_system_prompt: str = ""
    ai_bot_auto_post: bool = False
    ai_bot_post_interval: float = 24.0
    ai_bot_content_mode: str = "static_text"
    ai_bot_static_content: str = ""
    ai_bot_file_path: str = ""
    ai_bot_generation_prompt: str = ""
    # RAG Support
    ai_bot_rag_datastore_ids: List[str] = []
    # Moderation Support
    ai_bot_moderation_enabled: bool = False
    ai_bot_moderation_criteria: str = ""

    class Config:
        from_attributes = True

@bot_management_router.get("/ai-bot-settings", response_model=AiBotSettingsPublic)
async def get_ai_bot_settings(db: Session = Depends(get_db)):
    """
    Retrieves the specific settings for the @lollms system user and related global configs.
    """
    bot_user = db.query(DBUser).filter(DBUser.username == "lollms").first()
    if not bot_user:
        raise HTTPException(status_code=404, detail="@lollms user not found.")
    
    # Force refresh to ensure we have the latest DB values
    lollms_settings.refresh(db)

    return AiBotSettingsPublic(
        lollms_model_name=bot_user.lollms_model_name,
        active_personality_id=bot_user.active_personality_id,
        ai_bot_enabled=lollms_settings.get("ai_bot_enabled", False),
        ai_bot_system_prompt=lollms_settings.get("ai_bot_system_prompt", ""),
        ai_bot_auto_post=lollms_settings.get("ai_bot_auto_post", False),
        ai_bot_post_interval=float(lollms_settings.get("ai_bot_post_interval", 24.0)),
        ai_bot_content_mode=lollms_settings.get("ai_bot_content_mode", "static_text"),
        ai_bot_static_content=lollms_settings.get("ai_bot_static_content", ""),
        ai_bot_file_path=lollms_settings.get("ai_bot_file_path", ""),
        ai_bot_generation_prompt=lollms_settings.get("ai_bot_generation_prompt", ""),
        ai_bot_rag_datastore_ids=lollms_settings.get("ai_bot_rag_datastore_ids", []),
        ai_bot_moderation_enabled=lollms_settings.get("ai_bot_moderation_enabled", False),
        ai_bot_moderation_criteria=lollms_settings.get("ai_bot_moderation_criteria", "Be polite and respectful.")
    )

@bot_management_router.put("/ai-bot-settings", response_model=AiBotSettingsPublic)
async def update_ai_bot_settings(settings: AiBotSettingsUpdate, db: Session = Depends(get_db)):
    """
    Updates the specific settings for the @lollms system user and global configs.
    """
    ASCIIColors.info(f"Updating AI Bot Settings. Moderation Enabled: {settings.ai_bot_moderation_enabled}")
    
    bot_user = db.query(DBUser).filter(DBUser.username == "lollms").first()
    if not bot_user:
        raise HTTPException(status_code=404, detail="@lollms user not found.")

    # 1. Update User Fields
    if settings.lollms_model_name is not None:
        bot_user.lollms_model_name = settings.lollms_model_name
    if settings.active_personality_id is not None:
        bot_user.active_personality_id = settings.active_personality_id

    # 2. Update Global Configs (Upsert)
    configs_to_update = [
        ("ai_bot_enabled", settings.ai_bot_enabled, "boolean"),
        ("ai_bot_system_prompt", settings.ai_bot_system_prompt, "text"),
        ("ai_bot_auto_post", settings.ai_bot_auto_post, "boolean"),
        ("ai_bot_post_interval", settings.ai_bot_post_interval, "float"),
        ("ai_bot_content_mode", settings.ai_bot_content_mode, "string"),
        ("ai_bot_static_content", settings.ai_bot_static_content, "text"),
        ("ai_bot_file_path", settings.ai_bot_file_path, "string"),
        ("ai_bot_generation_prompt", settings.ai_bot_generation_prompt, "text"),
        ("ai_bot_rag_datastore_ids", settings.ai_bot_rag_datastore_ids, "json"),
        ("ai_bot_moderation_enabled", settings.ai_bot_moderation_enabled, "boolean"),
        ("ai_bot_moderation_criteria", settings.ai_bot_moderation_criteria, "text"),
    ]

    for key, value, type_ in configs_to_update:
        if value is not None:
            config_entry = db.query(GlobalConfig).filter(GlobalConfig.key == key).first()
            
            config_data = {
                "value": value,
                "type": type_
            }
            # Serialize to JSON string as expected by DB loader logic
            config_value_str = json.dumps(config_data)
            
            ASCIIColors.cyan(f"Saving setting {key}: {value}")

            if config_entry:
                config_entry.value = config_value_str
            else:
                new_entry = GlobalConfig(
                    key=key, 
                    value=config_value_str,
                    category="AI Bot"
                )
                db.add(new_entry)

    db.commit()
    db.refresh(bot_user)
    
    # Force refresh of the settings cache
    lollms_settings.refresh(db)
    
    from backend.ws_manager import manager
    manager.broadcast_sync({"type": "settings_updated"})

    return await get_ai_bot_settings(db)

@bot_management_router.post("/trigger-post", status_code=202)
async def trigger_ai_bot_post(
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Manually triggers the AI Bot to generate and post content to the feed immediately.
    """
    task_manager.submit_task(
        name="Manual AI Bot Post",
        target=_generate_feed_post_task,
        args=(True,), # Force = True
        description="Manually triggered AI bot post generation.",
        owner_username=current_user.username
    )
    return {"message": "Post generation task started."}

@bot_management_router.post("/trigger-moderation", status_code=202)
async def trigger_batch_moderation(
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Manually triggers the batch moderation task for pending content.
    """
    task_manager.submit_task(
        name="Batch Content Moderation",
        target=_batch_moderate_content_task,
        description="Moderating pending posts and comments.",
        owner_username=current_user.username
    )
    return {"message": "Batch moderation task started."}

@bot_management_router.post("/trigger-full-remoderation", status_code=202)
async def trigger_full_remoderation(
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Manually triggers a full re-evaluation of all posts and comments against moderation criteria.
    """
    task_manager.submit_task(
        name="Full Content Remoderation",
        target=_full_remoderation_task,
        description="Re-moderating ALL posts and comments.",
        owner_username=current_user.username
    )
    return {"message": "Full remoderation task started."}
