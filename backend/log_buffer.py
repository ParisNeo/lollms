
"""
Bounded in-memory capture of the server's own stdout/stderr + explicit app logs.

The admin "Live operations log" panel previously only showed background *task*
logs (from ``DBTask.logs``), which are empty when no task has run. Real server
output (uvicorn access lines, tracebacks, ``ascii_colors`` banners printed by
``main.py``) went straight to the console and was never retrievable from the UI.

This module fixes that by tee-ing ``sys.stdout`` / ``sys.stderr`` into a
thread-safe ring buffer while leaving the original streams untouched (so the
console, log files and container log collectors are unaffected).

Design:
  * ``install_stream_capture()`` wraps ``sys.stdout``/``sys.stderr`` once at
    process startup. It is idempotent and safe to call from every worker.
  * A bounded ``deque`` caps memory. Old lines are evicted automatically — the
    buffer never grows without bound.
  * Each entry records an ISO-8601 UTC timestamp so the UI can filter by window
    (last 1h / 6h / 24h / 48h / all), a ``level`` (inferred for raw stream
    lines) and a ``source`` (``stdout`` / ``stderr`` / ``app``).
  * All access is guarded by a single ``threading.Lock``; reads return plain
    dicts so FastAPI can serialize them without touching live objects.

ANSI / ascii_colors handling
----------------------------
``ascii_colors`` / ``ASCIIColors`` (and uvicorn's colorized output) decorate
text with two kinds of markup that are pure noise in a browser:

  1. Raw ANSI/VT100 escape sequences — SGR colours (``\\x1b[32m``), cursor moves
     (``\\x1b[2K``), OSC hyperlinks/titles, and single-char escapes.
  2. ``ascii_colors`` BBCode-style styling tags (``[green]...[/green]``).

Both are stripped at capture time via :func:`strip_ansi` so every consumer (the
endpoint, the UI, exports) receives clean plain text. The original console
stream still receives the raw, coloured bytes because the tee forwards data
before we sanitise the buffered copy.
"""
from __future__ import annotations

import io
import os
import re
import sys
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, List, Optional

# --------------------------------------------------------------------------- #
# ANSI / ascii_colors sanitisation
# --------------------------------------------------------------------------- #
# Comprehensive ANSI/VT100 escape matcher:
#   * CSI sequences  -> ESC [ ... final-byte  ("\x1b[32m", "\x1b[2K", "\x1b[1;31m")
#   * OSC sequences  -> ESC ] ... BEL|ST      (hyperlinks, window titles)
#   * Fe escapes     -> ESC <single>           (ESC(=, ESC>, ...)
_ANSI_ESCAPE_PATTERN = re.compile(
    r"""
    \x1b
    (?:
        \[[0-9;?]*[ -/]*[@-~]            # CSI ... (colours, cursor, erase)
      | \][^\x07\x1b]*(?:\x07|\x1b\\)    # OSC ... BEL / ST
      | [@-Z\\-_]                        # two-char Fe escapes
    )
    """,
    re.VERBOSE,
)

# When output is piped to a non-TTY some libraries drop the ESC byte but keep
# the bracket tail ("[32m", "[0m"). These residues carry no meaning, so we drop
# them too. Restricted to a short numeric SGR form to avoid eating legitimate
# bracketed text such as "[42]".
_BARE_SGR_PATTERN = re.compile(r"\[[0-9;]{1,4}m")

# ascii_colors BBCode-style tags: [tag], [/tag], [tag=value]. Only known styling
# keywords are stripped so legitimate bracketed words (e.g. "[INFO]") survive.
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


def strip_ansi(text: str) -> str:
    """Remove ANSI escapes, bare SGR residue and ascii_colors style tags.

    This is the single canonical sanitizer used both at capture time
    (:func:`_record`) and defensively on egress (the admin endpoint), so a line
    is guaranteed plain text regardless of how it reached the buffer. On any
    unexpected failure it degrades to returning the input unchanged rather than
    raising — logging must never crash the app.
    """
    if not text:
        return text
    try:
        cleaned = _ANSI_ESCAPE_PATTERN.sub("", text)
        cleaned = _BARE_SGR_PATTERN.sub("", cleaned)
        cleaned = _ASCIICOLORS_TAG.sub("", cleaned)
        # ascii_colors sometimes emits "\r" to redraw a line in place; keep only
        # the final visual state.
        if "\r" in cleaned:
            cleaned = cleaned.split("\r")[-1]
        return cleaned
    except Exception:
        return text


# --------------------------------------------------------------------------- #
# Buffer state
# --------------------------------------------------------------------------- #
# Maximum number of captured lines retained in memory. Sized so a multi-day
# window (24-48h) is realistically servable on a chatty server: a busy instance
# emits a few thousand lines/hour, so 50k lines holds roughly 1-2 days of
# history. Override with LOLLMS_LOG_BUFFER_MAX_LINES.
_MAX_LINES = int(os.getenv("LOLLMS_LOG_BUFFER_MAX_LINES", "50000") or 50000)

