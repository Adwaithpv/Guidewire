"""
Shift Guardian: pre-shift zone comparison using zone-level weather/AQI/news signals.
"""
from __future__ import annotations

import asyncio
import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.aqi_service import aqi_to_risk_factor, get_current_aqi
from app.services.news_service import get_closure_signal_from_news
from app.services.weather_service import _COORDS, _zone_geo_offset, get_current_weather_for_zone, weather_to_risk_factors

_CITY_ZONE_SUGGESTIONS: dict[str, list[str]] = {
    "Bengaluru": ["HSR Layout", "Koramangala", "Indiranagar", "Whitefield", "JP Nagar", "OMR", "Electronic City"],
    "Mumbai": ["Andheri", "Bandra", "Kurla", "Thane", "Powai"],
    "Delhi": ["Connaught Place", "Lajpat Nagar", "Dwarka", "Rohini", "Saket"],
    "Chennai": ["Anna Nagar", "T Nagar", "Velachery", "Adyar", "Tambaram"],
    "Kolkata": ["Salt Lake", "Park Street", "Howrah", "Dum Dum", "Behala"],
    "Hyderabad": ["Hitech City", "Banjara Hills", "Secunderabad", "Kukatpally", "LB Nagar"],
    "Pune": ["Kothrud", "Viman Nagar", "Hadapsar", "Wakad", "Aundh"],
    "Ahmedabad": ["Navrangpura", "Satellite", "Maninagar", "Bopal", "CG Road"],
    "Jaipur": ["C-Scheme", "Malviya Nagar", "Vaishali Nagar", "Mansarovar", "Raja Park"],
    "Lucknow": ["Hazratganj", "Gomti Nagar", "Alambagh", "Indira Nagar", "Aliganj"],
}


def _zone_micro_bias(zone_name: str) -> float:
    """Tiny deterministic spread so same-city zones are not identical in demos (±3% composite)."""
    h = int(hashlib.sha256(zone_name.encode()).hexdigest()[:8], 16)
    return (h % 2000) / 1_000_000.0 - 0.001  # [-0.001, 0.000999]


@dataclass
class ZoneRiskSnapshot:
    zone_name: str
    city: str
    rain_risk: float
    flood_risk: float
    aqi_risk: float
    closure_risk: float
    composite_risk: float
    risk_level: str
    is_disruptive: bool
    disruption_probability: float
    estimated_safe_hours: float
    income_protection_score: float


@dataclass
class ShiftRecommendation:
    recommended_zone: ZoneRiskSnapshot
    current_zone: ZoneRiskSnapshot
    alternatives: list[ZoneRiskSnapshot]
    estimated_income_difference: float
    recommendation_text: str
    alert_type: str
    risk_level: str
    forecast_window: str
    generated_at: str


def _composite_risk(rain: float, flood: float, aqi: float, closure: float, zone_name: str) -> float:
    base = 0.35 * rain + 0.25 * flood + 0.22 * aqi + 0.18 * closure
    return max(0.0, min(1.0, round(base + _zone_micro_bias(zone_name), 4)))


def _risk_level(composite: float) -> str:
    if composite < 0.15:
        return "low"
    if composite < 0.35:
        return "moderate"
    if composite < 0.60:
        return "high"
    return "critical"


def _disruption_probability(composite: float) -> float:
    return round(min(90.0, 100 * (1 - math.exp(-3.5 * composite))), 1)


def _income_protection_score(composite: float) -> float:
    return round(max(0.0, 100 * (1 - composite * 1.2)), 1)


def _estimated_safe_hours(composite: float, shift_hours: float = 8.0) -> float:
    disruption_fraction = min(0.9, composite * 1.5)
    return round(shift_hours * (1 - disruption_fraction), 1)


def _shift_hours(shift_type: str) -> float:
    return {
        "morning": 6.0,
        "afternoon": 6.0,
        "evening": 7.0,
        "night": 8.0,
        "full_day": 10.0,
        "split": 8.0,
    }.get(shift_type, 8.0)


