"""
Division 3 — Synthetic Data Engine.

THIS IS THE SINGLE SOURCE OF TRUTH for both:
  (a) the rich dataset that populates Postgres (users, sessions,
      behavioral_events, ussd_events, telco_state, transactions) — what
      OUR OWN Division 4 detection core (Isolation Forest + XGBoost) trains on
  (b) the flat data/app_channel_data.csv and data/ussd_channel_data.csv files
      — what the teammate's Brief A models train on

Both outputs are derived from the SAME underlying random draws per session.
This is deliberate: it eliminates the train/serve mismatch risk flagged
earlier, because the deviation-feature formulas below are copy-identical to
Brief C's Tasks 4 and 6 — not independently reinvented.

Run: python data/generate_dataset.py
Requires: DATABASE_URL env var (same as backend), pandas, psycopg2, numpy
"""
import os
import random
import uuid
import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import psycopg2

from personas import PERSONAS, sample_user_from_persona

random.seed(42)
np.random.seed(42)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://aegis:aegis_dev_pw@localhost:5432/aegis")

N_USERS = 80
NORMAL_SESSIONS_PER_USER = 25
LEGITIMATE_ANOMALY_RATE = 0.06     # fraction of a user's OWN sessions that are genuine-but-unusual
ATTACKER_SESSION_TOTAL_APP = 101   # 101 / (80*25 + 101) = 4.81% positive — matches ~4.8% app target
ATTACKER_SESSION_TOTAL_USSD = 107  # 107 / (80*25 + 107) = 5.08% positive — matches ~5.1% ussd target

ATTACK_ARCHETYPES = [
    "CREDENTIAL_STUFFING", "OTP_REPLAY", "SIM_SWAP_TAKEOVER",
    "COACHED_VICTIM", "SLOW_DRIFT", "IMPOSSIBLE_TRAVEL",
]

MAX_SCREENS = 6  # login, dashboard, beneficiary_select, amount_entry, review, confirm


# ======================================================================
# CANONICAL DEVIATION FORMULAS — copy-identical to Brief C Tasks 4 and 6.
# If these ever need to change, they must change in BOTH places at once,
# or Brief A's models and this dataset drift apart silently.
# ======================================================================

def app_deviation_features(chars_per_sec, pasted, screens_visited, amount):
    typing_speed_deviation = (chars_per_sec - 4.0) / 1.0
    pasted_char_ratio = 0.9 if pasted else 0.05
    screen_sequence_anomaly = (MAX_SCREENS - screens_visited) / MAX_SCREENS
    amount_deviation = (amount - 15000) / (15000 * 2.06)
    return typing_speed_deviation, pasted_char_ratio, screen_sequence_anomaly, amount_deviation


def ussd_deviation_features(hour, retries, days_since_swap_bucket, amount):
    time_of_day_deviation = abs(hour - 14) / 12
    session_retry_deviation = retries / 2.0
    swap_map = {"OVER_30": 0.0, "15_30": 0.2, "5_14": 0.6, "0_4": 0.95}
    sim_swap_risk = swap_map[days_since_swap_bucket]
    amount_deviation = (amount - 4000) / (4000 * 0.98)
    return amount_deviation, time_of_day_deviation, session_retry_deviation, sim_swap_risk


# ======================================================================
# Raw session simulation (normal + legitimate anomalies + attackers)
# ======================================================================

def simulate_normal_app_session(user):
    """A session consistent with this user's own baseline."""
    chars_per_sec = max(0.3, random.gauss(user["typing_speed_baseline"], user["typing_speed_std"] * 0.25))
    pasted = random.random() < 0.03  # people occasionally paste account numbers legitimately
    screens_visited = max(1, min(MAX_SCREENS, round(random.gauss(user["screens_typically_visited"], 0.7))))
    amount = max(200, random.gauss(user["amount_baseline"], user["amount_std"] * 0.4))
    return chars_per_sec, pasted, screens_visited, amount


def simulate_legitimate_anomaly_app_session(user):
    """
    A REAL customer doing something genuinely unusual but honest: the
    hospital-bill transfer, the new-phone typing rhythm, the rushed transfer.
    Label = 0. These are the dataset's false-positive test cases — without
    them, you can't honestly claim to have tested for false positives at all.
    """
    scenario = random.choice(["large_amount", "unfamiliar_device_typing", "rushed"])
    if scenario == "large_amount":
        chars_per_sec, pasted, screens_visited, _ = simulate_normal_app_session(user)
        amount = user["amount_baseline"] * random.uniform(3.5, 6.0)  # big but real: hospital bill etc.
    elif scenario == "unfamiliar_device_typing":
        chars_per_sec = max(0.3, user["typing_speed_baseline"] * random.uniform(0.4, 0.7))  # new phone, fumbling
        pasted = False
        screens_visited = user["screens_typically_visited"]
        amount = max(200, random.gauss(user["amount_baseline"], user["amount_std"] * 0.4))
    else:  # rushed
        chars_per_sec = user["typing_speed_baseline"] * random.uniform(1.4, 1.8)  # fast but still human & real
        pasted = False
        screens_visited = max(1, user["screens_typically_visited"] - 2)  # skipped steps, in a hurry, still legit
        amount = max(200, random.gauss(user["amount_baseline"], user["amount_std"] * 0.4))
    return chars_per_sec, pasted, screens_visited, amount


