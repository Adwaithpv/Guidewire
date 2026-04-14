from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import User, WorkerProfile
from app.schemas.common import OtpRequest, OtpVerifyRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-otp")
def send_otp(payload: OtpRequest) -> dict[str, str]:
    return {"message": f"OTP sent to {payload.phone}", "mock_otp": "123456"}


@router.post("/verify-otp")
def verify_otp(payload: OtpVerifyRequest, db: Session = Depends(get_db)) -> dict:
    if payload.otp != "123456":
        return {"status": "failed"}
    user = db.scalar(select(User).where(User.phone == payload.phone))
    if user is None:
        return {
            "status": "verified",
            "existing_user": False,
        }

    worker = db.scalar(
        select(WorkerProfile)
        .where(WorkerProfile.user_id == user.id)
        .order_by(WorkerProfile.id.desc())
    )
    return {
        "status": "verified",
        "existing_user": worker is not None,
        "worker_id": worker.id if worker is not None else None,
        "user_id": user.id,
    }
