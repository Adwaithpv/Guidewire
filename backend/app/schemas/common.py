from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OtpRequest(BaseModel):
    phone: str


class OtpVerifyRequest(BaseModel):
    phone: str
    otp: str


class WorkerProfileCreate(BaseModel):
    name: str
    phone: str
    email: str | None = None
    city: str
    persona_type: str = "grocery"
    platform_name: str
    avg_weekly_income: float = Field(gt=0)
    primary_zone: str
    shift_type: str
    gps_enabled: bool = False
    payout_upi: str


class WorkerProfileResponse(BaseModel):
    worker_id: int
    user_id: int
    risk_score: float


class RiskQuoteRequest(BaseModel):
    worker_id: int
    rain_risk: float = 0.3
    flood_risk: float = 0.2
    aqi_risk: float = 0.2
    closure_risk: float = 0.1
    shift_exposure: float = 0.2


class RiskQuoteResponse(BaseModel):
    risk_score: float
    premium_weekly: float
    max_weekly_payout: float
    confidence_level: float
    explanation: str


class PolicyQuoteRequest(BaseModel):
    worker_id: int
    risk_score: float


class PolicyQuoteResponse(BaseModel):
    premium_weekly: float
    max_weekly_payout: float
    covered_events: list[str]
    exclusions: list[str]


class PolicyCreateRequest(BaseModel):
    worker_id: int
    premium_weekly: float
    max_weekly_payout: float
    covered_events: list[str]
    auto_renew: bool = False


class EventIngestRequest(BaseModel):
    event_type: str
    zone_name: str
    started_at: datetime
    ended_at: datetime
    severity: str = "moderate"
    source_name: str = "mock"
    source_payload: dict[str, Any] | None = None


class ProcessClaimResponse(BaseModel):
    claim_id: int
    status: str
    approved_payout: float

