from __future__ import annotations

from datetime import datetime, timedelta


def coverage_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    start = now or datetime.utcnow()
    end = start + timedelta(days=7)
    return start, end


def default_triggers() -> list[tuple[str, float]]:
    return [
        ("heavy_rain", 50),
        ("flood", 1),
        ("aqi_severe", 300),
        ("curfew", 1),
        ("platform_outage", 30),
    ]
