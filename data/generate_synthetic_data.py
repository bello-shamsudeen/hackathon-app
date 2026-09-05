"""
Synthetic Data Generator — Account Takeover Detection (App + USSD channels)
=============================================================================

Calibrated against real published statistics from two public datasets:

1. PaySim (mobile money transaction simulator, based on a real African
   mobile money service):
     - Overall fraud rate: 0.129%
     - Fraud concentrated in TRANSFER (0.77%) and CASH_OUT (0.18%) types
     - Fraudulent amounts average ~8.2x higher than genuine amounts
     - TRANSFER amounts: mean 910,647 / std 1,879,574 (CV ~2.06, heavy tail)
     - PAYMENT/CASH_OUT amounts: CV ~0.96-1.0 (less skewed, everyday txns)

2. CMU Keystroke Dynamics Benchmark (51 subjects, 20,400 samples):
     - Mean dwell (hold) time: 0.0901s, std 0.0305s
     - Mean flight (UD) time: 0.1589s, std 0.2217s
     - Within-subject std: 0.0161  (a person's own session-to-session noise)
     - Between-subject std: 0.0236 (how much people differ from each other)
   Between-subject variance exceeding within-subject variance is exactly
   the statistical premise that makes "deviation from personal baseline"
   a viable global feature: people are more consistent with themselves
   than they are similar to each other.

IMPORTANT SCOPING NOTE (stated honestly, for the write-up):
PaySim's true fraud rate (~0.13%) is too extreme to yield enough positive
examples in a 5,000-10,000 row synthetic set for meaningful train/test
evaluation. We deliberately oversample fraud to 5% of sessions. This is a
scoping decision for prototype training/evaluation purposes, not a claim
about real-world fraud prevalence, and is disclosed as such.

Edge cases (SIM swap, shared phones) are deliberately NOT treated as
fraud signals on their own. They are injected into the NORMAL class at
realistic rates, and only co-occur with elevated risk in the ATTACKER
class alongside other deviations - this is what teaches the model (and
the decision-engine guardrail) that identity-change signals are
necessary-but-not-sufficient for escalation.
"""

import numpy as np
import pandas as pd
import os

# Helper to build paths correctly
def get_data_path(filename):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

RNG = np.random.default_rng(42)


# ----------------------------------------------------------------------------
# CALIBRATION CONSTANTS (sourced from the real dataset summaries above)
# ----------------------------------------------------------------------------

# --- CMU keystroke calibration ---
CMU_DWELL_MEAN = 0.0901
CMU_FLIGHT_MEAN = 0.1589
CMU_CHAR_TIME_MEAN = CMU_DWELL_MEAN + CMU_FLIGHT_MEAN   # ~0.249s per char
CMU_BETWEEN_SUBJECT_STD = 0.0236   # how baselines differ across people
CMU_WITHIN_SUBJECT_STD = 0.0161    # how noisy one person's own sessions are

# --- PaySim amount calibration (rescaled to a plausible Naira-context range
#     for demo readability, while PRESERVING the real coefficient of variation) ---
APP_AMOUNT_MEAN = 15000       # NGN, typical app transfer
APP_AMOUNT_CV = 2.06          # from PaySim TRANSFER (mean 910647, std 1879574)

USSD_AMOUNT_MEAN = 4000       # NGN, typical USSD/everyday transaction
USSD_AMOUNT_CV = 0.98         # from PaySim CASH_OUT/PAYMENT

FRAUD_AMOUNT_MULTIPLIER_MEAN = 8.2   # from PaySim: fraud amounts avg ~8.2x normal

FRAUD_RATE = 0.05   # oversampled from real ~0.13-0.77% -- see scoping note above

N_APP_USERS = 450
N_USSD_USERS = 450
N_APP_SESSIONS = 10000
N_USSD_SESSIONS = 10000

SHARED_PHONE_FRACTION = 0.20     # fraction of app accounts used by 2+ people
RECENT_SWAP_NORMAL_FRACTION = 0.15  # fraction of USSD accounts with a
                                     # legitimate recent SIM swap


def lognormal_params(mean, cv):
    """Convert a desired (mean, coefficient-of-variation) into the
    underlying normal-distribution parameters for np.random.lognormal."""
    sigma2 = np.log(1 + cv ** 2)
    mu = np.log(mean) - sigma2 / 2
    return mu, np.sqrt(sigma2)


# ----------------------------------------------------------------------------
# APP CHANNEL
# ----------------------------------------------------------------------------

APP_SCREENS = ["login", "dashboard", "beneficiary_select",
               "amount_entry", "review", "confirm"]


