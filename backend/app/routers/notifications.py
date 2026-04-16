"""
WhatsApp notification endpoints + inbound bot webhook.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Claim, Policy, User, WorkerProfile, Zone
from app.services.risk_service import fetch_live_risk_factors
from app.services.shift_guardian_service import generate_shift_recommendation
from app.services.whatsapp_service import (
    check_message_status,
    is_configured,
    notify_policy_activated,
    notify_shift_guardian,
    runtime_status,
    send_whatsapp,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])

WHATSAPP_DEMO_OTP = "123456"
WHATSAPP_SESSION_TTL_MINUTES = 60
_whatsapp_auth_sessions: dict[str, dict[str, Any]] = {}
_whatsapp_auth_pending: dict[str, dict[str, Any]] = {}


class WhatsAppTestRequest(BaseModel):
    phone: str
    message: str = "Hello from SurakshaShift! Your income protection is active. 🛡️"


def _norm_phone_digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _twiml_message(text: str) -> Response:
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{escape(text)}</Message></Response>"
    )
    return Response(content=body, media_type="application/xml")


def _menu_text() -> str:
    return (
        "👋 *Welcome to SurakshaShift WhatsApp Bot*\n\n"
        "Reply with one word:\n"
        "• *login* - verify your account first\n"
        "• *logout* - clear this chat session\n"
        "• *status* - your active policy\n"
        "• *claims* - your recent claims\n"
        "• *risk* - live risk in your city\n"
        "• *guardian* - safer zone suggestion before shift\n"
        "• *help* - show this menu again"
    )


def _find_worker_by_whatsapp_sender(
    db: Session,
    from_value: str,
) -> tuple[WorkerProfile, User] | tuple[None, None]:
    digits = _norm_phone_digits(from_value)
    # Twilio inbound From can be whatsapp:+9198XXXXXXXX. Most profiles store 10-digit local phone.
    candidates = []
    if len(digits) >= 10:
        candidates.append(digits[-10:])
    if digits:
        candidates.append(digits)

    for c in candidates:
        user = db.scalar(select(User).where(User.phone == c))
        if user:
            worker = db.scalar(
                select(WorkerProfile)
                .where(WorkerProfile.user_id == user.id)
                .order_by(WorkerProfile.id.desc())
            )
            if worker:
                return worker, user

    # Fallback: lenient suffix lookup for phones saved with country code/prefix formatting.
    if len(digits) >= 10:
        tail10 = digits[-10:]
        users = db.scalars(select(User)).all()
        for user in users:
            if _norm_phone_digits(user.phone).endswith(tail10):
                worker = db.scalar(
                    select(WorkerProfile)
                    .where(WorkerProfile.user_id == user.id)
                    .order_by(WorkerProfile.id.desc())
                )
                if worker:
                    return worker, user
    return None, None


def _prune_expired_whatsapp_sessions() -> None:
    now = datetime.now(timezone.utc)
    for sender, session in list(_whatsapp_auth_sessions.items()):
        expires_at = session.get("expires_at")
        if isinstance(expires_at, datetime) and expires_at <= now:
            _whatsapp_auth_sessions.pop(sender, None)


def _mask_phone(value: str) -> str:
    digits = _norm_phone_digits(value)
    if len(digits) < 4:
        return "****"
    return f"***{digits[-4:]}"


@router.get("/whatsapp/status")
def whatsapp_status() -> dict:
    status = runtime_status()
    status["configured"] = bool(is_configured())
    return status


@router.post("/whatsapp/test")
def test_whatsapp(payload: WhatsAppTestRequest) -> dict:
    result = send_whatsapp(payload.phone, payload.message)
    return result


@router.get("/whatsapp/message-status/{message_sid}")
def get_message_status(message_sid: str) -> dict:
    """Check actual delivery status of a Twilio message by SID."""
    return check_message_status(message_sid)


@router.post("/whatsapp/policy-activated/{worker_id}")
def send_policy_notification(worker_id: int, db: Session = Depends(get_db)) -> dict:
    worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == worker_id))
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    zone = db.scalar(select(Zone).where(Zone.id == worker.primary_zone_id))
    user = worker.user

    policy = db.scalar(
        select(Policy).where(Policy.worker_id == worker_id, Policy.status == "active")
    )
    if not policy:
        raise HTTPException(status_code=404, detail="No active policy")

    plan_labels = {
        "weekly-basic": "Basic Shield",
        "weekly-standard": "Standard Shield",
        "weekly-full": "Full Shield",
    }

    result = notify_policy_activated(
        to_phone=user.phone,
        worker_name=user.name,
        plan_label=plan_labels.get(policy.plan_name, policy.plan_name),
        premium=float(policy.premium_weekly),
        max_payout=float(policy.max_weekly_payout),
        zone_name=zone.zone_name if zone else "your zone",
    )
    return result


@router.post("/whatsapp/shift-guardian/{worker_id}")
async def send_shift_guardian_notification(worker_id: int, db: Session = Depends(get_db)) -> dict:
    worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == worker_id))
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    zone = db.scalar(select(Zone).where(Zone.id == worker.primary_zone_id))
    user = worker.user

    rec = await generate_shift_recommendation(
        worker_id=worker.id,
        current_zone=zone.zone_name if zone else "Delivery zone",
        city=zone.city if zone else "Bengaluru",
        avg_weekly_income=worker.avg_weekly_income,
        shift_type=worker.shift_type,
    )

    result = notify_shift_guardian(
        to_phone=user.phone,
        worker_name=user.name,
        current_zone=rec.current_zone.zone_name,
        recommended_zone=rec.recommended_zone.zone_name,
        disruption_prob=rec.current_zone.disruption_probability,
        income_diff=rec.estimated_income_difference,
    )
    return result


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)) -> Response:
    """
    Twilio inbound webhook for WhatsApp bot.
    Expects x-www-form-urlencoded payload with fields like Body, From.
    """
    raw = await request.body()
    form = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
    body = (form.get("Body", [""])[0] or "").strip()
    from_value = (form.get("From", [""])[0] or "").strip()
    cmd = body.lower()
    _prune_expired_whatsapp_sessions()

    if not body:
        return _twiml_message(
            "🔐 Please login before using the bot.\n\n"
            "Type *login* to begin phone verification."
        )

    if cmd in {"logout", "signout"}:
        _whatsapp_auth_sessions.pop(from_value, None)
        _whatsapp_auth_pending.pop(from_value, None)
        return _twiml_message(
            "You have been logged out.\n\n"
            "Type *login* to sign in again."
        )

    if cmd in {"login", "signin"}:
        _whatsapp_auth_pending[from_value] = {"step": "await_phone"}
        _whatsapp_auth_sessions.pop(from_value, None)
        return _twiml_message(
            "📱 Please enter the phone number used in SurakshaShift registration.\n\n"
            "Example: 9884922459"
        )

    session = _whatsapp_auth_sessions.get(from_value)
    pending = _whatsapp_auth_pending.get(from_value)

    if session is None:
        if pending is None:
            return _twiml_message(
                "🔐 Please login before using the bot.\n\n"
                "Type *login* to begin phone verification."
            )

        step = pending.get("step")
        if step == "await_phone":
            worker, user = _find_worker_by_whatsapp_sender(db, body)
            if worker is None or user is None:
                return _twiml_message(
                    "We could not find an account for that phone number.\n\n"
                    "Please try again with the number used during app signup."
                )
            _whatsapp_auth_pending[from_value] = {
                "step": "await_otp",
                "user_id": user.id,
                "worker_id": worker.id,
                "masked_phone": _mask_phone(user.phone),
            }
            return _twiml_message(
                f"✅ Number matched ({_mask_phone(user.phone)}).\n"
                "Enter OTP to continue.\n\n"
                "Demo OTP: *123456*"
            )

        if step == "await_otp":
            if cmd != WHATSAPP_DEMO_OTP:
                return _twiml_message(
                    "❌ Invalid OTP.\n\n"
                    "Please enter the 6-digit OTP again.\n"
                    "Demo OTP: *123456*"
                )

            user_id = pending.get("user_id")
            worker_id = pending.get("worker_id")
            user = db.scalar(select(User).where(User.id == user_id))
            worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == worker_id))
            if user is None or worker is None:
                _whatsapp_auth_pending.pop(from_value, None)
                return _twiml_message(
                    "Your account lookup failed. Please type *login* and try again."
                )

            _whatsapp_auth_sessions[from_value] = {
                "user_id": user.id,
                "worker_id": worker.id,
                "expires_at": datetime.now(timezone.utc)
                + timedelta(minutes=WHATSAPP_SESSION_TTL_MINUTES),
            }
            _whatsapp_auth_pending.pop(from_value, None)

            zone = db.scalar(select(Zone).where(Zone.id == worker.primary_zone_id))
            zone_name = zone.zone_name if zone else "your zone"
            return _twiml_message(
                f"🔓 Logged in as *{user.name}* ({zone_name}).\n\n{_menu_text()}"
            )

        _whatsapp_auth_pending.pop(from_value, None)
        return _twiml_message("Session reset. Type *login* to start again.")

    user = db.scalar(select(User).where(User.id == session.get("user_id")))
    worker = db.scalar(select(WorkerProfile).where(WorkerProfile.id == session.get("worker_id")))
    if worker is None or user is None:
        _whatsapp_auth_sessions.pop(from_value, None)
        return _twiml_message(
            "Your session is invalid now.\n\n"
            "Type *login* to authenticate again."
        )

    zone = db.scalar(select(Zone).where(Zone.id == worker.primary_zone_id))
    zone_name = zone.zone_name if zone else "your zone"
    city = zone.city if zone else user.city

    if cmd in {"menu", "help", "hi", "hello", "start"}:
        return _twiml_message(
            f"{_menu_text()}\n\n"
            f"Logged in as: *{user.name}* ({zone_name})\n"
            f"Session expires in {WHATSAPP_SESSION_TTL_MINUTES} minutes."
        )

    if cmd in {"status", "policy"}:
        policy = db.scalar(
            select(Policy)
            .where(Policy.worker_id == worker.id, Policy.status == "active")
            .order_by(Policy.id.desc())
        )
        if not policy:
            return _twiml_message(
                "You do not have an active weekly policy yet.\n\n"
                "Open the app and activate a plan, then try again."
            )
        return _twiml_message(
            "🛡️ *Your active policy*\n\n"
            f"Plan: *{policy.plan_name}*\n"
            f"Weekly premium: ₹{float(policy.premium_weekly):.0f}\n"
            f"Max weekly payout: ₹{float(policy.max_weekly_payout):.0f}\n"
            f"Zone: {zone_name}\n"
            f"Status: {policy.status.title()}"
        )

    if cmd in {"claims", "claim"}:
        claims = db.scalars(
            select(Claim)
            .where(Claim.worker_id == worker.id)
            .order_by(Claim.id.desc())
            .limit(3)
        ).all()
        if not claims:
            return _twiml_message(
                "No claims yet.\n\n"
                "When a covered disruption happens, claims are created automatically."
            )
        lines = []
        for c in claims:
            lines.append(
                f"#{c.id}: {c.claim_type.replace('_', ' ').title()} | {c.status.replace('_', ' ').title()} | ₹{float(c.approved_payout):.0f}"
            )
        return _twiml_message("📋 *Your recent claims*\n\n" + "\n".join(lines))

    if cmd in {"risk", "live", "weather"}:
        live = await fetch_live_risk_factors(city)
        return _twiml_message(
            f"🌦️ *Live risk in {city}*\n\n"
            f"Rain: {live.rain_risk * 100:.0f}%\n"
            f"Flood: {live.flood_risk * 100:.0f}%\n"
            f"AQI: {live.aqi_risk * 100:.0f}%\n"
            f"Closure: {live.closure_risk * 100:.0f}%\n\n"
            f"Overall risk: *{live.overall_risk.upper()}*"
        )

    if cmd in {"guardian", "shift", "recommend"}:
        rec = await generate_shift_recommendation(
            worker_id=worker.id,
            current_zone=zone_name,
            city=city,
            avg_weekly_income=worker.avg_weekly_income,
            shift_type=worker.shift_type,
        )
        return _twiml_message(
            "🧭 *Shift Guardian*\n\n"
            f"Current zone: {rec.current_zone.zone_name} ({rec.current_zone.disruption_probability:.0f}% disruption)\n"
            f"Recommended zone: {rec.recommended_zone.zone_name} ({rec.recommended_zone.disruption_probability:.0f}% disruption)\n"
            f"Potential extra protected earnings: +₹{rec.estimated_income_difference:.0f}\n\n"
            f"{rec.recommendation_text}"
        )

    return _twiml_message(
        "Sorry, I did not understand that.\n\n"
        "Please type *menu* to see available commands."
    )
