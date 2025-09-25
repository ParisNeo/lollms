from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
# The migration functions are no longer called from here.
from backend.config import SERVER_CONFIG
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
            connect_args={"check_same_thread": False, "timeout": 60}, 
            echo=False,
            pool_pre_ping=True,
            pool_size=SERVER_CONFIG.get("DB_POOL_SIZE",20),          # base pool size
            max_overflow=SERVER_CONFIG.get("DB_MAX_OVERFLOW",30),       # additional connections beyond pool_size
            pool_timeout=SERVER_CONFIG.get("DB_POOL_TIMEOUT",60)       # seconds to wait before raising TimeoutError
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
