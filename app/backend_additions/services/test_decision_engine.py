"""
Division 4/5 — regression tests for the decision engine guardrails.
These are the SAME 4 mock cases from the teammate's Brief B. If either
guardrail ever breaks, this is what catches it — run this after ANY change
to decision_engine.py, not just once.
"""
import sys
sys.path.append("backend/app/services")
from decision_engine import make_decision

mock_inputs = [
    {"user_id": "app_0001", "channel": "app", "risk_score": 15.0,
     "top_features": [["typing_speed_deviation", 0.2], ["amount_deviation", 0.1]],
     "session_count": 40},  # EXPECT: tier "low"

    {"user_id": "ussd_0002", "channel": "ussd", "risk_score": 45.0,
     "top_features": [["sim_swap_risk", 0.95], ["amount_deviation", 0.1]],
     "session_count": 30},  # EXPECT: tier "low" (Guardrail 1)

    {"user_id": "app_0003", "channel": "app", "risk_score": 85.0,
     "top_features": [["pasted_char_ratio", 0.9], ["screen_sequence_anomaly", 0.6]],
     "session_count": 25},  # EXPECT: tier "high"

    {"user_id": "ussd_0004", "channel": "ussd", "risk_score": 78.0,
     "top_features": [["amount_deviation", 5.0], ["sim_swap_risk", 0.9]],
     "session_count": 2},  # EXPECT: tier "medium" (Guardrail 2)
]

expected_tiers = ["low", "low", "high", "medium"]

if __name__ == "__main__":
    all_pass = True
    for i, (inp, expected) in enumerate(zip(mock_inputs, expected_tiers), 1):
        result = make_decision(inp)
        status = "PASS" if result["tier"] == expected else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"Case {i}: expected='{expected}' got='{result['tier']}' [{status}]")
        print(f"  action={result['action']} message=\"{result['message']}\"")

    print("\n" + ("ALL PASS" if all_pass else "SOME FAILED — DO NOT PROCEED TO DIVISION 5"))
