"""
Parametric claim rules: only pay when the policy covers the event type, index exceeds
stored trigger threshold (when payload has metrics), loss hours respect shift realism,
and remaining weekly benefit is not exhausted.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import Claim, DisruptionEvent, Policy, PolicyTrigger


_SHIFT_MAX_HOURS_PER_CALENDAR_DAY: dict[str, float] = {
    "morning": 6.0,
    "afternoon": 6.0,
    "evening": 7.0,
    "night": 8.0,
    "full_day": 11.0,
    "split": 8.0,
}


def _parse_payload(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def effective_loss_hours(
    shift_type: str,
    started_at: datetime,
    ended_at: datetime,
) -> float:
    """
    Income loss cannot exceed plausible on-shift hours across affected calendar days
    (gig workers are not assumed earning 24h/day).
    """
    delta_h = max(0.0, (ended_at - started_at).total_seconds() / 3600.0)
    if delta_h <= 0:
        return 1.0
    max_per_day = _SHIFT_MAX_HOURS_PER_CALENDAR_DAY.get(shift_type, 8.0)
    d0 = started_at.date()
    d1 = ended_at.date()
    calendar_days = (d1 - d0).days + 1
    calendar_days = max(1, min(7, calendar_days))
    cap = max_per_day * calendar_days
    return max(0.5, min(delta_h, cap))


def remaining_weekly_payout_budget(db: Session, policy: Policy) -> float:
    """Approved payouts already issued against this weekly policy window."""
    used = db.scalar(
        select(func.coalesce(func.sum(Claim.approved_payout), 0)).where(
            Claim.policy_id == policy.id,
            Claim.status == "approved",
            Claim.created_at >= policy.coverage_start,
            Claim.created_at <= policy.coverage_end,
        )
    )
    used_f = float(used or 0)
    return max(0.0, float(policy.max_weekly_payout) - used_f)


def policy_trigger_for_event(
    db: Session, policy_id: int, event_type: str
) -> PolicyTrigger | None:
    return db.scalar(
        select(PolicyTrigger).where(
            PolicyTrigger.policy_id == policy_id,
            PolicyTrigger.trigger_type == event_type,
        )
    )


def event_satisfies_trigger_index(event: DisruptionEvent, trigger: PolicyTrigger) -> bool:
    """
    If the event carries a measurable index, it must meet the policy trigger threshold.
    Missing payload → trust verified ingest (demo / trusted feeds only in production).
    """
    payload = _parse_payload(event.source_payload)
    if not payload:
        return True

    et = event.event_type
    th = float(trigger.threshold_value)

    if et == "heavy_rain":
        mm = float(
            payload.get("rainfall_mm")
            or payload.get("rain_mm_1h")
            or payload.get("rain_mm")
            or 0
        )
        if mm <= 0:
            return True
        return mm >= th

    if et == "flood":
        cm = float(payload.get("water_level_cm") or payload.get("flood_cm") or 0)
        if cm <= 0:
            return False
        return cm >= th

    if et == "aqi_severe":
        aqi = float(payload.get("aqi") or 0)
        if aqi <= 0:
            return True
        return aqi >= th

    if et == "platform_outage":
        mins = float(payload.get("downtime_min") or payload.get("downtime_minutes") or 0)
        if mins <= 0:
            return True
        return mins >= th

    if et == "curfew":
        return True

    return True


def recent_duplicate_event(
    db: Session,
    zone_id: int,
    event_type: str,
    cooldown_hours: float = 6.0,
) -> DisruptionEvent | None:
    """Avoid stacking identical zone events from polling / retries (real ops guard)."""
    from datetime import timedelta

    since = datetime.utcnow() - timedelta(hours=cooldown_hours)
    return db.scalar(
        select(DisruptionEvent)
        .where(
            DisruptionEvent.zone_id == zone_id,
            DisruptionEvent.event_type == event_type,
            DisruptionEvent.started_at >= since,
        )
        .order_by(DisruptionEvent.id.desc())
        .limit(1)
    )
