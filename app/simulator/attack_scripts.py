"""
Division 7 — Attack Simulator.
These scripts hit the REAL live API (not the database directly) — same as a
real attacker would. Each archetype's shape matches what Division 3's
synthetic data taught the models to recognize, and what Division 5's hard
controls specifically guard against. This is what proves the numbers on the
honesty dashboard are real, not claimed.

Each function returns a result dict summarizing what happened, so the
router (below) can report it back to the dashboard button that triggered it.
"""
import random
import time
import requests

BASE_URL = "http://localhost:8000"


def _pick_synthetic_user(cur):
    """Pick a random synthetic user (persona-based, from Division 3) to attack against."""
    cur.execute("SELECT id, msisdn FROM users WHERE persona_tag IS NOT NULL ORDER BY random() LIMIT 1")
    return cur.fetchone()


def attack_credential_stuffing(cur) -> dict:
    """Fast, pasted-looking login attempts, minimal navigation, large amount."""
    user_id, msisdn = _pick_synthetic_user(cur)
    login_resp = requests.post(f"{BASE_URL}/bank/login", json={
        "msisdn": msisdn, "pin": "0000", "device_fingerprint": "ATTACKER-DEVICE-CS"
    })
    if login_resp.status_code != 200:
        return {"archetype": "CREDENTIAL_STUFFING", "status": "login_failed", "detail": login_resp.text}
    session_id = login_resp.json()["session_id"]

    # Simulate instant paste + no browsing before transferring
    requests.post(f"{BASE_URL}/ingest/behavior", json={"events": [
        {"session_id": session_id, "event_type": "PASTE", "is_paste": True},
        {"session_id": session_id, "event_type": "NAV", "nav_screen": "confirm"},
    ]})
    transfer_resp = requests.post(f"{BASE_URL}/bank/transfer", json={
        "session_id": session_id, "beneficiary_account": "9999888877", "amount": 45000
    })
    return {"archetype": "CREDENTIAL_STUFFING", "session_id": session_id,
            "status": "completed", "transfer_response": transfer_resp.json()}


def attack_otp_replay(cur) -> dict:
    """
    Complete one legitimate-looking transfer (issuing/consuming a token via
    whatever real flow Division 5 wired), then attempt the SAME confirmation
    a second time — this should be caught by Token Integrity, not the ML model.
    """
    user_id, msisdn = _pick_synthetic_user(cur)
    login_resp = requests.post(f"{BASE_URL}/bank/login", json={
        "msisdn": msisdn, "pin": "0000", "device_fingerprint": "ATTACKER-DEVICE-REPLAY"
    })
    session_id = login_resp.json()["session_id"]

    first = requests.post(f"{BASE_URL}/bank/transfer", json={
        "session_id": session_id, "beneficiary_account": "1112223334", "amount": 20000
    })
    # NOTE: exact replay mechanics depend on how Division 5 wired token
    # issuance into the real transfer/confirm endpoint — adapt this call to
    # match whatever that shape actually is (see Claude Code prompt).
    second = requests.post(f"{BASE_URL}/bank/transfer", json={
        "session_id": session_id, "beneficiary_account": "1112223334", "amount": 20000
    })
    return {"archetype": "OTP_REPLAY", "session_id": session_id,
            "first_attempt": first.json(), "second_attempt": second.json()}


def attack_sim_swap_takeover(cur) -> dict:
    """
    The headline attack: correct PIN, correct OTP, NEW device, recent SIM
    swap. Should be blocked by Division 5's SIM-swap module regardless of
    how normal the behavioral score looks.
    """
    from datetime import datetime, timedelta
    user_id, msisdn = _pick_synthetic_user(cur)

    # Simulate the swap: update telco_state to show a swap 1 day ago
    cur.execute(
        "UPDATE telco_state SET last_sim_swap_at = %s WHERE user_id = %s",
        (datetime.utcnow() - timedelta(days=1), user_id)
    )
    cur.connection.commit()

    login_resp = requests.post(f"{BASE_URL}/bank/login", json={
        "msisdn": msisdn, "pin": "0000", "device_fingerprint": "ATTACKER-NEW-DEVICE-SWAP"
    })
    session_id = login_resp.json()["session_id"]

    # Deliberately NORMAL-looking behavior — the point is the hard control
    # fires even when behavior alone would score low.
    requests.post(f"{BASE_URL}/ingest/behavior", json={"events": [
        {"session_id": session_id, "event_type": "KEYDOWN", "key_flight_ms": 250},
        {"session_id": session_id, "event_type": "NAV", "nav_screen": "dashboard"},
        {"session_id": session_id, "event_type": "NAV", "nav_screen": "beneficiary_select"},
        {"session_id": session_id, "event_type": "NAV", "nav_screen": "amount_entry"},
        {"session_id": session_id, "event_type": "NAV", "nav_screen": "review"},
        {"session_id": session_id, "event_type": "NAV", "nav_screen": "confirm"},
    ]})
    transfer_resp = requests.post(f"{BASE_URL}/bank/transfer", json={
        "session_id": session_id, "beneficiary_account": "5556667778", "amount": 18000
    })
    score_resp = requests.post(f"{BASE_URL}/score/session/{session_id}")
    return {"archetype": "SIM_SWAP_TAKEOVER", "session_id": session_id,
            "transfer_response": transfer_resp.json(), "score_response": score_resp.json()}


