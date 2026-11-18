# backend/db/models/settings_policy.py
"""
Per-field admin policy governing whether a user may change a setting and whether
the administrator pins it to a specific value.

One row per governable field. Absence of a row (or locked="0"/forced="0") means the
field is freely editable by the user.

Enforcement lives in ``backend/routers/auth.py:update_my_details`` (write path) and
``get_my_details`` (read path) via the helpers in
``backend/routers/admin/settings_policy.py``.
"""
import json

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from backend.db.base import Base


class UserSettingPolicy(Base):
    __tablename__ = "user_setting_policies"

    id = Column(Integer, primary_key=True, index=True)
    field_name = Column(String, unique=True, index=True, nullable=False)

    # "1" / "0" string sentinels avoid SQLite ALTER-TABLE quirks on legacy DBs.
    locked = Column(String, nullable=False, default="0", server_default="'0'")
    forced = Column(String, nullable=False, default="0", server_default="'0'")

    # JSON-encoded forced value (so booleans/ints/lists survive round-trips without
    # per-column typing surprises).
    forced_value = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def get_forced_value(self):
        """Return the deserialized forced value, or ``None`` if unset."""
        if self.forced_value is None or self.forced_value == "":
            return None
        try:
            return json.loads(self.forced_value)
        except (TypeError, ValueError):
            return None

    def set_forced_value(self, value):
        """Serialize and store a forced value; pass ``None`` to clear."""
        if value is None:
            self.forced_value = None
        else:
            self.forced_value = json.dumps(value)