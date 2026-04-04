from __future__ import annotations

from datetime import datetime, timedelta, timezone


def build_default_alert(zone_name: str) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    return {
        "alert_type": "weather_forecast",
        "forecast_window": f"{now:%Y-%m-%d %H:%M} to {(now + timedelta(hours=2)):%H:%M} UTC",
        "risk_level": "high",
        "recommendation_text": (
            f"Heavy rain likely in {zone_name} soon. Prefer nearby deliveries and finish high-priority orders early."
        ),
    }
