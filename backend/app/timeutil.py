"""UTC-naive datetimes for consistent SQLite/Postgres comparisons in ORM filters."""
from __future__ import annotations

from datetime import datetime, timezone


def to_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)
