from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.db.base import Base, user_group_link

class Group(Base):
    __tablename__ = "user_groups"
    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, unique=True, index=True, nullable=True) # Kept for SCIM
    display_name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(Text, nullable=True)
    
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    owner = relationship("User")
    
    members = relationship("User", secondary=user_group_link, back_populates="groups")
