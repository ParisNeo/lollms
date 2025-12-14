from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
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
            pool_size=50, # Increased for higher concurrency
            max_overflow=50, # Increased overflow
            pool_timeout=60
        )

        # Optimize SQLite for concurrency
        if "sqlite" in db_url:
            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL") # Enable Write-Ahead Logging
                cursor.execute("PRAGMA synchronous=NORMAL") # Faster writes, still safe
                cursor.execute("PRAGMA cache_size=-64000") # Increase cache to ~64MB
                cursor.execute("PRAGMA busy_timeout=5000") # Wait up to 5s for lock
                cursor.close()

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database first.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
