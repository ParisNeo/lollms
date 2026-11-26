# backend/account_types.py
"""Account-type taxonomy for Simplified LoLLMs users.

Historically every ``User`` row was a human WebUI account. The mesh-network
feature introduces two additional, non-interactive account kinds that share
the SAME quota / metering / generation pipeline but are gated differently:

    * ``human`` — a normal WebUI account (login with password, full profile).
    * ``mesh``  — a *corporate* peer LoLLMs instance. It represents the entire
                  consumption of another server (and its own user base). It has
                  no interactive UI; it authenticates exclusively through an
                  API key against the OpenAI-compatible surface, and its token
                  usage is metered/quota'd as a single account.
    * ``agent`` — an AI/bot identity. It consumes generative services through
                  the API but is never a person: no email, no password, no
                  profile, no WebUI session.

Both ``mesh`` and ``agent`` accounts are *service principals*: they are
``is_active`` (so quota checks and generation succeed) but are explicitly
denied interactive login and hidden from human-facing user listings.
"""
from __future__ import annotations

from typing import Final

HUMAN: Final[str] = "human"
MESH: Final[str] = "mesh"
AGENT: Final[str] = "agent"

ALL_ACCOUNT_TYPES: Final[tuple[str, ...]] = (HUMAN, MESH, AGENT)

#: Account types that may authenticate interactively (WebUI / JWT login).
INTERACTIVE_ACCOUNT_TYPES: Final[frozenset[str]] = frozenset({HUMAN})

#: Account types that are service principals (API-key only, no profile).
SERVICE_ACCOUNT_TYPES: Final[frozenset[str]] = frozenset({MESH, AGENT})


def normalize_account_type(value: str | None) -> str:
    """Coerce arbitrary input to a known account type.

    Unknown / empty values default to ``human`` so legacy rows (which have no
    ``account_type``) and loose client input never break authentication.
    """
    candidate = (value or "").strip().lower()
    return candidate if candidate in ALL_ACCOUNT_TYPES else HUMAN


def is_human(value: str | None) -> bool:
    return normalize_account_type(value) == HUMAN


def is_service_account(value: str | None) -> bool:
    return normalize_account_type(value) in SERVICE_ACCOUNT_TYPES


def is_interactive(value: str | None) -> bool:
    """True when the account may log in to the WebUI (issue a session)."""
    return normalize_account_type(value) in INTERACTIVE_ACCOUNT_TYPES