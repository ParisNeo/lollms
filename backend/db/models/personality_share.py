"""Metadata-only personality sharing ACL and selection preference.

The filesystem (handbag folders under data/personalities/) is the single
source of truth for personality content. These tables only record *who may
read which personal handbag* and *which handbag a user has selected* — never
prompt text, tools, skills, or RAG metadata.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint

from backend.db.base import Base


class PersonalityShareLink(Base):
    """Read-only sharing ACL: a personal handbag visible to a user or group."""

    __tablename__ = "personality_share_link"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    handbag_name = Column(String, nullable=False)
    shared_with_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    group_id = Column(String, nullable=True, index=True)
    permission = Column(String, nullable=False, default="read")

    __table_args__ = (
        UniqueConstraint(
            "owner_user_id", "handbag_name", "shared_with_user_id", "group_id",
            name="uq_personality_share",
        ),
    )


class UserPersonalityPreference(Base):
    """Pointer to the personality a user selected (scope + handbag name)."""

    __tablename__ = "user_personality_preference"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    scope = Column(String, nullable=False, default="global")  # global|personal|shared
    handbag_name = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # set when scope == shared