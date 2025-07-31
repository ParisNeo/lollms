from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.db.migration import run_schema_migrations_and_bootstrap, check_and_update_db_version

engine = None
SessionLocal = None

def init_database(db_url: str):
    global engine, SessionLocal
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)
    print(f"INFO: Database tables checked/created using metadata at URL: {db_url}")

    with engine.connect() as connection:
        # Create the inspector from the connection, ensuring it operates within the same transaction.
        inspector = inspect(connection)
        
        transaction = connection.begin()
        try:
            run_schema_migrations_and_bootstrap(connection, inspector)
            transaction.commit()
            print("INFO: Database schema migration/check completed successfully.")
        except Exception as e_migrate:
            transaction.rollback()
            print(f"CRITICAL: Database migration failed: {e_migrate}. Changes rolled back.")
            raise

    # Handle DB version record outside the main migration transaction
    check_and_update_db_version(SessionLocal)

def get_db():
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database first.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()