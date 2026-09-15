# ELEVATION_THRESHOLDS: 95th percentile values computed from Task 2 data
ELEVATION_THRESHOLDS = {
    "app": {
        "typing_speed_deviation": 1.957880,
        "pasted_char_ratio": 0.703100,
        "first_action_deviation": 0.5,
        "amount_deviation": 1.276460
    },
    "ussd": {
        "amount_deviation": 4.214190,
        "time_of_day_deviation": 2.101655,
        "session_retry_deviation": 2.060035,
        "sim_swap_risk": 0.914600
    }
}


def make_decision(model_output: dict) -> dict:
    """
    Make a decision based on risk score and channel.

    Args:
        model_output (dict): Contains 'user_id', 'channel', 'risk_score',
            and 'top_features' keys.

    Returns:
        dict: Decision result with tier, action, message, user_id, and channel.
    """
    # Extract values from model_output
    user_id = model_output.get("user_id", "")
    channel = model_output.get("channel", "")
    risk_score = model_output.get("risk_score", 0)
    top_features = model_output.get("top_features", [])

    # 1. Base Tiering
    if risk_score < 30:
        tier = "low"
        action = "allow"
    elif 30 <= risk_score <= 70:
        tier = "medium"
        action = "step_up"
    else:
        tier = "high"
        action = "block"

    # Compute elevated_features: features whose absolute deviation exceeds ELEVATION_THRESHOLDS[channel]
    elevated_features = []
    if channel in ELEVATION_THRESHOLDS:
        # Normalize top_features to a list of (name, value) pairs
        if isinstance(top_features, dict):
            feature_pairs = list(top_features.items())
        else:
            feature_pairs = top_features  # list of [name, value] pairs

        for feature_name, value in feature_pairs:
            threshold = ELEVATION_THRESHOLDS[channel].get(feature_name)
            if threshold is not None and abs(value) > threshold:
                elevated_features.append(feature_name)

    # Guardrail 1: Elevation Override (sim_swap_risk)
    # If the ONLY elevated feature is "sim_swap_risk", override to low/allow
    if len(elevated_features) == 1 and elevated_features[0] == "sim_swap_risk":
        tier = "low"
        action = "allow"

    # Guardrail 2: Cold-start (session_count < 5)
    # If session_count < 5, tier can never be "high" — downgrade to "medium"
    session_count = model_output.get("session_count", 100)
    if session_count < 5 and tier == "high":
        tier = "medium"
        action = "step_up"

    # Guardrail 3: first_action_deviation-alone (App channel only)
    # If channel == "app" and ONLY elevated feature is "first_action_deviation"
    # and tier would be "high", downgrade to "medium"
    if channel == "app" and len(elevated_features) == 1 and elevated_features[0] == "first_action_deviation" and tier == "high":
        tier = "medium"
        action = "step_up"

    # Guardrail 4: typing_speed_deviation-alone (App channel only)
    # If channel == "app" and ONLY elevated feature is "typing_speed_deviation"
    # and tier would be "high", downgrade to "medium"
    # — protects against family member with different typing rhythm on shared account
    if channel == "app" and len(elevated_features) == 1 and elevated_features[0] == "typing_speed_deviation" and tier == "high":
        tier = "medium"
        action = "step_up"

    REASON_TEMPLATES = {
        "typing_speed_deviation": "you typed at an unusual speed for you",
        "pasted_char_ratio": "your details were pasted rather than typed",
        "first_action_deviation": "you went straight to a transfer without checking your balance first, which isn't your usual pattern",
        "amount_deviation": "this amount is unusual for you",
        "time_of_day_deviation": "this was sent at an unusual time for you",
        "session_retry_deviation": "there were more retries than usual",
        "sim_swap_risk": "your SIM was recently changed"
    }

    # Normalize top_features to a list of [name, value] pairs for consistent indexing
    if isinstance(top_features, dict):
        top_features = list(top_features.items())

    if tier == "low":
        message = "This transaction looks consistent with your normal activity."
    else:
        message = "This transaction was flagged because " + REASON_TEMPLATES[top_features[0][0]] + ", and " + REASON_TEMPLATES[top_features[1][0]] + "."

    return {
        "tier": tier,
        "action": action,
        "message": message,
        "user_id": user_id,
        "channel": channel,
    }


