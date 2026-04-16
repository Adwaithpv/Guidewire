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
TWILIO_WHATSAPP_OVERRIDE_TO = (os.getenv("TWILIO_WHATSAPP_OVERRIDE_TO") or "").strip()

_client: Any = None
_client_key: tuple[str, str] | None = None


def _runtime_settings() -> dict[str, str]:
    """
    Read Twilio settings at call time so env changes are picked up
    after backend restarts and during local dev.
    """
    return {
        "sid": (os.getenv("TWILIO_ACCOUNT_SID") or TWILIO_SID or "").strip(),
        "token": (os.getenv("TWILIO_AUTH_TOKEN") or TWILIO_TOKEN or "").strip(),
        "from": (os.getenv("TWILIO_WHATSAPP_FROM") or TWILIO_WHATSAPP_FROM or "").strip(),
        "override_to": (os.getenv("TWILIO_WHATSAPP_OVERRIDE_TO") or TWILIO_WHATSAPP_OVERRIDE_TO or "").strip(),
    }


def _get_client() -> Any:
    global _client, _client_key
    settings = _runtime_settings()
    sid = settings["sid"]
    token = settings["token"]
    key = (sid, token)

    if _client is not None and _client_key == key:
        return _client
    if not sid or not token:
        return None
    try:
        from twilio.rest import Client
        _client = Client(sid, token)
        _client_key = key
        log.info("Twilio WhatsApp client initialized (SID: %s...)", sid[:8])
        return _client
    except ImportError:
        log.warning("twilio package not installed — pip install twilio")
        return None
    except Exception as e:
        log.warning("Twilio init failed: %s", e)
        return None


def is_configured() -> bool:
    settings = _runtime_settings()
    return bool(settings["sid"] and settings["token"] and settings["from"])


def runtime_status() -> dict[str, Any]:
    settings = _runtime_settings()
    return {
        "configured": bool(settings["sid"] and settings["token"] and settings["from"]),
        "from": settings["from"],
        "override_to": settings["override_to"],
        "sid_prefix": f"{settings['sid'][:6]}..." if settings["sid"] else "",
    }


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
    settings = _runtime_settings()
    twilio_from = settings["from"]
    override_to = settings["override_to"]

    if client is None or not twilio_from:
        log.info("WhatsApp (no-op): to=%s msg=%s", to_phone, message[:80])
        return {
            "sent": False,
            "reason": "twilio_not_configured",
            "message_preview": message[:80],
        }

    requested_to_wa = _format_phone(to_phone)
    to_wa = _format_phone(override_to) if override_to else requested_to_wa
    from_wa = twilio_from if twilio_from.startswith("whatsapp:") else f"whatsapp:{twilio_from}"

    try:
        msg = client.messages.create(
            body=message,
            from_=from_wa,
            to=to_wa,
        )
        log.info("WhatsApp queued: sid=%s to=%s status=%s error_code=%s",
                 msg.sid, to_wa, msg.status, msg.error_code)
        actually_sent = msg.status in ("queued", "sent", "delivered", "read")
        return {
            "sent": actually_sent,
            "sid": msg.sid,
            "twilio_status": msg.status,
            "error_code": msg.error_code,
            "error_message": msg.error_message,
            "to": to_wa,
            "requested_to": requested_to_wa,
            "override_active": bool(override_to),
            "hint": "If status is 'queued' but nothing arrives, re-join the Twilio sandbox: send 'join <your-keyword>' to the sandbox number.",
        }
    except Exception as e:
        log.warning("WhatsApp send failed to %s: %s", to_wa, e)
        return {
            "sent": False,
            "reason": str(e),
            "to": to_wa,
            "requested_to": requested_to_wa,
            "override_active": bool(override_to),
        }


def check_message_status(message_sid: str) -> dict[str, Any]:
    """Fetch actual delivery status of a previously sent message from Twilio."""
    client = _get_client()
    if client is None:
        return {"error": "twilio_not_configured"}
    try:
        msg = client.messages(message_sid).fetch()
        return {
            "sid": msg.sid,
            "status": msg.status,
            "error_code": msg.error_code,
            "error_message": msg.error_message,
            "date_sent": str(msg.date_sent) if msg.date_sent else None,
            "to": msg.to,
        }
    except Exception as e:
        return {"error": str(e)}

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


def notify_registration_welcome(
    to_phone: str,
    worker_name: str,
    city: str,
    zone_name: str,
) -> dict[str, Any]:
    message = (
        f"👋 *Welcome to SurakshaShift*\n\n"
        f"Hi {worker_name}, your account is set up.\n"
        f"📍 City: {city}\n"
        f"🧭 Zone: {zone_name}\n\n"
        f"Next step: activate a policy to start coverage.\n"
        f"Reply *menu* anytime for quick actions."
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


def notify_claim_created(
    to_phone: str,
    worker_name: str,
    claim_type: str,
    zone_name: str,
    severity: str,
    claim_id: int,
    review_status: str,
    expected_payout: float,
) -> dict[str, Any]:
    event_label = claim_type.replace("_", " ").title()
    status_label = (
        "under fraud review" if review_status == "manual_review" else "approved for processing"
    )
    message = (
        f"🧾 *New claim created*\n\n"
        f"Hi {worker_name}, we detected *{event_label}* in *{zone_name}* ({severity}).\n"
        f"Claim ID: *#{claim_id}*\n"
        f"Status: *{status_label}*\n"
        f"Estimated payout: *₹{expected_payout:.0f}*\n\n"
        f"We will keep you updated on payout progress."
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
