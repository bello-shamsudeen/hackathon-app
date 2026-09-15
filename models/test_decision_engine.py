import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.decision_engine import make_decision, decide_offline_fallback


class TestDecisionEngine(unittest.TestCase):
    """Test cases for make_decision function."""

    def test_case_1_low_tier_app_client_small_anomaly(self):
        """Case 1: app_0001 - risk_score 15.0, low tier expected."""
        case = {
            "user_id": "app_0001",
            "channel": "app",
            "risk_score": 15.0,
            "top_features": [["typing_speed_deviation", 0.2], ["amount_deviation", 0.1]],
            "session_count": 40
        }
        result = make_decision(case)
        self.assertEqual(result["tier"], "low")

    def test_case_2_low_tier_ussd_sim_swap_only(self):
        """Case 2: ussd_0002 - sim_swap_risk alone triggers guardrail -> low tier."""
        case = {
            "user_id": "ussd_0002",
            "channel": "ussd",
            "risk_score": 45.0,
            "top_features": [["sim_swap_risk", 0.95], ["amount_deviation", 0.1]],
            "session_count": 30
        }
        result = make_decision(case)
        self.assertEqual(result["tier"], "low")

    def test_case_3_high_tier_app_pasted_first_action(self):
        """Case 3: app_0003 - high risk with pasted + first action -> high tier."""
        case = {
            "user_id": "app_0003",
            "channel": "app",
            "risk_score": 85.0,
            "top_features": [["pasted_char_ratio", 0.9], ["first_action_deviation", 1.0]],
            "session_count": 25
        }
        result = make_decision(case)
        self.assertEqual(result["tier"], "high")

    def test_case_4_medium_tier_ussd_cold_start(self):
        """Case 4: ussd_0004 - cold-start guardrail downgrades high -> medium."""
        case = {
            "user_id": "ussd_0004",
            "channel": "ussd",
            "risk_score": 78.0,
            "top_features": [["amount_deviation", 5.0], ["sim_swap_risk", 0.9]],
            "session_count": 2
        }
        result = make_decision(case)
        self.assertEqual(result["tier"], "medium")

    def test_case_5_medium_tier_app_first_action_deviation(self):
        """Case 5: app_0005 - first_action_deviation alone downgrades high -> medium."""
        case = {
            "user_id": "app_0005",
            "channel": "app",
            "risk_score": 85.0,
            "top_features": [["first_action_deviation", 1.0], ["amount_deviation", 0.3]],
            "session_count": 25
        }
        result = make_decision(case)
        self.assertEqual(result["tier"], "medium")

    def test_case_6_medium_tier_app_typing_deviation(self):
        """Case 6: app_0006 - typing_speed_deviation alone downgrades high -> medium."""
        case = {
            "user_id": "app_0006",
            "channel": "app",
            "risk_score": 85.0,
            "top_features": [["typing_speed_deviation", 3.5], ["amount_deviation", 0.3]],
            "session_count": 25
        }
        result = make_decision(case)
        self.assertEqual(result["tier"], "medium")


class TestDecideOfflineFallback(unittest.TestCase):
    """Test cases for decide_offline_fallback function."""

    def test_case_a_low_tier_small_amount(self):
        """Case (a): app_0008 - small amount, not first-time -> low tier."""
        case = {
            "user_id": "app_0008",
            "channel": "app",
            "amount": 5000,
            "is_first_time_recipient": False
        }
        result = decide_offline_fallback(case)
        self.assertEqual(result["tier"], "low")

    def test_case_b_medium_tier_large_amount(self):
        """Case (b): app_0009 - large amount > 100000 -> medium tier."""
        case = {
            "user_id": "app_0009",
            "channel": "app",
            "amount": 250000,
            "is_first_time_recipient": False
        }
        result = decide_offline_fallback(case)
        self.assertEqual(result["tier"], "medium")

    def test_case_c_medium_tier_first_time_recipient(self):
        """Case (c): app_0010 - first-time recipient -> medium tier."""
        case = {
            "user_id": "app_0010",
            "channel": "app",
            "amount": 5000,
            "is_first_time_recipient": True
        }
        result = decide_offline_fallback(case)
        self.assertEqual(result["tier"], "medium")

    def test_case_d_medium_tier_both_conditions(self):
        """Case (d): app_0011 - both amount > 100000 AND first-time -> medium tier."""
        case = {
            "user_id": "app_0011",
            "channel": "app",
            "amount": 250000,
            "is_first_time_recipient": True
        }
        result = decide_offline_fallback(case)
        self.assertEqual(result["tier"], "medium")


if __name__ == '__main__':
    unittest.main()
