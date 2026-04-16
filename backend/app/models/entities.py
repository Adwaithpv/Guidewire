from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now_naive)


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city: Mapped[str] = mapped_column(String(100))
    zone_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    geofence_polygon: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_risk_level: Mapped[float] = mapped_column(Float, default=0.3)


class WorkerProfile(Base):
    __tablename__ = "worker_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    persona_type: Mapped[str] = mapped_column(String(50))
    platform_name: Mapped[str] = mapped_column(String(50))
    avg_weekly_income: Mapped[float] = mapped_column(Float)
    primary_zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    shift_type: Mapped[str] = mapped_column(String(50))
    gps_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    payout_upi: Mapped[str] = mapped_column(String(120))
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True, default="prefer_not_to_say")
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)

    user: Mapped[User] = relationship()
    zone: Mapped[Zone] = relationship()


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("worker_profiles.id"), index=True)
    plan_name: Mapped[str] = mapped_column(String(50), default="weekly-basic")
    premium_weekly: Mapped[float] = mapped_column(Numeric(10, 2))
    max_weekly_payout: Mapped[float] = mapped_column(Numeric(10, 2))
    coverage_start: Mapped[datetime] = mapped_column(DateTime)
    coverage_end: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), default="active")
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)


class PolicyTrigger(Base):
    __tablename__ = "policy_triggers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id"), index=True)
    trigger_type: Mapped[str] = mapped_column(String(50))
    threshold_value: Mapped[float] = mapped_column(Float)
    payout_formula_type: Mapped[str] = mapped_column(String(50), default="hour_based")


class RiskProfile(Base):
    __tablename__ = "risk_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("worker_profiles.id"), index=True)
    rain_risk: Mapped[float] = mapped_column(Float)
    flood_risk: Mapped[float] = mapped_column(Float)
    aqi_risk: Mapped[float] = mapped_column(Float)
    closure_risk: Mapped[float] = mapped_column(Float)
    shift_exposure: Mapped[float] = mapped_column(Float)
    final_risk_score: Mapped[float] = mapped_column(Float)
    quoted_premium: Mapped[float] = mapped_column(Numeric(10, 2))
    model_version: Mapped[str] = mapped_column(String(40), default="weighted-v1")


class DisruptionEvent(Base):
    __tablename__ = "disruption_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime] = mapped_column(DateTime)
    severity: Mapped[str] = mapped_column(String(20), default="moderate")
    source_name: Mapped[str] = mapped_column(String(50))
    source_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True)


class TriggerMatch(Base):
    __tablename__ = "trigger_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("disruption_events.id"), index=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("worker_profiles.id"), index=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id"), index=True)
    matched_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now_naive)
    expected_payout: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="matched")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("worker_profiles.id"), index=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("disruption_events.id"), index=True)
    claim_type: Mapped[str] = mapped_column(String(50), default="parametric_income_loss")
    status: Mapped[str] = mapped_column(String(30), default="validation_pending")
    estimated_loss: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    approved_payout: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now_naive)
    auto_created: Mapped[bool] = mapped_column(Boolean, default=True)


class FraudCheck(Base):
    __tablename__ = "fraud_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    gps_score: Mapped[float] = mapped_column(Float, default=0)
    activity_score: Mapped[float] = mapped_column(Float, default=0)
    duplicate_score: Mapped[float] = mapped_column(Float, default=0)
    anomaly_score: Mapped[float] = mapped_column(Float, default=0)
    source_score: Mapped[float] = mapped_column(Float, default=0)
    final_fraud_score: Mapped[float] = mapped_column(Float, default=0)
    review_status: Mapped[str] = mapped_column(String(30), default="auto_approve")


class Payout(Base):
    __tablename__ = "payouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("worker_profiles.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    method: Mapped[str] = mapped_column(String(20), default="upi")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    gateway_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    initiated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now_naive)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ShiftGuardianAlert(Base):
    __tablename__ = "shift_guardian_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("worker_profiles.id"), index=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    alert_type: Mapped[str] = mapped_column(String(40))
    forecast_window: Mapped[str] = mapped_column(String(120))
    risk_level: Mapped[str] = mapped_column(String(20))
    recommendation_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now_naive)


class DataConsent(Base):
    __tablename__ = "data_consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("worker_profiles.id"), unique=True, index=True)
    gps_consent: Mapped[bool] = mapped_column(Boolean, default=True)
    upi_consent: Mapped[bool] = mapped_column(Boolean, default=True)
    platform_data_consent: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_version: Mapped[str] = mapped_column(String(20), default="v1")
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now_naive)

