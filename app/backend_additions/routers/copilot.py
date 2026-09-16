"""
Division 6C — AI Analyst Copilot.
A natural-language query box for the investigation console (built in
Division 9). The LLM is given ONLY the actual retrieved data for the
session in question as context — decision record, SHAP reason codes,
correlation edges, sensor alerts — and must answer strictly from that.
This is how real SOC copilots work: retrieval-grounded, not open-ended.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.db import get_connection
from app.services.llm_explainer import _try_groq, _try_gemini, _try_ollama

router = APIRouter(prefix="/copilot", tags=["copilot"])


class CopilotQuery(BaseModel):
    session_id: str
    question: str


def _gather_session_context(session_id: str, cur) -> str:
    cur.execute(
        """SELECT risk_score, verdict, triggered_rules, feature_contributions,
                  explanation_customer, explanation_analyst, model_version, latency_ms
           FROM decisions WHERE session_id = %s ORDER BY decided_at DESC LIMIT 1""",
        (session_id,)
    )
    decision = cur.fetchone()

    cur.execute(
        "SELECT device_fingerprint, ip_address, channel FROM sessions WHERE id = %s",
        (session_id,)
    )
    session = cur.fetchone()

    cur.execute(
        "SELECT sensor, alert_tag, severity FROM sensor_alerts WHERE session_id = %s",
        (session_id,)
    )
    alerts = cur.fetchall()

    context_parts = []
    if decision:
        context_parts.append(
            f"Decision: risk_score={decision[0]}, verdict={decision[1]}, "
            f"triggered_rules={decision[2]}, feature_contributions={decision[3]}, "
            f"customer_message='{decision[4]}', model_version={decision[6]}, latency_ms={decision[7]}"
        )
    if session:
        context_parts.append(f"Session: channel={session[2]}, device={session[0]}, ip={session[1]}")
    if alerts:
        context_parts.append(f"Sensor alerts: {alerts}")

    return "\n".join(context_parts) if context_parts else "No data found for this session."


@router.post("/ask")
def ask_copilot(query: CopilotQuery):
    conn = get_connection()
    cur = conn.cursor()
    context = _gather_session_context(query.session_id, cur)
    cur.close()
    conn.close()

    prompt = (
        f"You are a fraud analyst assistant. Answer the analyst's question using "
        f"ONLY the data below. If the data doesn't contain the answer, say so plainly "
        f"rather than guessing.\n\nSESSION DATA:\n{context}\n\n"
        f"QUESTION: {query.question}\n\nANSWER:"
    )

    for provider_fn in [_try_groq, _try_gemini, _try_ollama]:
        result = provider_fn(prompt)
        if result:
            return {"answer": result, "session_id": query.session_id}

    return {
        "answer": f"AI copilot is unavailable right now. Raw session data: {context}",
        "session_id": query.session_id,
    }
