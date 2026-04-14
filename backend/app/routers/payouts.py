"""
Phase 3 instant payout router — Razorpay test-mode style.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Claim, Payout, WorkerProfile
from app.services.payout_service import mock_razorpay_transfer

router = APIRouter(prefix="/payouts", tags=["payouts"])


@router.post("/initiate/{claim_id}")
def initiate_payout(claim_id: int, db: Session = Depends(get_db)) -> dict:
    claim = db.scalar(select(Claim).where(Claim.id == claim_id))
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.status not in {"approved", "payout_processing", "paid"}:
        raise HTTPException(status_code=400, detail="Claim is not approved for payout")

    worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == claim.worker_id))
    worker_upi = worker.payout_upi if worker else ""
    worker_name = ""
    if worker and worker.user:
        worker_name = worker.user.name

    gateway = mock_razorpay_transfer(
        amount=float(claim.approved_payout),
        worker_upi=worker_upi,
        worker_name=worker_name,
    )

    payout = Payout(
        claim_id=claim.id,
        worker_id=claim.worker_id,
        amount=float(claim.approved_payout),
        method="upi",
        status="success" if gateway["status"] == "captured" else "failed",
        gateway_ref=gateway["payment_id"],
        initiated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        completed_at=datetime.now(timezone.utc).replace(tzinfo=None) if gateway["status"] == "captured" else None,
    )
    db.add(payout)

    if payout.status == "success":
        claim.status = "paid"
    db.commit()
    db.refresh(payout)

    return {
        "payout_id": payout.id,
        "status": payout.status,
        "gateway_ref": payout.gateway_ref,
        "gateway_response": gateway,
    }


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
            "initiated_at": p.initiated_at.isoformat() if p.initiated_at else None,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        }
        for p in payouts
    ]
