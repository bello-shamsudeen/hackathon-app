"""
Division 2 - the fake bank's core endpoints (WEB channel).
Postgres calls replaced with memory_store. login() now actually verifies
the submitted PIN against the stored hash - previously req.pin was accepted
into the request model but never read or checked anywhere.
"""
from fastapi import APIRouter, HTTPException
import uuid
from datetime import datetime, timedelta

from app.services.memory_store import (
    get_user_by_msisdn, get_user_by_id, create_session, get_session, log_transaction,
    verify_pin, clear_freshly_registered, get_balance, debit_balance,
    is_blocked, set_blocked,
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
    if not verify_pin(user, req.pin):
        raise HTTPException(status_code=401, detail="Incorrect PIN.")

    # Capture the flag BEFORE clearing it, so this first login still reports
    # True (cold-start hint shows once) - every login after this one reports
    # False, since the column is cleared right below.
    was_freshly_registered = user.get("is_freshly_registered", False)
    if was_freshly_registered:
        clear_freshly_registered(str(user["id"]))

    session_id = create_session(str(user["id"]), "WEB", req.device_fingerprint)

    return LoginResponse(
        session_id=session_id, user_id=str(user["id"]), full_name=user["full_name"],
        account_number=user.get("account_number"), avatar_data_url=user.get("avatar_data_url"),
        is_freshly_registered=was_freshly_registered,
    )


@router.get("/dashboard/{session_id}")
def dashboard(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    user = get_user_by_id(session["user_id"]) if session.get("user_id") else None
    balance = get_balance(user["id"]) if user else 0.0
    return {"balance": balance, "currency": "NGN", "recent_transactions": []}


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

    # Division 9 - dynamic block timer: a blocked account is refused BEFORE
    #   velocity, token consumption, and scoring. blocked_until is server-side
    #   state - no endpoint can clear it; it expires on its own clock.
    _blocked, _blocked_until = is_blocked(user_id)
    if _blocked:
        return TransferResponse(
            transaction_id=transaction_id, status="blocked",
            detection={"action": "block", "reason": "ACCOUNT_BLOCKED",
                       "blocked_until": _blocked_until},
        )

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

    # Division 2 - execution: the verdict now settles the transfer against a
    # real balance. allow -> atomic debit (balance guard inside debit_balance)
    #   -> "completed", or "insufficient_funds" if the balance cannot cover it;
    # step_up -> held for OTP verification (Feature 2 hook); block -> the
    # balance is never touched.
    action = (detection or {}).get("action")
    status = "recorded"
    if action == "allow":
        status = "completed" if debit_balance(user_id, req.amount) else "insufficient_funds"
    elif action == "step_up":
        status = "otp_required"
    elif action == "block":
        # Division 9 - severity-scaled block timer: 1h at the low end up to
        #   6h for the highest-confidence blocks; 1h fallback when the scorer
        #   reports no risk_score.
        _sev = float((detection or {}).get("risk_score") or 0)
        _hours = 1 + int(5 * min(1.0, max(0.0, _sev)))
        set_blocked(user_id, (datetime.utcnow() + timedelta(hours=_hours)).isoformat())
        status = "blocked"

    return TransferResponse(transaction_id=transaction_id, status=status, detection=detection)