"""
Division 9A — registration, profile, and transaction history.

The registration flow deliberately creates a genuinely fresh user with zero
prior session history, then opens ONE web session for them — this is what
makes the cold-start guardrail (Division 5, Guardrail 2) demonstrable live by
anyone who registers, not just something described. A first-ever large
transfer from this account is scored against <5 sessions of history, so the
guardrail caps it away from an outright BLOCK to a step-up.

Backed by the in-memory store (memory_store.py) rather than Postgres.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid

from app.services import memory_store
from app.services.memory_store import (
    create_user,
    get_user_by_id,
    create_session,
    get_transactions_for_user,
    TELCO_STATE,
    DECISIONS,
)

router = APIRouter(prefix="/bank", tags=["profile"])


class RegisterRequest(BaseModel):
    full_name: str
    phone_number: str
    nin: str
    bvn: str
    avatar_data_url: Optional[str] = None  # base64 image, or None for initials fallback


def _mask(value: str, keep_last: int = 4) -> str:
    if not value or len(value) <= keep_last:
        return value
    return "•" * (len(value) - keep_last) + value[-keep_last:]


@router.post("/register")
def register(req: RegisterRequest):
    account_number = str(uuid.uuid4().int)[:10]
    user = create_user(
        req.full_name, req.phone_number, account_number,
        req.nin, req.bvn, req.avatar_data_url,
    )
    user_id = str(user["id"])

    # A genuinely fresh telco_state row too — first-ever device, no swap history.
    TELCO_STATE[user_id] = {
        "imei": f"IMEI-{uuid.uuid4().hex[:14]}",
        "sim_device_paired": True,
        "last_sim_swap_at": None,
    }

    # Open ONE web session for the new user so the consumer app has a session
    # to score against immediately after registration. This is the entire
    # session history for this account — exactly the cold-start condition.
    session_id = create_session(user_id, "WEB", f"reg-{user_id}")

    return {
        "user_id": user_id,
        "session_id": session_id,
        "full_name": req.full_name,
        "account_number": account_number,
        "avatar_data_url": req.avatar_data_url,
        "is_freshly_registered": True,
    }


@router.get("/profile/{user_id}")
def get_profile(user_id: str):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    full_name = user.get("full_name")
    initials = "".join([p[0].upper() for p in full_name.split()[:2]]) if full_name else "??"
    created_at = user.get("account_created_at")

    return {
        "full_name": full_name,
        "phone_number": user.get("msisdn"),
        "account_number": user.get("account_number"),
        "nin_masked": _mask(user.get("nin") or ""),
        "bvn_masked": _mask(user.get("bvn") or ""),
        "avatar_data_url": user.get("avatar_data_url"),
        "initials": initials,
        "member_since": created_at.strftime("%B %Y") if created_at else None,
    }


@router.get("/transactions/{user_id}")
def get_transaction_history(user_id: str):
    """
    Returns transactions joined with their decision verdict, so the frontend
    can show the same green/amber/red dot language used on the Aegis operator
    side — one consistent visual system across both apps. For each
    transaction, the latest DECISIONS entry sharing its session_id (by
    decided_at) supplies the verdict/message, mirroring the original
    LEFT JOIN ... ORDER BY decided_at DESC behavior.
    """
    transactions = get_transactions_for_user(user_id)

    txns = []
    for t in transactions:
        matching_decisions = [d for d in DECISIONS if d["transaction_id"] == t["id"]]
        latest_decision = max(matching_decisions, key=lambda d: d["decided_at"]) if matching_decisions else None

        txns.append({
            "id": str(t["id"]),
            "beneficiary_account": t["beneficiary_account"],
            "amount": float(t["amount"]),
            "date": t["requested_at"].isoformat() if t.get("requested_at") else None,
            "verdict": latest_decision["verdict"] if latest_decision else "ALLOW",
            "message": latest_decision["explanation_customer"] if latest_decision else None,
        })

    txns.sort(key=lambda x: x["date"] or "", reverse=True)
    return {"transactions": txns}