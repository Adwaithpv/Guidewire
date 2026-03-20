from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import DisruptionEvent, Zone
from app.schemas.common import EventIngestRequest
from app.services.trigger_engine import create_claim_candidates

router = APIRouter(prefix="/events", tags=["events"])


def _ingest(payload: EventIngestRequest, db: Session) -> dict:
    zone = db.scalar(select(Zone).where(Zone.zone_name == payload.zone_name))
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")
    event = DisruptionEvent(
        event_type=payload.event_type,
        zone_id=zone.id,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        severity=payload.severity,
        source_name=payload.source_name,
        source_payload=str(payload.source_payload) if payload.source_payload else None,
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
        }
        for e in rows
    ]
