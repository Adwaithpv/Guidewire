"""
WhatsApp notification service via Twilio.

Uses the Twilio WhatsApp sandbox for development or a production WhatsApp
Business number when configured. Gracefully degrades to logging when
credentials are missing (so the app works without Twilio for other devs).

Setup:
  1. Sign up at https://www.twilio.com (free trial gives $15 credit)
  2. Go to Console → Messaging → Try WhatsApp → join sandbox
  3. Copy Account SID, Auth Token, and sandbox number to .env
  4. Have the recipient send "join <sandbox-keyword>" to the sandbox number first
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

TWILIO_SID = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
TWILIO_TOKEN = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
TWILIO_WHATSAPP_FROM = (os.getenv("TWILIO_WHATSAPP_FROM") or "").strip()

_client: Any = None


def _get_client() -> Any:
    global _client
    if _client is not None:
        return _client
    if not TWILIO_SID or not TWILIO_TOKEN:
        return None
    try:
        from twilio.rest import Client
        _client = Client(TWILIO_SID, TWILIO_TOKEN)
        log.info("Twilio WhatsApp client initialized (SID: %s...)", TWILIO_SID[:8])
        return _client
    except ImportError:
        log.warning("twilio package not installed — pip install twilio")
        return None
    except Exception as e:
        log.warning("Twilio init failed: %s", e)
        return None


def is_configured() -> bool:
    return bool(TWILIO_SID and TWILIO_TOKEN and TWILIO_WHATSAPP_FROM)


def _format_phone(phone: str) -> str:
    """Ensure phone is in whatsapp:+91XXXXXXXXXX format."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 10:
        digits = "91" + digits
    if not digits.startswith("91"):
        digits = "91" + digits
    return f"whatsapp:+{digits}"


def send_whatsapp(
    to_phone: str,
    message: str,
) -> dict[str, Any]:
    """
    Send a WhatsApp message. Returns status dict.
    Falls back to a log entry when Twilio isn't configured.
    """
    client = _get_client()
    if client is None or not TWILIO_WHATSAPP_FROM:
        log.info("WhatsApp (no-op): to=%s msg=%s", to_phone, message[:80])
        return {
            "sent": False,
            "reason": "twilio_not_configured",
            "message_preview": message[:80],
        }

    to_wa = _format_phone(to_phone)
    from_wa = TWILIO_WHATSAPP_FROM if TWILIO_WHATSAPP_FROM.startswith("whatsapp:") else f"whatsapp:{TWILIO_WHATSAPP_FROM}"

    try:
        msg = client.messages.create(
            body=message,
            from_=from_wa,
            to=to_wa,
        )
        log.info("WhatsApp sent: sid=%s to=%s", msg.sid, to_wa)
        return {
            "sent": True,
            "sid": msg.sid,
            "status": msg.status,
            "to": to_wa,
        }
    except Exception as e:
        log.warning("WhatsApp send failed to %s: %s", to_wa, e)
        return {
            "sent": False,
            "reason": str(e),
            "to": to_wa,
        }

# ---------------------------------------------------------------------------
# Pre-built message templates
# ---------------------------------------------------------------------------

def notify_claim_paid(
    to_phone: str,
    worker_name: str,
    claim_type: str,
    payout_amount: float,
    gateway_ref: str,
    upi_id: str,
) -> dict[str, Any]:
    event_label = claim_type.replace("_", " ").title()
    message = (
        f"✅ *Payout sent successfully*\n\n"
        f"Hi {worker_name},\n"
        f"We approved your *{event_label}* claim.\n\n"
        f"💰 Amount: *₹{payout_amount:.0f}*\n"
        f"🏦 UPI: {upi_id}\n"
        f"🔗 Ref ID: {gateway_ref}\n\n"
        f"Thanks for using SurakshaShift. Ride safe! 🛡️"
    )
    return send_whatsapp(to_phone, message)


def notify_policy_activated(
    to_phone: str,
    worker_name: str,
    plan_label: str,
    premium: float,
    max_payout: float,
    zone_name: str,
) -> dict[str, Any]:
    message = (
        f"🛡️ *Your policy is now active*\n\n"
        f"Hi {worker_name},\n"
        f"Your *{plan_label}* plan is live for *{zone_name}*.\n\n"
        f"📋 Weekly premium: ₹{premium:.0f}\n"
        f"💰 Max weekly payout: ₹{max_payout:.0f}\n\n"
        f"You are covered for rain, flood, severe AQI, curfew/closure, and platform outage.\n"
        f"If disruption happens in your zone, we auto-create the claim and pay to your UPI."
    )
    return send_whatsapp(to_phone, message)


def notify_disruption_alert(
    to_phone: str,
    worker_name: str,
    event_type: str,
    zone_name: str,
    severity: str,
) -> dict[str, Any]:
    event_label = event_type.replace("_", " ").title()
    message = (
        f"⚠️ *Disruption alert*\n\n"
        f"Hi {worker_name},\n"
        f"We detected *{event_label}* ({severity}) in *{zone_name}*.\n\n"
        f"Good news: this is covered under your policy.\n"
        f"If affected, your claim will be processed automatically.\n\n"
        f"Please stay safe and check the app for live updates."
    )
    return send_whatsapp(to_phone, message)


def notify_shift_guardian(
    to_phone: str,
    worker_name: str,
    current_zone: str,
    recommended_zone: str,
    disruption_prob: float,
    income_diff: float,
) -> dict[str, Any]:
    message = (
        f"🧭 *Shift Guardian update*\n\n"
        f"Hi {worker_name},\n"
        f"Before you start in *{current_zone}*:\n"
        f"📍 Disruption risk there is *{disruption_prob:.0f}%*.\n"
    )
    if recommended_zone != current_zone and income_diff > 0:
        message += (
            f"✅ Better option right now: *{recommended_zone}*\n"
            f"💡 Estimated extra protected earnings: *+₹{income_diff:.0f}*\n"
        )
    else:
        message += "✅ Your current zone looks okay for this shift.\n"
    message += "\nReply *menu* anytime for quick actions."
    return send_whatsapp(to_phone, message)
