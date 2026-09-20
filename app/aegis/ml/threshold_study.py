"""
Division 4D — threshold tuning study.

Takes the XGBoost models already trained by train_models.py and, on the SAME
held-out 20% test split (same seed, same stratification — so this is exactly
the data train_models.py reported its 0.5 numbers on), sweeps the decision
threshold and records precision / recall / false-positive-rate at each point
for both channels.

Output:
  * ml/threshold_analysis.json  — machine-readable, incl. the chosen operating
    point and why
  * a printed tradeoff table

Run: python ml/threshold_study.py   (inside the backend container — it has the
     scientific stack; the host only has Python 3.14)
"""
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

APP_FEATURES = ["typing_speed_deviation", "pasted_char_ratio", "screen_sequence_anomaly", "amount_deviation"]
USSD_FEATURES = ["amount_deviation", "time_of_day_deviation", "session_retry_deviation", "sim_swap_risk"]

THRESHOLDS = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

# Per channel: the largest recall we can buy while keeping the false-positive
# rate under this budget. FPR is what a fraud team feels day to day (good
# customers challenged), so it's the constraint; recall is the objective.
FPR_BUDGET = 0.05


def sweep(csv_path, features, channel):
    df = pd.read_csv(csv_path)
    X, y = df[features], df["label"]
    _, X_test, _, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    model = joblib.load(f"ml/models/{channel}_xgb.pkl")
    proba = model.predict_proba(X_test)[:, 1]
    y_test = y_test.to_numpy()

    rows = []
    for t in THRESHOLDS:
        pred = (proba >= t).astype(int)
        tp = int(((pred == 1) & (y_test == 1)).sum())
        fp = int(((pred == 1) & (y_test == 0)).sum())
        fn = int(((pred == 0) & (y_test == 1)).sum())
        tn = int(((pred == 0) & (y_test == 0)).sum())
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        rows.append({
            "threshold": t,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "false_positive_rate": round(fpr, 4),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        })

    # Choose: best recall subject to FPR <= budget; tie-break on higher precision.
    eligible = [r for r in rows if r["false_positive_rate"] <= FPR_BUDGET]
    pool = eligible or rows
    chosen = sorted(pool, key=lambda r: (r["recall"], r["precision"]), reverse=True)[0]
    return rows, chosen


def print_table(channel, rows, chosen):
    print(f"\n{channel.upper()} channel  (held-out test set, n={rows[0]['tp']+rows[0]['fn']+rows[0]['fp']+rows[0]['tn']})")
    print(f"  {'thr':>4} | {'precision':>9} | {'recall':>7} | {'FPR':>6} | {'TP':>3} {'FP':>3} {'FN':>3} {'TN':>4}")
    print("  " + "-" * 58)
    for r in rows:
        mark = "  <-- chosen" if r["threshold"] == chosen["threshold"] else ""
        print(f"  {r['threshold']:>4} | {r['precision']:>9.4f} | {r['recall']:>7.4f} | "
              f"{r['false_positive_rate']:>6.4f} | {r['tp']:>3} {r['fp']:>3} {r['fn']:>3} {r['tn']:>4}{mark}")


if __name__ == "__main__":
    result = {"fpr_budget": FPR_BUDGET, "thresholds_swept": THRESHOLDS, "channels": {}}
    for channel, csv_path, feats in [
        ("app", "data/app_channel_data.csv", APP_FEATURES),
        ("ussd", "data/ussd_channel_data.csv", USSD_FEATURES),
    ]:
        rows, chosen = sweep(csv_path, feats, channel)
        print_table(channel, rows, chosen)
        result["channels"][channel] = {"sweep": rows, "chosen": chosen}

    result["rationale"] = (
        "Operating threshold per channel = highest recall whose false-positive "
        f"rate stays <= {FPR_BUDGET:.0%} on the held-out test split, tie-broken "
        "on precision. FPR is the constraint because every false positive is a "
        "good customer getting challenged; recall is the objective because a "
        "missed takeover is the expensive miss. The live scorer blends this "
        "XGBoost probability with the Isolation Forest anomaly score into a "
        "0-100 risk_score; these thresholds define where the supervised model "
        "alone would draw the line and are the reference point for the decision "
        "engine's 30/70 tier cuts."
    )

    with open("ml/threshold_analysis.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\nWrote ml/threshold_analysis.json")
    for ch, d in result["channels"].items():
        c = d["chosen"]
        print(f"  {ch}: threshold {c['threshold']}  (recall {c['recall']}, "
              f"precision {c['precision']}, FPR {c['false_positive_rate']})")
