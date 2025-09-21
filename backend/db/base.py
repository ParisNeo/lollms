# [UPDATE] backend/db/base.py
import enum
from sqlalchemy.orm import declarative_base
from sqlalchemy import (
    Table, Column, Integer, ForeignKey, DateTime
)
from sqlalchemy.sql import func

CURRENT_DB_VERSION = "1.7.1"

Base = declarative_base()

follows_table = Table('follows', Base.metadata,
    Column('follower_id', Integer, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True),
    Column('following_id', Integer, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True),
    Column('created_at', DateTime(timezone=True), server_default=func.now())
)

class PostVisibility(str, enum.Enum):
    public = "public"
    followers = "followers"
    friends = "friends"

class FriendshipStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED_BY_USER1 = "blocked_by_user1"
    BLOCKED_BY_USER2 = "blocked_by_user2"

class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"