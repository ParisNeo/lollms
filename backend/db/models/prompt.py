import uuid
from sqlalchemy import (
    Column, String, Text, ForeignKey, Integer
)
from sqlalchemy.orm import relationship

from backend.db.base import Base

class SavedPrompt(Base):
    __tablename__ = "saved_prompts"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    owner = relationship("User")