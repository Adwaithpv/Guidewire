from datetime import datetime

from app.models.entities import DisruptionEvent, PolicyTrigger
from app.services.parametric_rules import (
    effective_loss_hours,
    event_satisfies_trigger_index,
)
from app.services.pricing_service import actuarial_weekly_premium


def test_effective_loss_hours_respects_shift_cap() -> None:
    start = datetime(2026, 4, 1, 8, 0, 0)
    end = datetime(2026, 4, 1, 22, 0, 0)
    h = effective_loss_hours("morning", start, end)
    assert h <= 6.0


def test_effective_loss_hours_multi_day_cap() -> None:
    start = datetime(2026, 4, 1, 0, 0, 0)
    end = datetime(2026, 4, 3, 23, 0, 0)
    h = effective_loss_hours("full_day", start, end)
    assert h <= 11.0 * 3


def test_heavy_rain_trigger_requires_mm_when_payload_present() -> None:
    ev = DisruptionEvent(
        event_type="heavy_rain",
        zone_id=1,
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
        severity="high",
        source_name="test",
        source_payload='{"rainfall_mm": 20}',
        is_verified=True,
    )
    trig = PolicyTrigger(policy_id=1, trigger_type="heavy_rain", threshold_value=50.0, payout_formula_type="hour_based")
    assert event_satisfies_trigger_index(ev, trig) is False

    ev2 = DisruptionEvent(
        event_type="heavy_rain",
        zone_id=1,
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
        severity="high",
        source_name="test",
        source_payload='{"rainfall_mm": 62}',
        is_verified=True,
    )
    assert event_satisfies_trigger_index(ev2, trig) is True


def test_actuarial_premium_rises_with_exposure() -> None:
    low = actuarial_weekly_premium(0.1, 0.05, 0.05, 0.05, 0.35, 2800, "Jaipur")
    high = actuarial_weekly_premium(0.55, 0.45, 0.4, 0.12, 0.85, 2800, "Mumbai")
    assert 19 <= low <= 99
    assert 19 <= high <= 99
    assert high > low
