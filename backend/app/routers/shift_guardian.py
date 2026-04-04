from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import ShiftGuardianAlert, WorkerProfile, Zone
from app.services.shift_guardian_service import generate_shift_recommendation, recommendation_to_api_dict

router = APIRouter(prefix="/shift-guardian", tags=["shift-guardian"])


@router.get("/recommendation/{worker_id}")
async def get_shift_recommendation(worker_id: int, db: Session = Depends(get_db)) -> dict:
    worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == worker_id))
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")

    zone = db.scalar(select(Zone).where(Zone.id == worker.primary_zone_id))
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")

    rec = await generate_shift_recommendation(
        worker_id=worker_id,
        current_zone=zone.zone_name,
        city=zone.city,
        avg_weekly_income=float(worker.avg_weekly_income),
        shift_type=worker.shift_type,
    )

    alert = ShiftGuardianAlert(
        worker_id=worker_id,
        zone_id=zone.id,
        alert_type=rec.alert_type,
        forecast_window=rec.forecast_window,
        risk_level=rec.risk_level,
        recommendation_text=rec.recommendation_text,
    )
    db.add(alert)
    db.commit()

    out = recommendation_to_api_dict(rec)
    out["worker_id"] = worker_id
    return out


@router.get("/history/{worker_id}")
def get_alert_history(worker_id: int, db: Session = Depends(get_db)) -> list[dict]:
    alerts = db.scalars(
        select(ShiftGuardianAlert)
        .where(ShiftGuardianAlert.worker_id == worker_id)
        .order_by(ShiftGuardianAlert.id.desc())
        .limit(20)
    ).all()
    return [
        {
            "id": a.id,
            "alert_type": a.alert_type,
            "forecast_window": a.forecast_window,
            "risk_level": a.risk_level,
            "recommendation_text": a.recommendation_text,
            "created_at": a.created_at,
        }
        for a in alerts
    ]
