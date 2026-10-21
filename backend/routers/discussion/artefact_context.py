"""Read-side enrichment of the context status payload with loaded artefact mass.

lollms_client.LollmsDiscussion.get_context_status() aggregates context zones
from the system prompt, memory and messages, but content injected from loaded
artefacts is not part of that accounting. This module derives the artefact mass
from the discussion object at request time and merges it into the status
payload so the progress bar and the breakdown modal reflect the real budget.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from ascii_colors import ASCIIColors, trace_exception

ESTIMATE_CHARS_PER_TOKEN = 4
ARTEFACT_ZONE_NAME = "artefacts"
ARTEFACT_ACCESSORS = ("artefacts", "get_artefacts", "loaded_artefacts")
ZONE_DETAIL_KEYS = ("content", "tokens", "breakdown", "message_count")


def estimate_text_tokens(text: Any) -> int:
    if not isinstance(text, str) or not text:
        return 0
    return max(1, len(text) // ESTIMATE_CHARS_PER_TOKEN)


MANAGER_EXTRACTION_CANDIDATES = ("list_artefacts", "get_all_artefacts", "get_artefacts", "all")


def _as_artefact_collection(value: Any) -> Optional[List[Any]]:
    if not value:
        return None
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, dict):
        return list(value.values())
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        return list(value)
    return None


def _extract_from_manager(manager: Any) -> Optional[Tuple[List[Any], str]]:
    for candidate_name in MANAGER_EXTRACTION_CANDIDATES:
        candidate = getattr(manager, candidate_name, None)
        if candidate is None:
            continue
        try:
            result = candidate() if callable(candidate) else candidate
        except Exception as e:
            trace_exception(e)
            continue
        collected = _as_artefact_collection(result)
        if collected:
            return collected, f".{candidate_name}"
    nested = getattr(manager, "artefacts", None)
    if nested is not None and nested is not manager:
        collected = _as_artefact_collection(nested)
        if collected:
            return collected, ".artefacts"
    return None


def collect_loaded_artefacts(discussion: Any) -> Tuple[List[Any], str]:
    for accessor_name in ARTEFACT_ACCESSORS:
        accessor = getattr(discussion, accessor_name, None)
        if accessor is None:
            continue
        try:
            result = accessor() if callable(accessor) else accessor
        except Exception as e:
            trace_exception(e)
            continue
        collected = _as_artefact_collection(result)
        if collected:
            return collected, f"discussion.{accessor_name}"
        if result is not None and not callable(result):
            extracted = _extract_from_manager(result)
            if extracted:
                artefacts, candidate_label = extracted
                return artefacts, f"discussion.{accessor_name}{candidate_label}"
    zone = getattr(discussion, "data_zone", None)
    if isinstance(zone, str):
        try:
            zone = json.loads(zone)
        except Exception as e:
            trace_exception(e)
            zone = None
    if isinstance(zone, dict):
        collected = _as_artefact_collection(zone.get("artefacts"))
        if collected:
            return collected, "discussion.data_zone['artefacts']"
    elif zone is not None and hasattr(zone, "artefacts"):
        collected = _as_artefact_collection(getattr(zone, "artefacts"))
        if collected:
            return collected, "discussion.data_zone.artefacts"
    return [], "none"


def extract_artefact_fields(artefact: Any) -> Tuple[str, bool, Any, Any]:
    if isinstance(artefact, dict):
        return (
            artefact.get("title", "artefact"),
            bool(artefact.get("is_loaded")),
            artefact.get("content"),
            artefact.get("tokens"),
        )
    return (
        getattr(artefact, "title", "artefact"),
        bool(getattr(artefact, "is_loaded", False)),
        getattr(artefact, "content", None),
        getattr(artefact, "tokens", None),
    )


AUDIO_EXTENSIONS_CONTEXT = {".mp3", ".wav", ".ogg", ".oga", ".m4a", ".flac", ".webm", ".aac", ".opus"}
AUDIO_LOADED_TOKEN_FOOTPRINT = 24

def compute_artefact_zone(discussion: Any) -> Optional[Dict[str, Any]]:
    artefacts, source = collect_loaded_artefacts(discussion)
    if not isinstance(artefacts, (list, tuple, set)):
        if isinstance(artefacts, dict):
            artefacts = list(artefacts.values())
        else:
            trace_exception(TypeError(f"Non-iterable artefact collection from {source}"))
            return None
    breakdown: Dict[str, int] = {}
    for artefact in artefacts:
        title, is_loaded, content, declared = extract_artefact_fields(artefact)
        if not is_loaded:
            continue
        if isinstance(title, str) and any(title.lower().endswith(ext) for ext in AUDIO_EXTENSIONS_CONTEXT):
            if isinstance(declared, int) and not isinstance(declared, bool) and declared > 0:
                tokens = declared
            else:
                tokens = AUDIO_LOADED_TOKEN_FOOTPRINT
        elif isinstance(declared, int) and not isinstance(declared, bool) and declared > 0:
            tokens = declared
        else:
            tokens = estimate_text_tokens(content)
        if tokens > 0:
            breakdown[title] = breakdown.get(title, 0) + tokens
    if not breakdown:
        return None
    mass = sum(breakdown.values())
    ASCIIColors.green(
        f"[artefact_context] {len(breakdown)} loaded artefact(s) via {source}: "
        f"{mass} tokens counted into the context status."
    )
    return {"tokens": mass, "content": None, "breakdown": breakdown}


def normalize_zone(zone: Any) -> Any:
    if isinstance(zone, int) and not isinstance(zone, bool):
        return {"tokens": zone}
    if isinstance(zone, dict) or not hasattr(zone, "tokens"):
        return zone
    return {key: getattr(zone, key) for key in ZONE_DETAIL_KEYS if hasattr(zone, key)}


def normalize_status_to_dict(status: Any) -> Optional[Dict[str, Any]]:
    if isinstance(status, dict):
        return dict(status)
    if hasattr(status, "max_tokens"):
        return {
            key: getattr(status, key)
            for key in ("current_tokens", "max_tokens", "zones")
            if hasattr(status, key)
        }
    return None


def inject_loaded_artefact_tokens(status: Any, discussion: Any) -> Any:
    try:
        artefact_zone = compute_artefact_zone(discussion)
    except Exception as e:
        trace_exception(e)
        return status
    if artefact_zone is None:
        return status
    normalized = normalize_status_to_dict(status)
    if normalized is None:
        return status
    raw_zones = normalized.get("zones")
    if not isinstance(raw_zones, dict):
        return status
    zones = {name: normalize_zone(zone) for name, zone in raw_zones.items()}
    existing = zones.get(ARTEFACT_ZONE_NAME)
    previous_tokens = int(existing.get("tokens") or 0) if isinstance(existing, dict) else 0
    zones[ARTEFACT_ZONE_NAME] = artefact_zone
    current_tokens = int(normalized.get("current_tokens") or 0)
    normalized["zones"] = zones
    normalized["current_tokens"] = current_tokens + artefact_zone["tokens"] - previous_tokens
    ASCIIColors.green(
        f"[artefact_context] status merge: current_tokens {current_tokens} -> "
        f"{normalized['current_tokens']} (artefact mass {artefact_zone['tokens']})."
    )
    return normalized