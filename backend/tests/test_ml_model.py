from app.ml.premium_model import PremiumModel
from app.services.risk_service import calculate_risk_score, quote_premium, get_risk_explanation


def test_ml_risk_score_in_range() -> None:
    """ML model should predict risk scores between 0 and 1."""
    model = PremiumModel()
    model.train()
    score = model.predict_risk_score(
        rain_risk=0.5, flood_risk=0.3, aqi_risk=0.2,
        closure_risk=0.1, shift_exposure=0.7,
        avg_weekly_income=3500, city="Bengaluru",
    )
    assert 0.0 <= score <= 1.0


def test_ml_premium_in_range() -> None:
    """ML model should predict premiums in ₹19-99 range."""
    model = PremiumModel()
    model.train()
    premium = model.predict_premium(
        rain_risk=0.5, flood_risk=0.3, aqi_risk=0.2,
        closure_risk=0.1, shift_exposure=0.7,
        avg_weekly_income=4500, city="Mumbai",
    )
    assert 19.0 <= premium <= 99.0


def test_high_risk_higher_premium() -> None:
    """Higher risk factors should generally produce higher premiums."""
    model = PremiumModel()
    model.train()
    low_risk = model.predict_premium(
        rain_risk=0.1, flood_risk=0.05, aqi_risk=0.05,
        closure_risk=0.02, shift_exposure=0.3,
        avg_weekly_income=3000, city="Jaipur",
    )
    high_risk = model.predict_premium(
        rain_risk=0.9, flood_risk=0.8, aqi_risk=0.7,
        closure_risk=0.5, shift_exposure=0.9,
        avg_weekly_income=3000, city="Mumbai",
    )
    assert high_risk > low_risk


def test_risk_service_integration() -> None:
    """risk_service functions should work with ML backend."""
    score = calculate_risk_score(0.3, 0.2, 0.1, 0.05, 0.5, 3500, "Bengaluru")
    assert 0.0 <= score <= 1.0

    premium = quote_premium(0.3, 0.2, 0.1, 0.05, 0.5, 3500, "Bengaluru")
    assert 19.0 <= premium <= 99.0

    info = get_risk_explanation("Mumbai")
    assert "importances" in info
    assert "explanation" in info
    assert len(info["importances"]) == 7


def test_feature_importances_sum() -> None:
    """Feature importances should sum close to 1.0."""
    model = PremiumModel()
    model.train()
    importances = model.get_feature_importances()
    total = sum(importances.values())
    assert 0.95 <= total <= 1.05
