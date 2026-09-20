"""
Division 4 - Feature Engineering Layer.
Converts RAW rows from behavioral_events / ussd_events (captured live by
Division 2's frontend) into the same 4+4 deviation features the models were
trained on in Division 3. These formulas are COPY-IDENTICAL to
data/generate_dataset.py and the teammate's Brief C - this is the one place
train/serve mismatch would happen if they ever drifted apart, so treat any
change here as needing a matching change in both other places.
"""
from datetime import datetime

from app.services import velocity
from app.services import memory_store

# Screens that count as a "safe" first action. NOTE: first_action_deviation
# is meant to key off an explicit event_seq field the frontend doesn't send
# yet (useBehaviorCapture.js needs event_seq + client_ts added). Until then,
# we use recorded_at ordering as an interim proxy for "first nav event" -
# this is the documented fallback, not the final design.
SAFE_FIRST_SCREENS = {"DASHBOARD", "HOME", "BALANCE"}


def compute_velocity_features(user_id: str) -> dict:
    """
    Division 4B - the Redis rolling counters for this user, read (not
    incremented) as part of feature engineering. These do NOT go into the
    trained model's 4-feature input vector (that would break the Division 3
    pkls); they travel alongside it for the decision engine, the rules
    fallback (4E), the stored contribution record, and Division 5.
    """
    return velocity.snapshot(user_id)


def compute_app_features(session_id: str) -> dict:
    """
    Reads all behavioral_events for a session (plus its transaction, if any)
    and derives the 4 app-channel deviation features.
    """
    events = memory_store.get_behavioral_events_for_session(session_id)
    tx = memory_store.get_transaction_for_session(session_id)

    flight_times = [e.get("key_flight_ms") for e in events if e.get("key_flight_ms") is not None]
    pasted = any(e.get("is_paste") for e in events)
    amount = float(tx["amount"]) if tx else 0.0

    # Approximate chars/sec from average flight time between keys (ms -> chars/sec)
    if flight_times:
        avg_flight_ms = sum(flight_times) / len(flight_times)
        chars_per_sec = 1000.0 / avg_flight_ms if avg_flight_ms > 0 else 4.0
    else:
        chars_per_sec = 4.0  # no keystroke data captured - fall back to baseline, not zero

    # first_action_deviation: look at the first event carrying a nav_screen,
    # in recorded_at order (interim proxy for event_seq - see module docstring).
    nav_events = [e for e in events if e.get("nav_screen") is not None]
    if nav_events:
        first_screen = nav_events[0]["nav_screen"]
        first_action_deviation = 0.0 if str(first_screen).upper() in SAFE_FIRST_SCREENS else 1.0
    else:
        first_action_deviation = 1.0  # None -> 1.0, per the canonical rule

    # ---- CANONICAL FORMULAS - identical to data/generate_dataset.py ----
    typing_speed_deviation = (chars_per_sec - 4.0) / 1.0
    pasted_char_ratio = 0.9 if pasted else 0.05
    amount_deviation = (amount - 15000) / (15000 * 2.06)

    return {
        "typing_speed_deviation": typing_speed_deviation,
        "pasted_char_ratio": pasted_char_ratio,
        "first_action_deviation": first_action_deviation,
        "amount_deviation": amount_deviation,
    }


def compute_ussd_features(session_id: str) -> dict:
    session = memory_store.get_session(session_id)
    ussd_events = memory_store.get_ussd_events_for_session(session_id)
    tx = memory_store.get_transaction_for_session(session_id)

    retries = sum(e.get("retry_count", 0) for e in ussd_events) if ussd_events else 0
    hour = ussd_events[0]["recorded_at"].hour if ussd_events else 12

    amount = float(tx["amount"]) if tx else 0.0

    bucket = "OVER_30"
    if session:
        telco = memory_store.get_telco_state(session["user_id"])
        last_swap_at = telco.get("last_sim_swap_at") if telco else None
        if last_swap_at:
            days_since = (datetime.utcnow() - last_swap_at.replace(tzinfo=None)).days
            if days_since > 30:
                bucket = "OVER_30"
            elif days_since > 14:
                bucket = "15_30"
            elif days_since > 4:
                bucket = "5_14"
            else:
                bucket = "0_4"

    # ---- CANONICAL FORMULAS - identical to data/generate_dataset.py ----
    time_of_day_deviation = abs(hour - 14) / 12
    session_retry_deviation = retries / 2.0
    swap_map = {"OVER_30": 0.0, "15_30": 0.2, "5_14": 0.6, "0_4": 0.95}
    sim_swap_risk = swap_map[bucket]
    amount_deviation = (amount - 4000) / (4000 * 0.98)

    return {
        "amount_deviation": amount_deviation,
        "time_of_day_deviation": time_of_day_deviation,
        "session_retry_deviation": session_retry_deviation,
        "sim_swap_risk": sim_swap_risk,
    }