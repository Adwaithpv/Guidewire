from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import DataConsent, DisruptionEvent, Policy, PolicyTrigger, WorkerProfile, Zone
from app.schemas.common import (
    AllPlansQuoteResponse,
    PlanQuote,
    PolicyCreateRequest,
    PolicyQuoteRequest,
    PolicyQuoteResponse,
)
from app.services.pricing_service import (
    PLANS,
    blend_premium,
    exposure_index,
    quote_all_plans,
    risk_level_from_exposure,
)
from app.services.policy_service import coverage_window, default_triggers
from app.services.risk_service import fetch_live_risk_factors_sync, quote_premium, shift_type_to_exposure

router = APIRouter(prefix="/policies", tags=["policies"])


def _adverse_selection_lockout(
    db: Session,
    worker: WorkerProfile,
    city: str,
    zone_id: int | None,
) -> tuple[bool, str]:
    """
    Prevent purchases right after/near major disruptions (organizer checklist #8).
    """
    live = fetch_live_risk_factors_sync(city)
    if live.is_disruptive and (
        live.rain_risk >= 0.75
        or live.flood_risk >= 0.6
        or live.aqi_risk >= 0.75
        or live.closure_risk >= 0.4
    ):
        return True, "Policy purchase temporarily locked due to current high-severity disruption conditions."

    if zone_id is not None:
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=48)
        recent_zone_event = db.scalar(
            select(DisruptionEvent)
            .where(
                DisruptionEvent.zone_id == zone_id,
                DisruptionEvent.started_at >= since,
                DisruptionEvent.event_type.in_(["heavy_rain", "flood", "aqi_severe", "curfew", "platform_outage"]),
                DisruptionEvent.severity.in_(["high", "severe"]),
            )
            .order_by(DisruptionEvent.id.desc())
        )
        if recent_zone_event is not None:
            return (
                True,
                "Policy purchase is locked for 48 hours after a severe local disruption alert.",
            )

    return False, ""


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


@router.post("/quote-plans", response_model=AllPlansQuoteResponse)
def policy_quote_plans(
    worker_id: int = Query(...),
    db: Session = Depends(get_db),
) -> AllPlansQuoteResponse:
    worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == worker_id))
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    from app.ml.premium_model import model as ml_model
    from app.models.entities import Zone

    zone = db.scalar(select(Zone).where(Zone.id == worker.primary_zone_id))
    city = zone.city if zone else "Bengaluru"
    live = fetch_live_risk_factors_sync(city)
    shift_exposure = shift_type_to_exposure(worker.shift_type)

    composite = exposure_index(
        live.rain_risk,
        live.flood_risk,
        live.aqi_risk,
        live.closure_risk,
        shift_exposure,
        city,
    )
    risk_level = risk_level_from_exposure(composite)

    ml_premium = ml_model.predict_premium(
        live.rain_risk,
        live.flood_risk,
        live.aqi_risk,
        live.closure_risk,
        shift_exposure,
        worker.avg_weekly_income,
        city,
    )
    actuarial_plans = quote_all_plans(
        live.rain_risk,
        live.flood_risk,
        live.aqi_risk,
        live.closure_risk,
        shift_exposure,
        worker.avg_weekly_income,
        city,
    )
    plans: list[PlanQuote] = []
    for p in actuarial_plans:
        plan_cfg = PLANS[p["plan_id"]]
        blended = blend_premium(
            actuarial=float(p["premium_weekly"]),
            ml_premium=ml_premium,
            floor=float(plan_cfg["min_premium"]),
            ceiling=float(plan_cfg["max_premium"]),
            ml_weight=0.20,
        )
        plans.append(
            PlanQuote(
                plan_id=p["plan_id"],
                label=p["label"],
                description=p["description"],
                premium_weekly=blended,
                max_weekly_payout=float(p["max_weekly_payout"]),
                coverage_pct=float(p["coverage_pct"]),
                risk_rate_pct=float(p["risk_rate_pct"]),
                at_floor=bool(blended <= float(plan_cfg["min_premium"])),
                at_ceiling=bool(blended >= float(plan_cfg["max_premium"])),
            )
        )

    return AllPlansQuoteResponse(
        worker_id=worker_id,
        city=city,
        composite_risk=round(composite, 4),
        risk_level=risk_level,
        plans=plans,
        covered_events=["heavy_rain", "flood", "aqi_severe", "curfew", "platform_outage"],
        exclusions=["health", "life", "accident", "vehicle_repair"],
        live_factors=live,
        fetched_at=live.fetched_at,
    )


