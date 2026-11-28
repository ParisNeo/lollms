
"""
In-memory ring buffer that captures the server's real stdout/stderr stream.

Why this exists
---------------
``GET /api/admin/system/logs`` only returns *task* logs (``DBTask.logs``).
When no background task has run recently the admin "Live operations log"
panel is empty even though the process is actively printing to the console
via ``ascii_colors`` / uvicorn / plain ``print``.

This module installs a root-logger handler plus a ``sys.stdout``/``sys.stderr``
tee so that everything written to the process console is retained in a
bounded, thread-safe deque. The admin endpoint can then render the actual
server output with a configurable time window.

Design notes
------------
* **Bounded**: the deque has a hard ``maxlen`` so a chatty server cannot
  exhaust memory.
* **Thread-safe**: writers come from many request threads; every mutation is
  guarded by a single lock.
* **Zero-config**: ``install()`` is idempotent and cheap; calling it twice is
  a no-op.
* **Non-invasive**: the stdout/stderr tee forwards to the original streams so
  the console behaviour is unchanged. A failure inside the tee is swallowed so
  logging can never crash the app.
"""
from __future__ import annotations

import logging
import re
import sys
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional

_MAX_LINES = 5000

# ANSI / VT100 colour & control sequences emitted by ascii_colors / uvicorn.
# This feed is rendered as HTML in the admin panel, so escape codes must be
# stripped — otherwise "ESC[32m" shows up as literal garbage. Mirrors the
# pattern in backend.log_buffer so both log surfaces render identically.
_ANSI_ESCAPE_PATTERN = re.compile(
    r"""
    \x1b
    (?:
        \[[0-9;?]*[ -/]*[@-~]
      | \][^\x07\x1b]*(?:\x07|\x1b\\)
      | [@-Z\\-_]
    )
    """,
    re.VERBOSE,
)
_BARE_SGR_PATTERN = re.compile(r"\[[0-9;]{1,4}m")


def _strip_ansi(text: str) -> str:
    """Strip ANSI colour/control codes for clean HTML rendering."""
    if not text:
        return text
    cleaned = _ANSI_ESCAPE_PATTERN.sub("", text)
    cleaned = _BARE_SGR_PATTERN.sub("", cleaned)
    if "\r" in cleaned:
        cleaned = cleaned.split("\r")[-1]
    return cleaned

# Strip ANSI escape sequences and ascii_colors BBCode-style styling tags so the
# captured console output is plain text (never raw ``\x1b[..m`` or ``[green]``).
_ANSI_ESCAPE = re.compile(
    r"""
    \x1b
    (?:
        \[[0-?]*[ -/]*[@-~]
      | \][^\x07]*\x07
      | \][^\x1b]*\x1b\\
      | [@-Z\\-_]
    )
    """,
    re.VERBOSE,
)
_ASCIICOLORS_TAG = re.compile(
    r"\[/?(?:"
    r"bold|b|italic|i|underline|u|strike|s|blink|reverse|dim|"
    r"black|red|green|yellow|blue|magenta|cyan|white|"
    r"light_black|light_red|light_green|light_yellow|light_blue|"
    r"light_magenta|light_cyan|light_white|"
    r"bg_black|bg_red|bg_green|bg_yellow|bg_blue|bg_magenta|bg_cyan|bg_white|"
    r"dark_red|dark_green|dark_blue|dark_yellow"
    r")(?:=[^\]]*)?\]",
    re.IGNORECASE,
)


def _strip_markup(text: str) -> str:
    """Remove ANSI escapes and ascii_colors styling tags; fail-safe to input."""
    if not text:
        return text
    try:
        return _ASCIICOLORS_TAG.sub("", _ANSI_ESCAPE.sub("", text))
    except Exception:
        return text

# A single entry: {"timestamp": iso8601 str, "level": str, "source": str, "message": str}
_entries: Deque[Dict[str, str]] = deque(maxlen=_MAX_LINES)
_lock = threading.Lock()
_installed = False
_original_stdout = sys.stdout
_original_stderr = sys.stderr


def _append(message: str, level: str = "INFO", source: str = "stdout") -> None:
    """Record one line. Blank lines are skipped to keep the buffer dense."""
    text = _strip_ansi((message or "").rstrip("\n")).rstrip()
    if not text.strip():
        return
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": (level or "INFO").upper(),
        "source": source,
        "message": text,
    }
    with _lock:
        _entries.append(entry)


class _StreamTee:
    """File-like object that mirrors writes to the real stream and the buffer.

    Both ``write`` and ``flush`` are implemented because uvicorn/tqdm and
    ``ascii_colors`` call them on the object they believe is ``sys.stdout``.
    """

    def __init__(self, original, source: str):
        self._original = original
        self._source = source

    def write(self, data):
        try:
            if self._original is not None:
                self._original.write(data)
        except Exception:
            pass
        try:
            # ``data`` may contain several lines; split so the buffer keeps
            # one entry per line and timestamps stay meaningful.
            for line in str(data).splitlines():
                _append(line, level="INFO" if self._source == "stdout" else "ERROR", source=self._source)
        except Exception:
            pass
        return len(data) if data is not None else 0

    def flush(self):
        try:
            if self._original is not None:
                self._original.flush()
        except Exception:
            pass

    def isatty(self):
        try:
            return bool(self._original and self._original.isatty())
        except Exception:
            return False

    # Delegate any other attribute access (encoding, fileno, buffer, ...) to
    # the original stream so libraries that introspect stdout keep working.
    def __getattr__(self, name):
        return getattr(self._original, name)


class _BufferLoggingHandler(logging.Handler):
    """Root-logger handler that funnels formatted records into the buffer."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            source = "stderr" if record.levelno >= logging.WARNING else "stdout"
            _append(message, level=record.levelname, source=source)
        except Exception:
            # A logging error must never propagate into the application.
            pass


def install() -> None:
    """Install the stdout/stderr tee and the root-logger handler. Idempotent."""
    global _installed, _original_stdout, _original_stderr
    if _installed:
        return

    _original_stdout = sys.stdout
    _original_stderr = sys.stderr

    # 1. Tee the raw console streams (captures print / ascii_colors / uvicorn
    #    output that bypasses the logging module).
    sys.stdout = _StreamTee(_original_stdout, source="stdout")
    sys.stderr = _StreamTee(_original_stderr, source="stderr")

    # 2. Attach to the root logger so records emitted through ``logging`` are
    #    captured with their real level (INFO/WARNING/ERROR/...).
    handler = _BufferLoggingHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)

    _installed = True


def get_entries(hours: int = 24, limit: int = 500) -> List[Dict[str, str]]:
    """Return buffered lines newer than ``hours`` ago, newest first.

    ``hours <= 0`` disables the time filter (returns everything buffered).
    ``limit`` caps how many rows are returned after the time filter.
    """
    now = datetime.now(timezone.utc)
    cutoff: Optional[datetime] = None
    if hours and hours > 0:
        from datetime import timedelta
        cutoff = now - timedelta(hours=hours)

    with _lock:
        snapshot = list(_entries)

    result: List[Dict[str, str]] = []
    for entry in reversed(snapshot):  # newest first
        if cutoff is not None:
            try:
                ts = datetime.fromisoformat(entry["timestamp"])
            except (ValueError, KeyError):
                ts = None
            if ts is not None and ts < cutoff:
                continue
        result.append(entry)
        if len(result) >= limit:
            break
    return result
