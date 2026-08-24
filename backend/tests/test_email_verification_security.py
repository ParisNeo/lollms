import sys
import datetime
from datetime import timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from backend.security import generate_verification_code, send_verification_code_email, send_password_reset_email

class TestEmailSecurityAndVerification:
    """Regression tests validating password reset email fixes and the new Email 2FA feature."""

    def test_generate_verification_code_is_six_digits(self):
        code = generate_verification_code(6)
        assert len(code) == 6
        assert code.isdigit()

    @patch('backend.security.send_generic_email')
    def test_send_verification_code_email_triggers_generic_send(self, mock_send):
        send_verification_code_email("user@example.com", "123456", "testuser", 10)
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        assert args[0] == "user@example.com"
        assert "Authentication Code" in args[1]
        assert "123456" in args[2]

    @patch('backend.security.send_generic_email')
    def test_send_password_reset_email_html_and_fallback(self, mock_send):
        send_password_reset_email("user@example.com", "https://localhost:9642/reset-password?token=abc", "testuser")
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        assert args[0] == "user@example.com"
        assert "Password Reset Request" in args[1]
        assert "https://localhost:9642/reset-password?token=abc" in args[2]

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_system_mail_text_command_resolution(self, mock_subproc, mock_which):
        from backend.security import _send_email_system_mail_text
        
        # Test when sendmail is present
        mock_which.side_effect = lambda cmd: "/usr/sbin/sendmail" if cmd == "sendmail" else None
        _send_email_system_mail_text("dest@example.com", "Subject Test", "Body Content")
        mock_subproc.assert_called()
        cmd_called = mock_subproc.call_args[0][0]
        assert cmd_called == ["sendmail", "-t"]