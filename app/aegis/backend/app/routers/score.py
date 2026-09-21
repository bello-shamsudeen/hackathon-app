"""
Division 4 - live scoring endpoint, with the Division 5 hard-control layer
running IN FRONT of it.

Flow per transaction:
  1. run_hard_controls() - deterministic checks (SIM-swap+device, fraud-ring
     correlation, OTP request-rate, call/OTP interlock, token replay).
  2. ML score - always computed (features + Redis velocity -> risk_score ->
     decision engine), with the 4E rules fallback if the model path fails.
  3. If a hard control fired, ITS verdict is final and the ML decision is kept
     only for audit/comparison. Otherwise the ML/rules decision stands.
"""
from fastapi import APIRouter, HTTPException
import logging
import time

from app.services import memory_store
from app.services.feature_engineering import (
    compute_app_features, compute_ussd_features, compute_velocity_features,
)
from app.services.scoring import score_app_session, score_ussd_session
from app.services.decision_engine import make_decision
from app.services.rules_fallback import rules_verdict
from app.services.hard_controls import run_hard_controls
from app.services import scoring_health
# Division 6 - real SHAP attribution + grounded explanations.
from app.services.explainability import compute_shap_reason_codes
from app.services.llm_explainer import deterministic_explanation
# Division 8E - hash-chained audit log: every decision write is appended.
from app.services.audit_chain import append_audit_row

log = logging.getLogger("aegis.score")

router = APIRouter(prefix="/score", tags=["scoring"])

# Decision verdicts are ALLOW / CHALLENGE / BLOCK. The decision engine and the
# hard controls both speak in tiers (low/medium/high) + actions
# (allow/step_up/block); map the action onto the stored verdict.
_ACTION_TO_VERDICT = {"allow": "ALLOW", "step_up": "CHALLENGE", "block": "BLOCK"}


@router.get("/health")
def scoring_mode():
    """Division 4E - current scoring mode ('ml' or 'degraded'). The frontend
    polls this to decide whether to show a degraded-mode banner (Division 9)."""
    return scoring_health.get_state()


