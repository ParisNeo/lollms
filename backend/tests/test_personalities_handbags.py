"""Unit tests for the filesystem-backed personalities (handbag) subsystem.

Covers the pure/logic layer of ``backend/personalities.py`` and the declarative
model contracts of ``backend/db/models/personality_share.py``. No real DB, no
TestClient, no router imports; ``lollms_client`` is stubbed via sys.modules.
All filesystem work is redirected to ``tmp_path`` via ``LOLLMS_DATA_PATH``.
"""

import io
import os
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


# ---------------------------------------------------------------------------
# Test-environment shim: ``backend.db.models.*`` transitively imports
# ``backend.security``, which requires ``python-jose`` at *import time* for
# the JWT helpers (``jwt``/``JWTError``). Production always installs it, but
# stripped CI / dev environments frequently don't — which is exactly the
# situation the tests are meant to tolerate ("no real DB, no TestClient, no
# router imports"). We stub only what ``backend.security`` imports; real
# installs keep their working implementation because the try succeeds first.
# ---------------------------------------------------------------------------
try:                                                       # pragma: no cover
    import jose as _jose_real  # noqa: F401
except ImportError:                                        # pragma: no cover
    import types as _types
    _jose_mod = _types.ModuleType("jose")
    _jose_mod.JWTError = type("JWTError", (Exception,), {})
    _jwt_mod = _types.ModuleType("jose.jwt")
    _jwt_mod.encode = lambda *a, **k: ""
    _jwt_mod.decode = lambda *a, **k: {}
    _jose_mod.jwt = _jwt_mod
    sys.modules["jose"] = _jose_mod
    sys.modules["jose.jwt"] = _jwt_mod

# Same story for ``passlib``: ``backend.security`` instantiates
# ``CryptContext(schemes=["bcrypt"], deprecated="auto")`` at import time.
# Tests never hash passwords, so a no-op context is sufficient. Real installs
# short-circuit (the ``try`` succeeds) and keep the production implementation.
try:                                                       # pragma: no cover
    import passlib as _passlib_real  # noqa: F401
except ImportError:                                        # pragma: no cover
    import types as _types_pl
    _pl_context_mod = _types_pl.ModuleType("passlib.context")

    class _FakeCryptContext:
        def __init__(self, *a, **k):
            pass
        def hash(self, secret, **kw):
            return f"fakehash${secret}"
        def verify(self, secret, hashed, **kw):
            return True
        def needs_update(self, hashed):
            return False

    _pl_context_mod.CryptContext = _FakeCryptContext
    _pl_mod = _types_pl.ModuleType("passlib")
    _pl_mod.context = _pl_context_mod
    sys.modules["passlib"] = _pl_mod
    sys.modules["passlib.context"] = _pl_context_mod

# And finally ``toml``: ``backend.config`` does ``import toml`` unconditionally
# (line 8) because it needs to parse ``config.toml`` at import time. Python
# 3.11+ ships ``tomllib`` in the stdlib, so instead of a dead stub we back the
# fake module with a real parser — ``backend.config`` gets working TOML
# reading even in stripped environments, not just an empty dict.
try:                                                       # pragma: no cover
    import toml as _toml_real  # noqa: F401
