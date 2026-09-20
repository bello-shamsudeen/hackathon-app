"""
Division 6D — AI-drafted incident report.
One click on a blocked session produces a structured summary: what happened,
which signals fired, correlation context, recommended analyst action.
Grounded in the same real data the copilot uses — not a free-standing guess.
"""
from fastapi import APIRouter
from app.db import get_connection
from app.services.llm_explainer import _try_groq, _try_gemini, _try_ollama
from app.routers.copilot import _gather_session_context

router = APIRouter(prefix="/incident-report", tags=["incident_report"])


@router.get("/{session_id}")
def generate_incident_report(session_id: str):
    conn = get_connection()
    cur = conn.cursor()
    context = _gather_session_context(session_id, cur)
    cur.close()
    conn.close()

    prompt = (
        f"Write a short, structured fraud incident report using ONLY the data below. "
        f"Sections: What Happened, Signals Detected, Recommended Action. "
        f"Do not invent details not present in the data.\n\nSESSION DATA:\n{context}"
    )

    for name, provider_fn in [("groq", _try_groq), ("gemini", _try_gemini), ("ollama", _try_ollama)]:
        result = provider_fn(prompt)
        if result:
            return {"report": result, "session_id": session_id, "source": name}

    return {
        "report": f"AI report generation unavailable. Raw data for manual review:\n{context}",
        "session_id": session_id,
        "source": "raw_data_fallback",
    }
