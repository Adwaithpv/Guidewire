import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import engine
from app.models import Base

from app.routers import analytics, auth, claims, events, fraud, guardian, notifications, payouts, policies, risk, shift_guardian, workers

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="SurakshaShift AI API", version="0.3.0-phase3")

cors_env = os.getenv("CORS_ORIGINS", "*").strip()
allow_origin_regex = (os.getenv("CORS_ORIGIN_REGEX", "") or "").strip() or None
allow_credentials_env = (os.getenv("CORS_ALLOW_CREDENTIALS", "false") or "").strip().lower()
allow_credentials = allow_credentials_env in {"1", "true", "yes", "on"}

allow_origins = (
    ["*"]
    if cors_env == "*"
    else [origin.strip() for origin in cors_env.split(",") if origin.strip()]
)

# Browsers reject wildcard CORS when credentials are allowed.
# If "*" is used, force credentials off unless explicit origins are configured.
if allow_origins == ["*"] and allow_credentials:
    allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_sqlite_columns() -> None:
    """
    Render/free-tier deployments often keep an existing SQLite file.
    SQLAlchemy's create_all() won't add new columns, so we do a tiny, safe
    one-way migration for additive columns needed by newer versions.
    """
    try:
        if not str(engine.url).startswith("sqlite"):
            return
        with engine.begin() as conn:
            cols = conn.exec_driver_sql("PRAGMA table_info(worker_profiles)").fetchall()
            col_names = {str(r[1]) for r in cols}  # row[1] = name
            if "gender" not in col_names:
                conn.execute(
                    text(
                        "ALTER TABLE worker_profiles ADD COLUMN gender VARCHAR(20) DEFAULT 'prefer_not_to_say'"
                    )
                )
            if "preferred_next_plan" not in col_names:
                conn.execute(
                    text(
                        "ALTER TABLE worker_profiles ADD COLUMN preferred_next_plan VARCHAR(50) DEFAULT NULL"
                    )
                )
    except Exception:
        # Never fail startup for best-effort migrations in demo mode.
        return


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()
    from app.ml.premium_model import model
    model.train()
    log.info("SurakshaShift Phase 3 API ready. ML model trained.")


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "phase": "3",
        "note": "Phase 3: Advanced fraud detection, instant payouts, intelligent dashboards.",
    }


# Phase 2 (carried forward)
app.include_router(auth.router)
app.include_router(workers.router)
app.include_router(risk.router)
app.include_router(policies.router)
app.include_router(events.router)
app.include_router(claims.router)
app.include_router(shift_guardian.router)

# Phase 3 — now enabled
app.include_router(fraud.router)
app.include_router(payouts.router)
app.include_router(guardian.router)
app.include_router(analytics.router)
app.include_router(notifications.router)