def decide_offline_fallback(transaction: dict) -> dict:
    """
    Fallback decision when the real model + decision engine pipeline is
    unreachable (e.g. a power outage or network outage).  This must NOT depend
    on any trained model — it only inspects the raw transaction fields.

    This intentionally mirrors the "blunt" large / first-time-transfer rule the
    hackathon brief itself describes as the inferior status quo — used here
    ONLY as a degraded-mode fallback when the primary ML pipeline is unavailable.

    Args:
        transaction (dict): Contains 'user_id', 'channel', 'amount'
            (in NGN) and 'is_first_time_recipient' (bool) keys.

    Returns:
        dict: Decision result with tier, action, message, user_id, and channel.
    """
    # No "high" tier in degraded mode — only medium (step-up) or low (allow).
    user_id = transaction.get("user_id", "")
    channel = transaction.get("channel", "")
    amount = transaction.get("amount", 0)
    is_first_time_recipient = transaction.get("is_first_time_recipient", False)

    if amount > 100000 or is_first_time_recipient is True:
        tier = "medium"
        action = "step_up"
    else:
        tier = "low"
        action = "allow"

    return {
        "tier": tier,
        "action": action,
        "message": "operating in offline/degraded mode — fallback rule (no model)",
        "user_id": user_id,
        "channel": channel,
    }


if __name__ == "__main__":
    # === Previous test cases (regression check) ===
    # Case 1: risk_score 15.0, app -> expect tier "low"
    case_1 = {"user_id": "app_test1", "channel": "app", "risk_score": 15.0,
              "top_features": [["typing_speed_deviation", 0.1], ["amount_deviation", 0.1]], "session_count": 40}
    result_1 = make_decision(case_1)
    print(result_1)

    # Case 2: risk_score 85.0, ussd, amount_deviation elevated -> expect tier "high"
    case_2 = {"user_id": "ussd_test2", "channel": "ussd", "risk_score": 85.0,
              "top_features": [["amount_deviation", 5.0], ["sim_swap_risk", 0.1]], "session_count": 40}
    result_2 = make_decision(case_2)
    print(result_2)

    # Case 3: risk_score 45.0, ussd, sim_swap_risk elevated -> expect tier "low"
    case_3 = {"user_id": "ussd_0002", "channel": "ussd", "risk_score": 45.0,
              "top_features": [["sim_swap_risk", 0.95], ["amount_deviation", 0.1]], "session_count": 30}
    result_3 = make_decision(case_3)
    print(result_3)

    # === New test cases for Guardrails 2 and 3 ===
    # Case 4: cold-start (session_count < 5, tier would be "high") -> expect tier "medium"
    case_4 = {"user_id": "ussd_0004", "channel": "ussd", "risk_score": 78.0,
              "top_features": [["amount_deviation", 5.0], ["sim_swap_risk", 0.9]], "session_count": 2}
    result_4 = make_decision(case_4)
    print(result_4)

    # Case 5: App first_action_deviation-alone (tier would be "high") -> expect tier "medium"
    case_5 = {"user_id": "app_0005", "channel": "app", "risk_score": 85.0,
              "top_features": [["first_action_deviation", 1.0], ["amount_deviation", 0.3]], "session_count": 25}
    result_5 = make_decision(case_5)
    print(result_5)

    # Case 6: TWO features elevated (guardrail must NOT suppress) -> expect tier "high"
    case_6 = {"user_id": "app_0006", "channel": "app", "risk_score": 85.0,
              "top_features": [["first_action_deviation", 1.0], ["pasted_char_ratio", 0.9]], "session_count": 25}
    result_6 = make_decision(case_6)
    print(result_6)

    # Case 7: App typing_speed_deviation-alone (tier would be "high") -> expect tier "medium"
    case_7 = {"user_id": "app_0006", "channel": "app", "risk_score": 85.0,
              "top_features": [["typing_speed_deviation", 3.5], ["amount_deviation", 0.3]], "session_count": 25}
    result_7 = make_decision(case_7)
    print(result_7)

    # Case 8: App typing_speed_deviation + pasted_char_ratio both elevated -> expect tier "high"
    case_8 = {"user_id": "app_0007", "channel": "app", "risk_score": 85.0,
              "top_features": [["typing_speed_deviation", 3.5], ["pasted_char_ratio", 0.9]], "session_count": 25}
    result_8 = make_decision(case_8)
    print(result_8)

        # === decide_offline_fallback test cases (operating in offline/degraded mode) ===
    # Case (a): small amount, not first-time → expect tier "low"
    case_a = {"user_id": "app_0008", "channel": "app", "amount": 5000, "is_first_time_recipient": False}
    result_a = decide_offline_fallback(case_a)
    print(result_a)

    # Case (b): large amount (> 100000 NGN), not first-time → expect tier "medium"
    case_b = {"user_id": "app_0009", "channel": "app", "amount": 250000, "is_first_time_recipient": False}
    result_b = decide_offline_fallback(case_b)
    print(result_b)

    # Case (c): small amount, first-time recipient → expect tier "medium"
    case_c = {"user_id": "app_0010", "channel": "app", "amount": 5000, "is_first_time_recipient": True}
    result_c = decide_offline_fallback(case_c)
    print(result_c)

    # Case (d): large amount AND first-time recipient → expect tier "medium" (both conditions)
    case_d = {"user_id": "app_0011", "channel": "app", "amount": 250000, "is_first_time_recipient": True}
    result_d = decide_offline_fallback(case_d)
    print(result_d)

