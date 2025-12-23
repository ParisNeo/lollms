# [CREATE] backend/routers/admin/services_management.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Dict, List, Any
import json

from backend.db import get_db
from backend.db.models.config import GlobalConfig
from backend.session import get_current_admin_user
from backend.settings import settings
from backend.utils import service_usage_stats

router = APIRouter(prefix="/services", tags=["Admin", "Services Management"])

class ServiceUsageInfo(BaseModel):
    total_hits: int
    user_count: int

class ServiceDashboardStats(BaseModel):
    usage: Dict[str, ServiceUsageInfo]
    settings: Dict[str, Any]

@router.get("/dashboard", response_model=ServiceDashboardStats)
async def get_services_dashboard(db: Session = Depends(get_db)):
    """
    Retrieves status of all service interfaces and their usage statistics.
    """
    # 1. Gather usage from memory stats
    usage_response = {}
    for service, stats in service_usage_stats.items():
        usage_response[service] = ServiceUsageInfo(
            total_hits=stats["total_hits"],
            user_count=len(stats["users"])
        )

    # 2. Gather settings
    service_keys = [
        "openai_api_service_enabled", "openai_api_require_key",
        "ollama_service_enabled", "ollama_require_key",
        "lollms_services_enabled", "lollms_services_require_key",
        "rate_limit_enabled", "rate_limit_max_requests", "rate_limit_window_seconds"
    ]
    
    settings_response = {k: settings.get(k) for k in service_keys}

    return ServiceDashboardStats(
        usage=usage_response,
        settings=settings_response
    )

@router.post("/reset-usage")
async def reset_usage_stats():
    """Resets the in-memory usage counters."""
    for service in service_usage_stats:
        service_usage_stats[service] = {"total_hits": 0, "users": {}}
    return {"message": "Usage statistics reset."}
