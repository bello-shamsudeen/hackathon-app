ELEVATION_THRESHOLDS = {
    "app": {
        "typing_speed_deviation": 2.0,
        "pasted_char_ratio": 0.65,
        "screen_sequence_anomaly": 0.34,
        "amount_deviation": 1.26
    },
    "ussd": {
        "amount_deviation": 1.81,
        "time_of_day_deviation": 1.96,
        "session_retry_deviation": 1.29,
        "sim_swap_risk": 0.91
    }
}

REASON_TEMPLATES = {
    "typing_speed_deviation": "you typed at an unusual speed for you",
    "pasted_char_ratio": "your details were pasted rather than typed",
    "screen_sequence_anomaly": "you skipped steps you normally go through",
    "amount_deviation": "this amount is unusual for you",
    "time_of_day_deviation": "this was sent at an unusual time for you",
    "session_retry_deviation": "there were more retries than usual",
    "sim_swap_risk": "your SIM was recently changed"
}

def make_decision(model_output: dict) -> dict:
    risk_score = model_output.get("risk_score", 0)
    top_features = model_output.get("top_features", [])
    channel = model_output.get("channel")
    
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
        
    # 2. Guardrail 1: Elevation Override (sim_swap_risk)
    applied_sim_swap_override = False
    elevated_features = []
    
    if channel in ELEVATION_THRESHOLDS:
        for feature_name, value in top_features:
            threshold = ELEVATION_THRESHOLDS[channel].get(feature_name)
            if threshold is not None and abs(value) > threshold:
                elevated_features.append(feature_name)
        
        # Override condition: ONLY elevated feature is "sim_swap_risk"
        if len(elevated_features) == 1 and elevated_features[0] == "sim_swap_risk":
            tier = "low"
            action = "allow"
            applied_sim_swap_override = True
            
    # Guardrail 3: App screen_sequence_anomaly override
    if channel == "app" and len(elevated_features) == 1 and elevated_features[0] == "screen_sequence_anomaly" and tier == "high":
        tier = "medium"
        action = "step_up"
        
    # 3. Guardrail 2: New user (session_count < 5) downgrade
    session_count = model_output.get("session_count", 100)
    
    if session_count < 5 and tier == "high":
        if not applied_sim_swap_override:
            tier = "medium"
            action = "step_up"
            
    # 4. Generate Message
    if tier == "low":
        message = "This transaction looks consistent with your normal activity."
    else:
        if len(top_features) >= 2:
            feat1 = top_features[0][0]
            feat2 = top_features[1][0]
            message = f"This transaction was flagged because {REASON_TEMPLATES.get(feat1, 'unknown factor')}, and {REASON_TEMPLATES.get(feat2, 'unknown factor')}."
        else:
            message = "This transaction was flagged due to activity anomalies."
        
    return {
        "tier": tier,
        "action": action,
        "message": message,
        "user_id": model_output["user_id"],
        "channel": model_output["channel"]
    }

if __name__ == "__main__":
    mock_inputs = [
        {"user_id": "app_0001", "channel": "app", "risk_score": 15.0,
         "top_features": [["typing_speed_deviation", 0.2], ["amount_deviation", 0.1]],
         "session_count": 40},

        {"user_id": "ussd_0002", "channel": "ussd", "risk_score": 45.0,
         "top_features": [["sim_swap_risk", 0.95], ["amount_deviation", 0.1]],
         "session_count": 30},

        {"user_id": "app_0003", "channel": "app", "risk_score": 85.0,
         "top_features": [["pasted_char_ratio", 0.9], ["screen_sequence_anomaly", 0.6]],
         "session_count": 25},

        {"user_id": "ussd_0004", "channel": "ussd", "risk_score": 78.0,
         "top_features": [["amount_deviation", 5.0], ["sim_swap_risk", 0.9]],
         "session_count": 2},
         
        {"user_id": "app_0005", "channel": "app", "risk_score": 85.0,
         "top_features": [["screen_sequence_anomaly", 0.5], ["amount_deviation", 0.3]],
         "session_count": 25},

        {"user_id": "app_0006", "channel": "app", "risk_score": 85.0,
         "top_features": [["screen_sequence_anomaly", 0.5], ["pasted_char_ratio", 0.9]],
         "session_count": 25}
    ]
    
    for case in mock_inputs:
        result = make_decision(case)
        print(result)