def simulate_attacker_app_session(archetype):
    """Label = 1. Shape depends on archetype so the model learns distinct signatures, not one blob."""
    if archetype == "CREDENTIAL_STUFFING":
        return random.uniform(9, 15), True, 1, random.uniform(20000, 60000)
    elif archetype == "OTP_REPLAY":
        return random.uniform(4, 6), False, random.randint(3, 5), random.uniform(10000, 40000)
    elif archetype == "COACHED_VICTIM":
        # real user's own device/typing, but abnormal hesitation — modeled as unusually SLOW, not fast
        return random.uniform(0.8, 1.8), False, random.randint(2, 4), random.uniform(30000, 80000)
    elif archetype == "SLOW_DRIFT":
        return random.uniform(3.5, 5), False, random.randint(4, 6), random.uniform(14000, 19000)  # stays near-threshold
    else:  # SIM_SWAP_TAKEOVER / IMPOSSIBLE_TRAVEL — behaviourally near-normal, caught by OTHER modules (Division 5), not this model
        return random.uniform(3.5, 5.5), False, random.randint(4, 6), random.uniform(15000, 45000)


def simulate_normal_ussd_session(user):
    hour = int(np.clip(random.gauss((user["typical_hour_start"] + user["typical_hour_end"]) / 2, 2), 0, 23))
    retries = max(0, round(random.gauss(0.4, 0.5)))
    days_since_swap_bucket = np.random.choice(
        ["OVER_30", "15_30", "5_14", "0_4"], p=[0.90, 0.07, 0.02, 0.01]
    )
    amount = max(200, random.gauss(user["amount_baseline"], user["amount_std"] * 0.4))
    return hour, retries, days_since_swap_bucket, amount


def simulate_legitimate_anomaly_ussd_session(user):
    """Family-shared-phone / recent-legit-SIM-upgrade cases: label = 0 despite an odd-looking swap flag."""
    hour = int(np.clip(random.gauss(14, 5), 0, 23))
    retries = max(0, round(random.gauss(0.6, 0.6)))
    days_since_swap_bucket = "5_14"  # legit recent swap (lost phone, upgraded) — still label 0
    amount = max(200, random.gauss(user["amount_baseline"], user["amount_std"] * 0.4))
    return hour, retries, days_since_swap_bucket, amount


def simulate_attacker_ussd_session(archetype):
    if archetype == "SIM_SWAP_TAKEOVER":
        return random.choice([1, 2, 3]), random.randint(0, 2), "0_4", random.uniform(15000, 50000)
    elif archetype == "CREDENTIAL_STUFFING":
        return random.randint(0, 23), random.randint(4, 8), "OVER_30", random.uniform(5000, 15000)
    elif archetype == "SLOW_DRIFT":
        return int(np.clip(random.gauss(14, 3), 0, 23)), 0, "OVER_30", random.uniform(3800, 4300)
    else:
        return random.randint(0, 23), random.randint(1, 3), random.choice(["15_30", "5_14"]), random.uniform(8000, 30000)


