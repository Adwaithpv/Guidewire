"""
Weather data service — uses OpenWeatherMap free tier with mock fallback.
"""
from __future__ import annotations

import logging
import os
import random
import hashlib

import httpx

log = logging.getLogger(__name__)

OWM_KEY = (os.getenv("OPENWEATHERMAP_API_KEY") or "").strip()
OWM_URL = "https://api.openweathermap.org/data/2.5/weather"

# City coords for OWM
_COORDS: dict[str, tuple[float, float]] = {
    "Mumbai": (19.076, 72.8777), "Chennai": (13.0827, 80.2707),
    "Kolkata": (22.5726, 88.3639), "Bengaluru": (12.9716, 77.5946),
    "Delhi": (28.7041, 77.1025), "Hyderabad": (17.385, 78.4867),
    "Pune": (18.5204, 73.8567), "Ahmedabad": (23.0225, 72.5714),
    "Jaipur": (26.9124, 75.7873), "Lucknow": (26.8467, 80.9462),
}


def _mock_weather(city: str) -> dict:
    """Generate realistic mock weather when no API key available."""
    season_rain = random.uniform(0, 15)  # mm/hr
    temp = random.uniform(22, 42)
    wind = random.uniform(2, 25)
    conditions = random.choice(["Clear", "Clouds", "Rain", "Drizzle", "Thunderstorm", "Haze"])
    return {
        "source": "mock",
        "city": city,
        "temperature_c": round(temp, 1),
        "humidity": random.randint(30, 95),
        "wind_speed_kmh": round(wind, 1),
        "rain_mm_1h": round(season_rain, 1),
        "condition": conditions,
        "description": f"Mock: {conditions.lower()}",
    }


async def get_current_weather(city: str) -> dict:
    """Fetch current weather for a city. Falls back to mock if no API key."""
    if not OWM_KEY:
        log.info("No OWM key — using mock weather for %s", city)
        return _mock_weather(city)

    lat, lon = _COORDS.get(city, (12.97, 77.59))
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(OWM_URL, params={
                "lat": lat, "lon": lon, "appid": OWM_KEY, "units": "metric"
            })
            resp.raise_for_status()
            data = resp.json()

        rain_1h = data.get("rain", {}).get("1h", 0.0)
        return {
            "source": "openweathermap",
            "city": city,
            "temperature_c": round(data["main"]["temp"], 1),
            "humidity": data["main"]["humidity"],
            "wind_speed_kmh": round(data["wind"]["speed"] * 3.6, 1),
            "rain_mm_1h": round(rain_1h, 1),
            "condition": data["weather"][0]["main"],
            "description": data["weather"][0]["description"],
        }
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            log.warning(
                "OpenWeatherMap 401 for %s: API key rejected. Fix: use the key from "
                "https://home.openweathermap.org/api_keys (no spaces in .env), wait for "
                "activation after signup, then restart the server.",
                city,
            )
        else:
            log.warning("OWM API HTTP error for %s: %s — falling back to mock", city, exc)
        return _mock_weather(city)
    except Exception as exc:
        log.warning("OWM API error for %s: %s — falling back to mock", city, exc)
        return _mock_weather(city)


def _zone_geo_offset(zone_name: str) -> tuple[float, float]:
    """
    Deterministic micro-offset (about +/-4km range) to query nearby points
    within the same city for zone-level weather variation.
    """
    h = int(hashlib.sha256(zone_name.encode()).hexdigest()[:8], 16)
    # +/-0.04 degrees roughly ~4.4km lat, ~4km lon around Indian cities
    lat_off = ((h % 2001) - 1000) / 25000.0
    lon_off = (((h // 2001) % 2001) - 1000) / 25000.0
    return lat_off, lon_off


async def get_current_weather_for_zone(city: str, zone_name: str) -> dict:
    """
    Zone-aware weather snapshot by querying OpenWeatherMap near city center
    with deterministic zone-level geo offsets.
    """
    if not OWM_KEY:
        w = _mock_weather(city)
        # keep variation deterministic for repeated runs in the same zone
        lat_off, lon_off = _zone_geo_offset(zone_name)
        rain_delta = (lat_off + lon_off) * 25.0
        w["rain_mm_1h"] = round(max(0.0, float(w.get("rain_mm_1h", 0)) + rain_delta), 1)
        w["source"] = "mock-zone"
        w["zone_name"] = zone_name
        return w

    base_lat, base_lon = _COORDS.get(city, (12.97, 77.59))
    lat_off, lon_off = _zone_geo_offset(zone_name)
    lat, lon = base_lat + lat_off, base_lon + lon_off
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                OWM_URL,
                params={"lat": lat, "lon": lon, "appid": OWM_KEY, "units": "metric"},
            )
            resp.raise_for_status()
            data = resp.json()

        rain_1h = data.get("rain", {}).get("1h", 0.0)
        return {
            "source": "openweathermap-zone",
            "city": city,
            "zone_name": zone_name,
            "temperature_c": round(data["main"]["temp"], 1),
            "humidity": data["main"]["humidity"],
            "wind_speed_kmh": round(data["wind"]["speed"] * 3.6, 1),
            "rain_mm_1h": round(rain_1h, 1),
            "condition": data["weather"][0]["main"],
            "description": data["weather"][0]["description"],
            "lat": round(lat, 5),
            "lon": round(lon, 5),
        }
    except Exception as exc:
        log.warning(
            "OWM zone-weather API error for %s/%s: %s — falling back to city weather",
            city,
            zone_name,
            exc,
        )
        return await get_current_weather(city)


def weather_to_risk_factors(weather: dict) -> dict:
    """Convert raw weather data into normalized risk factors (0-1)."""
    rain = weather.get("rain_mm_1h", 0)
    wind = weather.get("wind_speed_kmh", 0)
    temp = weather.get("temperature_c", 30)
    condition = weather.get("condition", "Clear")

    rain_risk = min(1.0, rain / 50.0)  # 50mm/hr = max risk
    flood_risk = min(1.0, rain / 80.0) if rain > 20 else 0.0
    heat_risk = max(0, min(1.0, (temp - 38) / 10.0)) if temp > 38 else 0.0

    # Thunderstorm / heavy rain bump
    if condition in ("Thunderstorm",):
        rain_risk = max(rain_risk, 0.7)
        flood_risk = max(flood_risk, 0.4)

    return {
        "rain_risk": round(rain_risk, 3),
        "flood_risk": round(flood_risk, 3),
        "heat_risk": round(heat_risk, 3),
        "wind_risk": round(min(1.0, wind / 60.0), 3),
        "condition": condition,
        "is_disruptive": rain_risk > 0.5 or flood_risk > 0.3,
    }
