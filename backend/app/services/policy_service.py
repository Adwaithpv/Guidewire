from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.timeutil import to_utc_naive


def coverage_window(coverage_start: datetime | None = None) -> tuple[datetime, datetime]:
    """
    Weekly policy window. When coverage_start is None, window starts at current UTC (naive).
    Otherwise starts at coverage_start (e.g. renewal chaining from previous coverage_end).
    """
    if coverage_start is None:
        base = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        base = to_utc_naive(coverage_start)
    end = base + timedelta(days=7)
    return base, end


def default_triggers() -> list[tuple[str, float]]:
    return [
        ("heavy_rain", 50),
        ("flood", 1),
        ("aqi_severe", 300),
        ("curfew", 1),
        ("platform_outage", 30),
    ]
