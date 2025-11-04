from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from backend.db import get_db
from backend.db.models.user import User as DBUser

bot_management_router = APIRouter(tags=["Administration", "AI Bot"])

class AiBotSettingsUpdate(BaseModel):
    lollms_model_name: Optional[str] = None
    active_personality_id: Optional[str] = None

class AiBotSettingsPublic(BaseModel):
    lollms_model_name: Optional[str] = None
    active_personality_id: Optional[str] = None

    class Config:
        from_attributes = True

@bot_management_router.get("/ai-bot-settings", response_model=AiBotSettingsPublic)
async def get_ai_bot_settings(db: Session = Depends(get_db)):
    """
    Retrieves the specific settings for the @lollms system user.
    """
    bot_user = db.query(DBUser).filter(DBUser.username == "lollms").first()
    if not bot_user:
        raise HTTPException(status_code=404, detail="@lollms user not found.")
    return bot_user

@bot_management_router.put("/ai-bot-settings", response_model=AiBotSettingsPublic)
async def update_ai_bot_settings(settings: AiBotSettingsUpdate, db: Session = Depends(get_db)):
    """
    Updates the specific settings for the @lollms system user.
    """
    bot_user = db.query(DBUser).filter(DBUser.username == "lollms").first()
    if not bot_user:
        raise HTTPException(status_code=404, detail="@lollms user not found.")

    update_data = settings.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(bot_user, key, value)
    
    db.commit()
    db.refresh(bot_user)
    return bot_user