"""
Division 4 — live scoring endpoint.
Called right after a transfer is recorded (Division 2's /bank/transfer and
/ussd endpoints should call this next). This is the actual detection loop:
raw events -> features -> risk score -> decision -> plain-English message.
"""
from fastapi import APIRouter, HTTPException
import time

from app.db import get_connection
from app.services.feature_engineering import compute_app_features, compute_ussd_features
from app.services.scoring import score_app_session, score_ussd_session
from app.services.decision_engine import make_decision

router = APIRouter(prefix="/score", tags=["scoring"])


@router.post("/session/{session_id}")
def score_session(session_id: str):
    start = time.perf_counter()
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT channel, user_id FROM sessions WHERE id = %s", (session_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    channel, user_id = row

    cur.execute("SELECT COUNT(*) FROM sessions WHERE user_id = %s", (user_id,))
    session_count = cur.fetchone()[0]

    if channel == "WEB":
        features = compute_app_features(session_id, cur)
        features["user_id"] = str(user_id)
        features["session_count"] = session_count
        model_output = score_app_session(features)
    else:
        features = compute_ussd_features(session_id, cur)
        features["user_id"] = str(user_id)
        features["session_count"] = session_count
        model_output = score_ussd_session(features)

    decision = make_decision(model_output)

    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    cur.execute(
        """INSERT INTO decisions
           (id, session_id, risk_score, verdict, feature_contributions,
            explanation_customer, model_version, latency_ms, decided_at)
           VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, now())""",
        (session_id, model_output["risk_score"], decision["tier"].upper(),
         str(model_output["top_features"]), decision["message"],
         model_output.get("_model_version", "aegis-v1"), latency_ms)
    )
    conn.commit()
    cur.close()
    conn.close()

    return {
        **decision,
        "risk_score": model_output["risk_score"],
        "top_features": model_output["top_features"],
        "latency_ms": latency_ms,
    }
