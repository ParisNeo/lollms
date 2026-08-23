"""
Regression tests for Advisory 2:
Stored cross-site scripting via an unsanitized username in the group DM system message.
Validates that malicious usernames in group DM system messages are neutralized.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from backend.security import sanitize_content


class TestGroupDmSystemMessageSanitization:
    """Tests validating the fix for stored XSS via group DM system messages."""

    def test_javascript_markdown_link_in_username_neutralized(self):
        """Attacker username formatted as a markdown link with javascript: URI."""
        malicious_username = '[admin](javascript:alert(document.domain))'
        clean_username = sanitize_content(malicious_username)
        system_content = sanitize_content(f"{clean_username} was added to the group.")

        assert 'javascript:' not in system_content.lower()
        assert 'alert(' not in system_content
        assert 'was added to the group.' in system_content

    def test_html_javascript_link_in_username_neutralized(self):
        """Attacker username with raw HTML link using javascript: scheme."""
        malicious_username = '<a href="javascript:stealCookies()">EvilAdmin</a>'
        clean_username = sanitize_content(malicious_username)
        system_content = sanitize_content(f"{clean_username} was added to the group.")

        assert 'javascript:' not in system_content.lower()
        assert 'stealCookies' not in system_content
        assert 'was added to the group.' in system_content

    def test_script_tag_in_username_removed(self):
        """Attacker username containing inline <script> tags."""
        malicious_username = '<script>fetch("/api/admin/users")</script>attacker'
        clean_username = sanitize_content(malicious_username)
        system_content = sanitize_content(f"{clean_username} was added to the group.")

        assert '<script>' not in system_content
        assert '</script>' not in system_content
        assert 'fetch' not in system_content
        assert 'was added to the group.' in system_content

    def test_img_onerror_in_username_removed(self):
        """Attacker username with <img> event handler payload."""
        malicious_username = 'user<img src=x onerror=alert(1)>'
        clean_username = sanitize_content(malicious_username)
        system_content = sanitize_content(f"{clean_username} was added to the group.")

        assert 'onerror' not in system_content
        assert '<img' not in system_content
        assert 'alert(1)' not in system_content
        assert 'was added to the group.' in system_content

    def test_benign_username_preserved(self):
        """Legitimate usernames with standard characters remain intact."""
        normal_username = 'alice_smith-99'
        clean_username = sanitize_content(normal_username)
        system_content = sanitize_content(f"{clean_username} was added to the group.")

        assert system_content == 'alice_smith-99 was added to the group.'

    def test_empty_and_none_username_handling(self):
        """Empty or None inputs are handled safely without unhandled exceptions."""
        assert sanitize_content('') == ''
        assert sanitize_content(None) is None

        system_content = sanitize_content(f"{sanitize_content('')} was added to the group.")
        assert system_content == ' was added to the group.'