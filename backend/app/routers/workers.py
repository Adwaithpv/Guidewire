from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from datetime import datetime, timezone

from app.models.entities import DataConsent, User, WorkerProfile, Zone
from app.schemas.common import WorkerProfileCreate, WorkerProfileResponse
import logging

from app.services.whatsapp_service import notify_registration_welcome

log = logging.getLogger(__name__)

router = APIRouter(prefix="/workers", tags=["workers"])


def _normalize_platforms(platform_name: str, platform_names: list[str] | None) -> list[str]:
    raw = list(platform_names or [])
    if platform_name:
        raw.insert(0, platform_name)
    out: list[str] = []
    seen: set[str] = set()
    for p in raw:
        label = (p or "").strip()
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(label)
    return out or ["Unknown"]


def _parse_platforms_from_storage(platform_name: str | None) -> list[str]:
    if not platform_name:
        return ["Unknown"]
    parts = [part.strip() for part in platform_name.replace("|", ",").split(",")]
    clean = [p for p in parts if p]
    if not clean:
        return ["Unknown"]
    deduped: list[str] = []
    seen: set[str] = set()
    for p in clean:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    return deduped or ["Unknown"]


@router.post("/profile", response_model=WorkerProfileResponse)
def create_worker_profile(payload: WorkerProfileCreate, db: Session = Depends(get_db)) -> WorkerProfileResponse:
    normalized_platforms = _normalize_platforms(payload.platform_name, payload.platform_names)
    platform_storage = ", ".join(normalized_platforms)

    zone = db.scalar(select(Zone).where(Zone.zone_name == payload.primary_zone))
    if zone is None:
        zone = Zone(city=payload.city, zone_name=payload.primary_zone, default_risk_level=0.35)
        db.add(zone)
        db.flush()

    user = db.scalar(select(User).where(User.phone == payload.phone))
    if user is None:
        user = User(name=payload.name, phone=payload.phone, email=payload.email, city=payload.city)
        db.add(user)
        db.flush()
    else:
        # Same phone as a prior registration / demo — keep display name in sync with the form.
        user.name = payload.name
        user.email = payload.email
        user.city = payload.city

    profile = db.scalar(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    if profile is None:
        profile = WorkerProfile(
            user_id=user.id,
            persona_type=payload.persona_type,
            platform_name=platform_storage,
            avg_weekly_income=payload.avg_weekly_income,
            primary_zone_id=zone.id,
            shift_type=payload.shift_type,
            gps_enabled=payload.gps_enabled,
            payout_upi=payload.payout_upi,
            gender=payload.gender,
            risk_score=zone.default_risk_level,
        )
        db.add(profile)
    else:
        profile.persona_type = payload.persona_type
        profile.platform_name = platform_storage
        profile.avg_weekly_income = payload.avg_weekly_income
        profile.primary_zone_id = zone.id
        profile.shift_type = payload.shift_type
        profile.gps_enabled = payload.gps_enabled
        profile.payout_upi = payload.payout_upi
        profile.gender = payload.gender

    db.flush()
    consent = db.scalar(select(DataConsent).where(DataConsent.worker_id == profile.id))
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    if consent is None:
        consent = DataConsent(
            worker_id=profile.id,
            gps_consent=payload.gps_consent,
            upi_consent=payload.upi_consent,
            platform_data_consent=payload.platform_data_consent,
            consent_version="v1",
            captured_at=now_naive,
            updated_at=now_naive,
        )
        db.add(consent)
    else:
        consent.gps_consent = payload.gps_consent
        consent.upi_consent = payload.upi_consent
        consent.platform_data_consent = payload.platform_data_consent
        consent.updated_at = now_naive

    db.commit()
    db.refresh(profile)

    # Demo mode behavior: send WhatsApp on every successful registration/profile save.
    # If override-to is active, all messages still route to that joined sandbox number.
    wa_result: dict | None = None
    try:
        wa_result = notify_registration_welcome(
            to_phone=payload.phone,
            worker_name=payload.name,
            city=payload.city,
            zone_name=payload.primary_zone,
        )
        if not wa_result.get("sent"):
            log.warning("Registration WhatsApp not sent: %s", wa_result)
    except Exception as exc:
        log.exception("Registration WhatsApp failed: %s", exc)

    return WorkerProfileResponse(
        worker_id=profile.id,
        user_id=user.id,
        risk_score=profile.risk_score,
        whatsapp_notification=wa_result,
    )


@router.get("/profile/{worker_id}")
def get_worker_profile(worker_id: int, db: Session = Depends(get_db)) -> dict:
    profile = db.scalar(select(WorkerProfile).where(WorkerProfile.id == worker_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Worker not found")
    zone = db.scalar(select(Zone).where(Zone.id == profile.primary_zone_id))
    user = db.scalar(select(User).where(User.id == profile.user_id))
    consent = db.scalar(select(DataConsent).where(DataConsent.worker_id == profile.id))
    platform_names = _parse_platforms_from_storage(profile.platform_name)
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "name": user.name if user else "Worker",
        "phone": user.phone if user else "",
        "persona_type": profile.persona_type,
        "platform_name": platform_names[0],
        "platform_names": platform_names,
        "gender": profile.gender or "prefer_not_to_say",
        "avg_weekly_income": profile.avg_weekly_income,
        "city": zone.city if zone else "",
        "zone_name": zone.zone_name if zone else None,
        "shift_type": profile.shift_type,
        "gps_enabled": profile.gps_enabled,
        "payout_upi": profile.payout_upi,
        "risk_score": profile.risk_score,
        "consent": {
            "gps_consent": bool(consent.gps_consent) if consent else bool(profile.gps_enabled),
            "upi_consent": bool(consent.upi_consent) if consent else bool(profile.payout_upi),
            "platform_data_consent": bool(consent.platform_data_consent) if consent else True,
            "consent_version": consent.consent_version if consent else "v1",
            "captured_at": consent.captured_at.isoformat() if consent and consent.captured_at else None,
            "updated_at": consent.updated_at.isoformat() if consent and consent.updated_at else None,
        },
    }


@router.get("/all")
def list_workers(db: Session = Depends(get_db)) -> list[dict]:
    profiles = db.scalars(select(WorkerProfile).order_by(WorkerProfile.id.desc())).all()
    results = []
    for p in profiles:
        user = db.scalar(select(User).where(User.id == p.user_id))
        zone = db.scalar(select(Zone).where(Zone.id == p.primary_zone_id))
        platform_names = _parse_platforms_from_storage(p.platform_name)
        results.append({
            "id": p.id,
            "name": user.name if user else "Worker",
            "platform_name": platform_names[0],
            "platform_names": platform_names,
            "gender": p.gender or "prefer_not_to_say",
            "city": zone.city if zone else "",
            "risk_score": p.risk_score,
        })
    return results


@router.post("/profile/{worker_id}/location")
def update_worker_location(worker_id: int, payload: dict, db: Session = Depends(get_db)) -> dict:
    profile = db.scalar(select(WorkerProfile).where(WorkerProfile.id == worker_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Worker not found")

    city = str(payload.get("city") or "").strip()
    zone_name = str(payload.get("zone_name") or "").strip()
    if not city or not zone_name:
        raise HTTPException(status_code=400, detail="city and zone_name are required")

    zone = db.scalar(select(Zone).where(Zone.zone_name == zone_name))
    if zone is None:
        zone = Zone(
            city=city,
            zone_name=zone_name,
            default_risk_level=profile.risk_score if profile.risk_score > 0 else 0.35,
        )
        db.add(zone)
        db.flush()
    elif zone.city != city:
        zone.city = city

    profile.primary_zone_id = zone.id
    user = db.scalar(select(User).where(User.id == profile.user_id))
    if user is not None:
        user.city = city

    db.commit()
    return {
        "worker_id": profile.id,
        "city": city,
        "zone_name": zone.zone_name,
    }
