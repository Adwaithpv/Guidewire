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


def default_triggers(plan_id: str | None = None) -> list[tuple[str, float]]:
    base = [
        ("heavy_rain", 50),
        ("flood", 1),
        ("aqi_severe", 300),
        ("curfew", 1),
        ("platform_outage", 30),
    ]
    if plan_id and plan_id.startswith("her-"):
        base.append(("safety_incident", 1))
        base.append(("night_shift_disruption", 1))
        if plan_id in ("her-standard", "her-full"):
            pass  # already included above
        if plan_id == "her-full":
            base.append(("health_leave", 1))
    return base
