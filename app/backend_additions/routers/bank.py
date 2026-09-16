"""
Division 2 — the fake bank's core endpoints (WEB channel).
Deliberately plain/functional — visual polish is Division 9, not here.
Every action creates or updates rows in the Division 1 schema so the
behavioral/ML pipeline (Divisions 3-6) has real data to work against.
"""
from fastapi import APIRouter, HTTPException
import uuid
from datetime import datetime

# NOTE for integration: adapt these imports/connection calls to whatever
# DB access pattern already exists in the repo (SQLAlchemy session from
# Alembic setup, or the psycopg2 pattern from main.py) — don't introduce
# a second, inconsistent way of talking to Postgres.
from app.db import get_connection  # <-- create this helper if it doesn't exist yet

from app.models.schemas import (
    LoginRequest, LoginResponse, TransferRequest, TransferResponse
)

router = APIRouter(prefix="/bank", tags=["bank"])


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    """
    Fake auth: for the hackathon, any msisdn+pin combination that matches an
    existing synthetic user (Division 3 will populate these) succeeds.
    A session row is created regardless — the whole point is to start
    capturing behavioral telemetry from the moment login begins, not just
    after it succeeds, since typing behaviour DURING login is itself a signal.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, full_name FROM users WHERE msisdn = %s", (req.msisdn,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Unknown user (no synthetic data loaded yet?)")
    user_id, full_name = row

    session_id = str(uuid.uuid4())
    cur.execute(
        """INSERT INTO sessions (id, user_id, channel, device_fingerprint, started_at)
           VALUES (%s, %s, 'WEB', %s, %s)""",
        (session_id, user_id, req.device_fingerprint, datetime.utcnow())
    )
    conn.commit()
    cur.close()
    conn.close()

    return LoginResponse(session_id=session_id, user_id=str(user_id), full_name=full_name)


@router.get("/dashboard/{session_id}")
def dashboard(session_id: str):
    """Fake balance + recent activity. Static-ish for now — this is a demo bank, not a real one."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM sessions WHERE id = %s", (session_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    cur.close()
    conn.close()
    return {
        "balance": 458200.00,
        "currency": "NGN",
        "recent_transactions": []  # Division 4+ will populate this from real transaction history
    }


@router.post("/transfer", response_model=TransferResponse)
def transfer(req: TransferRequest):
    """
    Records the transfer attempt. Division 2 does NOT decide ALLOW/CHALLENGE/BLOCK —
    that's the detection core (Division 4) and hard controls (Division 5).
    This endpoint's only job is to log the attempt accurately so those divisions
    have something real to score.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM sessions WHERE id = %s", (req.session_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    user_id = row[0]

    cur.execute(
        "SELECT COUNT(*) FROM transactions WHERE user_id = %s AND beneficiary_account = %s",
        (user_id, req.beneficiary_account)
    )
    prior_count = cur.fetchone()[0]
    beneficiary_is_novel = prior_count == 0

    transaction_id = str(uuid.uuid4())
    cur.execute(
        """INSERT INTO transactions
           (id, session_id, user_id, beneficiary_account, beneficiary_is_novel, amount, requested_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (transaction_id, req.session_id, user_id, req.beneficiary_account,
         beneficiary_is_novel, req.amount, datetime.utcnow())
    )
    conn.commit()
    cur.close()
    conn.close()

    return TransferResponse(transaction_id=transaction_id, status="recorded")
