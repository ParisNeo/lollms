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
        Index('ix_generation_metrics_user_id', 'user_id'),
        Index('ix_generation_metrics_username', 'username'),
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

def _maybe_alert_single_generation(
    *,
    user_id: Optional[int],
    username: str,
    model_name: str,
    total_tokens: int,
) -> None:
    """
    Emit an admin alert when ONE generation is abnormally large.

    Fail-safe: any error (config lookup, DB, missing settings) is swallowed so
    token telemetry can never break the generation path. The threshold is read
    from the ``alert_token_single_generation`` global setting (0 disables it).
    """
    if not total_tokens or total_tokens <= 0:
        return
    try:
        from backend.settings import settings as _settings
        try:
            threshold = int(_settings.get("alert_token_single_generation", 0) or 0)
        except (TypeError, ValueError):
            threshold = 0
        if threshold <= 0 or total_tokens < threshold:
            return

        from backend.db.session import SessionLocal
        from backend.admin_alerts import emit_alert

        alert_db = SessionLocal()
        try:
            emit_alert(
                alert_db,
                category="tokens",
                severity="warning",
                title=f"Unusually large generation by {username}",
                message=(
                    f"A single generation by '{username}' on model '{model_name}' "
                    f"consumed {total_tokens:,} tokens (threshold {threshold:,})."
                ),
                details={
                    "user_id": user_id,
                    "username": username,
                    "model_name": model_name,
                    "total_tokens": total_tokens,
                    "threshold": threshold,
                },
                source="token_monitor",
                dedupe_key=f"token_single_{user_id or username}",
                related_user_id=user_id,
                related_username=username,
            )
        finally:
            alert_db.close()
    except Exception:
        # Never surface telemetry failures into the caller.
        pass


def _maybe_alert_single_generation(db: Session, user_id: Optional[int], username: Optional[str],
                                   total: int, model_name: str) -> None:
    """
    Raise an admin alert when a single generation exceeds the configured limit.

    Fail-safe: any error is swallowed so telemetry recording is never disrupted.
    """
    try:
        from backend.settings import settings as settings_obj
        limit = int(settings_obj.get("alert_token_single_generation", 0) or 0)
        if limit <= 0 or total < limit:
            return
        from backend.admin_alerts import emit_alert
        emit_alert(
            db,
            dedupe_key=f"single_generation:{user_id}",
            category="tokens",
            severity="warning",
            title=f"Very large single generation ({total:,} tokens)",
            message=(
                f"A single '{model_name}' generation consumed {total:,} tokens "
                f"(threshold {limit:,})."
            ),
            related_user_id=user_id,
            related_username=username,
            metadata={"tokens": total, "limit": limit, "model": model_name},
        )
    except Exception:
        pass


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
        _maybe_alert_single_generation(session, user_id, clean_username, total, clean_model)

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