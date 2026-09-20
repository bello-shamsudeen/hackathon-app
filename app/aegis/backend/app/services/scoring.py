"""
Division 4 — Scoring Service (ported from the team's models/ RandomForest
pipeline). Integration decision: aegis's own Isolation Forest + XGBoost
pipeline was never retrained on the first_action_deviation feature swap, so
the verified, tested models/ pipeline is used here instead of retraining
aegis's pipeline from scratch under deadline pressure.

Fixes applied during this port (not present in the original models/score.py):
  - session_count is no longer hardcoded to 10 — it now uses the real
    session_count passed in feature_dict by routers/score.py's score_session(),
    so the decision engine's cold-start guardrail can actually fire live.
  - Models and datasets are loaded ONCE and cached, not freshly on every
    call — the original per-call joblib.load() was costing ~3300-3400ms
    per request.
  - All paths are resolved relative to this file's own location, not to
    the process's working directory, so this works regardless of which
    directory uvicorn is launched from.
"""
import os
import joblib
import pandas as pd
import numpy as np

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", "..", "..", ".."))
_DATA_DIR = os.path.join(_REPO_ROOT, "data")
_MODEL_DIR = os.path.join(_REPO_ROOT, "models")

APP_FEATURES = ["typing_speed_deviation", "pasted_char_ratio", "first_action_deviation", "amount_deviation"]
USSD_FEATURES = ["amount_deviation", "time_of_day_deviation", "session_retry_deviation", "sim_swap_risk"]

_cache = {}


def _get_app_model():
    if "app_model" not in _cache:
        _cache["app_model"] = joblib.load(os.path.join(_MODEL_DIR, "app_model.pkl"))
    return _cache["app_model"]


def _get_ussd_model():
    if "ussd_model" not in _cache:
        _cache["ussd_model"] = joblib.load(os.path.join(_MODEL_DIR, "ussd_model.pkl"))
    return _cache["ussd_model"]


def _get_app_feature_scales():
    if "app_scales" not in _cache:
        df_app = pd.read_csv(os.path.join(_DATA_DIR, "app_channel_data.csv"))
        _cache["app_scales"] = df_app[APP_FEATURES].std().to_dict()
    return _cache["app_scales"]


def _get_ussd_feature_scales():
    if "ussd_scales" not in _cache:
        df_ussd = pd.read_csv(os.path.join(_DATA_DIR, "ussd_channel_data.csv"))
        _cache["ussd_scales"] = df_ussd[USSD_FEATURES].std().to_dict()
    return _cache["ussd_scales"]


def warm_models() -> None:
    """Pre-load both models + scaling factors at FastAPI startup — matches
    the warm_models() contract main.py's startup event already calls."""
    import logging
    log = logging.getLogger("aegis.scoring")
    try:
        _get_app_model()
        _get_app_feature_scales()
    except Exception as exc:  # noqa: BLE001
        log.warning("warm_models: app channel not loaded (%s) - rules fallback will engage", exc)
    try:
        _get_ussd_model()
        _get_ussd_feature_scales()
    except Exception as exc:  # noqa: BLE001
        log.warning("warm_models: ussd channel not loaded (%s) - rules fallback will engage", exc)


def score_app_session(feature_dict: dict) -> dict:
    model = _get_app_model()
    scales = _get_app_feature_scales()
    X = pd.DataFrame([feature_dict], columns=APP_FEATURES)
    prob = model.predict_proba(X)[0][1]
    risk_score = round(float(prob * 100), 2)
    importances = model.feature_importances_

    weighted_scores = []
    for i, feature_name in enumerate(APP_FEATURES):
        deviation = abs(feature_dict[feature_name])
        scale = scales[feature_name]
        norm_score = importances[i] * (deviation / scale) if scale > 0 else 0
        weighted_scores.append(norm_score)

    top_indices = np.argsort(weighted_scores)[-2:][::-1]
    top_features = [[APP_FEATURES[i], feature_dict[APP_FEATURES[i]]] for i in top_indices]

    return {
        "user_id": feature_dict["user_id"],
        "channel": "app",
        "risk_score": risk_score,
        "top_features": top_features,
        "session_count": feature_dict.get("session_count", 1),
        "_model_version": "models-rf-v1",
    }


def score_ussd_session(feature_dict: dict) -> dict:
    model = _get_ussd_model()
    scales = _get_ussd_feature_scales()
    X = pd.DataFrame([feature_dict], columns=USSD_FEATURES)
    prob = model.predict_proba(X)[0][1]
    risk_score = round(float(prob * 100), 2)
    importances = model.feature_importances_

    weighted_scores = []
    for i, feature_name in enumerate(USSD_FEATURES):
        deviation = abs(feature_dict[feature_name])
        scale = scales[feature_name]
        norm_score = importances[i] * (deviation / scale) if scale > 0 else 0
        weighted_scores.append(norm_score)

    top_indices = np.argsort(weighted_scores)[-2:][::-1]
    top_features = [[USSD_FEATURES[i], feature_dict[USSD_FEATURES[i]]] for i in top_indices]

    return {
        "user_id": feature_dict.get("user_id", "unknown"),
        "channel": "ussd",
        "risk_score": risk_score,
        "top_features": top_features,
        "session_count": feature_dict.get("session_count", 1),
        "_model_version": "models-rf-v1",
    }