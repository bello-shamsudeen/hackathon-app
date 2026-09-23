"""Division 2B - USSD gateway. Uses memory_store."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Response
import uuid

from app.services.memory_store import (
    get_user_by_msisdn, create_session, get_session, log_transaction, log_ussd_event,
    get_balance, debit_balance,
    is_blocked, set_blocked, verify_pin, get_user_by_id,
)
from app.models.schemas import USSDRequest
from app.routers.score import score_session

router = APIRouter(prefix="/ussd", tags=["ussd"])

USSD_SESSION_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")
_ussd_events: list[dict] = []

_session_map: dict[str, str] = {}

# Feature 2 - pending OTP step-ups for the USSD channel, keyed by user_id.
import secrets
_USSD_PENDING_OTP: dict[str, dict] = {}
_USSD_OTP_TTL_SECONDS = 300


def _fmt_remaining(iso_ts):
    """Human-readable remaining block time for USSD messages."""
    try:
        secs = max(0, int((datetime.fromisoformat(iso_ts) - datetime.utcnow()).total_seconds()))
        return f"{secs // 3600}h {(secs % 3600) // 60}m"
    except Exception:
        return "a short while"


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
        sess = get_session(real_session_id)
        if sess and sess["user_id"]:
            bal = get_balance(sess["user_id"])
            response_text = f"END Your balance is NGN {bal:,.2f}"
        else:
            response_text = "END Your balance is unavailable. Please try again."
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
                blocked, _blocked_until = is_blocked(sess["user_id"])
            else:
                blocked, _blocked_until = False, None
            if blocked:
                # Division 9 - dynamic block timer enforced before scoring.
                response_text = ("END Your account is temporarily blocked for your security. "
                                 f"Time remaining: {_fmt_remaining(_blocked_until)}.")
            elif sess and sess["user_id"] and not verify_pin(get_user_by_id(sess["user_id"]), pin):
                response_text = "END Incorrect PIN."
            elif sess and sess["user_id"]:
                log_transaction(real_session_id, sess["user_id"], recipient, float(amount))
                try:
                    detection = score_session(real_session_id)
                    action = detection.get("action", "allow")
                except Exception as exc:
                    action = "allow"
                if action == "block":
                    # Division 9 - severity-scaled block timer (1h-6h).
                    _sev = float((detection if isinstance(detection, dict) else {}).get("risk_score") or 0)
                    _hours = 1 + int(5 * min(1.0, max(0.0, _sev)))
                    _until = (datetime.utcnow() + timedelta(hours=_hours)).isoformat()
                    set_blocked(sess["user_id"], _until)
                    response_text = ("END Transaction declined for your security. "
                                     f"Your account is blocked for {_fmt_remaining(_until)}. "
                                     "Contact your bank if you believe this is an error.")
                elif action == "step_up":
                    # Feature 2 - hold the transfer and issue a 6-digit OTP.
                    #   Continues as: 2*recipient*amount*pin*otp
                    _otp = f"{secrets.randbelow(1000000):06d}"
                    _USSD_PENDING_OTP[sess["user_id"]] = {
                        "recipient": recipient, "amount": float(amount), "otp": _otp,
                        "expires": (datetime.utcnow() + timedelta(seconds=_USSD_OTP_TTL_SECONDS)).isoformat(),
                    }
                    response_text = f"CON Enter the 6-digit OTP sent to your phone (demo code: {_otp}):"
                else:
                    if debit_balance(sess["user_id"], float(amount)):
                        response_text = f"END Transaction successful. NGN {amount} sent to {recipient}."
                    else:
                        response_text = "END Insufficient funds. Your balance could not cover this transfer."
            else:
                response_text = "END Session expired. Please start again."
        elif len(steps) == 5:
            # Feature 2 - OTP verification for a held step-up transfer.
            otp_entered = steps[4]
            sess = get_session(real_session_id)
            _pending = _USSD_PENDING_OTP.get(sess["user_id"]) if sess and sess["user_id"] else None
            if not _pending:
                response_text = "END No transfer is awaiting verification. Start again from Send Money."
            elif datetime.utcnow() > datetime.fromisoformat(_pending["expires"]):
                _USSD_PENDING_OTP.pop(sess["user_id"], None)
                response_text = "END The OTP expired. Start the transfer again."
            elif otp_entered.strip() != _pending["otp"]:
                response_text = "END Incorrect OTP. Check the code and try again."
            else:
                _USSD_PENDING_OTP.pop(sess["user_id"], None)
                if debit_balance(sess["user_id"], _pending["amount"]):
                    response_text = f"END Transaction successful. NGN {_pending['amount']:,.0f} sent to {_pending['recipient']}."
                else:
                    response_text = "END Insufficient funds. Your balance could not cover this transfer."
        else:
            response_text = "END Invalid input."
    elif steps[0] == "3":
        response_text = "END Airtime purchase is not available in this demo."
    elif steps[0] == "4":
        response_text = "END PIN change is not available in this demo."
    else:
        response_text = "END Invalid option."

    # retry_count: a real, live-triggerable retry signal. Fires when the user
    # actually mistypes a menu selection (an invalid main-menu option, or an
    # invalid step within the Send Money flow) - genuine user error, not a
    # fabricated signal. PIN/timeout retry detection remains a known gap
    # (no PIN validation exists in this simplified flow at all), documented
    # separately - this only covers the menu-navigation-error case.
    is_retry = response_text in ("END Invalid input.", "END Invalid option.")
    log_ussd_event(real_session_id, retry_count=1 if is_retry else 0, timeout_count=0)

    return Response(content=response_text, media_type="text/plain")
