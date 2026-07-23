import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    import pipmaster as pm
    pm.ensure_packages(["markdown_pdf", "python-docx", "PyMuPDF", "Pillow"])
except Exception:
    pass

import base64
import os
import pytest
import zipfile
from fastapi import APIRouter
from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends

from backend.routers.discussion.utils import build_utils_router

class MockSettings:
    def get(self, key, default=None):
        if key == "latex_builder_enabled":
            return True
        if key == "latex_builder_path":
            return "pdflatex"
        return default

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
    utils_router = build_utils_router(router)
    
    async def mock_get_current_active_user():
        return mock_user
        
    app.dependency_overrides[
        __import__('backend.session', fromlist=['get_current_active_user']).get_current_active_user
    ] = mock_get_current_active_user
    
    app.include_router(utils_router, prefix="/api/discussions")
    return app

@pytest.fixture
def client(app):
    return TestClient(app)

def test_compile_latex_mitigates_arbitrary_file_read(client, tmp_path):
    """
    Test that the compile_latex_code endpoint applies the -cnf paranoid mode
    to prevent arbitrary file reads via LaTeX primitives.
    """
    malicious_code = r"""
    \documentclass{article}
    \newread\myfile
    \openin\myfile=/etc/passwd
    \typeout{LEAK_START}
    \read\myfile to \lineAA
    \typeout{LEAK:\lineAA}
    \closein\myfile
    \typeout{LEAK_END}
    \begin{document}
    hello
    \end{document}
    """

    with patch('backend.routers.discussion.utils.settings', MockSettings()), \
         patch('backend.routers.discussion.utils.subprocess.run') as mock_run, \
         patch('backend.routers.discussion.utils.shutil.which', return_value='/usr/bin/pdflatex'), \
         patch('backend.routers.discussion.utils.get_user_discussion_assets_path', return_value=tmp_path):

        def fake_run(*args, **kwargs):
            cmd_args = args[0] if args else kwargs.get('args', [])
            output_dir = Path(".")
            if "-output-directory" in cmd_args:
                idx = cmd_args.index("-output-directory")
                if idx + 1 < len(cmd_args):
                    output_dir = Path(cmd_args[idx + 1])
            
            (output_dir / "document.pdf").write_bytes(b"%PDF-1.4 mock")
            (output_dir / "document.log").write_text("LEAK_START\nLEAK:root:x:0:0:root:/root:/bin/bash\nLEAK_END", encoding="utf-8")
            
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.stdout = ""
            mock_process.stderr = ""
            return mock_process

        mock_run.side_effect = fake_run

        response = client.post(
            "/api/discussions/exploit-poc-001/compile-latex",
            json={"code": malicious_code}
        )

        assert mock_run.called
        call_args = mock_run.call_args[0][0]

        assert "pdflatex" in call_args
        assert "-no-shell-escape" in call_args
        assert "-cnf" in call_args
        
        cnf_index = call_args.index("-cnf")
        cnf_value = call_args[cnf_index + 1]
        assert "openin_any=p" in cnf_value
        assert "openout_any=p" in cnf_value
        assert "shell_escape=p" in cnf_value

        assert response.status_code == 200
        data = response.json()
        assert "pdf_b64" in data
        assert "logs" in data
        assert "LEAK_START" in data["logs"]
