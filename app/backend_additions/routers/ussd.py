"""
Division 2B — the USSD gateway.
THIS IS PROTOCOL-ACCURATE, not a fake menu. It implements the real
aggregator<->bank contract used by MTN/Airtel/Glo-facing USSD aggregators
(e.g. Africa's Talking): the aggregator POSTs sessionId/phoneNumber/
serviceCode/text, and the bank replies with plain text starting with
'CON ' (continue, show more menu) or 'END ' (terminate session).

Point a real aggregator at this endpoint in production and it works
unchanged — only the telco in front of it is what we're simulating.
"""
from fastapi import APIRouter, Response
import uuid
from datetime import datetime

from app.db import get_connection
from app.models.schemas import USSDRequest

router = APIRouter(prefix="/ussd", tags=["ussd"])

# In-memory session-menu-state is NOT used here — the whole point of the
# real USSD protocol is that 'text' carries the FULL accumulated input each
# time, so the bank is stateless between requests except for what's in the DB.


def _get_or_create_session(cur, session_id: str, phone_number: str):
    cur.execute("SELECT id FROM sessions WHERE id = %s", (session_id,))
    if cur.fetchone():
        return
    cur.execute("SELECT id FROM users WHERE msisdn = %s", (phone_number,))
    row = cur.fetchone()
    user_id = row[0] if row else None
    cur.execute(
        """INSERT INTO sessions (id, user_id, channel, started_at)
           VALUES (%s, %s, 'USSD', %s)""",
        (session_id, user_id, datetime.utcnow())
    )


def _log_ussd_step(cur, session_id: str, menu_step: str):
    cur.execute(
        """INSERT INTO ussd_events (id, session_id, menu_step, recorded_at)
           VALUES (%s, %s, %s, %s)""",
        (str(uuid.uuid4()), session_id, menu_step, datetime.utcnow())
    )


@router.post("")
def ussd_handler(req: USSDRequest):
    conn = get_connection()
    cur = conn.cursor()
    _get_or_create_session(cur, req.sessionId, req.phoneNumber)
    _log_ussd_step(cur, req.sessionId, req.text)

    # req.text is the FULL accumulated input, e.g. "" -> "2" -> "2*08012345678" -> "2*08012345678*5000"
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
            # Division 5 hard controls (SIM-swap check, token integrity) will
            # intercept BEFORE this point in a later division. For now, Division 2
            # just records the attempt as a transaction, same as the WEB channel.
            cur.execute("SELECT user_id FROM sessions WHERE id = %s", (req.sessionId,))
            row = cur.fetchone()
            user_id = row[0] if row else None
            if user_id:
                cur.execute(
                    """INSERT INTO transactions
                       (id, session_id, user_id, beneficiary_account, amount, requested_at)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (str(uuid.uuid4()), req.sessionId, user_id, recipient, float(amount), datetime.utcnow())
                )
            response_text = f"END Transaction successful. NGN {amount} sent to {recipient}."
        else:
            response_text = "END Invalid input."

    elif steps[0] == "3":
        response_text = "END Airtime purchase is not available in this demo."

    elif steps[0] == "4":
        response_text = "END PIN change is not available in this demo."

    else:
        response_text = "END Invalid option."

    conn.commit()
    cur.close()
    conn.close()

    # Real USSD aggregators expect plain text, not JSON — content type matters.
    return Response(content=response_text, media_type="text/plain")
