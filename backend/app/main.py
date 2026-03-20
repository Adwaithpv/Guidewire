from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app.models import Base

# Phase 1: Backend shell only. All routers are disabled for the minimal-scope prototype.
# They will be re-enabled in Phase 2 when registration, policies, and claims are implemented.
#
# from app.routers import analytics, auth, claims, events, fraud, guardian, payouts, policies, risk, workers

app = FastAPI(title="SurakshaShift AI API", version="0.1.0-phase1")

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "1", "note": "Backend shell active. Routers disabled for Phase 1 prototype."}


# Phase 2 will re-enable:
# app.include_router(auth.router)
# app.include_router(workers.router)
# app.include_router(risk.router)
# app.include_router(policies.router)
# app.include_router(events.router)
# app.include_router(claims.router)

# Phase 3 will re-enable:
# app.include_router(fraud.router)
# app.include_router(payouts.router)
# app.include_router(guardian.router)
# app.include_router(analytics.router)
