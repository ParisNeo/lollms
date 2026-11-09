"""Filesystem-backed personality (handbag) catalog service.

Single source of truth: personality behavior is defined by handbag folders on
disk, never by database rows. This module owns:

* Canonical roots under the app ``data`` folder::

      data/personalities/global/                    -> admin/zoo/uploaded, all users
      <user_data_root>/personalities/<handbag>/     -> per-user studio/uploaded handbags

  where ``<user_data_root>`` is the standard per-user data directory used by
  the rest of the platform (``data/users/<username>/``). Personal handbags
  therefore live next to the user's discussions, attachments and DM assets.

* Lightweight manifest discovery for header catalogs.
* Path-safe resolution for discussion runtime wiring.

Sharing is metadata-only (DB ACL ``PersonalityShareLink``); consumers get
read-only discovery of handbags that physically live in the owner's folder.
"""

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ascii_colors import ASCIIColors, trace_exception

try:
    import yaml
except ImportError:  # pragma: no cover - yaml ships with pyyaml, always present
    yaml = None

# ---------------------------------------------------------------------------
# Roots
# ---------------------------------------------------------------------------

_VALID_SCOPES = ("global", "personal", "shared")

# ---------------------------------------------------------------------------
# One-shot guards (per-process)
# ---------------------------------------------------------------------------
# The legacy DB -> handbag migration and the discussion FK cleanup are
# one-time data fixes. Both are attempted at most once per process so they
# cannot spam the log on every catalog refresh (each ``POST /install``
# triggers a catalog GET, which used to replay them and re-emit the same
# warnings over and over).
_db_personalities_migrated = False
_discussion_fk_cleanup_attempted = False


def _data_root() -> Path:
    """Resolve the application data folder.

    Priority:
      1. ``LOLLMS_DATA_PATH`` env var (tests / CI)
      2. ``backend.config.APP_DATA_DIR`` (canonical app data dir — this is
         the SAME folder the rest of LoLLMS uses for ``users/``, ``apps/``,
         ``safestores/``, ... so personalities live next to them)
      3. ``Path("data")`` fallback for exotic launches
    """
    env_root = os.environ.get("LOLLMS_DATA_PATH")
    if env_root:
        return Path(env_root).resolve()
    try:
        from backend.config import APP_DATA_DIR
        return Path(APP_DATA_DIR).resolve()
    except Exception:
        return Path("data").resolve()


def global_personalities_root() -> Path:
    return _data_root() / "personalities" / "global"


def user_personalities_root(username: str) -> Path:
    """Per-user personality root inside the user's standard data folder.

    Handbags live next to the rest of the user's data (discussions, assets,
    DM attachments) under ``<user_data_root>/personalities/``, so all of a
    user's files stay under one directory.

    ``LOLLMS_DATA_PATH`` (tests / CI) mirrors the production layout as
    ``<data>/users/<username>/personalities`` — resolved the same way as
    ``backend.session.get_user_data_root`` to keep the two consistent.
    """
    username = str(username)
    env_root = os.environ.get("LOLLMS_DATA_PATH")
    if env_root:
        return (Path(env_root).resolve() / "users" / username / "personalities")
    from backend.session import get_user_data_root
    return get_user_data_root(username) / "personalities"


def ensure_personality_roots() -> None:
    """Create handbag roots and fail fast if the data folder is not writable.

    Only the shared ``global`` root is materialised here. Per-user roots are
    created lazily inside each user's data folder on first access.
    """
    base = _data_root() / "personalities"
    root = base / "global"
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        ASCIIColors.error(f"[personalities] cannot create {root}: {exc}")
        raise RuntimeError(
            f"Cannot create personalities root {root}: {exc}") from exc
    probe = base / ".write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        ASCIIColors.error(f"[personalities] data folder not writable: {exc}")
        raise RuntimeError(
            f"Personalities data folder is not writable: {exc}") from exc
    ASCIIColors.info(f"[personalities] roots ready under {base}")


# ---------------------------------------------------------------------------
# Mandatory default persona ("lollms") — self-healing seed
# ---------------------------------------------------------------------------

DEFAULT_LOLLMS_SLUG = "lollms"

DEFAULT_LOLLMS_MANIFEST = """\
name: Lollms
description: The default LoLLMS personality — a polite, honest, and capable AI assistant that adapts to the task at hand.
author: LoLLMS
category: General
"""

DEFAULT_LOLLMS_SOUL = """\
# Lollms

You are **Lollms**, the default AI personality shipped with the LoLLMS platform.

## Behaviour

- Be clear, direct, and concise unless a longer answer is genuinely required.
- Prefer correct, safe, and honest answers over confident-sounding guesses.
- Explicitly state when you are uncertain instead of speculating.
- Ask a clarifying question when the request is ambiguous.
- Match the user's tone: professional when needed, warm always.

## Scope

- You do not impersonate real people.
- You do not fabricate citations, sources, or URLs.
- You refuse requests that would cause real-world harm.
"""