def attack_coached_victim(cur) -> dict:
    """Real user's own device/behavior, but slow, hesitant, call active."""
    user_id, msisdn = _pick_synthetic_user(cur)
    login_resp = requests.post(f"{BASE_URL}/bank/login", json={
        "msisdn": msisdn, "pin": "0000", "device_fingerprint": "KNOWN-DEVICE"
    })
    session_id = login_resp.json()["session_id"]

    requests.post(f"{BASE_URL}/ingest/behavior", json={"events": [
        {"session_id": session_id, "event_type": "KEYDOWN", "key_flight_ms": 1400},  # unusually slow
        {"session_id": session_id, "event_type": "CALL_STATE", "call_active": True},
        {"session_id": session_id, "event_type": "NAV", "nav_screen": "confirm"},
    ]})
    transfer_resp = requests.post(f"{BASE_URL}/bank/transfer", json={
        "session_id": session_id, "beneficiary_account": "7778889990", "amount": 60000
    })
    score_resp = requests.post(f"{BASE_URL}/score/session/{session_id}")
    return {"archetype": "COACHED_VICTIM", "session_id": session_id,
            "transfer_response": transfer_resp.json(), "score_response": score_resp.json()}


def attack_slow_drift(cur, n_transfers: int = 3) -> dict:
    """Several transfers, each just under the typical threshold, escalating slightly."""
    user_id, msisdn = _pick_synthetic_user(cur)
    results = []
    amount = 14000
    for i in range(n_transfers):
        login_resp = requests.post(f"{BASE_URL}/bank/login", json={
            "msisdn": msisdn, "pin": "0000", "device_fingerprint": "KNOWN-DEVICE"
        })
        session_id = login_resp.json()["session_id"]
        transfer_resp = requests.post(f"{BASE_URL}/bank/transfer", json={
            "session_id": session_id, "beneficiary_account": "3334445556", "amount": amount
        })
        score_resp = requests.post(f"{BASE_URL}/score/session/{session_id}")
        results.append({"amount": amount, "score": score_resp.json()})
        amount += 800  # creeping up, staying near threshold
        time.sleep(0.5)
    return {"archetype": "SLOW_DRIFT", "attempts": results}


def attack_impossible_travel(cur) -> dict:
    """Two sessions for the same user, different IPs, implausibly close in time."""
    user_id, msisdn = _pick_synthetic_user(cur)

    login1 = requests.post(f"{BASE_URL}/bank/login", json={
        "msisdn": msisdn, "pin": "0000", "device_fingerprint": "DEVICE-A"
    })
    session1 = login1.json()["session_id"]

    login2 = requests.post(f"{BASE_URL}/bank/login", json={
        "msisdn": msisdn, "pin": "0000", "device_fingerprint": "DEVICE-B-DIFFERENT-LOCATION"
    })
    session2 = login2.json()["session_id"]

    transfer_resp = requests.post(f"{BASE_URL}/bank/transfer", json={
        "session_id": session2, "beneficiary_account": "2223334445", "amount": 25000
    })
    score_resp = requests.post(f"{BASE_URL}/score/session/{session2}")
    return {"archetype": "IMPOSSIBLE_TRAVEL", "session_1": session1, "session_2": session2,
            "transfer_response": transfer_resp.json(), "score_response": score_resp.json()}


ATTACK_FUNCTIONS = {
    "CREDENTIAL_STUFFING": attack_credential_stuffing,
    "OTP_REPLAY": attack_otp_replay,
    "SIM_SWAP_TAKEOVER": attack_sim_swap_takeover,
    "COACHED_VICTIM": attack_coached_victim,
    "SLOW_DRIFT": attack_slow_drift,
    "IMPOSSIBLE_TRAVEL": attack_impossible_travel,
}
