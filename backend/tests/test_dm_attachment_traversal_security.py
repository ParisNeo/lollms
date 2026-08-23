import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from backend.routers.social.dm import get_dm_attachment

class TestDmAttachmentTraversalSecurity:
    """Tests ensuring directory traversal in DM attachments is prevented."""

    @pytest.mark.asyncio
    async def test_traversal_filename_is_blocked(self, tmp_path, monkeypatch):
        # Create a mock user data root
        mock_user = MagicMock()
        mock_user.username = "alice"
        
        user_dm_dir = tmp_path / "data" / "users" / "alice" / "dm_assets"
        user_dm_dir.mkdir(parents=True, exist_ok=True)
        
        # Place a secret file outside the dm_assets folder
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("SUPER_SECRET_KEY")

        monkeypatch.setattr("backend.routers.social.dm.get_user_dm_assets_path", lambda username: user_dm_dir)

        # Attempt path traversal
        with pytest.raises(HTTPException) as exc_info:
            await get_dm_attachment(
                username="alice",
                filename="../../secret.txt",
                current_user=mock_user
            )
        assert exc_info.value.status_code == 404