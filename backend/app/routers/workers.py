from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import User, WorkerProfile, Zone
from app.schemas.common import WorkerProfileCreate, WorkerProfileResponse

router = APIRouter(prefix="/workers", tags=["workers"])


@router.post("/profile", response_model=WorkerProfileResponse)
def create_worker_profile(payload: WorkerProfileCreate, db: Session = Depends(get_db)) -> WorkerProfileResponse:
    zone = db.scalar(select(Zone).where(Zone.zone_name == payload.primary_zone))
    if zone is None:
        zone = Zone(city=payload.city, zone_name=payload.primary_zone, default_risk_level=0.35)
        db.add(zone)
        db.flush()

    user = db.scalar(select(User).where(User.phone == payload.phone))
    if user is None:
        user = User(name=payload.name, phone=payload.phone, email=payload.email, city=payload.city)
        db.add(user)
        db.flush()

    profile = db.scalar(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    if profile is None:
        profile = WorkerProfile(
            user_id=user.id,
            persona_type=payload.persona_type,
            platform_name=payload.platform_name,
            avg_weekly_income=payload.avg_weekly_income,
            primary_zone_id=zone.id,
            shift_type=payload.shift_type,
            gps_enabled=payload.gps_enabled,
            payout_upi=payload.payout_upi,
            risk_score=zone.default_risk_level,
        )
        db.add(profile)
    else:
        profile.persona_type = payload.persona_type
        profile.platform_name = payload.platform_name
        profile.avg_weekly_income = payload.avg_weekly_income
        profile.primary_zone_id = zone.id
        profile.shift_type = payload.shift_type
        profile.gps_enabled = payload.gps_enabled
        profile.payout_upi = payload.payout_upi

    db.commit()
    db.refresh(profile)
    return WorkerProfileResponse(worker_id=profile.id, user_id=user.id, risk_score=profile.risk_score)


@router.get("/profile/{worker_id}")
def get_worker_profile(worker_id: int, db: Session = Depends(get_db)) -> dict:
    profile = db.scalar(select(WorkerProfile).where(WorkerProfile.id == worker_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Worker not found")
    zone = db.scalar(select(Zone).where(Zone.id == profile.primary_zone_id))
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "persona_type": profile.persona_type,
        "platform_name": profile.platform_name,
        "avg_weekly_income": profile.avg_weekly_income,
        "zone_name": zone.zone_name if zone else None,
        "shift_type": profile.shift_type,
        "risk_score": profile.risk_score,
    }
