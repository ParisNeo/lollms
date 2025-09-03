# backend/db/models/fun_fact.py
from sqlalchemy import (
    Column, Integer, String, Boolean,
    ForeignKey, Text
)
from sqlalchemy.orm import relationship

from backend.db.base import Base

class FunFactCategory(Base):
    __tablename__ = "fun_fact_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    color = Column(String(7), default="#4299e1", nullable=False) # e.g., #RRGGBB
    
    fun_facts = relationship("FunFact", back_populates="category", cascade="all, delete-orphan")

class FunFact(Base):
    __tablename__ = "fun_facts"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    category_id = Column(Integer, ForeignKey("fun_fact_categories.id"), nullable=False, index=True)
    
    category = relationship("FunFactCategory", back_populates="fun_facts")