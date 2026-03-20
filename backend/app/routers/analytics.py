from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.database import get_db
from app.models.entities import Claim, DisruptionEvent, Policy, Payout, WorkerProfile, Zone

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/kpis")
def kpis(db: Session = Depends(get_db)) -> dict:
    active_workers = db.scalar(select(func.count(WorkerProfile.id))) or 0
    active_policies = db.scalar(select(func.count(Policy.id)).where(Policy.status == "active")) or 0
    claims_count = db.scalar(select(func.count(Claim.id))) or 0
    payouts_count = db.scalar(select(func.count(Payout.id))) or 0
    payout_sum = db.scalar(select(func.coalesce(func.sum(Payout.amount), 0))) or 0
    premium_sum = db.scalar(select(func.coalesce(func.sum(Policy.premium_weekly), 0))) or 0
    prevented_loss_estimate = round(float(claims_count) * 45.0, 2)
    return {
        "active_workers": active_workers,
        "active_policies": active_policies,
        "claims_count": claims_count,
        "payouts_count": payouts_count,
        "premium_collected": float(premium_sum),
        "payout_made": float(payout_sum),
        "loss_ratio": float(payout_sum / premium_sum) if premium_sum else 0,
        "prevented_loss_estimate": prevented_loss_estimate,
    }


@router.get("/zone-heatmap")
def zone_heatmap(db: Session = Depends(get_db)) -> list[dict]:
    stmt = (
        select(Zone.zone_name, func.count(DisruptionEvent.id).label("event_count"))
        .join(DisruptionEvent, DisruptionEvent.zone_id == Zone.id, isouter=True)
        .group_by(Zone.zone_name)
        .order_by(func.count(DisruptionEvent.id).desc())
    )
    rows = db.execute(stmt).all()
    return [{"zone_name": row.zone_name, "event_count": row.event_count} for row in rows]


@router.get("/claims-by-trigger")
def claims_by_trigger(db: Session = Depends(get_db)) -> list[dict]:
    stmt = (
        select(DisruptionEvent.event_type, func.count(Claim.id).label("count"))
        .join(Claim, Claim.event_id == DisruptionEvent.id, isouter=True)
        .group_by(DisruptionEvent.event_type)
    )
    rows = db.execute(stmt).all()
    return [{"event_type": row.event_type, "count": row.count} for row in rows]
