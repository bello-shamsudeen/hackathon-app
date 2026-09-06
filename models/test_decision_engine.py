import unittest
from models.decision_engine import make_decision

class TestDecisionEngine(unittest.TestCase):
    def setUp(self):
        self.mock_inputs = [
            {"user_id": "app_0001", "channel": "app", "risk_score": 15.0,
             "top_features": [["typing_speed_deviation", 0.2], ["amount_deviation", 0.1]],
             "session_count": 40},  # expect tier "low"

            {"user_id": "ussd_0002", "channel": "ussd", "risk_score": 45.0,
             "top_features": [["sim_swap_risk", 0.95], ["amount_deviation", 0.1]],
             "session_count": 30},  # expect tier "low"

            {"user_id": "app_0003", "channel": "app", "risk_score": 85.0,
             "top_features": [["pasted_char_ratio", 0.9], ["screen_sequence_anomaly", 0.6]],
             "session_count": 25},  # expect tier "high"

            {"user_id": "ussd_0004", "channel": "ussd", "risk_score": 78.0,
             "top_features": [["amount_deviation", 5.0], ["sim_swap_risk", 0.9]],
             "session_count": 2}   # expect tier "medium"
        ]

    def test_case_1(self):
        result = make_decision(self.mock_inputs[0])
        self.assertEqual(result["tier"], "low")
        print(f"Test Case 1 (app_0001): PASS (Tier: {result['tier']})")

    def test_case_2(self):
        result = make_decision(self.mock_inputs[1])
        self.assertEqual(result["tier"], "low")
        print(f"Test Case 2 (ussd_0002): PASS (Tier: {result['tier']})")

    def test_case_3(self):
        result = make_decision(self.mock_inputs[2])
        self.assertEqual(result["tier"], "high")
        print(f"Test Case 3 (app_0003): PASS (Tier: {result['tier']})")

    def test_case_4(self):
        result = make_decision(self.mock_inputs[3])
        self.assertEqual(result["tier"], "medium")
        print(f"Test Case 4 (ussd_0004): PASS (Tier: {result['tier']})")

    def test_case_5(self):
        case = {"user_id": "app_0005", "channel": "app", "risk_score": 85.0,
                "top_features": [["screen_sequence_anomaly", 0.5], ["amount_deviation", 0.3]],
                "session_count": 25}
        result = make_decision(case)
        self.assertEqual(result["tier"], "medium")
        print(f"Test Case 5 (app_0005): PASS (Tier: {result['tier']})")

    def test_case_6(self):
        case = {"user_id": "app_0006", "channel": "app", "risk_score": 85.0,
                "top_features": [["screen_sequence_anomaly", 0.5], ["pasted_char_ratio", 0.9]],
                "session_count": 25}
        result = make_decision(case)
        self.assertEqual(result["tier"], "high")
        print(f"Test Case 6 (app_0006): PASS (Tier: {result['tier']})")

if __name__ == '__main__':
    unittest.main()
