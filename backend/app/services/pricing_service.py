"""
Interpretable weekly premium (Phase 2): admin + loss-cost load tied to declared income cap.

Blended with ML in risk_service so pricing reacts to live factors in a way actuaries can explain:
  premium ≈ admin + (max_weekly_payout × (floor_rate + exposure × variable_rate))

News-based closure only adjusts exposure for pricing — it does not by itself authorize a payout;
payouts require a verified parametric event ingested for the worker's zone.
"""
from __future__ import annotations

# Same city ordering as ML training for consistency
_CITY_BASE: dict[str, float] = {
    "Mumbai": 0.82,
    "Chennai": 0.75,
    "Kolkata": 0.70,
    "Bengaluru": 0.55,
    "Delhi": 0.65,
    "Hyderabad": 0.50,
    "Pune": 0.48,
    "Ahmedabad": 0.45,
    "Jaipur": 0.40,
    "Lucknow": 0.42,
}

# Weights sum ~1; closure kept moderate — news is a soft signal, not a claims trigger
_EXPOSURE_WEIGHTS = {
    "rain": 0.26,
    "flood": 0.20,
    "aqi": 0.18,
    "closure": 0.12,
    "shift": 0.12,
    "city": 0.12,
}

_ADMIN_WEEKLY = 14.0
# Fraction of max_weekly_payout charged as expected weekly loss cost at full exposure
_LOSS_COST_RATE_AT_FULL_EXPOSURE = 0.26
_LOSS_COST_FLOOR = 0.035


def exposure_index(
    rain_risk: float,
    flood_risk: float,
    aqi_risk: float,
    closure_risk: float,
    shift_exposure: float,
    city: str,
) -> float:
    """Scalar 0–1 summarizing external + schedule exposure (transparent)."""
    city_f = _CITY_BASE.get(city, 0.45)
    w = _EXPOSURE_WEIGHTS
    s = (
        w["rain"] * rain_risk
        + w["flood"] * flood_risk
        + w["aqi"] * aqi_risk
        + w["closure"] * closure_risk
        + w["shift"] * shift_exposure
        + w["city"] * city_f
    )
    return max(0.0, min(1.0, s))


def actuarial_weekly_premium(
    rain_risk: float,
    flood_risk: float,
    aqi_risk: float,
    closure_risk: float,
    shift_exposure: float,
    avg_weekly_income: float,
    city: str,
) -> float:
    """
    Weekly premium in INR before ML blend.
    max_weekly_payout is 40% of income (same rule as policies.quote).
    """
    max_weekly_payout = round(avg_weekly_income * 0.4, 2)
    exp = exposure_index(
        rain_risk, flood_risk, aqi_risk, closure_risk, shift_exposure, city
    )
    loss_cost = max_weekly_payout * (_LOSS_COST_FLOOR + exp * _LOSS_COST_RATE_AT_FULL_EXPOSURE)
    raw = _ADMIN_WEEKLY + loss_cost
    return float(max(19.0, min(99.0, round(raw, 2))))


def blend_premium(actuarial: float, ml_premium: float, ml_weight: float = 0.35) -> float:
    """Interpretable base + ML residual (capped)."""
    w = max(0.0, min(1.0, ml_weight))
    blended = (1.0 - w) * actuarial + w * ml_premium
    return float(max(19.0, min(99.0, round(blended, 2))))


def linear_risk_score(
    rain_risk: float,
    flood_risk: float,
    aqi_risk: float,
    closure_risk: float,
    shift_exposure: float,
    city: str,
) -> float:
    """Same exposure index, rescaled to typical risk score band."""
    exp = exposure_index(
        rain_risk, flood_risk, aqi_risk, closure_risk, shift_exposure, city
    )
    return float(max(0.02, min(0.98, round(0.08 + 0.88 * exp, 4))))
