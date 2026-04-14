from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Claim, FraudCheck, Payout
from app.schemas.common import ClaimsSummary, ProcessClaimResponse
from app.services.fraud_service import evaluate_claim_fraud

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("/{worker_id}")
def get_claims(worker_id: int, db: Session = Depends(get_db)) -> list[dict]:
    claims = db.scalars(select(Claim).where(Claim.worker_id == worker_id).order_by(Claim.id.desc())).all()
    result = []
    for c in claims:
        fraud = db.scalar(select(FraudCheck).where(FraudCheck.claim_id == c.id))
        payout = db.scalar(select(Payout).where(Payout.claim_id == c.id))
        result.append({
            "id": c.id,
            "event_id": c.event_id,
            "claim_type": c.claim_type,
            "status": c.status,
            "estimated_loss": float(c.estimated_loss),
            "approved_payout": float(c.approved_payout),
            "auto_created": c.auto_created,
            "created_at": c.created_at,
            "fraud_score": round(fraud.final_fraud_score, 3) if fraud else None,
            "fraud_status": fraud.review_status if fraud else None,
            "payout_status": payout.status if payout else None,
            "payout_ref": payout.gateway_ref if payout else None,
            "payout_amount": float(payout.amount) if payout else None,
        })
    return result


@router.get("/summary/{worker_id}", response_model=ClaimsSummary)
def claims_summary(worker_id: int, db: Session = Depends(get_db)) -> ClaimsSummary:
    claims = db.scalars(select(Claim).where(Claim.worker_id == worker_id)).all()
    approved = [c for c in claims if c.status in ("approved", "paid")]
    pending = [c for c in claims if c.status in ("validation_pending", "fraud_check")]
    total_paid = 0.0
    for c in approved:
        p = db.scalar(select(Payout).where(Payout.claim_id == c.id, Payout.status == "success"))
        if p:
            total_paid += float(p.amount)
    return ClaimsSummary(
        worker_id=worker_id,
        total_claims=len(claims),
        approved_claims=len(approved),
        total_payout=round(total_paid if total_paid > 0 else sum(float(c.approved_payout) for c in approved), 2),
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

    result = evaluate_claim_fraud(db, claim_id)
    db.refresh(claim)
    return ProcessClaimResponse(claim_id=claim.id, status=claim.status, approved_payout=float(claim.approved_payout))
