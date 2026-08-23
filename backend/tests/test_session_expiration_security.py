import sys
import datetime
from datetime import timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from backend.security import create_access_token
from backend.session import get_current_db_user_from_token


class TestSessionExpirationSecurity:
    """Regression tests ensuring JWT tokens are invalidated when passwords change/reset."""

    @pytest.mark.asyncio
    async def test_token_issued_before_password_change_is_rejected(self):
        # Token issued at T0
        past_time = datetime.datetime.now(timezone.utc) - timedelta(minutes=10)
        token = create_access_token(
            data={"sub": "alice", "iat": int(past_time.timestamp())},
            expires_delta=timedelta(days=1)
        )

        mock_user = MagicMock()
        mock_user.username = "alice"
        mock_user.is_active = True
        mock_user.password_changed_at = datetime.datetime.now(timezone.utc)

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_db_user_from_token(token=token, db=mock_db)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_token_issued_after_password_change_is_accepted(self):
        # Password changed at T0
        past_time = datetime.datetime.now(timezone.utc) - timedelta(minutes=10)
        
        # Token issued now (after password change)
        token = create_access_token(
            data={"sub": "alice"},
            expires_delta=timedelta(days=1)
        )

        mock_user = MagicMock()
        mock_user.username = "alice"
        mock_user.is_active = True
        mock_user.password_changed_at = past_time
        mock_user.last_activity_at = past_time

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        user = await get_current_db_user_from_token(token=token, db=mock_db)
        assert user.username == "alice"