import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app.models import Base

from app.routers import analytics, auth, claims, events, fraud, guardian, payouts, policies, risk, shift_guardian, workers

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="SurakshaShift AI API", version="0.2.0-phase2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    # Pre-train ML model on startup
    from app.ml.premium_model import model
    model.train()
    log.info("SurakshaShift Phase 2 API ready. ML model trained.")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "2", "note": "Phase 2 API active. ML-powered risk engine & live API triggers enabled."}


# Phase 2 enabled:
app.include_router(auth.router)
app.include_router(workers.router)
app.include_router(risk.router)
app.include_router(policies.router)
app.include_router(events.router)
app.include_router(claims.router)
app.include_router(shift_guardian.router)

# Phase 3 will re-enable:
# app.include_router(fraud.router)
# app.include_router(payouts.router)
# app.include_router(guardian.router)
# app.include_router(analytics.router)
