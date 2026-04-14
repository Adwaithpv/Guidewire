"""
Advanced fraud detection for SurakshaShift Phase 3.

Checks: GPS spoofing, historical weather cross-reference, duplicate/velocity detection,
activity absence, anomaly scoring, and source conflict analysis.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


# ---------------------------------------------------------------------------
# Individual fraud signal scorers
# ---------------------------------------------------------------------------

def gps_spoofing_score(
    worker_zone_name: str,
    event_zone_name: str | None,
    worker_gps_enabled: bool,
) -> float:
    """
    Compares worker's registered zone to the event zone.
    If GPS is disabled or zones don't match, score rises.
    """
    if not worker_gps_enabled:
        return 0.35
    if event_zone_name and worker_zone_name.lower() != event_zone_name.lower():
        return 0.70
    return 0.05


def historical_weather_score(
    event_type: str,
    event_payload: dict[str, Any],
    live_weather: dict[str, Any] | None,
) -> float:
    """
    Cross-reference claimed disruption against actual/live weather data.
    High score when the claimed event doesn't match observed conditions.
    """
    if not live_weather:
        return 0.10

    if event_type == "heavy_rain":
        claimed_mm = float(
            event_payload.get("rainfall_mm")
            or event_payload.get("rain_mm_1h")
            or 0
        )
        actual_mm = float(live_weather.get("rain_mm_1h") or 0)
        if claimed_mm > 0 and actual_mm < 5:
            return 0.85
        if claimed_mm > 0 and actual_mm > 0:
            ratio = abs(claimed_mm - actual_mm) / max(claimed_mm, actual_mm)
            return _clamp01(ratio * 0.8)
        return 0.05

    if event_type == "aqi_severe":
        actual_aqi = float(live_weather.get("aqi") or live_weather.get("aqi_value") or 0)
        if actual_aqi > 0 and actual_aqi < 150:
            return 0.70
        return 0.05

    return 0.05


def duplicate_velocity_score(
    db: Session,
    worker_id: int,
    event_type: str,
    lookback_hours: float = 24.0,
    max_normal_claims: int = 2,
) -> float:
    """
    Detects suspiciously frequent claims from the same worker.
    Also flags same event_type claims within a short window.
    """
    from app.models.entities import Claim

    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=lookback_hours)
    recent_claims = db.scalars(
        select(Claim).where(
            Claim.worker_id == worker_id,
            Claim.created_at >= since,
        )
    ).all()

    total_recent = len(recent_claims)
    same_type = sum(1 for c in recent_claims if c.claim_type == event_type)

    if total_recent > max_normal_claims * 2:
        return 0.90
    if same_type > max_normal_claims:
        return 0.75
    if total_recent > max_normal_claims:
        return 0.45
    return 0.0


def activity_absence_score(
    worker_shift_type: str,
    event_started_at: datetime,
) -> float:
    """
    Flags claims during hours when the worker is unlikely to be active.
    """
    hour = event_started_at.hour
    shift_hours: dict[str, tuple[int, int]] = {
        "morning": (5, 13),
        "afternoon": (11, 19),
        "evening": (16, 23),
        "night": (20, 6),
        "full_day": (6, 22),
        "split": (7, 21),
    }
    start_h, end_h = shift_hours.get(worker_shift_type, (6, 22))
    if start_h < end_h:
        on_shift = start_h <= hour < end_h
    else:
        on_shift = hour >= start_h or hour < end_h

    return 0.05 if on_shift else 0.55


def anomaly_payout_score(
    approved_payout: float,
    avg_weekly_income: float,
) -> float:
    """
    Flags payouts that are disproportionate to the worker's income.
    """
    if avg_weekly_income <= 0:
        return 0.50
    ratio = approved_payout / avg_weekly_income
    if ratio > 0.6:
        return 0.80
    if ratio > 0.4:
        return 0.40
    return 0.05


def source_conflict_score(
    event_source: str,
    event_is_verified: bool,
) -> float:
    """
    Flags events from unverified or mock sources.
    """
    if not event_is_verified:
        return 0.70
    source_lower = (event_source or "").lower()
    if source_lower.startswith("mock"):
        return 0.15
    if source_lower.startswith("live_"):
        return 0.02
    return 0.10


# ---------------------------------------------------------------------------
# Composite scoring
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "gps": 0.20,
    "historical_weather": 0.20,
    "duplicate_velocity": 0.20,
    "activity_absence": 0.15,
    "anomaly_payout": 0.15,
    "source_conflict": 0.10,
}


def compute_fraud_score(
    gps: float = 0.0,
    historical_weather: float = 0.0,
    duplicate_velocity: float = 0.0,
    activity_absence: float = 0.0,
    anomaly_payout: float = 0.0,
    source_conflict: float = 0.0,
) -> float:
    score = (
        _WEIGHTS["gps"] * _clamp01(gps)
        + _WEIGHTS["historical_weather"] * _clamp01(historical_weather)
        + _WEIGHTS["duplicate_velocity"] * _clamp01(duplicate_velocity)
        + _WEIGHTS["activity_absence"] * _clamp01(activity_absence)
        + _WEIGHTS["anomaly_payout"] * _clamp01(anomaly_payout)
        + _WEIGHTS["source_conflict"] * _clamp01(source_conflict)
    )
    return round(_clamp01(score), 4)


def compute_fraud_score_legacy(
    gps_mismatch: float = 0.0,
    duplicate_risk: float = 0.0,
    activity_absence: float = 0.0,
    anomaly_pattern: float = 0.0,
    source_conflict: float = 0.0,
) -> float:
    """Backward-compat wrapper for Phase 2 callers."""
    score = (
        gps_mismatch * 0.30
        + duplicate_risk * 0.25
        + activity_absence * 0.20
        + anomaly_pattern * 0.15
        + source_conflict * 0.10
    )
    return round(_clamp01(score), 4)


def review_status(score: float) -> str:
    if score <= 0.25:
        return "auto_approve"
    if score <= 0.55:
        return "soft_review"
    return "manual_review"


def evaluate_claim_fraud(
    db: Session,
    claim_id: int,
    live_weather: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Full fraud evaluation pipeline for a claim.
    Returns dict with individual scores, composite, and review status.
    """
    from app.models.entities import Claim, DisruptionEvent, FraudCheck, WorkerProfile, Zone

    claim = db.scalar(select(Claim).where(Claim.id == claim_id))
    if claim is None:
        return {"error": "Claim not found"}

    worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == claim.worker_id))
    event = db.scalar(select(DisruptionEvent).where(DisruptionEvent.id == claim.event_id))
    if not worker or not event:
        return {"error": "Worker or event not found"}

    worker_zone = db.scalar(select(Zone).where(Zone.id == worker.primary_zone_id))
    event_zone = db.scalar(select(Zone).where(Zone.id == event.zone_id))

    event_payload: dict[str, Any] = {}
    if event.source_payload:
        try:
            event_payload = json.loads(event.source_payload)
        except json.JSONDecodeError:
            pass

    gps = gps_spoofing_score(
        worker_zone.zone_name if worker_zone else "",
        event_zone.zone_name if event_zone else None,
        worker.gps_enabled,
    )
    hist_weather = historical_weather_score(event.event_type, event_payload, live_weather)
    dup_vel = duplicate_velocity_score(db, worker.id, event.event_type)
    activity = activity_absence_score(worker.shift_type, event.started_at)
    anomaly = anomaly_payout_score(float(claim.approved_payout), worker.avg_weekly_income)
    source = source_conflict_score(event.source_name, event.is_verified)

    composite = compute_fraud_score(
        gps=gps,
        historical_weather=hist_weather,
        duplicate_velocity=dup_vel,
        activity_absence=activity,
        anomaly_payout=anomaly,
        source_conflict=source,
    )
    status = review_status(composite)

    existing_check = db.scalar(select(FraudCheck).where(FraudCheck.claim_id == claim_id))
    if existing_check:
        existing_check.gps_score = gps
        existing_check.activity_score = activity
        existing_check.duplicate_score = dup_vel
        existing_check.anomaly_score = anomaly
        existing_check.source_score = source
        existing_check.final_fraud_score = composite
        existing_check.review_status = status
    else:
        db.add(FraudCheck(
            claim_id=claim_id,
            gps_score=gps,
            activity_score=activity,
            duplicate_score=dup_vel,
            anomaly_score=anomaly,
            source_score=source,
            final_fraud_score=composite,
            review_status=status,
        ))

    if status == "manual_review":
        claim.status = "fraud_check"
    elif status == "soft_review":
        claim.status = "approved"
    else:
        claim.status = "approved"

    db.commit()
    return {
        "claim_id": claim_id,
        "scores": {
            "gps_spoofing": round(gps, 3),
            "historical_weather": round(hist_weather, 3),
            "duplicate_velocity": round(dup_vel, 3),
            "activity_absence": round(activity, 3),
            "anomaly_payout": round(anomaly, 3),
            "source_conflict": round(source, 3),
        },
        "composite_fraud_score": composite,
        "review_status": status,
        "claim_status": claim.status,
    }
