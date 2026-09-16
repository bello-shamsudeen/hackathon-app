"""
Division 4 — Feature Engineering Layer.
Converts RAW rows from behavioral_events / ussd_events (captured live by
Division 2's frontend) into the same 4+4 deviation features the models were
trained on in Division 3. These formulas are COPY-IDENTICAL to
data/generate_dataset.py and the teammate's Brief C — this is the one place
train/serve mismatch would happen if they ever drifted apart, so treat any
change here as needing a matching change in both other places.
"""
from datetime import datetime


def compute_app_features(session_id: str, cur) -> dict:
    """
    Reads all behavioral_events for a session and derives the 4 app-channel
    deviation features. cur is an open psycopg2 cursor.
    """
    cur.execute(
        """SELECT event_type, key_dwell_ms, key_flight_ms, is_paste,
                  backspace_count, nav_screen, amount
           FROM behavioral_events be
           LEFT JOIN transactions t ON t.session_id = be.session_id
           WHERE be.session_id = %s""",
        (session_id,)
    )
    rows = cur.fetchall()

    flight_times = [r[2] for r in rows if r[2] is not None]
    pasted = any(r[3] for r in rows)
    nav_screens = set(r[5] for r in rows if r[5] is not None)
    amount = next((r[6] for r in rows if r[6] is not None), 0)

    # Approximate chars/sec from average flight time between keys (ms -> chars/sec)
    if flight_times:
        avg_flight_ms = sum(flight_times) / len(flight_times)
        chars_per_sec = 1000.0 / avg_flight_ms if avg_flight_ms > 0 else 4.0
    else:
        chars_per_sec = 4.0  # no keystroke data captured — fall back to baseline, not zero

    screens_visited = max(1, len(nav_screens))

    # ---- CANONICAL FORMULAS — identical to data/generate_dataset.py ----
    typing_speed_deviation = (chars_per_sec - 4.0) / 1.0
    pasted_char_ratio = 0.9 if pasted else 0.05
    screen_sequence_anomaly = (6 - screens_visited) / 6
    amount_deviation = (amount - 15000) / (15000 * 2.06)

    return {
        "typing_speed_deviation": typing_speed_deviation,
        "pasted_char_ratio": pasted_char_ratio,
        "screen_sequence_anomaly": screen_sequence_anomaly,
        "amount_deviation": amount_deviation,
    }


def compute_ussd_features(session_id: str, cur) -> dict:
    cur.execute(
        """SELECT retry_count, timeout_count, recorded_at
           FROM ussd_events WHERE session_id = %s ORDER BY recorded_at""",
        (session_id,)
    )
    rows = cur.fetchall()
    retries = sum(r[0] for r in rows) if rows else 0
    hour = rows[0][2].hour if rows else 12

    cur.execute("SELECT amount FROM transactions WHERE session_id = %s LIMIT 1", (session_id,))
    tx = cur.fetchone()
    amount = tx[0] if tx else 0

    cur.execute(
        """SELECT ts.last_sim_swap_at FROM telco_state ts
           JOIN sessions s ON s.user_id = ts.user_id
           WHERE s.id = %s""",
        (session_id,)
    )
    swap_row = cur.fetchone()
    if swap_row and swap_row[0]:
        days_since = (datetime.utcnow() - swap_row[0].replace(tzinfo=None)).days
        if days_since > 30: bucket = "OVER_30"
        elif days_since > 14: bucket = "15_30"
        elif days_since > 4: bucket = "5_14"
        else: bucket = "0_4"
    else:
        bucket = "OVER_30"

    # ---- CANONICAL FORMULAS — identical to data/generate_dataset.py ----
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
