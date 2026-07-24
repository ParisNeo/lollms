import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from fastapi import APIRouter, FastAPI, Depends
from fastapi.testclient import TestClient

from backend.routers.discussion.artefacts import build_artefacts_router
from backend.models import UserAuthDetails
from backend.session import get_current_active_user

class MockSettings:
    def get(self, key, default=None):
        return default

class MockDiscussion:
    def __init__(self):
        self.artefacts = []
        self.metadata = {}

    def import_github(self, url, auto_load):
        return {"title": "test", "content": "imported", "version": 1}

    def commit(self):
        pass

    def list_artefacts(self):
        return []

    def get_discussion_images(self):
        return []

@pytest.fixture
def mock_user():
    class MockUser:
        id = 1
        username = "testuser"
        is_admin = False
        is_moderator = False
        is_active = True
        lollms_model_name = "test/test"
    return MockUser()

@pytest.fixture
def app(mock_user):
    app = FastAPI()
    router = APIRouter()
    build_artefacts_router(router)

    async def mock_get_current_active_user():
        return mock_user

    app.dependency_overrides[get_current_active_user] = mock_get_current_active_user

    from backend.db import get_db
    def mock_get_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = mock_get_db

    app.include_router(router, prefix="/api/discussions")
    return app

@pytest.fixture
def client(app):
    return TestClient(app)

def test_github_import_ssrf_bypass_blocked(client):
    """
    Test that the GitHub import endpoint blocks the RFC 3986 userinfo bypass
    (e.g., http://github.com@169.254.169.254/).
    """
    malicious_url = "http://github.com@169.254.169.254/latest/meta-data/iam/security-credentials/"
    
    with patch('backend.routers.discussion.artefacts.get_discussion_and_owner_for_request') as mock_get_disc, \
         patch('backend.routers.files.socket.getaddrinfo') as mock_getaddrinfo:
        
        mock_get_disc.return_value = (MockDiscussion(), "testuser", "interact", mock_user)
        mock_getaddrinfo.return_value = [(None, None, None, None, ('169.254.169.254', 0))]

        response = client.post(
            "/api/discussions/test-disc/artefacts/github",
            json={"url": malicious_url, "auto_load": True}
        )

        assert response.status_code == 400
        assert "Not a valid GitHub URL" in response.json().get("detail", "")

def test_github_import_ssrf_raw_bypass_blocked(client):
    """
    Test that the GitHub import endpoint blocks the raw.githubusercontent.com bypass.
    """
    malicious_url = "http://raw.githubusercontent.com@127.0.0.1:9642/openapi.json"
    
    with patch('backend.routers.discussion.artefacts.get_discussion_and_owner_for_request') as mock_get_disc, \
         patch('backend.routers.files.socket.getaddrinfo') as mock_getaddrinfo:
        
        mock_get_disc.return_value = (MockDiscussion(), "testuser", "interact", mock_user)
        mock_getaddrinfo.return_value = [(None, None, None, None, ('127.0.0.1', 0))]

        response = client.post(
            "/api/discussions/test-disc/artefacts/github",
            json={"url": malicious_url, "auto_load": True}
        )

        assert response.status_code == 400
        assert "Not a valid GitHub URL" in response.json().get("detail", "")

def test_github_import_legitimate_url_allowed(client):
    """
    Test that a legitimate GitHub URL is allowed to pass validation.
    """
    legit_url = "https://raw.githubusercontent.com/ParisNeo/lollms/main/README.md"
    
    with patch('backend.routers.discussion.artefacts.get_discussion_and_owner_for_request') as mock_get_disc, \
         patch('backend.routers.files.socket.getaddrinfo') as mock_getaddrinfo, \
         patch('backend.routers.discussion.artefacts.requests.get') as mock_requests:
        
        mock_get_disc.return_value = (MockDiscussion(), "testuser", "interact", mock_user)
        mock_getaddrinfo.return_value = [(None, None, None, None, ('185.199.108.133', 0))]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# Lollms"
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        response = client.post(
            "/api/discussions/test-disc/artefacts/github",
            json={"url": legit_url, "auto_load": True}
        )

        assert response.status_code == 200
