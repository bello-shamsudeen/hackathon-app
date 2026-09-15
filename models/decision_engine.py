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

    return {
        "tier": tier,
        "action": action,
        "message": "placeholder",
        "user_id": user_id,
        "channel": channel,
    }


def decide_offline_fallback(session_data: dict) -> dict:
    """
    Fallback decision when the model/scoring service is unreachable.
    Uses the brief's described "blunt" legacy rule — no model calls,
    no ELEVATION_THRESHOLDS.

    Args:
        session_data (dict): Contains 'amount', 'is_first_time_recipient',
            'local_recent_session_count', and 'channel' keys.

    Returns:
        dict: Decision result with tier, action, message, and channel.
    """
    amount = session_data.get("amount", 0)
    is_first_time_recipient = session_data.get("is_first_time_recipient", False)
    local_recent_session_count = session_data.get("local_recent_session_count", 0)
    channel = session_data.get("channel", "unknown")

    # Blunt legacy rule
    if amount > 100000 and is_first_time_recipient is True:
        tier = "high"
        action = "block"
    elif local_recent_session_count == 0:
        tier = "medium"
        action = "step_up"
    else:
        tier = "low"
        action = "allow"

    return {
        "tier": tier,
        "action": action,
        "message": "offline_fallback_mode",
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

    # === decide_offline_fallback test cases ===
    # Case 9: amount > 100000 AND is_first_time_recipient → tier "high"
    case_9 = {"channel": "app", "amount": 150000, "is_first_time_recipient": True, "local_recent_session_count": 5}
    result_9 = decide_offline_fallback(case_9)
    print(result_9)

    # Case 10: local_recent_session_count == 0 → tier "medium"
    case_10 = {"channel": "ussd", "amount": 500, "is_first_time_recipient": False, "local_recent_session_count": 0}
    result_10 = decide_offline_fallback(case_10)
    print(result_10)

    # Case 11: default → tier "low"
    case_11 = {"channel": "app", "amount": 500, "is_first_time_recipient": False, "local_recent_session_count": 10}
    result_11 = decide_offline_fallback(case_11)
    print(result_11)

