from fastapi import APIRouter

from app.schemas.common import OtpRequest, OtpVerifyRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-otp")
def send_otp(payload: OtpRequest) -> dict[str, str]:
    return {"message": f"OTP sent to {payload.phone}", "mock_otp": "123456"}


@router.post("/verify-otp")
def verify_otp(payload: OtpVerifyRequest) -> dict[str, str]:
    if payload.otp != "123456":
        return {"status": "failed"}
    return {"status": "verified"}