def score_session(session_id: str, *, current_imei: str = None,
                  otp_being_entered: bool = False, call_active_hint: bool = False,
                  token_status: str = None, honeytoken_tripped: bool = False):
    start = time.perf_counter()

    session = memory_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    channel = session["channel"]
    user_id = session["user_id"]
    device_fingerprint = session.get("device_fingerprint")
    ip_address = session.get("ip_address")
    channel_label = "app" if channel == "WEB" else "ussd"

    session_count = memory_store.count_sessions_for_user(user_id)

    # Division 4B - rolling velocity counters for this user (read, not incremented).
    velocity_counts = compute_velocity_features(user_id)

    # Most recent transaction on this session - for the decisions link, the
    # rules fallback amount, and nothing else.
    tx = memory_store.get_transaction_for_session(session_id)
    transaction_id = tx["id"] if tx else None
    tx_amount = float(tx["amount"]) if tx else 0.0

    # Effective device identity: caller-supplied IMEI wins; otherwise derive one
    # from the session's device fingerprint (Step 3 of the Division 5 brief).
    if not current_imei and device_fingerprint:
        current_imei = f"imei::{device_fingerprint}"

    # Effective call state: explicit hint OR any CALL_STATE telemetry on the session.
    session_events = memory_store.get_behavioral_events_for_session(session_id)
    db_call = any(e.get("call_active") for e in session_events)
    effective_call_active = bool(call_active_hint) or bool(db_call)

    # ---- 1. HARD CONTROLS (deterministic, run first) ----
    hard_control = {"override": False}
    try:
        hard_control = run_hard_controls(
            session_id=str(session_id), user_id=str(user_id),
            device_fingerprint=device_fingerprint, ip_address=ip_address,
            current_imei=current_imei, call_active=effective_call_active,
            otp_being_entered=bool(otp_being_entered),
            token_status=token_status, honeytoken_tripped=bool(honeytoken_tripped),
        )
    except Exception as exc:  # noqa: BLE001 - a hard-control bug must not 500 a transfer
        log.warning("hard controls errored (%s: %s) - proceeding on ML score only",
                    type(exc).__name__, exc)
        hard_control = {"override": False, "error": f"{type(exc).__name__}: {exc}"}

    # ---- 2. ML score (ALWAYS computed, even when a hard control overrides) ----
    threshold_meta = None
    try:
        if channel == "WEB":
            features = compute_app_features(session_id)
        else:
            features = compute_ussd_features(session_id)
        features["user_id"] = str(user_id)
        features["session_count"] = session_count
        features["velocity"] = velocity_counts
        model_output = (score_app_session if channel == "WEB" else score_ussd_session)(features)

        ml_decision = make_decision(model_output)
        ml_risk = model_output["risk_score"]
        ml_top = model_output["top_features"]
        ml_model_version = model_output.get("_model_version", "aegis-v1")
        scoring_mode_used = "ml"
        threshold_meta = {
            "xgb_proba": model_output.get("_xgb_proba"),
            "threshold": model_output.get("_threshold"),
            "threshold_crossed": model_output.get("_threshold_crossed"),
        }
        scoring_health.mark_ml()

        # Division 6A - REAL per-prediction SHAP attribution (replaces the old
        # feature_importances proxy). If SHAP itself fails, degrade to the
        # importance-ranked top_features rather than losing the decision.
        try:
            reason_codes = compute_shap_reason_codes(channel_label, features, top_n=3)
        except Exception as exc:  # noqa: BLE001
            log.warning("SHAP attribution failed (%s: %s) - using importance top_features",
                        type(exc).__name__, exc)
            reason_codes = [
                {"feature": n, "value": round(float(v), 4), "shap_contribution": None}
                for n, v in ml_top
            ]
    except Exception as exc:  # noqa: BLE001 - any ML-path failure -> rules fallback
        log.warning("ML scoring failed (%s: %s) - engaging rules fallback",
                    type(exc).__name__, exc)
        scoring_health.mark_degraded(f"{type(exc).__name__}: {exc}")
        fb = rules_verdict(str(user_id), channel_label, tx_amount)
        ml_decision = fb
        ml_risk = fb["risk_score"]
        ml_top = fb["top_features"]
        ml_model_version = fb["_model_version"]
        scoring_mode_used = "degraded"
        reason_codes = [
            {"feature": n, "value": round(float(v), 4), "shap_contribution": None}
            for n, v in ml_top
        ]

    # ---- 3. Final decision: hard control wins if it fired ----
    if hard_control.get("override"):
        final_source = "hard_control"
        tier = hard_control["tier"]
        action = hard_control["action"]
        message = hard_control["message"]
        triggered_rules = [hard_control["source"]]
    else:
        final_source = "rules_fallback" if scoring_mode_used == "degraded" else "ml"
        tier = ml_decision["tier"]
        action = ml_decision["action"]
        message = ml_decision["message"]
        triggered_rules = None

    # ---- Division 6 - grounded explanations ----
    # SHAP-grounded, ZERO-latency sentences are written to the row NOW. An
    # inline LLM round-trip costs 15-30s, which the transfer path can't
    # absorb - the LLM *rewrite* of these same reason codes used to be an
    # on-demand /explain step; that endpoint has been removed, so the
    # frontend uses this deterministic message directly.
    explain_tier = tier if final_source != "hard_control" else "high"
    det_customer = deterministic_explanation(reason_codes, explain_tier, "customer")
    det_analyst = deterministic_explanation(reason_codes, explain_tier, "analyst")

    if hard_control.get("override"):
        explanation_customer = message  # deterministic hard-control reason stays
        explanation_analyst = (
            f"HARD CONTROL {hard_control['source']} overrode the ML decision "
            f"(ml_tier={ml_decision['tier']}, ml_risk={ml_risk}, ml_mode={scoring_mode_used}). "
            f"ML attribution: {det_analyst}"
        )
    else:
        explanation_customer = det_customer
        explanation_analyst = det_analyst
        message = explanation_customer  # customer-facing string in the response

    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    verdict = _ACTION_TO_VERDICT.get(action, "CHALLENGE")

    contribution_record = {
        "final_source": final_source,
        "mode": scoring_mode_used,
        "hard_control": {k: v for k, v in hard_control.items() if k != "error"},
        "ml": {
            "tier": ml_decision["tier"],
            "action": ml_decision["action"],
            "risk_score": ml_risk,
            "top_features": {name: value for name, value in ml_top},
        },
        "shap_reason_codes": reason_codes,
        "velocity": velocity_counts,
    }
    if threshold_meta is not None:
        contribution_record["threshold"] = threshold_meta

    # risk_score stored is ALWAYS the model's number - a hard-control override
    # changes the verdict, not the recorded ML score (audit/comparison).
    decision_id = memory_store.log_decision(
        session_id=session_id, transaction_id=transaction_id, risk_score=ml_risk,
        verdict=verdict, triggered_rules=triggered_rules,
        feature_contributions=contribution_record, explanation_customer=message,
        explanation_analyst=explanation_analyst, model_version=ml_model_version,
        latency_ms=latency_ms,
    )

    # Division 8E - append this decision to the hash chain.
    append_audit_row(str(decision_id), {
        "decision_id": str(decision_id),
        "transaction_id": str(transaction_id) if transaction_id else None,
        "session_id": str(session_id),
        "risk_score": str(ml_risk),
        "verdict": verdict,
        "final_source": final_source,
        "triggered_rules": ",".join(triggered_rules) if triggered_rules else "",
        "model_version": ml_model_version,
        "latency_ms": str(latency_ms),
        "explanation_customer": message,
    })

    resp = {
        "tier": tier,
        "action": action,
        "message": message,
        "user_id": str(user_id),
        "channel": channel_label,
        "final_source": final_source,
        "risk_score": ml_risk,
        # Division 6A - top_features is the real SHAP ranking.
        "top_features": [[rc["feature"], rc["value"]] for rc in reason_codes],
        "shap_reason_codes": reason_codes,
        "explanations": {
            "customer": {"text": explanation_customer, "source": "deterministic"},
            "analyst": {"text": explanation_analyst, "source": "deterministic"},
        },
        "hard_control": hard_control,
        "velocity": velocity_counts,
        "scoring_mode": scoring_mode_used,
        "latency_ms": latency_ms,
    }
    if threshold_meta is not None:
        resp["threshold"] = threshold_meta
    return resp


