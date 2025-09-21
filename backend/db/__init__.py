# backend/db/__init__.py
from .session import init_database, get_db
from .base import Base