except ImportError:                                        # pragma: no cover
    import types as _types_toml
    import tomllib as _tomllib

    def _toml_load(source):
        if hasattr(source, "read"):
            data = source.read()
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            return _tomllib.loads(data)
        with open(source, "rb") as fh:
            return _tomllib.load(fh)

    def _toml_loads(text):
        return _tomllib.loads(text)

    def _toml_dumps(obj):
        # stdlib tomllib has no writer; return a stable repr so callers that
        # only need *something* don't explode. Real writes never happen in
        # the test paths exercised here (backend.config only reads).
        return repr(obj)

    def _toml_dump(obj, f=None, **_kw):
        text = _toml_dumps(obj)
        if f is not None and hasattr(f, "write"):
            f.write(text)
            return None
        return text

    _toml_mod = _types_toml.ModuleType("toml")
    _toml_mod.load = _toml_load
    _toml_mod.loads = _toml_loads
    _toml_mod.dump = _toml_dump
    _toml_mod.dumps = _toml_dumps
    _toml_mod.TomlDecodeError = _tomllib.TOMLDecodeError
    sys.modules["toml"] = _toml_mod


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def personalities_env(tmp_path, monkeypatch):
    """Redirect the personalities data root to tmp_path and return the module."""
    monkeypatch.setenv("LOLLMS_DATA_PATH", str(tmp_path / "data"))
    from backend import personalities as p
    return p


def make_handbag(root: Path, name: str, manifest: str = None,
                 soul: bool = False, tools: bool = False,
                 rag: bool = False, docs: bool = False,
                 skills: bool = False) -> Path:
    hb = root / name
    hb.mkdir(parents=True)
    if manifest is not None:
        (hb / "handbag.yaml").write_text(manifest, encoding="utf-8")
    if soul:
        (hb / "SOUL.md").write_text("# Soul\n", encoding="utf-8")
    if tools:
        (hb / "tools").mkdir()
        (hb / "tools" / "my_tool.py").write_text("def tool_x(): ...")
    if rag:
        (hb / "rag").mkdir()
        (hb / "rag" / "notes.md").write_text("# notes")
    if docs:
        (hb / "docs").mkdir()
        (hb / "docs" / "doc.md").write_text("# docs")
    if skills:
        (hb / "skills").mkdir()
        (hb / "skills" / "SKILL.md").write_text("# skill")
    return hb


def _stub_lollms_personality(monkeypatch, result=None, exc=None):
    """Inject a stub lollms_client.lollms_personality module."""
    stub = SimpleNamespace()
    if exc is not None:
        stub.LollmsPersonality = SimpleNamespace(
            from_handbag=staticmethod(lambda p: (_ for _ in ()).throw(exc)))
    else:
        captured = {}
        def _from_handbag(path):
            captured["path"] = path
            return result
        stub.LollmsPersonality = SimpleNamespace(
            from_handbag=staticmethod(_from_handbag))
        stub.captured = captured
    monkeypatch.setitem(sys.modules, "lollms_client", MagicMock())
    monkeypatch.setitem(sys.modules, "lollms_client.lollms_personality", stub)
    return stub


# ---------------------------------------------------------------------------
# 1. Roots
# ---------------------------------------------------------------------------

class TestRoots:
    def test_data_root_env_override(self, personalities_env, tmp_path):
        assert personalities_env._data_root() == (tmp_path / "data").resolve()

    def test_data_root_default_when_env_missing(self, monkeypatch):
        monkeypatch.delenv("LOLLMS_DATA_PATH", raising=False)
        from backend import personalities as p
        assert p._data_root() == Path("data").resolve()

    def test_global_and_user_roots_paths(self, personalities_env, tmp_path):
        base = (tmp_path / "data").resolve() / "personalities"
        assert personalities_env.global_personalities_root() == base / "global"
        # Per-user handbags now live inside the user's standard data folder.
        user_root = (tmp_path / "data" / "users" / "alice" / "personalities").resolve()
        assert personalities_env.user_personalities_root("alice") == user_root

    def test_ensure_roots_creates_dirs(self, personalities_env):
        personalities_env.ensure_personality_roots()
        assert personalities_env.global_personalities_root().is_dir()
        # Per-user roots are created lazily now, not eagerly under data/personalities.
        assert not (personalities_env._data_root() / "personalities" / "users").exists()

    def test_ensure_roots_raises_on_unwritable(self, personalities_env, monkeypatch):
        def boom(self, *a, **k):
            raise OSError("read-only")
        monkeypatch.setattr(Path, "write_text", boom)
        with pytest.raises(RuntimeError):
            personalities_env.ensure_personality_roots()