def build_app_users(n_users):
    users = []
    for i in range(n_users):
        shared = RNG.random() < SHARED_PHONE_FRACTION

        # personal typing baseline, drawn around the real CMU population mean
        base_char_time = RNG.normal(CMU_CHAR_TIME_MEAN, CMU_BETWEEN_SUBJECT_STD)
        base_char_time = max(base_char_time, 0.05)  # floor, avoid nonsense values

        if shared:
            # a second co-user with a distinctly different typing rhythm
            second_char_time = RNG.normal(CMU_CHAR_TIME_MEAN, CMU_BETWEEN_SUBJECT_STD)
            second_char_time = max(second_char_time, 0.05)
            within_std = CMU_WITHIN_SUBJECT_STD * 2.2  # wider natural envelope
        else:
            second_char_time = base_char_time
            within_std = CMU_WITHIN_SUBJECT_STD

        # personal amount baseline (log-normal, shape calibrated from PaySim)
        personal_mean = RNG.lognormal(*lognormal_params(APP_AMOUNT_MEAN, 0.6))
        mu, sigma = lognormal_params(personal_mean, APP_AMOUNT_CV)

        users.append({
            "user_id": f"app_{i:04d}",
            "shared_phone": shared,
            "base_char_time": base_char_time,
            "second_char_time": second_char_time,
            "within_std": within_std,
            "amount_mu": mu,
            "amount_sigma": sigma,
            "amount_mean": personal_mean,
        })
    return pd.DataFrame(users)


def screen_missing_fraction(sequence):
    visited = set(sequence)
    missing = [s for s in APP_SCREENS if s not in visited]
    return len(missing) / len(APP_SCREENS)


def generate_app_sessions(users_df, n_sessions):
    rows = []
    user_ids = users_df["user_id"].values

    for _ in range(n_sessions):
        u = users_df[users_df["user_id"] == RNG.choice(user_ids)].iloc[0]
        is_fraud = RNG.random() < FRAUD_RATE

        # --- typing speed ---
        if u["shared_phone"] and RNG.random() < 0.5:
            personal_baseline = u["second_char_time"]
        else:
            personal_baseline = u["base_char_time"]

        if is_fraud:
            # bimodal: either bot-fast (paste/script) or unfamiliar-slow
            if RNG.random() < 0.7:
                multiplier = RNG.uniform(0.15, 0.45)   # much faster than normal
            else:
                multiplier = RNG.uniform(1.8, 3.0)     # much slower / hesitant
            observed_time = personal_baseline * multiplier
        else:
            observed_time = personal_baseline + RNG.normal(0, u["within_std"])
            observed_time = max(observed_time, 0.03)

        typing_speed_deviation = (observed_time - personal_baseline) / u["within_std"]

        # --- paste ratio ---
        if is_fraud:
            if RNG.random() < 0.65: # Changed from 0.8 to 0.65 (0.35 mimic-rate)
                pasted_char_ratio = RNG.beta(6, 3)   # typical rushed attacker
            else:
                pasted_char_ratio = RNG.beta(1, 10)  # careful attacker, mimics normal
        else:
            if RNG.random() < 0.8:  # Changed from 0.9 to 0.8 (0.2 mimic-rate)
                pasted_char_ratio = RNG.beta(1, 15)  # typical normal user
            else:
                pasted_char_ratio = RNG.beta(3, 3)   # normal user, password manager/autofill

        # --- screen sequence ---
        if is_fraud:
            r = RNG.random()
            if r < 0.25:
                n_skip = 0   # careful attacker navigates full flow to blend in
            elif r < 0.45:
                n_skip = 1
            else:
                n_skip = RNG.integers(2, 5)
        else:
            r = RNG.random()
            if r < 0.60: # (Proportional decrease: 0.75 -> 0.60)
                n_skip = 0
            elif r < 0.80: # (Proportional decrease: 0.95 -> 0.80)
                n_skip = 1
            else:
                n_skip = 2   # occasional distracted/confused normal user

        if n_skip == 0:
            visited = APP_SCREENS[:]
        elif n_skip == 1:
            visited = [s for s in APP_SCREENS if s != "review"]
        else:
            visited = list(RNG.choice(APP_SCREENS, size=len(APP_SCREENS) - n_skip, replace=False))
        screen_sequence_anomaly = screen_missing_fraction(visited)

        # --- amount ---
        if is_fraud:
            mult = RNG.lognormal(np.log(FRAUD_AMOUNT_MULTIPLIER_MEAN), 0.5)
            amount = u["amount_mean"] * mult
        else:
            amount = RNG.lognormal(u["amount_mu"], u["amount_sigma"])
        amount_deviation = (amount - u["amount_mean"]) / (u["amount_mean"] * APP_AMOUNT_CV)

        rows.append({
            "user_id": u["user_id"],
            "typing_speed_deviation": round(typing_speed_deviation, 4),
            "pasted_char_ratio": round(pasted_char_ratio, 4),
            "screen_sequence_anomaly": round(screen_sequence_anomaly, 4),
            "amount_deviation": round(amount_deviation, 4),
            "label": int(is_fraud),
        })

    df = pd.DataFrame(rows)
    df.insert(1, "session_id", [f"app_s{i:06d}" for i in range(len(df))])
    return df


# ----------------------------------------------------------------------------
# USSD CHANNEL
# ----------------------------------------------------------------------------

