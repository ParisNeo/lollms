"""Admin API for the operational alert feed."""
import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.db.models.admin_alert import AdminAlert
from backend.admin_alerts import check_token_consumption, ensure_schema, emit_alert
from backend.session import get_current_admin_user
from backend.models import UserAuthDetails

alerts_management_router = APIRouter(tags=["Administration", "Alerts"])


@alerts_management_router.get("/alerts", response_model=List[dict])
async def list_alerts(
    status: str = Query("open", enum=["open", "acknowledged", "all"]),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_admin_user),
):
    """Return the alert feed, newest activity first."""
    ensure_schema(db)

    query = db.query(AdminAlert)
    if status == "open":
        query = query.filter(AdminAlert.acknowledged.is_(False))
    elif status == "acknowledged":
        query = query.filter(AdminAlert.acknowledged.is_(True))
    if category:
        query = query.filter(AdminAlert.category == category)
    if severity:
        query = query.filter(AdminAlert.severity == severity)

    rows = query.order_by(AdminAlert.last_seen_at.desc()).limit(limit).all()
    return [a.to_dict() for a in rows]


@alerts_management_router.get("/alerts/summary", response_model=dict)
async def alerts_summary(
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_admin_user),
):
    """Aggregate counters for the badge/banner and category chips."""
    ensure_schema(db)

    open_q = db.query(AdminAlert).filter(AdminAlert.acknowledged.is_(False))

    total_open = open_q.count()
    critical = open_q.filter(AdminAlert.severity == "critical").count()
    warning = open_q.filter(AdminAlert.severity == "warning").count()
    info = open_q.filter(AdminAlert.severity == "info").count()

    by_category = {
        cat: cnt
        for cat, cnt in db.query(AdminAlert.category, func.count(AdminAlert.id))
        .filter(AdminAlert.acknowledged.is_(False))
        .group_by(AdminAlert.category)
        .all()
    }

    return {
        "total": total_open,
        "open": total_open,
        "critical": critical,
        "warning": warning,
        "info": info,
        "by_category": by_category,
    }


@alerts_management_router.post("/alerts/{alert_id}/ack", response_model=dict)
async def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_admin_user),
):
    ensure_schema(db)
    alert = db.query(AdminAlert).filter(AdminAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    alert.acknowledged = True
    alert.acknowledged_at = datetime.datetime.now(datetime.timezone.utc)
    alert.acknowledged_by = current_user.username
    db.commit()
    return {"message": "Alert acknowledged."}


@alerts_management_router.post("/alerts/ack-all", response_model=dict)
async def acknowledge_all(
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_admin_user),
):
    ensure_schema(db)
    now = datetime.datetime.now(datetime.timezone.utc)
    count = (
        db.query(AdminAlert)
        .filter(AdminAlert.acknowledged.is_(False))
        .update({
            AdminAlert.acknowledged: True,
            AdminAlert.acknowledged_at: now,
            AdminAlert.acknowledged_by: current_user.username,
        }, synchronize_session=False)
    )
    db.commit()
    return {"message": f"{count} alert(s) acknowledged."}


@alerts_management_router.delete("/alerts/{alert_id}", response_model=dict)
async def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_admin_user),
):
    ensure_schema(db)
    alert = db.query(AdminAlert).filter(AdminAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    db.delete(alert)
    db.commit()
    return {"message": "Alert deleted."}


@alerts_management_router.post("/alerts/scan", response_model=dict)
async def scan_now(
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_admin_user),
):
    """Run the token-consumption scan immediately."""
    ensure_schema(db)
    try:
        result = check_token_consumption(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scan failed: {exc}")
    return result


@alerts_management_router.post("/alerts/test", response_model=dict)
async def emit_test_alert(
    db: Session = Depends(get_db),
    current_user: UserAuthDetails = Depends(get_current_admin_user),
):
    """Emit a synthetic info alert so admins can verify the delivery pipeline."""
    ensure_schema(db)
    emit_alert(
        db,
        dedupe_key=f"test_alert:{int(datetime.datetime.now().timestamp())}",
        category="system",
        severity="info",
        title="Test alert",
        message=f"Test alert triggered by {current_user.username}.",
    )
    return {"message": "Test alert emitted."}