@router.post("/session/{session_id}")
def score_session_endpoint(session_id: str):
    return score_session(session_id)

# Division 4E console - direct, read-only access to the rules-based fallback
# engine so the offline safety net can be exercised on demand. Same verdict
# contract as the automatic path; nothing is written to the decisions table.
@router.get("/manual")
def manual_engine(amount: float, channel: str = "app"):
    if channel not in ("app", "ussd"):
        raise HTTPException(status_code=400, detail="channel must be 'app' or 'ussd'")
    return rules_verdict("manual-console", channel, amount)


# Division 4E engine status - read-only probe of the primary RandomForest
# model path (Brief A: models/app_model.pkl + models/ussd_model.pkl) so the
# frontend can show whether the rules fallback (Brief B Rule 6 - offline/
# degraded mode) is ACTIVELY serving or armed standby. The verdict combines:
#   (a) model-file health - the RF pickles exist and are loadable, and
#   (b) live scoring_health state - "degraded" if the ML path recently failed.
# Read-only: nothing is scored and nothing is written, same as /manual.
@router.get("/engine-status")
def engine_status():
    from pathlib import Path
    here = Path(__file__).resolve()
    models_dir = None
    for parent in here.parents:
        candidate = parent / "models"
        if (candidate / "app_model.pkl").exists() or (candidate / "ussd_model.pkl").exists():
            models_dir = candidate
            break

    model_files = {}
    model_files_ok = True
    for name in ("app_model.pkl", "ussd_model.pkl"):
        path = (models_dir / name) if models_dir else None
        status = "missing"
        if path is not None and path.exists():
            try:
                import joblib
                joblib.load(path)
                status = "ok"
            except Exception as exc:  # noqa: BLE001 - corrupt/unloadable pickle
                status = f"corrupt: {type(exc).__name__}"
        model_files[name] = status
        if status != "ok":
            model_files_ok = False

    health = scoring_health.get_state()
    degraded = isinstance(health, dict) and health.get("mode") == "degraded"

    return {
        "primary_model": "random_forest",
        "fallback_engine": "rules_fallback (Brief B Rule 6)",
        "model_files_ok": model_files_ok,
        "model_files": model_files,
        "scoring_health": health,
        "fallback_active": (not model_files_ok) or degraded,
    }
