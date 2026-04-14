"""
Simulated instant payout system — Razorpay test-mode style.

Generates realistic transaction IDs, status transitions, and timestamps
to demonstrate how workers receive lost wages via UPI.
"""
from __future__ import annotations

import random
import string
import time
from datetime import datetime, timezone
from typing import Any


def _txn_id() -> str:
    """Razorpay-style payment ID: pay_XXXXXXXXXXXXXX"""
    chars = string.ascii_letters + string.digits
    return "pay_" + "".join(random.choices(chars, k=14))


def _order_id() -> str:
    """Razorpay-style order ID: order_XXXXXXXXXX"""
    chars = string.ascii_letters + string.digits
    return "order_" + "".join(random.choices(chars, k=10))


def _upi_ref() -> str:
    """UPI transaction reference number."""
    return str(random.randint(100000000000, 999999999999))


def estimate_payout(avg_weekly_income: float, disrupted_hours: float, cap_remaining: float) -> tuple[float, float]:
    avg_hourly = avg_weekly_income / 42.0
    estimated_loss = disrupted_hours * avg_hourly
    payout = min(estimated_loss * 0.8, cap_remaining)
    return round(estimated_loss, 2), round(max(0.0, payout), 2)


def mock_razorpay_transfer(
    amount: float,
    worker_upi: str = "",
    worker_name: str = "",
) -> dict[str, Any]:
    """
    Simulates a Razorpay test-mode payout via UPI.
    Returns a realistic gateway response object.
    """
    txn = _txn_id()
    order = _order_id()
    upi_ref = _upi_ref()
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    success = random.random() < 0.95

    return {
        "gateway": "razorpay_test",
        "mode": "test",
        "status": "captured" if success else "failed",
        "payment_id": txn,
        "order_id": order,
        "amount_paise": int(amount * 100),
        "amount_inr": round(amount, 2),
        "currency": "INR",
        "method": "upi",
        "vpa": worker_upi or "worker@upi",
        "upi_transaction_id": upi_ref,
        "description": f"SurakshaShift claim payout to {worker_name or 'worker'}",
        "created_at": now_iso,
        "captured_at": now_iso if success else None,
        "error_code": None if success else "PAYMENT_FAILED",
        "error_description": None if success else "UPI transaction declined by bank",
        "settlement_eta": "instant" if success else None,
        "fee": round(amount * 0.02, 2) if success else 0,
        "tax": round(amount * 0.02 * 0.18, 2) if success else 0,
    }


def mock_gateway_transfer(amount: float) -> dict[str, str]:
    """Legacy wrapper for backward compat."""
    result = mock_razorpay_transfer(amount)
    return {
        "status": "success" if result["status"] == "captured" else "failed",
        "transaction_id": result["payment_id"],
        "message": f"Payout of {amount:.2f} processed successfully" if result["status"] == "captured" else "Payment failed",
    }
