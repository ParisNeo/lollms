import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException, UploadFile
from backend.routers.skills import import_skill

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