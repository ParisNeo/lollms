# scripts/migrate_account_types.py
"""Idempotent migration: add ``account_type`` to the ``users`` table.

Safe to run repeatedly. Supports the SQLite backend used by Simplified LoLLMs
(and degrades gracefully on other dialects). All pre-existing rows become
``human`` — the only behaviour-preserving default.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a standalone script from the repo root.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import inspect, text  # noqa: E402

from backend.db import engine  # noqa: E402  (centralised engine)
from backend.account_types import HUMAN  # noqa: E402


def _column_exists(connection, table: str, column: str) -> bool:
    inspector = inspect(connection)
    if table not in inspector.get_table_names():
        return False
    return any(col["name"] == column for col in inspector.get_columns(table))


def migrate() -> int:
    """Ensure ``users.account_type`` exists and backfill legacy rows."""
    with engine.begin() as connection:
        if not _column_exists(connection, "users", "account_type"):
            # SQLite accepts ADD COLUMN with a constant default in one pass.
            connection.execute(
                text(
                    "ALTER TABLE users "
                    f"ADD COLUMN account_type VARCHAR(16) NOT NULL DEFAULT '{HUMAN}'"
                )
            )
            print("MIGRATE: added users.account_type")
        else:
            print("MIGRATE: users.account_type already present")

        # Backfill any NULLs (e.g. DBs migrated from very old schemas).
        result = connection.execute(
            text("UPDATE users SET account_type = :h WHERE account_type IS NULL OR account_type = ''"),
            {"h": HUMAN},
        )
        if result.rowcount:
            print(f"MIGRATE: backfilled {result.rowcount} row(s) to '{HUMAN}'")
    return 0


if __name__ == "__main__":
    sys.exit(migrate())