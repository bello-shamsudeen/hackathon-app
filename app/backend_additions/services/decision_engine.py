"""
Division 4/5 — Decision Engine.
Base ALLOW/CHALLENGE/BLOCK tiering, PLUS both guardrails from the teammate's
Brief B, implemented here directly using OUR OWN scoring output. We do not
wait for their decision_engine.py to arrive — the guardrail LOGIC is
independent of whose model produced the risk score, so we build it now
(per the integration decision already agreed and saved).

Guardrail 1 — SIM-swap alone must not escalate risk (families share phones,
              people change SIMs — neither is fraud on its own).
Guardrail 2 — Cold-start cap: a new customer's first sessions can never be
              auto-blocked outright, only stepped-up, since we don't have
              enough history to judge deviation reliably yet.

If/when the teammate's real decision_engine.py arrives, compare it against
this one and merge — don't blindly replace either.
"""

REASON_TEMPLATES = {
    "typing_speed_deviation": "you typed at an unusual speed for you",
    "pasted_char_ratio": "your details were pasted rather than typed",
    "screen_sequence_anomaly": "you skipped steps you normally go through",
    "amount_deviation": "this amount is unusual for you",
    "time_of_day_deviation": "this was sent at an unusual time for you",
    "session_retry_deviation": "there were more retries than usual",
    "sim_swap_risk": "your SIM was recently changed",
}


def make_decision(model_output: dict) -> dict:
    risk_score = model_output["risk_score"]
    top_features = model_output["top_features"]
    session_count = model_output.get("session_count", 10)

    # ---- Base tiering ----
    if risk_score < 30:
        tier, action = "low", "allow"
    elif risk_score <= 70:
        tier, action = "medium", "step_up"
    else:
        tier, action = "high", "block"

    # ---- Guardrail 1: SIM-swap alone must not escalate ----
    elevated = [f for f in top_features if abs(f[1]) > 0.7]
    if len(elevated) == 1 and elevated[0][0] == "sim_swap_risk":
        tier, action = "low", "allow"

    # ---- Guardrail 2: cold-start cap ----
    if session_count < 5 and tier == "high":
        tier, action = "medium", "step_up"

    # ---- Message ----
    if tier == "low":
        message = "This transaction looks consistent with your normal activity."
    else:
        reason_a = REASON_TEMPLATES.get(top_features[0][0], "unusual activity was detected")
        reason_b = REASON_TEMPLATES.get(top_features[1][0], "additional unusual activity was detected")
        message = f"This transaction was flagged because {reason_a}, and {reason_b}."

    return {
        "tier": tier,
        "action": action,
        "message": message,
        "user_id": model_output["user_id"],
        "channel": model_output["channel"],
    }
