import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException, UploadFile
from backend.routers.skills import import_skill, _build_skill_markdown, _parse_zip_skill

import io
import zipfile

class TestSkillsXmlSecurity:
    """Tests ensuring XML DTD and XXE entities in skill imports are blocked."""

    @pytest.mark.asyncio
    async def test_xxe_payload_is_rejected(self):
        xxe_xml = """<?xml version="1.0"?>
        <!DOCTYPE skill [
        <!ENTITY xxe SYSTEM "file:///etc/passwd">
        ]>
        <skill>
            <name>Malicious</name>
            <content>&xxe;</content>
        </skill>
        """

        mock_file = MagicMock(spec=UploadFile)
        mock_file.read = AsyncMock(return_value=xxe_xml.encode('utf-8'))

        mock_user = MagicMock()
        mock_user.id = 1

        mock_db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await import_skill(
                file=mock_file,
                current_user=mock_user,
                db=mock_db
            )

        assert exc_info.value.status_code == 400
        assert "forbidden" in exc_info.value.detail.lower()

    def test_yaml_header_is_normalized_with_required_metadata(self):
        content, metadata = _build_skill_markdown(
            "# Instructions\n\nUse [subskill](helpers/detail.md).",
            "Researcher", "Alice", "Research assistance", "Knowledge", "1.0.0", "markdown"
        )
        assert metadata == {"name": "Researcher", "author": "Alice", "description": "Research assistance"}
        assert content.startswith("---\nname: Researcher\nauthor: Alice\ndescription: Research assistance\n")
        assert "[subskill](helpers/detail.md)" in content

    def test_zip_package_reads_subskills_readme_and_license(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("SKILL.md", "---\nname: Researcher\nauthor: Alice\ndescription: Research assistance\n---\n\nSee [helper](helpers/detail.md).")
            archive.writestr("helpers/detail.md", "# Helper directives")
            archive.writestr("README.md", "# Usage")
            archive.writestr("LICENSE.md", "MIT License")
        imported = _parse_zip_skill(output.getvalue())
        assert imported["name"] == "Researcher"
        assert imported["supporting_files"] == {
            "helpers/detail.md": "# Helper directives",
            "README.md": "# Usage",
            "LICENSE.md": "MIT License",
        }