def _supersede_active_policies(db: Session, worker_id: int) -> None:
    """Only one active policy per worker; older rows become superseded (prevents duplicate claims per event)."""
    for p in db.scalars(
        select(Policy).where(and_(Policy.worker_id == worker_id, Policy.status == "active"))
    ).all():
        p.status = "superseded"


@router.post("/create")
def create_policy(payload: PolicyCreateRequest, db: Session = Depends(get_db)) -> dict:
    worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == payload.worker_id))
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")

    zone = db.scalar(select(Zone).where(Zone.id == worker.primary_zone_id))
    city = zone.city if zone else "Bengaluru"

    consent = db.scalar(select(DataConsent).where(DataConsent.worker_id == worker.id))
    if consent is not None:
        if not (consent.gps_consent and consent.upi_consent and consent.platform_data_consent):
            raise HTTPException(
                status_code=400,
                detail="Required data consents (GPS, UPI, and platform activity) are needed before policy activation.",
            )
    else:
        # Backward-compatible fallback for older profiles created before consent table.
        if not worker.gps_enabled or not worker.payout_upi:
            raise HTTPException(
                status_code=400,
                detail="Enable GPS and provide UPI details before policy activation.",
            )

    locked, reason = _adverse_selection_lockout(
        db,
        worker=worker,
        city=city,
        zone_id=worker.primary_zone_id,
    )
    if locked:
        raise HTTPException(status_code=423, detail=reason)

    _supersede_active_policies(db, payload.worker_id)

    start, end = coverage_window()
    policy = Policy(
        worker_id=payload.worker_id,
        plan_name=payload.plan_id,
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

    try:
        from app.services.whatsapp_service import notify_policy_activated
        user = worker.user
        plan_labels = {"basic": "Basic Shield", "standard": "Standard Shield", "full": "Full Shield"}
        if user and user.phone:
            notify_policy_activated(
                to_phone=user.phone,
                worker_name=user.name,
                plan_label=plan_labels.get(payload.plan_id, payload.plan_id),
                premium=float(policy.premium_weekly),
                max_payout=float(policy.max_weekly_payout),
                zone_name=zone.zone_name if zone else "your zone",
            )
    except Exception:
        pass

    return {"policy_id": policy.id, "status": policy.status}


@router.get("/{worker_id}")
def get_worker_policies(worker_id: int, db: Session = Depends(get_db)) -> list[dict]:
    policies = db.scalars(select(Policy).where(Policy.worker_id == worker_id).order_by(Policy.id.desc())).all()
    return [
        {
            "id": p.id,
            "plan_name": p.plan_name,
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
    old_triggers = db.scalars(select(PolicyTrigger).where(PolicyTrigger.policy_id == latest.id)).all()
    latest.status = "superseded"
    start, end = coverage_window(latest.coverage_end)
    renewed = Policy(
        worker_id=latest.worker_id,
        plan_name=latest.plan_name,
        premium_weekly=latest.premium_weekly,
        max_weekly_payout=latest.max_weekly_payout,
        coverage_start=start,
        coverage_end=end,
        status="active",
        auto_renew=latest.auto_renew,
    )
    db.add(renewed)
    db.flush()
    for t in old_triggers:
        db.add(
            PolicyTrigger(
                policy_id=renewed.id,
                trigger_type=t.trigger_type,
                threshold_value=t.threshold_value,
                payout_formula_type=t.payout_formula_type,
            )
        )
    db.commit()
    db.refresh(renewed)
    return {"policy_id": renewed.id, "status": renewed.status}
