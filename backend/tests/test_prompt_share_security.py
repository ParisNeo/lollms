# backend/tests/test_prompt_share_security.py
"""
Regression tests for CVE: Stored XSS in Prompt-Sharing Direct Messages.
Validates that prompt share content is properly sanitized before persistence.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from backend.security import sanitize_content


class TestPromptShareSanitization:
    """Tests validating the fix for stored XSS via prompt sharing."""

    def test_sanitize_content_strips_xss_img_onerror(self):
        """CVE PoC payload: <img src=x onerror=alert(JSON.stringify(localStorage))>"""
        payload = '<img src=x onerror=alert(JSON.stringify(localStorage))>'
        result = sanitize_content(payload)
        assert 'onerror' not in result
        assert '<img' not in result  # img tag is not in ALLOWED_TAGS

    def test_sanitize_content_strips_quoted_event_handler(self):
        """Quoted event handlers should be removed."""
        payload = '<a href="#" onclick="alert(1)">click me</a>'
        result = sanitize_content(payload)
        assert 'onclick' not in result
        assert 'alert(1)' not in result

    def test_sanitize_content_strips_script_tags(self):
        """Script tags should be completely removed."""
        payload = '<script>fetch("/api/admin/users")</script>'
        result = sanitize_content(payload)
        assert '<script>' not in result
        assert 'fetch' not in result

    def test_sanitize_content_preserves_safe_formatting(self):
        """Safe HTML formatting should be preserved."""
        payload = '<b>Bold text</b> and <i>italic</i> with <a href="https://example.com">a link</a>'
        result = sanitize_content(payload)
        assert '<b>' in result
        assert '<i>' in result
        assert '<a' in result
        assert 'href="https://example.com"' in result

    def test_prompt_share_formatted_content_sanitization(self):
        """
        Simulates the fixed share_prompt_as_dm endpoint logic.
        The formatted content including the prefix must be sanitized.
        """
        prompt_content = '<img src=x onerror=alert(JSON.stringify(localStorage))>'
        formatted = f"--- SHARED PROMPT ---\n\n{prompt_content}"
        sanitized = sanitize_content(formatted)

        # The prefix must survive sanitization
        assert '--- SHARED PROMPT ---' in sanitized

        # The malicious payload must be neutralized
        assert 'onerror' not in sanitized
        assert 'alert' not in sanitized
        assert '<img' not in sanitized

    def test_sanitize_content_handles_empty_input(self):
        """Edge case: empty or None input should not crash."""
        assert sanitize_content('') == ''
        assert sanitize_content(None) is None