# ======================================================================
# Main generation pass
# ======================================================================

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    app_rows = []
    ussd_rows = []

    print(f"Generating {N_USERS} synthetic users across {len(PERSONAS)} personas...")

    users = []
    for i in range(N_USERS):
        persona = PERSONAS[i % len(PERSONAS)]
        user = sample_user_from_persona(persona)
        user_id = str(uuid.uuid4())
        msisdn = f"080{random.randint(10000000, 99999999)}"
        full_name = f"Synthetic User {i+1}"
        user["id"] = user_id
        users.append(user)

        cur.execute(
            """INSERT INTO users (id, full_name, msisdn, persona_tag, preferred_channel,
               typical_hour_start, typical_hour_end, typical_amount_avg, typical_amount_stddev,
               account_created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (user_id, full_name, msisdn, user["persona_tag"], user["channel_pref"],
             user["typical_hour_start"], user["typical_hour_end"], user["amount_baseline"],
             user["amount_std"], datetime.utcnow() - timedelta(days=random.randint(30, 900)))
        )

        # telco_state — most users have stable pairing; a small handful get a
        # LEGITIMATE recent swap (family/lost-phone), separate from attacker rows below.
        legit_recent_swap = random.random() < 0.03
        cur.execute(
            """INSERT INTO telco_state (id, user_id, imei, sim_device_paired, last_sim_swap_at, cell_region)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (str(uuid.uuid4()), user_id, f"IMEI-{uuid.uuid4().hex[:14]}", True,
             datetime.utcnow() - timedelta(days=random.randint(1, 10) if legit_recent_swap else random.randint(60, 900)),
             random.choice(["Lagos-Mainland", "Lagos-Island", "Ibadan", "Abuja", "PortHarcourt"]))
        )

        # -------- APP-channel sessions for this user --------
        for _ in range(NORMAL_SESSIONS_PER_USER):
            is_anomaly = random.random() < LEGITIMATE_ANOMALY_RATE
            if is_anomaly:
                cps, pasted, screens, amount = simulate_legitimate_anomaly_app_session(user)
            else:
                cps, pasted, screens, amount = simulate_normal_app_session(user)
            feats = app_deviation_features(cps, pasted, screens, amount)
            app_rows.append({
                "user_id": user_id, "session_id": str(uuid.uuid4()),
                "typing_speed_deviation": feats[0], "pasted_char_ratio": feats[1],
                "screen_sequence_anomaly": feats[2], "amount_deviation": feats[3],
                "label": 0
            })

        # -------- USSD-channel sessions for this user --------
        for _ in range(NORMAL_SESSIONS_PER_USER):
            is_anomaly = random.random() < LEGITIMATE_ANOMALY_RATE
            if is_anomaly:
                hour, retries, swap_bucket, amount = simulate_legitimate_anomaly_ussd_session(user)
            else:
                hour, retries, swap_bucket, amount = simulate_normal_ussd_session(user)
            feats = ussd_deviation_features(hour, retries, swap_bucket, amount)
            ussd_rows.append({
                "user_id": user_id, "session_id": str(uuid.uuid4()),
                "amount_deviation": feats[0], "time_of_day_deviation": feats[1],
                "session_retry_deviation": feats[2], "sim_swap_risk": feats[3],
                "label": 0
            })

    conn.commit()

    # -------- Attacker sessions (label = 1), spread across archetypes --------
    print("Generating attacker sessions...")
    for _ in range(ATTACKER_SESSION_TOTAL_APP):
        archetype = random.choice(ATTACK_ARCHETYPES)
        cps, pasted, screens, amount = simulate_attacker_app_session(archetype)
        feats = app_deviation_features(cps, pasted, screens, amount)
        app_rows.append({
            "user_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()),
            "typing_speed_deviation": feats[0], "pasted_char_ratio": feats[1],
            "screen_sequence_anomaly": feats[2], "amount_deviation": feats[3],
            "label": 1
        })

    for _ in range(ATTACKER_SESSION_TOTAL_USSD):
        archetype = random.choice(ATTACK_ARCHETYPES)
        hour, retries, swap_bucket, amount = simulate_attacker_ussd_session(archetype)
        feats = ussd_deviation_features(hour, retries, swap_bucket, amount)
        ussd_rows.append({
            "user_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()),
            "amount_deviation": feats[0], "time_of_day_deviation": feats[1],
            "session_retry_deviation": feats[2], "sim_swap_risk": feats[3],
            "label": 1
        })

    # -------- Write flat CSVs for Brief A's model training --------
    app_df = pd.DataFrame(app_rows)
    ussd_df = pd.DataFrame(ussd_rows)

    os.makedirs("data", exist_ok=True)
    app_df.to_csv("data/app_channel_data.csv", index=False)
    ussd_df.to_csv("data/ussd_channel_data.csv", index=False)

    app_pos_rate = app_df["label"].mean() * 100
    ussd_pos_rate = ussd_df["label"].mean() * 100

    print(f"\napp_channel_data.csv: {len(app_df)} rows, {app_pos_rate:.2f}% positive (target ~4.8%)")
    print(f"ussd_channel_data.csv: {len(ussd_df)} rows, {ussd_pos_rate:.2f}% positive (target ~5.1%)")

    summary = {
        "n_users": N_USERS,
        "n_personas": len(PERSONAS),
        "app_rows": len(app_df),
        "app_positive_rate_pct": round(app_pos_rate, 2),
        "ussd_rows": len(ussd_df),
        "ussd_positive_rate_pct": round(ussd_pos_rate, 2),
        "attack_archetypes": ATTACK_ARCHETYPES,
        "legitimate_anomaly_rate": LEGITIMATE_ANOMALY_RATE,
        "generated_at": datetime.utcnow().isoformat(),
    }
    with open("data/generation_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    cur.close()
    conn.close()
    print("\nDone. See data/generation_summary.json and docs/DATA_GENERATION.md.")


if __name__ == "__main__":
    main()
