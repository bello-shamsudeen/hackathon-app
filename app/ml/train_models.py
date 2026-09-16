"""
Division 4 — model training.
Trains BOTH an unsupervised Isolation Forest and a supervised XGBoost
classifier per channel, per the original Build Plan (Division 4C):
Isolation Forest learns "normal" without needing labeled fraud (matches
"real fraud examples are rare and arrive late"); XGBoost sharpens scoring
using the labels we DO have from Division 3's synthetic data.

Run: python ml/train_models.py
Outputs: ml/models/{app,ussd}_isolation_forest.pkl, {app,ussd}_xgb.pkl,
         ml/models/{app,ussd}_metrics.json
"""
import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, confusion_matrix, precision_score,
    recall_score, roc_auc_score, average_precision_score
)
from xgboost import XGBClassifier

os.makedirs("ml/models", exist_ok=True)

APP_FEATURES = ["typing_speed_deviation", "pasted_char_ratio", "screen_sequence_anomaly", "amount_deviation"]
USSD_FEATURES = ["amount_deviation", "time_of_day_deviation", "session_retry_deviation", "sim_swap_risk"]


def train_channel(csv_path, features, channel_name):
    print(f"\n{'='*60}\nTraining {channel_name} channel\n{'='*60}")
    df = pd.read_csv(csv_path)
    X = df[features]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    # --- Isolation Forest: unsupervised, trained ONLY on normal (label=0) rows ---
    # This is the point of using it — it never needs fraud labels to learn what's normal.
    iso = IsolationForest(contamination=0.05, random_state=42)
    iso.fit(X_train[y_train == 0])
    iso_scores_test = -iso.score_samples(X_test)  # higher = more anomalous
    joblib.dump(iso, f"ml/models/{channel_name}_isolation_forest.pkl")

    # --- XGBoost: supervised, sharpens scoring using the labels we do have ---
    xgb = XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.1,
        scale_pos_weight=(y_train == 0).sum() / max((y_train == 1).sum(), 1),
        random_state=42, eval_metric="logloss"
    )
    xgb.fit(X_train, y_train)
    joblib.dump(xgb, f"ml/models/{channel_name}_xgb.pkl")

    y_pred_proba = xgb.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    print("XGBoost classification report:")
    print(classification_report(y_test, y_pred))
    cm = confusion_matrix(y_test, y_pred)
    print("Confusion matrix:\n", cm)

    tn, fp, fn, tp = cm.ravel()
    metrics = {
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "false_positive_rate": round(fp / (fp + tn), 4) if (fp + tn) > 0 else 0.0,
        "pr_auc": round(average_precision_score(y_test, y_pred_proba), 4),
        "roc_auc": round(roc_auc_score(y_test, y_pred_proba), 4),
        "threshold_used": 0.5,
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
        "isolation_forest_mean_anomaly_score": round(float(np.mean(iso_scores_test)), 4),
    }
    with open(f"ml/models/{channel_name}_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\n{channel_name} metrics written:", json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    app_metrics = train_channel("data/app_channel_data.csv", APP_FEATURES, "app")
    ussd_metrics = train_channel("data/ussd_channel_data.csv", USSD_FEATURES, "ussd")
    print("\nDone. Both models + metrics saved to ml/models/.")
