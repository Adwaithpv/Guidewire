from __future__ import annotations

from datetime import datetime, timedelta


def build_default_alert(zone_name: str) -> dict[str, str]:
    return {
        "alert_type": "weather_forecast",
        "forecast_window": f"{datetime.utcnow():%Y-%m-%d %H:%M} to {(datetime.utcnow() + timedelta(hours=2)):%H:%M} UTC",
        "risk_level": "high",
        "recommendation_text": (
            f"Heavy rain likely in {zone_name} soon. Prefer nearby deliveries and finish high-priority orders early."
        ),
    }
