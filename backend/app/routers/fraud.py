"""
Phase 3 fraud detection router — advanced multi-signal evaluation.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Claim, FraudCheck
from app.services.fraud_service import evaluate_claim_fraud

router = APIRouter(prefix="/fraud", tags=["fraud"])


@router.post("/evaluate/{claim_id}")
def evaluate_fraud(claim_id: int, db: Session = Depends(get_db)) -> dict:
    """Run the full advanced fraud evaluation pipeline on a claim."""
    result = evaluate_claim_fraud(db, claim_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/flags")
def fraud_flags(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(FraudCheck).order_by(FraudCheck.id.desc()).limit(100)).all()
    return [
        {
            "claim_id": row.claim_id,
            "gps_score": round(row.gps_score, 3),
            "activity_score": round(row.activity_score, 3),
            "duplicate_score": round(row.duplicate_score, 3),
            "anomaly_score": round(row.anomaly_score, 3),
            "source_score": round(row.source_score, 3),
            "final_fraud_score": round(row.final_fraud_score, 3),
            "review_status": row.review_status,
        }
        for row in rows
    ]
