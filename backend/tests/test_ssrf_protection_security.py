import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from fastapi import HTTPException

from backend.security import validate_url, safe_requests_get

@pytest.mark.parametrize("malicious_url", [
    "http://127.0.0.1/",
    "http://10.0.0.1/",
    "http://169.254.169.254/latest/meta-data/",
    "http://localhost/",
    "ftp://internal.server/",
    "http://[::1]/",
    "http://[fe80::1]/"
])
def test_validate_url_blocks_ssrf(malicious_url):
    with pytest.raises(ValueError):
        validate_url(malicious_url)

def test_validate_url_allows_public():
    validate_url("https://example.com")

def test_safe_requests_get_blocks_redirect_to_internal():
    mock_redirect_response = MagicMock()
    mock_redirect_response.status_code = 302
    mock_redirect_response.headers = {"Location": "http://169.254.169.254/latest/meta-data/"}

    with patch("requests.Session.get", return_value=mock_redirect_response):
        with pytest.raises(ValueError, match="forbidden"):
            safe_requests_get("https://example.com/redirect")
