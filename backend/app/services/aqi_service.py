"""
Air Quality Index service — uses WAQI (aqicn.org) free tier with mock fallback.
"""
from __future__ import annotations

import logging
import os
import random
import hashlib

import httpx

log = logging.getLogger(__name__)

WAQI_TOKEN = os.getenv("WAQI_API_TOKEN", "")
WAQI_URL = "https://api.waqi.info/feed"


def _mock_aqi(city: str) -> dict:
    """Generate realistic mock AQI data."""
    # Delhi/Kolkata/Lucknow tend to have higher AQI
    base = 180 if city in ("Delhi", "Kolkata", "Lucknow") else 90
    aqi_val = max(20, int(random.gauss(base, 60)))
    dominant = random.choice(["pm25", "pm10", "o3", "no2"])
    return {
        "source": "mock",
        "city": city,
        "aqi": aqi_val,
        "dominant_pollutant": dominant,
        "category": _aqi_category(aqi_val),
    }


def _aqi_category(aqi: int) -> str:
    if aqi <= 50:
        return "good"
    if aqi <= 100:
        return "moderate"
    if aqi <= 150:
        return "unhealthy_sensitive"
    if aqi <= 200:
        return "unhealthy"
    if aqi <= 300:
        return "very_unhealthy"
    return "hazardous"


def _zone_aqi_bias(zone_name: str) -> int:
    h = int(hashlib.sha256(zone_name.encode()).hexdigest()[:8], 16)
    return (h % 35) - 17  # [-17, +17]


async def get_current_aqi(city: str, lat: float | None = None, lon: float | None = None, zone_name: str | None = None) -> dict:
    """Fetch current AQI for a city. Falls back to mock if no API token."""
    if not WAQI_TOKEN:
        log.info("No WAQI token — using mock AQI for %s", city)
        out = _mock_aqi(city)
        if zone_name:
            out["aqi"] = max(20, int(out["aqi"]) + _zone_aqi_bias(zone_name))
            out["source"] = "mock-zone"
            out["zone_name"] = zone_name
        return out

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if lat is not None and lon is not None:
                resp = await client.get(f"{WAQI_URL}/geo:{lat:.5f};{lon:.5f}/", params={"token": WAQI_TOKEN})
            else:
                resp = await client.get(f"{WAQI_URL}/{city}/", params={"token": WAQI_TOKEN})
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "ok":
            raise ValueError(f"WAQI returned status: {data.get('status')}")

        aqi_data = data["data"]
        aqi_val = int(aqi_data["aqi"])
        dominant = aqi_data.get("dominentpol", "pm25")
        return {
            "source": "waqi-zone" if lat is not None and lon is not None else "waqi",
            "city": city,
            "zone_name": zone_name,
            "aqi": aqi_val,
            "dominant_pollutant": dominant,
            "category": _aqi_category(aqi_val),
        }
    except Exception as exc:
        log.warning("WAQI API error for %s: %s — falling back to mock", city, exc)
        return _mock_aqi(city)


def aqi_to_risk_factor(aqi_data: dict) -> dict:
    """Convert raw AQI data into normalized risk factors."""
    aqi_val = aqi_data.get("aqi", 50)
    # Risk ramps up after AQI 150, severe at 300+
    risk = min(1.0, max(0.0, (aqi_val - 100) / 200.0))
    is_severe = aqi_val >= 300
    return {
        "aqi_value": aqi_val,
        "aqi_risk": round(risk, 3),
        "category": aqi_data.get("category", "moderate"),
        "is_disruptive": is_severe,
    }
