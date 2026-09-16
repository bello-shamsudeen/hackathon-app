"""
Division 2 — behavioral telemetry ingestion (WEB channel).
This is the endpoint the frontend's useBehaviorCapture hook streams to
continuously, not just on form submit. Every keystroke, paste, backspace,
nav change, and call-state toggle lands here in near real time.
"""
from fastapi import APIRouter
import uuid
from datetime import datetime

from app.db import get_connection
from app.models.schemas import BehaviorBatch

router = APIRouter(prefix="/ingest", tags=["behavior"])


@router.post("/behavior")
def ingest_behavior(batch: BehaviorBatch):
    conn = get_connection()
    cur = conn.cursor()
    for event in batch.events:
        cur.execute(
            """INSERT INTO behavioral_events
               (id, session_id, event_type, key_dwell_ms, key_flight_ms, is_paste,
                backspace_count, nav_screen, cursor_smoothness_score, call_active, recorded_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (str(uuid.uuid4()), event.session_id, event.event_type, event.key_dwell_ms,
             event.key_flight_ms, event.is_paste, event.backspace_count, event.nav_screen,
             event.cursor_smoothness_score, event.call_active, datetime.utcnow())
        )
    conn.commit()
    cur.close()
    conn.close()
    return {"ingested": len(batch.events)}
