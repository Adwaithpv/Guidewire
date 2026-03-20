from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Claim, FraudCheck
from app.services.fraud_service import compute_fraud_score, review_status

router = APIRouter(prefix="/fraud", tags=["fraud"])


@router.post("/evaluate/{claim_id}")
def evaluate_claim_fraud(claim_id: int, db: Session = Depends(get_db)) -> dict:
    claim = db.scalar(select(Claim).where(Claim.id == claim_id))
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    duplicate = 1.0 if claim.status == "duplicate_rejected" else 0.0
    score = compute_fraud_score(
        gps_mismatch=0.1,
        duplicate_risk=duplicate,
        activity_absence=0.05,
        anomaly_pattern=0.05,
        source_conflict=0.03,
    )
    status = review_status(score)
    fraud = FraudCheck(
        claim_id=claim.id,
        gps_score=0.1,
        duplicate_score=duplicate,
        activity_score=0.05,
        anomaly_score=0.05,
        source_score=0.03,
        final_fraud_score=score,
        review_status=status,
    )
    db.add(fraud)

    if status == "manual_review":
        claim.status = "fraud_check"
    else:
        claim.status = "approved"
    db.commit()
    return {"claim_id": claim.id, "fraud_score": score, "review_status": status}


@router.get("/flags")
def fraud_flags(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(FraudCheck).order_by(FraudCheck.id.desc()).limit(100)).all()
    return [
        {
            "claim_id": row.claim_id,
            "final_fraud_score": row.final_fraud_score,
            "review_status": row.review_status,
        }
        for row in rows
    ]
