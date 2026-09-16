"""Division 2B — USSD gateway. Uses memory_store."""
from fastapi import APIRouter, Response
import uuid

from app.backend_additions.services.memory_store import (
    get_user_by_msisdn, create_session, get_session, log_transaction,
)
from app.models.schemas import USSDRequest

router = APIRouter(prefix="/ussd", tags=["ussd"])

USSD_SESSION_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")
_ussd_events: list[dict] = []


def _session_uuid(aggregator_session_id: str) -> str:
    return str(uuid.uuid5(USSD_SESSION_NAMESPACE, aggregator_session_id))


@router.post("")
def ussd_handler(req: USSDRequest):
    session_uuid = _session_uuid(req.sessionId)
    sess = get_session(session_uuid)
    if not sess:
        user = get_user_by_msisdn(req.phoneNumber)
        user_id = str(user["id"]) if user else None
        create_session(user_id, "USSD", "USSD-DEVICE")
    _ussd_events.append({
        "id": str(uuid.uuid4()), "session_id": session_uuid,
        "menu_step": req.text, "recorded_at": __import__("datetime").datetime.utcnow(),
    })

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
            sess = get_session(session_uuid)
            if sess and sess["user_id"]:
                log_transaction(session_uuid, sess["user_id"], recipient, float(amount))
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