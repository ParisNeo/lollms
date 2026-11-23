"""Security regression tests for CWE-22 path traversal (GHSA-w6j2-6h82-xj6m).

``GET /api/skills_zoo/readme`` historically concatenated the client-supplied
``folder_name`` directly into a filesystem path without normalization or a
containment check, allowing an unauthenticated attacker to read arbitrary
local files (e.g. ``../../../../etc/passwd``).

This suite locks in the fix:

* ``_resolve_within_root`` rejects ``..`` escapes but serves contained files,
* a traversal ``repository`` name never escapes the zoo root,
* ``get_skill_readme`` blocks traversal and requires authentication,
* a legitimate readme is still served.

Runs under ``pytest``; when pytest is absent it can be executed directly:

    python backend/tests/test_skills_zoo_readme_traversal_security.py

which uses a tiny built-in harness and exits non-zero on failure.
"""
import sys
import tempfile
import types
from pathlib import Path

try:
    import pytest
except ImportError:  # pragma: no cover - exercised only without pytest
    pytest = None

from fastapi import HTTPException

def _build_env(tmp_root: Path):
    """Materialize an isolated skills zoo plus an out-of-root secret file."""
    skills_root = tmp_root / "skills_zoo"
    skill_dir = skills_root / "lollms_skills_zoo" / "my_skill"
    skill_dir.mkdir(parents=True)
    readme = skill_dir / "README.md"
    readme.write_text("# My Skill\n", encoding="utf-8")
    secret = tmp_root / "secret_outside_root.txt"
    secret.write_text("TOP_SECRET_TOKEN", encoding="utf-8")
    return skills_root, readme, secret

def _run_core_checks(tmp_root: Path):
    """Framework-agnostic exploit-reproduction + fix-verification."""
    skills_root, readme, _secret = _build_env(tmp_root)

    from backend.routers.zoos import skills_zoo as mod
    original_root = mod.SKILLS_ZOO_ROOT_PATH
    original_auth = mod.get_current_active_user
    mod.SKILLS_ZOO_ROOT_PATH = skills_root
    mod.get_current_active_user = lambda: types.SimpleNamespace(username="tester")
    try:
        # (1) containment helper blocks traversal
        try:
            mod._resolve_within_root(skills_root, "../../secret_outside_root.txt")
        except HTTPException as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("_resolve_within_root allowed traversal")

        # (2) containment helper still serves contained paths
        contained = mod._resolve_within_root(
            skills_root, "lollms_skills_zoo/my_skill/README.md"
        )
        assert contained == readme.resolve()
        assert contained.read_text(encoding="utf-8") == "# My Skill\n"

        # (3) traversal repository name cannot escape the zoo root
        resolved = Path(mod._resolve_safe_skill_root("../../..")).resolve()
        root_resolved = skills_root.resolve()
        assert (
            resolved == root_resolved or root_resolved in resolved.parents
        ), f"repo-name traversal escaped root: {resolved}"

        # (4) endpoint function blocks traversal
        try:
            mod.get_skill_readme(
                repository="lollms_skills_zoo",
                folder_name="../../secret_outside_root.txt",
            )
        except HTTPException as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("get_skill_readme allowed traversal")

        # (5) endpoint still serves a legitimate readme
        body = mod.get_skill_readme(
            repository="lollms_skills_zoo", folder_name="my_skill"
        )
        assert "# My Skill" in body
    finally:
        mod.SKILLS_ZOO_ROOT_PATH = original_root
        mod.get_current_active_user = original_auth

if pytest is not None:

    @pytest.fixture()
    def zoo_env(tmp_path, monkeypatch):
        skills_root, readme, secret = _build_env(tmp_path)
        from backend.routers.zoos import skills_zoo as mod

        monkeypatch.setattr(mod, "SKILLS_ZOO_ROOT_PATH", skills_root, raising=True)
        return types.SimpleNamespace(
            mod=mod,
            skills_root=skills_root,
            secret=secret,
            skill_readme=readme,
        )

    def test_resolve_within_root_blocks_traversal(zoo_env):
        with pytest.raises(HTTPException) as exc:
            zoo_env.mod._resolve_within_root(
                zoo_env.skills_root, "../../secret_outside_root.txt"
            )
        assert exc.value.status_code == 400

    def test_resolve_within_root_allows_contained(zoo_env):
        target = zoo_env.mod._resolve_within_root(
            zoo_env.skills_root, "lollms_skills_zoo/my_skill/README.md"
        )
        assert target == zoo_env.skill_readme.resolve()
        assert target.read_text(encoding="utf-8") == "# My Skill\n"

    def test_safe_skill_root_rejects_traversal_repo_name(zoo_env):
        resolved = Path(zoo_env.mod._resolve_safe_skill_root("../../..")).resolve()
        root_resolved = zoo_env.skills_root.resolve()
        assert resolved == root_resolved or root_resolved in resolved.parents

    def test_get_skill_readme_blocks_traversal(zoo_env, monkeypatch):
        monkeypatch.setattr(
            zoo_env.mod,
            "get_current_active_user",
            lambda: types.SimpleNamespace(username="tester"),
        )
        with pytest.raises(HTTPException) as exc:
            zoo_env.mod.get_skill_readme(
                repository="lollms_skills_zoo",
                folder_name="../../secret_outside_root.txt",
            )
        assert exc.value.status_code == 400

    def test_get_skill_readme_serves_legit_file(zoo_env, monkeypatch):
        monkeypatch.setattr(
            zoo_env.mod,
            "get_current_active_user",
            lambda: types.SimpleNamespace(username="tester"),
        )
        body = zoo_env.mod.get_skill_readme(
            repository="lollms_skills_zoo", folder_name="my_skill"
        )
        assert "# My Skill" in body

    def test_endpoint_requires_authentication(zoo_env):
        """The readme endpoint must reject unauthenticated callers (401/403)."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(zoo_env.mod.skills_zoo_router)
        resp = TestClient(app).get(
            "/api/skills_zoo/readme",
            params={"repository": "lollms_skills_zoo", "folder_name": "my_skill"},
        )
        assert resp.status_code in (401, 403)

if __name__ == "__main__":
    # Ensure the project root (three levels up: backend/tests/ -> repo root)
    # is importable when this file is executed directly as a script, since
    # sys.path[0] would otherwise be backend/tests/.
    _project_root = Path(__file__).resolve().parents[2]
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    with tempfile.TemporaryDirectory() as tmp:
        _run_core_checks(Path(tmp))
    print("SECURITY CHECKS PASSED")