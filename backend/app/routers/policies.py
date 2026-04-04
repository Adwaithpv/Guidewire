from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Policy, PolicyTrigger, WorkerProfile
from app.schemas.common import PolicyCreateRequest, PolicyQuoteRequest, PolicyQuoteResponse
from app.services.policy_service import coverage_window, default_triggers
from app.services.risk_service import fetch_live_risk_factors_sync, quote_premium, shift_type_to_exposure

router = APIRouter(prefix="/policies", tags=["policies"])


@router.post("/quote", response_model=PolicyQuoteResponse)
def policy_quote(payload: PolicyQuoteRequest, db: Session = Depends(get_db)) -> PolicyQuoteResponse:
    worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == payload.worker_id))
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    from app.models.entities import Zone

    zone = db.scalar(select(Zone).where(Zone.id == worker.primary_zone_id))
    city = zone.city if zone else "Bengaluru"
    live = fetch_live_risk_factors_sync(city)
    shift_exposure = shift_type_to_exposure(worker.shift_type)
    premium = quote_premium(
        live.rain_risk,
        live.flood_risk,
        live.aqi_risk,
        live.closure_risk,
        shift_exposure,
        worker.avg_weekly_income,
        city,
    )
    max_weekly_payout = round(worker.avg_weekly_income * 0.4, 2)
    return PolicyQuoteResponse(
        premium_weekly=premium,
        max_weekly_payout=max_weekly_payout,
        covered_events=["heavy_rain", "flood", "aqi_severe", "curfew", "platform_outage"],
        exclusions=["health", "life", "accident", "vehicle_repair"],
    )


@router.post("/create")
def create_policy(payload: PolicyCreateRequest, db: Session = Depends(get_db)) -> dict:
    worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == payload.worker_id))
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")

    start, end = coverage_window()
    policy = Policy(
        worker_id=payload.worker_id,
        premium_weekly=payload.premium_weekly,
        max_weekly_payout=payload.max_weekly_payout,
        coverage_start=start,
        coverage_end=end,
        status="active",
        auto_renew=payload.auto_renew,
    )
    db.add(policy)
    db.flush()
    for trigger_type, threshold in default_triggers():
        if trigger_type in payload.covered_events:
            db.add(
                PolicyTrigger(
                    policy_id=policy.id,
                    trigger_type=trigger_type,
                    threshold_value=threshold,
                    payout_formula_type="hour_based",
                )
            )
    db.commit()
    db.refresh(policy)
    return {"policy_id": policy.id, "status": policy.status}


@router.get("/{worker_id}")
def get_worker_policies(worker_id: int, db: Session = Depends(get_db)) -> list[dict]:
    policies = db.scalars(select(Policy).where(Policy.worker_id == worker_id).order_by(Policy.id.desc())).all()
    return [
        {
            "id": p.id,
            "premium_weekly": float(p.premium_weekly),
            "max_weekly_payout": float(p.max_weekly_payout),
            "coverage_start": p.coverage_start,
            "coverage_end": p.coverage_end,
            "status": p.status,
            "auto_renew": p.auto_renew,
        }
        for p in policies
    ]


@router.post("/renew")
def renew_policy(worker_id: int, db: Session = Depends(get_db)) -> dict:
    latest = db.scalar(
        select(Policy).where(and_(Policy.worker_id == worker_id, Policy.status == "active")).order_by(Policy.id.desc())
    )
    if latest is None:
        raise HTTPException(status_code=404, detail="No active policy")
    start, end = coverage_window(latest.coverage_end)
    renewed = Policy(
        worker_id=latest.worker_id,
        premium_weekly=latest.premium_weekly,
        max_weekly_payout=latest.max_weekly_payout,
        coverage_start=start,
        coverage_end=end,
        status="active",
        auto_renew=latest.auto_renew,
    )
    db.add(renewed)
    db.commit()
    db.refresh(renewed)
    return {"policy_id": renewed.id, "status": renewed.status}
