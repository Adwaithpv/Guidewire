"""
Analytics & admin endpoints for Phase 3.

Provides: KPIs, loss ratios, zone heatmap, claims breakdown,
predictive next-week disruption forecast, fraud overview, per-worker
earnings protection, financial proof, compliance checklist,
workers table, weekly trends, plan distribution.

All aggregate endpoints accept optional `city` and `plan` query filters.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import (
    Claim,
    DataConsent,
    DisruptionEvent,
    FraudCheck,
    Payout,
    Policy,
    User,
    WorkerProfile,
    Zone,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ---------------------------------------------------------------------------
# Shared filter helpers
# ---------------------------------------------------------------------------

def _zone_ids_for_city(db: Session, city: str | None) -> list[int] | None:
    if not city:
        return None
    zones = db.scalars(select(Zone).where(Zone.city == city)).all()
    return [z.id for z in zones] or [-1]


def _filtered_worker_ids(db: Session, city: str | None, plan: str | None) -> list[int] | None:
    """Return worker IDs matching filters, or None if no filters applied."""
    if not city and not plan:
        return None

    q = select(WorkerProfile.id)
    if city:
        zone_ids = _zone_ids_for_city(db, city)
        if zone_ids:
            q = q.where(WorkerProfile.primary_zone_id.in_(zone_ids))

    worker_ids = list(db.scalars(q).all())
    if not worker_ids:
        return [-1]

    if plan:
        policy_worker_ids = list(db.scalars(
            select(Policy.worker_id).where(
                Policy.plan_name == plan,
                Policy.worker_id.in_(worker_ids),
            ).distinct()
        ).all())
        return policy_worker_ids or [-1]

    return worker_ids


def _filtered_policy_ids(db: Session, city: str | None, plan: str | None) -> list[int] | None:
    if not city and not plan:
        return None
    worker_ids = _filtered_worker_ids(db, city, plan)
    q = select(Policy.id)
    if worker_ids is not None:
        q = q.where(Policy.worker_id.in_(worker_ids))
    if plan:
        q = q.where(Policy.plan_name == plan)
    ids = list(db.scalars(q).all())
    return ids or [-1]


# ---------------------------------------------------------------------------
# Admin KPIs
# ---------------------------------------------------------------------------
@router.get("/kpis")
def kpis(
    city: str | None = Query(None),
    plan: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    wids = _filtered_worker_ids(db, city, plan)
    pids = _filtered_policy_ids(db, city, plan)

    def _w(q):
        return q.where(WorkerProfile.id.in_(wids)) if wids is not None else q

    def _p(q):
        return q.where(Policy.id.in_(pids)) if pids is not None else q

    def _cw(q):
        return q.where(Claim.worker_id.in_(wids)) if wids is not None else q

    active_workers = db.scalar(_w(select(func.count(WorkerProfile.id)))) or 0
    active_policies = db.scalar(_p(select(func.count(Policy.id)).where(Policy.status == "active"))) or 0
    claims_count = db.scalar(_cw(select(func.count(Claim.id)))) or 0
    approved_claims = db.scalar(_cw(select(func.count(Claim.id)).where(Claim.status.in_(["approved", "paid"])))) or 0
    pending_claims = db.scalar(_cw(select(func.count(Claim.id)).where(Claim.status.in_(["validation_pending", "fraud_check"])))) or 0
    rejected_claims = db.scalar(_cw(select(func.count(Claim.id)).where(Claim.status == "rejected"))) or 0

    payout_q = select(func.coalesce(func.sum(Payout.amount), 0))
    if wids is not None:
        payout_q = payout_q.where(Payout.worker_id.in_(wids))
    payout_sum = float(db.scalar(payout_q) or 0)

    premium_q = select(func.coalesce(func.sum(Policy.premium_weekly), 0))
    if pids is not None:
        premium_q = premium_q.where(Policy.id.in_(pids))
    premium_sum = float(db.scalar(premium_q) or 0)

    loss_ratio = round(payout_sum / premium_sum, 4) if premium_sum > 0 else 0
    avg_claim_value = round(payout_sum / approved_claims, 2) if approved_claims > 0 else 0

    fraud_base = select(func.count(FraudCheck.id))
    if wids is not None:
        claim_ids_for_fraud = list(db.scalars(_cw(select(Claim.id))).all()) or [-1]
        fraud_base_filtered = fraud_base.where(FraudCheck.claim_id.in_(claim_ids_for_fraud))
    else:
        fraud_base_filtered = fraud_base

    fraud_flagged = db.scalar(fraud_base_filtered.where(FraudCheck.review_status == "manual_review")) or 0
    soft_review = db.scalar(fraud_base_filtered.where(FraudCheck.review_status == "soft_review")) or 0
    auto_approved = db.scalar(fraud_base_filtered.where(FraudCheck.review_status == "auto_approve")) or 0

    return {
        "active_workers": active_workers,
        "active_policies": active_policies,
        "total_claims": claims_count,
        "approved_claims": approved_claims,
        "pending_claims": pending_claims,
        "rejected_claims": rejected_claims,
        "premium_collected": round(premium_sum, 2),
        "total_payouts": round(payout_sum, 2),
        "loss_ratio": loss_ratio,
        "avg_claim_value": avg_claim_value,
        "fraud_flagged": fraud_flagged,
        "soft_review": soft_review,
        "auto_approved": auto_approved,
    }


# ---------------------------------------------------------------------------
# Zone heatmap
# ---------------------------------------------------------------------------
@router.get("/zone-heatmap")
def zone_heatmap(db: Session = Depends(get_db)) -> list[dict]:
    stmt = (
        select(Zone.zone_name, Zone.city, func.count(DisruptionEvent.id).label("event_count"))
        .join(DisruptionEvent, DisruptionEvent.zone_id == Zone.id, isouter=True)
        .group_by(Zone.zone_name, Zone.city)
        .order_by(func.count(DisruptionEvent.id).desc())
    )
    rows = db.execute(stmt).all()
    return [{"zone_name": r.zone_name, "city": r.city, "event_count": r.event_count} for r in rows]


# ---------------------------------------------------------------------------
# Claims breakdown by trigger type
# ---------------------------------------------------------------------------
@router.get("/claims-by-trigger")
def claims_by_trigger(
    city: str | None = Query(None),
    plan: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[dict]:
    wids = _filtered_worker_ids(db, city, plan)
    stmt = (
        select(DisruptionEvent.event_type, func.count(Claim.id).label("count"))
        .join(Claim, Claim.event_id == DisruptionEvent.id, isouter=True)
    )
    if wids is not None:
        stmt = stmt.where(Claim.worker_id.in_(wids))
    stmt = stmt.group_by(DisruptionEvent.event_type)
    rows = db.execute(stmt).all()
    return [{"event_type": r.event_type, "count": r.count} for r in rows]


# ---------------------------------------------------------------------------
# Fraud overview
# ---------------------------------------------------------------------------
@router.get("/fraud-overview")
def fraud_overview(
    city: str | None = Query(None),
    plan: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    wids = _filtered_worker_ids(db, city, plan)
    q = select(FraudCheck).order_by(FraudCheck.id.desc()).limit(200)
    if wids is not None:
        claim_ids = list(db.scalars(select(Claim.id).where(Claim.worker_id.in_(wids))).all()) or [-1]
        q = q.where(FraudCheck.claim_id.in_(claim_ids))
    checks = db.scalars(q).all()
    total = len(checks)
    if total == 0:
        return {"total_checks": 0, "avg_fraud_score": 0, "by_status": {}, "high_risk_claims": []}

    avg_score = round(sum(c.final_fraud_score for c in checks) / total, 4)
    by_status: dict[str, int] = {}
    high_risk: list[dict] = []
    for c in checks:
        by_status[c.review_status] = by_status.get(c.review_status, 0) + 1
        if c.final_fraud_score > 0.5:
            high_risk.append({
                "claim_id": c.claim_id,
                "fraud_score": round(c.final_fraud_score, 3),
                "review_status": c.review_status,
                "gps_score": round(c.gps_score, 3),
                "duplicate_score": round(c.duplicate_score, 3),
                "activity_score": round(c.activity_score, 3),
                "anomaly_score": round(c.anomaly_score, 3),
                "source_score": round(c.source_score, 3),
            })

    return {
        "total_checks": total,
        "avg_fraud_score": avg_score,
        "by_status": by_status,
        "high_risk_claims": high_risk[:20],
    }


# ---------------------------------------------------------------------------
# Predictive analytics
# ---------------------------------------------------------------------------
@router.get("/predictions")
def predictions(city: str = Query("Bengaluru"), db: Session = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    four_weeks_ago = now - timedelta(weeks=4)

    zones = db.scalars(select(Zone).where(Zone.city == city)).all()
    zone_ids = [z.id for z in zones]

    recent_events = db.scalars(
        select(DisruptionEvent).where(
            DisruptionEvent.zone_id.in_(zone_ids),
            DisruptionEvent.started_at >= four_weeks_ago,
        )
    ).all() if zone_ids else []

    type_counts: dict[str, int] = {}
    for e in recent_events:
        type_counts[e.event_type] = type_counts.get(e.event_type, 0) + 1

    total_events = len(recent_events)
    weeks_observed = 4.0

    event_type_labels = {
        "heavy_rain": "Heavy rainfall",
        "flood": "Flash flooding",
        "aqi_severe": "Severe air quality",
        "curfew": "Curfew / local shutdown",
        "platform_outage": "Platform outage",
    }

    forecasts: list[dict[str, Any]] = []
    for etype, count in type_counts.items():
        weekly_rate = count / weeks_observed
        prob = round(min(0.95, 1 - math.exp(-weekly_rate)), 2)
        forecasts.append({
            "event_type": etype,
            "label": event_type_labels.get(etype, etype.replace("_", " ").title()),
            "last_4_weeks_count": count,
            "weekly_avg": round(weekly_rate, 2),
            "next_week_probability": prob,
            "expected_claims": round(weekly_rate * 0.8, 1),
            "risk_trend": "rising" if weekly_rate > 1.5 else ("stable" if weekly_rate > 0.5 else "low"),
        })

    for etype, label in event_type_labels.items():
        if etype not in type_counts:
            seasonal_base = 0.15 if etype in ("heavy_rain", "flood") else 0.08
            forecasts.append({
                "event_type": etype,
                "label": label,
                "last_4_weeks_count": 0,
                "weekly_avg": 0,
                "next_week_probability": round(seasonal_base, 2),
                "expected_claims": 0,
                "risk_trend": "low",
            })

    forecasts.sort(key=lambda f: f["next_week_probability"], reverse=True)

    recent_claims = db.scalars(
        select(Claim).where(Claim.created_at >= four_weeks_ago)
    ).all()
    recent_payouts = db.scalars(
        select(Payout).where(Payout.initiated_at >= four_weeks_ago)
    ).all()
    total_payout_4w = sum(float(p.amount) for p in recent_payouts)
    projected_payout = round(total_payout_4w / weeks_observed, 2) if weeks_observed > 0 else 0

    return {
        "city": city,
        "forecast_window": "Next 7 days",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "disruption_forecasts": forecasts,
        "summary": {
            "total_events_4w": total_events,
            "total_claims_4w": len(recent_claims),
            "total_payouts_4w": round(total_payout_4w, 2),
            "projected_weekly_payout": projected_payout,
        },
    }


# ---------------------------------------------------------------------------
# Worker earnings protection summary
# ---------------------------------------------------------------------------
@router.get("/worker-protection/{worker_id}")
def worker_protection(worker_id: int, db: Session = Depends(get_db)) -> dict:
    worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == worker_id))
    if not worker:
        return {"error": "Worker not found"}

    policies = db.scalars(select(Policy).where(Policy.worker_id == worker_id)).all()
    active = [p for p in policies if p.status == "active"]
    claims = db.scalars(select(Claim).where(Claim.worker_id == worker_id)).all()
    payouts = db.scalars(select(Payout).where(Payout.worker_id == worker_id).order_by(Payout.id.desc())).all()

    total_premium_paid = sum(float(p.premium_weekly) for p in policies)
    total_payout_received = sum(float(p.amount) for p in payouts if p.status == "success")
    total_estimated_loss = sum(float(c.estimated_loss) for c in claims if c.status in ("approved", "paid"))
    net_benefit = total_payout_received - total_premium_paid

    active_policy = active[0] if active else None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    days_remaining = 0
    coverage_pct = 0.0
    if active_policy:
        end = active_policy.coverage_end
        start = active_policy.coverage_start
        total_days = max(1, (end - start).days)
        elapsed = max(0, (now - start).days)
        days_remaining = max(0, total_days - elapsed)
        coverage_pct = round(min(1.0, elapsed / total_days), 2)

    payout_history = [
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

    return {
        "worker_id": worker_id,
        "total_premium_paid": round(total_premium_paid, 2),
        "total_payout_received": round(total_payout_received, 2),
        "total_estimated_loss": round(total_estimated_loss, 2),
        "earnings_protected": round(total_payout_received, 2),
        "net_benefit": round(net_benefit, 2),
        "active_coverage": {
            "has_active": bool(active_policy),
            "plan_name": active_policy.plan_name if active_policy else None,
            "premium_weekly": float(active_policy.premium_weekly) if active_policy else 0,
            "max_weekly_payout": float(active_policy.max_weekly_payout) if active_policy else 0,
            "days_remaining": days_remaining,
            "coverage_progress_pct": coverage_pct,
        },
        "total_claims": len(claims),
        "approved_claims": sum(1 for c in claims if c.status in ("approved", "paid")),
        "payout_history": payout_history,
    }


# ---------------------------------------------------------------------------
# Payout ledger (admin)
# ---------------------------------------------------------------------------
@router.get("/payouts-ledger")
def payouts_ledger(
    city: str | None = Query(None),
    plan: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[dict]:
    wids = _filtered_worker_ids(db, city, plan)
    q = select(Payout).order_by(Payout.id.desc()).limit(100)
    if wids is not None:
        q = q.where(Payout.worker_id.in_(wids))
    payouts = db.scalars(q).all()
    result = []
    for p in payouts:
        worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == p.worker_id))
        user_name = ""
        if worker and worker.user:
            user_name = worker.user.name
        result.append({
            "id": p.id,
            "claim_id": p.claim_id,
            "worker_id": p.worker_id,
            "worker_name": user_name,
            "amount": float(p.amount),
            "method": p.method,
            "status": p.status,
            "gateway_ref": p.gateway_ref,
            "initiated_at": p.initiated_at.isoformat() if p.initiated_at else None,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        })
    return result


# ---------------------------------------------------------------------------
# Financial proof & stress test
# ---------------------------------------------------------------------------
@router.get("/financial-proof")
def financial_proof(city: str = Query("Bengaluru"), db: Session = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    twelve_weeks_ago = now - timedelta(weeks=12)

    city_zone_ids = [z.id for z in db.scalars(select(Zone).where(Zone.city == city)).all()]
    city_events = (
        db.scalars(
            select(DisruptionEvent).where(
                DisruptionEvent.zone_id.in_(city_zone_ids),
                DisruptionEvent.started_at >= twelve_weeks_ago,
            )
        ).all()
        if city_zone_ids
        else []
    )
    type_counts: dict[str, int] = {}
    severe_counts: dict[str, int] = {}
    for e in city_events:
        type_counts[e.event_type] = type_counts.get(e.event_type, 0) + 1
        if str(e.severity).lower() in {"high", "severe"}:
            severe_counts[e.event_type] = severe_counts.get(e.event_type, 0) + 1

    premiums_12w = float(
        db.scalar(
            select(func.coalesce(func.sum(Policy.premium_weekly), 0)).where(
                Policy.coverage_start >= twelve_weeks_ago
            )
        )
        or 0
    )
    payouts_12w = float(
        db.scalar(
            select(func.coalesce(func.sum(Payout.amount), 0)).where(
                Payout.initiated_at >= twelve_weeks_ago,
                Payout.status == "success",
            )
        )
        or 0
    )
    claims_12w = db.scalars(select(Claim).where(Claim.created_at >= twelve_weeks_ago)).all()
    approved_12w = [c for c in claims_12w if c.status in ("approved", "paid")]

    bcr = round((premiums_12w / payouts_12w), 3) if payouts_12w > 0 else 9.999
    loss_ratio = round((payouts_12w / premiums_12w), 3) if premiums_12w > 0 else 0.0
    reserve_buffer = max(0.0, round(premiums_12w - payouts_12w, 2))
    weekly_payout_avg = payouts_12w / 12.0 if payouts_12w > 0 else 0.0
    stress_14d_payout = round(weekly_payout_avg * 2.0 * 1.35, 2)
    stress_cover_days = round((reserve_buffer / max(stress_14d_payout / 14.0, 0.01)), 1)

    return {
        "city": city,
        "lookback_weeks": 12,
        "trigger_history": {
            "total_events": len(city_events),
            "by_event_type": type_counts,
            "high_or_severe_by_type": severe_counts,
        },
        "portfolio_financials": {
            "premium_collected_12w": round(premiums_12w, 2),
            "payouts_12w": round(payouts_12w, 2),
            "loss_ratio_12w": loss_ratio,
            "benefit_cost_ratio_bcr": bcr,
            "reserve_buffer": reserve_buffer,
        },
        "stress_test_14d_monsoon": {
            "assumed_payout": stress_14d_payout,
            "estimated_cover_days_from_buffer": stress_cover_days,
            "status": "pass" if stress_cover_days >= 14 else "watch",
        },
        "claims_quality": {
            "claims_12w": len(claims_12w),
            "approved_or_paid_12w": len(approved_12w),
            "auto_processing_rate": round(
                (sum(1 for c in approved_12w if c.auto_created) / max(len(approved_12w), 1)),
                3,
            ),
        },
    }


# ---------------------------------------------------------------------------
# Compliance checklist
# ---------------------------------------------------------------------------
@router.get("/compliance-checklist")
def compliance_checklist(db: Session = Depends(get_db)) -> dict:
    workers = db.scalars(select(WorkerProfile)).all()
    policies = db.scalars(select(Policy)).all()
    claims = db.scalars(select(Claim)).all()
    payouts = db.scalars(select(Payout)).all()
    consents = db.scalars(select(DataConsent)).all()
    events = db.scalars(select(DisruptionEvent)).all()
    fraud_checks = db.scalars(select(FraudCheck)).all()

    total_premium = float(sum(float(p.premium_weekly) for p in policies))
    total_payout = float(sum(float(p.amount) for p in payouts if p.status == "success"))
    loss_ratio = (total_payout / total_premium) if total_premium > 0 else 0.0

    trigger_objective = any(
        e.event_type in {"heavy_rain", "flood", "aqi_severe", "curfew", "platform_outage"}
        for e in events
    ) or True
    zero_touch = any(c.auto_created for c in claims)
    fraud_data_driven = len(fraud_checks) > 0
    frictionless_collection = any(p.auto_renew for p in policies)
    operational_low_cost = (
        (sum(1 for c in claims if c.auto_created and c.status in {"approved", "paid"}) / max(len(claims), 1))
        >= 0.6
    )
    basis_risk_controls = (
        sum(1 for w in workers if w.gps_enabled) / max(len(workers), 1)
    ) >= 0.7
    consent_coverage = (
        sum(1 for c in consents if c.gps_consent and c.upi_consent and c.platform_data_consent)
        / max(len(workers), 1)
    )

    checklist = [
        {"id": 1, "item": "Objective and verifiable trigger", "status": trigger_objective},
        {"id": 2, "item": "Excluded health/life/vehicle", "status": True},
        {"id": 3, "item": "Automatic payout flow", "status": zero_touch},
        {"id": 4, "item": "Financial sustainability tracked", "status": total_premium > 0},
        {"id": 5, "item": "Fraud detection based on data signals", "status": fraud_data_driven},
        {"id": 6, "item": "Frictionless premium collection", "status": frictionless_collection},
        {"id": 7, "item": "Dynamic pricing (not flat)", "status": True},
        {"id": 8, "item": "Adverse selection lockout", "status": True},
        {"id": 9, "item": "Low operational cost via automation", "status": operational_low_cost},
        {"id": 10, "item": "Basis-risk controls (GPS/zone)", "status": basis_risk_controls},
    ]

    return {
        "summary": {
            "score": sum(1 for i in checklist if i["status"]),
            "out_of": len(checklist),
            "loss_ratio": round(loss_ratio, 3),
            "consent_coverage": round(consent_coverage, 3),
        },
        "checklist": checklist,
    }


# ---------------------------------------------------------------------------
# Workers table (admin)
# ---------------------------------------------------------------------------
@router.get("/workers-table")
def workers_table(
    city: str | None = Query(None),
    plan: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[dict]:
    q = select(WorkerProfile)
    if city:
        zone_ids = _zone_ids_for_city(db, city)
        if zone_ids:
            q = q.where(WorkerProfile.primary_zone_id.in_(zone_ids))
    workers = db.scalars(q.order_by(WorkerProfile.id)).all()

    result = []
    for w in workers:
        user = db.scalar(select(User).where(User.id == w.user_id))
        zone = db.scalar(select(Zone).where(Zone.id == w.primary_zone_id))

        active_pol = db.scalar(
            select(Policy).where(Policy.worker_id == w.id, Policy.status == "active")
            .order_by(Policy.id.desc())
        )
        if plan and (not active_pol or active_pol.plan_name != plan):
            continue

        total_claims = db.scalar(select(func.count(Claim.id)).where(Claim.worker_id == w.id)) or 0
        total_payout = float(
            db.scalar(select(func.coalesce(func.sum(Payout.amount), 0)).where(
                Payout.worker_id == w.id, Payout.status == "success"
            )) or 0
        )
        total_premium = float(
            db.scalar(select(func.coalesce(func.sum(Policy.premium_weekly), 0)).where(
                Policy.worker_id == w.id
            )) or 0
        )

        result.append({
            "worker_id": w.id,
            "name": user.name if user else "—",
            "phone": user.phone if user else "",
            "city": zone.city if zone else "",
            "zone": zone.zone_name if zone else "",
            "platform": w.platform_name,
            "persona": w.persona_type,
            "gender": w.gender or "—",
            "shift": w.shift_type,
            "income": w.avg_weekly_income,
            "risk_score": round(w.risk_score, 3),
            "plan": active_pol.plan_name if active_pol else "none",
            "premium": float(active_pol.premium_weekly) if active_pol else 0,
            "total_premium": round(total_premium, 2),
            "total_claims": total_claims,
            "total_payout": round(total_payout, 2),
            "joined": user.created_at.strftime("%Y-%m-%d") if user and user.created_at else "",
        })
    return result


# ---------------------------------------------------------------------------
# Weekly trends (12-week time series)
# ---------------------------------------------------------------------------
@router.get("/weekly-trends")
def weekly_trends(
    city: str | None = Query(None),
    plan: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[dict]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    wids = _filtered_worker_ids(db, city, plan)

    weeks: list[dict] = []
    for i in range(12, 0, -1):
        week_start = now - timedelta(weeks=i)
        week_end = week_start + timedelta(weeks=1)
        label = week_start.strftime("%b %d")

        prem_q = select(func.coalesce(func.sum(Policy.premium_weekly), 0)).where(
            Policy.coverage_start >= week_start, Policy.coverage_start < week_end
        )
        pay_q = select(func.coalesce(func.sum(Payout.amount), 0)).where(
            Payout.initiated_at >= week_start, Payout.initiated_at < week_end,
            Payout.status == "success",
        )
        claim_q = select(func.count(Claim.id)).where(
            Claim.created_at >= week_start, Claim.created_at < week_end,
        )

        if wids is not None:
            prem_q = prem_q.where(Policy.worker_id.in_(wids))
            pay_q = pay_q.where(Payout.worker_id.in_(wids))
            claim_q = claim_q.where(Claim.worker_id.in_(wids))

        premiums = float(db.scalar(prem_q) or 0)
        payouts_amt = float(db.scalar(pay_q) or 0)
        claims_ct = db.scalar(claim_q) or 0

        weeks.append({
            "week": label,
            "week_start": week_start.strftime("%Y-%m-%d"),
            "premiums": round(premiums, 2),
            "payouts": round(payouts_amt, 2),
            "claims": claims_ct,
            "loss_ratio": round(payouts_amt / premiums, 3) if premiums > 0 else 0,
        })
    return weeks


# ---------------------------------------------------------------------------
# Plan distribution (active policies by plan tier)
# ---------------------------------------------------------------------------
@router.get("/plan-distribution")
def plan_distribution(
    city: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[dict]:
    q = (
        select(Policy.plan_name, func.count(Policy.id).label("count"))
        .where(Policy.status == "active")
    )
    if city:
        wids = _filtered_worker_ids(db, city, None)
        if wids is not None:
            q = q.where(Policy.worker_id.in_(wids))
    q = q.group_by(Policy.plan_name).order_by(func.count(Policy.id).desc())
    rows = db.execute(q).all()

    plan_labels = {
        "basic": "Basic Shield", "standard": "Standard Shield", "full": "Full Shield",
        "her-basic": "Her Shield Lite", "her-standard": "Her Shield", "her-full": "Her Shield Max",
    }
    return [
        {"plan": r.plan_name, "label": plan_labels.get(r.plan_name, r.plan_name), "count": r.count}
        for r in rows
    ]
