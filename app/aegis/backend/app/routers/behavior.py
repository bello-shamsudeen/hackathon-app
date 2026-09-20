"""
Division 2 - behavioral telemetry ingestion (WEB channel).
This is the endpoint the frontend's useBehaviorCapture hook streams to
continuously, not just on form submit. Every keystroke, paste, backspace,
nav change, and call-state toggle lands here in near real time.
"""
from fastapi import APIRouter

from app.services import memory_store
from app.models.schemas import BehaviorBatch

router = APIRouter(prefix="/ingest", tags=["behavior"])


@router.post("/behavior")
def ingest_behavior(batch: BehaviorBatch):
    events = [
        {
            "session_id": event.session_id,
            "event_type": event.event_type,
            "key_dwell_ms": event.key_dwell_ms,
            "key_flight_ms": event.key_flight_ms,
            "is_paste": event.is_paste,
            "backspace_count": event.backspace_count,
            "nav_screen": event.nav_screen,
            "cursor_smoothness_score": event.cursor_smoothness_score,
            "call_active": event.call_active,
        }
        for event in batch.events
    ]
    memory_store.log_behavioral_events(events)
    return {"ingested": len(events)}