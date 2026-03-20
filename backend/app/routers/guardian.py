from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import ShiftGuardianAlert, WorkerProfile, Zone
from app.services.guardian_service import build_default_alert

router = APIRouter(prefix="/guardian", tags=["guardian"])


@router.get("/alerts/{worker_id}")
def get_alerts(worker_id: int, db: Session = Depends(get_db)) -> list[dict]:
    alerts = db.scalars(
        select(ShiftGuardianAlert).where(ShiftGuardianAlert.worker_id == worker_id).order_by(ShiftGuardianAlert.id.desc())
    ).all()
    if alerts:
        return [
            {
                "id": a.id,
                "alert_type": a.alert_type,
                "forecast_window": a.forecast_window,
                "risk_level": a.risk_level,
                "recommendation_text": a.recommendation_text,
            }
            for a in alerts
        ]

    worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == worker_id))
    if worker is None:
        return []
    zone = db.scalar(select(Zone).where(Zone.id == worker.primary_zone_id))
    generated = build_default_alert(zone.zone_name if zone else "your zone")
    row = ShiftGuardianAlert(worker_id=worker.id, zone_id=worker.primary_zone_id, **generated)
    db.add(row)
    db.commit()
    db.refresh(row)
    return [
        {
            "id": row.id,
            "alert_type": row.alert_type,
            "forecast_window": row.forecast_window,
            "risk_level": row.risk_level,
            "recommendation_text": row.recommendation_text,
        }
    ]
