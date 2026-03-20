from app.services.fraud_service import compute_fraud_score, review_status
from app.services.payout_service import estimate_payout
from app.services.risk_service import calculate_risk_score, quote_premium


def test_risk_score_bounds() -> None:
    score = calculate_risk_score(1, 1, 1, 1, 1)
    assert 0 <= score <= 1
    premium = quote_premium(score)
    assert 19 <= premium <= 99


def test_fraud_review_status_mapping() -> None:
    low = compute_fraud_score(0.1, 0.0, 0.0, 0.0, 0.0)
    high = compute_fraud_score(1.0, 1.0, 1.0, 1.0, 1.0)
    assert review_status(low) == "auto_approve"
    assert review_status(high) == "manual_review"


def test_payout_cap_enforcement() -> None:
    estimated_loss, payout = estimate_payout(avg_weekly_income=4200, disrupted_hours=10, cap_remaining=150)
    assert estimated_loss > payout
    assert payout <= 150
