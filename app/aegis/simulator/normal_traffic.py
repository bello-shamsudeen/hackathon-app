"""
Division 7 — Normal Traffic Generator.
Runs continuously in the background during a demo so the dashboard shows a
realistic stream of legitimate activity that stays green — proving the
system isn't just flagging everything, it's actually discriminating.
"""
import random
import time
import threading
import requests

BASE_URL = "http://localhost:8000"
_stop_flag = threading.Event()


# Full, unremarkable navigation path (all 6 screens -> screen_sequence_anomaly 0).
_NORMAL_NAV = ["login", "dashboard", "beneficiary_select", "amount_entry", "review", "confirm"]
# Small/moderate amounts. The app model's amount_deviation is measured against a
# FIXED ~15k baseline (Division 3), not the user's own typical, so amounts are
# kept comfortably inside that band rather than drawn from typical_amount_avg.
_NORMAL_AMOUNTS = [2000, 3500, 5000, 7500, 9000, 11000, 13000, 15000]


def _run_one_normal_session(cur):
    cur.execute(
        """SELECT u.id, u.msisdn FROM users u
           JOIN telco_state t ON t.user_id = u.id
           WHERE u.persona_tag IS NOT NULL AND u.persona_tag <> 'DIV2_TEST'
           ORDER BY random() LIMIT 1"""
    )
    row = cur.fetchone()
    if not row:
        return
    user_id, msisdn = row

    # Each legitimate customer uses their OWN device, deterministically — a
    # single shared fingerprint across many users would (correctly) trip the
    # identity-correlation fraud-ring control.
    device_fp = f"legit-dev-{user_id}"

    login_resp = requests.post(f"{BASE_URL}/bank/login", json={
        "msisdn": msisdn, "pin": "0000", "device_fingerprint": device_fp
    })
    if login_resp.status_code != 200:
        return
    session_id = login_resp.json()["session_id"]

    events = [{"session_id": session_id, "event_type": "NAV", "nav_screen": s} for s in _NORMAL_NAV]
    for _ in range(random.randint(12, 20)):
        events.append({"session_id": session_id, "event_type": "KEYUP",
                       "key_flight_ms": random.randint(210, 260)})  # ~4 chars/sec, normal
    requests.post(f"{BASE_URL}/ingest/behavior", json={"events": events})

    amount = random.choice(_NORMAL_AMOUNTS)
    requests.post(f"{BASE_URL}/bank/transfer", json={
        "session_id": session_id, "beneficiary_account": f"44{random.randint(10**6, 10**7-1)}",
        "amount": amount,
    })
    requests.post(f"{BASE_URL}/score/session/{session_id}")


def start_background_traffic(get_connection_fn, interval_seconds: int = 8):
    """Runs in a background thread until stop_background_traffic() is called."""
    _stop_flag.clear()

    def loop():
        while not _stop_flag.is_set():
            try:
                conn = get_connection_fn()
                cur = conn.cursor()
                _run_one_normal_session(cur)
                cur.close()
                conn.close()
            except Exception as e:
                print(f"[normal_traffic] error (non-fatal): {e}")
            time.sleep(interval_seconds)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread


def stop_background_traffic():
    _stop_flag.set()
