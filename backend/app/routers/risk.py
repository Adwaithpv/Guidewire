from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import RiskProfile, WorkerProfile
from app.schemas.common import (
    LiveRiskFactors,
    QuoteExposureInputs,
    RiskQuoteLiveRequest,
    RiskQuoteLiveResponse,
    RiskQuoteRequest,
    RiskQuoteResponse,
)
from app.services.risk_service import (
    calculate_risk_score,
    fetch_live_risk_factors,
    get_risk_explanation,
    quote_max_payout,
    quote_premium,
    shift_type_to_exposure,
)

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/quote", response_model=RiskQuoteResponse)
def risk_quote(payload: RiskQuoteRequest, db: Session = Depends(get_db)) -> RiskQuoteResponse:
    worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == payload.worker_id))
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Use the worker's city from their zone
    from app.models.entities import Zone
    zone = db.scalar(select(Zone).where(Zone.id == worker.primary_zone_id))
    city = payload.city or (zone.city if zone else "Bengaluru")

    risk_score = calculate_risk_score(
        payload.rain_risk, payload.flood_risk, payload.aqi_risk,
        payload.closure_risk, payload.shift_exposure,
        worker.avg_weekly_income, city,
    )
    premium = quote_premium(
        payload.rain_risk,
        payload.flood_risk,
        payload.aqi_risk,
        payload.closure_risk,
        payload.shift_exposure,
        worker.avg_weekly_income,
        city,
    )
    max_payout = quote_max_payout(worker.avg_weekly_income)
    worker.risk_score = risk_score

    risk_profile = RiskProfile(
        worker_id=worker.id,
        rain_risk=payload.rain_risk,
        flood_risk=payload.flood_risk,
        aqi_risk=payload.aqi_risk,
        closure_risk=payload.closure_risk,
        shift_exposure=payload.shift_exposure,
        final_risk_score=risk_score,
        quoted_premium=premium,
        model_version="actuarial-gbm-blend-v1",
    )
    db.add(risk_profile)
    db.commit()

    risk_info = get_risk_explanation(city)
    return RiskQuoteResponse(
        risk_score=risk_score,
        premium_weekly=premium,
        max_weekly_payout=max_payout,
        confidence_level=0.87,
        explanation=risk_info["explanation"],
        feature_importances=risk_info["importances"],
        model_version="actuarial-gbm-blend-v1",
    )


@router.post("/quote-live", response_model=RiskQuoteLiveResponse)
async def risk_quote_live(payload: RiskQuoteLiveRequest, db: Session = Depends(get_db)) -> RiskQuoteLiveResponse:
    """Weekly premium quote using live weather + AQI for the worker's city (single round-trip)."""
    worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == payload.worker_id))
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")

    from app.models.entities import Zone

    zone = db.scalar(select(Zone).where(Zone.id == worker.primary_zone_id))
    city = zone.city if zone else "Bengaluru"

    live = await fetch_live_risk_factors(city)
    shift_exposure = shift_type_to_exposure(worker.shift_type)

    inner = RiskQuoteRequest(
        worker_id=payload.worker_id,
        city=city,
        rain_risk=live.rain_risk,
        flood_risk=live.flood_risk,
        aqi_risk=live.aqi_risk,
        closure_risk=live.closure_risk,
        shift_exposure=shift_exposure,
    )
    base = risk_quote(inner, db)
    return RiskQuoteLiveResponse(
        risk_score=base.risk_score,
        premium_weekly=base.premium_weekly,
        max_weekly_payout=base.max_weekly_payout,
        confidence_level=base.confidence_level,
        explanation=base.explanation,
        feature_importances=base.feature_importances,
        model_version=base.model_version,
        live_factors=live,
        quote_exposure_inputs=QuoteExposureInputs(
            rain_risk=live.rain_risk,
            flood_risk=live.flood_risk,
            aqi_risk=live.aqi_risk,
            closure_risk=live.closure_risk,
            shift_exposure=shift_exposure,
            city=city,
        ),
    )


@router.get("/profile/{worker_id}")
def get_risk_profile(worker_id: int, db: Session = Depends(get_db)) -> dict:
    profile = db.scalar(
        select(RiskProfile).where(RiskProfile.worker_id == worker_id).order_by(RiskProfile.id.desc())
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Risk profile not found")
    return {
        "worker_id": profile.worker_id,
        "risk_score": profile.final_risk_score,
        "quoted_premium": profile.quoted_premium,
        "model_version": profile.model_version,
    }


@router.get("/live-factors/{city}", response_model=LiveRiskFactors)
async def live_risk_factors(city: str) -> LiveRiskFactors:
    """Get real-time risk factors from weather + AQI APIs for a city."""
    return await fetch_live_risk_factors(city)
