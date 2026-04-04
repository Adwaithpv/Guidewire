from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Claim
from app.schemas.common import ClaimsSummary, ProcessClaimResponse
from app.services.fraud_service import compute_fraud_score, review_status

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("/{worker_id}")
def get_claims(worker_id: int, db: Session = Depends(get_db)) -> list[dict]:
    claims = db.scalars(select(Claim).where(Claim.worker_id == worker_id).order_by(Claim.id.desc())).all()
    return [
        {
            "id": c.id,
            "event_id": c.event_id,
            "claim_type": c.claim_type,
            "status": c.status,
            "estimated_loss": float(c.estimated_loss),
            "approved_payout": float(c.approved_payout),
            "auto_created": c.auto_created,
            "created_at": c.created_at,
        }
        for c in claims
    ]


@router.get("/summary/{worker_id}", response_model=ClaimsSummary)
def claims_summary(worker_id: int, db: Session = Depends(get_db)) -> ClaimsSummary:
    claims = db.scalars(select(Claim).where(Claim.worker_id == worker_id)).all()
    approved = [c for c in claims if c.status == "approved"]
    pending = [c for c in claims if c.status in ("validation_pending", "fraud_check")]
    return ClaimsSummary(
        worker_id=worker_id,
        total_claims=len(claims),
        approved_claims=len(approved),
        total_payout=round(sum(float(c.approved_payout) for c in approved), 2),
        pending_claims=len(pending),
    )


@router.post("/manual-review/{claim_id}")
def manual_review(claim_id: int, db: Session = Depends(get_db)) -> dict:
    claim = db.scalar(select(Claim).where(Claim.id == claim_id))
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    claim.status = "approved"
    db.commit()
    return {"claim_id": claim_id, "status": "approved"}


@router.post("/process/{claim_id}", response_model=ProcessClaimResponse)
def process_claim(claim_id: int, db: Session = Depends(get_db)) -> ProcessClaimResponse:
    claim = db.scalar(select(Claim).where(Claim.id == claim_id))
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    duplicate_risk = 1.0 if claim.status == "duplicate_rejected" else 0.0
    fraud_score = compute_fraud_score(
        gps_mismatch=0.1, duplicate_risk=duplicate_risk, activity_absence=0.05, anomaly_pattern=0.02, source_conflict=0.05
    )
    status = review_status(fraud_score)
    claim.status = "approved" if status != "manual_review" else "fraud_check"
    db.commit()
    db.refresh(claim)
    return ProcessClaimResponse(claim_id=claim.id, status=claim.status, approved_payout=float(claim.approved_payout))
