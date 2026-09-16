"""
Division 8 — Security Ops endpoints.
Exposes: audit chain verify (+ a clearly-marked DEMO-ONLY tamper endpoint),
live metrics, and honeytoken check. Rate limiting is added as FastAPI
middleware in main.py (see Claude Code prompt) rather than a separate Nginx
container — same protective effect, far less infra risk for a hackathon.
"""
from fastapi import APIRouter, HTTPException
from app.db import get_connection
from app.services.audit_chain import verify_chain
from app.services.metrics import compute_live_metrics

router = APIRouter(prefix="/secops", tags=["secops"])


@router.get("/audit/verify")
def audit_verify():
    conn = get_connection()
    cur = conn.cursor()
    result = verify_chain(cur)
    cur.close()
    conn.close()
    return result


@router.post("/audit/demo-tamper/{decision_id}")
def audit_demo_tamper(decision_id: str):
    """
    DEMO-ONLY ENDPOINT — deliberately corrupts one audit row so the verify
    button can be shown going from green to red on stage. This should be
    clearly labeled in the UI (Division 9) as a demo control, never exposed
    as a real feature. Do not leave this reachable in a production build.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE audit_log SET row_data = row_data || '{\"tampered\": true}'::jsonb WHERE decision_id = %s",
        (decision_id,)
    )
    if cur.rowcount == 0:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="No audit row for that decision_id")
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "tampered", "decision_id": decision_id,
            "note": "Run GET /secops/audit/verify now — it should return valid=false."}


@router.get("/metrics")
def live_metrics():
    return compute_live_metrics()
