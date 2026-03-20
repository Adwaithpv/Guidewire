from __future__ import annotations


def compute_fraud_score(
    gps_mismatch: float,
    duplicate_risk: float,
    activity_absence: float,
    anomaly_pattern: float,
    source_conflict: float,
) -> float:
    score = (
        gps_mismatch * 0.30
        + duplicate_risk * 0.25
        + activity_absence * 0.20
        + anomaly_pattern * 0.15
        + source_conflict * 0.10
    )
    return round(max(0.0, min(1.0, score)), 4)


def review_status(score: float) -> str:
    if score <= 0.30:
        return "auto_approve"
    if score <= 0.60:
        return "soft_review"
    return "manual_review"