# A single ``Lock`` serialises writes (from arbitrary threads) and reads.
_lock = threading.Lock()

# Each entry: {timestamp: str, level: str, source: str, message: str}
_buffer: Deque[Dict[str, str]] = deque(maxlen=_MAX_LINES)

# Guard so the stream wrappers are installed only once per process.
_installed = False

# Matches common Python logging prefixes / level tokens used to infer a level
# from a raw console line ("INFO: ...", "... - WARNING - ...", "ERROR ...").
_LEVEL_PATTERN = re.compile(
    r"(?:\b(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL|TRACE)\b)",
    re.IGNORECASE,
)


def _infer_level(message: str, default: str = "INFO") -> str:
    """Best-effort level inference from a raw console line."""
    match = _LEVEL_PATTERN.search(message or "")
    if not match:
        return default
    token = match.group(1).upper()
    if token == "WARN":
        return "WARNING"
    if token == "FATAL":
        return "CRITICAL"
    return token


def _record(message: str, source: str, level: Optional[str] = None) -> None:
    """Append one physical line to the buffer (thread-safe).

    The line is sanitised here so the stored/browsable text is always clean:
    ANSI colour codes from ``ascii_colors``, bare SGR residue and stray styling
    tags are removed. Level inference runs on the cleaned text.
    """
    if not message:
        return
    text = strip_ansi(message.rstrip("\r\n")).rstrip()
    if not text:
        return
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level or _infer_level(text, "ERROR" if source == "stderr" else "INFO"),
        "source": source,
        "message": text,
    }
    with _lock:
        _buffer.append(entry)


class _TeeStream(io.TextIOBase):
    """A write-only stream that forwards to an original stream AND the buffer.

    Both ``stdout`` and ``stderr`` are replaced by one of these so console
    behaviour is unchanged while every line is also captured.
    """

    def __init__(self, original: io.TextIOBase, source: str):
        self._original = original
        self._source = source
        self._line_buffer = ""

    def write(self, data):
        # Forward first so console output ordering is never delayed by us.
        written = 0
        try:
            if self._original is not None:
                written = self._original.write(data)
        except Exception:
            # A broken console must not break the application.
            pass

        text = data if isinstance(data, str) else str(data)
        # Split on newlines and only record complete lines. Partial writes
        # (common with print(end=""), progress bars) are buffered until a
        # newline arrives.
        self._line_buffer += text
        while "\n" in self._line_buffer:
            line, self._line_buffer = self._line_buffer.split("\n", 1)
            _record(line, self._source)

        return written if written else len(text)

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

    def fileno(self):
        if self._original is None:
            raise io.UnsupportedOperation("fileno")
        return self._original.fileno()

    @property
    def encoding(self):  # pragma: no cover - passthrough
        return getattr(self._original, "encoding", "utf-8")

    def writable(self):
        return True


def install_stream_capture() -> bool:
    """Install the stdout/stderr tee once. Returns True if installed now."""
    global _installed
    with _lock:
        if _installed:
            return False
    # Detect if we already wrapped these streams (e.g. reloader re-import).
    if isinstance(sys.stdout, _TeeStream) and isinstance(sys.stderr, _TeeStream):
        with _lock:
            _installed = True
        return False
    original_out, original_err = sys.stdout, sys.stderr
    with _lock:
        _installed = True
    sys.stdout = _TeeStream(original_out, "stdout")  # type: ignore[assignment]
    sys.stderr = _TeeStream(original_err, "stderr")  # type: ignore[assignment]
    return True


def log_app(message: str, level: str = "INFO") -> None:
    """Explicitly record an application-level line (visible as source='app')."""
    _record(message, "app", level=level)


def get_logs(
    hours: float = 24.0,
    limit: int = 500,
    level: Optional[str] = None,
    source: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Return captured lines newest-last, filtered by window/level/source.

    ``hours`` <= 0 means "no time window" (return everything retained).
    ``level`` / ``source`` are exact (case-insensitive) matches so the UI can
    offer simple dropdowns.
    """
    cutoff = None
    if hours and hours > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    level_upper = (level or "").strip().upper() or None
    source_norm = (source or "").strip().lower() or None

    with _lock:
        snapshot = list(_buffer)

    filtered: List[Dict[str, str]] = []
    for entry in snapshot:
        if source_norm and entry.get("source") != source_norm:
            continue
        if level_upper and (entry.get("level") or "").upper() != level_upper:
            continue
        if cutoff is not None:
            try:
                ts = datetime.fromisoformat(entry["timestamp"])
            except (ValueError, KeyError):
                continue
            if ts < cutoff:
                continue
        filtered.append(entry)

    if limit and limit > 0:
        filtered = filtered[-limit:]
    return filtered


def clear_logs() -> int:
    """Empty the buffer. Returns the number of dropped lines."""
    with _lock:
        count = len(_buffer)
        _buffer.clear()
    return count


def buffer_size() -> int:
    """Current number of retained lines (useful for health/debug)."""
    with _lock:
        return len(_buffer)
