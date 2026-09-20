"""Division 2B - USSD gateway. Uses memory_store."""
from datetime import datetime
from fastapi import APIRouter, Response
import uuid

from app.services.memory_store import (
    get_user_by_msisdn, create_session, get_session, log_transaction, log_ussd_event,
)
from app.models.schemas import USSDRequest
from app.routers.score import score_session

router = APIRouter(prefix="/ussd", tags=["ussd"])

USSD_SESSION_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")
_ussd_events: list[dict] = []

# Maps the deterministic per-aggregator-session UUID to the real memory_store
# session id, since create_session() always mints its own id internally and
# has no way to be told to use a specific one. Keeping this mapping local to
# this router avoids touching memory_store.create_session(), which every
# other channel (app login, registration) also depends on.
_session_map: dict[str, str] = {}


def _session_uuid(aggregator_session_id: str) -> str:
    return str(uuid.uuid5(USSD_SESSION_NAMESPACE, aggregator_session_id))


@router.post("")
def ussd_handler(req: USSDRequest):
    session_uuid = _session_uuid(req.sessionId)

    real_session_id = _session_map.get(session_uuid)
    if real_session_id is None:
        user = get_user_by_msisdn(req.phoneNumber)
        user_id = str(user["id"]) if user else None
        real_session_id = create_session(user_id, "USSD", "USSD-DEVICE")
        _session_map[session_uuid] = real_session_id

    _ussd_events.append({
        "id": str(uuid.uuid4()), "session_id": real_session_id,
        "menu_step": req.text, "recorded_at": datetime.utcnow(),
    })

    # retry_count/timeout_count: no retry or timeout detection exists yet in
    # this menu logic, so both are recorded as 0 for now. This is a known,
    # separate feature gap, not a functioning signal - flagged, not invented.
    log_ussd_event(real_session_id, retry_count=0, timeout_count=0)

    steps = req.text.split("*") if req.text else []

    if steps == [] or steps == [""]:
        response_text = (
            "CON Welcome to Aegis Bank\n"
            "1. Check Balance\n"
            "2. Send Money\n"
            "3. Buy Airtime\n"
            "4. Change PIN"
        )
    elif steps[0] == "1":
        response_text = "END Your balance is NGN 458,200.00"
    elif steps[0] == "2":
        if len(steps) == 1:
            response_text = "CON Enter recipient number:"
        elif len(steps) == 2:
            response_text = "CON Enter amount:"
        elif len(steps) == 3:
            response_text = "CON Enter your PIN to confirm:"
        elif len(steps) == 4:
            recipient, amount, pin = steps[1], steps[2], steps[3]
            sess = get_session(real_session_id)
            if sess and sess["user_id"]:
                log_transaction(real_session_id, sess["user_id"], recipient, float(amount))
                try:
                    detection = score_session(real_session_id)
                    action = detection.get("action", "allow")
                except Exception as exc:
                    action = "allow"
                if action == "block":
                    response_text = "END Transaction declined for your security. Contact your bank if you believe this is an error."
                elif action == "step_up":
                    response_text = "END Additional verification needed to complete this transfer. Please contact your bank or visit a branch."
                else:
                    response_text = f"END Transaction successful. NGN {amount} sent to {recipient}."
            else:
                response_text = f"END Transaction successful. NGN {amount} sent to {recipient}."
        else:
            response_text = "END Invalid input."
    elif steps[0] == "3":
        response_text = "END Airtime purchase is not available in this demo."
    elif steps[0] == "4":
        response_text = "END PIN change is not available in this demo."
    else:
        response_text = "END Invalid option."

    return Response(content=response_text, media_type="text/plain")