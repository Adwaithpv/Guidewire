"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False, unique=True),
        sa.Column("email", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "zones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("zone_name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("geofence_polygon", sa.Text(), nullable=True),
        sa.Column("default_risk_level", sa.Float(), nullable=False, server_default="0.3"),
    )
    op.create_table(
        "worker_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("persona_type", sa.String(length=50), nullable=False),
        sa.Column("platform_name", sa.String(length=50), nullable=False),
        sa.Column("avg_weekly_income", sa.Float(), nullable=False),
        sa.Column("primary_zone_id", sa.Integer(), sa.ForeignKey("zones.id"), nullable=False),
        sa.Column("shift_type", sa.String(length=50), nullable=False),
        sa.Column("gps_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("payout_upi", sa.String(length=120), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_table(
        "policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("worker_id", sa.Integer(), sa.ForeignKey("worker_profiles.id"), nullable=False),
        sa.Column("plan_name", sa.String(length=50), nullable=False),
        sa.Column("premium_weekly", sa.Numeric(10, 2), nullable=False),
        sa.Column("max_weekly_payout", sa.Numeric(10, 2), nullable=False),
        sa.Column("coverage_start", sa.DateTime(), nullable=False),
        sa.Column("coverage_end", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "policy_triggers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("policies.id"), nullable=False),
        sa.Column("trigger_type", sa.String(length=50), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.Column("payout_formula_type", sa.String(length=50), nullable=False),
    )
    op.create_table(
        "risk_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("worker_id", sa.Integer(), sa.ForeignKey("worker_profiles.id"), nullable=False),
        sa.Column("rain_risk", sa.Float(), nullable=False),
        sa.Column("flood_risk", sa.Float(), nullable=False),
        sa.Column("aqi_risk", sa.Float(), nullable=False),
        sa.Column("closure_risk", sa.Float(), nullable=False),
        sa.Column("shift_exposure", sa.Float(), nullable=False),
        sa.Column("final_risk_score", sa.Float(), nullable=False),
        sa.Column("quoted_premium", sa.Numeric(10, 2), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=False),
    )
    op.create_table(
        "disruption_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("zone_id", sa.Integer(), sa.ForeignKey("zones.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("source_name", sa.String(length=50), nullable=False),
        sa.Column("source_payload", sa.Text(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("worker_id", sa.Integer(), sa.ForeignKey("worker_profiles.id"), nullable=False),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("policies.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("disruption_events.id"), nullable=False),
        sa.Column("claim_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("estimated_loss", sa.Numeric(10, 2), nullable=False),
        sa.Column("approved_payout", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("auto_created", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "payouts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("worker_id", sa.Integer(), sa.ForeignKey("worker_profiles.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("gateway_ref", sa.String(length=80), nullable=True),
        sa.Column("initiated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    for table_name in [
        "payouts",
        "claims",
        "disruption_events",
        "risk_profiles",
        "policy_triggers",
        "policies",
        "worker_profiles",
        "zones",
        "users",
    ]:
        op.drop_table(table_name)
