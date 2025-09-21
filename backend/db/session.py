from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
# The migration functions are no longer called from here.
from backend.db.migration import run_schema_migrations_and_bootstrap, check_and_update_db_version

engine = None
SessionLocal = None

def init_database(db_url: str):
    """
    Initializes the database engine and session factory for the current process.
    The main process calls this first to log messages. Workers call it to get their
    own connections without re-logging.
    """
    global engine, SessionLocal
    if engine is None:  # Ensure it's only created once per process
        engine = create_engine(
            db_url, 
            connect_args={"check_same_thread": False, "timeout": 30}, 
            echo=False,
            pool_pre_ping=True
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        # The verbose "Database tables checked/created" log is now handled
        # exclusively in the locked section of main.py's startup tasks.

def get_db():
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database first.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()