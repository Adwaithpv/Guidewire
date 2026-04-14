"""
Trigger engine: matches disruption events against active policies,
runs advanced fraud detection, creates claims, and auto-initiates payouts.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.entities import Claim, DisruptionEvent, FraudCheck, Payout, Policy, TriggerMatch, WorkerProfile, Zone
from app.services.fraud_service import (
    activity_absence_score,
    anomaly_payout_score,
    compute_fraud_score,
    duplicate_velocity_score,
    gps_spoofing_score,
    review_status,
    source_conflict_score,
)
from app.services.parametric_rules import (
    effective_loss_hours,
    event_satisfies_trigger_index,
    policy_trigger_for_event,
    remaining_weekly_payout_budget,
)
from app.services.payout_service import estimate_payout, mock_razorpay_transfer
from app.services.whatsapp_service import notify_claim_created, notify_claim_paid


def find_impacted_policies(db: Session, zone_id: int, started_at: datetime, ended_at: datetime) -> list[tuple[WorkerProfile, Policy]]:
    stmt = (
        select(WorkerProfile, Policy)
        .join(Policy, Policy.worker_id == WorkerProfile.id)
        .where(
            and_(
                WorkerProfile.primary_zone_id == zone_id,
                Policy.status == "active",
                Policy.coverage_start <= ended_at,
                Policy.coverage_end >= started_at,
            )
        )
        .order_by(Policy.id.desc())
    )
    return list(db.execute(stmt).all())


def _run_fraud_checks(
    db: Session,
    worker: WorkerProfile,
    event: DisruptionEvent,
    approved_payout: float,
) -> tuple[float, str, dict]:
    """Run all six fraud signals and return (score, review_status, individual_scores)."""
    worker_zone = db.scalar(select(Zone).where(Zone.id == worker.primary_zone_id))
    event_zone = db.scalar(select(Zone).where(Zone.id == event.zone_id))

    gps = gps_spoofing_score(
        worker_zone.zone_name if worker_zone else "",
        event_zone.zone_name if event_zone else None,
        worker.gps_enabled,
    )
    dup_vel = duplicate_velocity_score(db, worker.id, event.event_type)
    activity = activity_absence_score(worker.shift_type, event.started_at)
    anomaly = anomaly_payout_score(approved_payout, worker.avg_weekly_income)
    source = source_conflict_score(event.source_name, event.is_verified)

    composite = compute_fraud_score(
        gps=gps,
        historical_weather=0.05,
        duplicate_velocity=dup_vel,
        activity_absence=activity,
        anomaly_payout=anomaly,
        source_conflict=source,
    )
    status = review_status(composite)
    scores = {
        "gps": gps,
        "duplicate_velocity": dup_vel,
        "activity": activity,
        "anomaly": anomaly,
        "source": source,
    }
    return composite, status, scores


def _auto_initiate_payout(db: Session, claim: Claim, worker: WorkerProfile) -> Payout | None:
    """Create a payout record using the Razorpay mock gateway."""
    if float(claim.approved_payout) <= 0:
        return None

    gateway_result = mock_razorpay_transfer(
        amount=float(claim.approved_payout),
        worker_upi=worker.payout_upi,
        worker_name=getattr(worker.user, "name", ""),
    )

    payout = Payout(
        claim_id=claim.id,
        worker_id=worker.id,
        amount=float(claim.approved_payout),
        method="upi",
        status="success" if gateway_result["status"] == "captured" else "failed",
        gateway_ref=gateway_result["payment_id"],
        initiated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        completed_at=datetime.now(timezone.utc).replace(tzinfo=None) if gateway_result["status"] == "captured" else None,
    )
    db.add(payout)

    if payout.status == "success":
        claim.status = "paid"
        try:
            user = worker.user
            if user and user.phone:
                notify_claim_paid(
                    to_phone=user.phone,
                    worker_name=user.name,
                    claim_type=claim.claim_type,
                    payout_amount=float(claim.approved_payout),
                    gateway_ref=gateway_result["payment_id"],
                    upi_id=worker.payout_upi,
                )
        except Exception:
            pass

    return payout


def create_claim_candidates(
    db: Session,
    event: DisruptionEvent,
    restrict_worker_id: int | None = None,
) -> list[Claim]:
    impacted = find_impacted_policies(db, event.zone_id, event.started_at, event.ended_at)
    if restrict_worker_id is not None:
        impacted = [(w, p) for w, p in impacted if w.id == restrict_worker_id]
    claims: list[Claim] = []
    for worker, policy in impacted:
        if db.scalar(
            select(Claim.id).where(
                Claim.worker_id == worker.id,
                Claim.event_id == event.id,
            ).limit(1)
        ):
            continue

        trig = policy_trigger_for_event(db, policy.id, event.event_type)
        if trig is None:
            continue
        if not event_satisfies_trigger_index(event, trig):
            continue

        budget = remaining_weekly_payout_budget(db, policy)
        if budget <= 0:
            continue

        disrupted_hours = effective_loss_hours(
            worker.shift_type, event.started_at, event.ended_at
        )
        estimated_loss, payout = estimate_payout(
            worker.avg_weekly_income, disrupted_hours, budget
        )
        match = TriggerMatch(
            event_id=event.id,
            worker_id=worker.id,
            policy_id=policy.id,
            expected_payout=payout,
            status="matched",
        )
        claim = Claim(
            worker_id=worker.id,
            policy_id=policy.id,
            event_id=event.id,
            claim_type=event.event_type,
            status="validation_pending",
            estimated_loss=estimated_loss,
            approved_payout=payout,
            auto_created=True,
        )

        fraud_score, fraud_review, fraud_scores = _run_fraud_checks(db, worker, event, payout)
        claim.status = "approved" if fraud_review != "manual_review" else "fraud_check"
        db.add(claim)
        db.flush()

        db.add(
            FraudCheck(
                claim_id=claim.id,
                gps_score=fraud_scores["gps"],
                activity_score=fraud_scores["activity"],
                duplicate_score=fraud_scores["duplicate_velocity"],
                anomaly_score=fraud_scores["anomaly"],
                source_score=fraud_scores["source"],
                final_fraud_score=fraud_score,
                review_status=fraud_review,
            )
        )
        db.add(match)

        # Notify worker as soon as claim is created for this disruption.
        try:
            user = worker.user
            zone = db.scalar(select(Zone).where(Zone.id == event.zone_id))
            if user and user.phone:
                notify_claim_created(
                    to_phone=user.phone,
                    worker_name=user.name or "Worker",
                    claim_type=claim.claim_type,
                    zone_name=zone.zone_name if zone else "your zone",
                    severity=event.severity or "moderate",
                    claim_id=claim.id,
                    review_status=fraud_review,
                    expected_payout=float(claim.approved_payout),
                )
        except Exception:
            pass

        if claim.status == "approved":
            _auto_initiate_payout(db, claim, worker)

        claims.append(claim)
    db.commit()
    for claim in claims:
        db.refresh(claim)
    return claims
