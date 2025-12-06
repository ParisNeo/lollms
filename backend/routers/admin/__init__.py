# [UPDATE] backend/routers/admin/__init__.py
from fastapi import APIRouter, Depends

from backend.session import get_current_admin_user
from .bindings_management import bindings_management_router
from .content_management import content_management_router
from .settings_management import settings_management_router
from .system_management import system_management_router
from .user_management import user_management_router
from .rag_management import rag_management_router
from .rss_management import rss_management_router
from .bot_management import bot_management_router
from .news_management import news_management_router
from .moderation_management import router as moderation_router

# This is the main router that will be imported by the main application.
# It aggregates all the theme-based admin routers.
admin_router = APIRouter(
    prefix="/api/admin",
    tags=["Administration"],
    dependencies=[Depends(get_current_admin_user)]
)

# Include all the sub-routers
admin_router.include_router(bindings_management_router)
admin_router.include_router(content_management_router)
admin_router.include_router(settings_management_router)
admin_router.include_router(system_management_router)
admin_router.include_router(user_management_router)
admin_router.include_router(rag_management_router)
admin_router.include_router(rss_management_router)
admin_router.include_router(bot_management_router)
admin_router.include_router(news_management_router)
admin_router.include_router(moderation_router)
