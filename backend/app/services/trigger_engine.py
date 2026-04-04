from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.entities import Claim, DisruptionEvent, FraudCheck, Policy, TriggerMatch, WorkerProfile
from app.services.fraud_service import compute_fraud_score, review_status
from app.services.parametric_rules import (
    effective_loss_hours,
    event_satisfies_trigger_index,
    policy_trigger_for_event,
    remaining_weekly_payout_budget,
)
from app.services.payout_service import estimate_payout


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
        # One claim per worker per disruption event (avoids N identical claims when N active policies exist).
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
        baseline_fraud_score = compute_fraud_score(
            gps_mismatch=0.05,
            duplicate_risk=0.0,
            activity_absence=0.05,
            anomaly_pattern=0.02,
            source_conflict=0.02,
        )
        baseline_review = review_status(baseline_fraud_score)
        claim.status = "approved" if baseline_review != "manual_review" else "fraud_check"
        db.add(claim)
        db.flush()
        db.add(
            FraudCheck(
                claim_id=claim.id,
                gps_score=0.05,
                activity_score=0.05,
                duplicate_score=0.0,
                anomaly_score=0.02,
                source_score=0.02,
                final_fraud_score=baseline_fraud_score,
                review_status=baseline_review,
            )
        )
        db.add(match)
        claims.append(claim)
    db.commit()
    for claim in claims:
        db.refresh(claim)
    return claims