def ensure_default_lollms_handbag() -> bool:
    """Self-healing seed for the mandatory ``lollms`` persona.

    The ``lollms`` personality is *mandatory*: it is (re)created here whenever
    it is missing, so the global catalog is never empty — even if the startup
    bootstrap ran before migration finished, was skipped because the server
    was already running, or a previous attempt failed mid-write.

    Never raises: the whole sequence is wrapped and failures are logged.
    Returns ``True`` when this call actually created the handbag folder,
    ``False`` when it was already present or when creation failed.
    """
    try:
        target = global_personalities_root() / DEFAULT_LOLLMS_SLUG
        if target.is_dir():
            return False
        target.mkdir(parents=True, exist_ok=True)
        (target / "handbag.yaml").write_text(DEFAULT_LOLLMS_MANIFEST, encoding="utf-8")
        (target / "SOUL.md").write_text(DEFAULT_LOLLMS_SOUL, encoding="utf-8")
        ASCIIColors.info(f"[personalities] ensured mandatory 'lollms' handbag at {target}")
        return True
    except Exception as exc:
        ASCIIColors.warning(
            f"[personalities] cannot seed mandatory 'lollms' handbag: {exc}")
        return False


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

def _safe_resolve(root: Path, name: str) -> Path:
    """Resolve ``root/name`` and reject traversal outside ``root``."""
    if not name or Path(name).name != name or name.startswith("."):
        raise ValueError(f"Invalid handbag name: {name!r}")
    candidate = (root / name).resolve()
    if root.resolve() not in candidate.parents and candidate != root.resolve():
        raise ValueError(f"Path traversal rejected: {name!r}")
    return candidate


# ---------------------------------------------------------------------------
# Discovery (lightweight manifest scan — no Handbag() instantiation)
# ---------------------------------------------------------------------------

def _read_handbag_icon(path: Path) -> Optional[str]:
    """Return a data-URI icon for a handbag, or ``None``.

    Resolution order (files first — a real file always beats the manifest):

    1. ``icon.{png,jpg,jpeg,svg,webp}`` in the handbag root.
    2. ``icon.*`` directly under ``assets/``.
    3. ``handbag.yaml`` ``icon`` / ``icon_base64`` field, tolerant of:
       - a ``data:<mime>;base64,<...>`` URI (returned verbatim),
       - an ``http(s)://`` URL (returned verbatim; frontend fetches),
       - a relative file path inside the handbag (resolved and read),
       - a raw base64 string (wrapped as a PNG data URI).

    Returns a URI string consumable directly by ``<img :src="...">``.
    Never raises: any IO/parse failure degrades to ``None`` so one bad icon
    cannot blank the whole catalog response.
    """
    import base64 as _b64
    import mimetypes as _mime

    def _encode_file(candidate: Path) -> Optional[str]:
        try:
            mime = _mime.guess_type(candidate.name)[0] or "image/png"
            return (f"data:{mime};base64,"
                    + _b64.b64encode(candidate.read_bytes()).decode("ascii"))
        except OSError:
            return None

    # 1. Icon file at handbag root (authoritative: an actual file is always
    #    valid, unlike a possibly-bogus manifest field declaring a path).
    for fname in ("icon.png", "icon.jpg", "icon.jpeg", "icon.svg", "icon.webp"):
        candidate = path / fname
        if candidate.is_file():
            encoded = _encode_file(candidate)
            if encoded:
                return encoded

    # 2. Icon file under assets/
    assets = path / "assets"
    if assets.is_dir():
        for candidate in sorted(assets.glob("icon.*")):
            if candidate.is_file():
                encoded = _encode_file(candidate)
                if encoded:
                    return encoded

    # 3. Manifest-declared icon (data URI / URL / relative path / raw base64)
    manifest = _load_manifest(path)
    for key in ("icon", "icon_base64"):
        declared = manifest.get(key)
        if not isinstance(declared, str) or not declared.strip():
            continue
        declared = declared.strip()
        if declared.startswith("data:"):
            return declared
        if declared.startswith(("http://", "https://")):
            return declared
        try:
            handbag_root = path.resolve()
            candidate = (handbag_root / declared).resolve()
            if handbag_root in candidate.parents and candidate.is_file():
                encoded = _encode_file(candidate)
                if encoded:
                    return encoded
        except (OSError, ValueError):
            pass
        try:
            raw = _b64.b64decode(declared, validate=True)
            if raw:
                return (f"data:image/png;base64,"
                        + _b64.b64encode(raw).decode("ascii"))
        except Exception:
            pass
    return None


