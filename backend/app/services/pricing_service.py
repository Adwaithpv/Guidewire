"""
Tiered actuarial pricing for SurakshaShift AI.

The primary premium comes from transparent exposure-based pricing per plan tier.
GBM remains in the stack as a 20% residual blend in risk_service.py.
"""
from __future__ import annotations

from typing import Any

PLANS: dict[str, dict[str, Any]] = {
    "basic": {
        "label": "Basic Shield",
        "description": "Entry cover for light income disruption days.",
        "coverage_pct": 0.20,
        "min_premium": 15.0,
        "max_premium": 49.0,
    },
    "standard": {
        "label": "Standard Shield",
        "description": "Balanced cover for typical gig-worker disruption risk.",
        "coverage_pct": 0.35,
        "min_premium": 25.0,
        "max_premium": 79.0,
    },
    "full": {
        "label": "Full Shield",
        "description": "Maximum weekly protection when disruption risk spikes.",
        "coverage_pct": 0.50,
        "min_premium": 35.0,
        "max_premium": 120.0,
    },
}

_CITY_RISK: dict[str, float] = {
    "Mumbai": 0.79,
    "Chennai": 0.75,
    "Kolkata": 0.68,
    "Delhi": 0.52,
    "Bengaluru": 0.44,
    "Hyderabad": 0.48,
    "Pune": 0.46,
    "Ahmedabad": 0.38,
    "Jaipur": 0.35,
    "Lucknow": 0.41,
}

_EXPOSURE_WEIGHTS = {
    "rain": 0.30,
    "flood": 0.25,
    "aqi": 0.20,
    "closure": 0.13,
    "shift": 0.12,
}

_MIN_RISK_RATE = 0.015
_MAX_RISK_RATE = 0.080

# Back-compat export for existing imports.
CITY_RISK_WEIGHTS = _CITY_RISK


def city_risk_factor(city: str) -> float:
    return float(_CITY_RISK.get(city, 0.45))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def exposure_index(
    rain_risk: float,
    flood_risk: float,
    aqi_risk: float,
    closure_risk: float,
    shift_exposure: float,
    city: str,
) -> float:
    """
    Composite 0-1 exposure used for pricing/risk bands.

    First compute weighted live exposure, then apply a city-risk multiplier so two workers
    with identical live factors still reflect different base climatic disruption profiles.
    """
    weighted = (
        _EXPOSURE_WEIGHTS["rain"] * _clamp01(rain_risk)
        + _EXPOSURE_WEIGHTS["flood"] * _clamp01(flood_risk)
        + _EXPOSURE_WEIGHTS["aqi"] * _clamp01(aqi_risk)
        + _EXPOSURE_WEIGHTS["closure"] * _clamp01(closure_risk)
        + _EXPOSURE_WEIGHTS["shift"] * _clamp01(shift_exposure)
    )
    city_multiplier = 0.75 + 0.50 * city_risk_factor(city)
    return _clamp01(weighted * city_multiplier)


def composite_exposure(
    rain_risk: float,
    flood_risk: float,
    aqi_risk: float,
    closure_risk: float,
    shift_exposure: float,
    city: str,
) -> float:
    return exposure_index(
        rain_risk, flood_risk, aqi_risk, closure_risk, shift_exposure, city
    )


def risk_rate_pct_from_exposure(exposure: float) -> float:
    exp = _clamp01(exposure)
    return (_MIN_RISK_RATE + (_MAX_RISK_RATE - _MIN_RISK_RATE) * exp) * 100.0


def _risk_rate_from_exposure(exposure: float) -> float:
    return risk_rate_pct_from_exposure(exposure) / 100.0


def risk_level_from_exposure(exposure: float) -> str:
    e = _clamp01(exposure)
    if e < 0.20:
        return "low"
    if e < 0.45:
        return "moderate"
    if e < 0.70:
        return "high"
    return "critical"


def blend_premium(
    actuarial: float,
    ml_premium: float,
    floor: float,
    ceiling: float,
    ml_weight: float = 0.20,
) -> float:
    """Actuarial 80% + ML residual 20%, then clamp to plan affordability bounds."""
    w = _clamp01(ml_weight)
    blended = (1.0 - w) * float(actuarial) + w * float(ml_premium)
    return float(max(floor, min(ceiling, round(blended, 2))))


def quote_plan(
    plan_id: str,
    rain_risk: float,
    flood_risk: float,
    aqi_risk: float,
    closure_risk: float,
    shift_exposure: float,
    avg_weekly_income: float,
    city: str,
) -> dict[str, Any]:
    plan = PLANS.get(plan_id)
    if plan is None:
        raise ValueError(f"Unsupported plan_id: {plan_id}")

    composite = exposure_index(
        rain_risk, flood_risk, aqi_risk, closure_risk, shift_exposure, city
    )
    risk_rate = _risk_rate_from_exposure(composite)
    max_payout = float(avg_weekly_income) * float(plan["coverage_pct"])
    actuarial = max_payout * risk_rate

    floor = float(plan["min_premium"])
    ceiling = float(plan["max_premium"])
    premium = float(max(floor, min(ceiling, round(actuarial, 2))))
    # At realistic incomes, high exposure can hit plan ceilings by design; this is an
    # affordability cap for workers, not a model flaw.
    return {
        "plan_id": plan_id,
        "label": str(plan["label"]),
        "description": str(plan["description"]),
        "premium_weekly": premium,
        "max_weekly_payout": round(max_payout, 2),
        "coverage_pct": float(plan["coverage_pct"]),
        "risk_rate_pct": round(risk_rate * 100.0, 2),
        "at_floor": premium <= floor,
        "at_ceiling": premium >= ceiling,
        "composite_risk": round(composite, 4),
    }


def quote_all_plans(
    rain_risk: float,
    flood_risk: float,
    aqi_risk: float,
    closure_risk: float,
    shift_exposure: float,
    avg_weekly_income: float,
    city: str,
) -> list[dict[str, Any]]:
    return [
        quote_plan(
            plan_id,
            rain_risk,
            flood_risk,
            aqi_risk,
            closure_risk,
            shift_exposure,
            avg_weekly_income,
            city,
        )
        for plan_id in ("basic", "standard", "full")
    ]


def actuarial_weekly_premium(
    rain_risk: float,
    flood_risk: float,
    aqi_risk: float,
    closure_risk: float,
    shift_exposure: float,
    avg_weekly_income: float,
    city: str,
) -> float:
    """Back-compat single premium: standard plan actuarial amount (pre-ML)."""
    return float(
        quote_plan(
            "standard",
            rain_risk,
            flood_risk,
            aqi_risk,
            closure_risk,
            shift_exposure,
            avg_weekly_income,
            city,
        )["premium_weekly"]
    )


def linear_risk_score(
    rain_risk: float,
    flood_risk: float,
    aqi_risk: float,
    closure_risk: float,
    shift_exposure: float,
    city: str,
) -> float:
    exp = exposure_index(
        rain_risk, flood_risk, aqi_risk, closure_risk, shift_exposure, city
    )
    return float(max(0.02, min(0.98, round(0.08 + 0.88 * exp, 4))))


actuarial_premium = actuarial_weekly_premium
