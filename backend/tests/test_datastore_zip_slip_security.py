import sys
import io
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException, UploadFile
from backend.routers.stores import import_datastore

class TestDatastoreZipSlipSecurity:
    """Tests ensuring Zip Slip attacks during Datastore imports are rejected."""

    @pytest.mark.asyncio
    async def test_zip_slip_payload_raises_http_exception(self):
        # Construct a malicious in-memory zip archive with path traversal entry
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr("../../evil.txt", "MALICIOUS_CONTENT")
            zf.writestr("metadata.json", '{"name": "test"}')
        zip_buffer.seek(0)

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "malicious_import.zip"
        mock_file.file = zip_buffer

        mock_user = MagicMock()
        mock_user.username = "alice"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with pytest.raises(HTTPException) as exc_info:
            await import_datastore(
                file=mock_file,
                name="Test Store",
                current_user=mock_user,
                db=mock_db
            )

        assert exc_info.value.status_code == 400
        assert "Path traversal" in exc_info.value.detail or "Invalid ZIP" in exc_info.value.detail