def _scan_handbag(path: Path, scope: str, owner: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path.is_dir():
        return None
    manifest: Dict[str, Any] = {}
    manifest_file = path / "handbag.yaml"
    if manifest_file.is_file() and yaml is not None:
        try:
            manifest = yaml.safe_load(manifest_file.read_text(encoding="utf-8")) or {}
            if not isinstance(manifest, dict):
                manifest = {}
        except Exception:
            manifest = {}
    icon_data = _read_handbag_icon(path)
    extra_kbs = _normalize_extra_kbs(manifest.get("extra_knowledge_bases"))
    native_rag_present = (path / "rag").is_dir() and any((path / "rag").iterdir())
    dto = {
        "name": manifest.get("name") or path.name,
        "handbag_name": path.name,
        "scope": scope,
        "owner": owner,
        "description": manifest.get("description", ""),
        "author": manifest.get("author", ""),
        "category": manifest.get("category", ""),
        "version": str(manifest.get("version")) if manifest.get("version") is not None else None,
        "icon": icon_data,
        "icon_base64": icon_data,  # alias: consumers still binding this legacy field get the icon too
        "has_soul": (path / "SOUL.md").is_file(),
        "has_tools": any((path / "tools").glob("*.py")) if (path / "tools").is_dir() else False,
        # ``has_rag`` now reflects extra knowledge bases too: a handbag with a
        # linked SafeStore ``.db`` but no local ``rag/`` folder still exposes
        # RAG capability at runtime, so the header badge must match reality.
        "has_rag": native_rag_present or bool(extra_kbs),
        "has_extra_kbs": bool(extra_kbs),
        "extra_knowledge_bases": extra_kbs,
        "has_docs": (path / "docs").is_dir() and any((path / "docs").iterdir()),
        "has_skills": (path / "skills").is_dir() and any((path / "skills").iterdir()),
    }
    return dto


def discover_global_handbags() -> List[Dict[str, Any]]:
    # The mandatory 'lollms' persona is self-healing: this call (re)creates
    # its folder whenever it is missing, so the global catalog is never empty
    # on a running instance — regardless of whether the one-time startup
    # bootstrap reached that step.
    ensure_default_lollms_handbag()
    root = global_personalities_root()
    if not root.is_dir():
        return []
    out = []
    for child in sorted(root.iterdir()):
        dto = _scan_handbag(child, "global", None)
        if dto:
            out.append(dto)
    return out


def discover_personal_handbags(username: str, owner_name: Optional[str] = None,
                               scope: str = "personal") -> List[Dict[str, Any]]:
    username = str(username)
    root = user_personalities_root(username)
    if not root.is_dir():
        return []
    out = []
    for child in sorted(root.iterdir()):
        dto = _scan_handbag(child, scope, owner_name or username)
        if dto:
            out.append(dto)
    return out


def discover_catalog(db, user) -> Dict[str, List[Dict[str, Any]]]:
    """Full catalog for the global header: global / personal / shared scopes.

    ``db`` is a SQLAlchemy session; ``user`` is the DBUser row. Shared scope is
    the union of handbags shared with the caller via PersonalityShareLink
    (groups or friends).
    """
    # Scopes are collected independently so a failure in one scope never
    # blanks the others. A bad username blocking personal discovery must not
    # hide the global catalog, and vice versa.
    try:
        global_bags = discover_global_handbags()
    except Exception as exc:
        ASCIIColors.warning(f"[personalities] global discovery failed: {exc}")
        global_bags = []

    personal_username = getattr(user, "username", None)
    if not personal_username:
        ASCIIColors.warning(
            "[personalities] discover_catalog: user has no username; "
            "personal scope skipped. The caller must pass a DBUser row "
            "or an auth object that carries the username claim.")
        personal_bags = []
    else:
        try:
            personal_bags = [
                {**dto, "owner_id": user.id}
                for dto in discover_personal_handbags(
                    personal_username, personal_username, "personal")
            ]
        except Exception as exc:
            ASCIIColors.warning(
                f"[personalities] personal discovery failed: {exc}")
            personal_bags = []

    catalog = {
        "global": global_bags,
        "personal": personal_bags,
        "shared": [],
    }
    try:
        from backend.db.models.personality_share import PersonalityShareLink
        # Reference the canonical ORM column, never ``type(user).id``: the
        # latter is a plain Python attribute lookup and raises AttributeError
        # for any non-SQLAlchemy user stub (tests, mocks, SimpleNamespace).
        from backend.db.models.user import User as DBUser

        links = db.query(PersonalityShareLink).filter(
            (PersonalityShareLink.shared_with_user_id == user.id)
            | (PersonalityShareLink.group_id.in_(
                [m.group_id for m in getattr(user, "group_memberships", [])]
            ))
        ).all() if hasattr(user, "group_memberships") else db.query(
            PersonalityShareLink
        ).filter(PersonalityShareLink.shared_with_user_id == user.id).all()

        seen = set()
        for link in links:
            owner = db.query(DBUser).filter(DBUser.id == link.owner_user_id).first()
            if not owner:
                continue
            key = (link.owner_user_id, link.handbag_name)
            if key in seen:
                continue
            seen.add(key)
            path = _safe_resolve(user_personalities_root(owner.username), link.handbag_name)
            dto = _scan_handbag(path, "shared", owner.username)
            if dto:
                dto["owner_id"] = link.owner_user_id
                catalog["shared"].append(dto)
    except Exception as exc:
        ASCIIColors.warning(f"[personalities] shared discovery failed: {exc}")
    return catalog


# ---------------------------------------------------------------------------
# Handbag file helpers (studio CRUD + legacy materialization)
# ---------------------------------------------------------------------------

def slugify_handbag_name(name: str) -> str:
    """Filesystem-safe handbag folder name derived from a display name."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", (name or "").strip())[:64] or "personality"


def _load_manifest(path: Path) -> Dict[str, Any]:
    manifest_file = path / "handbag.yaml"
    if not manifest_file.is_file() or yaml is None:
        return {}
    try:
        manifest = yaml.safe_load(manifest_file.read_text(encoding="utf-8")) or {}
        return manifest if isinstance(manifest, dict) else {}
    except Exception:
        return {}


def _normalize_extra_kbs(raw: Any) -> List[str]:
    """Normalize a handbag manifest's ``extra_knowledge_bases`` into a flat list.

    Accepts a single string / Path-like, or a mixed list of them (this mirrors
    the shape that ``Handbag.normalize_extra_knowledge_bases(...)`` accepts in
    ``lollms_client``). Entries are stripped, de-duplicated, and returned in
    declaration order. Empty/invalid entries are dropped.

    Existence is **intentionally not checked here**: the ``lollms_client``
    ``Handbag`` loader skips non-existent entries with a warning (extra KBs
    are optional by design), and the studio editor should be able to display
    an entry the user is about to fix instead of having it silently vanish.
    """
    if raw is None:
        return []
    if isinstance(raw, (str, os.PathLike)):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return []
    out: List[str] = []
    seen = set()
    for entry in raw:
        if not isinstance(entry, (str, os.PathLike)):
            continue
        text = str(entry).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def read_handbag_detail(path: Path) -> Dict[str, Any]:
    """Full handbag content for the studio editor (manifest + SOUL prompt)."""
    if not path.is_dir():
        raise ValueError(f"Not a handbag folder: {path}")
    manifest = _load_manifest(path)
    soul_file = path / "SOUL.md"
    icon_data = _read_handbag_icon(path)
    extra_kbs = _normalize_extra_kbs(manifest.get("extra_knowledge_bases"))

    # Scan directories
    skills = []
    if (path / "skills").is_dir():
        for s in sorted((path / "skills").iterdir()):
            if s.name.startswith("."): continue
            skills.append(s.name)
            
    tools = []
    if (path / "tools").is_dir():
        for t in sorted((path / "tools").glob("*.py")):
            if t.is_file() and not t.name.startswith("."):
                tools.append(t.name)
                
    databases = []
    if (path / "rag").is_dir():
        for r in sorted((path / "rag").iterdir()):
            if not r.name.startswith("."):
                databases.append(r.name)

    return {
        "name": manifest.get("name") or path.name,
        "handbag_name": path.name,
        "description": manifest.get("description", ""),
        "author": manifest.get("author", ""),
        "category": manifest.get("category", ""),
        "version": str(manifest.get("version")) if manifest.get("version") is not None else None,
        "icon": icon_data,
        "icon_base64": icon_data,
        "prompt_text": soul_file.read_text(encoding="utf-8") if soul_file.is_file() else "",
        "has_soul": soul_file.is_file(),
        "has_tools": len(tools) > 0,
        # Mirror ``_scan_handbag``: extra KBs (SafeStore .db files, docs, or
        # folders) count as RAG capability even when there is no local
        # ``rag/`` folder. Without this, the studio editor would show "No
        # RAG" for a handbag that already links a live datastore at runtime.
        "has_rag": len(databases) > 0 or bool(extra_kbs),
        "has_docs": (path / "docs").is_dir() and any((path / "docs").iterdir()),
        "has_skills": len(skills) > 0,
        "skills": skills,
        "tools": tools,
        "databases": databases,
        # Extra RAG sources declared in handbag.yaml — files (.db SafeStore
        # databases, plain docs, ...) or folders. These are merged with the
        # handbag's native ``rag/`` + ``docs/`` sources by
        # ``LollmsPersonality.from_handbag()`` and are exposed to
        # ``tool_query_rag`` transparently.
        "extra_knowledge_bases": extra_kbs,
        "has_extra_kbs": bool(extra_kbs),
    }


def write_handbag_files(path: Path, *, display_name: Optional[str] = None,
                        description: Optional[str] = None, author: Optional[str] = None,
                        category: Optional[str] = None,
                        prompt_text: Optional[str] = None,
                        icon_base64: Optional[str] = None,
                        extra_knowledge_bases: Optional[List[Any]] = None) -> None:
    """Update handbag metadata (handbag.yaml), SOUL.md, and/or icon in place.

    ``icon_base64`` accepts either a data URI (``data:image/png;base64,...``)
    or a raw base64 payload; the decoded bytes are written to ``icon.png`` so
    the icon travels with the handbag folder and is picked up by
    ``_read_handbag_icon`` on the next catalog scan.

    ``extra_knowledge_bases`` accepts the same shapes the ``lollms_client``
    ``Handbag`` accepts at load time (a single string/Path or a mixed list of
    them). When provided, the normalized list is written to ``handbag.yaml``
    so ``LollmsPersonality.from_handbag()`` wires those sources into the
    personality's RAG pipeline on the next load — no manual per-personality
    RAG bookkeeping needed. Passing ``[]`` removes the key entirely.
    """
    if not path.is_dir():
        raise ValueError(f"Not a handbag folder: {path}")
    manifest = _load_manifest(path)
    for key, value in (("name", display_name), ("description", description),
                       ("author", author), ("category", category)):
        if value is not None:
            manifest[key] = value
    if extra_knowledge_bases is not None:
        normalized = _normalize_extra_kbs(extra_knowledge_bases)
        if normalized:
            manifest["extra_knowledge_bases"] = normalized
        else:
            manifest.pop("extra_knowledge_bases", None)
    if yaml is not None:
        (path / "handbag.yaml").write_text(
            yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
    if prompt_text is not None:
        (path / "SOUL.md").write_text(prompt_text or f"# {manifest.get('name', path.name)}\n",
                                      encoding="utf-8")
    if icon_base64:
        try:
            import base64 as _b64
            payload = icon_base64.split(",", 1)[-1] \
                if icon_base64.startswith("data:") else icon_base64
            (path / "icon.png").write_bytes(_b64.b64decode(payload))
        except Exception as exc:
            ASCIIColors.warning(f"[personalities] cannot write icon for {path}: {exc}")


def write_handbag_skill(path: Path, skill_name: str, content: str) -> Path:
    """Write a skill to the handbag's skills/ directory."""
    if not path.is_dir():
        raise ValueError(f"Not a handbag folder: {path}")
    skills_dir = path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", skill_name)
    if not safe_name.endswith(".md"):
        safe_name += ".md"
    target = skills_dir / safe_name
    target.write_text(content, encoding="utf-8")
    return target


def write_handbag_tool(path: Path, filename: str, content: str) -> Path:
    """Write an LCP tool to the handbag's tools/ directory."""
    if not path.is_dir():
        raise ValueError(f"Not a handbag folder: {path}")
    tools_dir = path / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", filename)
    if not safe_name.endswith(".py"):
        safe_name += ".py"
    target = tools_dir / safe_name
    target.write_text(content, encoding="utf-8")
    return target


def copy_skill_from_library(path: Path, skill_name: str, library_root: Path) -> Path:
    """Copy a skill from the global library to the handbag."""
    if not path.is_dir():
        raise ValueError(f"Not a handbag folder: {path}")
    source = library_root / skill_name
    if not source.exists():
        source = library_root / f"{skill_name}.md"
    if not source.exists():
        raise ValueError(f"Skill not found in library: {skill_name}")
    skills_dir = path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    target = skills_dir / source.name
    if source.is_dir():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)
    return target


