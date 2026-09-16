"""
Division 9A-revised — registration, profile, and transaction history.
The registration flow deliberately creates a genuinely fresh user with zero
session history — this is what makes the cold-start guardrail (Division 5)
demonstrable live by anyone who registers, not just something described.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid
import random
from datetime import datetime

from app.db import get_connection

router = APIRouter(prefix="/bank", tags=["profile"])


class RegisterRequest(BaseModel):
    full_name: str
    phone_number: str
    nin: str
    bvn: str
    avatar_data_url: Optional[str] = None  # base64 image, or None for initials fallback


def _generate_account_number() -> str:
    return str(random.randint(1000000000, 9999999999))


def _mask(value: str, keep_last: int = 4) -> str:
    if not value or len(value) <= keep_last:
        return value
    return "•" * (len(value) - keep_last) + value[-keep_last:]


@router.post("/register")
def register(req: RegisterRequest):
    conn = get_connection()
    cur = conn.cursor()

    account_number = _generate_account_number()
    user_id = str(uuid.uuid4())

    cur.execute(
        """INSERT INTO users
           (id, full_name, msisdn, account_number, nin, bvn, avatar_data_url,
            is_freshly_registered, account_created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s)""",
        (user_id, req.full_name, req.phone_number, account_number,
         req.nin, req.bvn, req.avatar_data_url, datetime.utcnow())
    )

    # A genuinely fresh telco_state row too — first-ever device, no swap history.
    cur.execute(
        """INSERT INTO telco_state (id, user_id, imei, sim_device_paired)
           VALUES (%s, %s, %s, TRUE)""",
        (str(uuid.uuid4()), user_id, f"IMEI-{uuid.uuid4().hex[:14]}")
    )

    conn.commit()
    cur.close()
    conn.close()

    return {
        "user_id": user_id,
        "full_name": req.full_name,
        "account_number": account_number,
        "is_freshly_registered": True,
    }


@router.get("/profile/{user_id}")
def get_profile(user_id: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT full_name, msisdn, account_number, nin, bvn, avatar_data_url,
                  account_created_at
           FROM users WHERE id = %s""",
        (user_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    full_name, msisdn, account_number, nin, bvn, avatar, created_at = row
    initials = "".join([p[0].upper() for p in full_name.split()[:2]]) if full_name else "??"

    return {
        "full_name": full_name,
        "phone_number": msisdn,
        "account_number": account_number,
        "nin_masked": _mask(nin or ""),
        "bvn_masked": _mask(bvn or ""),
        "avatar_data_url": avatar,
        "initials": initials,
        "member_since": created_at.strftime("%B %Y") if created_at else None,
    }


@router.get("/transactions/{user_id}")
def get_transaction_history(user_id: str):
    """
    Returns transactions joined with their decision verdict, so the
    frontend can show the same green/amber/red dot language used on the
    Aegis operator side — one consistent visual system across both apps.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT t.id, t.beneficiary_account, t.amount, t.requested_at,
                  d.verdict, d.explanation_customer
           FROM transactions t
           LEFT JOIN decisions d ON d.session_id = t.session_id
           WHERE t.user_id = %s
           ORDER BY t.requested_at DESC
           LIMIT 100""",
        (user_id,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return {
        "transactions": [
            {
                "id": str(r[0]),
                "beneficiary_account": r[1],
                "amount": float(r[2]),
                "date": r[3].isoformat() if r[3] else None,
                "verdict": r[4] or "ALLOW",
                "message": r[5],
            }
            for r in rows
        ]
    }
