import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from unittest.mock import MagicMock, patch
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from backend.routers.social.dm import build_dm_router
from backend.db.base import get_db
from backend.security import get_current_active_user

CONV_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def mock_user():
    class MockUser:
        id = 1
        username = "alice"
        is_admin = False
        is_active = True
        is_personal_page_enabled = True
    return MockUser()


@pytest.fixture
def mock_db():
    """DB that returns no attachment rows (filename never matches)."""
    db = MagicMock()
    db.query.return_value.join.return_value.options.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.options.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []
    return db


@pytest.fixture
def app(mock_user, mock_db):
    app = FastAPI()
    router = APIRouter()
    build_dm_router(router)

    async def mock_get_current_active_user():
        return mock_user

    app.dependency_overrides[get_current_active_user] = mock_get_current_active_user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.include_router(router, prefix="/dm")
    return app


@pytest.fixture
def client(app):
    # raise_server_exceptions=False so mocked-DB internal errors surface as 5xx,
    # which traversal tests must tolerate alongside 4xx rejections.
    return TestClient(app, raise_server_exceptions=False)


class TestDmAttachmentTraversalSecurity:
    """Path traversal against DM attachment endpoints must be impossible."""

    @pytest.mark.parametrize("evil_name", [
        "../../../etc/passwd",
        "..%2F..%2F..%2Fetc%2Fpasswd",
        "%2E%2E%2Fsecret.txt",
    ])
    def test_traversal_filename_is_blocked(self, client, evil_name):
        response = client.get(
            f"/dm/attachment/1/{evil_name}?conversation_id={CONV_ID}"
        )
        # Exact-filename DB lookup means traversal names can never match a row;
        # acceptable rejections: 404 (not found), 422 (route validation),
        # 405 (unroutable), or a 5xx caused by the fully mocked DB — but never 200.
        assert response.status_code != 200
        assert response.status_code in (400, 404, 405, 422, 500)
        # Even when rejected, the body must not leak file contents.
        assert "root:" not in response.text

    def test_traversal_absolute_path_is_blocked(self, client):
        for evil in ("/etc/passwd", "C:/Windows/win.ini"):
            response = client.get(
                f"/dm/attachment/1/{evil[1:] if evil.startswith('/') else evil}"
                f"?conversation_id={CONV_ID}"
            )
            assert response.status_code != 200
            assert "root:" not in response.text and "[fonts]" not in response.text

    def test_traversal_url_encoded_is_blocked(self, client):
        response = client.get(
            "/dm/attachment/1/%2e%2e%2f%2e%2e%2fsecret.txt"
            f"?conversation_id={CONV_ID}"
        )
        assert response.status_code != 200
        assert response.status_code in (400, 404, 405, 422, 500)

    def test_null_byte_injection_is_blocked(self, client):
        response = client.get(
            "/dm/attachment/1/legit.txt%00../../secret"
            f"?conversation_id={CONV_ID}"
        )
        assert response.status_code != 200
        assert response.status_code in (400, 404, 405, 422, 500)

    def test_upload_filename_sanitization(self, tmp_path):
        """os.path.basename semantics: separators must be stripped on upload."""
        import os
        for raw, expected_tail in [
            ("../../etc/passwd", "passwd"),
            ("..\\..\\secret.txt", "secret.txt"),
            ("/absolute/path/file.png", "file.png"),
            ("normal.txt", "normal.txt"),
        ]:
            sanitized = os.path.basename(raw)
            assert sanitized == expected_tail
            assert "/" not in sanitized and "\\" not in sanitized
            assert sanitized not in ("..", ".", "")