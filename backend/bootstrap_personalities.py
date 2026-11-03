"""One-shot startup bootstrap for the filesystem-backed personalities subsystem.

This module is the canonical "migration script" that runs when the FastAPI app
starts. It performs four steps, in order, all idempotent and non-fatal:

1. **Ensure roots** — create ``data/personalities/global`` and locate each
   user's personal personality folder lazily under ``<user_data_root>``.
2. **Move legacy per-user folders** — the old ``personalities/users/<id>/``
   layout is relocated into each user's standard data folder.
3. **Migrate legacy rows** — every ``DBPersonality`` row is materialized as a
   handbag folder on disk (``handbag.yaml`` + ``SOUL.md``), the filepath is
   recorded in ``UserPersonalityPreference`` for the owner, then the DB row is
   deleted. A second call finds zero rows and is a no-op.
4. **Mandatory seed** — delegates to
   ``backend.personalities.ensure_default_lollms_handbag()``, which is
   self-healing (it recreates the folder whenever it is missing, including
   on running instances where the startup phase 4 was skipped).

Wire-up: ``main._bootstrap_personalities`` invokes ``run_personalities_bootstrap``
from inside the one-time startup task plan, right after schema migration and
before filesystem/DB sync. Any failure is logged via ``trace_exception`` and
the server keeps booting. The import-time hook in
``backend.routers.personalities`` only creates the empty roots (filesystem
work), never touches the DB.
"""
from ascii_colors import ASCIIColors, trace_exception

from backend.personalities import (
    ensure_default_lollms_handbag,
    ensure_personality_roots,
    migrate_db_personalities_to_handbags,
    migrate_legacy_user_personality_folders,
)


# ---------------------------------------------------------------------------
# Startup pipeline
# ---------------------------------------------------------------------------

def run_personalities_bootstrap(db) -> None:
    """Execute the full personalities startup pipeline.

    ``db`` is an open SQLAlchemy session. The caller owns it. This function
    never raises: every stage is individually guarded and traced so a broken
    DB or read-only disk can never block the server from starting.
    """
    try:
        ensure_personality_roots()
    except Exception as exc:
        trace_exception(exc)
        ASCIIColors.error(f"[personalities] roots bootstrap failed: {exc}")
        return

    try:
        moved = migrate_legacy_user_personality_folders(db)
        if moved:
            ASCIIColors.info(
                f"[personalities] relocated {moved} users' handbags into "
                f"their user data folders")
    except Exception as exc:
        trace_exception(exc)
        ASCIIColors.warning(f"[personalities] legacy user-folder migration failed: {exc}")

    try:
        migrated = migrate_db_personalities_to_handbags(db)
        if migrated:
            ASCIIColors.info(
                f"[personalities] migrated {migrated} legacy DB personalities to handbags")
    except Exception as exc:
        trace_exception(exc)
        ASCIIColors.warning(f"[personalities] DB → handbag migration failed: {exc}")

    try:
        ensure_default_lollms_handbag()
    except Exception as exc:
        trace_exception(exc)
        ASCIIColors.warning(f"[personalities] default handbag seeding failed: {exc}")