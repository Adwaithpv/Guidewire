from __future__ import annotations

import random


def estimate_payout(avg_weekly_income: float, disrupted_hours: float, cap_remaining: float) -> tuple[float, float]:
    avg_hourly = avg_weekly_income / 42.0
    estimated_loss = disrupted_hours * avg_hourly
    payout = min(estimated_loss * 0.8, cap_remaining)
    return round(estimated_loss, 2), round(max(0.0, payout), 2)


def mock_gateway_transfer(amount: float) -> dict[str, str]:
    return {
        "status": "success",
        "transaction_id": f"TXN{random.randint(100000, 999999)}",
        "message": f"Payout of {amount:.2f} processed successfully",
    }
