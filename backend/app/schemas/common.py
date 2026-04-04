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
    city: str = "Bengaluru"
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
    feature_importances: dict[str, float] = {}
    model_version: str = "actuarial-gbm-blend-v1"


class PolicyQuoteRequest(BaseModel):
    worker_id: int


class PolicyQuoteResponse(BaseModel):
    premium_weekly: float
    max_weekly_payout: float
    covered_events: list[str]
    exclusions: list[str]


class PolicyCreateRequest(BaseModel):
    worker_id: int
    plan_id: str = "standard"
    premium_weekly: float
    max_weekly_payout: float
    covered_events: list[str]
    auto_renew: bool = False


class PlanQuote(BaseModel):
    plan_id: str
    label: str
    description: str
    premium_weekly: float
    max_weekly_payout: float
    coverage_pct: float
    risk_rate_pct: float
    at_floor: bool
    at_ceiling: bool


class AllPlansQuoteResponse(BaseModel):
    worker_id: int
    city: str
    composite_risk: float
    risk_level: str
    plans: list[PlanQuote]
    covered_events: list[str]
    exclusions: list[str]
    live_factors: "LiveRiskFactors"
    fetched_at: str


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


class LiveRiskFactors(BaseModel):
    city: str
    weather: dict = {}
    aqi: dict = {}
    rain_risk: float = 0.0
    flood_risk: float = 0.0
    aqi_risk: float = 0.0
    closure_risk: float = 0.0
    """From NewsData.io or GNews (bandh/curfew/hartal/etc.) when configured; else mock."""
    closure_source: str = "mock"
    closure_headlines: list[dict[str, Any]] = Field(default_factory=list)
    overall_risk: str = "low"
    is_disruptive: bool = False
    fetched_at: str = ""


class RiskQuoteLiveRequest(BaseModel):
    worker_id: int


class QuoteExposureInputs(BaseModel):
    """Normalized 0–1 factors actually passed into actuarial + GBM for this quote."""

    rain_risk: float
    flood_risk: float
    aqi_risk: float
    closure_risk: float
    shift_exposure: float
    city: str


class RiskQuoteLiveResponse(RiskQuoteResponse):
    live_factors: LiveRiskFactors
    quote_exposure_inputs: QuoteExposureInputs


class ClaimsSummary(BaseModel):
    worker_id: int
    total_claims: int = 0
    approved_claims: int = 0
    total_payout: float = 0.0
    pending_claims: int = 0
