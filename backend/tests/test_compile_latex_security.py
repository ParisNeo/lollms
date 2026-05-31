# backend/tests/test_compile_latex_security.py
import sys
from unittest.mock import patch, MagicMock

# Dynamically mock optional third-party packages and all their submodules 
# to prevent import-time ModuleNotFoundError during test collection on some systems
optional_modules = [
    'markdown_pdf', 
    'docx', 'docx.shared', 'docx.oxml', 'docx.oxml.ns',
    'openpyxl', 'openpyxl.utils', 
    'pptx', 'pptx.enum', 'pptx.enum.shapes', 'pptx.util', 
    'weasyprint', 'xhtml2pdf', 'docx2python', 'pandas', 'extract_msg', 'fitz',
    'mdtopptx', 'scrapemaster',
    'latex2mathml', 'latex2mathml.converter',
    'markdown2', 'bs4', 'PIL'
]
for module_name in optional_modules:
    if module_name not in sys.modules:
        sys.modules[module_name] = MagicMock()

import unittest
import os
import tempfile
import base64
import asyncio
from pathlib import Path

# Ensure the backend directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.routers.discussion.utils import compile_latex_code, LatexCompilationRequest

class TestCompileLatexSecurity(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch('backend.routers.discussion.utils.get_user_discussion_assets_path')
    @patch('backend.routers.discussion.utils.settings')
    @patch('backend.routers.discussion.utils.shutil.which')
    @patch('backend.routers.discussion.utils.subprocess.run')
    def test_compile_latex_security_enforcement(
        self, mock_run, mock_which, mock_settings, mock_get_assets_path
    ):
        """
        Verify that LaTeX compilation enforces security constraints:
        - -no-shell-escape option is passed to the compiler to block RCE.
        - Environment variables (openin_any, openout_any, shell_escape) are set to paranoid.
        """
        # Configure directory mock
        mock_get_assets_path.return_value = self.temp_path
        
        # Configure global settings mocks
        def mock_settings_get(key, default=None):
            if key == "latex_builder_enabled":
                return True
            if key == "latex_builder_path":
                return "pdflatex"
            return default
        mock_settings.get.side_effect = mock_settings_get
        
        # Simulate local executable found in path
        mock_which.return_value = "/usr/bin/pdflatex"

        # Mock subprocess run to write a dummy PDF file in the temp output directory so the function succeeds
        def side_effect_run(args, **kwargs):
            try:
                out_dir_idx = args.index("-output-directory")
                out_dir = args[out_dir_idx + 1]
                pdf_file = Path(out_dir) / "document.pdf"
                pdf_file.write_bytes(b"dummy pdf content")
                
                log_file = Path(out_dir) / "document.log"
                log_file.write_text("dummy log content")
            except Exception as e:
                pass
            
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "Success stdout"
            mock_proc.stderr = ""
            return mock_proc

        mock_run.side_effect = side_effect_run

        # Prepare request payload
        request_payload = LatexCompilationRequest(
            code=r"\documentclass{article}\begin{document}Hello\end{document}"
        )
        mock_user = MagicMock()
        mock_user.username = "test_user"

        # Execute endpoint function asynchronously
        response = asyncio.run(compile_latex_code(
            discussion_id="test_disc",
            request=request_payload,
            current_user=mock_user
        ))

        # Verify response structure
        self.assertIn("pdf_b64", response)
        self.assertEqual(response["pdf_b64"], base64.b64encode(b"dummy pdf content").decode('utf-8'))

        # Verify subprocess.run arguments
        mock_run.assert_called_once()
        called_args, called_kwargs = mock_run.call_args
        
        command_list = called_args[0]
        self.assertIn("-no-shell-escape", command_list)
        
        # Verify secure environment variables are passed to sandbox the LaTeX run
        env_dict = called_kwargs.get("env")
        self.assertIsNotNone(env_dict)
        self.assertEqual(env_dict.get("openin_any"), "p")
        self.assertEqual(env_dict.get("openout_any"), "p")
        self.assertEqual(env_dict.get("shell_escape"), "f")

if __name__ == '__main__':
    unittest.main()
