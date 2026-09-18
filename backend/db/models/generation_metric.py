import uuid
import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Index
)
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from backend.db.base import Base

class GenerationMetric(Base):
    __tablename__ = "generation_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username = Column(String, nullable=True, index=True)
    model_name = Column(String, nullable=False, index=True)
    binding_name = Column(String, nullable=True, index=True)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    energy_kwh = Column(Float, default=0.0, nullable=False)
    co2_g = Column(Float, default=0.0, nullable=False)
    source = Column(String, default="chat", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index('ix_generation_metrics_created_user', 'created_at', 'user_id'),
    )

# Energy & Carbon conversion constants (0.0002 kWh / 1k tokens, 400g CO2 / kWh)
KWH_PER_TOKEN = 0.0000002
CO2_G_PER_KWH = 400.0

def calculate_co2_equivalents(co2_grams: float) -> Dict[str, float]:
    """Calculates tangible real-world carbon equivalences from CO2 in grams."""
    return {
        "car_km": round(co2_grams / 120.0, 2),
        "smartphone_charges": round(co2_grams / 8.22, 1),
        "tree_days": round(co2_grams / 60.27, 1),
        "led_bulb_hours": round((co2_grams / 400.0) * 100.0, 1)
    }

def record_generation_metric(
    db: Optional[Session] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    model_name: str = "unknown",
    binding_name: Optional[str] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    source: str = "chat"
):
    """
    Safely records a generation metric into the database without blocking or interrupting client turns.
    """
    total = max(0, prompt_tokens) + max(0, completion_tokens)
    energy = total * KWH_PER_TOKEN
    co2 = energy * CO2_G_PER_KWH

    clean_model = model_name or "unknown"
    clean_username = username or "anonymous"

    def _persist(session: Session):
        metric = GenerationMetric(
            user_id=user_id,
            username=clean_username,
            model_name=clean_model,
            binding_name=binding_name,
            prompt_tokens=max(0, prompt_tokens),
            completion_tokens=max(0, completion_tokens),
            total_tokens=total,
            energy_kwh=energy,
            co2_g=co2,
            source=source
        )
        session.add(metric)
        session.commit()

    if db and hasattr(db, 'is_active') and db.is_active:
        try:
            _persist(db)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
    else:
        try:
            from backend.db.session import SessionLocal
            temp_session = SessionLocal()
            try:
                _persist(temp_session)
            except Exception:
                temp_session.rollback()
            finally:
                temp_session.close()
        except Exception:
            pass