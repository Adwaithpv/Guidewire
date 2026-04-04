from __future__ import annotations

import asyncio
from datetime import datetime

from app.ml.premium_model import model as _ml_model
from app.schemas.common import LiveRiskFactors
from app.services.pricing_service import (
    actuarial_weekly_premium,
    blend_premium,
    linear_risk_score,
)


def shift_type_to_exposure(shift_type: str) -> float:
    return {
        "morning": 0.6,
        "afternoon": 0.8,
        "evening": 0.9,
        "night": 1.0,
        "full_day": 0.85,
        "split": 0.75,
    }.get(shift_type, 0.75)


def calculate_risk_score(
    rain_risk: float,
    flood_risk: float,
    aqi_risk: float,
    closure_risk: float,
    shift_exposure: float,
    avg_weekly_income: float = 3500.0,
    city: str = "Bengaluru",
) -> float:
    """Transparent exposure index blended with GBM so live APIs move the score predictably."""
    linear = linear_risk_score(
        rain_risk, flood_risk, aqi_risk, closure_risk, shift_exposure, city
    )
    ml = _ml_model.predict_risk_score(
        rain_risk, flood_risk, aqi_risk, closure_risk,
        shift_exposure, avg_weekly_income, city,
    )
    return round(0.55 * linear + 0.45 * ml, 4)


def quote_premium(
    rain_risk: float,
    flood_risk: float,
    aqi_risk: float,
    closure_risk: float,
    shift_exposure: float,
    avg_weekly_income: float = 3500.0,
    city: str = "Bengaluru",
) -> float:
    """Weekly premium: interpretable loss-cost + admin, blended with GBM (Phase 2)."""
    actuarial = actuarial_weekly_premium(
        rain_risk, flood_risk, aqi_risk, closure_risk,
        shift_exposure, avg_weekly_income, city,
    )
    ml = _ml_model.predict_premium(
        rain_risk, flood_risk, aqi_risk, closure_risk,
        shift_exposure, avg_weekly_income, city,
    )
    return blend_premium(actuarial, ml, ml_weight=0.20)


def quote_max_payout(avg_weekly_income: float) -> float:
    return round(avg_weekly_income * 0.4, 2)


def get_risk_explanation(city: str = "Bengaluru") -> dict:
    """GBM feature importances + narrative (pricing also uses an actuarial loss-cost layer)."""
    importances = _ml_model.get_feature_importances()
    top_factor = max(importances, key=importances.get)  # type: ignore[arg-type]
    explanation = (
        f"About 80% of your weekly premium comes from an actuarial formula: admin load plus "
        f"expected loss (max payout × exposure) grossed up for a 65% loss-ratio target, "
        f"then a 15% margin — with city weights aligned to IMD-style regional rainfall exposure. "
        f"About 20% is a GBM blend trained on actuarial-anchored scenarios. "
        f"The sensitivity chart reflects tree splits on that training set, not live rain %. "
        f"Use the this-quote exposure bars for today's inputs. "
        f"Claims need a verified zone event; news only nudges pricing."
    )
    return {"importances": importances, "explanation": explanation}


async def fetch_live_risk_factors(city: str) -> LiveRiskFactors:
    """Real-time weather + AQI + news (closures/bandhs) → normalized factors."""
    from app.services.aqi_service import aqi_to_risk_factor, get_current_aqi
    from app.services.news_service import get_closure_signal_from_news
    from app.services.weather_service import get_current_weather, weather_to_risk_factors

    weather, aqi_data, news_closure = await asyncio.gather(
        get_current_weather(city),
        get_current_aqi(city),
        get_closure_signal_from_news(city),
    )
    weather_risks = weather_to_risk_factors(weather)
    aqi_risks = aqi_to_risk_factor(aqi_data)

    rain_risk = weather_risks["rain_risk"]
    flood_risk = weather_risks["flood_risk"]
    aqi_risk = aqi_risks["aqi_risk"]
    closure_risk = float(news_closure["closure_risk"])
    closure_source = str(news_closure["source"])
    closure_headlines = list(news_closure.get("headlines") or [])

    is_disruptive = (
        weather_risks["is_disruptive"]
        or aqi_risks["is_disruptive"]
        or closure_risk >= 0.18
    )

    if is_disruptive:
        overall = "critical"
    elif rain_risk > 0.3 or aqi_risk > 0.3:
        overall = "elevated"
    else:
        overall = "low"

    fetched_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    return LiveRiskFactors(
        city=city,
        weather=weather,
        aqi=aqi_data,
        rain_risk=rain_risk,
        flood_risk=flood_risk,
        aqi_risk=aqi_risk,
        closure_risk=closure_risk,
        closure_source=closure_source,
        closure_headlines=closure_headlines,
        overall_risk=overall,
        is_disruptive=is_disruptive,
        fetched_at=fetched_at,
    )


def fetch_live_risk_factors_sync(city: str) -> LiveRiskFactors:
    """Sync wrapper for non-async routes (e.g. policy quote)."""
    return asyncio.run(fetch_live_risk_factors(city))
