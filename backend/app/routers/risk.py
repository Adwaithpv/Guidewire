from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import RiskProfile, WorkerProfile
from app.schemas.common import RiskQuoteRequest, RiskQuoteResponse
from app.services.risk_service import calculate_risk_score, quote_max_payout, quote_premium

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/quote", response_model=RiskQuoteResponse)
def risk_quote(payload: RiskQuoteRequest, db: Session = Depends(get_db)) -> RiskQuoteResponse:
    worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == payload.worker_id))
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")

    risk_score = calculate_risk_score(
        payload.rain_risk, payload.flood_risk, payload.aqi_risk, payload.closure_risk, payload.shift_exposure
    )
    premium = quote_premium(risk_score)
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
    )
    db.add(risk_profile)
    db.commit()

    explanation = "Premium is driven by zone exposure and shift disruption probability."
    return RiskQuoteResponse(
        risk_score=risk_score,
        premium_weekly=premium,
        max_weekly_payout=max_payout,
        confidence_level=0.81,
        explanation=explanation,
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
