#!/usr/bin/env python
"""
repair_user_chat_flag_columns.py

One-shot, idempotent repair for databases created BEFORE the new
LollmsDiscussion.chat() flag columns were added to the `users` model.

Symptom this fixes:
    sqlite3.OperationalError: no such column: users.auto_activate_artefacts
    (and any of the other enable_* / capability columns)

Why it is needed:
    SQLAlchemy's ``Base.metadata.create_all`` only creates MISSING TABLES.
    It never ALTERs an existing table to add columns. If the startup
    column-migration step did not run against the updated model metadata
    (e.g. it inspected before the model was re-imported, or used a cached
    inspector snapshot), an existing ``users`` table stays stale and every
    ORM SELECT that includes the new columns fails.

What it does:
    1. Loads the real application engine and ``Base`` metadata.
    2. Uses a FRESH inspector to compute the set of missing ``users`` columns.
    3. Emits an ``ALTER TABLE users ADD COLUMN ...`` for each, preserving the
       SQLAlchemy type and ``server_default`` from the model (single source
       of truth — no hardcoded duplicate list of types/defaults).

Safe to run multiple times: already-present columns are skipped.
Safe on a fresh DB: there is nothing to add, it simply reports OK.
"""
from __future__ import annotations

import sys
from pathlib import Path

# --- Ensure the project root (parent of this script's dir) is importable ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError


def _resolve_engine_and_base():
    """
    Import the application engine and declarative Base, tolerating the few
    common module layouts used across the project.
    """
    engine = None
    Base = None

    # Preferred: backend.db package re-exports both.
    try:
        import backend.db as db_pkg  # noqa: WPS433
        engine = getattr(db_pkg, "engine", None)
        Base = getattr(db_pkg, "Base", None)
    except Exception:
        pass

    if Base is None:
        from backend.db.base import Base as _Base  # noqa: WPS433
        Base = _Base

    if engine is None:
        # Common locations for the SQLAlchemy engine.
        for module_path in ("backend.db.session", "backend.db"):
            try:
                mod = __import__(module_path, fromlist=["engine"])
                engine = getattr(mod, "engine", None)
                if engine is not None:
                    break
            except Exception:
                continue

    if engine is None:
        raise RuntimeError(
            "Could not resolve the SQLAlchemy engine. "
            "Adjust _resolve_engine_and_base() to point to your engine."
        )

    # Importing all models guarantees Base.metadata is fully populated.
    try:
        import backend.db.models  # noqa: F401,WPS433
    except Exception:
        pass

    return engine, Base


def _build_add_column_ddl(engine, table_name: str, column) -> str:
    """Build `ALTER TABLE ... ADD COLUMN ...` preserving type and server_default."""
    from sqlalchemy.schema import CreateColumn  # local import

    col_type = column.type.compile(dialect=engine.dialect)

    default_clause = ""
    if column.server_default is not None:
        arg = getattr(column.server_default, "arg", None)
        if arg is not None:
            # TextClause / literal defaults
            try:
                rendered = str(arg)
            except Exception:
                rendered = None
            if rendered is not None:
                if isinstance(arg, (int, float)):
                    default_clause = f" DEFAULT {arg}"
                elif isinstance(arg, str) and not _looks_like_sql_expression(arg):
                    escaped = arg.replace("'", "''")
                    default_clause = f" DEFAULT '{escaped}'"
                else:
                    # e.g. a func.now() TextClause — inline as-is
                    default_clause = f" DEFAULT {rendered}"

    return f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {col_type}{default_clause}'


def _looks_like_sql_expression(value: str) -> bool:
    """Heuristic: treat obvious SQL fragments (parentheses, keywords) as expressions."""
    lowered = value.strip().lower()
    return "(" in value or ")" in value or lowered.startswith(("current_", "now", "datetime"))


def ensure_columns(engine, Base, table_name: str) -> list[str]:
    """
    Add every column declared on ``table_name`` in ``Base.metadata`` that is
    missing from the live database. Returns the list of added column names.
    """
    metadata = Base.metadata
    if table_name not in metadata.tables:
        raise RuntimeError(f"Table '{table_name}' is not present in model metadata.")

    model_table = metadata.tables[table_name]

    added: list[str] = []

    # A brand-new inspector guarantees we read the CURRENT on-disk schema.
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        # Table itself is missing — create_all should have handled this; do it now.
        metadata.create_all(engine, tables=[model_table])
        print(f"[repair] Table '{table_name}' did not exist — created it.")
        return added

    existing_columns = {col["name"] for col in inspector.get_columns(table_name)}

    with engine.begin() as conn:
        for column in model_table.columns:
            if column.name in existing_columns:
                continue
            ddl = _build_add_column_ddl(engine, table_name, column)
            try:
                conn.execute(text(ddl))
                added.append(column.name)
                print(f"[repair] ADDED  {table_name}.{column.name}")
            except SQLAlchemyError as exc:
                # Do not swallow: report and continue so one odd column cannot
                # block the rest of the repair.
                print(f"[repair] FAILED {table_name}.{column.name}: {exc}")

    return added


def main() -> int:
    engine, Base = _resolve_engine_and_base()
    print(f"[repair] Using engine: {engine.url}")

    added = ensure_columns(engine, Base, "users")

    # Final verification with another fresh inspector.
    inspector = inspect(engine)
    final_columns = {c["name"] for c in inspector.get_columns("users")}

    required_flag_columns = [c.name for c in Base.metadata.tables["users"].columns]
    still_missing = [name for name in required_flag_columns if name not in final_columns]

    print("")
    if still_missing:
        print(f"[repair] ERROR: still missing columns after repair: {still_missing}")
        return 1

    print(f"[repair] Done. Added {len(added)} column(s). 'users' schema is now in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())