"""
Division 2 - the fake bank's core endpoints (WEB channel).
Restored to the full Division 2/4/5/8 version (velocity, hard controls,
honeytoken, token consumption, inline detection) after an earlier accidental
overwrite with a simplified draft. Postgres calls replaced with memory_store.
"""
from fastapi import APIRouter, HTTPException
import uuid
from datetime import datetime

from app.services.memory_store import (
    get_user_by_msisdn, create_session, get_session, log_transaction,
)
from app.models.schemas import (
    LoginRequest, LoginResponse, TransferRequest, TransferResponse,
)
from app.services import velocity
from app.services.token_integrity import consume_token
from app.services.honeytokens import check_honeytoken
from app.routers.score import score_session

router = APIRouter(prefix="/bank", tags=["bank"])


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    user = get_user_by_msisdn(req.msisdn)
    if not user:
        raise HTTPException(status_code=401, detail="Unknown user (no synthetic data loaded yet?)")

    session_id = create_session(user["id"], "WEB", req.device_fingerprint)

    return LoginResponse(
        session_id=session_id, user_id=str(user["id"]), full_name=user["full_name"],
        account_number=user.get("account_number"), avatar_data_url=user.get("avatar_data_url"),
        is_freshly_registered=user.get("is_freshly_registered", False),
    )


@router.get("/dashboard/{session_id}")
def dashboard(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"balance": 458200.00, "currency": "NGN", "recent_transactions": []}


@router.post("/transfer", response_model=TransferResponse)
def transfer(req: TransferRequest):
    """
    Records the transfer attempt, then runs the full detection loop
    (hard controls + scoring + decision) inline so a verdict lands with
    every transfer, without a second call.
    """
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    user_id = session["user_id"]

    transaction_id = log_transaction(req.session_id, user_id, req.beneficiary_account, req.amount)

    # Division 4B - count this transfer in the rolling velocity window before scoring.
    velocity.record_transfer(user_id)

    # Division 5 - consume the one-time confirmation token, if supplied.
    token_status = None
    if req.token:
        res = consume_token(req.token)
        token_status = "OK" if res["valid"] else res["reason"]

    # Division 8B - honeytoken: only a bot that auto-fills every field populates this.
    honeytoken = check_honeytoken({"confirm_email_address": req.confirm_email_address})

    # Division 4/5/8 - run the detection loop now, on this same request.
    detection = None
    try:
        detection = score_session(
            req.session_id,
            current_imei=req.current_imei,
            otp_being_entered=req.otp_being_entered,
            call_active_hint=req.call_active,
            token_status=token_status,
            honeytoken_tripped=honeytoken["triggered"],
        )
    except Exception as exc:  # noqa: BLE001 - detection is best-effort here
        detection = {"error": str(exc)}

    return TransferResponse(transaction_id=transaction_id, status="recorded", detection=detection)