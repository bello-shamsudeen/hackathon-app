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
    user_id = model_output.get("user_id", "")
    channel = model_output.get("channel", "")
    risk_score = model_output.get("risk_score", 0)
    top_features = model_output.get("top_features", [])

    if risk_score < 30:
        tier = "low"
        action = "allow"
    elif 30 <= risk_score <= 70:
        tier = "medium"
        action = "step_up"
    else:
        tier = "high"
        action = "block"

    elevated_features = []
    if channel in ELEVATION_THRESHOLDS:
        if isinstance(top_features, dict):
            feature_pairs = list(top_features.items())
        else:
            feature_pairs = top_features

        for feature_name, value in feature_pairs:
            threshold = ELEVATION_THRESHOLDS[channel].get(feature_name)
            if threshold is not None and abs(value) > threshold:
                elevated_features.append(feature_name)

    if len(elevated_features) == 1 and elevated_features[0] == "sim_swap_risk":
        tier = "low"
        action = "allow"

    session_count = model_output.get("session_count", 100)
    if session_count < 5 and tier == "high":
        tier = "medium"
        action = "step_up"

    if channel == "app" and len(elevated_features) == 1 and elevated_features[0] == "first_action_deviation" and tier == "high":
        tier = "medium"
        action = "step_up"

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

    if isinstance(top_features, dict):
        top_features = list(top_features.items())

    if tier == "low":
        message = "This transaction looks consistent with your normal activity."
    else:
        message = "This transaction was flagged because " + REASON_TEMPLATES.get(top_features[0][0], "unusual activity was detected") + ", and " + REASON_TEMPLATES.get(top_features[1][0], "additional unusual activity was detected") + "."

    return {
        "tier": tier,
        "action": action,
        "message": message,
        "user_id": user_id,
        "channel": channel,
    }


def decide_offline_fallback(transaction: dict) -> dict:
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