def build_ussd_users(n_users):
    users = []
    for i in range(n_users):
        personal_mean = RNG.lognormal(*lognormal_params(USSD_AMOUNT_MEAN, 0.6))
        mu, sigma = lognormal_params(personal_mean, USSD_AMOUNT_CV)

        preferred_hour = RNG.uniform(0, 24)
        hour_std = RNG.uniform(1.5, 4.0)   # how tightly clustered their usual hours are

        mean_retries = RNG.gamma(1.2, 0.3)  # most people rarely retry

        recent_swap_normal = RNG.random() < RECENT_SWAP_NORMAL_FRACTION
        days_since_swap = (RNG.uniform(0, 15) if recent_swap_normal
                            else RNG.exponential(180))

        users.append({
            "user_id": f"ussd_{i:04d}",
            "amount_mu": mu,
            "amount_sigma": sigma,
            "amount_mean": personal_mean,
            "preferred_hour": preferred_hour,
            "hour_std": hour_std,
            "mean_retries": mean_retries,
            "days_since_swap": days_since_swap,
        })
    return pd.DataFrame(users)


def circular_hour_diff(h1, h2):
    diff = abs(h1 - h2) % 24
    return min(diff, 24 - diff)


def swap_risk_from_days(days):
    return float(np.clip(1 - days / 30, 0, 1))


def generate_ussd_sessions(users_df, n_sessions):
    rows = []
    user_ids = users_df["user_id"].values

    for _ in range(n_sessions):
        u = users_df[users_df["user_id"] == RNG.choice(user_ids)].iloc[0]
        is_fraud = RNG.random() < FRAUD_RATE

        # --- amount ---
        if is_fraud:
            mult = RNG.lognormal(np.log(FRAUD_AMOUNT_MULTIPLIER_MEAN), 0.5)
            amount = u["amount_mean"] * mult
        else:
            amount = RNG.lognormal(u["amount_mu"], u["amount_sigma"])
        amount_deviation = (amount - u["amount_mean"]) / (u["amount_mean"] * USSD_AMOUNT_CV)

        # --- time of day ---
        if is_fraud and RNG.random() < 0.65:
            session_hour = RNG.uniform(0, 24)   # off-hour / random
        else:
            session_hour = (u["preferred_hour"] + RNG.normal(0, u["hour_std"])) % 24
        time_of_day_deviation = circular_hour_diff(session_hour, u["preferred_hour"]) / u["hour_std"]

        # --- retries ---
        if is_fraud:
            retries = RNG.poisson(u["mean_retries"] + RNG.uniform(2, 5))
        else:
            retries = RNG.poisson(u["mean_retries"])
        session_retry_deviation = (retries - u["mean_retries"]) / (u["mean_retries"] + 0.5)

        # --- SIM swap risk ---
        # Attackers co-occur a recent swap with other elevated signals ~60% of
        # the time; the remaining 40% use a non-swap vector (e.g. phishing).
        if is_fraud and RNG.random() < 0.6:
            days_since_swap = RNG.uniform(0, 10)
        else:
            days_since_swap = u["days_since_swap"]
        sim_swap_risk = swap_risk_from_days(days_since_swap)

        rows.append({
            "user_id": u["user_id"],
            "amount_deviation": round(amount_deviation, 4),
            "time_of_day_deviation": round(time_of_day_deviation, 4),
            "session_retry_deviation": round(session_retry_deviation, 4),
            "sim_swap_risk": round(sim_swap_risk, 4),
            "label": int(is_fraud),
        })

    df = pd.DataFrame(rows)
    df.insert(1, "session_id", [f"ussd_s{i:06d}" for i in range(len(df))])
    return df


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    print("Building App channel users and sessions...")
    app_users = build_app_users(N_APP_USERS)
    app_sessions = generate_app_sessions(app_users, N_APP_SESSIONS)

    print("Building USSD channel users and sessions...")
    ussd_users = build_ussd_users(N_USSD_USERS)
    ussd_sessions = generate_ussd_sessions(ussd_users, N_USSD_SESSIONS)

    app_sessions.to_csv(get_data_path("app_channel_data.csv"), index=False)
    ussd_sessions.to_csv(get_data_path("ussd_channel_data.csv"), index=False)

    print("\n" + "=" * 60)
    print("APP CHANNEL SUMMARY")
    print("=" * 60)
    print(f"Rows: {len(app_sessions)}   Fraud rate: {app_sessions['label'].mean():.3f}")
    print(app_sessions.groupby("label")[
        ["typing_speed_deviation", "pasted_char_ratio",
         "screen_sequence_anomaly", "amount_deviation"]].mean())

    print("\n" + "=" * 60)
    print("USSD CHANNEL SUMMARY")
    print("=" * 60)
    print(f"Rows: {len(ussd_sessions)}   Fraud rate: {ussd_sessions['label'].mean():.3f}")
    print(ussd_sessions.groupby("label")[
        ["amount_deviation", "time_of_day_deviation",
         "session_retry_deviation", "sim_swap_risk"]].mean())

    print("\nSaved: app_channel_data.csv, ussd_channel_data.csv")
