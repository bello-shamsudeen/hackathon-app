"""
Division 4 — Scoring Service.
Loads the REAL trained models (Isolation Forest + XGBoost, both channels)
and produces output matching the SAME contract shape agreed with the
teammate's Model Agent brief — so either implementation is a drop-in
replacement for the other:

{"user_id": str, "channel": "app"|"ussd", "risk_score": float 0-100,
 "top_features": [[name, value], [name, value]], "session_count": int}
"""
import time
import joblib
import numpy as np

APP_FEATURES = ["typing_speed_deviation", "pasted_char_ratio", "screen_sequence_anomaly", "amount_deviation"]
USSD_FEATURES = ["amount_deviation", "time_of_day_deviation", "session_retry_deviation", "sim_swap_risk"]

_models_cache = {}


def _load(channel):
    if channel not in _models_cache:
        _models_cache[channel] = {
            "iso": joblib.load(f"ml/models/{channel}_isolation_forest.pkl"),
            "xgb": joblib.load(f"ml/models/{channel}_xgb.pkl"),
        }
    return _models_cache[channel]


def _score(channel: str, features: dict, feature_order: list, user_id: str, session_count: int) -> dict:
    start = time.perf_counter()
    models = _load(channel)
    X = np.array([[features[f] for f in feature_order]])

    xgb_proba = models["xgb"].predict_proba(X)[0][1]
    iso_anomaly = -models["iso"].score_samples(X)[0]

    # Blend: XGBoost carries most of the weight (it has labels), Isolation
    # Forest nudges the score for sessions that look statistically odd even
    # if XGBoost's supervised boundary doesn't flag them — this is the
    # "catches things we haven't seen labeled fraud for yet" contribution.
    blended = (0.75 * xgb_proba) + (0.25 * min(1.0, iso_anomaly / 0.5))
    risk_score = round(min(100.0, blended * 100), 2)

    importances = models["xgb"].feature_importances_
    weighted = [(feature_order[i], importances[i] * abs(features[feature_order[i]])) for i in range(len(feature_order))]
    weighted.sort(key=lambda x: x[1], reverse=True)
    top_features = [[name, round(features[name], 4)] for name, _ in weighted[:2]]

    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    return {
        "user_id": user_id,
        "channel": channel,
        "risk_score": risk_score,
        "top_features": top_features,
        "session_count": session_count,
        "_latency_ms": latency_ms,        # internal — surfaced in the UI (Division 9), not part of the external contract
        "_model_version": "aegis-v1",     # internal — displayed in the investigation console later
    }


def score_app_session(feature_dict: dict) -> dict:
    return _score("app", feature_dict, APP_FEATURES, feature_dict["user_id"], feature_dict.get("session_count", 1))


def score_ussd_session(feature_dict: dict) -> dict:
    return _score("ussd", feature_dict, USSD_FEATURES, feature_dict["user_id"], feature_dict.get("session_count", 1))
