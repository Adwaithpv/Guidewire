from __future__ import annotations


def calculate_risk_score(
    rain_risk: float,
    flood_risk: float,
    aqi_risk: float,
    closure_risk: float,
    shift_exposure: float,
) -> float:
    score = (
        0.30 * rain_risk
        + 0.25 * flood_risk
        + 0.20 * aqi_risk
        + 0.15 * closure_risk
        + 0.10 * shift_exposure
    )
    return round(max(0.0, min(1.0, score)), 4)


def quote_premium(risk_score: float) -> float:
    base = 25.0
    premium = base + risk_score * 70.0
    return round(max(19.0, min(99.0, premium)), 2)


def quote_max_payout(avg_weekly_income: float) -> float:
    return round(avg_weekly_income * 0.4, 2)
