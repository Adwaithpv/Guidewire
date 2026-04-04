import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import DisruptionEvent, Zone
from app.schemas.common import EventIngestRequest
from app.services.parametric_rules import recent_duplicate_event
from app.services.trigger_engine import create_claim_candidates

router = APIRouter(prefix="/events", tags=["events"])


def _ingest(payload: EventIngestRequest, db: Session) -> dict:
    zone = db.scalar(select(Zone).where(Zone.zone_name == payload.zone_name))
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")

    dup = recent_duplicate_event(db, zone.id, payload.event_type)
    if dup is not None:
        return {
            "event_id": dup.id,
            "claim_candidates": 0,
            "deduplicated": True,
            "reason": "Same zone and event type within cooldown window",
        }

    payload_json = (
        json.dumps(payload.source_payload, default=str)
        if payload.source_payload is not None
        else None
    )
    event = DisruptionEvent(
        event_type=payload.event_type,
        zone_id=zone.id,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        severity=payload.severity,
        source_name=payload.source_name,
        source_payload=payload_json,
        is_verified=True,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    created_claims = create_claim_candidates(db, event)
    return {"event_id": event.id, "claim_candidates": len(created_claims)}


@router.post("/ingest/weather")
def ingest_weather(payload: EventIngestRequest, db: Session = Depends(get_db)) -> dict:
    return _ingest(payload, db)


@router.post("/ingest/aqi")
def ingest_aqi(payload: EventIngestRequest, db: Session = Depends(get_db)) -> dict:
    return _ingest(payload, db)


@router.post("/ingest/closure")
def ingest_closure(payload: EventIngestRequest, db: Session = Depends(get_db)) -> dict:
    return _ingest(payload, db)


@router.post("/ingest/platform-outage")
def ingest_platform_outage(payload: EventIngestRequest, db: Session = Depends(get_db)) -> dict:
    return _ingest(payload, db)


@router.post("/ingest/flood")
def ingest_flood(payload: EventIngestRequest, db: Session = Depends(get_db)) -> dict:
    return _ingest(payload, db)


@router.get("/live")
def live_events(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(DisruptionEvent).order_by(DisruptionEvent.id.desc()).limit(50)).all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "zone_id": e.zone_id,
            "started_at": e.started_at,
            "ended_at": e.ended_at,
            "severity": e.severity,
            "source_name": e.source_name,
        }
        for e in rows
    ]


@router.get("/check-live/{city}")
async def check_live_events(city: str, db: Session = Depends(get_db)) -> dict:
    """Check real weather+AQI for a city and auto-ingest events if thresholds exceeded."""
    from app.services.weather_service import get_current_weather, weather_to_risk_factors
    from app.services.aqi_service import get_current_aqi, aqi_to_risk_factor

    weather = await get_current_weather(city)
    weather_risks = weather_to_risk_factors(weather)
    aqi_data = await get_current_aqi(city)
    aqi_risks = aqi_to_risk_factor(aqi_data)

    events_created = 0
    now = datetime.utcnow()

    # Find zones in this city
    zones = db.scalars(select(Zone).where(Zone.city == city)).all()

    for zone in zones:
        rain_mm = float(weather.get("rain_mm_1h") or 0)
        # Align with policy trigger (e.g. 50 mm/h): only ingest when the index is verifiable in payload
        if rain_mm >= 50.0:
            payload = EventIngestRequest(
                event_type="heavy_rain",
                zone_name=zone.zone_name,
                started_at=now,
                ended_at=now,
                severity="severe" if rain_mm >= 70 else "high",
                source_name=f"live_{weather['source']}",
                source_payload={**weather, "rainfall_mm": rain_mm},
            )
            _ingest(payload, db)
            events_created += 1

        if aqi_risks["is_disruptive"]:
            payload = EventIngestRequest(
                event_type="aqi_severe",
                zone_name=zone.zone_name,
                started_at=now,
                ended_at=now,
                severity="severe",
                source_name=f"live_{aqi_data['source']}",
                source_payload=aqi_data,
            )
            _ingest(payload, db)
            events_created += 1

    return {
        "city": city,
        "weather": weather,
        "aqi": aqi_data,
        "weather_disruptive": weather_risks["is_disruptive"],
        "aqi_disruptive": aqi_risks["is_disruptive"],
        "events_auto_created": events_created,
    }
