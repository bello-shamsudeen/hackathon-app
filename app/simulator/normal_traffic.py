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


def _run_one_normal_session(cur):
    cur.execute("SELECT id, msisdn, typical_amount_avg FROM users WHERE persona_tag IS NOT NULL ORDER BY random() LIMIT 1")
    row = cur.fetchone()
    if not row:
        return
    user_id, msisdn, avg_amount = row

    login_resp = requests.post(f"{BASE_URL}/bank/login", json={
        "msisdn": msisdn, "pin": "0000", "device_fingerprint": "KNOWN-DEVICE-NORMAL"
    })
    if login_resp.status_code != 200:
        return
    session_id = login_resp.json()["session_id"]

    requests.post(f"{BASE_URL}/ingest/behavior", json={"events": [
        {"session_id": session_id, "event_type": "KEYDOWN", "key_flight_ms": random.randint(200, 350)},
        {"session_id": session_id, "event_type": "NAV", "nav_screen": "dashboard"},
        {"session_id": session_id, "event_type": "NAV", "nav_screen": "beneficiary_select"},
        {"session_id": session_id, "event_type": "NAV", "nav_screen": "amount_entry"},
        {"session_id": session_id, "event_type": "NAV", "nav_screen": "review"},
        {"session_id": session_id, "event_type": "NAV", "nav_screen": "confirm"},
    ]})
    amount = max(500, random.gauss(float(avg_amount or 15000), 3000))
    requests.post(f"{BASE_URL}/bank/transfer", json={
        "session_id": session_id, "beneficiary_account": "4445556667", "amount": round(amount, 2)
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