# ---------------------------------------------------------------------------
# 2. Path safety
# ---------------------------------------------------------------------------

class TestSafeResolve:
    def test_happy_path(self, personalities_env, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        result = personalities_env._safe_resolve(root, "agent")
        assert result == (root / "agent").resolve()

    @pytest.mark.parametrize("bad", ["../evil", "..", "a/b", "a\\b",
                                     "sub/../evil", "", ".hidden", "."])
    def test_rejected_names(self, personalities_env, tmp_path, bad):
        root = tmp_path / "root"
        root.mkdir()
        with pytest.raises(ValueError):
            personalities_env._safe_resolve(root, bad)


# ---------------------------------------------------------------------------
# 3. Manifest scanning
# ---------------------------------------------------------------------------

class TestScanHandbag:
    def test_non_dir_returns_none(self, personalities_env, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        assert personalities_env._scan_handbag(f, "global", None) is None

    def test_minimal_dir_defaults(self, personalities_env, tmp_path):
        hb = make_handbag(tmp_path, "agent_one")
        dto = personalities_env._scan_handbag(hb, "global", None)
        assert dto["name"] == "agent_one"          # folder fallback
        assert dto["handbag_name"] == "agent_one"
        assert dto["scope"] == "global"
        assert dto["owner"] is None
        assert dto["description"] == ""
        assert dto["author"] == ""
        assert dto["category"] == ""
        for flag in ("has_soul", "has_tools", "has_rag", "has_docs", "has_skills"):
            assert dto[flag] is False

    def test_manifest_values_flow(self, personalities_env, tmp_path):
        manifest = 'name: Cool Agent\ndescription: says hi\nauthor: Neo\ncategory: Fun\n'
        hb = make_handbag(tmp_path, "agent_two", manifest=manifest)
        dto = personalities_env._scan_handbag(hb, "personal", "alice")
        assert dto["name"] == "Cool Agent"
        assert dto["description"] == "says hi"
        assert dto["author"] == "Neo"
        assert dto["category"] == "Fun"
        assert dto["owner"] == "alice"

    def test_malformed_yaml_yields_defaults(self, personalities_env, tmp_path):
        hb = make_handbag(tmp_path, "agent_bad", manifest=": [broken\n  not yaml: {")
        dto = personalities_env._scan_handbag(hb, "global", None)
        assert dto["name"] == "agent_bad"
        assert dto["description"] == ""

    def test_non_dict_yaml_yields_defaults(self, personalities_env, tmp_path):
        hb = make_handbag(tmp_path, "agent_list", manifest="- just\n- a\n- list\n")
        dto = personalities_env._scan_handbag(hb, "global", None)
        assert dto["name"] == "agent_list"

    def test_yaml_missing_branch(self, personalities_env, tmp_path, monkeypatch):
        hb = make_handbag(tmp_path, "agent_noyaml", manifest="name: Ignored\n")
        monkeypatch.setattr(personalities_env, "yaml", None)
        dto = personalities_env._scan_handbag(hb, "global", None)
        assert dto["name"] == "agent_noyaml"

    def test_capability_flags(self, personalities_env, tmp_path):
        hb = make_handbag(tmp_path, "agent_full", soul=True, tools=True,
                          rag=True, docs=True, skills=True)
        dto = personalities_env._scan_handbag(hb, "global", None)
        assert dto["has_soul"] is True
        assert dto["has_tools"] is True
        assert dto["has_rag"] is True
        assert dto["has_docs"] is True
        assert dto["has_skills"] is True

    def test_has_tools_only_for_py_files(self, personalities_env, tmp_path):
        hb = make_handbag(tmp_path, "agent_txt")
        (hb / "tools").mkdir()
        (hb / "tools" / "readme.txt").write_text("not a tool")
        dto = personalities_env._scan_handbag(hb, "global", None)
        assert dto["has_tools"] is False

    def test_has_rag_requires_non_empty_dir(self, personalities_env, tmp_path):
        hb = tmp_path / "agent_emptyrag"
        (hb / "rag").mkdir(parents=True)
        dto = personalities_env._scan_handbag(hb, "global", None)
        assert dto["has_rag"] is False


# ---------------------------------------------------------------------------
# 4. Discovery listing
# ---------------------------------------------------------------------------

class TestDiscovery:
    def test_global_listing_sorted_and_skips_files(self, personalities_env):
        root = personalities_env.global_personalities_root()
        make_handbag(root, "zeta")
        make_handbag(root, "alpha")
        (root / "stray.txt").write_text("not a dir")
        (root / ".hidden").mkdir()
        names = [d["handbag_name"] for d in personalities_env.discover_global_handbags()]
        # sorted dirs; stray file excluded (non-dir scan returns None)
        assert names == sorted(n for n in names)
        assert "alpha" in names and "zeta" in names
        assert "stray.txt" not in names
        assert all(d["scope"] == "global" for d in personalities_env.discover_global_handbags())

    def test_personal_listing_owner_default(self, personalities_env):
        root = personalities_env.user_personalities_root("7")
        make_handbag(root, "mine")
        out = personalities_env.discover_personal_handbags("7")
        assert len(out) == 1
        assert out[0]["owner"] == "7"
        assert out[0]["scope"] == "personal"

    def test_personal_listing_owner_name_override(self, personalities_env):
        root = personalities_env.user_personalities_root("7")
        make_handbag(root, "mine")
        out = personalities_env.discover_personal_handbags("7", "bob", "shared")
        assert out[0]["owner"] == "bob"
        assert out[0]["scope"] == "shared"

    def test_missing_roots_return_empty(self, personalities_env):
        # Per-user discovery of a non-existent user is empty.
        assert personalities_env.discover_personal_handbags("nobody") == []
        # Global discovery self-heals the mandatory 'lollms' seed, so it is
        # never empty even on a fresh install.
        glob = personalities_env.discover_global_handbags()
        assert [d["handbag_name"] for d in glob] == ["lollms"]


# ---------------------------------------------------------------------------
# 5. Catalog with shared scope
# ---------------------------------------------------------------------------

def _link(owner_id, name, shared_with=None, group=None):
    return SimpleNamespace(owner_user_id=owner_id, handbag_name=name,
                           shared_with_user_id=shared_with, group_id=group)


class TestCatalogShared:
    def _user(self):
        # No group_memberships attribute -> simple query branch
        return SimpleNamespace(id=1, username="alice")

    def _db(self, links, owners):
        """Mock db whose query() dispatches on the model class argument."""
        db = MagicMock()

        class _Q:
            def __init__(self, result): self._result = result
            def filter(self, *a, **k): return self
            def all(self): return list(self._result)
            def first(self):
                return self._result[0] if self._result else None

        def query(model):
            name = getattr(model, "__tablename__", "")
            # model may be a real class or type(user)
            if "personality_share_link" in name or model.__name__ == "PersonalityShareLink" or name == "":
                return _Q(links)
            if model is type(self._user()):
                return _Q(owners)
            # owner lookup: type(db user class match)
            if owners and model is type(owners[0]):
                return _Q(owners)
            return _Q([])
        db.query.side_effect = query
        return db

    def test_shared_entries_with_dedup(self, personalities_env, tmp_path):
        owner_root = personalities_env.user_personalities_root("carol")
        make_handbag(owner_root, "team_agent")
        links = [_link(99, "team_agent", shared_with=1),
                 _link(99, "team_agent", shared_with=1)]  # duplicate row
        owner = SimpleNamespace(id=99, username="carol")

        db = MagicMock()

        class _Q:
            def __init__(self, links, owner): self._links, self._owner = links, owner
            def filter(self, *a, **k): return self
            def all(self): return list(self._links)
            def first(self): return self._owner
        db.query.side_effect = lambda model: _Q(links, owner)

        user = self._user()
        catalog = personalities_env.discover_catalog(db, user)
        assert [d["handbag_name"] for d in catalog["shared"]] == ["team_agent"]
        assert catalog["shared"][0]["scope"] == "shared"
        assert catalog["shared"][0]["owner"] == "carol"

    def test_shared_db_failure_keeps_empty_without_raise(self, personalities_env):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        catalog = personalities_env.discover_catalog(db, self._user())
        assert catalog["shared"] == []   # graceful, no raise


# ---------------------------------------------------------------------------
# 6. Runtime path resolution
# ---------------------------------------------------------------------------

class TestResolveHandbagPath:
    def _user(self, uid=1):
        return SimpleNamespace(id=uid, username="alice")

    def test_global_happy(self, personalities_env):
        make_handbag(personalities_env.global_personalities_root(), "pub")
        p = personalities_env.resolve_handbag_path("global", "pub", self._user())
        assert p is not None and p.name == "pub"

    def test_personal_happy(self, personalities_env):
        make_handbag(personalities_env.user_personalities_root("alice"), "mine")
        p = personalities_env.resolve_handbag_path("personal", "mine", self._user())
        assert p is not None and p.name == "mine"

    def test_nonexistent_returns_none(self, personalities_env):
        personalities_env.ensure_personality_roots()
        assert personalities_env.resolve_handbag_path("global", "nope", self._user()) is None

    def test_invalid_scope_returns_none(self, personalities_env):
        assert personalities_env.resolve_handbag_path("weird", "x", self._user()) is None

    def test_traversal_name_returns_none(self, personalities_env):
        personalities_env.ensure_personality_roots()
        assert personalities_env.resolve_handbag_path("global", "../evil", self._user()) is None

    def test_shared_requires_db_and_owner(self, personalities_env):
        assert personalities_env.resolve_handbag_path(
            "shared", "x", self._user(), owner_id=None, db=MagicMock()) is None
        assert personalities_env.resolve_handbag_path(
            "shared", "x", self._user(), owner_id=99, db=None) is None

    def _db_acl(self, row):
        db = MagicMock()
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.first.return_value = row
        db.query.return_value = chain
        return db

    def test_shared_denied_without_acl(self, personalities_env):
        assert personalities_env.resolve_handbag_path(
            "shared", "agent", self._user(), owner_id=99, db=self._db_acl(None)) is None

    def test_shared_allowed_with_acl(self, personalities_env):
        make_handbag(personalities_env.user_personalities_root("carol"), "agent")
        acl_row = SimpleNamespace(id=1)
        owner = SimpleNamespace(id=99, username="carol")

        class _Q:
            def __init__(self, result): self._result = result
            def filter(self, *a, **k): return self
            def first(self): return self._result

        def query(model):
            if getattr(model, "__name__", "") == "PersonalityShareLink":
                return _Q(acl_row)
            return _Q(owner)

        db = MagicMock()
        db.query.side_effect = query
        p = personalities_env.resolve_handbag_path(
            "shared", "agent", self._user(), owner_id=99, db=db)
        assert p is not None and p.name == "agent"
        assert p.parent == personalities_env.user_personalities_root("carol")


# ---------------------------------------------------------------------------
# 7. Loading & active personality selection
# ---------------------------------------------------------------------------

class TestLoadAndActive:
    def test_load_returns_personality(self, personalities_env, tmp_path, monkeypatch):
        sentinel = object()
        stub = _stub_lollms_personality(monkeypatch, result=sentinel)
        hb = make_handbag(tmp_path, "agent")
        assert personalities_env.load_personality_from_handbag(hb) is sentinel
        assert stub.captured["path"] == str(hb)

    def test_load_failure_returns_none(self, personalities_env, tmp_path, monkeypatch):
        _stub_lollms_personality(monkeypatch, exc=RuntimeError("wiring broke"))
        hb = make_handbag(tmp_path, "agent")
        assert personalities_env.load_personality_from_handbag(hb) is None

    def test_load_missing_library_returns_none(self, personalities_env, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "lollms_client", None)
        monkeypatch.setitem(sys.modules, "lollms_client.lollms_personality", None)
        hb = make_handbag(tmp_path, "agent")
        assert personalities_env.load_personality_from_handbag(hb) is None

    def test_active_prefers_personal_when_no_pref(self, personalities_env, monkeypatch):
        make_handbag(personalities_env.user_personalities_root("alice"), "mine")
        stub = _stub_lollms_personality(monkeypatch, result=object())
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        user = SimpleNamespace(id=1, username="alice")
        assert personalities_env.get_active_personality(user, db) is not None
        assert stub.captured["path"].endswith("mine")

    def test_active_falls_back_to_global(self, personalities_env, monkeypatch):
        make_handbag(personalities_env.global_personalities_root(), "pub")
        stub = _stub_lollms_personality(monkeypatch, result=object())
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        user = SimpleNamespace(id=2, username="bob")
        assert personalities_env.get_active_personality(user, db) is not None
        # Global discovery now includes the mandatory 'lollms' seed, which
        # sorts before 'pub'. The fallback picks lollms — a valid choice.
        # Assert the caller used a global handbag (not a personal one).
        captured = Path(stub.captured["path"])
        assert captured.parent == personalities_env.global_personalities_root()
        assert captured.name in ("lollms", "pub")

    def test_active_returns_lollms_when_nothing_else_exists(self, personalities_env, monkeypatch):
        """Mandatory 'lollms' is always present, so the fallback is never None."""
        personalities_env.ensure_personality_roots()
        stub = _stub_lollms_personality(monkeypatch, result=object())
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        user = SimpleNamespace(id=3, username="carol")
        assert personalities_env.get_active_personality(user, db) is not None
        assert stub.captured["path"].endswith("lollms")

    def test_active_honors_stored_preference(self, personalities_env, monkeypatch):
        make_handbag(personalities_env.global_personalities_root(), "chosen")
        stub = _stub_lollms_personality(monkeypatch, result=object())
        pref = SimpleNamespace(scope="global", handbag_name="chosen", owner_id=None)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = pref
        user = SimpleNamespace(id=4, username="dave")
        assert personalities_env.get_active_personality(user, db) is not None
        assert stub.captured["path"].endswith("chosen")

    def test_active_unresolvable_pref_returns_none(self, personalities_env, monkeypatch):
        personalities_env.ensure_personality_roots()
        _stub_lollms_personality(monkeypatch, result=object())
        pref = SimpleNamespace(scope="global", handbag_name="ghost", owner_id=None)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = pref
        user = SimpleNamespace(id=5, username="erin")
        assert personalities_env.get_active_personality(user, db) is None

    def test_active_db_exception_falls_back_to_discovery(self, personalities_env, monkeypatch):
        make_handbag(personalities_env.user_personalities_root("fred"), "mine")
        stub = _stub_lollms_personality(monkeypatch, result=object())
        db = MagicMock()
        db.query.side_effect = RuntimeError("db gone")
        user = SimpleNamespace(id=6, username="fred")
        assert personalities_env.get_active_personality(user, db) is not None
        assert stub.captured["path"].endswith("mine")


# ---------------------------------------------------------------------------
# 8. Atomic installs
# ---------------------------------------------------------------------------

def _make_zip(path: Path, members: dict) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return path


class TestInstall:
    def test_install_from_folder(self, personalities_env, tmp_path):
        src = tmp_path / "src_agent"
        (src / "tools").mkdir(parents=True)
        (src / "tools" / "t.py").write_text("def tool(): ...")
        (src / "SOUL.md").write_text("# soul")
        target_root = tmp_path / "target"
        final = personalities_env.install_handbag_from_folder(src, target_root)
        assert final.is_dir()
        assert (final / "SOUL.md").read_text() == "# soul"
        assert (final / "tools" / "t.py").is_file()
        # staging cleaned up
        leftovers = [p for p in target_root.iterdir() if p.name.startswith("handbag_stage_")]
        assert leftovers == []

    def test_install_from_folder_overwrites_existing(self, personalities_env, tmp_path):
        target_root = tmp_path / "target"
        (target_root / "agent").mkdir(parents=True)
        (target_root / "agent" / "old.txt").write_text("old")
        src = tmp_path / "agent"
        src.mkdir()
        (src / "new.txt").write_text("new")
        final = personalities_env.install_handbag_from_folder(src, target_root)
        assert (final / "new.txt").is_file()
        assert not (final / "old.txt").exists()

    def test_install_from_folder_rejects_file(self, personalities_env, tmp_path):
        f = tmp_path / "not_a_dir.txt"
        f.write_text("x")
        with pytest.raises(ValueError):
            personalities_env.install_handbag_from_folder(f, tmp_path / "t")

    def test_install_from_folder_name_override(self, personalities_env, tmp_path):
        src = tmp_path / "orig"
        src.mkdir()
        final = personalities_env.install_handbag_from_folder(
            src, tmp_path / "t", handbag_name="renamed")
        assert final.name == "renamed"

    def test_install_from_zip_single_top_folder(self, personalities_env, tmp_path):
        zp = _make_zip(tmp_path / "hb.zip", {
            "myagent/SOUL.md": "# soul",
            "myagent/handbag.yaml": "name: My Agent\n",
        })
        final = personalities_env.install_handbag_from_zip(zp, tmp_path / "target")
        assert final.name == "myagent"
        assert (final / "SOUL.md").is_file()
        assert (final / "handbag.yaml").is_file()

    def test_install_from_zip_name_override(self, personalities_env, tmp_path):
        zp = _make_zip(tmp_path / "hb.zip", {"wrapped-agent/SOUL.md": "# x"})
        final = personalities_env.install_handbag_from_zip(
            zp, tmp_path / "target", handbag_name="renamed_zip")
        assert final.name == "renamed_zip"
        assert (final / "SOUL.md").is_file()

    def test_install_from_flat_zip(self, personalities_env, tmp_path):
        zp = _make_zip(tmp_path / "hb.zip", {
            "SOUL.md": "# soul",
            "handbag.yaml": "name: Flat\n",
        })
        final = personalities_env.install_handbag_from_zip(
            zp, tmp_path / "target", handbag_name="flat_agent")
        assert (final / "SOUL.md").is_file()
        assert (final / "handbag.yaml").is_file()

    def test_install_from_zip_rejects_zip_slip(self, personalities_env, tmp_path):
        zp = _make_zip(tmp_path / "evil.zip", {
            "../../evil.txt": "pwn",
            "agent/SOUL.md": "# x",
        })
        target_root = tmp_path / "target"
        with pytest.raises(ValueError):
            personalities_env.install_handbag_from_zip(zp, target_root)
        # nothing escaped anywhere under tmp_path
        assert not (tmp_path / "evil.txt").exists()

    def test_install_from_zip_rejects_absolute_member(self, personalities_env, tmp_path):
        zp = _make_zip(tmp_path / "abs.zip", {
            "/etc/pwned.txt": "pwn",
            "agent/SOUL.md": "# x",
        })
        with pytest.raises(ValueError):
            personalities_env.install_handbag_from_zip(zp, tmp_path / "target")


# ---------------------------------------------------------------------------
# 9. Declarative model contracts (no DB engine)
# ---------------------------------------------------------------------------

class TestModelContracts:
    def test_imports_and_tablenames(self):
        from backend.db.models.personality_share import (
            PersonalityShareLink, UserPersonalityPreference)
        assert PersonalityShareLink.__tablename__ == "personality_share_link"
        assert UserPersonalityPreference.__tablename__ == "user_personality_preference"

    def test_share_link_unique_constraint(self):
        from backend.db.models.personality_share import PersonalityShareLink
        names = [c.name for c in PersonalityShareLink.__table__.constraints
                 if getattr(c, "name", None)]
        assert "uq_personality_share" in names

    def test_share_link_columns(self):
        from backend.db.models.personality_share import PersonalityShareLink
        cols = PersonalityShareLink.__table__.columns
        for col in ("id", "owner_user_id", "handbag_name",
                    "shared_with_user_id", "group_id", "permission"):
            assert col in cols
        assert cols["shared_with_user_id"].nullable is True
        assert cols["group_id"].nullable is True
        assert cols["owner_user_id"].nullable is False

    def test_user_preference_columns(self):
        from backend.db.models.personality_share import UserPersonalityPreference
        cols = UserPersonalityPreference.__table__.columns
        for col in ("id", "user_id", "scope", "handbag_name", "owner_id"):
            assert col in cols
        assert cols["user_id"].unique is True
        assert cols["owner_id"].nullable is True
        assert cols["scope"].default.arg == "global"


# ---------------------------------------------------------------------------
# 10. Startup bootstrap (default 'lollms' handbag seeding)
# ---------------------------------------------------------------------------

class TestBootstrap:
    def test_first_run_seeds_lollms_handbag(self, personalities_env):
        from backend.bootstrap_personalities import ensure_default_lollms_handbag
        assert ensure_default_lollms_handbag() is True
        target = personalities_env.global_personalities_root() / "lollms"
        assert (target / "handbag.yaml").is_file()
        assert (target / "SOUL.md").is_file()
        assert "Lollms" in (target / "handbag.yaml").read_text(encoding="utf-8")

    def test_seed_idempotent(self, personalities_env):
        from backend.bootstrap_personalities import ensure_default_lollms_handbag
        assert ensure_default_lollms_handbag() is True
        assert ensure_default_lollms_handbag() is False

    def test_lollms_is_mandatory_even_with_other_globals(self, personalities_env):
        from backend.bootstrap_personalities import ensure_default_lollms_handbag
        make_handbag(personalities_env.global_personalities_root(), "existing")
        # 'lollms' is mandatory: it coexists with admin-curated global content.
        assert ensure_default_lollms_handbag() is True
        assert (personalities_env.global_personalities_root() / "lollms").is_dir()

    def test_lollms_is_mandatory_even_with_user_handbags(self, personalities_env):
        from backend.bootstrap_personalities import ensure_default_lollms_handbag
        make_handbag(personalities_env.user_personalities_root("7"), "mine")
        # 'lollms' is mandatory: it coexists with personal handbags, never hides them.
        assert ensure_default_lollms_handbag() is True
        assert (personalities_env.global_personalities_root() / "lollms").is_dir()

    def test_full_bootstrap_seeds_default_on_empty_db(self, personalities_env):
        from backend.bootstrap_personalities import run_personalities_bootstrap
        db = MagicMock()
        db.query.return_value.all.return_value = []          # no legacy rows
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.first.return_value = None
        run_personalities_bootstrap(db)
        target = personalities_env.global_personalities_root() / "lollms"
        assert (target / "SOUL.md").is_file()
        assert (target / "handbag.yaml").is_file()

    def test_full_bootstrap_never_raises_on_db_error(self, personalities_env):
        from backend.bootstrap_personalities import run_personalities_bootstrap
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        # Must not raise; default seed still happens
        run_personalities_bootstrap(db)
        assert (personalities_env.global_personalities_root() / "lollms" / "SOUL.md").is_file()