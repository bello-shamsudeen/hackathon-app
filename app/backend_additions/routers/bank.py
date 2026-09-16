"""Division 2 — fake bank endpoints (WEB). Uses memory_store."""
from fastapi import APIRouter, HTTPException

from app.backend_additions.services.memory_store import (
    get_user_by_msisdn, create_session, get_session, log_transaction,
)
from app.models.schemas import (
    LoginRequest, LoginResponse, TransferRequest, TransferResponse,
)

router = APIRouter(prefix="/bank", tags=["bank"])


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    """Fake auth: any msisdn+pin matching a seeded user succeeds."""
    user = get_user_by_msisdn(req.msisdn)
    if not user:
        raise HTTPException(status_code=401, detail="Unknown user (no synthetic data loaded yet?)")
    user_id = str(user["id"])
    session_id = create_session(user_id, "WEB", req.device_fingerprint)
    return LoginResponse(session_id=session_id, user_id=user_id, full_name=user["full_name"])


@router.get("/dashboard/{session_id}")
def dashboard(session_id: str):
    """Fake balance + recent activity."""
    sess = get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"balance": 458200.00, "currency": "NGN", "recent_transactions": []}


@router.post("/transfer", response_model=TransferResponse)
def transfer(req: TransferRequest):
    """Record the transfer attempt."""
    sess = get_session(req.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    user_id = sess["user_id"]
    txn_id = log_transaction(req.session_id, user_id, req.beneficiary_account, req.amount)
    return TransferResponse(transaction_id=txn_id, status="recorded")