async def _build_zone_snapshot(zone_name: str, city: str, shift_type: str) -> ZoneRiskSnapshot:
    base_lat, base_lon = _COORDS.get(city, (12.97, 77.59))
    lat_off, lon_off = _zone_geo_offset(zone_name)
    lat, lon = base_lat + lat_off, base_lon + lon_off

    weather, aqi_data, news = await asyncio.gather(
        get_current_weather_for_zone(city, zone_name),
        get_current_aqi(city, lat=lat, lon=lon, zone_name=zone_name),
        get_closure_signal_from_news(city, locality=zone_name),
    )
    weather_risks = weather_to_risk_factors(weather)
    aqi_risks = aqi_to_risk_factor(aqi_data)
    rain_risk = weather_risks["rain_risk"]
    flood_risk = weather_risks["flood_risk"]
    aqi_risk = aqi_risks["aqi_risk"]
    closure_risk = float(news["closure_risk"])
    composite = _composite_risk(rain_risk, flood_risk, aqi_risk, closure_risk, zone_name)
    level = _risk_level(composite)
    sh = _shift_hours(shift_type)
    return ZoneRiskSnapshot(
        zone_name=zone_name,
        city=city,
        rain_risk=rain_risk,
        flood_risk=flood_risk,
        aqi_risk=aqi_risk,
        closure_risk=closure_risk,
        composite_risk=composite,
        risk_level=level,
        is_disruptive=composite > 0.35,
        disruption_probability=_disruption_probability(composite),
        estimated_safe_hours=_estimated_safe_hours(composite, sh),
        income_protection_score=_income_protection_score(composite),
    )


def _build_recommendation_text(
    current: ZoneRiskSnapshot,
    best: ZoneRiskSnapshot,
    income_diff: float,
) -> str:
    if best.zone_name == current.zone_name:
        if current.risk_level == "low":
            return (
                f"Your zone {current.zone_name} looks favourable. "
                f"Disruption probability is about {current.disruption_probability}% — "
                f"reasonable conditions to protect earnings this shift."
            )
        return (
            f"{current.zone_name} shows {current.risk_level} disruption risk "
            f"({current.disruption_probability}% estimated). "
            f"No clearly safer nearby zone right now — monitor conditions."
        )

    return (
        f"Consider {best.zone_name} before you start: disruption probability "
        f"falls from about {current.disruption_probability}% to {best.disruption_probability}%. "
        f"Estimated extra protected earnings this shift: ₹{income_diff:.0f}."
    )


def _roster_for_city(city: str, current_zone: str) -> list[str]:
    base = list(_CITY_ZONE_SUGGESTIONS.get(city, []))
    if current_zone and current_zone not in base:
        base = [current_zone] + base
    return base if base else ([current_zone] if current_zone else ["Delivery zone"])


async def generate_shift_recommendation(
    worker_id: int,
    current_zone: str,
    city: str,
    avg_weekly_income: float,
    shift_type: str = "full_day",
) -> ShiftRecommendation:
    _ = worker_id
    roster = _roster_for_city(city, current_zone)
    candidate_zones = [z for z in roster if z != current_zone]
    all_zones = [current_zone] + candidate_zones

    snapshots = await asyncio.gather(
        *[_build_zone_snapshot(z, city, shift_type) for z in all_zones]
    )
    current_snapshot = snapshots[0]
    alternatives = list(snapshots[1:])

    best = max([current_snapshot] + alternatives, key=lambda z: z.income_protection_score)

    avg_hourly = avg_weekly_income / 42.0
    income_diff = max(
        0.0,
        (best.estimated_safe_hours - current_snapshot.estimated_safe_hours) * avg_hourly,
    )

    if best.zone_name != current_zone and income_diff > 50:
        alert_type = "zone_switch_recommended"
    elif current_snapshot.is_disruptive:
        alert_type = "disruption_warning"
    else:
        alert_type = "all_clear"

    now = datetime.now(timezone.utc)
    forecast_window = f"{now:%Y-%m-%d %H:%M} UTC → {(now + timedelta(hours=4)):%H:%M} UTC"

    return ShiftRecommendation(
        recommended_zone=best,
        current_zone=current_snapshot,
        alternatives=alternatives,
        estimated_income_difference=round(income_diff, 2),
        recommendation_text=_build_recommendation_text(current_snapshot, best, income_diff),
        alert_type=alert_type,
        risk_level=best.risk_level,
        forecast_window=forecast_window,
        generated_at=now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )


def recommendation_to_api_dict(rec: ShiftRecommendation) -> dict[str, Any]:
    def snap(z: ZoneRiskSnapshot) -> dict[str, Any]:
        return {
            "zone_name": z.zone_name,
            "city": z.city,
            "risk_level": z.risk_level,
            "disruption_probability": z.disruption_probability,
            "income_protection_score": z.income_protection_score,
            "estimated_safe_hours": z.estimated_safe_hours,
            "composite_risk": z.composite_risk,
        }

    return {
        "recommendation_text": rec.recommendation_text,
        "alert_type": rec.alert_type,
        "risk_level": rec.risk_level,
        "forecast_window": rec.forecast_window,
        "generated_at": rec.generated_at,
        "estimated_income_difference": rec.estimated_income_difference,
        "recommended_zone": snap(rec.recommended_zone),
        "current_zone": snap(rec.current_zone),
        "alternatives": [snap(z) for z in rec.alternatives],
    }