def export_skill_to_library(path: Path, skill_name: str, library_root: Path) -> Path:
    """Export a skill from the handbag to the global library."""
    if not path.is_dir():
        raise ValueError(f"Not a handbag folder: {path}")
    source_dir = path / "skills"
    source = source_dir / skill_name
    if not source.exists():
        source = source_dir / f"{skill_name}.md"
    if not source.exists():
        raise ValueError(f"Skill not found in handbag: {skill_name}")
    library_root.mkdir(parents=True, exist_ok=True)
    target = library_root / source.name
    if source.is_dir():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)
    return target


def delete_handbag(root: Path, name: str) -> None:
    """Delete a handbag folder from a root (traversal-safe)."""
    path = _safe_resolve(root, name)
    if not path.is_dir():
        raise ValueError(f"Handbag not found: {name!r}")
    shutil.rmtree(path)


# ---------------------------------------------------------------------------
# Legacy DB personality -> handbag materialization
# ---------------------------------------------------------------------------

def materialize_legacy_handbag(name: str, prompt_text: Optional[str],
                               description: Optional[str], author: Optional[str],
                               category: Optional[str], root: Path) -> Optional[Path]:
    """Write a minimal handbag (handbag.yaml + SOUL.md) for a legacy DB row.

    Idempotent: an existing folder with the same slug is left untouched.
    Atomic: staged in a temp dir and renamed into place.
    """
    slug = slugify_handbag_name(name)
    root.mkdir(parents=True, exist_ok=True)
    try:
        final_path = _safe_resolve(root, slug)
    except ValueError as exc:
        ASCIIColors.warning(f"[personalities] legacy import rejected name {name!r}: {exc}")
        return None
    if final_path.exists():
        return final_path
    staging = Path(tempfile.mkdtemp(prefix="legacy_stage_", dir=str(root)))
    try:
        staged = staging / slug
        staged.mkdir()
        if yaml is not None:
            manifest = {"name": (name or slug).strip()}
            if description:
                manifest["description"] = description
            if author:
                manifest["author"] = author
            if category:
                manifest["category"] = category
            (staged / "handbag.yaml").write_text(
                yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
        (staged / "SOUL.md").write_text(prompt_text or f"# {name or slug}\n",
                                        encoding="utf-8")
        try:
            os.replace(staged, final_path)
        except OSError:
            # Windows: os.replace on directories is unreliable; copy + cleanup.
            shutil.copytree(staged, final_path)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return final_path


# ---------------------------------------------------------------------------
# One-shot migration: DB personalities -> handbag folders on disk
# ---------------------------------------------------------------------------

def migrate_db_personalities_to_handbags(db) -> int:
    """Materialize every legacy DB personality as a handbag folder, point user
    preferences at the new folder names, then delete the legacy DB rows.

    One-shot per process (``_db_personalities_migrated``): a clean run ends
    with no DBPersonality rows, so subsequent calls are a no-op. Returns the
    count of migrated rows. Rolls back on failure to avoid half-migrated state.
    """
    global _db_personalities_migrated, _discussion_fk_cleanup_attempted
    if _db_personalities_migrated:
        return 0

    from backend.db.models.personality import Personality as DBPersonality
    from backend.db.models.user import User as DBUser
    from backend.db.models.personality_share import UserPersonalityPreference

    # ALWAYS ensure handbag roots exist, even when there is nothing to migrate.
    # Without this, an empty DB (or one already migrated, or one where the
    # query errors out) leaves data/personalities/ missing entirely.
    try:
        ensure_personality_roots()
    except Exception as roots_exc:
        ASCIIColors.warning(
            f"[personalities] cannot prepare handbag roots: {roots_exc}")
        return 0

    try:
        rows = db.query(DBPersonality).all()
    except Exception as exc:
        ASCIIColors.warning(f"[personalities] migration skipped (table unavailable): {exc}")
        return 0
    if not rows:
        _db_personalities_migrated = True
        return 0

    id_to_ref: Dict[Any, Tuple[str, str]] = {}
    migrated = 0
    successfully_materialized: set = set()
    for pers in rows:
        try:
            is_global = bool(getattr(pers, "is_public", False)) \
                or getattr(pers, "owner_user_id", None) is None
            if is_global:
                root = global_personalities_root()
            else:
                owner = db.query(DBUser).filter(
                    DBUser.id == pers.owner_user_id).first()
                if owner is None:
                    ASCIIColors.warning(
                        f"[personalities] migration row {pers.id}: "
                        f"owner {pers.owner_user_id} not found; skipping.")
                    continue
                root = user_personalities_root(owner.username)
            path = materialize_legacy_handbag(
                name=getattr(pers, "name", None) or f"personality_{pers.id}",
                prompt_text=getattr(pers, "prompt_text", None),
                description=getattr(pers, "description", None),
                author=getattr(pers, "author", None),
                category=getattr(pers, "category", None),
                root=root,
            )
            if path is not None:
                id_to_ref[pers.id] = ("global" if is_global else "personal", path.name)
                successfully_materialized.add(pers.id)
                migrated += 1
        except Exception as row_exc:
            ASCIIColors.warning(
                f"[personalities] migration row {getattr(pers, 'id', '?')} failed: {row_exc}")

    # Clear orphan FK references in tables that may point at DBPersonality.id.
    # Attempted at most once per process: ``backend.db.models.discussion``
    # does not define a ``Discussion`` ORM class, so this can only ever raise
    # ImportError. The one-shot guard keeps that from spamming the log on every
    # catalog request while still allowing a process restart to retry if the
    # schema changes in the future.
    if not _discussion_fk_cleanup_attempted:
        _discussion_fk_cleanup_attempted = True
        try:
            from backend.db.models.discussion import Discussion as _DBDiscussion
            if hasattr(_DBDiscussion, "active_personality_id"):
                db.query(_DBDiscussion).filter(
                    _DBDiscussion.active_personality_id.isnot(None)
                ).update({"active_personality_id": None}, synchronize_session=False)
        except ImportError:
            # No Discussion ORM model in this schema; nothing to clean up.
            pass
        except Exception as fk_exc:
            ASCIIColors.warning(
                f"[personalities] discussion FK cleanup skipped: {fk_exc}")

    # Remap users' active personality to the handbag preference model AND
    # clear the legacy FK on every user whose personality is about to be
    # deleted (prevents FK violations in RDBMSes that enforce them).
    try:
        prefs_users = db.query(DBUser).filter(DBUser.active_personality_id.isnot(None)).all()
        for u in prefs_users:
            ref = id_to_ref.get(u.active_personality_id)
            if ref is not None:
                scope, slug = ref
                existing = db.query(UserPersonalityPreference).filter(
                    UserPersonalityPreference.user_id == u.id).first()
                if existing is None:
                    db.add(UserPersonalityPreference(
                        user_id=u.id, scope=scope, handbag_name=slug, owner_id=None))
            u.active_personality_id = None
    except Exception as pref_exc:
        ASCIIColors.warning(f"[personalities] preference remap failed: {pref_exc}")

    for pers in rows:
        # Only delete rows whose handbag folder was successfully written to
        # disk. The previous behaviour deleted every row unconditionally,
        # which silently destroyed any personality whose materialisation
        # failed (path traversal rejection, disk full, permission error...).
        # Failed rows are preserved here and retried on the next startup.
        if pers.id in successfully_materialized:
            db.delete(pers)
        else:
            ASCIIColors.warning(
                f"[personalities] preserving DB row {pers.id} "
                f"({getattr(pers, 'name', '?')}): handbag materialisation "
                "failed; will retry on next startup.")
    try:
        db.commit()
    except Exception as commit_exc:
        db.rollback()
        ASCIIColors.warning(
            f"[personalities] migration commit failed ({commit_exc}); "
            "handbag folders were created but DB rows are still present — "
            "the migration will retry on next startup.")
        return migrated
    _db_personalities_migrated = True
    ASCIIColors.info(f"[personalities] migrated {migrated} DB personalities to handbags")
    return migrated


# ---------------------------------------------------------------------------
# One-shot migration: legacy per-user folder -> user data root
# ---------------------------------------------------------------------------

def migrate_legacy_user_personality_folders(db) -> int:
    """Move handbags from ``personalities/users/<id>/`` into each user's
    standard data folder (``<user_data_root>/personalities/``).

    Idempotent: existing target folders are left untouched (per-handbag
    conflicts are logged and the legacy copy is preserved), and the top-level
    legacy directory can be safely removed once it goes empty.

    Returns the number of user accounts whose folders were migrated.
    """
    from backend.db.models.user import User as DBUser

    legacy_root = _data_root() / "personalities" / "users"
    if not legacy_root.is_dir():
        return 0
    try:
        users = db.query(DBUser).all()
    except Exception as exc:
        ASCIIColors.warning(
            f"[personalities] legacy user-folder migration skipped "
            f"(cannot list users): {exc}")
        return 0
    migrated = 0
    for user in users:
        legacy_user_dir = legacy_root / str(user.id)
        if not legacy_user_dir.is_dir():
            continue
        try:
            has_content = any(legacy_user_dir.iterdir())
        except OSError as exc:
            ASCIIColors.warning(
                f"[personalities] legacy folder {legacy_user_dir} unreadable: {exc}")
            continue
        if not has_content:
            try:
                legacy_user_dir.rmdir()
            except OSError:
                pass
            continue
        target_root = user_personalities_root(user.username)
        try:
            target_root.mkdir(parents=True, exist_ok=True)
            for child in list(legacy_user_dir.iterdir()):
                target_child = target_root / child.name
                if target_child.exists():
                    ASCIIColors.warning(
                        f"[personalities] legacy handbag {child} already "
                        f"exists at {target_child}; leaving legacy copy in place.")
                    continue
                shutil.move(str(child), str(target_child))
            try:
                legacy_user_dir.rmdir()
            except OSError:
                pass
            migrated += 1
        except Exception as exc:
            ASCIIColors.warning(
                f"[personalities] legacy migration failed for user "
                f"{user.username} (id={user.id}): {exc}")
    if migrated:
        ASCIIColors.info(
            f"[personalities] moved {migrated} users' handbags into their "
            f"user data folders")
    return migrated


# ---------------------------------------------------------------------------
# Runtime resolution + loading
# ---------------------------------------------------------------------------

def resolve_handbag_path(scope: str, handbag_name: str, user,
                         owner_id: Optional[Any] = None, db=None) -> Optional[Path]:
    """Map (scope, name, owner) to an absolute handbag path with ACL enforcement.

    Returns None when the reference is invalid or access is denied (caller
    falls back to a safe default / NullPersonality).
    """
    try:
        if scope == "global":
            path = _safe_resolve(global_personalities_root(), handbag_name)
        elif scope == "personal":
            path = _safe_resolve(user_personalities_root(user.username), handbag_name)
        elif scope == "shared":
            if db is None or owner_id is None:
                return None
            from backend.db.models.personality_share import PersonalityShareLink
            allowed = db.query(PersonalityShareLink).filter(
                PersonalityShareLink.owner_user_id == owner_id,
                PersonalityShareLink.handbag_name == handbag_name,
                PersonalityShareLink.shared_with_user_id == user.id,
            ).first()
            if not allowed:
                ASCIIColors.warning(
                    f"[personalities] access denied: user {user.id} -> shared "
                    f"handbag {handbag_name} of owner {owner_id}"
                )
                return None
            # Same reasoning as ``discover_catalog``: never touch
            # ``type(user).id``, which is not guaranteed on non-ORM user objects.
            from backend.db.models.user import User as DBUser
            owner = db.query(DBUser).filter(DBUser.id == owner_id).first()
            if owner is None:
                ASCIIColors.warning(
                    f"[personalities] shared handbag {handbag_name}: "
                    f"owner {owner_id} not found.")
                return None
            path = _safe_resolve(user_personalities_root(owner.username), handbag_name)
        else:
            return None
        return path if path.is_dir() else None
    except (ValueError, AttributeError) as exc:
        ASCIIColors.warning(f"[personalities] {exc}")
        return None


def load_personality_from_handbag(path: Path):
    """Build the runtime brain; returns None on any failure (graceful)."""
    try:
        from lollms_client.lollms_personality import LollmsPersonality
        return LollmsPersonality.from_handbag(str(path))
    except Exception as exc:
        ASCIIColors.error(f"[personalities] failed to load handbag {path}: {exc}")
        return None


def get_active_personality(user, db=None):
    """Resolve the user's preferred personality and hand it to the chat loop.

    Preference source: ``UserPersonalityPreference`` (scope, handbag_name,
    owner_id). Behavior is intentionally *loud* about drift:

    * Preference exists and resolves -> return that handbag. No fallback.
    * Preference exists but cannot resolve (handbag deleted, scope/owner
      mismatch, share revoked) -> log the exact stored reference and return
      ``None`` so the caller surfaces the drift. Never silently substitute
      "first in catalog" (that masked the original revert bug).
    * No preference at all -> fall back to ``personal[0]`` -> ``global[0]``
      -> ``None`` (chat loop uses its NullPersonality contract).

    Also hardened against two caller-side wiring bugs:

    * ``db`` is ``None`` (route forgot to pass a session) -> we cannot read
      ``UserPersonalityPreference``, so we warn loudly and fall through to
      first-in-catalog instead of pretending nothing is wrong.
    * ``user.id`` does not match the DB row id (a ``UserAuthDetails`` was
      passed in) -> we retry the lookup via ``user.username``.
    """
    ref: Optional[Tuple[str, str, Optional[Any]]] = None
    pref_found = False

    if db is None:
        ASCIIColors.warning(
            f"[personalities] get_active_personality called without a DB "
            f"session for user {getattr(user, 'username', '?')!r} "
            f"(id={getattr(user, 'id', '?')!r}); UserPersonalityPreference "
            f"cannot be read, so the fallback will pick the first catalog "
            f"handbag. This is a call-site bug — pass `db`."
        )
    else:
        try:
            from backend.db.models.personality_share import UserPersonalityPreference
            pref = db.query(UserPersonalityPreference).filter(
                UserPersonalityPreference.user_id == user.id
            ).first()

            # Safety net for UserAuthDetails callers whose ``id`` may not
            # match the DB row id (or may be None, or may point at the wrong
            # row). Whenever the direct ``user.id`` lookup misses, retry by
            # ``user.username`` — the username is the canonical identity
            # that survives auth-layer drift. We do NOT gate this on
            # ``db_user.id != user.id`` because that check skips the retry
            # in the exact case we need it (either side is None, or one side
            # has drifted to an unrelated row), leaving the real preference
            # stranded and silently falling back to ``personal[0]`` — the
            # original "reverts to first in list" bug.
            if pref is None and getattr(user, "username", None):
                from backend.db.models.user import User as DBUser
                db_user = db.query(DBUser).filter(
                    DBUser.username == user.username).first()
                if db_user is not None:
                    pref = db.query(UserPersonalityPreference).filter(
                        UserPersonalityPreference.user_id == db_user.id).first()
                    if pref is not None:
                        ASCIIColors.info(
                            f"[personalities] preference recovered by "
                            f"username for {user.username!r} "
                            f"(auth-id={getattr(user, 'id', '?')!r} "
                            f"!= db-id={db_user.id!r}) — the caller passed "
                            f"a UserAuthDetails whose id does not match "
                            f"the DB row.")

            if pref is not None:
                ref = (pref.scope, pref.handbag_name, pref.owner_id)
                pref_found = True
        except Exception as exc:
            # Silence here used to manifest as "reverts to first in list":
            # the query raised (table missing, session closed, ...) and we
            # fell through to personal[0]/global[0].
            trace_exception(exc)
            ASCIIColors.warning(
                f"[personalities] preference lookup failed for user "
                f"{getattr(user, 'id', '?')!r}: {exc}"
            )

    if ref is None:
        username = getattr(user, "username", None)
        try:
            personal = discover_personal_handbags(username, username) if username else []
        except Exception as exc:
            ASCIIColors.warning(
                f"[personalities] personal discovery failed while picking "
                f"a default personality: {exc}"
            )
            personal = []
        if personal:
            ref = ("personal", personal[0]["handbag_name"], None)
        else:
            try:
                glob = discover_global_handbags()
            except Exception as exc:
                ASCIIColors.warning(
                    f"[personalities] global discovery failed while picking "
                    f"a default personality: {exc}"
                )
                glob = []
            if glob:
                ref = ("global", glob[0]["handbag_name"], None)

    if ref is None:
        return None

    scope, name, owner_id = ref
    path = resolve_handbag_path(scope, name, user, owner_id=owner_id, db=db)
    if path is None:
        if pref_found:
            ASCIIColors.warning(
                f"[personalities] stored preference {scope}/{name} "
                f"(owner_id={owner_id!r}) for user "
                f"{getattr(user, 'id', '?')!r} cannot be resolved — the "
                f"handbag folder is missing or access was revoked. "
                f"Returning None; the user must re-select a personality."
            )
        else:
            ASCIIColors.warning(
                f"[personalities] default handbag {scope}/{name} could not "
                f"be resolved for user {getattr(user, 'id', '?')!r}."
            )
        return None
    return load_personality_from_handbag(path)


# ---------------------------------------------------------------------------
# Atomic install (zip / folder copy via staging + rename)
# ---------------------------------------------------------------------------

def install_handbag_from_folder(source: Path, target_root: Path,
                                handbag_name: Optional[str] = None) -> Path:
    """Atomically copy a handbag folder into a root via staging + rename."""
    source = Path(source).resolve()
    if not source.is_dir():
        raise ValueError(f"Not a handbag folder: {source}")
    target_root.mkdir(parents=True, exist_ok=True)
    name = handbag_name or source.name
    final_path = _safe_resolve(target_root, name)
    staging = Path(tempfile.mkdtemp(prefix="handbag_stage_", dir=str(target_root)))
    staged = staging / name
    try:
        shutil.copytree(source, staged)
        if final_path.exists():
            shutil.rmtree(final_path)
        os.replace(staged, final_path)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return final_path


def install_handbag_from_zip(zip_path: Path, target_root: Path,
                             handbag_name: Optional[str] = None) -> Path:
    """Extract a zipped handbag into staging, then atomically rename.

    Zip-slip safe: every member is validated against the staging dir.
    """
    import zipfile

    target_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="handbag_zip_", dir=str(target_root)))
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.namelist():
                dest = (staging / member).resolve()
                if staging.resolve() not in dest.parents and dest != staging.resolve():
                    raise ValueError(f"Zip traversal rejected: {member!r}")
            zf.extractall(staging)
        # If the zip wraps a single top-level folder, use it as the handbag root
        children = [c for c in staging.iterdir() if c.is_dir()]
        root = children[0] if len(children) == 1 and not any(
            c.is_file() for c in staging.iterdir()
        ) else staging
        name = handbag_name or Path(root).name
        final_path = _safe_resolve(target_root, name)
        if final_path.exists():
            shutil.rmtree(final_path)
        if root != staging:
            os.replace(root, final_path)
        else:
            # flat zip: move contents out of staging, then staging is cleaned in finally
            final_path.mkdir(parents=True, exist_ok=True)
            for item in list(staging.iterdir()):
                shutil.move(str(item), str(final_path / item.name))
        return final_path
    finally:
        shutil.rmtree(staging, ignore_errors=True)