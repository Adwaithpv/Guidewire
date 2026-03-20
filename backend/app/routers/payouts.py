from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Claim, Payout
from app.services.payout_service import mock_gateway_transfer

router = APIRouter(prefix="/payouts", tags=["payouts"])


@router.post("/initiate/{claim_id}")
def initiate_payout(claim_id: int, db: Session = Depends(get_db)) -> dict:
    claim = db.scalar(select(Claim).where(Claim.id == claim_id))
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.status not in {"approved", "payout_processing", "paid"}:
        raise HTTPException(status_code=400, detail="Claim is not approved for payout")

    payout = Payout(
        claim_id=claim.id,
        worker_id=claim.worker_id,
        amount=float(claim.approved_payout),
        method="upi",
        status="pending",
    )
    db.add(payout)
    db.flush()

    transfer = mock_gateway_transfer(float(claim.approved_payout))
    payout.status = "success" if transfer["status"] == "success" else "failed"
    payout.gateway_ref = transfer["transaction_id"]
    payout.completed_at = datetime.utcnow()
    claim.status = "paid" if payout.status == "success" else "payout_processing"
    db.commit()
    return {"payout_id": payout.id, "status": payout.status, "gateway_ref": payout.gateway_ref}


@router.get("/{worker_id}")
def get_payouts(worker_id: int, db: Session = Depends(get_db)) -> list[dict]:
    payouts = db.scalars(select(Payout).where(Payout.worker_id == worker_id).order_by(Payout.id.desc())).all()
    return [
        {
            "id": p.id,
            "claim_id": p.claim_id,
            "amount": float(p.amount),
            "method": p.method,
            "status": p.status,
            "gateway_ref": p.gateway_ref,
            "completed_at": p.completed_at,
        }
        for p in payouts
    ]
