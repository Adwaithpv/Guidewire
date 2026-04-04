from app.services.pricing_service import (
    PLANS,
    actuarial_weekly_premium,
    exposure_index,
    quote_all_plans,
    quote_plan,
)


def test_exposure_index_zero_full_and_mixed() -> None:
    zero = exposure_index(0, 0, 0, 0, 0, "Bengaluru")
    full = exposure_index(1, 1, 1, 1, 1, "Mumbai")
    mixed = exposure_index(0.35, 0.25, 0.3, 0.1, 0.7, "Pune")
    assert zero == 0.0
    assert 0.0 <= mixed <= 1.0
    assert full <= 1.0
    assert full > mixed > zero


def test_quote_plan_within_bounds_all_tiers() -> None:
    for plan_id, cfg in PLANS.items():
        out = quote_plan(plan_id, 0.4, 0.25, 0.2, 0.1, 0.75, 4000, "Bengaluru")
        assert cfg["min_premium"] <= out["premium_weekly"] <= cfg["max_premium"]


def test_higher_risk_means_higher_premium_within_plan() -> None:
    income = 4000
    low = quote_plan("standard", 0.1, 0.05, 0.05, 0.05, 0.35, income, "Mumbai")
    high = quote_plan("standard", 0.7, 0.55, 0.45, 0.25, 0.9, income, "Mumbai")
    assert high["premium_weekly"] >= low["premium_weekly"]
    assert not (low["at_floor"] and high["at_floor"])
    assert not (low["at_ceiling"] and high["at_ceiling"])


def test_higher_income_means_higher_premium_below_ceiling() -> None:
    low_income = quote_plan("standard", 0.28, 0.18, 0.15, 0.1, 0.65, 1600, "Bengaluru")
    high_income = quote_plan("standard", 0.28, 0.18, 0.15, 0.1, 0.65, 2600, "Bengaluru")
    assert not low_income["at_ceiling"]
    assert not high_income["at_ceiling"]
    assert high_income["premium_weekly"] > low_income["premium_weekly"]


def test_tier_ordering_premium_and_payout() -> None:
    basic = quote_plan("basic", 0.35, 0.2, 0.2, 0.1, 0.7, 4000, "Pune")
    standard = quote_plan("standard", 0.35, 0.2, 0.2, 0.1, 0.7, 4000, "Pune")
    full = quote_plan("full", 0.35, 0.2, 0.2, 0.1, 0.7, 4000, "Pune")
    assert full["premium_weekly"] >= standard["premium_weekly"] >= basic["premium_weekly"]
    assert full["max_weekly_payout"] > standard["max_weekly_payout"] > basic["max_weekly_payout"]


def test_quote_all_plans_returns_three_expected_ids() -> None:
    plans = quote_all_plans(0.3, 0.2, 0.15, 0.1, 0.75, 4000, "Delhi")
    ids = [p["plan_id"] for p in plans]
    assert len(plans) == 3
    assert ids == ["basic", "standard", "full"]


def test_affordability_under_150_at_4000_income() -> None:
    plans = quote_all_plans(0.45, 0.3, 0.25, 0.12, 0.8, 4000, "Mumbai")
    assert all(float(p["premium_weekly"]) < 150.0 for p in plans)


def test_backcompat_actuarial_weekly_premium_ordering() -> None:
    # Keep both quotes away from plan floor/ceiling so monotonicity is measurable.
    income = 2500
    low = actuarial_weekly_premium(0.24, 0.18, 0.16, 0.08, 0.55, income, "Mumbai")
    high = actuarial_weekly_premium(0.55, 0.45, 0.4, 0.2, 0.9, income, "Mumbai")
    assert high > low
