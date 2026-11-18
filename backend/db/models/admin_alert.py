"""
Operational alert model for the admin monitoring feed.

An :class:`AdminAlert` is a deduplicated, persisted incident record. Distinct
operational conditions (a user over-consuming tokens, a platform-wide budget
breach, a startup failure, etc.) map to distinct ``dedupe_key`` values; repeated
occurrences of the same open condition bump ``occurrence_count`` and
``last_seen_at`` instead of flooding the feed with duplicates.
"""
import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, ForeignKey, Index,
)
from sqlalchemy.sql import func

from backend.db.base import Base


class AdminAlert(Base):
    __tablename__ = "admin_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Stable identity of the underlying condition; used for dedup/aggregation.
    # e.g. "user_token_daily:<user_id>:warning" or "system_daily_budget".
    dedupe_key = Column(String, nullable=False, index=True)

    # Coarse bucket for filtering: tokens, system, security, task, etc.
    category = Column(String, nullable=False, default="system", index=True)

    # info | warning | critical
    severity = Column(String, nullable=False, default="warning", index=True)

    title = Column(String, nullable=False)
    message = Column(Text, nullable=True)

    # Optional relations for drill-down.
    related_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    related_username = Column(String, nullable=True)

    # Free-form payload (thresholds, counters, model names, ...).
    metadata_json = Column(Text, nullable=True)

    # Aggregation counters.
    occurrence_count = Column(Integer, nullable=False, default=1)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Acknowledgment trail.
    acknowledged = Column(Boolean, nullable=False, default=False, index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_admin_alerts_dedupe_open", "dedupe_key", "acknowledged"),
        Index("ix_admin_alerts_category_ack", "category", "acknowledged"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "dedupe_key": self.dedupe_key,
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "related_user_id": self.related_user_id,
            "related_username": self.related_username,
            "metadata_json": self.metadata_json,
            "occurrence_count": self.occurrence_count,
            "first_seen_at": self.first_seen_at.isoformat() if self.first_seen_at else None,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
        }